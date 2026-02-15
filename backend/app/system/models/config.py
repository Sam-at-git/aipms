"""
系统配置 ORM 模型
- SysConfig: 统一 key-value 配置，支持分组和脱敏
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text

from app.database import Base


class SysConfig(Base):
    """系统配置"""
    __tablename__ = "sys_config"

    id = Column(Integer, primary_key=True, index=True)
    group = Column(String(50), nullable=False, index=True)  # system, llm, security, business
    key = Column(String(200), unique=True, nullable=False, index=True)
    value = Column(Text, default="")
    value_type = Column(String(20), default="string")  # string, number, boolean, json
    name = Column(String(200), nullable=False)
    description = Column(String(500), default="")
    is_public = Column(Boolean, default=False)  # accessible without login
    is_system = Column(Boolean, default=False)  # built-in, cannot delete
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, nullable=True)  # FK to employees (nullable for system init)
