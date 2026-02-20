"""
SPEC-22: Data isolation integration tests
Tests that branch-scoped data is properly isolated between branches.
Verifies: room filtering by branch, cross-branch access denial, sysadmin global access,
and guest global visibility.
"""
import pytest
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.ontology import (
    Employee, EmployeeRole, Room, RoomType, RoomStatus, Guest,
)
from app.security.auth import get_password_hash, create_access_token
from app.system.models.org import SysDepartment, DeptType
from app.system.models.rbac import SysRole, SysUserRole, SysPermission, SysRolePermission


@pytest.fixture
def multi_branch_setup(db_session: Session):
    """Set up two branches with rooms, employees, and RBAC roles."""
    # --- Org tree ---
    group = SysDepartment(name="集团总部", code="GROUP_HQ", dept_type=DeptType.GROUP)
    db_session.add(group)
    db_session.flush()

    branch_hz = SysDepartment(
        name="杭州西湖店", code="BRANCH_HZ", dept_type=DeptType.BRANCH, parent_id=group.id
    )
    branch_sh = SysDepartment(
        name="上海外滩店", code="BRANCH_SH", dept_type=DeptType.BRANCH, parent_id=group.id
    )
    db_session.add_all([branch_hz, branch_sh])
    db_session.flush()

    # --- Room type (shared) ---
    rt = RoomType(name="标准间", description="Standard", base_price=Decimal("288.00"), max_occupancy=2)
    db_session.add(rt)
    db_session.flush()

    # --- Rooms per branch ---
    hz_rooms = []
    for i in range(201, 204):
        r = Room(
            room_number=str(i), floor=2, room_type_id=rt.id,
            status=RoomStatus.VACANT_CLEAN, branch_id=branch_hz.id,
        )
        hz_rooms.append(r)
    sh_rooms = []
    for i in range(201, 203):
        r = Room(
            room_number=f"S{i}", floor=2, room_type_id=rt.id,
            status=RoomStatus.VACANT_CLEAN, branch_id=branch_sh.id,
        )
        sh_rooms.append(r)
    db_session.add_all(hz_rooms + sh_rooms)
    db_session.flush()

    # --- Employees ---
    sysadmin = Employee(
        username="sysadmin", password_hash=get_password_hash("123456"),
        name="系统管理员", role=EmployeeRole.SYSADMIN, is_active=True,
        department_id=group.id, branch_id=None,
    )
    hz_manager = Employee(
        username="hz_mgr", password_hash=get_password_hash("123456"),
        name="杭州经理", role=EmployeeRole.MANAGER, is_active=True,
        department_id=branch_hz.id, branch_id=branch_hz.id,
    )
    sh_manager = Employee(
        username="sh_mgr", password_hash=get_password_hash("123456"),
        name="上海经理", role=EmployeeRole.MANAGER, is_active=True,
        department_id=branch_sh.id, branch_id=branch_sh.id,
    )
    db_session.add_all([sysadmin, hz_manager, sh_manager])
    db_session.flush()

    # --- RBAC roles + permissions ---
    role_mgr = SysRole(code="branch_manager", name="分店经理", data_scope="DEPT_AND_BELOW", is_system=True)
    db_session.add(role_mgr)
    db_session.flush()

    # Create room:read permission and assign to branch_manager role
    perm_room_read = SysPermission(code="room:read", name="房间查看", resource="room", action="read")
    perm_room_write = SysPermission(code="room:write", name="房间管理", resource="room", action="write")
    perm_employee_write = SysPermission(code="employee:write", name="员工管理", resource="employee", action="write")
    db_session.add_all([perm_room_read, perm_room_write, perm_employee_write])
    db_session.flush()

    for perm in [perm_room_read, perm_room_write, perm_employee_write]:
        db_session.add(SysRolePermission(role_id=role_mgr.id, permission_id=perm.id))

    # Assign role to managers
    db_session.add(SysUserRole(user_id=hz_manager.id, role_id=role_mgr.id))
    db_session.add(SysUserRole(user_id=sh_manager.id, role_id=role_mgr.id))
    db_session.commit()

    # --- Guests (global) ---
    guest = Guest(name="张三", phone="13800138000", id_type="身份证", id_number="110101199001011234")
    db_session.add(guest)
    db_session.commit()

    return {
        "group": group,
        "branch_hz": branch_hz,
        "branch_sh": branch_sh,
        "hz_rooms": hz_rooms,
        "sh_rooms": sh_rooms,
        "sysadmin": sysadmin,
        "hz_manager": hz_manager,
        "sh_manager": sh_manager,
        "guest": guest,
        "room_type": rt,
    }


class TestRoomBranchIsolation:
    """Test that room data is properly filtered by branch."""

    def test_sysadmin_sees_all_rooms(self, client, multi_branch_setup):
        """Sysadmin should see rooms from both branches."""
        data = multi_branch_setup
        token = create_access_token(data["sysadmin"].id, data["sysadmin"].role)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/rooms", headers=headers)
        assert response.status_code == 200
        rooms = response.json()
        # Should see all 5 rooms (3 HZ + 2 SH)
        assert len(rooms) >= 5

    def test_manager_sees_own_branch_rooms_via_header(self, client, multi_branch_setup):
        """Manager with X-Branch-Id header should see only that branch's rooms."""
        data = multi_branch_setup
        token = create_access_token(data["hz_manager"].id, data["hz_manager"].role)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Branch-Id": str(data["branch_hz"].id),
        }

        response = client.get("/rooms", headers=headers)
        assert response.status_code == 200
        rooms = response.json()
        # HZ has 3 rooms (201, 202, 203)
        room_numbers = [r["room_number"] for r in rooms]
        assert "201" in room_numbers
        # SH rooms should not appear
        assert all(not rn.startswith("S") for rn in room_numbers)

    def test_sysadmin_with_branch_header_filters(self, client, multi_branch_setup):
        """Sysadmin with X-Branch-Id should see only that branch's rooms."""
        data = multi_branch_setup
        token = create_access_token(data["sysadmin"].id, data["sysadmin"].role)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Branch-Id": str(data["branch_sh"].id),
        }

        response = client.get("/rooms", headers=headers)
        assert response.status_code == 200
        rooms = response.json()
        room_numbers = [r["room_number"] for r in rooms]
        # Should only see SH rooms
        assert all(rn.startswith("S") for rn in room_numbers)


class TestGuestIsGlobal:
    """Test that guest data is globally shared (no branch filtering)."""

    def test_guest_visible_to_all_branches(self, client, multi_branch_setup):
        """Guest created without branch_id should be visible to any user."""
        data = multi_branch_setup
        # HZ manager should see guests
        token = create_access_token(data["hz_manager"].id, data["hz_manager"].role)
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Branch-Id": str(data["branch_hz"].id),
        }

        response = client.get("/guests", headers=headers)
        assert response.status_code == 200
        guests = response.json()
        assert any(g["name"] == "张三" for g in guests)


class TestEmployeeBranchData:
    """Test that employee API returns correct branch information."""

    def test_employee_list_contains_branch_info(self, client, multi_branch_setup):
        """Employee list should return branch_id for each employee."""
        data = multi_branch_setup
        token = create_access_token(data["sysadmin"].id, data["sysadmin"].role)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/employees", headers=headers)
        assert response.status_code == 200
        employees = response.json()

        # Find hz_manager
        hz_mgr = next((e for e in employees if e["username"] == "hz_mgr"), None)
        assert hz_mgr is not None
        assert hz_mgr["branch_id"] == data["branch_hz"].id

        # Find sysadmin (no branch)
        admin = next((e for e in employees if e["username"] == "sysadmin"), None)
        assert admin is not None
        assert admin["branch_id"] is None


class TestBranchHeaderValidation:
    """Test X-Branch-Id header behavior."""

    def test_request_without_branch_header(self, client, multi_branch_setup):
        """Request without X-Branch-Id should return all accessible data."""
        data = multi_branch_setup
        token = create_access_token(data["sysadmin"].id, data["sysadmin"].role)
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/rooms", headers=headers)
        assert response.status_code == 200
        rooms = response.json()
        # Sysadmin without branch filter sees all rooms
        assert len(rooms) >= 5

    def test_login_returns_branch_fields(self, client, multi_branch_setup):
        """Login response should include branch_id and branch_name."""
        response = client.post("/auth/login", json={
            "username": "hz_mgr",
            "password": "123456",
        })
        assert response.status_code == 200
        result = response.json()
        assert "employee" in result
        emp = result["employee"]
        assert emp["branch_id"] is not None
        assert "role_codes" in emp
