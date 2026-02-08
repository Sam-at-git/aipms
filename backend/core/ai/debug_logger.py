"""
core/ai/debug_logger.py

DebugLogger - Complete session tracking and replay support for AI decision-making.

This module provides comprehensive logging of AI interactions:
- User input and retrieved schema/tools
- LLM prompts and responses
- Action execution attempts (success/failure)
- Error tracking and retry history
- Performance metrics (execution time, tokens)

Supports session replay for debugging and analysis.
"""
import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# ==================== Data Models ====================

@dataclass
class DebugSession:
    """
    A complete debug session record.

    Tracks the full lifecycle of an AI interaction from input to result.
    """

    session_id: str
    timestamp: datetime
    user_id: Optional[int]
    user_role: Optional[str]

    # Input
    input_message: str

    # Retrieved context (JSON strings)
    retrieved_schema: Optional[str] = None
    retrieved_tools: Optional[str] = None

    # LLM interaction
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    llm_tokens_used: Optional[int] = None
    llm_model: Optional[str] = None

    # Execution
    actions_executed: Optional[str] = None  # JSON list
    execution_time_ms: Optional[int] = None

    # Result
    final_result: Optional[str] = None  # JSON
    errors: Optional[str] = None  # JSON list

    # Metadata
    status: str = "pending"  # pending, success, error, partial
    metadata: Optional[str] = None  # JSON

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, parsing JSON fields."""
        result = {
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "user_role": self.user_role,
            "input_message": self.input_message,
            "retrieved_schema": self._parse_json(self.retrieved_schema),
            "retrieved_tools": self._parse_json(self.retrieved_tools),
            "llm_prompt": self.llm_prompt,
            "llm_response": self.llm_response,
            "llm_tokens_used": self.llm_tokens_used,
            "llm_model": self.llm_model,
            "actions_executed": self._parse_json(self.actions_executed),
            "execution_time_ms": self.execution_time_ms,
            "final_result": self._parse_json(self.final_result),
            "errors": self._parse_json(self.errors),
            "status": self.status,
            "metadata": self._parse_json(self.metadata)
        }
        return result

    @staticmethod
    def _parse_json(value: Optional[str]) -> Optional[Any]:
        """Safely parse JSON string."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "DebugSession":
        """Create DebugSession from database row."""
        return cls(
            session_id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            user_id=row["user_id"],
            user_role=row["user_role"],
            input_message=row["input_message"],
            retrieved_schema=row["retrieved_schema"],
            retrieved_tools=row["retrieved_tools"],
            llm_prompt=row["llm_prompt"],
            llm_response=row["llm_response"],
            llm_tokens_used=row["llm_tokens_used"],
            llm_model=row["llm_model"],
            actions_executed=row["actions_executed"],
            execution_time_ms=row["execution_time_ms"],
            final_result=row["final_result"],
            errors=row["errors"],
            status=row["status"],
            metadata=row["metadata"]
        )


@dataclass
class AttemptLog:
    """Record of a single execution attempt within a session."""

    attempt_id: str
    session_id: str
    attempt_number: int
    action_name: str
    params: str  # JSON
    success: bool
    error: Optional[str] = None  # JSON
    result: Optional[str] = None  # JSON
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, parsing JSON fields."""
        return {
            "attempt_id": self.attempt_id,
            "session_id": self.session_id,
            "attempt_number": self.attempt_number,
            "action_name": self.action_name,
            "params": self._parse_json(self.params),
            "success": self.success,
            "error": self._parse_json(self.error),
            "result": self._parse_json(self.result),
            "timestamp": self.timestamp.isoformat()
        }

    @staticmethod
    def _parse_json(value: Optional[str]) -> Optional[Any]:
        """Safely parse JSON string."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "AttemptLog":
        """Create AttemptLog from database row."""
        return cls(
            attempt_id=row["attempt_id"],
            session_id=row["session_id"],
            attempt_number=row["attempt_number"],
            action_name=row["action_name"],
            params=row["params"],
            success=bool(row["success"]),
            error=row["error"],
            result=row["result"],
            timestamp=datetime.fromisoformat(row["timestamp"])
        )


# ==================== Debug Logger ====================

class DebugLogger:
    """
    Debug session logger for AI decision-making.

    Provides complete observability into AI interactions:
    - Session lifecycle tracking
    - Attempt-level execution logging
    - Error and retry history
    - Performance metrics

    Database stored at db_path (default: data/debug_logs.db)

    Example:
        ```python
        logger = DebugLogger()

        # Start session
        session_id = logger.create_session(
            input_message="查询在住客人",
            user=current_user
        )

        # Log retrieval
        logger.update_session_retrieval(
            session_id,
            retrieved_schema={"entities": ["Guest"]},
            retrieved_tools=[...]
        )

        # Log LLM call
        logger.update_session_llm(
            session_id,
            prompt="...",
            response="...",
            tokens_used=500,
            model="deepseek-chat"
        )

        # Log attempt
        logger.log_attempt(
            session_id,
            action_name="ontology_query",
            params={...},
            success=True,
            result={...}
        )

        # Complete session
        logger.complete_session(
            session_id,
            result={"rows": [...]},
            status="success"
        )
        ```
    """

    # Default database path
    DEFAULT_DB_PATH = "data/debug_logs.db"

    # Session cleanup days
    DEFAULT_RETENTION_DAYS = 30

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize DebugLogger.

        Args:
            db_path: Path to SQLite database. Defaults to DEFAULT_DB_PATH.
                    Use ":memory:" for in-memory database (testing).
        """
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_conn()
        try:
            # Create debug_sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS debug_sessions (
                    id TEXT PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER,
                    user_role TEXT,

                    -- Input
                    input_message TEXT NOT NULL,

                    -- Retrieved context
                    retrieved_schema TEXT,
                    retrieved_tools TEXT,

                    -- LLM interaction
                    llm_prompt TEXT,
                    llm_response TEXT,
                    llm_tokens_used INTEGER,
                    llm_model TEXT,

                    -- Execution
                    actions_executed TEXT,
                    execution_time_ms INTEGER,

                    -- Result
                    final_result TEXT,
                    errors TEXT,

                    -- Metadata
                    status TEXT DEFAULT 'pending',
                    metadata TEXT
                )
            """)

            # Create attempt_logs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attempt_logs (
                    attempt_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    action_name TEXT NOT NULL,
                    params TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    error TEXT,
                    result TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES debug_sessions(id) ON DELETE CASCADE
                )
            """)

            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_debug_sessions_timestamp
                ON debug_sessions(timestamp DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_debug_sessions_user
                ON debug_sessions(user_id, timestamp DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_debug_sessions_status
                ON debug_sessions(status, timestamp DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_attempt_logs_session
                ON attempt_logs(session_id, attempt_number)
            """)

            conn.commit()
            logger.debug(f"DebugLogger: Database initialized at {self.db_path}")

        finally:
            conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ==================== Session Management ====================

    def create_session(
        self,
        input_message: str,
        user: Optional[Any] = None
    ) -> str:
        """
        Create a new debug session.

        Args:
            input_message: User input message
            user: Optional user object (must have id and role attributes)

        Returns:
            session_id: UUID for the new session
        """
        session_id = str(uuid.uuid4())
        timestamp = datetime.now()

        user_id = getattr(user, "id", None) if user else None
        user_role = getattr(user, "role", None) if user else None
        if user_role and hasattr(user_role, "value"):
            user_role = user_role.value

        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO debug_sessions
                (id, timestamp, user_id, user_role, input_message, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                timestamp.isoformat(),
                user_id,
                user_role,
                input_message,
                "pending"
            ))
            conn.commit()
            logger.debug(f"DebugLogger: Created session {session_id}")
            return session_id

        finally:
            conn.close()

    def update_session_retrieval(
        self,
        session_id: str,
        retrieved_schema: Optional[Dict[str, Any]] = None,
        retrieved_tools: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Update session with retrieved context.

        Args:
            session_id: Session ID
            retrieved_schema: Schema retrieval result (will be JSON-encoded)
            retrieved_tools: Tool retrieval result (will be JSON-encoded)

        Returns:
            True if update successful, False if session not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                UPDATE debug_sessions
                SET retrieved_schema = ?, retrieved_tools = ?
                WHERE id = ?
            """, (
                json.dumps(retrieved_schema) if retrieved_schema is not None else None,
                json.dumps(retrieved_tools) if retrieved_tools is not None else None,
                session_id
            ))
            conn.commit()
            return cursor.rowcount > 0

        finally:
            conn.close()

    def update_session_llm(
        self,
        session_id: str,
        prompt: str,
        response: str,
        tokens_used: int,
        model: str
    ) -> bool:
        """
        Update session with LLM interaction data.

        Args:
            session_id: Session ID
            prompt: LLM prompt
            response: LLM response
            tokens_used: Number of tokens used
            model: Model name

        Returns:
            True if update successful, False if session not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                UPDATE debug_sessions
                SET llm_prompt = ?, llm_response = ?, llm_tokens_used = ?, llm_model = ?
                WHERE id = ?
            """, (prompt, response, tokens_used, model, session_id))
            conn.commit()
            return cursor.rowcount > 0

        finally:
            conn.close()

    def complete_session(
        self,
        session_id: str,
        result: Optional[Dict[str, Any]] = None,
        status: str = "success",
        execution_time_ms: Optional[int] = None,
        actions_executed: Optional[List[Dict[str, Any]]] = None,
        errors: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Mark session as complete with final result.

        Args:
            session_id: Session ID
            result: Final result (will be JSON-encoded)
            status: Session status (success, error, partial)
            execution_time_ms: Execution time in milliseconds
            actions_executed: List of executed actions
            errors: List of errors that occurred

        Returns:
            True if update successful, False if session not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                UPDATE debug_sessions
                SET final_result = ?, status = ?, execution_time_ms = ?,
                    actions_executed = ?, errors = ?
                WHERE id = ?
            """, (
                json.dumps(result) if result is not None else None,
                status,
                execution_time_ms,
                json.dumps(actions_executed) if actions_executed is not None else None,
                json.dumps(errors) if errors is not None else None,
                session_id
            ))
            conn.commit()
            logger.debug(f"DebugLogger: Completed session {session_id} with status {status}")
            return cursor.rowcount > 0

        finally:
            conn.close()

    # ==================== Attempt Logging ====================

    def log_attempt(
        self,
        session_id: str,
        action_name: str,
        params: Dict[str, Any],
        success: bool,
        error: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        attempt_number: Optional[int] = None
    ) -> Optional[str]:
        """
        Log an execution attempt.

        Args:
            session_id: Session ID
            action_name: Name of action executed
            params: Action parameters (will be JSON-encoded)
            success: Whether attempt succeeded
            error: Error details if failed (will be JSON-encoded)
            result: Result if succeeded (will be JSON-encoded)
            attempt_number: Attempt number (auto-incremented if None)

        Returns:
            attempt_id if successful, None if session not found
        """
        # Verify session exists first
        if not self.get_session(session_id):
            return None

        # Auto-increment attempt_number
        if attempt_number is None:
            attempt_number = self._get_next_attempt_number(session_id)

        attempt_id = str(uuid.uuid4())
        timestamp = datetime.now()

        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO attempt_logs
                (attempt_id, session_id, attempt_number, action_name, params, success, error, result, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                attempt_id,
                session_id,
                attempt_number,
                action_name,
                json.dumps(params),
                success,
                json.dumps(error) if error else None,
                json.dumps(result) if result else None,
                timestamp.isoformat()
            ))
            conn.commit()
            logger.debug(f"DebugLogger: Logged attempt {attempt_id} for session {session_id}")
            return attempt_id

        finally:
            conn.close()

    def _get_next_attempt_number(self, session_id: str) -> Optional[int]:
        """Get next attempt number for a session."""
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT COALESCE(MAX(attempt_number), -1) + 1 as next_num
                FROM attempt_logs
                WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            return row["next_num"] if row else None

        finally:
            conn.close()

    # ==================== Query Methods ====================

    def get_session(self, session_id: str) -> Optional[DebugSession]:
        """
        Get a debug session by ID.

        Args:
            session_id: Session ID

        Returns:
            DebugSession if found, None otherwise
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT * FROM debug_sessions WHERE id = ?
            """, (session_id,))
            row = cursor.fetchone()
            return DebugSession.from_row(row) if row else None

        finally:
            conn.close()

    def list_sessions(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[DebugSession]:
        """
        List debug sessions with optional filters.

        Args:
            user_id: Filter by user ID
            status: Filter by status (success, error, partial)
            limit: Maximum number of sessions to return
            offset: Offset for pagination

        Returns:
            List of DebugSession objects
        """
        conn = self._get_conn()
        try:
            query = "SELECT * FROM debug_sessions"
            params: List = []

            conditions = []
            if user_id is not None:
                conditions.append("user_id = ?")
                params.append(user_id)
            if status is not None:
                conditions.append("status = ?")
                params.append(status)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor = conn.execute(query, params)
            return [DebugSession.from_row(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_attempts(self, session_id: str) -> List[AttemptLog]:
        """
        Get all attempts for a session.

        Args:
            session_id: Session ID

        Returns:
            List of AttemptLog objects ordered by attempt_number
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT * FROM attempt_logs
                WHERE session_id = ?
                ORDER BY attempt_number ASC
            """, (session_id,))
            return [AttemptLog.from_row(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_attempt(self, attempt_id: str) -> Optional[AttemptLog]:
        """
        Get a specific attempt by ID.

        Args:
            attempt_id: Attempt ID

        Returns:
            AttemptLog if found, None otherwise
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT * FROM attempt_logs WHERE attempt_id = ?
            """, (attempt_id,))
            row = cursor.fetchone()
            return AttemptLog.from_row(row) if row else None

        finally:
            conn.close()

    # ==================== Management ====================

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its attempts.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                DELETE FROM attempt_logs WHERE session_id = ?
            """, (session_id,))
            cursor = conn.execute("""
                DELETE FROM debug_sessions WHERE id = ?
            """, (session_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.debug(f"DebugLogger: Deleted session {session_id}")
            return deleted

        finally:
            conn.close()

    def cleanup_old_sessions(self, days: int = DEFAULT_RETENTION_DAYS) -> int:
        """
        Delete sessions older than specified days.

        Args:
            days: Number of days to retain (default: DEFAULT_RETENTION_DAYS)

        Returns:
            Number of sessions deleted
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                DELETE FROM attempt_logs
                WHERE session_id IN (
                    SELECT id FROM debug_sessions WHERE timestamp < ?
                )
            """, (cutoff_date,))

            cursor = conn.execute("""
                DELETE FROM debug_sessions WHERE timestamp < ?
            """, (cutoff_date,))

            conn.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(f"DebugLogger: Cleaned up {deleted} old sessions (older than {days} days)")
            return deleted

        finally:
            conn.close()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get debug logger statistics.

        Returns:
            Dict with total_sessions, total_attempts, status_counts, etc.
        """
        conn = self._get_conn()
        try:
            # Total sessions
            cursor = conn.execute("SELECT COUNT(*) as count FROM debug_sessions")
            total_sessions = cursor.fetchone()["count"]

            # Total attempts
            cursor = conn.execute("SELECT COUNT(*) as count FROM attempt_logs")
            total_attempts = cursor.fetchone()["count"]

            # Status counts
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM debug_sessions
                GROUP BY status
            """)
            status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

            # Recent sessions (last 24h)
            cursor = conn.execute("""
                SELECT COUNT(*) as count
                FROM debug_sessions
                WHERE timestamp > datetime('now', '-1 day')
            """)
            recent_sessions = cursor.fetchone()["count"]

            return {
                "total_sessions": total_sessions,
                "total_attempts": total_attempts,
                "status_counts": status_counts,
                "recent_sessions_24h": recent_sessions
            }

        finally:
            conn.close()

    def export_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Export a complete session with all attempts for replay.

        Args:
            session_id: Session ID

        Returns:
            Dict containing session data and all attempts, or None if not found
        """
        session = self.get_session(session_id)
        if not session:
            return None

        attempts = self.get_attempts(session_id)

        return {
            "session": session.to_dict(),
            "attempts": [attempt.to_dict() for attempt in attempts]
        }


__all__ = [
    "DebugLogger",
    "DebugSession",
    "AttemptLog",
]
