"""
组织机构 ORM 模型 — 部门 + 岗位
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey
)
from sqlalchemy.orm import relationship
from app.database import Base


class SysDepartment(Base):
    """部门表 — 支持树形结构（最多 3-4 级）"""
    __tablename__ = "sys_department"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("sys_department.id"), nullable=True)
    leader_id = Column(
        Integer,
        ForeignKey("employees.id", use_alter=True, name="fk_department_leader"),
        nullable=True,
    )
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Self-referential: children
    children = relationship(
        "SysDepartment",
        backref="parent",
        remote_side="SysDepartment.id",
        lazy="selectin",
    )
    # Positions in this department
    positions = relationship("SysPosition", back_populates="department", lazy="selectin")


class SysPosition(Base):
    """岗位表"""
    __tablename__ = "sys_position"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("sys_department.id"), nullable=True)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    department = relationship("SysDepartment", back_populates="positions")
