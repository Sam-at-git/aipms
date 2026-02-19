"""
app/services/actions/employee_actions.py

Employee management action handlers using ActionRegistry.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee, EmployeeRole
from app.services.actions.base import (
    CreateEmployeeParams, UpdateEmployeeParams, DeactivateEmployeeParams,
)

import logging

logger = logging.getLogger(__name__)


def register_employee_actions(
    registry: ActionRegistry
) -> None:
    """Register all employee-related actions."""

    @registry.register(
        name="create_employee",
        entity="Employee",
        description="创建新员工。设置账号、姓名、角色等。默认密码123456。",
        category="employee_management",
        requires_confirmation=True,
        allowed_roles={"manager", "sysadmin"},
        undoable=False,
        side_effects=["creates_employee"],
        search_keywords=["创建员工", "新增员工", "添加员工", "create employee"]
    )
    def handle_create_employee(
        params: CreateEmployeeParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """创建新员工"""
        from app.security.auth import get_password_hash

        try:
            # Check username uniqueness
            existing = db.query(Employee).filter(
                Employee.username == params.username
            ).first()
            if existing:
                return {
                    "success": False,
                    "message": f"用户名「{params.username}」已存在",
                    "error": "duplicate"
                }

            password = params.password or "123456"
            role = EmployeeRole(params.role)

            employee = Employee(
                username=params.username,
                name=params.name,
                password_hash=get_password_hash(password),
                role=role,
                phone=params.phone,
                is_active=True
            )
            db.add(employee)
            db.commit()
            db.refresh(employee)

            return {
                "success": True,
                "message": f"员工「{employee.name}」已创建，角色：{role.value}",
                "employee_id": employee.id,
                "username": employee.username,
                "name": employee.name,
                "role": employee.role.value
            }
        except Exception as e:
            logger.error(f"Error in create_employee: {e}")
            return {
                "success": False,
                "message": f"创建员工失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="update_employee",
        entity="Employee",
        description="更新员工信息。可修改姓名、手机号、角色等。",
        category="employee_management",
        requires_confirmation=True,
        allowed_roles={"manager", "sysadmin"},
        undoable=False,
        side_effects=["updates_employee"],
        search_keywords=["修改员工", "更新员工", "update employee"]
    )
    def handle_update_employee(
        params: UpdateEmployeeParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """更新员工信息"""
        try:
            employee = db.query(Employee).filter(
                Employee.id == params.employee_id
            ).first()
            if not employee:
                return {
                    "success": False,
                    "message": f"员工ID {params.employee_id} 不存在",
                    "error": "not_found"
                }

            changes = []
            if params.name is not None:
                employee.name = params.name
                changes.append(f"姓名: {params.name}")
            if params.phone is not None:
                employee.phone = params.phone
                changes.append(f"手机号: {params.phone}")
            if params.role is not None:
                employee.role = EmployeeRole(params.role)
                changes.append(f"角色: {params.role}")

            if not changes:
                return {
                    "success": False,
                    "message": "没有需要更新的字段",
                    "error": "no_updates"
                }

            db.commit()
            db.refresh(employee)

            return {
                "success": True,
                "message": f"员工「{employee.name}」已更新：{'、'.join(changes)}",
                "employee_id": employee.id,
                "name": employee.name,
                "role": employee.role.value
            }
        except Exception as e:
            logger.error(f"Error in update_employee: {e}")
            return {
                "success": False,
                "message": f"更新员工失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="deactivate_employee",
        entity="Employee",
        description="停用员工账号。停用后员工无法登录。",
        category="employee_management",
        requires_confirmation=True,
        allowed_roles={"manager", "sysadmin"},
        undoable=False,
        side_effects=["deactivates_employee"],
        search_keywords=["停用员工", "禁用员工", "deactivate employee"],
        risk_level="high",
    )
    def handle_deactivate_employee(
        params: DeactivateEmployeeParams,
        db: Session,
        user: Employee,
        **context
    ) -> Dict[str, Any]:
        """停用员工"""
        try:
            employee = db.query(Employee).filter(
                Employee.id == params.employee_id
            ).first()
            if not employee:
                return {
                    "success": False,
                    "message": f"员工ID {params.employee_id} 不存在",
                    "error": "not_found"
                }

            if not employee.is_active:
                return {
                    "success": False,
                    "message": f"员工「{employee.name}」已处于停用状态",
                    "error": "already_deactivated"
                }

            employee.is_active = False
            db.commit()
            db.refresh(employee)

            return {
                "success": True,
                "message": f"员工「{employee.name}」已停用",
                "employee_id": employee.id,
                "name": employee.name,
                "is_active": employee.is_active
            }
        except Exception as e:
            logger.error(f"Error in deactivate_employee: {e}")
            return {
                "success": False,
                "message": f"停用员工失败: {str(e)}",
                "error": "execution_error"
            }


__all__ = ["register_employee_actions"]
