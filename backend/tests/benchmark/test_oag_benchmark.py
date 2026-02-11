"""
OAG (Ontology-Action-Generation) 端到端 Benchmark 测试

完整流程：
  自然语言 → AIService.process_message() → 验证 action
  → AIService.execute_action() → SQL 数据库验证

特点：
  - 真实 LLM 调用，不 mock
  - YAML 声明式测试用例
  - 每个 group 独立数据库（function scope fixture 自动重置）
  - 组内用例按序执行（支持依赖关系）
  - SQL 声明式断言验证数据库状态

运行：
  OPENAI_API_KEY=sk-xxx uv run pytest tests/benchmark/ -v -s --timeout=120
"""
import os
import re
import logging
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml
from sqlalchemy import text

logger = logging.getLogger(__name__)

# 查询类 action，跳过 execute_action
QUERY_ACTIONS = {"ontology_query", "query_smart", "view", "semantic_query"}

# Fields that _resolve_action_params can auto-resolve from DB context
# These should not cause missing_fields assertion failures
AUTO_RESOLVABLE_FIELDS = {
    "extend_stay": {"stay_record_id"},
    "change_room": {"stay_record_id"},
    "assign_task": {"task_id"},
    "complete_task": {"task_id"},
    "cancel_reservation": {"reservation_id"},
    "modify_reservation": {"reservation_id"},
    "add_payment": {"bill_id"},
    "checkout": {"stay_record_id"},
}

# ID fields that can always be resolved from DB regardless of action type
# These are entity IDs the LLM cannot extract from natural language
DB_RESOLVABLE_IDS = {"task_id", "stay_record_id", "bill_id", "reservation_id"}

BENCHMARK_DATA_PATH = Path(__file__).parent / "benchmark_data.yaml"


def _load_benchmark_data():
    """加载 YAML benchmark 数据，解析日期占位符"""
    with open(BENCHMARK_DATA_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["groups"]


def _resolve_date_placeholder(value):
    """将 $today/$tomorrow/$day_after_tomorrow 替换为实际日期字符串"""
    if not isinstance(value, str):
        return value
    today = date.today()
    replacements = {
        "$today": today.isoformat(),
        "$tomorrow": (today + timedelta(days=1)).isoformat(),
        "$day_after_tomorrow": (today + timedelta(days=2)).isoformat(),
    }
    result = value
    for placeholder, date_str in replacements.items():
        result = result.replace(placeholder, date_str)
    return result


def _resolve_in_dict(d):
    """递归替换字典中的日期占位符"""
    if isinstance(d, dict):
        return {k: _resolve_in_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_resolve_in_dict(item) for item in d]
    if isinstance(d, str):
        return _resolve_date_placeholder(d)
    return d


def _is_query_action(action_type: str) -> bool:
    """判断是否为查询类操作"""
    return (
        action_type in QUERY_ACTIONS
        or action_type.startswith("query_")
    )


# 动态加载 benchmark groups 作为 parametrize ids
_groups = _load_benchmark_data()


@pytest.mark.slow
class TestOAGBenchmark:
    """OAG 端到端 benchmark 测试"""

    @pytest.mark.parametrize(
        "group_data",
        _groups,
        ids=[g["name"] for g in _groups],
    )
    def test_group(self, group_data, benchmark_db, ai_service, receptionist_user):
        """
        每个 group 一个 test function，组内按序执行所有 test cases。
        function scope fixtures 保证每个 group 数据库独立。
        """
        group_name = group_data["name"]
        tests = group_data["tests"]
        logger.info(f"\n{'='*60}\nBenchmark Group: {group_name}\n{'='*60}")

        for i, case in enumerate(tests):
            case_name = case["name"]
            logger.info(f"\n--- [{i+1}/{len(tests)}] {case_name} ---")
            self._run_test_case(
                case, ai_service, receptionist_user, benchmark_db, group_name
            )

    def _run_test_case(self, case, ai_service, user, db, group_name):
        """执行单个测试用例"""
        case_name = case["name"]
        user_input = _resolve_date_placeholder(case["input"])
        expect = _resolve_in_dict(case.get("expect_action", {}))
        skip_execute = case.get("skip_execute", False)
        expect_query_result = case.get("expect_query_result", False)
        follow_up_fields = case.get("follow_up_fields")
        verify_db_specs = _resolve_in_dict(case.get("verify_db", []))

        # Step 1: process_message
        result = ai_service.process_message(
            message=user_input,
            user=user,
            conversation_history=None,
            topic_id=None,
            follow_up_context=None,
            language="zh",
        )

        # Step 2a: expect_query_result — query actions may return results directly
        if expect_query_result:
            has_query_result = result.get("query_result") is not None
            has_message = bool(result.get("message"))
            has_actions = len(result.get("suggested_actions", [])) > 0
            assert has_query_result or has_message or has_actions, (
                f"[{group_name}/{case_name}] expect_query_result but no "
                f"query_result, message, or suggested_actions returned.\n"
                f"Full result: {result}"
            )
            logger.info(f"  [QUERY OK] got query result or message")
            return

        # Step 2b: 验证 suggested_actions 存在
        actions = result.get("suggested_actions", [])
        assert len(actions) > 0, (
            f"[{group_name}/{case_name}] No suggested_actions returned for: "
            f"{user_input!r}\nFull result: {result}"
        )

        action = actions[0]

        # Step 3: Handle missing_fields — auto-select from options + follow_up_fields
        missing = action.get("missing_fields")
        action_type = action.get("action_type", "")
        if missing:
            resolved = self._auto_resolve_missing_fields(
                missing, follow_up_fields or {}, action_type=action_type
            )
            if resolved is not None and resolved:
                # Merge: original params + auto-resolved + all follow_up_fields
                collected = {**action.get("params", {}), **resolved}
                if follow_up_fields:
                    for k, v in follow_up_fields.items():
                        if k not in collected:
                            collected[k] = _resolve_date_placeholder(str(v))
                logger.info(
                    f"  [FOLLOW-UP] missing_fields resolved with: {resolved}"
                )
                follow_up_context = {
                    "action_type": action_type,
                    "collected_fields": collected,
                }
                result = ai_service.process_message(
                    message=user_input,
                    user=user,
                    conversation_history=None,
                    topic_id=None,
                    follow_up_context=follow_up_context,
                    language="zh",
                )
                actions = result.get("suggested_actions", [])
                assert len(actions) > 0, (
                    f"[{group_name}/{case_name}] No suggested_actions after "
                    f"follow-up for: {user_input!r}\nFull result: {result}"
                )
                action = actions[0]
                missing = action.get("missing_fields")

        # Filter out auto-resolvable fields (handled by _resolve_action_params)
        # and fields already provided via follow_up_fields
        if missing:
            resolvable = AUTO_RESOLVABLE_FIELDS.get(action_type, set()) | DB_RESOLVABLE_IDS
            follow_up_keys = set(follow_up_fields.keys()) if follow_up_fields else set()
            ignorable = resolvable | follow_up_keys
            remaining = [f for f in missing if self._get_field_name(f) not in ignorable]
            if not remaining:
                filtered = [self._get_field_name(f) for f in missing]
                logger.info(f"  [OK] All missing_fields are resolvable/provided: "
                           f"{filtered}")
                missing = None
            else:
                missing = remaining

        assert not missing, (
            f"[{group_name}/{case_name}] LLM returned missing_fields: {missing}\n"
            f"Input: {user_input!r}"
        )

        # Step 4: 验证 action_type
        if "action_type" in expect:
            assert action["action_type"] == expect["action_type"], (
                f"[{group_name}/{case_name}] action_type mismatch: "
                f"expected {expect['action_type']!r}, got {action['action_type']!r}"
            )
        elif "action_type_pattern" in expect:
            pattern = expect["action_type_pattern"]
            assert re.match(pattern, action["action_type"]), (
                f"[{group_name}/{case_name}] action_type {action['action_type']!r} "
                f"does not match pattern {pattern!r}"
            )

        # Step 5: 验证 params_contain
        if "params_contain" in expect:
            params = action.get("params", {})
            for key, expected_val in expect["params_contain"].items():
                actual_val = params.get(key)
                assert actual_val is not None, (
                    f"[{group_name}/{case_name}] param '{key}' not found in params. "
                    f"Available: {list(params.keys())}"
                )
                assert str(actual_val) == str(expected_val), (
                    f"[{group_name}/{case_name}] param '{key}': "
                    f"expected {expected_val!r}, got {actual_val!r}"
                )

        # Step 6: execute_action（非查询类操作）
        if skip_execute or _is_query_action(action.get("action_type", "")):
            logger.info(
                f"  [SKIP execute] query action: {action.get('action_type')}"
            )
            return

        # Resolve entity IDs that the LLM can't extract (task_id, bill_id, etc.)
        self._resolve_action_params(action, db, user_input)

        exec_result = ai_service.execute_action(action, user)
        assert exec_result.get("success"), (
            f"[{group_name}/{case_name}] execute_action failed: "
            f"{exec_result.get('message')}\nAction: {action}"
        )
        logger.info(f"  [EXEC OK] {exec_result.get('message', '')[:80]}")

        # Step 7: SQL 验证
        if verify_db_specs:
            self._verify_db(db, verify_db_specs, group_name, case_name)

    @staticmethod
    def _get_field_name(field):
        """Extract field name from various missing_field formats."""
        if isinstance(field, str):
            return field
        if isinstance(field, dict):
            return field.get("field_name", "")
        return getattr(field, "field_name", "")

    def _auto_resolve_missing_fields(self, missing_fields, follow_up_fields,
                                      action_type=None):
        """Auto-select first option for select fields, use follow_up for others.

        Fields in AUTO_RESOLVABLE_FIELDS are skipped (handled by _resolve_action_params).
        Returns resolved dict or None if any non-auto-resolvable field cannot be resolved.
        """
        resolvable = AUTO_RESOLVABLE_FIELDS.get(action_type, set()) if action_type else set()
        resolved = {}
        for field in missing_fields:
            fname = self._get_field_name(field)

            if isinstance(field, dict):
                options = field.get("options") or []
            elif isinstance(field, str):
                options = []
            else:
                options = getattr(field, "options", None) or []

            # follow_up_fields take priority over auto-select from options
            if fname in follow_up_fields:
                resolved[fname] = follow_up_fields[fname]
                logger.info(f"  [FOLLOW-UP-FIELD] {fname} = {resolved[fname]}")
            elif options:
                opt = options[0]
                resolved[fname] = (
                    opt["value"] if isinstance(opt, dict) else opt.value
                )
                logger.info(f"  [AUTO-SELECT] {fname} = {resolved[fname]}")
            elif fname in resolvable or fname in DB_RESOLVABLE_IDS:
                # Skip fields that _resolve_action_params will handle from DB
                logger.info(f"  [AUTO-RESOLVABLE] {fname} (will resolve from DB)")
                continue
            else:
                logger.warning(f"  [UNRESOLVED] missing field: {fname}")
                return None
        return resolved

    def _resolve_action_params(self, action, db, user_input=""):
        """Resolve entity IDs from available params before execution.

        Some actions require entity IDs (task_id, bill_id) that the LLM cannot
        extract from natural language. This method looks them up from the DB.
        """
        # Flush so raw SQL can see ORM-created records from prior steps
        db.flush()

        action_type = action.get("action_type", "")
        params = action.get("params", {})

        # Extract room_number from params or user input text
        room_number = params.get("room_number")
        if not room_number:
            # Match room numbers: "308房", "308再收", "205的客人", etc.
            m = re.search(r"(\d{3,4})(?:房|号|的|再|$)", user_input)
            if not m:
                # Fallback: first 3-4 digit number in input
                m = re.search(r"(\d{3,4})", user_input)
            if m:
                room_number = m.group(1)

        if action_type == "checkout":
            # Allow unsettled bill checkout for benchmark tests
            if "allow_unsettled" not in params:
                params["allow_unsettled"] = True
                params["unsettled_reason"] = "benchmark test"
                logger.info("  [RESOLVE] set allow_unsettled=True")
            # Resolve stay_record_id from room_number
            if not params.get("stay_record_id"):
                rn = room_number or params.get("room_number")
                if rn:
                    row = db.execute(
                        text(
                            "SELECT s.id FROM stay_records s "
                            "JOIN rooms r ON s.room_id = r.id "
                            "WHERE r.room_number = :rn "
                            "AND s.status IN ('ACTIVE', 'active') "
                            "ORDER BY s.id DESC LIMIT 1"
                        ),
                        {"rn": str(rn)},
                    ).fetchone()
                    if row:
                        params["stay_record_id"] = row[0]
                        logger.info(f"  [RESOLVE] stay_record_id = {row[0]}")

        elif action_type in ("complete_task", "assign_task") and not params.get("task_id"):
            if room_number:
                row = db.execute(
                    text(
                        "SELECT t.id FROM tasks t JOIN rooms r ON t.room_id = r.id "
                        "WHERE r.room_number = :rn "
                        "AND t.status NOT IN ('COMPLETED', 'completed') "
                        "ORDER BY t.created_at DESC LIMIT 1"
                    ),
                    {"rn": str(room_number)},
                ).fetchone()
                if row:
                    params["task_id"] = row[0]
                    logger.info(f"  [RESOLVE] task_id = {row[0]}")

        elif action_type in ("extend_stay", "change_room"):
            # Always resolve stay_record_id from room_number — LLM may put
            # room number as stay_record_id (e.g. "203" instead of actual ID)
            if room_number:
                row = db.execute(
                    text(
                        "SELECT s.id FROM stay_records s "
                        "JOIN rooms r ON s.room_id = r.id "
                        "WHERE r.room_number = :rn "
                        "AND s.status IN ('ACTIVE', 'active') "
                        "ORDER BY s.id DESC LIMIT 1"
                    ),
                    {"rn": str(room_number)},
                ).fetchone()
                if row:
                    params["stay_record_id"] = row[0]
                    logger.info(f"  [RESOLVE] stay_record_id = {row[0]}")

        elif action_type in ("cancel_reservation", "modify_reservation"):
            if not params.get("reservation_id") and not params.get("reservation_no"):
                # Try to find reservation by guest name from params or input
                guest_name = params.get("guest_name")
                if not guest_name:
                    # Extract guest name: match 2-3 Chinese chars followed by
                    # a non-name char (的/不/要/说 etc.) to avoid greedy over-capture
                    m = re.search(
                        r"(?:客人|客户|预订人)?[，,\s]*([\u4e00-\u9fa5]{2,3})(?:的|不|要|说|$)",
                        user_input,
                    )
                    if not m:
                        # Fallback: find guest by matching against known guests in DB
                        m = re.search(r"([\u4e00-\u9fa5]{2,3})", user_input)
                    if m:
                        guest_name = m.group(1)
                if guest_name:
                    row = db.execute(
                        text(
                            "SELECT r.id FROM reservations r "
                            "JOIN guests g ON r.guest_id = g.id "
                            "WHERE g.name LIKE :name "
                            "AND LOWER(r.status) = 'confirmed' "
                            "ORDER BY r.id DESC LIMIT 1"
                        ),
                        {"name": f"%{guest_name}%"},
                    ).fetchone()
                    if row:
                        params["reservation_id"] = row[0]
                        logger.info(f"  [RESOLVE] reservation_id = {row[0]}")

        elif action_type == "add_payment" and not params.get("bill_id"):
            if room_number:
                row = db.execute(
                    text(
                        "SELECT b.id FROM bills b "
                        "JOIN stay_records s ON b.stay_record_id = s.id "
                        "JOIN rooms r ON s.room_id = r.id "
                        "WHERE r.room_number = :rn "
                        "ORDER BY b.created_at DESC LIMIT 1"
                    ),
                    {"rn": str(room_number)},
                ).fetchone()
                if row:
                    params["bill_id"] = row[0]
                    logger.info(f"  [RESOLVE] bill_id = {row[0]}")

    def _verify_db(self, db, verifications, group_name, case_name):
        """执行 SQL 声明式验证"""
        # flush pending changes so raw SQL can see them
        db.flush()

        for v in verifications:
            sql = v["sql"]
            expect = v["expect"]

            rows = db.execute(text(sql)).fetchall()

            # 验证行数
            if "rows" in expect:
                assert len(rows) == expect["rows"], (
                    f"[{group_name}/{case_name}] SQL row count mismatch.\n"
                    f"SQL: {sql}\n"
                    f"Expected {expect['rows']} rows, got {len(rows)}"
                )

            # 验证第一行值
            if "values" in expect:
                assert len(rows) > 0, (
                    f"[{group_name}/{case_name}] SQL returned 0 rows, "
                    f"cannot verify values.\nSQL: {sql}"
                )
                row = rows[0]
                # 兼容 Row 对象的不同属性访问方式
                if hasattr(row, "_mapping"):
                    row_dict = dict(row._mapping)
                elif hasattr(row, "_fields"):
                    row_dict = dict(zip(row._fields, row))
                else:
                    row_dict = dict(row)

                for col, expected_val in expect["values"].items():
                    actual_val = row_dict.get(col)
                    assert actual_val is not None, (
                        f"[{group_name}/{case_name}] Column '{col}' not in result.\n"
                        f"SQL: {sql}\nAvailable: {list(row_dict.keys())}"
                    )
                    assert str(actual_val).lower() == str(expected_val).lower(), (
                        f"[{group_name}/{case_name}] Column '{col}': "
                        f"expected {expected_val!r}, got {actual_val!r}\n"
                        f"SQL: {sql}"
                    )
                    logger.info(f"  [DB OK] {col} = {actual_val}")
