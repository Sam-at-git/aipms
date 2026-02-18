"""
定时任务 ORM 模型 — 任务定义 + 执行日志
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship
from app.database import Base


class SysJob(Base):
    """定时任务表"""
    __tablename__ = "sys_job"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(100), unique=True, nullable=False, index=True)
    group = Column(String(50), nullable=True, default="default")
    invoke_target = Column(String(200), nullable=False)
    cron_expression = Column(String(100), nullable=False)
    misfire_policy = Column(String(20), nullable=False, default="ignore")
    is_concurrent = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    logs = relationship("SysJobLog", back_populates="job", lazy="dynamic")


class SysJobLog(Base):
    """任务执行日志表"""
    __tablename__ = "sys_job_log"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("sys_job.id"), nullable=False, index=True)
    status = Column(String(20), nullable=False)  # success / fail
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    result = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("SysJob", back_populates="logs")
