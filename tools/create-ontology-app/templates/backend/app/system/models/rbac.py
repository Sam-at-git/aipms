"""
RBAC ORM 模型 — 角色、权限、角色-权限映射、用户-角色映射
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from app.database import Base


class SysRole(Base):
    """角色表"""
    __tablename__ = "sys_role"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500), default="")
    data_scope = Column(String(20), default="ALL")  # ALL, DEPT, DEPT_AND_BELOW, SELF
    sort_order = Column(Integer, default=0)
    is_system = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    permissions = relationship(
        "SysPermission",
        secondary="sys_role_permission",
        back_populates="roles",
        lazy="selectin"
    )
    users = relationship(
        "SysUserRole",
        back_populates="role",
        cascade="all, delete-orphan"
    )


class SysPermission(Base):
    """权限表"""
    __tablename__ = "sys_permission"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    type = Column(String(20), nullable=False, default="api")  # menu, button, api, data
    resource = Column(String(50), default="")  # 资源名, e.g. "room", "guest"
    action = Column(String(50), default="")    # 操作名, e.g. "view", "update"
    parent_id = Column(Integer, ForeignKey("sys_permission.id"), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Self-referential relationship
    children = relationship("SysPermission", backref="parent", remote_side="SysPermission.id", lazy="selectin")

    # Many-to-many with roles
    roles = relationship(
        "SysRole",
        secondary="sys_role_permission",
        back_populates="permissions",
        lazy="selectin"
    )


class SysRolePermission(Base):
    """角色-权限映射表"""
    __tablename__ = "sys_role_permission"

    role_id = Column(Integer, ForeignKey("sys_role.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("sys_permission.id", ondelete="CASCADE"), primary_key=True)


class SysUserRole(Base):
    """用户-角色映射表"""
    __tablename__ = "sys_user_role"

    user_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(Integer, ForeignKey("sys_role.id", ondelete="CASCADE"), primary_key=True)

    # Relationships
    role = relationship("SysRole", back_populates="users")
