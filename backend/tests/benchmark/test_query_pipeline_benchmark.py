"""
Query Pipeline Benchmark — 验证统一查询管道 (ontology_query) 的端到端行为

完整流程（对齐 Chat UI）：
  自然语言 → AIService.process_message() → ontology_query / query_reports → 验证

特点：
  - 真实 LLM 调用，不 mock
  - YAML 声明式测试用例 + 弹性断言（LLM 输出有随机性）
  - 每个 group 独立数据库 + init_data 种子数据
  - 组内用例按序执行，共享对话历史（模拟 Chat UI 多轮对话）
  - setup 阶段可执行 mutation 操作构造查询前提条件

运行：
  OPENAI_API_KEY=sk-xxx uv run pytest tests/benchmark/test_query_pipeline_benchmark.py -v -s --no-cov
"""
import logging
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

logger = logging.getLogger(__name__)

QUERY_BENCHMARK_DATA_PATH = Path(__file__).parent / "query_benchmark_data.yaml"

# 查询类 action，不需要 execute_action
QUERY_ACTIONS = {
    "ontology_query", "query_smart", "view", "semantic_query", "query_reports",
}


def _load_query_benchmark_data():
    with open(QUERY_BENCHMARK_DATA_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["groups"]


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


_groups = _load_query_benchmark_data()


@pytest.mark.slow
class TestQueryPipelineBenchmark:
    """Query pipeline 端到端 benchmark"""

    @pytest.mark.parametrize(
        "group_data",
        _groups,
        ids=[g["name"] for g in _groups],
    )
    def test_group(self, group_data, benchmark_db, ai_service, receptionist_user):
        group_name = group_data["name"]
        setup_cases = group_data.get("setup", [])
        tests = group_data["tests"]
        logger.info(f"\n{'='*60}\nQuery Benchmark: {group_name}\n{'='*60}")

        conversation_history = []

        # Phase 1: setup — execute mutations to build pre-conditions
        for i, setup in enumerate(setup_cases):
            logger.info(f"\n  [SETUP {i+1}/{len(setup_cases)}] {setup['input'][:50]}")
            self._run_setup(
                setup, ai_service, receptionist_user,
                conversation_history, group_name,
            )

        # Phase 2: query tests
        for i, case in enumerate(tests):
            case_name = case["name"]
            logger.info(f"\n--- [{i+1}/{len(tests)}] {case_name} ---")
            self._run_query_test(
                case, ai_service, receptionist_user,
                conversation_history, group_name,
            )

    # ------------------------------------------------------------------
    # Setup: execute a mutation to create preconditions for queries
    # ------------------------------------------------------------------
    def _run_setup(self, setup, ai_service, user, history, group_name):
        user_input = _resolve_date(setup["input"])
        expect_action = setup.get("expect_action", "")
        follow_up_fields = _resolve_in_dict(setup.get("follow_up_fields") or {})

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
            assert action_type == expect_action, (
                f"[{group_name}/setup] expected {expect_action}, "
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
    def _run_query_test(self, case, ai_service, user, history, group_name):
        case_name = case["name"]
        user_input = _resolve_date(case["input"])
        expect = case.get("expect", {})

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
        # execute it to get the actual query result (simulates user clicking confirm)
        if (
            actions
            and _is_query_action(action_type)
            and query_result is None
        ):
            logger.info(f"  [AUTO-EXECUTE] {action_type} (requires_confirmation)")
            exec_result = ai_service.execute_action(actions[0], user)
            if exec_result:
                # Merge execution result
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

        # When query_result exists, the pipeline already executed the query.
        # suggested_actions will be empty — that's expected behavior.
        query_resolved = query_result is not None or len(message) > 20

        label = f"[{group_name}/{case_name}]"
        logger.info(f"  action_type={action_type!r}, resolved={query_resolved}")
        logger.info(f"  message={message[:120]}")
        if query_result:
            rows = query_result.get("rows", [])
            logger.info(f"  query_result: {len(rows)} rows, type={query_result.get('display_type')}")

        # --- Assertions (flexible for LLM variance) ---

        # 0. Basic: query must produce a message or query_result
        assert message or query_result, (
            f"{label} no message and no query_result. Full result: {result}"
        )

        # 1. action_type check — only when actions exist
        #    When query was already resolved, actions are empty (expected)
        #    Always tolerate semantic_query / view as valid query variants
        if "action_type_in" in expect and action_type:
            allowed = expect["action_type_in"]
            is_ok = (
                action_type in allowed
                or action_type.startswith("query_")
                or action_type in ("view", "semantic_query")
            )
            assert is_ok, (
                f"{label} action_type={action_type!r} not in {allowed} "
                f"and not a query variant."
            )

        # 2. message must contain at least one of the keywords
        if "message_contains" in expect:
            keywords = expect["message_contains"]
            found = any(kw in message for kw in keywords)
            assert found, (
                f"{label} message should contain one of {keywords}, "
                f"got: {message[:200]}"
            )

        # 3. message must NOT contain error keywords
        if "message_not_contains" in expect:
            for kw in expect["message_not_contains"]:
                assert kw not in message, (
                    f"{label} message should not contain '{kw}', "
                    f"got: {message[:200]}"
                )

        # 4. Should have query_result structure
        if expect.get("has_query_result"):
            assert query_resolved, (
                f"{label} expected query_result or meaningful message, "
                f"got neither. Full result: {result}"
            )

        # 5. Minimum rows in query_result
        if "min_rows" in expect and query_result:
            rows = query_result.get("rows", [])
            assert len(rows) >= expect["min_rows"], (
                f"{label} expected >= {expect['min_rows']} rows, "
                f"got {len(rows)}"
            )

        # 6. columns_contain
        if "columns_contain" in expect and query_result:
            columns = query_result.get("columns", [])
            column_keys = query_result.get("column_keys", [])
            all_cols = set(columns + column_keys)
            for col in expect["columns_contain"]:
                assert col in all_cols, (
                    f"{label} expected column '{col}' in {all_cols}"
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
