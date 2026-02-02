"""
认证路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.schemas import LoginRequest, LoginResponse, PasswordChange
from app.models.ontology import Employee
from app.services.employee_service import EmployeeService
from app.security.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    service = EmployeeService(db)
    try:
        result = service.authenticate(data.username, data.password)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me")
def get_current_user_info(current_user: Employee = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        'id': current_user.id,
        'username': current_user.username,
        'name': current_user.name,
        'role': current_user.role,
        'is_active': current_user.is_active
    }


@router.post("/change-password")
def change_password(
    data: PasswordChange,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """修改密码"""
    service = EmployeeService(db)
    try:
        service.change_password(current_user.id, data)
        return {"message": "密码修改成功"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
