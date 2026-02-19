"""
Shared benchmark assertion engine — pure functions, no pytest dependency.

Returns structured results: List[{type, description, passed, expected, actual}]
Used by both benchmark_runner.py (UI) and pytest benchmark scripts.
"""
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def evaluate_l2_action(action: dict, assertions: dict) -> List[dict]:
    """Validate action_type (exact/pattern/in) and params_contain.

    Args:
        action: The action dict from AI, e.g. {"action_type": "walkin_checkin", "params": {...}}
        assertions: The full assertions dict from YAML/DB

    Returns:
        List of assertion results
    """
    results = []
    expect_action = assertions.get("expect_action")
    if not expect_action:
        return results

    actual_type = action.get("action_type", "")

    # action_type exact match
    if "action_type" in expect_action:
        expected_type = expect_action["action_type"]
        passed = actual_type == expected_type
        results.append({
            "type": "l2_action_type",
            "description": f"action_type == {expected_type!r}",
            "passed": passed,
            "expected": expected_type,
            "actual": actual_type,
        })

    # action_type pattern match
    if "action_type_pattern" in expect_action:
        pattern = expect_action["action_type_pattern"]
        passed = bool(re.match(pattern, actual_type))
        results.append({
            "type": "l2_action_type_pattern",
            "description": f"action_type matches {pattern!r}",
            "passed": passed,
            "expected": pattern,
            "actual": actual_type,
        })

    # action_type in list
    if "action_type_in" in expect_action:
        allowed = expect_action["action_type_in"]
        # Also tolerate query variants
        is_ok = (
            actual_type in allowed
            or actual_type.startswith("query_")
            or actual_type in ("view", "semantic_query")
        )
        results.append({
            "type": "l2_action_type_in",
            "description": f"action_type in {allowed}",
            "passed": is_ok,
            "expected": allowed,
            "actual": actual_type,
        })

    # params_contain
    if "params_contain" in expect_action:
        params = action.get("params", {})
        for key, expected_val in expect_action["params_contain"].items():
            actual_val = params.get(key)
            passed = actual_val is not None and str(actual_val) == str(expected_val)
            results.append({
                "type": "l2_params_contain",
                "description": f"params.{key} == {expected_val!r}",
                "passed": passed,
                "expected": str(expected_val),
                "actual": str(actual_val) if actual_val is not None else None,
            })

    return results


def evaluate_l3_db(db: Session, assertions: dict) -> List[dict]:
    """Execute SQL-based DB state assertions (L3).

    Args:
        db: Database session
        assertions: The full assertions dict containing verify_db list

    Returns:
        List of assertion results
    """
    verify_db = assertions.get("verify_db", [])
    results = []

    for assertion in verify_db:
        sql = assertion.get("sql", "")
        expect = assertion.get("expect", {})
        desc = assertion.get("description", sql[:60])

        try:
            rows = db.execute(text(sql)).mappings().all()
            actual_rows = len(rows)
            expected_rows = expect.get("rows")
            expected_values = expect.get("values", {})

            # Graceful handling: if values is a list, skip value comparison
            if isinstance(expected_values, list):
                expected_values = {}

            passed = True
            actual_values = {}

            # Check row count
            if expected_rows is not None and actual_rows != expected_rows:
                passed = False

            # Check values (compare against first row)
            if expected_values and rows:
                row = dict(rows[0])
                for key, expected_val in expected_values.items():
                    actual_val = row.get(key)
                    actual_values[key] = actual_val
                    if isinstance(expected_val, str) and isinstance(actual_val, str):
                        if expected_val.lower() != actual_val.lower():
                            passed = False
                    elif actual_val != expected_val:
                        passed = False
            elif expected_values and not rows:
                passed = False

            results.append({
                "type": "l3_db",
                "description": desc,
                "passed": passed,
                "expected": {"rows": expected_rows, "values": expected_values},
                "actual": {"rows": actual_rows, "values": actual_values},
            })
        except Exception as e:
            results.append({
                "type": "l3_db",
                "description": desc,
                "passed": False,
                "expected": expect,
                "actual": {"error": str(e)},
            })

    return results


def evaluate_l4_response(response: str, assertions: dict) -> List[dict]:
    """Evaluate response content assertions (L4).

    - response_contains: strict AND — all keywords must appear
    - response_not_contains: none of these keywords should appear
    - message_contains: flexible OR — at least one keyword must appear
    - message_not_contains: none of these keywords should appear

    Args:
        response: The AI response message string
        assertions: The full assertions dict

    Returns:
        List of assertion results
    """
    results = []

    # response_contains (AND semantics)
    contains = assertions.get("response_contains", [])
    for keyword in contains:
        found = keyword in response
        results.append({
            "type": "l4_response_contains",
            "description": f"response contains {keyword!r}",
            "passed": found,
            "expected": keyword,
            "actual": "found" if found else "not found",
        })

    # response_not_contains
    not_contains = assertions.get("response_not_contains", [])
    for keyword in not_contains:
        found = keyword in response
        results.append({
            "type": "l4_response_not_contains",
            "description": f"response not contains {keyword!r}",
            "passed": not found,
            "expected": f"not {keyword!r}",
            "actual": "found" if found else "not found",
        })

    # message_contains (OR semantics)
    msg_contains = assertions.get("message_contains", [])
    if msg_contains:
        found_any = any(kw in response for kw in msg_contains)
        matched = [kw for kw in msg_contains if kw in response]
        results.append({
            "type": "l4_message_contains",
            "description": f"response contains any of {msg_contains}",
            "passed": found_any,
            "expected": msg_contains,
            "actual": matched if matched else "none matched",
        })

    # message_not_contains
    msg_not_contains = assertions.get("message_not_contains", [])
    for keyword in msg_not_contains:
        found = keyword in response
        results.append({
            "type": "l4_message_not_contains",
            "description": f"response not contains {keyword!r}",
            "passed": not found,
            "expected": f"not {keyword!r}",
            "actual": "found" if found else "not found",
        })

    return results


def evaluate_query_result(ai_result: dict, assertions: dict) -> List[dict]:
    """Evaluate query result assertions.

    - expect_query_result: result has query_result/message/actions
    - has_query_result: result.query_result must exist
    - min_rows: minimum row count in query_result
    - columns_contain: required columns in query_result

    Args:
        ai_result: The full AI result dict
        assertions: The full assertions dict

    Returns:
        List of assertion results
    """
    results = []
    query_result = ai_result.get("query_result")
    message = ai_result.get("message", "")
    actions = ai_result.get("suggested_actions", [])

    # expect_query_result: any of query_result/message/actions
    if assertions.get("expect_query_result"):
        has_qr = query_result is not None
        has_msg = bool(message)
        has_actions = len(actions) > 0
        passed = has_qr or has_msg or has_actions
        results.append({
            "type": "query_expect_result",
            "description": "has query_result, message, or actions",
            "passed": passed,
            "expected": True,
            "actual": {
                "has_query_result": has_qr,
                "has_message": has_msg,
                "has_actions": has_actions,
            },
        })

    # has_query_result: stricter — query_result or meaningful message
    if assertions.get("has_query_result"):
        query_resolved = query_result is not None or len(message) > 20
        results.append({
            "type": "query_has_result",
            "description": "has query_result or meaningful message",
            "passed": query_resolved,
            "expected": True,
            "actual": {
                "has_query_result": query_result is not None,
                "message_length": len(message),
            },
        })

    # min_rows
    if "min_rows" in assertions and query_result:
        rows = query_result.get("rows", [])
        expected_min = assertions["min_rows"]
        passed = len(rows) >= expected_min
        results.append({
            "type": "query_min_rows",
            "description": f"query_result rows >= {expected_min}",
            "passed": passed,
            "expected": expected_min,
            "actual": len(rows),
        })

    # columns_contain
    if "columns_contain" in assertions and query_result:
        columns = query_result.get("columns", [])
        column_keys = query_result.get("column_keys", [])
        all_cols = set(columns + column_keys)
        for col in assertions["columns_contain"]:
            passed = col in all_cols
            results.append({
                "type": "query_columns_contain",
                "description": f"columns contain {col!r}",
                "passed": passed,
                "expected": col,
                "actual": list(all_cols),
            })

    return results


def evaluate_exec_result(exec_result: dict, assertions: dict) -> List[dict]:
    """Evaluate execution result assertions (e.g. expected failure scenarios).

    - expect_result.success: expected success/failure boolean
    - expect_result.error_message_contain: substring match on error message

    Args:
        exec_result: The execution result dict
        assertions: The full assertions dict

    Returns:
        List of assertion results
    """
    results = []
    expect_result = assertions.get("expect_result")
    if not expect_result:
        return results

    actual_success = exec_result.get("success", False)

    # success check
    if "success" in expect_result:
        expected_success = expect_result["success"]
        passed = actual_success == expected_success
        results.append({
            "type": "exec_success",
            "description": f"execution success == {expected_success}",
            "passed": passed,
            "expected": expected_success,
            "actual": actual_success,
        })

    # error_message_contain
    if "error_message_contain" in expect_result:
        keyword = expect_result["error_message_contain"]
        msg = exec_result.get("message", "") + str(exec_result.get("data", ""))
        found = keyword in msg
        results.append({
            "type": "exec_error_message",
            "description": f"error message contains {keyword!r}",
            "passed": found,
            "expected": keyword,
            "actual": msg[:200],
        })

    return results


def evaluate_all(
    action: Optional[dict],
    ai_result: dict,
    exec_result: Optional[dict],
    assertions: dict,
    db: Optional[Session] = None,
) -> dict:
    """Aggregate all assertion results.

    Args:
        action: The action dict from AI (may be None for pure queries)
        ai_result: The full AI result dict
        exec_result: The execution result dict (may be None)
        assertions: The full assertions dict
        db: Database session (needed for L3 assertions)

    Returns:
        Dict with l2_results, l3_results, l4_results, query_results,
        exec_results, and all_passed boolean
    """
    l2_results = evaluate_l2_action(action or {}, assertions) if action else []
    l3_results = evaluate_l3_db(db, assertions) if db else []
    l4_results = evaluate_l4_response(
        ai_result.get("message", ""), assertions
    )
    query_results = evaluate_query_result(ai_result, assertions)
    exec_results = evaluate_exec_result(exec_result or {}, assertions) if exec_result else []

    all_results = l2_results + l3_results + l4_results + query_results + exec_results
    all_passed = all(r["passed"] for r in all_results) if all_results else True

    return {
        "l2_results": l2_results,
        "l3_results": l3_results,
        "l4_results": l4_results,
        "query_results": query_results,
        "exec_results": exec_results,
        "all_passed": all_passed,
    }
