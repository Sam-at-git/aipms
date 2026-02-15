"""
菜单管理 ORM 模型
"""
from datetime import datetime, UTC

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class SysMenu(Base):
    __tablename__ = "sys_menu"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="菜单名称")
    code = Column(String(100), unique=True, nullable=False, comment="菜单编码")
    parent_id = Column(Integer, ForeignKey("sys_menu.id", ondelete="SET NULL"), nullable=True, comment="父菜单ID")
    path = Column(String(200), default="", comment="前端路由路径")
    icon = Column(String(50), default="", comment="图标名称")
    component = Column(String(200), default="", comment="前端组件路径")
    permission_code = Column(String(100), default="", comment="关联权限码")
    menu_type = Column(String(20), default="menu", comment="类型: directory|menu|button")
    is_visible = Column(Boolean, default=True, comment="是否在菜单中显示")
    sort_order = Column(Integer, default=0, comment="排序")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Self-referential relationship
    children = relationship("SysMenu", backref="parent", remote_side="SysMenu.id", lazy="selectin")
