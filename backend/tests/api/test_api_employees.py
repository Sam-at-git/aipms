"""
员工管理 API 单元测试
覆盖 /employees 端点的所有功能
"""
import pytest
from fastapi.testclient import TestClient


class TestListEmployees:
    """员工列表测试"""

    def test_list_employees(self, client: TestClient, manager_auth_headers, db_session):
        """测试获取员工列表"""
        from app.models.ontology import Employee, EmployeeRole

        employee = Employee(
            username="test1",
            password_hash="hash",
            name="测试员工",
            role=EmployeeRole.RECEPTIONIST
        )
        db_session.add(employee)
        db_session.commit()

        response = client.get("/employees", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_employees_filter_by_role(self, client: TestClient, manager_auth_headers, db_session):
        """测试按角色筛选员工"""
        from app.models.ontology import Employee, EmployeeRole

        emp1 = Employee(
            username="front1",
            password_hash="hash",
            name="前台1",
            role=EmployeeRole.RECEPTIONIST
        )
        emp2 = Employee(
            username="cleaner1",
            password_hash="hash",
            name="清洁员1",
            role=EmployeeRole.CLEANER
        )
        db_session.add(emp1)
        db_session.add(emp2)
        db_session.commit()

        response = client.get("/employees?role=receptionist", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert all(emp["role"] == "receptionist" for emp in data)

    def test_search_employees(self, client: TestClient, manager_auth_headers, db_session):
        """测试搜索员工"""
        from app.models.ontology import Employee, EmployeeRole

        employee = Employee(
            username="search_test",
            password_hash="hash",
            name="搜索测试员",
            role=EmployeeRole.RECEPTIONIST
        )
        db_session.add(employee)
        db_session.commit()

        # 使用列表端点进行筛选
        response = client.get("/employees?role=receptionist", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestCreateEmployee:
    """创建员工测试"""

    def test_create_employee(self, client: TestClient, manager_auth_headers):
        """测试创建员工"""
        response = client.post("/employees", headers=manager_auth_headers, json={
            "username": "new_employee",
            "password": "password123",
            "name": "新员工",
            "role": "receptionist"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "new_employee"
        assert data["name"] == "新员工"
        assert data["role"] == "receptionist"

    def test_create_duplicate_username(self, client: TestClient, manager_auth_headers, db_session):
        """测试创建重复用户名"""
        from app.models.ontology import Employee, EmployeeRole
        from app.security.auth import get_password_hash

        employee = Employee(
            username="duplicate",
            password_hash=get_password_hash("pass"),
            name="已存在",
            role=EmployeeRole.RECEPTIONIST
        )
        db_session.add(employee)
        db_session.commit()

        response = client.post("/employees", headers=manager_auth_headers, json={
            "username": "duplicate",
            "password": "password123",
            "name": "重复名称",
            "role": "receptionist"
        })

        assert response.status_code == 400

    def test_create_employee_unauthorized(self, client: TestClient, receptionist_auth_headers):
        """测试非经理不能创建员工"""
        response = client.post("/employees", headers=receptionist_auth_headers, json={
            "username": "unauthorized",
            "password": "password123",
            "name": "未授权创建",
            "role": "receptionist"
        })

        assert response.status_code == 403


class TestGetEmployeeDetail:
    """员工详情测试"""

    def test_get_employee_detail(self, client: TestClient, manager_auth_headers, db_session):
        """测试获取员工详情"""
        from app.models.ontology import Employee, EmployeeRole

        employee = Employee(
            username="detail_test",
            password_hash="hash",
            name="详情测试",
            role=EmployeeRole.RECEPTIONIST
        )
        db_session.add(employee)
        db_session.commit()
        db_session.refresh(employee)

        response = client.get(f"/employees/{employee.id}", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == employee.id
        assert data["username"] == "detail_test"

    def test_get_employee_not_found(self, client: TestClient, manager_auth_headers):
        """测试获取不存在的员工"""
        response = client.get("/employees/99999", headers=manager_auth_headers)

        assert response.status_code == 404


class TestUpdateEmployee:
    """更新员工测试"""

    def test_update_employee(self, client: TestClient, manager_auth_headers, db_session):
        """测试更新员工"""
        from app.models.ontology import Employee, EmployeeRole

        employee = Employee(
            username="update_test",
            password_hash="hash",
            name="更新前",
            role=EmployeeRole.RECEPTIONIST
        )
        db_session.add(employee)
        db_session.commit()
        db_session.refresh(employee)

        response = client.put(f"/employees/{employee.id}", headers=manager_auth_headers, json={
            "name": "更新后",
            "email": "updated@example.com"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "更新后"

    def test_update_employee_role(self, client: TestClient, manager_auth_headers, db_session):
        """测试更新员工角色"""
        from app.models.ontology import Employee, EmployeeRole

        employee = Employee(
            username="role_test",
            password_hash="hash",
            name="角色测试",
            role=EmployeeRole.RECEPTIONIST
        )
        db_session.add(employee)
        db_session.commit()
        db_session.refresh(employee)

        response = client.put(f"/employees/{employee.id}", headers=manager_auth_headers, json={
            "role": "manager"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "manager"


class TestDeleteEmployee:
    """删除员工测试"""

    def test_delete_employee(self, client: TestClient, manager_auth_headers, db_session):
        """测试删除员工"""
        from app.models.ontology import Employee, EmployeeRole

        employee = Employee(
            username="delete_test",
            password_hash="hash",
            name="待删除",
            role=EmployeeRole.RECEPTIONIST
        )
        db_session.add(employee)
        db_session.commit()
        db_session.refresh(employee)

        response = client.delete(f"/employees/{employee.id}", headers=manager_auth_headers)

        assert response.status_code == 200
        assert "员工已停用" in response.json()["message"]

    def test_delete_employee_unauthorized(self, client: TestClient, receptionist_auth_headers, db_session):
        """测试非经理不能删除员工"""
        from app.models.ontology import Employee, EmployeeRole

        employee = Employee(
            username="cannot_delete",
            password_hash="hash",
            name="不能删除",
            role=EmployeeRole.RECEPTIONIST
        )
        db_session.add(employee)
        db_session.commit()
        db_session.refresh(employee)

        response = client.delete(f"/employees/{employee.id}", headers=receptionist_auth_headers)

        assert response.status_code == 403


class TestResetPassword:
    """重置密码测试"""

    def test_reset_password(self, client: TestClient, manager_auth_headers, db_session):
        """测试重置密码"""
        from app.models.ontology import Employee, EmployeeRole

        employee = Employee(
            username="password_test",
            password_hash="old_hash",
            name="密码测试",
            role=EmployeeRole.RECEPTIONIST
        )
        db_session.add(employee)
        db_session.commit()
        db_session.refresh(employee)

        response = client.post(f"/employees/{employee.id}/reset-password", headers=manager_auth_headers, json={
            "new_password": "new_password123"
        })

        assert response.status_code == 200
        assert response.json()["message"] == "密码已重置"

    def test_reset_password_unauthorized(self, client: TestClient, receptionist_auth_headers, db_session):
        """测试非经理不能重置他人密码"""
        from app.models.ontology import Employee, EmployeeRole

        employee = Employee(
            username="other",
            password_hash="hash",
            name="其他员工",
            role=EmployeeRole.RECEPTIONIST
        )
        db_session.add(employee)
        db_session.commit()
        db_session.refresh(employee)

        response = client.post(f"/employees/{employee.id}/reset-password", headers=receptionist_auth_headers, json={
            "new_password": "new_password123"
        })

        assert response.status_code == 403

    def test_manager_cannot_reset_sysadmin_password(self, client: TestClient, manager_auth_headers, db_session):
        """测试经理不能重置系统管理员密码"""
        from app.models.ontology import Employee, EmployeeRole
        from app.security.auth import get_password_hash

        sysadmin = Employee(
            username="sysadmin_target",
            password_hash=get_password_hash("old_password"),
            name="系统管理员",
            role=EmployeeRole.SYSADMIN
        )
        db_session.add(sysadmin)
        db_session.commit()
        db_session.refresh(sysadmin)

        response = client.post(f"/employees/{sysadmin.id}/reset-password", headers=manager_auth_headers, json={
            "new_password": "new_password123"
        })

        assert response.status_code == 400
        assert "系统管理员" in response.json()["detail"]

    def test_sysadmin_can_reset_sysadmin_password(self, client: TestClient, sysadmin_auth_headers, db_session):
        """测试系统管理员可以重置系统管理员密码"""
        from app.models.ontology import Employee, EmployeeRole
        from app.security.auth import get_password_hash

        another_sysadmin = Employee(
            username="sysadmin_target2",
            password_hash=get_password_hash("old_password"),
            name="另一个管理员",
            role=EmployeeRole.SYSADMIN
        )
        db_session.add(another_sysadmin)
        db_session.commit()
        db_session.refresh(another_sysadmin)

        response = client.post(f"/employees/{another_sysadmin.id}/reset-password", headers=sysadmin_auth_headers, json={
            "new_password": "new_password123"
        })

        assert response.status_code == 200
        assert response.json()["message"] == "密码已重置"


class TestEmployeePermissions:
    """员工权限测试"""

    def test_cleaner_cannot_access_employees(self, client: TestClient, cleaner_auth_headers):
        """测试清洁员不能访问员工管理"""
        response = client.get("/employees", headers=cleaner_auth_headers)

        assert response.status_code == 403

    def test_manager_can_access_all(self, client: TestClient, manager_auth_headers):
        """测试经理可以访问所有功能"""
        response = client.get("/employees", headers=manager_auth_headers)

        assert response.status_code == 200
