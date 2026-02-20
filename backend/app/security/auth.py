"""
认证与授权模块
遵循 Palantir 原则：安全内嵌，属性级访问控制

支持动态 RBAC（通过 SysRole/SysPermission）和旧枚举角色（过渡兼容）。
"""
import bcrypt
import logging
from datetime import datetime, timedelta, UTC
from typing import Optional, List, Set
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee, EmployeeRole

logger = logging.getLogger(__name__)

# 配置
SECRET_KEY = "pms-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer()


def get_password_hash(password: str) -> str:
    """密码哈希"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def create_access_token(employee_id: int, role: EmployeeRole,
                        role_codes: Optional[List[str]] = None,
                        branch_id: Optional[int] = None,
                        data_scope: Optional[str] = None) -> str:
    """创建 JWT token — 新格式包含 role_codes、branch_id、data_scope"""
    expire = datetime.now(UTC) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode = {
        "sub": str(employee_id),
        "role": role.value if isinstance(role, EmployeeRole) else str(role),
        "exp": expire
    }
    if role_codes is not None:
        to_encode["role_codes"] = role_codes
    if branch_id is not None:
        to_encode["branch_id"] = branch_id
    if data_scope is not None:
        to_encode["data_scope"] = data_scope
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


def _get_role_codes(employee: Employee) -> List[str]:
    """从 Employee 的 RBAC 关系获取角色编码列表"""
    try:
        from app.system.models.rbac import SysUserRole
        if hasattr(employee, 'user_roles') and employee.user_roles:
            return [ur.role.code for ur in employee.user_roles if ur.role and ur.role.is_active]
    except Exception:
        pass
    # fallback: 使用旧 role 枚举
    if employee.role:
        return [employee.role.value if isinstance(employee.role, EmployeeRole) else str(employee.role)]
    return []


def _get_max_data_scope(employee: Employee) -> str:
    """从用户所有角色中获取最大的 data_scope"""
    try:
        if hasattr(employee, 'user_roles') and employee.user_roles:
            scopes = [ur.role.data_scope for ur in employee.user_roles if ur.role and ur.role.is_active and ur.role.data_scope]
            # 优先级: ALL > DEPT_AND_BELOW > DEPT > SELF
            scope_priority = {"ALL": 4, "DEPT_AND_BELOW": 3, "DEPT": 2, "SELF": 1}
            if scopes:
                return max(scopes, key=lambda s: scope_priority.get(s, 0))
    except Exception:
        pass
    # sysadmin 默认 ALL
    if employee.role == EmployeeRole.SYSADMIN:
        return "ALL"
    return "DEPT_AND_BELOW"


def _get_branch_id(employee: Employee) -> Optional[int]:
    """获取员工的分店 ID"""
    return getattr(employee, 'branch_id', None)


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


async def get_security_context(
    request: Request,
    current_user: Employee = Depends(get_current_user),
):
    """构建 SecurityContext — 作为独立依赖注入（不影响 get_current_user 签名）

    支持 X-Branch-Id header 覆盖默认 branch_id。
    下游需要 SecurityContext 时使用此依赖。
    """
    from core.security.context import SecurityContext

    branch_id = getattr(current_user, 'branch_id', None)
    header_branch = request.headers.get("X-Branch-Id")
    if header_branch:
        try:
            branch_id = int(header_branch)
        except (ValueError, TypeError):
            pass

    return SecurityContext(
        user_id=current_user.id,
        role=current_user.role.value,
        branch_id=branch_id,
    )


def require_role(allowed_roles: List[EmployeeRole]):
    """角色权限验证装饰器（旧版 — 兼容保留）"""
    async def role_checker(current_user: Employee = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足"
            )
        return current_user
    return role_checker


# 便捷的角色检查器（旧版 — 兼容保留）
require_sysadmin = require_role([EmployeeRole.SYSADMIN])
require_manager = require_role([EmployeeRole.SYSADMIN, EmployeeRole.MANAGER])
require_receptionist_or_manager = require_role([EmployeeRole.SYSADMIN, EmployeeRole.MANAGER, EmployeeRole.RECEPTIONIST])
require_any_role = require_role([EmployeeRole.SYSADMIN, EmployeeRole.MANAGER, EmployeeRole.RECEPTIONIST, EmployeeRole.CLEANER])


def require_permission(*permission_codes: str):
    """动态权限检查装饰器 — 支持多个权限码（OR 逻辑）

    检查顺序:
    1. sysadmin 角色始终通过
    2. RBAC provider 检查（任一权限码匹配即通过）
    3. 旧角色映射回退
    """
    async def permission_checker(current_user: Employee = Depends(get_current_user)):
        from core.security.permission import permission_provider_registry

        # sysadmin 始终拥有所有权限
        if current_user.role == EmployeeRole.SYSADMIN:
            return current_user

        # 尝试通过 RBAC provider 检查
        if permission_provider_registry.has_provider():
            for code in permission_codes:
                if permission_provider_registry.has_permission(current_user.id, code):
                    return current_user

        # 旧角色映射回退: manager 拥有大多数业务权限
        if current_user.role == EmployeeRole.MANAGER:
            # manager 除系统管理、调试、安全审计、系统设置外的权限
            admin_prefixes = ("sys:", "debug:", "security:", "settings:", "audit:", "conversation:")
            if not any(code.startswith(admin_prefixes) for code in permission_codes):
                return current_user

        # receptionist 基础业务权限
        if current_user.role == EmployeeRole.RECEPTIONIST:
            receptionist_perms = {
                "room:read", "room:status", "guest:read", "guest:write",
                "reservation:read", "reservation:write", "reservation:cancel",
                "checkin:execute", "checkout:execute",
                "bill:read", "task:read", "task:write", "task:assign",
                "ai:chat", "ontology:read", "report:read",
                "undo:read", "undo:execute",
            }
            if any(code in receptionist_perms for code in permission_codes):
                return current_user

        # cleaner 仅任务相关
        if current_user.role == EmployeeRole.CLEANER:
            cleaner_perms = ("task:read", "task:write", "room:read")
            if any(code in cleaner_perms for code in permission_codes):
                return current_user

        # 无权限
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"缺少权限: {', '.join(permission_codes)}"
        )
    return permission_checker


def require_any_permission(*permission_codes: str):
    """require_permission 的别名（已支持 OR 逻辑）"""
    return require_permission(*permission_codes)
