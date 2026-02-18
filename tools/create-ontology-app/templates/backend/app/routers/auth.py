"""
认证路由
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.schemas import LoginRequest, LoginResponse
from app.hotel.models.schemas import PasswordChange
from app.hotel.models.ontology import Employee
from app.hotel.services.employee_service import EmployeeService
from app.security.auth import get_current_user
from app.services.security_event_service import security_event_service
from app.models.security_events import SecurityEventType, SecurityEventSeverity

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """用户登录"""
    service = EmployeeService(db)
    client_ip = request.client.host if request.client else None

    try:
        result = service.authenticate(data.username, data.password)
        if not result:
            # 记录登录失败事件
            security_event_service.record_event(
                db,
                event_type=SecurityEventType.LOGIN_FAILED,
                description=f"用户 {data.username} 登录失败",
                severity=SecurityEventSeverity.LOW,
                source_ip=client_ip,
                details={"username": data.username}
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )

        # 记录登录成功事件
        user_info = result.get('employee', {})
        security_event_service.record_event(
            db,
            event_type=SecurityEventType.LOGIN_SUCCESS,
            description=f"用户 {user_info.get('name', data.username)} 登录成功",
            severity=SecurityEventSeverity.LOW,
            source_ip=client_ip,
            user_id=user_info.get('id'),
            user_name=user_info.get('name'),
            details={"username": data.username, "role": str(user_info.get('role'))}
        )
        db.commit()
        return result
    except ValueError as e:
        # 记录登录失败事件（账号停用等情况）
        security_event_service.record_event(
            db,
            event_type=SecurityEventType.LOGIN_FAILED,
            description=f"用户 {data.username} 登录失败: {str(e)}",
            severity=SecurityEventSeverity.MEDIUM,
            source_ip=client_ip,
            details={"username": data.username, "reason": str(e)}
        )
        db.commit()
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
    request: Request,
    current_user: Employee = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """修改密码"""
    service = EmployeeService(db)
    client_ip = request.client.host if request.client else None

    try:
        service.change_password(current_user.id, data)

        # 记录密码修改事件
        security_event_service.record_event(
            db,
            event_type=SecurityEventType.PASSWORD_CHANGED,
            description=f"用户 {current_user.name} 修改了密码",
            severity=SecurityEventSeverity.LOW,
            source_ip=client_ip,
            user_id=current_user.id,
            user_name=current_user.name
        )
        db.commit()
        return {"message": "密码修改成功"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
