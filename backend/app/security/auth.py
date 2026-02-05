"""
认证与授权模块
遵循 Palantir 原则：安全内嵌，属性级访问控制
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee, EmployeeRole

# 配置
SECRET_KEY = "pms-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def get_password_hash(password: str) -> str:
    """密码哈希"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(employee_id: int, role: EmployeeRole) -> str:
    """创建 JWT token"""
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode = {
        "sub": str(employee_id),
        "role": role.value,
        "exp": expire
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """解码 JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证"
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Employee:
    """获取当前登录用户"""
    token = credentials.credentials
    payload = decode_token(token)

    employee_id = int(payload.get("sub"))
    employee = db.query(Employee).filter(Employee.id == employee_id).first()

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )

    if not employee.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号已停用"
        )

    return employee


def require_role(allowed_roles: List[EmployeeRole]):
    """角色权限验证装饰器"""
    async def role_checker(current_user: Employee = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足"
            )
        return current_user
    return role_checker


# 便捷的角色检查器
require_sysadmin = require_role([EmployeeRole.SYSADMIN])
require_manager = require_role([EmployeeRole.SYSADMIN, EmployeeRole.MANAGER])
require_receptionist_or_manager = require_role([EmployeeRole.SYSADMIN, EmployeeRole.MANAGER, EmployeeRole.RECEPTIONIST])
require_any_role = require_role([EmployeeRole.SYSADMIN, EmployeeRole.MANAGER, EmployeeRole.RECEPTIONIST, EmployeeRole.CLEANER])
