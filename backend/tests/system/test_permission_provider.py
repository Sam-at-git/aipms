"""
RBACPermissionProvider tests.

Covers:
- has_permission: checks permission code in resolved set
- get_user_permissions: DB lookup + caching
- get_user_roles: DB lookup + caching
- invalidate_user: clears per-user caches
- invalidate_all: clears all caches
"""
from unittest.mock import MagicMock, patch

import pytest

from app.system.services.permission_provider import RBACPermissionProvider


@pytest.fixture
def mock_db():
    """A mock DB session."""
    return MagicMock()


@pytest.fixture
def mock_db_factory(mock_db):
    """Factory that returns the mock DB session."""
    return MagicMock(return_value=mock_db)


@pytest.fixture
def provider(mock_db_factory):
    return RBACPermissionProvider(db_session_factory=mock_db_factory)


# ── has_permission ────────────────────────────────────────


class TestHasPermission:

    def test_has_permission_true(self, provider):
        with patch.object(
            provider, "get_user_permissions", return_value={"room:view", "room:edit"}
        ):
            assert provider.has_permission(1, "room:view") is True

    def test_has_permission_false(self, provider):
        with patch.object(
            provider, "get_user_permissions", return_value={"room:view"}
        ):
            assert provider.has_permission(1, "room:delete") is False

    def test_has_permission_empty_set(self, provider):
        with patch.object(
            provider, "get_user_permissions", return_value=set()
        ):
            assert provider.has_permission(1, "any") is False


# ── get_user_permissions ──────────────────────────────────


class TestGetUserPermissions:

    def test_cache_miss_fetches_from_db(self, provider, mock_db_factory, mock_db):
        mock_perm_service = MagicMock()
        mock_perm_service.get_user_permissions.return_value = {"room:view", "task:view"}

        with patch(
            "app.system.services.permission_provider.PermissionService",
            return_value=mock_perm_service,
        ):
            perms = provider.get_user_permissions(42)

        assert perms == {"room:view", "task:view"}
        mock_db_factory.assert_called_once()
        mock_db.close.assert_called_once()

    def test_cache_hit_no_db_call(self, provider, mock_db_factory):
        # Seed cache
        provider._permission_cache[42] = {"cached:perm"}

        perms = provider.get_user_permissions(42)

        assert perms == {"cached:perm"}
        mock_db_factory.assert_not_called()

    def test_caches_result(self, provider, mock_db_factory, mock_db):
        mock_perm_service = MagicMock()
        mock_perm_service.get_user_permissions.return_value = {"x"}

        with patch(
            "app.system.services.permission_provider.PermissionService",
            return_value=mock_perm_service,
        ):
            provider.get_user_permissions(99)

        # Second call should use cache
        mock_db_factory.reset_mock()
        perms = provider.get_user_permissions(99)
        assert perms == {"x"}
        mock_db_factory.assert_not_called()


# ── get_user_roles ────────────────────────────────────────


class TestGetUserRoles:

    def test_cache_miss_fetches_from_db(self, provider, mock_db_factory, mock_db):
        mock_role1 = MagicMock()
        mock_role1.code = "admin"
        mock_role2 = MagicMock()
        mock_role2.code = "editor"

        mock_perm_service = MagicMock()
        mock_perm_service.get_user_roles.return_value = [mock_role1, mock_role2]

        with patch(
            "app.system.services.permission_provider.PermissionService",
            return_value=mock_perm_service,
        ):
            roles = provider.get_user_roles(7)

        assert roles == ["admin", "editor"]
        mock_db_factory.assert_called_once()
        mock_db.close.assert_called_once()

    def test_cache_hit(self, provider, mock_db_factory):
        provider._role_cache[7] = ["cached_role"]
        roles = provider.get_user_roles(7)
        assert roles == ["cached_role"]
        mock_db_factory.assert_not_called()

    def test_caches_result(self, provider, mock_db_factory, mock_db):
        mock_role = MagicMock()
        mock_role.code = "viewer"
        mock_perm_service = MagicMock()
        mock_perm_service.get_user_roles.return_value = [mock_role]

        with patch(
            "app.system.services.permission_provider.PermissionService",
            return_value=mock_perm_service,
        ):
            provider.get_user_roles(10)

        mock_db_factory.reset_mock()
        roles = provider.get_user_roles(10)
        assert roles == ["viewer"]
        mock_db_factory.assert_not_called()


# ── invalidate_user ───────────────────────────────────────


class TestInvalidateUser:

    def test_invalidate_clears_both_caches(self, provider):
        provider._permission_cache[1] = {"a"}
        provider._role_cache[1] = ["b"]

        provider.invalidate_user(1)

        assert 1 not in provider._permission_cache
        assert 1 not in provider._role_cache

    def test_invalidate_nonexistent_user(self, provider):
        """Invalidating a user not in cache should not raise."""
        provider.invalidate_user(999)

    def test_invalidate_one_user_does_not_affect_other(self, provider):
        provider._permission_cache[1] = {"a"}
        provider._permission_cache[2] = {"b"}
        provider._role_cache[1] = ["r1"]
        provider._role_cache[2] = ["r2"]

        provider.invalidate_user(1)

        assert 1 not in provider._permission_cache
        assert 2 in provider._permission_cache
        assert 1 not in provider._role_cache
        assert 2 in provider._role_cache


# ── invalidate_all ────────────────────────────────────────


class TestInvalidateAll:

    def test_invalidate_all_clears_everything(self, provider):
        provider._permission_cache[1] = {"a"}
        provider._permission_cache[2] = {"b"}
        provider._role_cache[1] = ["r1"]
        provider._role_cache[2] = ["r2"]

        provider.invalidate_all()

        assert len(provider._permission_cache) == 0
        assert len(provider._role_cache) == 0

    def test_invalidate_all_empty_cache(self, provider):
        """Calling invalidate_all on empty cache should not raise."""
        provider.invalidate_all()
        assert len(provider._permission_cache) == 0
        assert len(provider._role_cache) == 0
