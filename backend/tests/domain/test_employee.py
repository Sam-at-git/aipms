"""测试 core.domain.employee 模块"""
import pytest
import hashlib

from app.hotel.domain.employee import EmployeeRole, EmployeeEntity, EmployeeRepository
from app.models.ontology import Employee, EmployeeRole as ORMRole


def hash_password(password: str) -> str:
    """Simple password hashing for tests"""
    return hashlib.sha256(password.encode()).hexdigest()


@pytest.fixture
def sample_employee(db_session):
    emp = Employee(
        name="张经理",
        username="manager",
        role=ORMRole.MANAGER,
        phone="13800138000",
        password_hash=hash_password("123456"),
        is_active=True,
    )
    db_session.add(emp)
    db_session.commit()
    return emp


class TestEmployeeEntity:
    def test_creation(self, sample_employee):
        entity = EmployeeEntity(sample_employee)
        assert entity.name == "张经理"
        assert entity.role == "manager"
        assert entity.is_manager() is True

    def test_update_role(self, sample_employee):
        entity = EmployeeEntity(sample_employee)
        entity.update_role("cleaner")
        assert entity.role == "cleaner"

    def test_is_cleaner(self, sample_employee):
        sample_employee.role = ORMRole.CLEANER
        entity = EmployeeEntity(sample_employee)
        assert entity.is_cleaner() is True

    def test_to_dict(self, sample_employee):
        entity = EmployeeEntity(sample_employee)
        d = entity.to_dict()
        assert d["name"] == "张经理"
        assert d["role"] == "manager"


class TestEmployeeRepository:
    def test_get_by_id(self, db_session, sample_employee):
        repo = EmployeeRepository(db_session)
        entity = repo.get_by_id(sample_employee.id)
        assert entity is not None

    def test_get_by_username(self, db_session, sample_employee):
        repo = EmployeeRepository(db_session)
        entity = repo.get_by_username("manager")
        assert entity is not None

    def test_find_by_role(self, db_session, sample_employee):
        repo = EmployeeRepository(db_session)
        managers = repo.find_by_role("manager")
        assert len(managers) >= 1


class TestEmployeeRole:
    def test_values(self):
        assert EmployeeRole.MANAGER == "manager"
        assert EmployeeRole.RECEPTIONIST == "receptionist"
        assert EmployeeRole.CLEANER == "cleaner"
