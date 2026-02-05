"""
core/engine/snapshot.py

快照/撤销引擎 - 支持操作回滚
从 app/services/undo_service.py 增强迁移
"""
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import uuid

logger = logging.getLogger(__name__)


@dataclass
class OperationSnapshot:
    """
    操作快照 - 记录操作前后的状态

    Attributes:
        snapshot_id: 快照唯一标识
        operation_type: 操作类型
        entity_type: 实体类型
        entity_id: 实体ID
        before_state: 操作前的状态（JSON序列化）
        after_state: 操作后的状态（JSON序列化）
        rollback_func: 回滚函数
        timestamp: 快照时间
        expires_at: 过期时间
    """

    snapshot_id: str
    operation_type: str
    entity_type: str
    entity_id: Any
    before_state: Dict[str, Any]
    after_state: Optional[Dict[str, Any]] = None
    rollback_func: Optional[Callable[[], None]] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    def is_expired(self) -> bool:
        """检查快照是否过期"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def mark_executed(self, after_state: Dict[str, Any]) -> None:
        """标记操作已执行，记录后状态"""
        self.after_state = after_state


class SnapshotEngine:
    """
    快照引擎 - 管理操作快照和撤销

    特性：
    - 快照创建和管理
    - 操作撤销
    - 自动过期清理
    - 线程安全（简化版）

    Example:
        >>> engine = SnapshotEngine()
        >>> snapshot = engine.create_snapshot(
        ...     operation_type="checkin",
        ...     entity_type="StayRecord",
        ...     entity_id=123,
        ...     before_state={"status": "pending"},
        ...     rollback_func=lambda: print("Rollback")
        ... )
        >>> engine.undo(snapshot.snapshot_id)
    """

    def __init__(self, ttl_hours: int = 24):
        """
        初始化快照引擎

        Args:
            ttl_hours: 快照默认有效期（小时）
        """
        self._snapshots: Dict[str, OperationSnapshot] = {}
        self._ttl_hours = ttl_hours
        self._entity_snapshots: Dict[Any, List[str]] = {}  # entity_id -> snapshot_ids

    def create_snapshot(
        self,
        operation_type: str,
        entity_type: str,
        entity_id: Any,
        before_state: Dict[str, Any],
        rollback_func: Optional[Callable[[], None]] = None,
        ttl_hours: Optional[int] = None,
    ) -> OperationSnapshot:
        """
        创建操作快照

        Args:
            operation_type: 操作类型
            entity_type: 实体类型
            entity_id: 实体ID
            before_state: 操作前状态
            rollback_func: 回滚函数
            ttl_hours: 有效期（小时），None 表示使用默认值

        Returns:
            创建的快照对象
        """
        snapshot_id = str(uuid.uuid4())

        # 计算过期时间
        expires_at = None
        if ttl_hours is not None:
            expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        elif self._ttl_hours > 0:
            expires_at = datetime.utcnow() + timedelta(hours=self._ttl_hours)

        snapshot = OperationSnapshot(
            snapshot_id=snapshot_id,
            operation_type=operation_type,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            rollback_func=rollback_func,
            expires_at=expires_at,
        )

        self._snapshots[snapshot_id] = snapshot

        # 按实体索引
        if entity_id not in self._entity_snapshots:
            self._entity_snapshots[entity_id] = []
        self._entity_snapshots[entity_id].append(snapshot_id)

        logger.info(f"Snapshot created: {snapshot_id} for {entity_type}:{entity_id}")
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[OperationSnapshot]:
        """获取快照"""
        return self._snapshots.get(snapshot_id)

    def get_undoable_snapshots(
        self, entity_id: Optional[Any] = None, limit: int = 50
    ) -> List[OperationSnapshot]:
        """
        获取可撤销的快照列表

        Args:
            entity_id: 实体ID，None 表示获取所有
            limit: 返回数量限制

        Returns:
            快照列表（最新的在前）
        """
        # 清理过期快照
        self._cleanup_expired()

        snapshots = list(self._snapshots.values())

        if entity_id is not None:
            snapshot_ids = self._entity_snapshots.get(entity_id, [])
            snapshots = [s for s in snapshots if s.snapshot_id in snapshot_ids]

        # 过滤未执行的和过期的
        valid_snapshots = [s for s in snapshots if s.after_state is not None and not s.is_expired()]

        # 按时间倒序排序
        valid_snapshots.sort(key=lambda s: s.timestamp, reverse=True)

        return valid_snapshots[:limit]

    def undo(self, snapshot_id: str) -> bool:
        """
        撤销操作

        Args:
            snapshot_id: 快照ID

        Returns:
            True 如果撤销成功
        """
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            logger.warning(f"Snapshot not found: {snapshot_id}")
            return False

        if snapshot.is_expired():
            logger.warning(f"Snapshot expired: {snapshot_id}")
            return False

        if snapshot.rollback_func is None:
            logger.warning(f"Snapshot has no rollback function: {snapshot_id}")
            return False

        try:
            snapshot.rollback_func()
            logger.info(f"Undo successful: {snapshot_id}")
            return True
        except Exception as e:
            logger.error(f"Undo failed for {snapshot_id}: {e}", exc_info=True)
            return False

    def mark_executed(self, snapshot_id: str, after_state: Dict[str, Any]) -> bool:
        """
        标记操作已执行

        Args:
            snapshot_id: 快照ID
            after_state: 操作后状态

        Returns:
            True 如果成功
        """
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            return False

        snapshot.mark_executed(after_state)
        return True

    def _cleanup_expired(self) -> None:
        """清理过期快照"""
        expired_ids = [
            s.snapshot_id for s in self._snapshots.values() if s.is_expired()
        ]

        for snapshot_id in expired_ids:
            snapshot = self._snapshots.pop(snapshot_id, None)
            if snapshot:
                # 从实体索引中移除
                if snapshot.entity_id in self._entity_snapshots:
                    try:
                        self._entity_snapshots[snapshot.entity_id].remove(snapshot_id)
                    except ValueError:
                        pass

        if expired_ids:
            logger.debug(f"Cleaned up {len(expired_ids)} expired snapshots")

    def clear(self) -> None:
        """清空所有快照（用于测试）"""
        self._snapshots.clear()
        self._entity_snapshots.clear()


# 全局快照引擎实例
snapshot_engine = SnapshotEngine()


# 导出
__all__ = [
    "OperationSnapshot",
    "SnapshotEngine",
    "snapshot_engine",
]
