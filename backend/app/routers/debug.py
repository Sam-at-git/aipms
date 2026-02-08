"""
app/routers/debug.py

Debug API - Frontend debug panel endpoints.

Provides access to DebugLogger and ReplayEngine functionality for the
frontend debug panel. Requires sysadmin role.

Endpoints:
- GET  /debug/sessions       - List debug sessions
- GET  /debug/sessions/{id}  - Get session details
- GET  /debug/statistics     - Get debug statistics
- POST /debug/replay         - Replay a session
- GET  /debug/replay/{id}    - Get replay results
- GET  /debug/replays        - List replays
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.security.auth import get_current_user, require_sysadmin
from app.models.ontology import Employee
from core.ai.debug_logger import DebugLogger
from core.ai.replay import (
    ReplayEngine,
    ReplayOverrides,
    ReplayConfig,
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/debug", tags=["debug"])

# Singleton instances
_debug_logger: Optional[DebugLogger] = None
_replay_engine: Optional[ReplayEngine] = None


def get_debug_logger() -> DebugLogger:
    """Get or create DebugLogger singleton."""
    global _debug_logger
    if _debug_logger is None:
        _debug_logger = DebugLogger()
    return _debug_logger


def get_replay_engine() -> Optional[ReplayEngine]:
    """Get or create ReplayEngine singleton. Returns None if dependencies unavailable."""
    global _replay_engine
    if _replay_engine is None:
        try:
            # Import here to avoid circular dependency
            from core.ai.actions import get_action_registry
            from core.ai.llm_client import get_default_llm_client
            from core.ai.reflexion import get_reflexion_loop

            debug_logger = get_debug_logger()
            action_registry = get_action_registry()
            llm_client = get_default_llm_client()
            reflexion_loop = get_reflexion_loop()

            _replay_engine = ReplayEngine(
                debug_logger=debug_logger,
                action_registry=action_registry,
                llm_client=llm_client,
                reflexion_loop=reflexion_loop,
            )
        except Exception as e:
            logger.warning(f"ReplayEngine not available: {e}")
            _replay_engine = None
    return _replay_engine


# ==================== Session Endpoints ====================

@router.get("/sessions")
def list_sessions(
    status: Optional[str] = Query(None, description="Filter by status (success, error, partial, pending)"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    limit: int = Query(20, ge=1, le=100, description="Max sessions to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: Employee = Depends(require_sysadmin),
) -> Dict[str, Any]:
    """
    List debug sessions with optional filters.

    Requires sysadmin role.
    """
    debug_logger = get_debug_logger()

    sessions = debug_logger.list_sessions(
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    # Get total count
    total_sessions = debug_logger.get_statistics().get("total_sessions", 0)

    # Format sessions for API response
    formatted_sessions = []
    for session in sessions:
        # Get attempt count
        attempts = debug_logger.get_attempts(session.session_id)
        attempt_count = len(attempts)

        formatted_sessions.append({
            "session_id": session.session_id,
            "timestamp": session.timestamp.isoformat(),
            "user_id": session.user_id,
            "user_role": session.user_role,
            "input_message": session.input_message,
            "status": session.status,
            "llm_model": session.llm_model,
            "execution_time_ms": session.execution_time_ms,
            "attempt_count": attempt_count,
        })

    return {
        "sessions": formatted_sessions,
        "total": total_sessions,
        "limit": limit,
        "offset": offset,
    }


@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: str,
    current_user: Employee = Depends(require_sysadmin),
) -> Dict[str, Any]:
    """
    Get session detail with all attempts.

    Requires sysadmin role.
    """
    debug_logger = get_debug_logger()

    session = debug_logger.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    attempts = debug_logger.get_attempts(session_id)

    # Format session
    formatted_session = session.to_dict()

    # Format attempts
    formatted_attempts = [attempt.to_dict() for attempt in attempts]

    return {
        "session": formatted_session,
        "attempts": formatted_attempts,
    }


@router.get("/statistics")
def get_statistics(
    current_user: Employee = Depends(require_sysadmin),
) -> Dict[str, Any]:
    """
    Get debug logger statistics.

    Requires sysadmin role.
    """
    debug_logger = get_debug_logger()
    return debug_logger.get_statistics()


# ==================== Replay Endpoints ====================

@router.post("/replay")
def replay_session(
    request: Dict[str, Any],
    current_user: Employee = Depends(require_sysadmin),
) -> Dict[str, Any]:
    """
    Replay a session with optional parameter overrides.

    Request body:
    {
        "session_id": "uuid",
        "overrides": {
            "llm_model": "gpt-4",
            "llm_temperature": 0.3,
            "action_params_override": {...}
        },
        "dry_run": false
    }

    Requires sysadmin role.
    """
    session_id = request.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    overrides_data = request.get("overrides")
    dry_run = request.get("dry_run", False)

    replay_engine = get_replay_engine()
    if replay_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Replay functionality not available. Required dependencies (ActionRegistry, LLMClient, ReflexionLoop) are not configured."
        )

    # Create overrides
    overrides = ReplayOverrides(
        llm_model=overrides_data.get("llm_model") if overrides_data else None,
        llm_temperature=overrides_data.get("llm_temperature") if overrides_data else None,
        llm_max_tokens=overrides_data.get("llm_max_tokens") if overrides_data else None,
        llm_base_url=overrides_data.get("llm_base_url") if overrides_data else None,
        action_params_override=overrides_data.get("action_params_override") if overrides_data else None,
    )

    # Execute replay
    result = replay_engine.replay_session(
        session_id=session_id,
        overrides=overrides,
        dry_run=dry_run,
    )

    if not result:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return result.to_dict()


@router.get("/replay/{replay_id}")
def get_replay_result(
    replay_id: str,
    current_user: Employee = Depends(require_sysadmin),
) -> Dict[str, Any]:
    """
    Get replay result with comparison to original session.

    Requires sysadmin role.
    """
    replay_engine = get_replay_engine()
    if replay_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Replay functionality not available. Required dependencies (ActionRegistry, LLMClient, ReflexionLoop) are not configured."
        )

    replay = replay_engine.get_replay(replay_id)
    if not replay:
        raise HTTPException(status_code=404, detail=f"Replay {replay_id} not found")

    # Load original session
    original_session_id = replay["original_session_id"]
    export = replay_engine.load_session(original_session_id)
    if not export:
        raise HTTPException(status_code=404, detail=f"Original session {original_session_id} not found")

    # Generate comparison
    from core.ai.replay import ReplayResult

    replay_result = ReplayResult(
        replay_id=replay["replay_id"],
        original_session_id=replay["original_session_id"],
        success=replay["success"],
        result=replay["result"],
        attempts=replay["attempts"] or [],
        execution_time_ms=replay["execution_time_ms"],
        llm_model=replay["llm_model"],
        llm_tokens_used=replay["llm_tokens_used"],
        error=replay["error"],
        timestamp=datetime.fromisoformat(replay["timestamp"]),
        dry_run=replay["dry_run"],
    )

    comparison = replay_engine.compare_sessions(original_session_id, replay_result)

    return {
        "replay": replay,
        "original_session": export.get("session"),
        "comparison": comparison.to_dict() if comparison else None,
    }


@router.get("/replays")
def list_replays(
    original_session_id: Optional[str] = Query(None, description="Filter by original session ID"),
    limit: int = Query(20, ge=1, le=100, description="Max replays to return"),
    current_user: Employee = Depends(require_sysadmin),
) -> Dict[str, Any]:
    """
    List replay records.

    Requires sysadmin role.
    """
    replay_engine = get_replay_engine()
    if replay_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Replay functionality not available. Required dependencies (ActionRegistry, LLMClient, ReflexionLoop) are not configured."
        )

    replays = replay_engine.list_replays(
        original_session_id=original_session_id,
        limit=limit,
    )

    return {
        "replays": replays,
        "count": len(replays),
    }


# ==================== Management Endpoints ====================

@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: Employee = Depends(require_sysadmin),
) -> Dict[str, Any]:
    """
    Delete a debug session and all its attempts.

    Requires sysadmin role.
    """
    debug_logger = get_debug_logger()

    deleted = debug_logger.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return {
        "message": f"Session {session_id} deleted",
        "session_id": session_id,
    }


@router.post("/cleanup")
def cleanup_old_sessions(
    days: int = Query(30, ge=1, le=365, description="Days to retain"),
    current_user: Employee = Depends(require_sysadmin),
) -> Dict[str, Any]:
    """
    Delete sessions older than specified days.

    Requires sysadmin role.
    """
    debug_logger = get_debug_logger()

    deleted_count = debug_logger.cleanup_old_sessions(days=days)

    return {
        "message": f"Deleted {deleted_count} sessions older than {days} days",
        "deleted_count": deleted_count,
        "days": days,
    }
