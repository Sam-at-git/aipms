"""
员工服务 - 本体操作层
管理 Employee 对象和认证
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.hotel.models.ontology import Employee, EmployeeRole
from app.hotel.models.schemas import EmployeeCreate, EmployeeUpdate, PasswordReset, PasswordChange
from app.security.auth import get_password_hash, verify_password, create_access_token


class EmployeeService:
    """员工服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_employees(self, role: Optional[EmployeeRole] = None,
                      is_active: Optional[bool] = None) -> List[Employee]:
        """获取员工列表"""
        query = self.db.query(Employee)

        if role:
            query = query.filter(Employee.role == role)
        if is_active is not None:
            query = query.filter(Employee.is_active == is_active)

        return query.order_by(Employee.created_at.desc()).all()

    def get_employee(self, employee_id: int) -> Optional[Employee]:
        """获取单个员工"""
        return self.db.query(Employee).filter(Employee.id == employee_id).first()

    def get_employee_by_username(self, username: str) -> Optional[Employee]:
        """根据用户名获取员工"""
        return self.db.query(Employee).filter(Employee.username == username).first()

    def create_employee(self, data: EmployeeCreate) -> Employee:
        """创建员工"""
        if self.get_employee_by_username(data.username):
            raise ValueError(f"用户名 '{data.username}' 已存在")

        employee = Employee(
            username=data.username,
            password_hash=get_password_hash(data.password),
            name=data.name,
            phone=data.phone,
            role=data.role
        )
        self.db.add(employee)
        self.db.commit()
        self.db.refresh(employee)
        return employee

    def update_employee(self, employee_id: int, data: EmployeeUpdate) -> Employee:
        """更新员工"""
        employee = self.get_employee(employee_id)
        if not employee:
            raise ValueError("员工不存在")

        update_data = data.model_dump(exclude_unset=True)

        # 检查是否是最后一个经理
        if 'role' in update_data and update_data['role'] != EmployeeRole.MANAGER:
            if employee.role == EmployeeRole.MANAGER:
                manager_count = self.db.query(Employee).filter(
                    Employee.role == EmployeeRole.MANAGER,
                    Employee.is_active == True
                ).count()
                if manager_count <= 1:
                    raise ValueError("系统需至少保留一个经理账号")

        # 检查是否停用最后一个经理
        if 'is_active' in update_data and update_data['is_active'] == False:
            if employee.role == EmployeeRole.MANAGER:
                manager_count = self.db.query(Employee).filter(
                    Employee.role == EmployeeRole.MANAGER,
                    Employee.is_active == True
                ).count()
                if manager_count <= 1:
                    raise ValueError("系统需至少保留一个活跃的经理账号")

        for key, value in update_data.items():
            setattr(employee, key, value)

        self.db.commit()
        self.db.refresh(employee)
        return employee

    def reset_password(self, employee_id: int, data: PasswordReset,
                       operator: Optional[Employee] = None) -> bool:
        """重置密码

        只有 sysadmin 角色才能重置 sysadmin 角色用户的密码。
        """
        employee = self.get_employee(employee_id)
        if not employee:
            raise ValueError("员工不存在")

        if employee.role == EmployeeRole.SYSADMIN:
            if operator is None or operator.role != EmployeeRole.SYSADMIN:
                raise ValueError("只有系统管理员才能重置系统管理员的密码")

        employee.password_hash = get_password_hash(data.new_password)
        self.db.commit()
        return True

    def change_password(self, employee_id: int, data: PasswordChange) -> bool:
        """修改密码（本人操作）"""
        employee = self.get_employee(employee_id)
        if not employee:
            raise ValueError("员工不存在")

        if not verify_password(data.old_password, employee.password_hash):
            raise ValueError("原密码错误")

        employee.password_hash = get_password_hash(data.new_password)
        self.db.commit()
        return True

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        """认证登录"""
        employee = self.get_employee_by_username(username)
        if not employee:
            return None

        if not employee.is_active:
            raise ValueError("账号已停用")

        if not verify_password(password, employee.password_hash):
            return None

        token = create_access_token(employee.id, employee.role)

        return {
            'access_token': token,
            'token_type': 'bearer',
            'employee': {
                'id': employee.id,
                'username': employee.username,
                'name': employee.name,
                'phone': employee.phone,
                'role': employee.role,
                'is_active': employee.is_active,
                'created_at': employee.created_at
            }
        }

    def delete_employee(self, employee_id: int) -> bool:
        """删除员工（实际上是停用）"""
        employee = self.get_employee(employee_id)
        if not employee:
            raise ValueError("员工不存在")

        if employee.role == EmployeeRole.MANAGER:
            manager_count = self.db.query(Employee).filter(
                Employee.role == EmployeeRole.MANAGER,
                Employee.is_active == True
            ).count()
            if manager_count <= 1:
                raise ValueError("系统需至少保留一个经理账号")

        employee.is_active = False
        self.db.commit()
        return True
