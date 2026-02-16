"""
core/engine/snapshot.py

Snapshot/undo engine - supports operation rollback.
Enhanced migration from app/services/undo_service.py.
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
    Operation snapshot - records state before and after an operation.

    Attributes:
        snapshot_id: Unique snapshot identifier
        operation_type: Type of operation
        entity_type: Entity type name
        entity_id: Entity identifier
        before_state: State before the operation (JSON-serializable)
        after_state: State after the operation (JSON-serializable)
        rollback_func: Rollback function
        timestamp: Snapshot creation time
        expires_at: Expiration time
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
        """Check whether the snapshot has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def mark_executed(self, after_state: Dict[str, Any]) -> None:
        """Mark the operation as executed and record the after-state."""
        self.after_state = after_state


class SnapshotEngine:
    """
    Snapshot engine - manages operation snapshots and undo.

    Features:
    - Snapshot creation and management
    - Operation undo
    - Automatic expiration cleanup
    - Thread-safe (simplified)

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
        Initialize the snapshot engine.

        Args:
            ttl_hours: Default snapshot TTL in hours.
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
        Create an operation snapshot.

        Args:
            operation_type: Type of operation
            entity_type: Entity type name
            entity_id: Entity identifier
            before_state: State before the operation
            rollback_func: Rollback function
            ttl_hours: TTL in hours; None uses the default

        Returns:
            The created snapshot object.
        """
        snapshot_id = str(uuid.uuid4())

        # Calculate expiration time
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

        # Index by entity
        if entity_id not in self._entity_snapshots:
            self._entity_snapshots[entity_id] = []
        self._entity_snapshots[entity_id].append(snapshot_id)

        logger.info(f"Snapshot created: {snapshot_id} for {entity_type}:{entity_id}")
        return snapshot

    def get_snapshot(self, snapshot_id: str) -> Optional[OperationSnapshot]:
        """Get a snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    def get_undoable_snapshots(
        self, entity_id: Optional[Any] = None, limit: int = 50
    ) -> List[OperationSnapshot]:
        """
        Get a list of undoable snapshots.

        Args:
            entity_id: Entity ID filter; None returns all.
            limit: Maximum number of results.

        Returns:
            List of snapshots, newest first.
        """
        # Clean up expired snapshots
        self._cleanup_expired()

        snapshots = list(self._snapshots.values())

        if entity_id is not None:
            snapshot_ids = self._entity_snapshots.get(entity_id, [])
            snapshots = [s for s in snapshots if s.snapshot_id in snapshot_ids]

        # Filter out unexecuted and expired
        valid_snapshots = [s for s in snapshots if s.after_state is not None and not s.is_expired()]

        # Sort by time descending
        valid_snapshots.sort(key=lambda s: s.timestamp, reverse=True)

        return valid_snapshots[:limit]

    def undo(self, snapshot_id: str) -> bool:
        """
        Undo an operation.

        Args:
            snapshot_id: Snapshot ID.

        Returns:
            True if undo succeeded.
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
        Mark an operation as executed.

        Args:
            snapshot_id: Snapshot ID.
            after_state: State after the operation.

        Returns:
            True if successful.
        """
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            return False

        snapshot.mark_executed(after_state)
        return True

    def _cleanup_expired(self) -> None:
        """Clean up expired snapshots."""
        expired_ids = [
            s.snapshot_id for s in self._snapshots.values() if s.is_expired()
        ]

        for snapshot_id in expired_ids:
            snapshot = self._snapshots.pop(snapshot_id, None)
            if snapshot:
                # Remove from entity index
                if snapshot.entity_id in self._entity_snapshots:
                    try:
                        self._entity_snapshots[snapshot.entity_id].remove(snapshot_id)
                    except ValueError:
                        pass

        if expired_ids:
            logger.debug(f"Cleaned up {len(expired_ids)} expired snapshots")

    def clear(self) -> None:
        """Clear all snapshots (for testing)."""
        self._snapshots.clear()
        self._entity_snapshots.clear()


# Global snapshot engine instance
snapshot_engine = SnapshotEngine()


__all__ = [
    "OperationSnapshot",
    "SnapshotEngine",
    "snapshot_engine",
]
