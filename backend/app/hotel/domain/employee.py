"""
core/domain/employee.py

Employee 领域实体 - OODA 运行时的领域层
"""
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
import logging

from core.ontology.base import BaseEntity

if TYPE_CHECKING:
    from app.models.ontology import Employee

logger = logging.getLogger(__name__)


class EmployeeRole(str):
    MANAGER = "manager"
    RECEPTIONIST = "receptionist"
    CLEANER = "cleaner"


class EmployeeEntity(BaseEntity):
    def __init__(self, orm_model: "Employee"):
        self._orm_model = orm_model

    @property
    def id(self) -> int:
        return self._orm_model.id

    @property
    def name(self) -> str:
        return self._orm_model.name

    @property
    def username(self) -> str:
        return self._orm_model.username

    @property
    def role(self) -> str:
        return self._orm_model.role.value if self._orm_model.role else EmployeeRole.RECEPTIONIST

    @property
    def phone(self) -> Optional[str]:
        return self._orm_model.phone

    @property
    def is_active(self) -> bool:
        return self._orm_model.is_active

    @property
    def created_at(self) -> datetime:
        return self._orm_model.created_at

    def update_role(self, role: str) -> None:
        from app.models.ontology import EmployeeRole as ORMRole
        self._orm_model.role = ORMRole(role)

    def deactivate(self) -> None:
        self._orm_model.is_active = False

    def activate(self) -> None:
        self._orm_model.is_active = True

    def is_manager(self) -> bool:
        return self.role == EmployeeRole.MANAGER

    def is_cleaner(self) -> bool:
        return self.role == EmployeeRole.CLEANER

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "role": self.role,
            "phone": self.phone,
            "is_active": self.is_active,
            "is_manager": self.is_manager(),
            "is_cleaner": self.is_cleaner(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EmployeeRepository:
    def __init__(self, db_session):
        self._db = db_session

    def get_by_id(self, employee_id: int) -> Optional[EmployeeEntity]:
        from app.models.ontology import Employee
        orm_model = self._db.query(Employee).filter(Employee.id == employee_id).first()
        if orm_model is None:
            return None
        return EmployeeEntity(orm_model)

    def get_by_username(self, username: str) -> Optional[EmployeeEntity]:
        from app.models.ontology import Employee
        orm_model = self._db.query(Employee).filter(Employee.username == username).first()
        if orm_model is None:
            return None
        return EmployeeEntity(orm_model)

    def find_by_role(self, role: str) -> List[EmployeeEntity]:
        from app.models.ontology import Employee, EmployeeRole as ORMRole
        try:
            role_enum = ORMRole(role)
        except ValueError:
            return []
        orm_models = self._db.query(Employee).filter(Employee.role == role_enum).all()
        return [EmployeeEntity(m) for m in orm_models]

    def find_active(self) -> List[EmployeeEntity]:
        from app.models.ontology import Employee
        orm_models = self._db.query(Employee).filter(Employee.is_active == True).all()
        return [EmployeeEntity(m) for m in orm_models]

    def find_cleaners(self) -> List[EmployeeEntity]:
        return self.find_by_role("cleaner")

    def save(self, employee: EmployeeEntity) -> None:
        self._db.add(employee._orm_model)
        self._db.commit()

    def list_all(self) -> List[EmployeeEntity]:
        from app.models.ontology import Employee
        orm_models = self._db.query(Employee).all()
        return [EmployeeEntity(m) for m in orm_models]


__all__ = ["EmployeeRole", "EmployeeEntity", "EmployeeRepository"]
