"""
Query Pipeline Benchmark — 验证统一查询管道 (ontology_query) 的端到端行为

完整流程（对齐 Chat UI）：
  自然语言 → AIService.process_message() → ontology_query / query_reports → 验证

特点：
  - 真实 LLM 调用，不 mock
  - YAML 声明式测试用例（统一 assertions dict 格式）+ 弹性断言
  - 每个 suite 独立数据库 + init_data 种子数据
  - 组内用例按序执行，共享对话历史（模拟 Chat UI 多轮对话）
  - is_setup 标记的 cases 执行 mutation 构造查询前提条件

运行：
  OPENAI_API_KEY=sk-xxx uv run pytest tests/benchmark/test_query_pipeline_benchmark.py -v -s --no-cov
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
    evaluate_l4_response,
    evaluate_query_result,
)

logger = logging.getLogger(__name__)

QUERY_BENCHMARK_DATA_PATH = Path(__file__).parent / "query_benchmark_data.yaml"
BENCHMARK_INIT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "benchmark_init",
)

# 查询类 action，不需要 execute_action
QUERY_ACTIONS = {
    "ontology_query", "query_smart", "view", "semantic_query", "query_reports",
}


def _load_query_benchmark_data():
    with open(QUERY_BENCHMARK_DATA_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["suites"]


def _resolve_date(value):
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
    if isinstance(d, dict):
        return {k: _resolve_in_dict(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_resolve_in_dict(item) for item in d]
    if isinstance(d, str):
        return _resolve_date(d)
    return d


def _is_query_action(action_type: str) -> bool:
    return action_type in QUERY_ACTIONS or action_type.startswith("query_")


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


_suites = _load_query_benchmark_data()


@pytest.mark.slow
class TestQueryPipelineBenchmark:
    """Query pipeline 端到端 benchmark"""

    @pytest.mark.parametrize(
        "suite_data",
        _suites,
        ids=[s["name"] for s in _suites],
    )
    def test_suite(self, suite_data, benchmark_db, ai_service, receptionist_user):
        suite_name = suite_data["name"]
        cases = suite_data["cases"]
        logger.info(f"\n{'='*60}\nQuery Benchmark: {suite_name}\n{'='*60}")

        # Execute init_script if specified
        init_script = (suite_data.get("init_script") or "").strip()
        if init_script and init_script.lower() != "null":
            _run_init_script(init_script, benchmark_db)

        conversation_history = []

        for i, case in enumerate(cases):
            case_name = case["name"]
            assertions = _resolve_in_dict(case.get("assertions", {}))
            is_setup = assertions.get("is_setup", False)

            if is_setup:
                logger.info(f"\n  [SETUP {i+1}] {case_name}")
                self._run_setup(
                    case, ai_service, receptionist_user,
                    conversation_history, suite_name,
                )
            else:
                logger.info(f"\n--- [{i+1}/{len(cases)}] {case_name} ---")
                self._run_query_test(
                    case, ai_service, receptionist_user,
                    conversation_history, suite_name,
                )

    # ------------------------------------------------------------------
    # Setup: execute a mutation to create preconditions for queries
    # ------------------------------------------------------------------
    def _run_setup(self, case, ai_service, user, history, suite_name):
        user_input = _resolve_date(case["input"])
        assertions = _resolve_in_dict(case.get("assertions", {}))
        expect_action = assertions.get("expect_action", {})
        follow_up_fields = _resolve_in_dict(case.get("follow_up_fields") or {})

        result = ai_service.process_message(
            message=user_input,
            user=user,
            conversation_history=history,
            topic_id=None,
            follow_up_context=None,
            language="zh",
        )

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": result.get("message", "")})

        actions = result.get("suggested_actions", [])
        if not actions:
            logger.warning(f"  [SETUP WARN] No actions for: {user_input}")
            return

        action = actions[0]
        action_type = action.get("action_type", "")

        # Verify expected action type if specified
        if expect_action:
            expected_type = expect_action.get("action_type", "")
            if expected_type:
                assert action_type == expected_type, (
                    f"[{suite_name}/setup] expected {expected_type}, "
                    f"got {action_type} for: {user_input}"
                )

        # Handle missing_fields
        missing = action.get("missing_fields")
        if missing:
            resolved = self._resolve_missing(missing, follow_up_fields)
            if resolved is not None:
                collected = {**action.get("params", {}), **resolved}
                follow_up_context = {
                    "action_type": action_type,
                    "collected_fields": collected,
                }
                result = ai_service.process_message(
                    message=user_input,
                    user=user,
                    conversation_history=history,
                    topic_id=None,
                    follow_up_context=follow_up_context,
                    language="zh",
                )
                history.append({"role": "user", "content": user_input})
                history.append({
                    "role": "assistant",
                    "content": result.get("message", ""),
                })
                actions = result.get("suggested_actions", [])
                if actions:
                    action = actions[0]

        # Skip execute for query actions
        if _is_query_action(action.get("action_type", "")):
            logger.info(f"  [SETUP] query action, skip execute")
            return

        # Execute the mutation
        if action.get("action_type") == "checkout":
            action.get("params", {}).setdefault("allow_unsettled", True)
            action.get("params", {}).setdefault("unsettled_reason", "benchmark")

        exec_result = ai_service.execute_action(action, user)
        if exec_result.get("success"):
            logger.info(f"  [SETUP OK] {exec_result.get('message', '')[:60]}")
        else:
            logger.warning(
                f"  [SETUP FAIL] {exec_result.get('message', '')[:80]}"
            )

        history.append({
            "role": "assistant",
            "content": exec_result.get("message", ""),
        })

    # ------------------------------------------------------------------
    # Query test: send natural language, validate response
    # ------------------------------------------------------------------
    def _run_query_test(self, case, ai_service, user, history, suite_name):
        case_name = case["name"]
        user_input = _resolve_date(case["input"])
        assertions = _resolve_in_dict(case.get("assertions", {}))

        result = ai_service.process_message(
            message=user_input,
            user=user,
            conversation_history=history,
            topic_id=None,
            follow_up_context=None,
            language="zh",
        )

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": result.get("message", "")})

        message = result.get("message", "")
        actions = result.get("suggested_actions", [])
        query_result = result.get("query_result")
        action_type = actions[0].get("action_type", "") if actions else ""

        # If the LLM returned a query action that requires confirmation,
        # execute it to get the actual query result
        if (
            actions
            and _is_query_action(action_type)
            and query_result is None
        ):
            logger.info(f"  [AUTO-EXECUTE] {action_type} (requires_confirmation)")
            exec_result = ai_service.execute_action(actions[0], user)
            if exec_result:
                if exec_result.get("message"):
                    message = exec_result["message"]
                if exec_result.get("query_result"):
                    query_result = exec_result["query_result"]
                    result["query_result"] = query_result
                result["message"] = message
                history.append({
                    "role": "assistant",
                    "content": message,
                })

        label = f"[{suite_name}/{case_name}]"
        logger.info(f"  action_type={action_type!r}")
        logger.info(f"  message={message[:120]}")
        if query_result:
            rows = query_result.get("rows", [])
            logger.info(f"  query_result: {len(rows)} rows")

        # --- Assertions via shared engine ---

        # 0. Basic: must produce a message or query_result
        assert message or query_result, (
            f"{label} no message and no query_result. Full result: {result}"
        )

        # 1. L2: action_type check (from assertions.expect_action)
        if assertions.get("expect_action") and action_type:
            l2_results = evaluate_l2_action(
                {"action_type": action_type, "params": {}}, assertions
            )
            for r in l2_results:
                assert r["passed"], (
                    f"{label} {r['description']}: "
                    f"expected {r['expected']}, got {r['actual']}"
                )

        # 2. L4: message assertions (message_contains OR, message_not_contains)
        l4_results = evaluate_l4_response(message, assertions)
        for r in l4_results:
            assert r["passed"], (
                f"{label} {r['description']}: "
                f"expected {r['expected']}, got {r['actual']}"
            )

        # 3. Query result assertions
        qr_results = evaluate_query_result(result, assertions)
        for r in qr_results:
            assert r["passed"], (
                f"{label} {r['description']}: "
                f"expected {r['expected']}, got {r['actual']}"
            )

        logger.info(f"  [PASS] {case_name}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _get_field_name(field):
        if isinstance(field, str):
            return field
        if isinstance(field, dict):
            return field.get("field_name", "")
        return getattr(field, "field_name", "")

    def _resolve_missing(self, missing_fields, follow_up_fields):
        resolved = {}
        for field in missing_fields:
            fname = self._get_field_name(field)
            options = []
            if isinstance(field, dict):
                options = field.get("options") or []
            elif not isinstance(field, str):
                options = getattr(field, "options", None) or []

            if fname in follow_up_fields:
                resolved[fname] = _resolve_date(str(follow_up_fields[fname]))
            elif options:
                opt = options[0]
                resolved[fname] = (
                    opt["value"] if isinstance(opt, dict) else opt.value
                )
            else:
                logger.warning(f"  [UNRESOLVED] {fname}")
                return None
        return resolved
