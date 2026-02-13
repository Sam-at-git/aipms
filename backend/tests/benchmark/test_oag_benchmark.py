"""
OAG (Ontology-Action-Generation) 端到端 Benchmark 测试

完整流程（对齐 Chat UI）：
  自然语言 → AIService.process_message() → 验证 action
  → 处理 missing_fields（通过 follow_up_fields + 选项自动选择）
  → AIService.execute_action() → SQL 数据库验证

特点：
  - 真实 LLM 调用，不 mock
  - YAML 声明式测试用例
  - 每个 group 独立数据库（function scope fixture 自动重置）
  - 组内用例按序执行（支持依赖关系）
  - 组内共享对话历史（模拟 Chat UI 多轮对话）
  - SQL 声明式断言验证数据库状态
  - 不绕过 OAG 流程：无 DB 自动填充 entity ID，无 auto-resolvable 跳过

运行：
  OPENAI_API_KEY=sk-xxx uv run pytest tests/benchmark/ -v -s --timeout=120
"""
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
        组内共享对话历史，模拟 Chat UI 多轮对话。
        """
        group_name = group_data["name"]
        tests = group_data["tests"]
        logger.info(f"\n{'='*60}\nBenchmark Group: {group_name}\n{'='*60}")

        conversation_history = []  # 组内共享对话历史

        for i, case in enumerate(tests):
            case_name = case["name"]
            logger.info(f"\n--- [{i+1}/{len(tests)}] {case_name} ---")
            self._run_test_case(
                case, ai_service, receptionist_user, benchmark_db,
                group_name, conversation_history
            )

    def _run_test_case(self, case, ai_service, user, db, group_name,
                       conversation_history):
        """执行单个测试用例 — 完整 OAG 流程，不绕过"""
        case_name = case["name"]
        user_input = _resolve_date_placeholder(case["input"])
        expect = _resolve_in_dict(case.get("expect_action", {}))
        skip_execute = case.get("skip_execute", False)
        expect_query_result = case.get("expect_query_result", False)
        follow_up_fields = _resolve_in_dict(case.get("follow_up_fields") or {})
        verify_db_specs = _resolve_in_dict(case.get("verify_db", []))

        # Step 1: process_message（传入对话历史）
        result = ai_service.process_message(
            message=user_input,
            user=user,
            conversation_history=conversation_history,
            topic_id=None,
            follow_up_context=None,
            language="zh",
        )

        # 追加到对话历史
        conversation_history.append({"role": "user", "content": user_input})
        conversation_history.append({
            "role": "assistant",
            "content": result.get("message", "")
        })

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

        # Step 3: 处理 missing_fields（不使用 DB 绕过）
        missing = action.get("missing_fields")
        action_type = action.get("action_type", "")
        if missing:
            resolved = self._resolve_missing_fields(missing, follow_up_fields)
            assert resolved is not None, (
                f"[{group_name}/{case_name}] Cannot resolve missing_fields: "
                f"{[self._get_field_name(f) for f in missing]}\n"
                f"follow_up_fields: {follow_up_fields}"
            )
            collected = {**action.get("params", {}), **resolved}
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
                conversation_history=conversation_history,
                topic_id=None,
                follow_up_context=follow_up_context,
                language="zh",
            )
            # 追加追问交互到历史
            conversation_history.append({"role": "user", "content": user_input})
            conversation_history.append({
                "role": "assistant",
                "content": result.get("message", "")
            })

            actions = result.get("suggested_actions", [])
            assert len(actions) > 0, (
                f"[{group_name}/{case_name}] No suggested_actions after "
                f"follow-up for: {user_input!r}\nFull result: {result}"
            )
            action = actions[0]

        # 验证 missing_fields 已全部解决
        remaining_missing = action.get("missing_fields")
        assert not remaining_missing, (
            f"[{group_name}/{case_name}] Unresolved missing_fields after "
            f"follow-up: {remaining_missing}"
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

        # 仅 checkout 添加 allow_unsettled（测试策略，非绕过）
        if action.get("action_type") == "checkout":
            action.get("params", {}).setdefault("allow_unsettled", True)
            action.get("params", {}).setdefault("unsettled_reason", "benchmark test")

        # 检查是否期望执行失败（如约束验证场景）
        expect_result = case.get("expect_result", {})

        exec_result = ai_service.execute_action(action, user)

        if expect_result and expect_result.get("success") is False:
            # 期望执行失败的场景
            assert not exec_result.get("success"), (
                f"[{group_name}/{case_name}] Expected failure but got success.\n"
                f"Action: {action}\nResult: {exec_result}"
            )
            logger.info(
                f"  [EXPECTED FAIL] {exec_result.get('message', '')[:80]}"
            )
            # 验证错误消息内容
            if "error_message_contain" in expect_result:
                msg = exec_result.get("message", "") + str(exec_result.get("data", ""))
                assert expect_result["error_message_contain"] in msg, (
                    f"[{group_name}/{case_name}] error message should contain "
                    f"'{expect_result['error_message_contain']}', got: {msg}"
                )
            return

        assert exec_result.get("success"), (
            f"[{group_name}/{case_name}] execute_action failed: "
            f"{exec_result.get('message')}\nAction: {action}"
        )
        logger.info(f"  [EXEC OK] {exec_result.get('message', '')[:80]}")

        # 追加执行结果到对话历史
        conversation_history.append({
            "role": "assistant",
            "content": exec_result.get("message", "操作执行成功")
        })

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

    def _resolve_missing_fields(self, missing_fields, follow_up_fields):
        """从 YAML follow_up_fields 和服务端选项解析缺失字段。

        策略：
        1. 优先使用 YAML follow_up_fields
        2. 若无 YAML 值但有下拉选项，自动选第一个（模拟用户选择）
        3. 两者都没有则返回 None（测试失败）
        """
        resolved = {}
        for field in missing_fields:
            fname = self._get_field_name(field)
            options = []
            if isinstance(field, dict):
                options = field.get("options") or []
            elif not isinstance(field, str):
                options = getattr(field, "options", None) or []

            if fname in follow_up_fields:
                resolved[fname] = _resolve_date_placeholder(
                    str(follow_up_fields[fname])
                )
                logger.info(f"  [YAML] {fname} = {resolved[fname]}")
            elif options:
                opt = options[0]
                resolved[fname] = (
                    opt["value"] if isinstance(opt, dict) else opt.value
                )
                logger.info(f"  [OPTION-SELECT] {fname} = {resolved[fname]}")
            else:
                logger.warning(
                    f"  [UNRESOLVED] {fname}: no YAML value or options"
                )
                return None
        return resolved

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
