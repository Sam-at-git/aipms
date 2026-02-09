"""
Tests for SPEC-18: ResponseGenerator + OntologyResult

Pure template formatting - no LLM, no database needed.
"""
import pytest
from core.ai.response_generator import OntologyResult, ResponseGenerator, VALID_RESULT_TYPES


# ---------------------------------------------------------------------------
# OntologyResult dataclass
# ---------------------------------------------------------------------------

class TestOntologyResult:
    def test_create_minimal(self):
        r = OntologyResult(result_type="query_result")
        assert r.result_type == "query_result"
        assert r.data == {}
        assert r.entity_type is None
        assert r.action_name is None
        assert r.message is None

    def test_create_full(self):
        r = OntologyResult(
            result_type="action_confirmed",
            data={"message": "OK"},
            entity_type="Room",
            action_name="checkin",
            message="override",
        )
        assert r.result_type == "action_confirmed"
        assert r.data == {"message": "OK"}
        assert r.entity_type == "Room"
        assert r.action_name == "checkin"
        assert r.message == "override"

    def test_data_isolation(self):
        """Mutable default dict should not leak between instances."""
        r1 = OntologyResult(result_type="error")
        r2 = OntologyResult(result_type="error")
        r1.data["leak"] = True
        assert "leak" not in r2.data

    def test_valid_result_types_set(self):
        assert "query_result" in VALID_RESULT_TYPES
        assert "action_confirmed" in VALID_RESULT_TYPES
        assert "action_needs_confirm" in VALID_RESULT_TYPES
        assert "missing_fields" in VALID_RESULT_TYPES
        assert "constraint_violation" in VALID_RESULT_TYPES
        assert "state_violation" in VALID_RESULT_TYPES
        assert "error" in VALID_RESULT_TYPES
        assert len(VALID_RESULT_TYPES) == 7


# ---------------------------------------------------------------------------
# ResponseGenerator initialization
# ---------------------------------------------------------------------------

class TestResponseGeneratorInit:
    def test_default_language(self):
        gen = ResponseGenerator()
        assert gen.language == "zh"

    def test_custom_language(self):
        gen = ResponseGenerator(language="en")
        assert gen.language == "en"


# ---------------------------------------------------------------------------
# Query result formatting
# ---------------------------------------------------------------------------

class TestQueryResultFormatting:
    def setup_method(self):
        self.gen = ResponseGenerator()

    def test_empty_results(self):
        result = OntologyResult(
            result_type="query_result",
            data={"results": [], "entity": "Guest", "total": 0},
        )
        output = self.gen.generate(result)
        assert output == "未找到Guest记录"

    def test_single_result(self):
        result = OntologyResult(
            result_type="query_result",
            data={
                "results": [{"name": "Alice", "phone": "13800138000"}],
                "entity": "Guest",
                "total": 1,
            },
        )
        output = self.gen.generate(result)
        assert "找到 1 条Guest记录" in output
        assert "1. name: Alice, phone: 13800138000" in output

    def test_multiple_results(self):
        result = OntologyResult(
            result_type="query_result",
            data={
                "results": [
                    {"room_number": "101", "status": "vacant_clean"},
                    {"room_number": "102", "status": "occupied"},
                    {"room_number": "103", "status": "vacant_dirty"},
                ],
                "entity": "Room",
                "total": 3,
            },
        )
        output = self.gen.generate(result)
        assert "找到 3 条Room记录" in output
        assert "1. room_number: 101" in output
        assert "2. room_number: 102" in output
        assert "3. room_number: 103" in output

    def test_total_defaults_to_results_length(self):
        """When total is not provided, infer from results list length."""
        result = OntologyResult(
            result_type="query_result",
            data={
                "results": [{"id": 1}, {"id": 2}],
                "entity": "Task",
            },
        )
        output = self.gen.generate(result)
        assert "找到 2 条Task记录" in output

    def test_missing_entity(self):
        """When entity is not provided, still works with empty string."""
        result = OntologyResult(
            result_type="query_result",
            data={"results": [], "total": 0},
        )
        output = self.gen.generate(result)
        assert "未找到" in output


# ---------------------------------------------------------------------------
# Action confirmed formatting
# ---------------------------------------------------------------------------

class TestActionConfirmedFormatting:
    def setup_method(self):
        self.gen = ResponseGenerator()

    def test_basic_confirmed(self):
        result = OntologyResult(
            result_type="action_confirmed",
            data={"message": "客人 Alice 已成功入住 201 房间", "entity_type": "StayRecord"},
        )
        output = self.gen.generate(result)
        assert output.startswith("\u2705")
        assert "客人 Alice 已成功入住 201 房间" in output

    def test_default_message(self):
        result = OntologyResult(
            result_type="action_confirmed",
            data={},
        )
        output = self.gen.generate(result)
        assert "\u2705 操作完成" == output


# ---------------------------------------------------------------------------
# Action needs confirmation formatting
# ---------------------------------------------------------------------------

class TestActionNeedsConfirmFormatting:
    def setup_method(self):
        self.gen = ResponseGenerator()

    def test_needs_confirm(self):
        result = OntologyResult(
            result_type="action_needs_confirm",
            data={
                "action_name": "checkout",
                "params": {"room_number": "201", "guest_name": "Alice"},
                "description": "为 Alice 办理 201 房间退房",
            },
        )
        output = self.gen.generate(result)
        assert "请确认以下操作" in output
        assert "为 Alice 办理 201 房间退房" in output
        assert "参数：" in output
        assert "room_number=201" in output
        assert "guest_name=Alice" in output

    def test_empty_params(self):
        result = OntologyResult(
            result_type="action_needs_confirm",
            data={
                "action_name": "refresh",
                "params": {},
                "description": "刷新数据",
            },
        )
        output = self.gen.generate(result)
        assert "请确认以下操作" in output
        assert "刷新数据" in output
        assert "参数：" in output


# ---------------------------------------------------------------------------
# Missing fields formatting
# ---------------------------------------------------------------------------

class TestMissingFieldsFormatting:
    def setup_method(self):
        self.gen = ResponseGenerator()

    def test_missing_fields(self):
        result = OntologyResult(
            result_type="missing_fields",
            data={
                "action_name": "create_reservation",
                "missing": ["check_in_date", "guest_name", "room_type"],
            },
        )
        output = self.gen.generate(result)
        assert "执行 create_reservation 还需要以下信息" in output
        assert "- check_in_date" in output
        assert "- guest_name" in output
        assert "- room_type" in output

    def test_single_missing_field(self):
        result = OntologyResult(
            result_type="missing_fields",
            data={
                "action_name": "checkin",
                "missing": ["id_number"],
            },
        )
        output = self.gen.generate(result)
        assert "执行 checkin 还需要以下信息" in output
        assert "- id_number" in output
        # Only one bullet
        lines = output.strip().split("\n")
        bullet_lines = [l for l in lines if l.startswith("- ")]
        assert len(bullet_lines) == 1


# ---------------------------------------------------------------------------
# Constraint violation formatting
# ---------------------------------------------------------------------------

class TestConstraintViolationFormatting:
    def setup_method(self):
        self.gen = ResponseGenerator()

    def test_constraint_violation(self):
        result = OntologyResult(
            result_type="constraint_violation",
            data={
                "constraint": "max_occupancy",
                "message": "房间已满，无法加入更多客人",
            },
        )
        output = self.gen.generate(result)
        assert "\u26a0\ufe0f" in output
        assert "操作违反业务规则" in output
        assert "房间已满，无法加入更多客人" in output

    def test_default_constraint_message(self):
        result = OntologyResult(
            result_type="constraint_violation",
            data={"constraint": "unknown"},
        )
        output = self.gen.generate(result)
        assert "未知约束违反" in output


# ---------------------------------------------------------------------------
# State violation formatting
# ---------------------------------------------------------------------------

class TestStateViolationFormatting:
    def setup_method(self):
        self.gen = ResponseGenerator()

    def test_state_violation(self):
        result = OntologyResult(
            result_type="state_violation",
            data={
                "current_state": "vacant_clean",
                "target_state": "vacant_dirty",
                "valid_alternatives": ["occupied", "out_of_order"],
            },
        )
        output = self.gen.generate(result)
        assert "\u26a0\ufe0f" in output
        assert "状态转换无效" in output
        assert "vacant_clean" in output
        assert "vacant_dirty" in output
        assert "\u2192" in output
        assert "可选操作" in output
        assert "occupied" in output
        assert "out_of_order" in output

    def test_state_violation_no_alternatives(self):
        result = OntologyResult(
            result_type="state_violation",
            data={
                "current_state": "checked_out",
                "target_state": "checked_in",
                "valid_alternatives": [],
            },
        )
        output = self.gen.generate(result)
        assert "可选操作：无" in output

    def test_state_violation_defaults(self):
        """Missing keys produce placeholder '?' values."""
        result = OntologyResult(
            result_type="state_violation",
            data={},
        )
        output = self.gen.generate(result)
        assert "? \u2192 ?" in output


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------

class TestErrorFormatting:
    def setup_method(self):
        self.gen = ResponseGenerator()

    def test_basic_error(self):
        result = OntologyResult(
            result_type="error",
            data={"message": "数据库连接失败"},
        )
        output = self.gen.generate(result)
        assert output == "\u274c 数据库连接失败"

    def test_default_error_message(self):
        result = OntologyResult(
            result_type="error",
            data={},
        )
        output = self.gen.generate(result)
        assert "\u274c 未知错误" == output


# ---------------------------------------------------------------------------
# Unknown result_type handling
# ---------------------------------------------------------------------------

class TestUnknownResultType:
    def setup_method(self):
        self.gen = ResponseGenerator()

    def test_unknown_type_falls_back_to_error(self):
        result = OntologyResult(
            result_type="totally_made_up",
            data={"foo": "bar"},
        )
        output = self.gen.generate(result)
        assert "\u274c" in output
        assert "未知结果类型: totally_made_up" in output

    def test_empty_result_type_falls_back(self):
        result = OntologyResult(
            result_type="",
            data={},
        )
        output = self.gen.generate(result)
        assert "\u274c" in output


# ---------------------------------------------------------------------------
# format_query_table
# ---------------------------------------------------------------------------

class TestFormatQueryTable:
    def setup_method(self):
        self.gen = ResponseGenerator()

    def test_empty_table(self):
        output = self.gen.format_query_table([])
        assert output == "（无数据）"

    def test_single_row_auto_fields(self):
        rows = [{"name": "Alice", "phone": "13800138000"}]
        output = self.gen.format_query_table(rows)
        lines = output.split("\n")
        # Header, separator, 1 data row
        assert len(lines) == 3
        assert "姓名" in lines[0]
        assert "电话" in lines[0]
        assert "Alice" in lines[2]
        assert "13800138000" in lines[2]

    def test_explicit_fields_filter(self):
        """Only specified fields should appear in output."""
        rows = [{"name": "Alice", "phone": "123", "email": "a@b.com"}]
        output = self.gen.format_query_table(rows, fields=["name", "email"])
        assert "姓名" in output
        assert "邮箱" in output
        # phone / 电话 should NOT appear
        assert "电话" not in output
        assert "123" not in output

    def test_multiple_rows_alignment(self):
        rows = [
            {"room_number": "101", "status": "vacant_clean"},
            {"room_number": "1001", "status": "occupied"},
        ]
        output = self.gen.format_query_table(rows)
        lines = output.split("\n")
        assert len(lines) == 4  # header + sep + 2 rows
        # Separator should contain dashes
        assert "-" in lines[1]
        assert "+" in lines[1]

    def test_chinese_header_mapping(self):
        rows = [{"room_number": "201", "status": "occupied", "floor": "2"}]
        output = self.gen.format_query_table(rows, fields=["room_number", "status", "floor"])
        assert "房间号" in output
        assert "状态" in output
        assert "楼层" in output

    def test_unknown_field_uses_key_as_header(self):
        rows = [{"custom_field": "value"}]
        output = self.gen.format_query_table(rows)
        # No Chinese mapping exists, so the raw key is used
        assert "custom_field" in output
        assert "value" in output

    def test_missing_field_in_row(self):
        """If a row is missing a requested field, it should show empty string."""
        rows = [
            {"name": "Alice", "phone": "123"},
            {"name": "Bob"},  # missing phone
        ]
        output = self.gen.format_query_table(rows, fields=["name", "phone"])
        lines = output.split("\n")
        # Bob's row should still have correct column count
        assert len(lines) == 4
        # Bob's row should contain "Bob"
        assert "Bob" in lines[3]

    def test_cjk_alignment(self):
        """Chinese characters should be accounted for in column widths."""
        rows = [
            {"name": "张三", "status": "在住"},
            {"name": "Alice", "status": "vacant"},
        ]
        output = self.gen.format_query_table(rows)
        lines = output.split("\n")
        # All non-separator lines should have | separators
        assert " | " in lines[0]
        assert " | " in lines[2]
        assert " | " in lines[3]


# ---------------------------------------------------------------------------
# Integration: generate dispatches to all types
# ---------------------------------------------------------------------------

class TestGenerateDispatch:
    """Verify that generate() dispatches correctly for every valid type."""

    def setup_method(self):
        self.gen = ResponseGenerator()

    @pytest.mark.parametrize("result_type", list(VALID_RESULT_TYPES))
    def test_all_valid_types_produce_output(self, result_type):
        """Every valid result type should produce a non-empty string."""
        # Build minimal data for each type
        data_map = {
            "query_result": {"results": [], "entity": "Test", "total": 0},
            "action_confirmed": {"message": "ok"},
            "action_needs_confirm": {"action_name": "x", "params": {}, "description": "d"},
            "missing_fields": {"action_name": "x", "missing": ["f"]},
            "constraint_violation": {"constraint": "c", "message": "m"},
            "state_violation": {"current_state": "a", "target_state": "b", "valid_alternatives": []},
            "error": {"message": "err"},
        }
        result = OntologyResult(result_type=result_type, data=data_map[result_type])
        output = self.gen.generate(result)
        assert isinstance(output, str)
        assert len(output) > 0
