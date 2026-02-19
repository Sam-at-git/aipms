"""
ConfigService extended coverage tests.

Focuses on uncovered paths in config_service.py:
- _is_sensitive_key: various patterns
- _mask_value: edge cases (short values, long values)
- _cast_value: number, boolean, json, string
- get_value: typed value retrieval
- get_groups: distinct group listing
- get_public_configs: public config filtering
- create: duplicate key error
- update: key not found
- update_by_id: id not found, partial updates
- delete: not found, system config protection
- to_api_dict: sensitive masking, non-sensitive display
- reset_cache: clears global cache
- _ensure_cache / _load_cache: cache loading
"""
import json

import pytest

from app.system.models.config import SysConfig
from app.system.services.config_service import (
    ConfigService,
    _is_sensitive_key,
    _mask_value,
)


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset config cache before and after each test."""
    ConfigService.reset_cache()
    yield
    ConfigService.reset_cache()


# ── _is_sensitive_key ─────────────────────────────────────


class TestIsSensitiveKey:

    def test_api_key(self):
        assert _is_sensitive_key("llm.api_key") is True

    def test_secret(self):
        assert _is_sensitive_key("jwt_secret") is True

    def test_password(self):
        assert _is_sensitive_key("smtp_password") is True

    def test_token(self):
        assert _is_sensitive_key("refresh_token") is True

    def test_credential(self):
        assert _is_sensitive_key("db_credential") is True

    def test_normal_key(self):
        assert _is_sensitive_key("site.name") is False

    def test_case_insensitive(self):
        assert _is_sensitive_key("LLM.API_KEY") is True

    def test_empty_string(self):
        assert _is_sensitive_key("") is False


# ── _mask_value ───────────────────────────────────────────


class TestMaskValue:

    def test_empty_string(self):
        assert _mask_value("") == "****"

    def test_short_value(self):
        assert _mask_value("ab") == "****"
        assert _mask_value("abcd") == "****"

    def test_normal_value(self):
        result = _mask_value("sk-abc123xyz789")
        assert result == "sk****89"
        assert "abc123" not in result

    def test_five_chars(self):
        result = _mask_value("12345")
        assert result == "12****45"


# ── ConfigService._cast_value ─────────────────────────────


class TestCastValue:

    def test_string_type(self):
        assert ConfigService._cast_value("hello", "string") == "hello"

    def test_number_int(self):
        assert ConfigService._cast_value("42", "number") == 42

    def test_number_float(self):
        assert ConfigService._cast_value("3.14", "number") == 3.14

    def test_number_invalid(self):
        assert ConfigService._cast_value("abc", "number") == "abc"

    def test_boolean_true_values(self):
        assert ConfigService._cast_value("true", "boolean") is True
        assert ConfigService._cast_value("1", "boolean") is True
        assert ConfigService._cast_value("yes", "boolean") is True
        assert ConfigService._cast_value("True", "boolean") is True

    def test_boolean_false_values(self):
        assert ConfigService._cast_value("false", "boolean") is False
        assert ConfigService._cast_value("0", "boolean") is False
        assert ConfigService._cast_value("no", "boolean") is False

    def test_json_valid(self):
        val = ConfigService._cast_value('{"a": 1}', "json")
        assert val == {"a": 1}

    def test_json_array(self):
        val = ConfigService._cast_value('[1, 2, 3]', "json")
        assert val == [1, 2, 3]

    def test_json_invalid(self):
        val = ConfigService._cast_value("{bad json", "json")
        assert val == "{bad json"

    def test_unknown_type_returns_string(self):
        assert ConfigService._cast_value("val", "unknown") == "val"


# ── ConfigService Read Operations ─────────────────────────


class TestConfigServiceRead:

    def test_get_all_empty(self, db_session):
        svc = ConfigService(db_session)
        assert svc.get_all() == []

    def test_get_all_with_group_filter(self, db_session):
        svc = ConfigService(db_session)
        svc.create(key="sys.a", value="1", name="A", group="system")
        svc.create(key="llm.b", value="2", name="B", group="llm")

        system_configs = svc.get_all(group="system")
        assert len(system_configs) == 1
        assert system_configs[0].key == "sys.a"

    def test_get_by_key_from_cache(self, db_session):
        svc = ConfigService(db_session)
        svc.create(key="cached.key", value="val", name="Cached")

        # First get loads cache, second should use it
        c1 = svc.get_by_key("cached.key")
        c2 = svc.get_by_key("cached.key")
        assert c1.value == "val"
        assert c2.value == "val"

    def test_get_by_key_not_found(self, db_session):
        svc = ConfigService(db_session)
        svc._load_cache()
        assert svc.get_by_key("nonexistent") is None

    def test_get_by_key_fallback_to_db(self, db_session):
        """When key is not in cache but exists in DB, it should be fetched."""
        svc = ConfigService(db_session)
        # Create but don't go through get_by_key first
        config = SysConfig(
            group="test", key="db.fallback", value="found",
            value_type="string", name="Fallback"
        )
        db_session.add(config)
        db_session.commit()

        svc._load_cache()
        # The key IS in cache now because _load_cache loads all. Test the fallback
        # by directly clearing the key from cache.
        from app.system.services import config_service
        config_service._config_cache.pop("db.fallback", None)

        result = svc.get_by_key("db.fallback")
        assert result is not None
        assert result.value == "found"

    def test_get_value_typed(self, db_session):
        svc = ConfigService(db_session)
        svc.create(key="max.retry", value="3", name="Max Retry", value_type="number")
        assert svc.get_value("max.retry") == 3

    def test_get_value_default(self, db_session):
        svc = ConfigService(db_session)
        svc._load_cache()
        assert svc.get_value("missing.key", default=10) == 10

    def test_get_groups(self, db_session):
        svc = ConfigService(db_session)
        svc.create(key="g1.a", value="", name="A", group="group1")
        svc.create(key="g2.b", value="", name="B", group="group2")
        svc.create(key="g1.c", value="", name="C", group="group1")

        groups = svc.get_groups()
        assert "group1" in groups
        assert "group2" in groups

    def test_get_public_configs(self, db_session):
        svc = ConfigService(db_session)
        svc.create(key="public.key", value="pub", name="Public", is_public=True)
        svc.create(key="private.key", value="priv", name="Private", is_public=False)

        public = svc.get_public_configs()
        assert len(public) == 1
        assert public[0].key == "public.key"


# ── ConfigService Write Operations ────────────────────────


class TestConfigServiceWrite:

    def test_create_success(self, db_session):
        svc = ConfigService(db_session)
        config = svc.create(
            key="new.key",
            value="new_val",
            name="New Config",
            group="test",
            value_type="string",
            description="A test config",
            is_public=False,
            is_system=False,
            updated_by=1,
        )
        assert config.id is not None
        assert config.key == "new.key"
        assert config.updated_by == 1

    def test_create_duplicate_raises(self, db_session):
        svc = ConfigService(db_session)
        svc.create(key="dup.key", value="v1", name="Dup")
        with pytest.raises(ValueError, match="已存在"):
            svc.create(key="dup.key", value="v2", name="Dup2")

    def test_update_success(self, db_session):
        svc = ConfigService(db_session)
        svc.create(key="upd.key", value="old", name="Update Test")
        config = svc.update("upd.key", "new", updated_by=2)
        assert config.value == "new"
        assert config.updated_by == 2

    def test_update_not_found(self, db_session):
        svc = ConfigService(db_session)
        with pytest.raises(ValueError, match="不存在"):
            svc.update("missing", "val")

    def test_update_without_updated_by(self, db_session):
        svc = ConfigService(db_session)
        svc.create(key="no.updater", value="old", name="No Updater")
        config = svc.update("no.updater", "new")
        assert config.value == "new"

    def test_update_by_id_success(self, db_session):
        svc = ConfigService(db_session)
        config = svc.create(key="byid.key", value="old", name="By ID")
        updated = svc.update_by_id(config.id, value="new", description="Updated")
        assert updated.value == "new"
        assert updated.description == "Updated"

    def test_update_by_id_not_found(self, db_session):
        svc = ConfigService(db_session)
        with pytest.raises(ValueError, match="不存在"):
            svc.update_by_id(99999, value="x")

    def test_update_by_id_ignores_unknown_attrs(self, db_session):
        svc = ConfigService(db_session)
        config = svc.create(key="attr.test", value="v", name="Attr Test")
        updated = svc.update_by_id(config.id, nonexistent_field="ignored", value="new")
        assert updated.value == "new"

    def test_delete_success(self, db_session):
        svc = ConfigService(db_session)
        config = svc.create(key="del.key", value="", name="Delete Me")
        assert svc.delete(config.id) is True
        assert svc.get_by_key("del.key") is None

    def test_delete_not_found(self, db_session):
        svc = ConfigService(db_session)
        with pytest.raises(ValueError, match="不存在"):
            svc.delete(99999)

    def test_delete_system_config_blocked(self, db_session):
        svc = ConfigService(db_session)
        config = svc.create(key="sys.protected", value="x", name="System", is_system=True)
        with pytest.raises(ValueError, match="不可删除"):
            svc.delete(config.id)


# ── ConfigService to_api_dict ─────────────────────────────


class TestConfigServiceToApiDict:

    def test_normal_key_not_masked(self, db_session):
        svc = ConfigService(db_session)
        config = svc.create(key="site.name", value="Hotel PMS", name="Site Name")
        d = svc.to_api_dict(config)
        assert d["value"] == "Hotel PMS"
        assert d["key"] == "site.name"
        assert "id" in d
        assert "group" in d

    def test_sensitive_key_masked(self, db_session):
        svc = ConfigService(db_session)
        config = svc.create(key="llm.api_key", value="sk-abc123xyz789", name="API Key")
        d = svc.to_api_dict(config, mask_sensitive=True)
        assert d["value"] == "sk****89"

    def test_sensitive_key_not_masked_when_disabled(self, db_session):
        svc = ConfigService(db_session)
        config = svc.create(key="llm.api_key", value="sk-abc123xyz789", name="API Key")
        d = svc.to_api_dict(config, mask_sensitive=False)
        assert d["value"] == "sk-abc123xyz789"

    def test_dict_fields_complete(self, db_session):
        svc = ConfigService(db_session)
        config = svc.create(
            key="complete.test",
            value="val",
            name="Complete",
            group="test",
            value_type="string",
            description="desc",
            is_public=True,
            is_system=True,
            updated_by=5,
        )
        d = svc.to_api_dict(config)
        expected_keys = {
            "id", "group", "key", "value", "value_type", "name",
            "description", "is_public", "is_system", "created_at",
            "updated_at", "updated_by",
        }
        assert expected_keys.issubset(set(d.keys()))
        assert d["updated_by"] == 5
        assert d["is_public"] is True

    def test_dict_created_at_format(self, db_session):
        svc = ConfigService(db_session)
        config = svc.create(key="time.test", value="t", name="Time")
        d = svc.to_api_dict(config)
        # created_at should be ISO format string or None
        assert d["created_at"] is None or isinstance(d["created_at"], str)


# ── Cache Behavior ────────────────────────────────────────


class TestConfigCache:

    def test_reset_cache(self, db_session):
        svc = ConfigService(db_session)
        svc.create(key="cache.test", value="v", name="Cache Test")
        svc.get_by_key("cache.test")
        # Cache should have data now
        ConfigService.reset_cache()
        # After reset, _ensure_cache should reload
        from app.system.services import config_service
        assert config_service._cache_loaded is False
        assert len(config_service._config_cache) == 0

    def test_ensure_cache_loads_once(self, db_session):
        svc = ConfigService(db_session)
        svc.create(key="once.test", value="v", name="Once")
        svc._ensure_cache()
        # Calling again should not reload
        from app.system.services import config_service
        assert config_service._cache_loaded is True
        svc._ensure_cache()  # Should be no-op
        assert config_service._cache_loaded is True
