"""
RBAC Service extended coverage tests.

Focuses on uncovered paths in rbac_service.py:
- RoleService: update_role code conflicts, delete_role cascades, get_role_permissions,
  add_permission, remove_permission
- PermissionService: update_permission code conflict, delete_permission in use,
  get_permission_tree hierarchies, get_user_permissions aggregation,
  assign_user_roles, add_user_role, remove_user_role
"""
import pytest

from app.hotel.models.ontology import Employee, EmployeeRole
from app.security.auth import get_password_hash
from app.system.models.rbac import (
    SysPermission,
    SysRole,
    SysRolePermission,
    SysUserRole,
)
from app.system.services.rbac_service import PermissionService, RoleService


# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture
def role_svc(db_session):
    return RoleService(db_session)


@pytest.fixture
def perm_svc(db_session):
    return PermissionService(db_session)


@pytest.fixture
def sample_role(db_session) -> SysRole:
    role = SysRole(code="test_role", name="Test Role", sort_order=1)
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture
def system_role(db_session) -> SysRole:
    role = SysRole(code="sys_builtin", name="System Built-in", is_system=True)
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture
def sample_perm(db_session) -> SysPermission:
    perm = SysPermission(code="test:view", name="Test View", type="api", resource="test", action="view")
    db_session.add(perm)
    db_session.flush()
    return perm


@pytest.fixture
def sample_perm_2(db_session) -> SysPermission:
    perm = SysPermission(code="test:edit", name="Test Edit", type="api", resource="test", action="edit")
    db_session.add(perm)
    db_session.flush()
    return perm


@pytest.fixture
def test_user(db_session) -> Employee:
    user = Employee(
        username="rbac_test_user",
        password_hash=get_password_hash("123456"),
        name="RBAC Test User",
        role=EmployeeRole.RECEPTIONIST,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ── RoleService Tests ─────────────────────────────────────


class TestRoleServiceGetRoles:

    def test_get_roles_empty(self, role_svc):
        assert role_svc.get_roles() == []

    def test_get_roles_excludes_inactive(self, db_session, role_svc):
        db_session.add(SysRole(code="active", name="Active", is_active=True))
        db_session.add(SysRole(code="inactive", name="Inactive", is_active=False))
        db_session.flush()

        active_roles = role_svc.get_roles(include_inactive=False)
        assert len(active_roles) == 1
        assert active_roles[0].code == "active"

    def test_get_roles_includes_inactive(self, db_session, role_svc):
        db_session.add(SysRole(code="a", name="A", is_active=True))
        db_session.add(SysRole(code="b", name="B", is_active=False))
        db_session.flush()

        all_roles = role_svc.get_roles(include_inactive=True)
        assert len(all_roles) == 2


class TestRoleServiceGetById:

    def test_found(self, role_svc, sample_role):
        role = role_svc.get_role_by_id(sample_role.id)
        assert role is not None
        assert role.code == "test_role"

    def test_not_found(self, role_svc):
        assert role_svc.get_role_by_id(99999) is None


class TestRoleServiceGetByCode:

    def test_found(self, role_svc, sample_role):
        role = role_svc.get_role_by_code("test_role")
        assert role is not None

    def test_not_found(self, role_svc):
        assert role_svc.get_role_by_code("nope") is None


class TestRoleServiceCreate:

    def test_create_success(self, role_svc):
        role = role_svc.create_role(
            code="new_role",
            name="New Role",
            description="desc",
            data_scope="DEPT",
            sort_order=5,
        )
        assert role.id is not None
        assert role.code == "new_role"
        assert role.data_scope == "DEPT"
        assert role.sort_order == 5

    def test_create_duplicate_raises(self, role_svc, sample_role):
        with pytest.raises(ValueError, match="已存在"):
            role_svc.create_role(code="test_role", name="Dup")


class TestRoleServiceUpdate:

    def test_update_name(self, role_svc, sample_role):
        updated = role_svc.update_role(sample_role.id, name="Updated Name")
        assert updated.name == "Updated Name"

    def test_update_not_found(self, role_svc):
        with pytest.raises(ValueError, match="不存在"):
            role_svc.update_role(99999, name="X")

    def test_update_code_to_existing_raises(self, db_session, role_svc, sample_role):
        db_session.add(SysRole(code="other_role", name="Other"))
        db_session.flush()

        with pytest.raises(ValueError, match="已存在"):
            role_svc.update_role(sample_role.id, code="other_role")

    def test_update_code_same_value_ok(self, role_svc, sample_role):
        """Updating code to the same value should not raise."""
        updated = role_svc.update_role(sample_role.id, code="test_role", name="Same Code")
        assert updated.code == "test_role"
        assert updated.name == "Same Code"

    def test_update_nonexistent_attr_ignored(self, role_svc, sample_role):
        """Attributes not on the model should be silently ignored."""
        updated = role_svc.update_role(sample_role.id, nonexistent="value", name="Good")
        assert updated.name == "Good"


class TestRoleServiceDelete:

    def test_delete_success(self, role_svc, sample_role, db_session):
        role_id = sample_role.id
        role_svc.delete_role(role_id)
        assert role_svc.get_role_by_id(role_id) is None

    def test_delete_not_found(self, role_svc):
        with pytest.raises(ValueError, match="不存在"):
            role_svc.delete_role(99999)

    def test_delete_system_role_blocked(self, role_svc, system_role):
        with pytest.raises(ValueError, match="不可删除"):
            role_svc.delete_role(system_role.id)

    def test_delete_cascades_permissions_and_user_roles(
        self, db_session, role_svc, sample_role, sample_perm, test_user
    ):
        """Deleting a role should remove its role-permission and user-role mappings."""
        db_session.add(SysRolePermission(role_id=sample_role.id, permission_id=sample_perm.id))
        db_session.add(SysUserRole(user_id=test_user.id, role_id=sample_role.id))
        db_session.flush()

        role_svc.delete_role(sample_role.id)

        # Verify cascaded deletes
        rp_count = db_session.query(SysRolePermission).filter(
            SysRolePermission.role_id == sample_role.id
        ).count()
        ur_count = db_session.query(SysUserRole).filter(
            SysUserRole.role_id == sample_role.id
        ).count()
        assert rp_count == 0
        assert ur_count == 0


class TestRoleServicePermissions:

    def test_get_role_permissions_empty(self, role_svc, sample_role):
        perms = role_svc.get_role_permissions(sample_role.id)
        assert perms == []

    def test_get_role_permissions_not_found(self, role_svc):
        perms = role_svc.get_role_permissions(99999)
        assert perms == []

    def test_assign_permissions(self, db_session, role_svc, sample_role, sample_perm, sample_perm_2):
        role_svc.assign_permissions(sample_role.id, [sample_perm.id, sample_perm_2.id])
        db_session.commit()
        db_session.expire_all()
        perms = role_svc.get_role_permissions(sample_role.id)
        assert len(perms) == 2
        perm_codes = {p.code for p in perms}
        assert "test:view" in perm_codes
        assert "test:edit" in perm_codes

    def test_assign_permissions_replaces_existing(self, db_session, role_svc, sample_role, sample_perm, sample_perm_2):
        """assign_permissions should replace, not append."""
        role_svc.assign_permissions(sample_role.id, [sample_perm.id, sample_perm_2.id])
        db_session.commit()
        role_svc.assign_permissions(sample_role.id, [sample_perm.id])
        db_session.commit()
        db_session.expire_all()
        perms = role_svc.get_role_permissions(sample_role.id)
        assert len(perms) == 1

    def test_assign_permissions_role_not_found(self, role_svc):
        with pytest.raises(ValueError, match="不存在"):
            role_svc.assign_permissions(99999, [1])

    def test_add_permission(self, db_session, role_svc, sample_role, sample_perm):
        role_svc.add_permission(sample_role.id, sample_perm.id)
        perms = role_svc.get_role_permissions(sample_role.id)
        assert len(perms) == 1

    def test_add_permission_duplicate_noop(self, db_session, role_svc, sample_role, sample_perm):
        """Adding the same permission twice should not create duplicates."""
        role_svc.add_permission(sample_role.id, sample_perm.id)
        role_svc.add_permission(sample_role.id, sample_perm.id)
        perms = role_svc.get_role_permissions(sample_role.id)
        assert len(perms) == 1

    def test_remove_permission(self, db_session, role_svc, sample_role, sample_perm):
        role_svc.add_permission(sample_role.id, sample_perm.id)
        role_svc.remove_permission(sample_role.id, sample_perm.id)
        perms = role_svc.get_role_permissions(sample_role.id)
        assert len(perms) == 0

    def test_remove_permission_nonexistent_noop(self, role_svc, sample_role):
        """Removing a non-existent mapping should not raise."""
        role_svc.remove_permission(sample_role.id, 99999)


# ── PermissionService Tests ───────────────────────────────


class TestPermissionServiceGet:

    def test_get_permissions_empty(self, perm_svc):
        assert perm_svc.get_permissions() == []

    def test_get_permissions_filter_by_type(self, db_session, perm_svc):
        db_session.add(SysPermission(code="menu:a", name="Menu A", type="menu"))
        db_session.add(SysPermission(code="api:a", name="API A", type="api"))
        db_session.flush()

        menus = perm_svc.get_permissions(perm_type="menu")
        assert len(menus) == 1
        assert menus[0].type == "menu"

    def test_get_permissions_excludes_inactive(self, db_session, perm_svc):
        db_session.add(SysPermission(code="active:p", name="Active", is_active=True))
        db_session.add(SysPermission(code="inactive:p", name="Inactive", is_active=False))
        db_session.flush()

        perms = perm_svc.get_permissions()
        assert len(perms) == 1
        assert perms[0].code == "active:p"


class TestPermissionServiceGetById:

    def test_found(self, perm_svc, sample_perm):
        p = perm_svc.get_permission_by_id(sample_perm.id)
        assert p is not None
        assert p.code == "test:view"

    def test_not_found(self, perm_svc):
        assert perm_svc.get_permission_by_id(99999) is None


class TestPermissionServiceGetByCode:

    def test_found(self, perm_svc, sample_perm):
        p = perm_svc.get_permission_by_code("test:view")
        assert p is not None

    def test_not_found(self, perm_svc):
        assert perm_svc.get_permission_by_code("nope") is None


class TestPermissionServiceCreate:

    def test_create_success(self, perm_svc):
        perm = perm_svc.create_permission(
            code="room:view",
            name="View Room",
            perm_type="api",
            resource="room",
            action="view",
            sort_order=10,
        )
        assert perm.id is not None
        assert perm.code == "room:view"
        assert perm.resource == "room"

    def test_create_with_parent(self, db_session, perm_svc):
        parent = perm_svc.create_permission(code="parent:p", name="Parent")
        child = perm_svc.create_permission(code="child:p", name="Child", parent_id=parent.id)
        assert child.parent_id == parent.id

    def test_create_duplicate_raises(self, perm_svc, sample_perm):
        with pytest.raises(ValueError, match="已存在"):
            perm_svc.create_permission(code="test:view", name="Dup")


class TestPermissionServiceUpdate:

    def test_update_name(self, perm_svc, sample_perm):
        updated = perm_svc.update_permission(sample_perm.id, name="Updated Name")
        assert updated.name == "Updated Name"

    def test_update_not_found(self, perm_svc):
        with pytest.raises(ValueError, match="不存在"):
            perm_svc.update_permission(99999, name="X")

    def test_update_code_to_existing_raises(self, db_session, perm_svc, sample_perm):
        db_session.add(SysPermission(code="other:perm", name="Other"))
        db_session.flush()

        with pytest.raises(ValueError, match="已存在"):
            perm_svc.update_permission(sample_perm.id, code="other:perm")

    def test_update_code_same_value_ok(self, perm_svc, sample_perm):
        updated = perm_svc.update_permission(sample_perm.id, code="test:view", name="Same")
        assert updated.code == "test:view"

    def test_update_type_field(self, perm_svc, sample_perm):
        """The 'type' key in kwargs should be handled correctly."""
        updated = perm_svc.update_permission(sample_perm.id, type="button")
        assert updated.type == "button"


class TestPermissionServiceDelete:

    def test_delete_success(self, db_session, perm_svc, sample_perm):
        perm_svc.delete_permission(sample_perm.id)
        assert perm_svc.get_permission_by_id(sample_perm.id) is None

    def test_delete_not_found(self, perm_svc):
        with pytest.raises(ValueError, match="不存在"):
            perm_svc.delete_permission(99999)

    def test_delete_in_use_raises(self, db_session, perm_svc, sample_perm, sample_role):
        db_session.add(SysRolePermission(role_id=sample_role.id, permission_id=sample_perm.id))
        db_session.flush()

        with pytest.raises(ValueError, match="仍被"):
            perm_svc.delete_permission(sample_perm.id)


class TestPermissionTree:

    def test_empty_tree(self, perm_svc):
        assert perm_svc.get_permission_tree() == []

    def test_flat_tree(self, db_session, perm_svc):
        db_session.add(SysPermission(code="a", name="A"))
        db_session.add(SysPermission(code="b", name="B"))
        db_session.flush()

        tree = perm_svc.get_permission_tree()
        assert len(tree) == 2
        for node in tree:
            assert node["children"] == []

    def test_nested_tree(self, db_session, perm_svc):
        parent = SysPermission(code="room", name="Room Mgmt", type="menu")
        db_session.add(parent)
        db_session.flush()

        child1 = SysPermission(code="room:view", name="View", type="api", parent_id=parent.id)
        child2 = SysPermission(code="room:edit", name="Edit", type="api", parent_id=parent.id)
        db_session.add_all([child1, child2])
        db_session.flush()

        tree = perm_svc.get_permission_tree()
        # Should have 1 root node with 2 children
        assert len(tree) == 1
        root = tree[0]
        assert root["code"] == "room"
        assert len(root["children"]) == 2
        child_codes = {c["code"] for c in root["children"]}
        assert child_codes == {"room:view", "room:edit"}


# ── PermissionService User-Role Operations ────────────────


class TestUserRoleOperations:

    def test_get_user_roles_empty(self, perm_svc, test_user):
        roles = perm_svc.get_user_roles(test_user.id)
        assert roles == []

    def test_get_user_roles_nonexistent_user(self, perm_svc):
        roles = perm_svc.get_user_roles(99999)
        assert roles == []

    def test_assign_user_roles(self, db_session, perm_svc, test_user, sample_role):
        perm_svc.assign_user_roles(test_user.id, [sample_role.id])
        roles = perm_svc.get_user_roles(test_user.id)
        assert len(roles) == 1
        assert roles[0].code == "test_role"

    def test_assign_user_roles_replaces(self, db_session, perm_svc, test_user):
        role_a = SysRole(code="role_a", name="Role A")
        role_b = SysRole(code="role_b", name="Role B")
        db_session.add_all([role_a, role_b])
        db_session.flush()

        perm_svc.assign_user_roles(test_user.id, [role_a.id])
        perm_svc.assign_user_roles(test_user.id, [role_b.id])

        roles = perm_svc.get_user_roles(test_user.id)
        assert len(roles) == 1
        assert roles[0].code == "role_b"

    def test_add_user_role(self, db_session, perm_svc, test_user, sample_role):
        perm_svc.add_user_role(test_user.id, sample_role.id)
        roles = perm_svc.get_user_roles(test_user.id)
        assert len(roles) == 1

    def test_add_user_role_duplicate_noop(self, db_session, perm_svc, test_user, sample_role):
        perm_svc.add_user_role(test_user.id, sample_role.id)
        perm_svc.add_user_role(test_user.id, sample_role.id)
        roles = perm_svc.get_user_roles(test_user.id)
        assert len(roles) == 1

    def test_remove_user_role(self, db_session, perm_svc, test_user, sample_role):
        perm_svc.add_user_role(test_user.id, sample_role.id)
        perm_svc.remove_user_role(test_user.id, sample_role.id)
        roles = perm_svc.get_user_roles(test_user.id)
        assert roles == []

    def test_remove_user_role_nonexistent_noop(self, perm_svc, test_user):
        """Removing a non-existent user-role mapping should not raise."""
        perm_svc.remove_user_role(test_user.id, 99999)


class TestGetUserPermissions:

    def test_no_roles_no_permissions(self, perm_svc, test_user):
        perms = perm_svc.get_user_permissions(test_user.id)
        assert perms == set()

    def test_aggregated_permissions(self, db_session, perm_svc, test_user):
        """Permissions from multiple roles should be aggregated."""
        role_a = SysRole(code="ra", name="Role A")
        role_b = SysRole(code="rb", name="Role B")
        db_session.add_all([role_a, role_b])
        db_session.flush()

        perm1 = SysPermission(code="p1", name="P1", type="api")
        perm2 = SysPermission(code="p2", name="P2", type="api")
        perm3 = SysPermission(code="p3", name="P3", type="api")
        db_session.add_all([perm1, perm2, perm3])
        db_session.flush()

        db_session.add(SysRolePermission(role_id=role_a.id, permission_id=perm1.id))
        db_session.add(SysRolePermission(role_id=role_a.id, permission_id=perm2.id))
        db_session.add(SysRolePermission(role_id=role_b.id, permission_id=perm2.id))
        db_session.add(SysRolePermission(role_id=role_b.id, permission_id=perm3.id))
        db_session.flush()

        perm_svc.assign_user_roles(test_user.id, [role_a.id, role_b.id])

        perms = perm_svc.get_user_permissions(test_user.id)
        assert perms == {"p1", "p2", "p3"}

    def test_inactive_permissions_excluded(self, db_session, perm_svc, test_user):
        """Inactive permissions should not be included."""
        role = SysRole(code="inactive_perm_role", name="R")
        db_session.add(role)
        db_session.flush()

        active_perm = SysPermission(code="active:p", name="Active", is_active=True)
        inactive_perm = SysPermission(code="inactive:p", name="Inactive", is_active=False)
        db_session.add_all([active_perm, inactive_perm])
        db_session.flush()

        db_session.add(SysRolePermission(role_id=role.id, permission_id=active_perm.id))
        db_session.add(SysRolePermission(role_id=role.id, permission_id=inactive_perm.id))
        db_session.flush()

        perm_svc.assign_user_roles(test_user.id, [role.id])

        perms = perm_svc.get_user_permissions(test_user.id)
        assert "active:p" in perms
        assert "inactive:p" not in perms

    def test_inactive_role_excluded(self, db_session, perm_svc, test_user):
        """Inactive roles should not contribute permissions."""
        inactive_role = SysRole(code="inactive_role", name="Inactive", is_active=False)
        db_session.add(inactive_role)
        db_session.flush()

        perm = SysPermission(code="should_not_show", name="Hidden")
        db_session.add(perm)
        db_session.flush()

        db_session.add(SysRolePermission(role_id=inactive_role.id, permission_id=perm.id))
        db_session.add(SysUserRole(user_id=test_user.id, role_id=inactive_role.id))
        db_session.flush()

        perms = perm_svc.get_user_permissions(test_user.id)
        # Inactive role's permissions should be excluded because get_user_roles
        # filters by is_active == True
        assert "should_not_show" not in perms
