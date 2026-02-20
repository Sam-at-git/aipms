"""
组织机构 ORM 模型 — 部门 + 岗位

dept_type 枚举: GROUP(集团), BRANCH(分店), DEPARTMENT(店内部门)
"""
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from app.database import Base


class DeptType(str, PyEnum):
    """部门类型枚举"""
    GROUP = "GROUP"            # 集团
    BRANCH = "BRANCH"          # 分店
    DEPARTMENT = "DEPARTMENT"  # 店内部门


class SysDepartment(Base):
    """部门表 — 支持树形结构（集团→分店→部门）"""
    __tablename__ = "sys_department"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("sys_department.id"), nullable=True)
    dept_type = Column(SQLEnum(DeptType), default=DeptType.DEPARTMENT, nullable=False)
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
