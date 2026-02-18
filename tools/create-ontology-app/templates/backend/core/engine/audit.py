"""
core/engine/audit.py

Audit log engine - records critical system operations.
Enhanced migration from app/services/audit_service.py.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AuditSeverity(str, Enum):
    """Audit log severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditLog:
    """
    Audit log entry.

    Attributes:
        log_id: Unique log identifier
        timestamp: Log timestamp
        operator_id: Operator (user) ID
        action: Action type
        entity_type: Entity type name
        entity_id: Entity identifier
        old_value: Previous value (JSON string)
        new_value: New value (JSON string)
        severity: Severity level
        ip_address: Client IP address
        user_agent: Client user agent
        extra: Additional metadata
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
        """Convert to dictionary."""
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
    Audit log engine.

    Features:
    - Log recording
    - Log querying
    - Filtering by entity or operator
    - In-memory storage (extensible to persistent)

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
        Initialize the audit engine.

        Args:
            max_logs: Maximum log entries (in-memory storage).
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
        Record an audit log entry.

        Args:
            operator_id: Operator (user) ID
            action: Action type
            entity_type: Entity type name
            entity_id: Entity identifier
            old_value: Previous value (JSON string)
            new_value: New value (JSON string)
            severity: Severity level
            ip_address: Client IP address
            user_agent: Client user agent
            extra: Additional metadata

        Returns:
            The created audit log entry.
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

        # Add to log list
        log_index = len(self._logs)
        self._logs.append(log)

        # Index by operator
        if operator_id is not None:
            if operator_id not in self._operator_logs:
                self._operator_logs[operator_id] = []
            self._operator_logs[operator_id].append(log_index)

        # Index by entity
        if entity_type is not None and entity_id is not None:
            key = f"{entity_type}:{entity_id}"
            if key not in self._entity_logs:
                self._entity_logs[key] = []
            self._entity_logs[key].append(log_index)

        # Limit log count
        if len(self._logs) > self._max_logs:
            self._logs.pop(0)
            # Rebuild indices
            self._rebuild_indices()

        logger.info(f"Audit log: {action} by {operator_id} on {entity_type}:{entity_id}")
        return log

    def get_by_id(self, log_id: str) -> Optional[AuditLog]:
        """Get a log entry by ID."""
        for log in self._logs:
            if log.log_id == log_id:
                return log
        return None

    def get_by_operator(
        self, operator_id: int, limit: int = 100
    ) -> List[AuditLog]:
        """Get log entries for a specific operator."""
        indices = self._operator_logs.get(operator_id, [])
        return [self._logs[i] for i in indices if i < len(self._logs)][:limit]

    def get_by_entity(
        self, entity_type: str, entity_id: int, limit: int = 100
    ) -> List[AuditLog]:
        """Get log entries for a specific entity."""
        key = f"{entity_type}:{entity_id}"
        indices = self._entity_logs.get(key, [])
        return [self._logs[i] for i in indices if i < len(self._logs)][:limit]

    def get_by_action(self, action: str, limit: int = 100) -> List[AuditLog]:
        """Get log entries for a specific action type."""
        return [log for log in self._logs if log.action == action][:limit]

    def get_all(
        self,
        limit: int = 100,
        offset: int = 0,
        severity: Optional[AuditSeverity] = None,
    ) -> List[AuditLog]:
        """
        Get all log entries (paginated).

        Args:
            limit: Maximum number of results.
            offset: Pagination offset.
            severity: Filter by severity level.

        Returns:
            List of audit log entries.
        """
        logs = self._logs

        if severity is not None:
            logs = [log for log in logs if log.severity == severity]

        return logs[offset : offset + limit]

    def get_statistics(self) -> Dict[str, Any]:
        """Get audit statistics."""
        return {
            "total_logs": len(self._logs),
            "by_severity": {
                severity.value: len([log for log in self._logs if log.severity == severity])
                for severity in AuditSeverity
            },
            "by_action": self._get_action_counts(),
        }

    def _get_action_counts(self) -> Dict[str, int]:
        """Get action counts."""
        counts: Dict[str, int] = {}
        for log in self._logs:
            counts[log.action] = counts.get(log.action, 0) + 1
        return counts

    def _rebuild_indices(self) -> None:
        """Rebuild indices (after removing old logs)."""
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
        """Clear all logs (for testing)."""
        self._logs.clear()
        self._operator_logs.clear()
        self._entity_logs.clear()


# Global audit engine instance
audit_engine = AuditEngine()


__all__ = [
    "AuditSeverity",
    "AuditLog",
    "AuditEngine",
    "audit_engine",
]
