"""
消息通知 ORM 模型 — 站内消息 + 消息模板 + 系统公告
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text
)
from app.database import Base


class SysMessage(Base):
    """站内消息表"""
    __tablename__ = "sys_message"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("employees.id"), nullable=True)  # null=系统消息
    recipient_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    msg_type = Column(String(20), nullable=False, default="system")  # system|business|todo
    related_entity_type = Column(String(50), nullable=True)  # 关联实体类型（如 Task, Room）
    related_entity_id = Column(Integer, nullable=True)        # 关联实体 ID
    is_read = Column(Boolean, default=False, index=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class SysMessageTemplate(Base):
    """消息模板表"""
    __tablename__ = "sys_message_template"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    channel = Column(String(20), nullable=False, default="internal")  # internal|email|sms|webhook
    subject_template = Column(String(500), nullable=False, default="")
    content_template = Column(Text, nullable=False, default="")
    variables = Column(Text, default="")  # JSON: 模板变量定义
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SysAnnouncement(Base):
    """系统公告表"""
    __tablename__ = "sys_announcement"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    publisher_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    status = Column(String(20), default="draft")  # draft|published|archived
    publish_at = Column(DateTime, nullable=True)
    expire_at = Column(DateTime, nullable=True)
    is_pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SysAnnouncementRead(Base):
    """公告已读记录"""
    __tablename__ = "sys_announcement_read"

    announcement_id = Column(Integer, ForeignKey("sys_announcement.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True)
    read_at = Column(DateTime, default=datetime.utcnow)
