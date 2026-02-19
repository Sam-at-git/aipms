"""
Benchmark 执行引擎
逐条执行测试用例，验证 L2/L3/L4/Query/Exec 断言
使用 benchmark_assertions 共享断言引擎
"""
import importlib.util
import json
import logging
import os
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.benchmark import (
    BenchmarkCase, BenchmarkCaseResult, BenchmarkRun, BenchmarkSuite,
)
from app.hotel.models.ontology import Employee
from app.services.benchmark_assertions import (
    evaluate_l2_action,
    evaluate_l3_db,
    evaluate_l4_response,
    evaluate_query_result,
    evaluate_exec_result,
    evaluate_all,
)

logger = logging.getLogger(__name__)

# Query actions that return results directly, no need to call execute_action
QUERY_ACTIONS = {"ontology_query", "query_smart", "view", "semantic_query", "query_reports"}


def _is_query_action(action_type: str) -> bool:
    """Check if the action is a query (no DB mutation)."""
    return action_type in QUERY_ACTIONS or action_type.startswith("query_")


def _resolve_placeholders(input_text: str) -> str:
    """Replace date placeholders like $today, $tomorrow, etc."""
    today = date.today()
    replacements = {
        "$today": today.isoformat(),
        "$tomorrow": (today + timedelta(days=1)).isoformat(),
        "$day_after_tomorrow": (today + timedelta(days=2)).isoformat(),
        "$yesterday": (today - timedelta(days=1)).isoformat(),
    }
    result = input_text
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result


BENCHMARK_INIT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "benchmark_init")


def list_init_scripts() -> List[str]:
    """List available init scripts from the benchmark_init/ directory."""
    scripts = []
    if os.path.isdir(BENCHMARK_INIT_DIR):
        for f in sorted(os.listdir(BENCHMARK_INIT_DIR)):
            if f.endswith(".py") and f != "__init__.py":
                scripts.append(f)
    return scripts


def run_single_suite(
    suite: BenchmarkSuite,
    db: Session,
    user: Employee,
) -> BenchmarkRun:
    """Execute all cases in a single suite.

    1. Initialize data based on init_script setting
    2. Create/update BenchmarkRun
    3. For each case: call AI, verify assertions, record result
    4. Return the BenchmarkRun with results
    """
    from init_data import reset_business_data
    from app.hotel.services.ai_service import AIService

    # Step 1: Initialize data based on init_script
    init_script = (suite.init_script or "").strip()

    if init_script.lower() == "none":
        logger.info(f"Suite '{suite.name}': skipping DB init (init_script=none)")
    else:
        reset_business_data(db)

        if init_script and init_script.lower() != "none":
            script_path = os.path.join(BENCHMARK_INIT_DIR, init_script)
            if os.path.isfile(script_path):
                import importlib.util
                spec = importlib.util.spec_from_file_location("benchmark_init_script", script_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "run"):
                    module.run(db)
                    logger.info(f"Suite '{suite.name}': executed init script '{init_script}'")
                else:
                    logger.warning(f"Init script '{init_script}' has no run(db) function, skipped")
            else:
                logger.warning(f"Init script '{init_script}' not found in {BENCHMARK_INIT_DIR}, using default")

    # Step 3: Create or replace BenchmarkRun
    existing_run = db.query(BenchmarkRun).filter_by(suite_id=suite.id).first()
    if existing_run:
        db.query(BenchmarkCaseResult).filter_by(run_id=existing_run.id).delete()
        db.delete(existing_run)
        db.commit()

    run = BenchmarkRun(
        suite_id=suite.id,
        status="running",
        total_cases=len(suite.cases),
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Step 4: Execute each case
    passed_count = 0
    failed_count = 0
    error_count = 0
    conversation_history = []

    for case in suite.cases:
        case_result = _execute_case(case, run, db, user, conversation_history)
        db.add(case_result)
        db.commit()

        if case_result.status == "passed":
            passed_count += 1
        elif case_result.status == "failed":
            failed_count += 1
        else:
            error_count += 1

        conversation_history.append({"role": "user", "content": _resolve_placeholders(case.input)})
        if case_result.actual_response:
            conversation_history.append({"role": "assistant", "content": case_result.actual_response})

    # Step 5: Update run summary
    run.passed = passed_count
    run.failed = failed_count
    run.error_count = error_count
    run.status = "passed" if failed_count == 0 and error_count == 0 else "failed"
    run.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(run)

    return run


def _execute_case(
    case: BenchmarkCase,
    run: BenchmarkRun,
    db: Session,
    user: Employee,
    conversation_history: List[Dict],
) -> BenchmarkCaseResult:
    """Execute a single benchmark case using shared assertion engine."""
    from app.hotel.services.ai_service import AIService

    try:
        input_text = _resolve_placeholders(case.input)
        assertions = json.loads(case.assertions) if case.assertions else {}
        follow_up_fields = json.loads(case.follow_up_fields) if case.follow_up_fields else {}

        # Control flags
        is_setup = assertions.get("is_setup", False)
        skip_execute = assertions.get("skip_execute", False)
        expect_result = assertions.get("expect_result", {})

        # Resolve run_as user
        effective_user = user
        if case.run_as:
            run_as_user = db.query(Employee).filter(Employee.username == case.run_as).first()
            if run_as_user:
                effective_user = run_as_user
            else:
                logger.warning(f"run_as user '{case.run_as}' not found, using default user")

        # Call AI
        ai_service = AIService(db)
        result = ai_service.process_message(
            message=input_text,
            user=effective_user,
            conversation_history=list(conversation_history),
            topic_id=None,
            follow_up_context=None,
            language="zh",
        )

        response_message = result.get("message", "")
        debug_session_id = result.get("debug_session_id")
        exec_result_data = None
        action_dict = {}

        # Handle suggested_actions: resolve missing_fields, then execute
        suggested_actions = result.get("suggested_actions", [])
        if suggested_actions:
            action = suggested_actions[0]
            action_dict = action if isinstance(action, dict) else (action.dict() if hasattr(action, 'dict') else {})
            missing = action_dict.get("missing_fields", [])

            if missing and follow_up_fields:
                action_type = action_dict.get("action_type", "")
                existing_params = action_dict.get("params", {})
                collected = {**existing_params, **follow_up_fields}

                result = ai_service.process_message(
                    message=input_text,
                    user=effective_user,
                    conversation_history=list(conversation_history),
                    topic_id=None,
                    follow_up_context={
                        "action_type": action_type,
                        "collected_fields": collected,
                    },
                    language="zh",
                )
                response_message = result.get("message", "")
                debug_session_id = result.get("debug_session_id") or debug_session_id

                suggested_actions = result.get("suggested_actions", [])
                if suggested_actions:
                    action_dict = suggested_actions[0]
                    if not isinstance(action_dict, dict):
                        action_dict = action_dict.dict() if hasattr(action_dict, 'dict') else {}

            # Execute mutation actions (skip query actions unless skip_execute)
            action_type = action_dict.get("action_type", "")
            should_execute = (
                not skip_execute
                and not _is_query_action(action_type)
                and not action_dict.get("missing_fields")
            )

            if should_execute:
                if action_type == "checkout":
                    action_dict.get("params", {}).setdefault("allow_unsettled", True)
                    action_dict.get("params", {}).setdefault("unsettled_reason", "benchmark test")

                exec_result_data = ai_service.execute_action(action_dict, effective_user)

                # For expected failure scenarios, keep the error message
                if expect_result and expect_result.get("success") is False:
                    response_message = exec_result_data.get("message", response_message)
                elif exec_result_data.get("success"):
                    response_message = exec_result_data.get("message", response_message)
                else:
                    response_message = f"[执行失败] {exec_result_data.get('message', '')}"
                db.flush()

        # --- Run all assertions via shared engine ---
        all_results = evaluate_all(
            action=action_dict if action_dict else None,
            ai_result=result,
            exec_result=exec_result_data,
            assertions=assertions,
            db=db,
        )

        all_passed = all_results["all_passed"]

        # For setup cases, always pass (setup failures are logged but don't fail)
        if is_setup:
            all_passed = True

        assertion_details = {
            "l2_action": all_results["l2_results"],
            "verify_db": all_results["l3_results"],
            "response": all_results["l4_results"],
            "query": all_results["query_results"],
            "exec_result": all_results["exec_results"],
        }

        return BenchmarkCaseResult(
            run_id=run.id,
            case_id=case.id,
            status="passed" if all_passed else "failed",
            debug_session_id=debug_session_id,
            actual_response=response_message,
            assertion_details=json.dumps(assertion_details, ensure_ascii=False),
            executed_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.exception(f"Error executing benchmark case {case.id}: {e}")
        return BenchmarkCaseResult(
            run_id=run.id,
            case_id=case.id,
            status="error",
            error_message=str(e),
            executed_at=datetime.utcnow(),
        )


def run_suites(
    suite_ids: List[int],
    db: Session,
    user: Employee,
) -> List[BenchmarkRun]:
    """Execute multiple suites sequentially."""
    runs = []
    for suite_id in suite_ids:
        suite = db.query(BenchmarkSuite).filter_by(id=suite_id).first()
        if not suite:
            logger.warning(f"Suite {suite_id} not found, skipping")
            continue
        run = run_single_suite(suite, db, user)
        runs.append(run)
    return runs
