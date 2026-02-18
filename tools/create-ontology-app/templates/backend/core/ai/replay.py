"""
core/ai/replay.py

ReplayEngine - Re-execute recorded AI sessions with parameter overrides.

This module provides the ability to replay previously recorded AI sessions
from DebugLogger with different parameters for debugging, A/B testing,
and root cause analysis.

Key features:
- Load complete session data from DebugLogger
- Apply parameter overrides (LLM model, temperature, etc.)
- Re-execute using ReflexionLoop
- Generate comparison diffs
- Store replay results separately
"""
import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from core.ai.debug_logger import DebugLogger, DebugSession, AttemptLog
    from core.ai.actions import ActionRegistry
    from core.ai.llm_client import LLMClient
    from core.ai.reflexion import ReflexionLoop, AttemptRecord

logger = logging.getLogger(__name__)


# ==================== Data Models ====================

@dataclass
class ReplayOverrides:
    """
    Parameters to override during replay.

    Allows modifying various aspects of the original execution:
    - LLM configuration (model, temperature, tokens)
    - Schema and tools retrieval
    - Specific action parameters

    Attributes:
        llm_model: Override LLM model name
        llm_temperature: Override LLM temperature
        llm_max_tokens: Override max tokens
        llm_base_url: Override LLM base URL
        schema_override: Override retrieved schema
        tools_override: Override retrieved tools
        action_params_override: Override specific action params (action_name -> params)
    """

    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    llm_base_url: Optional[str] = None
    schema_override: Optional[Dict[str, Any]] = None
    tools_override: Optional[List[Dict[str, Any]]] = None
    action_params_override: Optional[Dict[str, Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "llm_model": self.llm_model,
            "llm_temperature": self.llm_temperature,
            "llm_max_tokens": self.llm_max_tokens,
            "llm_base_url": self.llm_base_url,
            "schema_override": self.schema_override,
            "tools_override": self.tools_override,
            "action_params_override": self.action_params_override
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReplayOverrides":
        """Create from dictionary."""
        return cls(
            llm_model=data.get("llm_model"),
            llm_temperature=data.get("llm_temperature"),
            llm_max_tokens=data.get("llm_max_tokens"),
            llm_base_url=data.get("llm_base_url"),
            schema_override=data.get("schema_override"),
            tools_override=data.get("tools_override"),
            action_params_override=data.get("action_params_override")
        )

    def apply_to_params(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply action-specific parameter overrides.

        Args:
            action_name: Name of the action
            params: Original parameters

        Returns:
            Parameters with overrides applied
        """
        if not self.action_params_override:
            return params

        action_overrides = self.action_params_override.get(action_name)
        if not action_overrides:
            return params

        # Create a copy and apply overrides
        result = params.copy()
        result.update(action_overrides)
        return result


@dataclass
class ReplayConfig:
    """
    Configuration for a replay execution.

    Contains all information needed to replay a session:
    - Original session data
    - Override configuration
    - Execution flags

    Note: original_session and original_attempts can be either dataclass objects
    or dictionaries (from export_session).

    Attributes:
        original_session_id: ID of the original session
        original_session: The original DebugSession (as dict or object)
        original_attempts: List of original AttemptLogs (as dicts or objects)
        overrides: Parameter overrides to apply
        dry_run: If True, plan without executing
        save_replay: If True, save replay results to database
    """

    original_session_id: str
    original_session: Any  # Dict or DebugSession
    original_attempts: List[Any]  # List of Dict or AttemptLog
    overrides: ReplayOverrides = field(default_factory=ReplayOverrides)
    dry_run: bool = False
    save_replay: bool = True

    def _get_session_attr(self, attr: str, default: Any = None) -> Any:
        """Get attribute from session (handles both dict and object)."""
        if isinstance(self.original_session, dict):
            return self.original_session.get(attr, default)
        return getattr(self.original_session, attr, default)

    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration with overrides applied."""
        config = {}

        if self.overrides.llm_model:
            config["model"] = self.overrides.llm_model
        else:
            llm_model = self._get_session_attr("llm_model")
            if llm_model:
                config["model"] = llm_model

        if self.overrides.llm_temperature is not None:
            config["temperature"] = self.overrides.llm_temperature

        if self.overrides.llm_max_tokens is not None:
            config["max_tokens"] = self.overrides.llm_max_tokens

        if self.overrides.llm_base_url:
            config["base_url"] = self.overrides.llm_base_url

        return config

    def get_retrieved_schema(self) -> Optional[Dict[str, Any]]:
        """Get schema with override applied."""
        if self.overrides.schema_override is not None:
            return self.overrides.schema_override

        schema = self._get_session_attr("retrieved_schema")
        if schema:
            if isinstance(schema, str):
                return json.loads(schema)
            return schema

        return None

    def get_retrieved_tools(self) -> Optional[List[Dict[str, Any]]]:
        """Get tools with override applied."""
        if self.overrides.tools_override is not None:
            return self.overrides.tools_override

        tools = self._get_session_attr("retrieved_tools")
        if tools:
            if isinstance(tools, str):
                return json.loads(tools)
            return tools

        return None


@dataclass
class ReplayResult:
    """
    Result of a replay execution.

    Contains the outcome of replaying a session, including
    success/failure status, execution details, and comparison data.

    Attributes:
        replay_id: Unique ID for this replay
        original_session_id: ID of the original session
        success: Whether the replay succeeded
        result: Result data if successful
        attempts: List of attempt records
        execution_time_ms: Execution time in milliseconds
        llm_model: LLM model used
        llm_tokens_used: Tokens consumed
        error: Error if failed
        timestamp: When the replay was executed
        dry_run: Whether this was a dry run
    """

    replay_id: str
    original_session_id: str
    success: bool
    result: Optional[Dict[str, Any]]
    attempts: List["AttemptRecord"]
    execution_time_ms: int
    llm_model: str
    llm_tokens_used: Optional[int]
    error: Optional[str]
    timestamp: datetime
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        # Handle attempts - can be dicts or AttemptRecord objects
        attempts_data = []
        for attempt in self.attempts:
            if isinstance(attempt, dict):
                attempts_data.append(attempt)
            elif hasattr(attempt, "to_dict"):
                attempts_data.append(attempt.to_dict())
            else:
                # Convert to basic dict
                attempts_data.append({
                    "attempt_number": getattr(attempt, "attempt_number", 0),
                    "params": getattr(attempt, "params", {}),
                    "success": getattr(attempt, "success", False),
                    "result": getattr(attempt, "result", None),
                    "error": getattr(attempt, "error", None)
                })

        return {
            "replay_id": self.replay_id,
            "original_session_id": self.original_session_id,
            "success": self.success,
            "result": self.result,
            "attempts": attempts_data,
            "execution_time_ms": self.execution_time_ms,
            "llm_model": self.llm_model,
            "llm_tokens_used": self.llm_tokens_used,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "dry_run": self.dry_run
        }


@dataclass
class SessionDiff:
    """Comparison between original and replay sessions."""

    status_changed: bool
    original_status: str
    replay_status: str
    result_changed: bool
    original_result: Optional[Dict[str, Any]]
    replay_result: Optional[Dict[str, Any]]
    field_diffs: Dict[str, Tuple[Any, Any]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status_changed": self.status_changed,
            "original_status": self.original_status,
            "replay_status": self.replay_status,
            "result_changed": self.result_changed,
            "original_result": self.original_result,
            "replay_result": self.replay_result,
            "field_diffs": {
                k: {"original": v[0], "replay": v[1]}
                for k, v in self.field_diffs.items()
            }
        }


@dataclass
class AttemptDiff:
    """Comparison between original and replay attempts."""

    attempt_number: int
    success_changed: bool
    original_success: bool
    replay_success: bool
    params_changed: bool
    original_params: Dict[str, Any]
    replay_params: Dict[str, Any]
    error_changed: bool
    original_error: Optional[str]
    replay_error: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "attempt_number": self.attempt_number,
            "success_changed": self.success_changed,
            "original_success": self.original_success,
            "replay_success": self.replay_success,
            "params_changed": self.params_changed,
            "original_params": self.original_params,
            "replay_params": self.replay_params,
            "error_changed": self.error_changed,
            "original_error": self.original_error,
            "replay_error": self.replay_error
        }


@dataclass
class PerformanceDiff:
    """Performance comparison between original and replay."""

    execution_time_diff_ms: Optional[int]
    execution_time_change_pct: Optional[float]
    tokens_diff: Optional[int]
    tokens_change_pct: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "execution_time_diff_ms": self.execution_time_diff_ms,
            "execution_time_change_pct": self.execution_time_change_pct,
            "tokens_diff": self.tokens_diff,
            "tokens_change_pct": self.tokens_change_pct
        }


@dataclass
class ReplayDiff:
    """
    Complete comparison between original and replay.

    Provides comprehensive diff analysis including:
    - Session-level differences
    - Attempt-level differences
    - Performance metrics
    - Human-readable summary
    """

    session_comparison: SessionDiff
    attempt_comparison: List[AttemptDiff]
    performance_diff: PerformanceDiff
    summary: str
    replay_metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_comparison": self.session_comparison.to_dict(),
            "attempt_comparison": [a.to_dict() for a in self.attempt_comparison],
            "performance_diff": self.performance_diff.to_dict(),
            "summary": self.summary,
            "replay_metadata": self.replay_metadata
        }


# ==================== Replay Engine ====================

class ReplayEngine:
    """
    Replay engine for re-executing AI sessions.

    Enables debugging and analysis by re-running past sessions with
    different parameters (e.g., different LLM model, temperature).

    Features:
    - Load session from DebugLogger
    - Apply parameter overrides
    - Re-execute with ReflexionLoop
    - Compare results with original
    - Store replay data separately

    Example:
        ```python
        engine = ReplayEngine(debug_logger, action_registry, llm_client)

        # Replay with different model
        overrides = ReplayOverrides(llm_model="gpt-4")
        result = engine.replay_session("session-123", overrides)

        # Compare results
        diff = engine.compare_sessions("session-123", result)
        print(diff.summary)
        ```
    """

    # Default database path for replay storage
    DEFAULT_DB_PATH = "data/debug_logs.db"

    def __init__(
        self,
        debug_logger: "DebugLogger",
        action_registry: "ActionRegistry",
        llm_client: Optional["LLMClient"] = None,
        reflexion_loop: Optional["ReflexionLoop"] = None,
        db_path: Optional[str] = None
    ):
        """
        Initialize ReplayEngine.

        Args:
            debug_logger: DebugLogger instance for loading/saving sessions
            action_registry: ActionRegistry for dispatching actions
            llm_client: Optional LLM client (creates default if None)
            reflexion_loop: Optional ReflexionLoop for retry logic
            db_path: Path to database (defaults to debug_logger's path)
        """
        self.debug_logger = debug_logger
        self.action_registry = action_registry
        self.llm_client = llm_client
        self.reflexion_loop = reflexion_loop

        # Use debug_logger's database path
        self.db_path = db_path or getattr(debug_logger, "db_path", self.DEFAULT_DB_PATH)

        # Initialize replay table
        self._init_replay_table()

    def _init_replay_table(self) -> None:
        """Initialize replay_records table in database."""
        if self.db_path == ":memory:":
            return  # Skip for in-memory databases

        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS replay_records (
                    id TEXT PRIMARY KEY,
                    original_session_id TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

                    -- Configuration
                    llm_model TEXT,
                    llm_temperature REAL,
                    llm_max_tokens INTEGER,
                    llm_base_url TEXT,
                    overrides TEXT,

                    -- Execution
                    success BOOLEAN NOT NULL,
                    result TEXT,
                    attempts TEXT,
                    execution_time_ms INTEGER,
                    llm_tokens_used INTEGER,

                    -- Error
                    error TEXT,

                    -- Metadata
                    dry_run BOOLEAN DEFAULT 0,
                    FOREIGN KEY (original_session_id) REFERENCES debug_sessions(id) ON DELETE CASCADE
                )
            """)

            # Create indexes
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_replay_original_session
                ON replay_records(original_session_id, timestamp DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_replay_timestamp
                ON replay_records(timestamp DESC)
            """)

            conn.commit()
            logger.debug(f"ReplayEngine: Initialized replay table at {self.db_path}")

        finally:
            conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ==================== Session Loading ====================

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Load complete session data for replay.

        Args:
            session_id: Session ID to load

        Returns:
            Dict with session and attempts, or None if not found
        """
        # Get session export from debug logger
        export = self.debug_logger.export_session(session_id)
        if not export:
            logger.warning(f"ReplayEngine: Session {session_id} not found")
            return None

        logger.debug(f"ReplayEngine: Loaded session {session_id}")
        return export

    # ==================== Replay Preparation ====================

    def prepare_replay(
        self,
        session_id: str,
        overrides: Optional[ReplayOverrides] = None,
        dry_run: bool = False
    ) -> Optional[ReplayConfig]:
        """
        Prepare configuration for replay.

        Args:
            session_id: Session ID to replay
            overrides: Parameter overrides to apply
            dry_run: If True, plan without executing

        Returns:
            ReplayConfig if session found, None otherwise
        """
        export = self.load_session(session_id)
        if not export:
            return None

        # Create ReplayConfig
        config = ReplayConfig(
            original_session_id=session_id,
            original_session=export["session"],  # This is a dict from to_dict()
            original_attempts=export["attempts"],
            overrides=overrides or ReplayOverrides(),
            dry_run=dry_run,
            save_replay=not dry_run
        )

        logger.debug(f"ReplayEngine: Prepared replay for session {session_id} (dry_run={dry_run})")
        return config

    # ==================== Replay Execution ====================

    def replay_session(
        self,
        session_id: str,
        overrides: Optional[ReplayOverrides] = None,
        dry_run: bool = False
    ) -> Optional[ReplayResult]:
        """
        Replay a session with optional overrides.

        This is a convenience method that combines load_session,
        prepare_replay, and execute_replay.

        Args:
            session_id: Session ID to replay
            overrides: Parameter overrides to apply
            dry_run: If True, plan without executing

        Returns:
            ReplayResult if session found, None otherwise
        """
        config = self.prepare_replay(session_id, overrides, dry_run)
        if not config:
            return None

        return self.execute_replay(config)

    def execute_replay(self, config: ReplayConfig) -> ReplayResult:
        """
        Execute a replay with the given configuration.

        Replays the session using ReflexionLoop for execution.
        Supports dry-run mode and parameter overrides.

        Args:
            config: ReplayConfig from prepare_replay()

        Returns:
            ReplayResult with execution details
        """
        replay_id = str(uuid.uuid4())
        start_time = datetime.now()
        original_session_dict = config.original_session

        logger.info(f"ReplayEngine: Executing replay {replay_id} for session {config.original_session_id}")

        if config.dry_run:
            logger.info(f"ReplayEngine: Dry run mode - skipping execution")
            # Return dry-run result
            return ReplayResult(
                replay_id=replay_id,
                original_session_id=config.original_session_id,
                success=True,
                result={"dry_run": True, "message": "Dry run - no execution performed"},
                attempts=[],
                execution_time_ms=0,
                llm_model=config.get_llm_config().get("model", "unknown"),
                llm_tokens_used=None,
                error=None,
                timestamp=start_time,
                dry_run=True
            )

        # Determine which action to replay
        # Use the first attempt from original session
        if not config.original_attempts:
            logger.error(f"ReplayEngine: No attempts found in original session")
            result = ReplayResult(
                replay_id=replay_id,
                original_session_id=config.original_session_id,
                success=False,
                result=None,
                attempts=[],
                execution_time_ms=0,
                llm_model=config.get_llm_config().get("model", "unknown"),
                llm_tokens_used=None,
                error="No attempts found in original session",
                timestamp=start_time,
                dry_run=config.dry_run
            )
            if config.save_replay:
                self._save_replay(result, config)
            return result

        # Get first attempt's action and params
        first_attempt = config.original_attempts[0]

        # Handle both dict and object format for attempts
        if isinstance(first_attempt, dict):
            action_name = first_attempt.get("action_name")
            params_value = first_attempt.get("params")
        else:
            action_name = first_attempt.action_name
            params_value = first_attempt.params

        # Parse params if it's a JSON string
        if isinstance(params_value, str):
            original_params = json.loads(params_value)
        else:
            original_params = params_value or {}

        # Apply parameter overrides
        params = config.overrides.apply_to_params(action_name, original_params)

        # Create execution context
        # Note: In a real system, you'd need db session and user from original session
        # For now, we'll use minimal context
        context = {
            # "db": db_session,  # Would need to be passed in
            # "user": user,      # Would need to be passed in
        }

        # Execute using ReflexionLoop if available
        if self.reflexion_loop:
            try:
                loop_result = self.reflexion_loop.execute_with_reflexion(
                    action_name=action_name,
                    params=params,
                    context=context
                )

                execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                result = ReplayResult(
                    replay_id=replay_id,
                    original_session_id=config.original_session_id,
                    success=True,
                    result=loop_result.get("result"),
                    attempts=loop_result.get("attempts", []),
                    execution_time_ms=execution_time_ms,
                    llm_model=config.get_llm_config().get("model", "unknown"),
                    llm_tokens_used=None,  # Would need to extract from ReflexionLoop
                    error=None,
                    timestamp=start_time,
                    dry_run=config.dry_run
                )

            except Exception as e:
                execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                error_msg = str(e)

                result = ReplayResult(
                    replay_id=replay_id,
                    original_session_id=config.original_session_id,
                    success=False,
                    result=None,
                    attempts=[],
                    execution_time_ms=execution_time_ms,
                    llm_model=config.get_llm_config().get("model", "unknown"),
                    llm_tokens_used=None,
                    error=error_msg,
                    timestamp=start_time,
                    dry_run=config.dry_run
                )

        else:
            # No ReflexionLoop - try direct dispatch
            try:
                dispatch_result = self.action_registry.dispatch(
                    action_name=action_name,
                    params=params,
                    context=context
                )

                execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

                # Create mock attempt record for consistency
                from core.ai.reflexion import AttemptRecord
                attempt = AttemptRecord(
                    attempt_number=1,
                    params=params,
                    success=True,
                    result=dispatch_result
                )

                result = ReplayResult(
                    replay_id=replay_id,
                    original_session_id=config.original_session_id,
                    success=True,
                    result=dispatch_result,
                    attempts=[attempt.to_dict()],
                    execution_time_ms=execution_time_ms,
                    llm_model=config.get_llm_config().get("model", "unknown"),
                    llm_tokens_used=None,
                    error=None,
                    timestamp=start_time,
                    dry_run=config.dry_run
                )

            except Exception as e:
                execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                error_msg = str(e)

                result = ReplayResult(
                    replay_id=replay_id,
                    original_session_id=config.original_session_id,
                    success=False,
                    result=None,
                    attempts=[],
                    execution_time_ms=execution_time_ms,
                    llm_model=config.get_llm_config().get("model", "unknown"),
                    llm_tokens_used=None,
                    error=error_msg,
                    timestamp=start_time,
                    dry_run=config.dry_run
                )

        # Save replay if requested
        if config.save_replay:
            self._save_replay(result, config)

        logger.info(f"ReplayEngine: Replay {replay_id} completed (success={result.success})")
        return result

    def _save_replay(self, result: ReplayResult, config: ReplayConfig) -> None:
        """Save replay result to database."""
        if self.db_path == ":memory:":
            return

        conn = self._get_conn()
        try:
            conn.execute("""
                INSERT INTO replay_records
                (id, original_session_id, timestamp, llm_model, llm_temperature, llm_max_tokens,
                 llm_base_url, overrides, success, result, attempts, execution_time_ms,
                 llm_tokens_used, error, dry_run)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.replay_id,
                result.original_session_id,
                result.timestamp.isoformat(),
                result.llm_model,
                config.overrides.llm_temperature,
                config.overrides.llm_max_tokens,
                config.overrides.llm_base_url,
                json.dumps(config.overrides.to_dict()),
                result.success,
                json.dumps(result.result) if result.result else None,
                json.dumps(result.attempts) if result.attempts else None,
                result.execution_time_ms,
                result.llm_tokens_used,
                result.error,
                config.dry_run
            ))
            conn.commit()
            logger.debug(f"ReplayEngine: Saved replay {result.replay_id}")

        except Exception as e:
            logger.error(f"ReplayEngine: Failed to save replay: {e}")
        finally:
            conn.close()

    # ==================== Comparison ====================

    def compare_sessions(
        self,
        original_session_id: str,
        replay_result: ReplayResult
    ) -> Optional[ReplayDiff]:
        """
        Generate comparison between original and replay.

        Args:
            original_session_id: Original session ID
            replay_result: Result from execute_replay()

        Returns:
            ReplayDiff with comprehensive comparison
        """
        # Load original session
        export = self.load_session(original_session_id)
        if not export:
            logger.warning(f"ReplayEngine: Cannot compare - original session {original_session_id} not found")
            return None

        original_session = export["session"]
        original_attempts = export["attempts"]

        # Session comparison
        session_diff = SessionDiff(
            status_changed=original_session["status"] != ("success" if replay_result.success else "error"),
            original_status=original_session["status"],
            replay_status="success" if replay_result.success else "error",
            result_changed=self._results_differ(original_session.get("final_result"), replay_result.result),
            original_result=original_session.get("final_result"),
            replay_result=replay_result.result,
            field_diffs={}
        )

        # Attempt comparison
        attempt_diffs = []
        max_attempts = max(len(original_attempts), len(replay_result.attempts))

        for i in range(max_attempts):
            original = original_attempts[i] if i < len(original_attempts) else None
            replay = replay_result.attempts[i] if i < len(replay_result.attempts) else None

            diff = self._compare_attempts(i + 1, original, replay)
            if diff:
                attempt_diffs.append(diff)

        # Performance comparison
        performance_diff = self._compare_performance(
            original_session.get("execution_time_ms"),
            original_session.get("llm_tokens_used"),
            replay_result.execution_time_ms,
            replay_result.llm_tokens_used
        )

        # Generate summary
        summary = self._generate_summary(session_diff, attempt_diffs, performance_diff)

        # Replay metadata
        replay_metadata = {
            "replay_id": replay_result.replay_id,
            "llm_model": replay_result.llm_model,
            "dry_run": replay_result.dry_run
        }

        return ReplayDiff(
            session_comparison=session_diff,
            attempt_comparison=attempt_diffs,
            performance_diff=performance_diff,
            summary=summary,
            replay_metadata=replay_metadata
        )

    def _results_differ(
        self,
        original: Optional[Any],
        replay: Optional[Any]
    ) -> bool:
        """Check if results differ."""
        if original is None and replay is None:
            return False
        if original is None or replay is None:
            return True

        # Convert to comparable format
        if isinstance(original, str):
            try:
                original = json.loads(original)
            except json.JSONDecodeError:
                pass

        return original != replay

    def _compare_attempts(
        self,
        attempt_number: int,
        original: Optional[Dict[str, Any]],
        replay: Optional[Dict[str, Any]]
    ) -> Optional[AttemptDiff]:
        """Compare a single attempt."""
        if not original and not replay:
            return None

        # Extract original attempt data
        orig_success = original.get("success") if original else None
        orig_params = original.get("params") if original else None
        orig_error = original.get("error") if original else None

        # Extract replay attempt data
        replay_success = replay.get("success") if replay else None
        replay_params = replay.get("params") if replay else None
        replay_error = replay.get("error") if replay else None

        # Convert errors to string for comparison
        orig_error_str = json.dumps(orig_error) if orig_error else None
        replay_error_str = json.dumps(replay_error) if isinstance(replay_error, dict) else str(replay_error) if replay_error else None

        return AttemptDiff(
            attempt_number=attempt_number,
            success_changed=orig_success != replay_success,
            original_success=orig_success or False,
            replay_success=replay_success or False,
            params_changed=orig_params != replay_params,
            original_params=orig_params or {},
            replay_params=replay_params or {},
            error_changed=orig_error_str != replay_error_str,
            original_error=orig_error_str,
            replay_error=replay_error_str
        )

    def _compare_performance(
        self,
        orig_time_ms: Optional[int],
        orig_tokens: Optional[int],
        replay_time_ms: Optional[int],
        replay_tokens: Optional[int]
    ) -> PerformanceDiff:
        """Compare performance metrics."""
        time_diff = None
        time_pct = None
        if orig_time_ms is not None and replay_time_ms is not None:
            time_diff = replay_time_ms - orig_time_ms
            if orig_time_ms > 0:
                time_pct = (time_diff / orig_time_ms) * 100

        tokens_diff = None
        tokens_pct = None
        if orig_tokens is not None and replay_tokens is not None:
            tokens_diff = replay_tokens - orig_tokens
            if orig_tokens > 0:
                tokens_pct = (tokens_diff / orig_tokens) * 100

        return PerformanceDiff(
            execution_time_diff_ms=time_diff,
            execution_time_change_pct=time_pct,
            tokens_diff=tokens_diff,
            tokens_change_pct=tokens_pct
        )

    def _generate_summary(
        self,
        session_diff: SessionDiff,
        attempt_diffs: List[AttemptDiff],
        performance_diff: PerformanceDiff
    ) -> str:
        """Generate human-readable summary."""
        lines = ["## Replay Comparison Summary"]

        # Status
        if session_diff.status_changed:
            lines.append(f"- Status changed: {session_diff.original_status} -> {session_diff.replay_status}")
        else:
            lines.append(f"- Status: {session_diff.original_status} (no change)")

        # Attempts
        success_changed = [a for a in attempt_diffs if a.success_changed]
        if success_changed:
            lines.append(f"- {len(success_changed)} attempts changed success status")

        # Performance
        if performance_diff.execution_time_diff_ms is not None:
            change = performance_diff.execution_time_diff_ms
            pct = performance_diff.execution_time_change_pct
            if change > 0:
                lines.append(f"- Execution time: +{change}ms (+{pct:.1f}%)")
            elif change < 0:
                lines.append(f"- Execution time: {change}ms ({pct:.1f}%)")

        return "\n".join(lines)

    # ==================== Query Methods ====================

    def list_replays(
        self,
        original_session_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List replays, optionally filtered by original session.

        Args:
            original_session_id: Filter by original session ID
            limit: Maximum number of replays to return

        Returns:
            List of replay dictionaries
        """
        if self.db_path == ":memory:":
            return []

        conn = self._get_conn()
        try:
            query = "SELECT * FROM replay_records"
            params: List = []

            if original_session_id:
                query += " WHERE original_session_id = ?"
                params.append(original_session_id)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            return [self._replay_row_to_dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_replay(self, replay_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details of a specific replay.

        Args:
            replay_id: Replay ID

        Returns:
            Replay dictionary or None if not found
        """
        if self.db_path == ":memory:":
            return None

        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT * FROM replay_records WHERE id = ?
            """, (replay_id,))
            row = cursor.fetchone()
            return self._replay_row_to_dict(row) if row else None

        finally:
            conn.close()

    def _replay_row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to dictionary."""
        return {
            "replay_id": row["id"],
            "original_session_id": row["original_session_id"],
            "timestamp": row["timestamp"],
            "llm_model": row["llm_model"],
            "llm_temperature": row["llm_temperature"],
            "llm_max_tokens": row["llm_max_tokens"],
            "llm_base_url": row["llm_base_url"],
            "overrides": json.loads(row["overrides"]) if row["overrides"] else None,
            "success": bool(row["success"]),
            "result": json.loads(row["result"]) if row["result"] else None,
            "attempts": json.loads(row["attempts"]) if row["attempts"] else None,
            "execution_time_ms": row["execution_time_ms"],
            "llm_tokens_used": row["llm_tokens_used"],
            "error": row["error"],
            "dry_run": bool(row["dry_run"])
        }


__all__ = [
    "ReplayEngine",
    "ReplayOverrides",
    "ReplayConfig",
    "ReplayResult",
    "ReplayDiff",
    "SessionDiff",
    "AttemptDiff",
    "PerformanceDiff",
]
