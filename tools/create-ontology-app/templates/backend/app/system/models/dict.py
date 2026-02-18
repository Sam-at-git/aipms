"""
数据字典 ORM 模型
- SysDictType: 字典类型（如 room_status, task_type）
- SysDictItem: 字典项（如 vacant_clean, occupied）
"""
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship

from app.database import Base


class SysDictType(Base):
    """字典类型"""
    __tablename__ = "sys_dict_type"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(String(500), default="")
    is_system = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items = relationship("SysDictItem", back_populates="dict_type", cascade="all, delete-orphan",
                         order_by="SysDictItem.sort_order")


class SysDictItem(Base):
    """字典项"""
    __tablename__ = "sys_dict_item"

    id = Column(Integer, primary_key=True, index=True)
    dict_type_id = Column(Integer, ForeignKey("sys_dict_type.id"), nullable=False, index=True)
    label = Column(String(200), nullable=False)
    value = Column(String(200), nullable=False)
    color = Column(String(50), default="")
    extra = Column(Text, default="")  # JSON string for extension attributes
    sort_order = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    dict_type = relationship("SysDictType", back_populates="items")
