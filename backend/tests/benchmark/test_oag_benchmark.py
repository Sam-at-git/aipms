"""
OAG (Ontology-Action-Generation) 端到端 Benchmark 测试

完整流程（对齐 Chat UI）：
  自然语言 → AIService.process_message() → 验证 action
  → 处理 missing_fields（通过 follow_up_fields + 选项自动选择）
  → AIService.execute_action() → SQL 数据库验证

特点：
  - 真实 LLM 调用，不 mock
  - YAML 声明式测试用例（统一 assertions dict 格式）
  - 每个 suite 独立数据库（function scope fixture 自动重置）
  - 组内用例按序执行（支持依赖关系）
  - 组内共享对话历史（模拟 Chat UI 多轮对话）
  - 使用 benchmark_assertions 共享断言引擎

运行：
  OPENAI_API_KEY=sk-xxx uv run pytest tests/benchmark/ -v -s --timeout=120
"""
import importlib.util
import logging
import os
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from app.services.benchmark_assertions import (
    evaluate_l2_action,
    evaluate_l3_db,
    evaluate_l4_response,
    evaluate_exec_result,
)

logger = logging.getLogger(__name__)

# 查询类 action，跳过 execute_action
QUERY_ACTIONS = {"ontology_query", "query_smart", "view", "semantic_query", "query_reports"}

BENCHMARK_DATA_PATH = Path(__file__).parent / "benchmark_data.yaml"
BENCHMARK_INIT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "benchmark_init",
)


def _load_benchmark_data():
    """加载 YAML benchmark 数据"""
    with open(BENCHMARK_DATA_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["suites"]


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


def _run_init_script(script_name: str, db) -> None:
    """执行 benchmark_init/ 下的初始化脚本"""
    script_path = os.path.join(BENCHMARK_INIT_DIR, script_name)
    if not os.path.isfile(script_path):
        logger.warning(f"Init script '{script_name}' not found at {script_path}")
        return
    spec = importlib.util.spec_from_file_location("benchmark_init_script", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if hasattr(module, "run"):
        module.run(db)
        logger.info(f"Executed init script: {script_name}")
    else:
        logger.warning(f"Init script '{script_name}' has no run(db) function")


# 动态加载 benchmark suites 作为 parametrize ids
_suites = _load_benchmark_data()


@pytest.mark.slow
class TestOAGBenchmark:
    """OAG 端到端 benchmark 测试"""

    @pytest.mark.parametrize(
        "suite_data",
        _suites,
        ids=[s["name"] for s in _suites],
    )
    def test_suite(self, suite_data, benchmark_db, ai_service, receptionist_user):
        """
        每个 suite 一个 test function，组内按序执行所有 cases。
        function scope fixtures 保证每个 suite 数据库独立。
        组内共享对话历史，模拟 Chat UI 多轮对话。
        """
        suite_name = suite_data["name"]
        cases = suite_data["cases"]
        logger.info(f"\n{'='*60}\nBenchmark Suite: {suite_name}\n{'='*60}")

        # Execute init_script if specified
        init_script = (suite_data.get("init_script") or "").strip()
        if init_script and init_script.lower() != "null":
            _run_init_script(init_script, benchmark_db)

        conversation_history = []

        for i, case in enumerate(cases):
            case_name = case["name"]
            logger.info(f"\n--- [{i+1}/{len(cases)}] {case_name} ---")
            self._run_test_case(
                case, ai_service, receptionist_user, benchmark_db,
                suite_name, conversation_history
            )

    def _run_test_case(self, case, ai_service, user, db, suite_name,
                       conversation_history):
        """执行单个测试用例 — 完整 OAG 流程"""
        case_name = case["name"]
        user_input = _resolve_date_placeholder(case["input"])
        assertions = _resolve_in_dict(case.get("assertions", {}))
        follow_up_fields = _resolve_in_dict(case.get("follow_up_fields") or {})

        # Extract assertion fields from unified assertions dict
        expect_action = assertions.get("expect_action", {})
        skip_execute = assertions.get("skip_execute", False)
        expect_query_result = assertions.get("expect_query_result", False)
        verify_db_specs = assertions.get("verify_db", [])
        expect_result = assertions.get("expect_result", {})

        # Step 1: process_message
        result = ai_service.process_message(
            message=user_input,
            user=user,
            conversation_history=conversation_history,
            topic_id=None,
            follow_up_context=None,
            language="zh",
        )

        conversation_history.append({"role": "user", "content": user_input})
        conversation_history.append({
            "role": "assistant",
            "content": result.get("message", "")
        })

        # Step 2a: expect_query_result — query actions return results directly
        if expect_query_result and not expect_action:
            has_query_result = result.get("query_result") is not None
            has_message = bool(result.get("message"))
            has_actions = len(result.get("suggested_actions", [])) > 0
            assert has_query_result or has_message or has_actions, (
                f"[{suite_name}/{case_name}] expect_query_result but no "
                f"query_result, message, or suggested_actions returned.\n"
                f"Full result: {result}"
            )
            # Check L4 response assertions if present
            l4_results = evaluate_l4_response(result.get("message", ""), assertions)
            for r in l4_results:
                assert r["passed"], (
                    f"[{suite_name}/{case_name}] {r['description']}: "
                    f"expected {r['expected']}, got {r['actual']}"
                )
            logger.info(f"  [QUERY OK] got query result or message")
            return

        # Step 2b: 验证 suggested_actions 存在
        actions = result.get("suggested_actions", [])
        assert len(actions) > 0, (
            f"[{suite_name}/{case_name}] No suggested_actions returned for: "
            f"{user_input!r}\nFull result: {result}"
        )

        action = actions[0]

        # Step 3: 处理 missing_fields
        missing = action.get("missing_fields")
        action_type = action.get("action_type", "")
        if missing:
            resolved = self._resolve_missing_fields(missing, follow_up_fields)
            assert resolved is not None, (
                f"[{suite_name}/{case_name}] Cannot resolve missing_fields: "
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
            conversation_history.append({"role": "user", "content": user_input})
            conversation_history.append({
                "role": "assistant",
                "content": result.get("message", "")
            })

            actions = result.get("suggested_actions", [])
            assert len(actions) > 0, (
                f"[{suite_name}/{case_name}] No suggested_actions after "
                f"follow-up for: {user_input!r}\nFull result: {result}"
            )
            action = actions[0]

        # 验证 missing_fields 已全部解决
        remaining_missing = action.get("missing_fields")
        assert not remaining_missing, (
            f"[{suite_name}/{case_name}] Unresolved missing_fields after "
            f"follow-up: {remaining_missing}"
        )

        # Step 4: L2 — 验证 action_type and params (via assertions engine)
        l2_results = evaluate_l2_action(action, assertions)
        for r in l2_results:
            assert r["passed"], (
                f"[{suite_name}/{case_name}] {r['description']}: "
                f"expected {r['expected']}, got {r['actual']}"
            )

        # Step 5: execute_action（非查询类操作）
        if skip_execute or _is_query_action(action.get("action_type", "")):
            logger.info(
                f"  [SKIP execute] query action: {action.get('action_type')}"
            )
            return

        # 仅 checkout 添加 allow_unsettled
        if action.get("action_type") == "checkout":
            action.get("params", {}).setdefault("allow_unsettled", True)
            action.get("params", {}).setdefault("unsettled_reason", "benchmark test")

        exec_result = ai_service.execute_action(action, user)

        # Step 5b: expect_result — expected failure scenarios
        if expect_result and expect_result.get("success") is False:
            exec_checks = evaluate_exec_result(exec_result, assertions)
            for r in exec_checks:
                assert r["passed"], (
                    f"[{suite_name}/{case_name}] {r['description']}: "
                    f"expected {r['expected']}, got {r['actual']}"
                )
            logger.info(
                f"  [EXPECTED FAIL] {exec_result.get('message', '')[:80]}"
            )
            return

        assert exec_result.get("success"), (
            f"[{suite_name}/{case_name}] execute_action failed: "
            f"{exec_result.get('message')}\nAction: {action}"
        )
        logger.info(f"  [EXEC OK] {exec_result.get('message', '')[:80]}")

        conversation_history.append({
            "role": "assistant",
            "content": exec_result.get("message", "操作执行成功")
        })

        # Step 6: L3 — SQL 验证
        if verify_db_specs:
            db.flush()
            l3_results = evaluate_l3_db(db, assertions)
            for r in l3_results:
                assert r["passed"], (
                    f"[{suite_name}/{case_name}] {r['description']}: "
                    f"expected {r['expected']}, got {r['actual']}"
                )

        # Step 7: L4 — Response assertions
        l4_results = evaluate_l4_response(
            result.get("message", "") + exec_result.get("message", ""),
            assertions,
        )
        for r in l4_results:
            assert r["passed"], (
                f"[{suite_name}/{case_name}] {r['description']}: "
                f"expected {r['expected']}, got {r['actual']}"
            )

    @staticmethod
    def _get_field_name(field):
        """Extract field name from various missing_field formats."""
        if isinstance(field, str):
            return field
        if isinstance(field, dict):
            return field.get("field_name", "")
        return getattr(field, "field_name", "")

    def _resolve_missing_fields(self, missing_fields, follow_up_fields):
        """从 YAML follow_up_fields 和服务端选项解析缺失字段。"""
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
