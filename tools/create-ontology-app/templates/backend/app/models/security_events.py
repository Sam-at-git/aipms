"""
安全事件定义
定义可检测的安全事件类型、严重程度和告警阈值
"""
from enum import Enum
from datetime import datetime, UTC
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from app.database import Base


class SecurityEventType(str, Enum):
    """安全事件类型"""
    # 认证相关
    LOGIN_FAILED = "login_failed"
    LOGIN_SUCCESS = "login_success"
    MULTIPLE_LOGIN_FAILURES = "multiple_login_failures"  # 连续失败超过阈值
    LOGOUT = "logout"

    # 授权相关
    UNAUTHORIZED_ACCESS = "unauthorized_access"  # 尝试访问无权限资源
    ROLE_ESCALATION_ATTEMPT = "role_escalation_attempt"  # 尝试越权操作

    # 操作相关
    SENSITIVE_DATA_ACCESS = "sensitive_data_access"  # 访问敏感数据
    BULK_DATA_EXPORT = "bulk_data_export"  # 大量数据导出
    UNUSUAL_TIME_ACCESS = "unusual_time_access"  # 异常时间访问

    # 配置相关
    SECURITY_CONFIG_CHANGED = "security_config_changed"  # 安全配置变更
    PASSWORD_CHANGED = "password_changed"  # 密码修改


class SecurityEventSeverity(str, Enum):
    """事件严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# SQLAlchemy ORM 模型
class SecurityEventModel(Base):
    """安全事件数据库模型"""
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.now(UTC), index=True)
    source_ip = Column(String(50))
    user_id = Column(Integer, index=True)
    user_name = Column(String(100))
    description = Column(Text, nullable=False)
    details = Column(Text)  # JSON string
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(Integer)
    acknowledged_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now(UTC))


# Pydantic 模型用于 API
class SecurityEvent(BaseModel):
    """安全事件响应模型"""
    id: int
    event_type: SecurityEventType
    severity: SecurityEventSeverity
    timestamp: datetime
    source_ip: Optional[str] = None
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    description: str
    details: Dict[str, Any] = {}
    is_acknowledged: bool = False
    acknowledged_by: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class SecurityEventCreate(BaseModel):
    """创建安全事件的请求模型"""
    event_type: SecurityEventType
    severity: SecurityEventSeverity = SecurityEventSeverity.LOW
    source_ip: Optional[str] = None
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    description: str
    details: Dict[str, Any] = {}


class SecurityStatistics(BaseModel):
    """安全统计响应模型"""
    total: int
    unacknowledged: int
    by_type: Dict[str, int]
    by_severity: Dict[str, int]
    time_range_hours: int


# 告警阈值配置
ALERT_THRESHOLDS = {
    SecurityEventType.LOGIN_FAILED: {
        "count": 3,
        "window_minutes": 5,
        "escalate_to": SecurityEventType.MULTIPLE_LOGIN_FAILURES,
        "escalate_severity": SecurityEventSeverity.HIGH
    },
    SecurityEventType.UNAUTHORIZED_ACCESS: {
        "count": 5,
        "window_minutes": 10,
        "severity": SecurityEventSeverity.HIGH
    },
    SecurityEventType.ROLE_ESCALATION_ATTEMPT: {
        "count": 1,
        "window_minutes": 1,
        "severity": SecurityEventSeverity.CRITICAL
    }
}


# 事件严重程度描述
SEVERITY_DESCRIPTIONS = {
    SecurityEventSeverity.LOW: "低风险 - 正常操作记录",
    SecurityEventSeverity.MEDIUM: "中等风险 - 需要关注",
    SecurityEventSeverity.HIGH: "高风险 - 需要及时处理",
    SecurityEventSeverity.CRITICAL: "紧急 - 需要立即处理"
}


# 事件类型描述
EVENT_TYPE_DESCRIPTIONS = {
    SecurityEventType.LOGIN_FAILED: "登录失败",
    SecurityEventType.LOGIN_SUCCESS: "登录成功",
    SecurityEventType.MULTIPLE_LOGIN_FAILURES: "多次登录失败",
    SecurityEventType.LOGOUT: "用户登出",
    SecurityEventType.UNAUTHORIZED_ACCESS: "未授权访问尝试",
    SecurityEventType.ROLE_ESCALATION_ATTEMPT: "权限提升尝试",
    SecurityEventType.SENSITIVE_DATA_ACCESS: "敏感数据访问",
    SecurityEventType.BULK_DATA_EXPORT: "批量数据导出",
    SecurityEventType.UNUSUAL_TIME_ACCESS: "异常时间访问",
    SecurityEventType.SECURITY_CONFIG_CHANGED: "安全配置变更",
    SecurityEventType.PASSWORD_CHANGED: "密码已修改"
}
