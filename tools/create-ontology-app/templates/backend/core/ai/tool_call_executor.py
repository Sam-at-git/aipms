"""
core/ai/tool_call_executor.py

Text-based tool calling protocol for Phase 3 dynamic action discovery.

Parses <tool_call> tags from LLM output, executes the requested tool,
and formats results as <tool_result> for the next LLM round.

Available tools:
- search_actions(query): Find relevant actions by keyword
- describe_action(name): Get full action schema

IMPORTANT: Core-layer component, zero domain knowledge.
"""
import json
import re
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from core.ai.action_search import ActionSearchEngine
    from core.ai.actions import ActionRegistry

logger = logging.getLogger(__name__)

TOOL_CALL_PATTERN = re.compile(
    r'<tool_call>\s*(.*?)\s*</tool_call>',
    re.DOTALL,
)

MAX_ROUNDS = 3


@dataclass
class ToolCall:
    """Parsed tool call from LLM output."""
    tool: str
    args: Dict[str, Any]


def extract_tool_call(text: str) -> Optional[ToolCall]:
    """Extract a tool call from LLM text output.

    Looks for <tool_call>{"tool": "...", "args": {...}}</tool_call> pattern.

    Returns:
        ToolCall if found and valid, None otherwise.
    """
    match = TOOL_CALL_PATTERN.search(text)
    if not match:
        return None

    try:
        data = json.loads(match.group(1))
    except (json.JSONDecodeError, TypeError):
        logger.debug("ToolCallExecutor: invalid JSON in <tool_call>")
        return None

    tool = data.get("tool", "")
    args = data.get("args", {})
    if not tool:
        return None

    return ToolCall(tool=tool, args=args)


def execute_tool(
    tool_call: ToolCall,
    search_engine: Optional["ActionSearchEngine"] = None,
    action_registry: Optional["ActionRegistry"] = None,
    user_role: str = "",
) -> Dict[str, Any]:
    """Execute a tool call and return the result.

    Args:
        tool_call: Parsed tool call.
        search_engine: ActionSearchEngine for search_actions.
        action_registry: ActionRegistry for describe_action.
        user_role: User role for search filtering.

    Returns:
        Dict with tool result data.
    """
    if tool_call.tool == "search_actions":
        return _execute_search_actions(tool_call.args, search_engine, user_role)
    elif tool_call.tool == "describe_action":
        return _execute_describe_action(tool_call.args, action_registry)
    else:
        return {"error": f"Unknown tool: {tool_call.tool}"}


def format_result(tool_name: str, result: Dict[str, Any]) -> str:
    """Format tool execution result as <tool_result> tag.

    Returns:
        String like: <tool_result>{"tool": "search_actions", "result": {...}}</tool_result>
    """
    payload = {"tool": tool_name, "result": result}
    return f"<tool_result>{json.dumps(payload, ensure_ascii=False)}</tool_result>"


def _execute_search_actions(
    args: Dict[str, Any],
    search_engine: Optional["ActionSearchEngine"],
    user_role: str,
) -> Dict[str, Any]:
    """Execute search_actions tool."""
    if search_engine is None:
        return {"error": "Search engine not available"}

    query = args.get("query", "")
    if not query:
        return {"error": "Missing 'query' argument"}

    top_k = args.get("top_k", 5)
    results = search_engine.search(query, user_role=user_role, top_k=top_k)

    return {
        "actions": [
            {
                "name": r.name,
                "entity": r.entity,
                "description": r.description,
                "score": round(r.score, 2),
            }
            for r in results
        ],
        "total": len(results),
    }


def _execute_describe_action(
    args: Dict[str, Any],
    action_registry: Optional["ActionRegistry"],
) -> Dict[str, Any]:
    """Execute describe_action tool."""
    if action_registry is None:
        return {"error": "Action registry not available"}

    name = args.get("name", "")
    if not name:
        return {"error": "Missing 'name' argument"}

    defn = action_registry.get_action(name)
    if defn is None:
        return {"error": f"Action '{name}' not found"}

    # Build parameter schema from Pydantic model
    try:
        schema = defn.parameters_schema.model_json_schema()
    except Exception:
        schema = {}

    return {
        "name": defn.name,
        "entity": defn.entity,
        "description": defn.description,
        "category": defn.category,
        "parameters": schema,
        "requires_confirmation": defn.requires_confirmation,
    }


__all__ = [
    "ToolCall",
    "extract_tool_call",
    "execute_tool",
    "format_result",
    "MAX_ROUNDS",
]
