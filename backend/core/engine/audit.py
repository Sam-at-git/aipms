"""
core/engine/audit.py

审计日志引擎 - 记录系统关键操作
从 app/services/audit_service.py 增强迁移
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AuditSeverity(str, Enum):
    """审计日志严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditLog:
    """
    审计日志条目

    Attributes:
        log_id: 日志唯一标识
        timestamp: 日志时间戳
        operator_id: 操作人ID
        action: 操作类型
        entity_type: 实体类型
        entity_id: 实体ID
        old_value: 旧值（JSON）
        new_value: 新值（JSON）
        severity: 严重程度
        ip_address: IP地址
        user_agent: 用户代理
        extra: 额外信息
    """

    log_id: str
    timestamp: datetime
    operator_id: Optional[int]
    action: str
    entity_type: Optional[str]
    entity_id: Optional[int]
    old_value: Optional[str]
    new_value: Optional[str]
    severity: AuditSeverity
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "log_id": self.log_id,
            "timestamp": self.timestamp.isoformat(),
            "operator_id": self.operator_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "severity": self.severity.value,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "extra": self.extra,
        }


class AuditEngine:
    """
    审计日志引擎

    特性：
    - 日志记录
    - 日志查询
    - 按实体/操作人筛选
    - 内存存储（可扩展为持久化）

    Example:
        >>> engine = AuditEngine()
        >>> engine.log(
        ...     operator_id=1,
        ...     action="room.update_status",
        ...     entity_type="Room",
        ...     entity_id=101,
        ...     old_value='{"status": "vacant"}',
        ...     new_value='{"status": "occupied"}'
        ... )
        >>> logs = engine.get_by_entity("Room", 101)
    """

    def __init__(self, max_logs: int = 10000):
        """
        初始化审计引擎

        Args:
            max_logs: 最大日志条数（内存存储）
        """
        self._logs: List[AuditLog] = []
        self._max_logs = max_logs
        self._operator_logs: Dict[int, List[str]] = {}  # operator_id -> log indices
        self._entity_logs: Dict[str, List[str]] = {}  # f"{type}:{id}" -> log indices

    def log(
        self,
        operator_id: Optional[int] = None,
        action: str = "",
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        记录审计日志

        Args:
            operator_id: 操作人ID
            action: 操作类型
            entity_type: 实体类型
            entity_id: 实体ID
            old_value: 旧值（JSON字符串）
            new_value: 新值（JSON字符串）
            severity: 严重程度
            ip_address: IP地址
            user_agent: 用户代理
            extra: 额外信息

        Returns:
            创建的审计日志
        """
        import uuid

        log = AuditLog(
            log_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            operator_id=operator_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            severity=severity,
            ip_address=ip_address,
            user_agent=user_agent,
            extra=extra or {},
        )

        # 添加到日志列表
        log_index = len(self._logs)
        self._logs.append(log)

        # 按操作人索引
        if operator_id is not None:
            if operator_id not in self._operator_logs:
                self._operator_logs[operator_id] = []
            self._operator_logs[operator_id].append(log_index)

        # 按实体索引
        if entity_type is not None and entity_id is not None:
            key = f"{entity_type}:{entity_id}"
            if key not in self._entity_logs:
                self._entity_logs[key] = []
            self._entity_logs[key].append(log_index)

        # 限制日志数量
        if len(self._logs) > self._max_logs:
            self._logs.pop(0)
            # 更新索引
            self._rebuild_indices()

        logger.info(f"Audit log: {action} by {operator_id} on {entity_type}:{entity_id}")
        return log

    def get_by_id(self, log_id: str) -> Optional[AuditLog]:
        """根据ID获取日志"""
        for log in self._logs:
            if log.log_id == log_id:
                return log
        return None

    def get_by_operator(
        self, operator_id: int, limit: int = 100
    ) -> List[AuditLog]:
        """获取操作人的日志"""
        indices = self._operator_logs.get(operator_id, [])
        return [self._logs[i] for i in indices if i < len(self._logs)][:limit]

    def get_by_entity(
        self, entity_type: str, entity_id: int, limit: int = 100
    ) -> List[AuditLog]:
        """获取实体的日志"""
        key = f"{entity_type}:{entity_id}"
        indices = self._entity_logs.get(key, [])
        return [self._logs[i] for i in indices if i < len(self._logs)][:limit]

    def get_by_action(self, action: str, limit: int = 100) -> List[AuditLog]:
        """获取指定操作的日志"""
        return [log for log in self._logs if log.action == action][:limit]

    def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        severity: Optional[AuditSeverity] = None,
    ) -> List[AuditLog]:
        """
        获取所有日志（分页）

        Args:
            limit: 返回数量限制
            offset: 偏移量
            severity: 筛选严重程度

        Returns:
            日志列表
        """
        logs = self._logs

        if severity is not None:
            logs = [log for log in logs if log.severity == severity]

        return logs[offset : offset + limit]

    def get_statistics(self) -> Dict[str, Any]:
        """获取审计统计"""
        return {
            "total_logs": len(self._logs),
            "by_severity": {
                severity.value: len([log for log in self._logs if log.severity == severity])
                for severity in AuditSeverity
            },
            "by_action": self._get_action_counts(),
        }

    def _get_action_counts(self) -> Dict[str, int]:
        """获取操作计数"""
        counts: Dict[str, int] = {}
        for log in self._logs:
            counts[log.action] = counts.get(log.action, 0) + 1
        return counts

    def _rebuild_indices(self) -> None:
        """重建索引（在删除旧日志后）"""
        self._operator_logs.clear()
        self._entity_logs.clear()

        for i, log in enumerate(self._logs):
            if log.operator_id is not None:
                if log.operator_id not in self._operator_logs:
                    self._operator_logs[log.operator_id] = []
                self._operator_logs[log.operator_id].append(i)

            if log.entity_type is not None and log.entity_id is not None:
                key = f"{log.entity_type}:{log.entity_id}"
                if key not in self._entity_logs:
                    self._entity_logs[key] = []
                self._entity_logs[key].append(i)

    def clear(self) -> None:
        """清空所有日志（用于测试）"""
        self._logs.clear()
        self._operator_logs.clear()
        self._entity_logs.clear()


# 全局审计引擎实例
audit_engine = AuditEngine()


# 导出
__all__ = [
    "AuditSeverity",
    "AuditLog",
    "AuditEngine",
    "audit_engine",
]
