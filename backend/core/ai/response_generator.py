"""
core/ai/response_generator.py

SPEC-18: ResponseGenerator - Zero-LLM response formatting

Converts OntologyResult into human-readable Chinese text using pure template
formatting. No LLM calls are made; all output is deterministic.

Result types:
  - query_result: Table/list of query results
  - action_confirmed: Successful action completion
  - action_needs_confirm: Action awaiting user confirmation
  - missing_fields: Missing required parameters
  - constraint_violation: Business rule violation
  - state_violation: State machine transition error
  - error: Generic error
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


# Valid result types
VALID_RESULT_TYPES = frozenset({
    "query_result",
    "action_confirmed",
    "action_needs_confirm",
    "missing_fields",
    "constraint_violation",
    "state_violation",
    "error",
})


@dataclass
class OntologyResult:
    """
    Structured result from ontology operations.

    Attributes:
        result_type: One of VALID_RESULT_TYPES
        data: Result payload (structure varies by result_type)
        entity_type: Optional entity name (e.g. "Guest", "Room")
        action_name: Optional action that produced this result
        message: Optional human-readable override message
    """
    result_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    entity_type: Optional[str] = None
    action_name: Optional[str] = None
    message: Optional[str] = None


class ResponseGenerator:
    """
    Zero-LLM response formatter.

    Converts OntologyResult into formatted Chinese text using
    deterministic template methods. No external API calls.

    Usage:
        >>> gen = ResponseGenerator()
        >>> result = OntologyResult(
        ...     result_type="query_result",
        ...     data={"results": [{"name": "Alice"}], "entity": "Guest", "total": 1}
        ... )
        >>> print(gen.generate(result))
        找到 1 条Guest记录：
        name: Alice
    """

    def __init__(self, language: str = "zh"):
        self.language = language

        # Dispatch table mapping result_type -> formatter method
        self._formatters = {
            "query_result": self._format_query_result,
            "action_confirmed": self._format_action_confirmed,
            "action_needs_confirm": self._format_action_needs_confirm,
            "missing_fields": self._format_missing_fields,
            "constraint_violation": self._format_constraint_violation,
            "state_violation": self._format_state_violation,
            "error": self._format_error,
        }

    def generate(self, result: OntologyResult) -> str:
        """
        Main entry point. Dispatches to the appropriate template method
        based on result.result_type.

        If result.message is set and result_type is recognized, the message
        is used as a prefix or override depending on the type.

        Unknown result_type falls back to error formatting.
        """
        formatter = self._formatters.get(result.result_type)
        if formatter is None:
            # Unknown result_type: treat as error with descriptive message
            return self._format_error({
                "message": f"未知结果类型: {result.result_type}",
                "raw_data": result.data,
            })
        return formatter(result.data)

    # ------------------------------------------------------------------
    # Template methods
    # ------------------------------------------------------------------

    def _format_query_result(self, data: Dict[str, Any]) -> str:
        """
        Format query results as a readable list.

        Expected data keys:
            - results: List[Dict] - rows of data
            - entity: str - entity type name
            - total: int - total count
        """
        results = data.get("results", [])
        entity = data.get("entity", "")
        total = data.get("total", len(results))

        if not results:
            return f"未找到{entity}记录"

        header = f"找到 {total} 条{entity}记录：\n"
        rows = []
        for i, row in enumerate(results, 1):
            parts = [f"{k}: {v}" for k, v in row.items()]
            rows.append(f"{i}. " + ", ".join(parts))

        return header + "\n".join(rows)

    def _format_action_confirmed(self, data: Dict[str, Any]) -> str:
        """
        Format a successful action confirmation.

        Expected data keys:
            - message: str - success message
            - entity_type: str (optional)
        """
        message = data.get("message", "操作完成")
        return f"\u2705 {message}"

    def _format_action_needs_confirm(self, data: Dict[str, Any]) -> str:
        """
        Format an action that needs user confirmation before execution.

        Expected data keys:
            - action_name: str - action identifier
            - params: dict - action parameters
            - description: str - human-readable description
        """
        description = data.get("description", "")
        params = data.get("params", {})

        params_str = ", ".join(f"{k}={v}" for k, v in params.items())

        lines = [
            "请确认以下操作：",
            description,
            f"参数：{params_str}",
        ]
        return "\n".join(lines)

    def _format_missing_fields(self, data: Dict[str, Any]) -> str:
        """
        Format a prompt for missing required fields.

        Expected data keys:
            - missing: List[str] - field names that are missing
            - action_name: str - the action that needs them
        """
        action_name = data.get("action_name", "该操作")
        missing = data.get("missing", [])

        header = f"执行 {action_name} 还需要以下信息："
        items = [f"- {field_name}" for field_name in missing]

        return header + "\n" + "\n".join(items)

    def _format_constraint_violation(self, data: Dict[str, Any]) -> str:
        """
        Format a business constraint violation.

        Expected data keys:
            - constraint: str - constraint identifier
            - message: str - human-readable explanation
        """
        message = data.get("message", "未知约束违反")
        return f"\u26a0\ufe0f 操作违反业务规则：{message}"

    def _format_state_violation(self, data: Dict[str, Any]) -> str:
        """
        Format a state machine transition error.

        Expected data keys:
            - current_state: str - current state
            - target_state: str - attempted target state
            - valid_alternatives: List[str] - valid transitions from current
        """
        current = data.get("current_state", "?")
        target = data.get("target_state", "?")
        alternatives = data.get("valid_alternatives", [])

        alt_str = ", ".join(alternatives) if alternatives else "无"
        return f"\u26a0\ufe0f 状态转换无效：{current} \u2192 {target}。可选操作：{alt_str}"

    def _format_error(self, data: Dict[str, Any]) -> str:
        """
        Format a generic error.

        Expected data keys:
            - message: str - error description
        """
        message = data.get("message", "未知错误")
        return f"\u274c {message}"

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def format_query_table(
        self,
        results: List[Dict],
        fields: Optional[List[str]] = None,
    ) -> str:
        """
        Format query results as an aligned text table.

        If fields is None, columns are inferred from the first row.
        Column widths are auto-calculated to accommodate the widest value,
        accounting for Chinese character display width (2 columns per CJK char).

        Args:
            results: List of row dicts
            fields: Optional column keys to include (and their order)

        Returns:
            Formatted table string with header, separator, and data rows
        """
        if not results:
            return "（无数据）"

        # Determine columns
        if fields is None:
            fields = list(results[0].keys())

        # Chinese header mapping (extend as needed)
        header_map = {
            "name": "姓名",
            "phone": "电话",
            "room_number": "房间号",
            "room_type": "房型",
            "status": "状态",
            "check_in_date": "入住日期",
            "check_out_date": "退房日期",
            "guest_name": "客人姓名",
            "id": "ID",
            "price": "价格",
            "total": "合计",
            "email": "邮箱",
            "id_number": "证件号",
            "floor": "楼层",
            "description": "描述",
            "created_at": "创建时间",
            "updated_at": "更新时间",
        }

        headers = [header_map.get(f, f) for f in fields]

        # Convert all values to strings
        str_rows = []
        for row in results:
            str_rows.append([str(row.get(f, "")) for f in fields])

        # Calculate column widths accounting for CJK display width
        def display_width(s: str) -> int:
            """Calculate display width: CJK chars count as 2, others as 1."""
            width = 0
            for ch in s:
                if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
                    width += 2
                else:
                    width += 1
            return width

        def pad_to_width(s: str, target_width: int) -> str:
            """Pad string with spaces to reach target display width."""
            current = display_width(s)
            return s + " " * (target_width - current)

        col_widths = []
        for i, header in enumerate(headers):
            max_w = display_width(header)
            for row in str_rows:
                w = display_width(row[i])
                if w > max_w:
                    max_w = w
            col_widths.append(max_w)

        # Build header line
        header_cells = [pad_to_width(h, col_widths[i]) for i, h in enumerate(headers)]
        header_line = " | ".join(header_cells)

        # Build separator
        sep_parts = ["-" * w for w in col_widths]
        separator = "-+-".join(sep_parts)

        # Build data rows
        data_lines = []
        for row in str_rows:
            cells = [pad_to_width(row[i], col_widths[i]) for i, _ in enumerate(fields)]
            data_lines.append(" | ".join(cells))

        return "\n".join([header_line, separator, *data_lines])
