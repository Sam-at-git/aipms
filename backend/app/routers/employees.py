"""
员工管理路由
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee, EmployeeRole
from app.models.schemas import EmployeeCreate, EmployeeUpdate, PasswordReset, EmployeeResponse
from app.services.employee_service import EmployeeService
from app.security.auth import get_current_user, require_manager

router = APIRouter(prefix="/employees", tags=["员工管理"])


@router.get("", response_model=List[EmployeeResponse])
def list_employees(
    role: Optional[EmployeeRole] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """获取员工列表"""
    service = EmployeeService(db)
    employees = service.get_employees(role, is_active)
    return [EmployeeResponse.model_validate(e) for e in employees]


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """获取员工详情"""
    service = EmployeeService(db)
    employee = service.get_employee(employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="员工不存在")
    return EmployeeResponse.model_validate(employee)


@router.post("", response_model=EmployeeResponse)
def create_employee(
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """创建员工"""
    service = EmployeeService(db)
    try:
        employee = service.create_employee(data)
        return EmployeeResponse.model_validate(employee)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """更新员工"""
    service = EmployeeService(db)
    try:
        employee = service.update_employee(employee_id, data)
        return EmployeeResponse.model_validate(employee)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{employee_id}/reset-password")
def reset_password(
    employee_id: int,
    data: PasswordReset,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """重置密码"""
    service = EmployeeService(db)
    try:
        service.reset_password(employee_id, data, operator=current_user)
        return {"message": "密码已重置"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{employee_id}")
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager)
):
    """停用员工"""
    service = EmployeeService(db)
    try:
        service.delete_employee(employee_id)
        return {"message": "员工已停用"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
