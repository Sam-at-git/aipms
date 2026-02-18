"""
操作快照模型 - 支持操作撤销功能
记录操作前后的状态，支持回滚
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class OperationType(str, Enum):
    """可撤销的操作类型"""
    CHECK_IN = "check_in"
    CHECK_OUT = "check_out"
    EXTEND_STAY = "extend_stay"
    CHANGE_ROOM = "change_room"
    CREATE_RESERVATION = "create_reservation"
    CANCEL_RESERVATION = "cancel_reservation"
    ASSIGN_TASK = "assign_task"
    COMPLETE_TASK = "complete_task"
    ADD_PAYMENT = "add_payment"


class OperationSnapshot(Base):
    """
    操作快照表
    记录每次可撤销操作的前后状态
    """
    __tablename__ = "operation_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_uuid = Column(String(36), unique=True, nullable=False, index=True)  # UUID
    operation_type = Column(String(50), nullable=False)
    operator_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    operation_time = Column(DateTime, nullable=False, default=datetime.utcnow)

    # 关联实体
    entity_type = Column(String(50), nullable=False)  # stay_record, reservation, task, room
    entity_id = Column(Integer, nullable=False)

    # 操作前后状态（JSON格式）
    before_state = Column(Text, nullable=False)
    after_state = Column(Text, nullable=False)

    # 关联快照（用于级联回滚，JSON数组）
    related_snapshots = Column(Text)

    # 是否已撤销
    is_undone = Column(Boolean, default=False)
    undone_time = Column(DateTime)
    undone_by = Column(Integer, ForeignKey("employees.id"))

    # 过期时间（超过后不可撤销）
    expires_at = Column(DateTime, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联
    operator = relationship("Employee", foreign_keys=[operator_id])
    undone_operator = relationship("Employee", foreign_keys=[undone_by])

    def __repr__(self):
        return f"<OperationSnapshot {self.snapshot_uuid}: {self.operation_type}>"


class ConfigHistory(Base):
    """
    配置变更历史表
    记录系统配置的版本历史
    """
    __tablename__ = "config_history"

    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), nullable=False, index=True)  # 配置项标识
    version = Column(Integer, nullable=False)

    # 变更内容（JSON格式）
    old_value = Column(Text, nullable=False)
    new_value = Column(Text, nullable=False)

    # 变更信息
    changed_by = Column(Integer, ForeignKey("employees.id"), nullable=False)
    changed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    change_reason = Column(Text)

    # 是否为当前版本
    is_current = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联
    changer = relationship("Employee")

    def __repr__(self):
        return f"<ConfigHistory {self.config_key} v{self.version}>"
