"""
Tests for app/services/benchmark_assertions.py

Covers:
- evaluate_l2_action: action_type exact/pattern/in match, params_contain
- evaluate_l3_db: SQL-based DB state verification
- evaluate_l4_response: response_contains, response_not_contains,
  message_contains, message_not_contains
- evaluate_query_result: expect_query_result, has_query_result, min_rows, columns_contain
- evaluate_exec_result: success check, error_message_contain
- evaluate_all: aggregate all assertions
"""
import pytest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base


@pytest.fixture
def mem_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mem_session(mem_engine):
    Session = sessionmaker(bind=mem_engine)
    session = Session()
    yield session
    session.close()


# ============== evaluate_l2_action ==============


class TestEvaluateL2Action:
    def test_no_expect_action(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action({"action_type": "checkin"}, {})
        assert results == []

    def test_action_type_exact_match(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "checkin"},
            {"expect_action": {"action_type": "checkin"}}
        )
        assert len(results) == 1
        assert results[0]["passed"] is True
        assert results[0]["type"] == "l2_action_type"

    def test_action_type_exact_mismatch(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "checkout"},
            {"expect_action": {"action_type": "checkin"}}
        )
        assert results[0]["passed"] is False

    def test_action_type_pattern_match(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "ontology_query"},
            {"expect_action": {"action_type_pattern": r"ontology_.*"}}
        )
        assert len(results) == 1
        assert results[0]["passed"] is True
        assert results[0]["type"] == "l2_action_type_pattern"

    def test_action_type_pattern_no_match(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "checkin"},
            {"expect_action": {"action_type_pattern": r"ontology_.*"}}
        )
        assert results[0]["passed"] is False

    def test_action_type_in_match(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "checkin"},
            {"expect_action": {"action_type_in": ["checkin", "walkin_checkin"]}}
        )
        assert results[0]["passed"] is True

    def test_action_type_in_query_variant_tolerated(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "query_reports"},
            {"expect_action": {"action_type_in": ["ontology_query"]}}
        )
        assert results[0]["passed"] is True  # query_ prefix tolerated

    def test_action_type_in_semantic_query_tolerated(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "semantic_query"},
            {"expect_action": {"action_type_in": ["ontology_query"]}}
        )
        assert results[0]["passed"] is True

    def test_action_type_in_view_tolerated(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "view"},
            {"expect_action": {"action_type_in": ["ontology_query"]}}
        )
        assert results[0]["passed"] is True

    def test_action_type_in_no_match(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "create_guest"},
            {"expect_action": {"action_type_in": ["checkin", "checkout"]}}
        )
        assert results[0]["passed"] is False

    def test_params_contain_match(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "checkin", "params": {"room_number": "101", "guest_name": "Zhang"}},
            {"expect_action": {"params_contain": {"room_number": "101"}}}
        )
        assert len(results) == 1
        assert results[0]["passed"] is True
        assert results[0]["type"] == "l2_params_contain"

    def test_params_contain_mismatch(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "checkin", "params": {"room_number": "102"}},
            {"expect_action": {"params_contain": {"room_number": "101"}}}
        )
        assert results[0]["passed"] is False

    def test_params_contain_missing_key(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "checkin", "params": {}},
            {"expect_action": {"params_contain": {"room_number": "101"}}}
        )
        assert results[0]["passed"] is False
        assert results[0]["actual"] is None

    def test_params_contain_no_params(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "checkin"},
            {"expect_action": {"params_contain": {"room_number": "101"}}}
        )
        assert results[0]["passed"] is False

    def test_combined_assertions(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {"action_type": "checkin", "params": {"room_number": "101"}},
            {"expect_action": {
                "action_type": "checkin",
                "params_contain": {"room_number": "101"}
            }}
        )
        assert len(results) == 2
        assert all(r["passed"] for r in results)

    def test_empty_action(self):
        from app.services.benchmark_assertions import evaluate_l2_action
        results = evaluate_l2_action(
            {},
            {"expect_action": {"action_type": "checkin"}}
        )
        assert results[0]["passed"] is False
        assert results[0]["actual"] == ""


# ============== evaluate_l3_db ==============


class TestEvaluateL3Db:
    def test_no_verify_db(self, mem_session):
        from app.services.benchmark_assertions import evaluate_l3_db
        results = evaluate_l3_db(mem_session, {})
        assert results == []

    def test_row_count_match(self, mem_session):
        from app.services.benchmark_assertions import evaluate_l3_db
        # Create a table and insert data
        mem_session.execute(text("CREATE TABLE test_t (id INTEGER PRIMARY KEY, name TEXT)"))
        mem_session.execute(text("INSERT INTO test_t VALUES (1, 'Alice')"))
        mem_session.execute(text("INSERT INTO test_t VALUES (2, 'Bob')"))
        mem_session.commit()

        results = evaluate_l3_db(mem_session, {
            "verify_db": [{
                "sql": "SELECT * FROM test_t",
                "expect": {"rows": 2},
                "description": "Two rows"
            }]
        })
        assert len(results) == 1
        assert results[0]["passed"] is True

    def test_row_count_mismatch(self, mem_session):
        from app.services.benchmark_assertions import evaluate_l3_db
        mem_session.execute(text("CREATE TABLE test_t2 (id INTEGER PRIMARY KEY)"))
        mem_session.execute(text("INSERT INTO test_t2 VALUES (1)"))
        mem_session.commit()

        results = evaluate_l3_db(mem_session, {
            "verify_db": [{
                "sql": "SELECT * FROM test_t2",
                "expect": {"rows": 5},
            }]
        })
        assert results[0]["passed"] is False

    def test_value_match(self, mem_session):
        from app.services.benchmark_assertions import evaluate_l3_db
        mem_session.execute(text("CREATE TABLE test_t3 (id INTEGER PRIMARY KEY, name TEXT)"))
        mem_session.execute(text("INSERT INTO test_t3 VALUES (1, 'Alice')"))
        mem_session.commit()

        results = evaluate_l3_db(mem_session, {
            "verify_db": [{
                "sql": "SELECT * FROM test_t3 WHERE id = 1",
                "expect": {"values": {"name": "Alice"}},
            }]
        })
        assert results[0]["passed"] is True

    def test_value_case_insensitive(self, mem_session):
        from app.services.benchmark_assertions import evaluate_l3_db
        mem_session.execute(text("CREATE TABLE test_ci (id INTEGER PRIMARY KEY, status TEXT)"))
        mem_session.execute(text("INSERT INTO test_ci VALUES (1, 'ACTIVE')"))
        mem_session.commit()

        results = evaluate_l3_db(mem_session, {
            "verify_db": [{
                "sql": "SELECT * FROM test_ci WHERE id = 1",
                "expect": {"values": {"status": "active"}},
            }]
        })
        assert results[0]["passed"] is True

    def test_value_mismatch(self, mem_session):
        from app.services.benchmark_assertions import evaluate_l3_db
        mem_session.execute(text("CREATE TABLE test_t4 (id INTEGER PRIMARY KEY, name TEXT)"))
        mem_session.execute(text("INSERT INTO test_t4 VALUES (1, 'Alice')"))
        mem_session.commit()

        results = evaluate_l3_db(mem_session, {
            "verify_db": [{
                "sql": "SELECT * FROM test_t4 WHERE id = 1",
                "expect": {"values": {"name": "Bob"}},
            }]
        })
        assert results[0]["passed"] is False

    def test_values_with_no_rows(self, mem_session):
        from app.services.benchmark_assertions import evaluate_l3_db
        mem_session.execute(text("CREATE TABLE test_empty (id INTEGER PRIMARY KEY, name TEXT)"))
        mem_session.commit()

        results = evaluate_l3_db(mem_session, {
            "verify_db": [{
                "sql": "SELECT * FROM test_empty WHERE id = 999",
                "expect": {"values": {"name": "Alice"}},
            }]
        })
        assert results[0]["passed"] is False

    def test_sql_error(self, mem_session):
        from app.services.benchmark_assertions import evaluate_l3_db
        results = evaluate_l3_db(mem_session, {
            "verify_db": [{
                "sql": "SELECT * FROM nonexistent_table_xyz",
                "expect": {"rows": 0},
            }]
        })
        assert results[0]["passed"] is False
        assert "error" in results[0]["actual"]

    def test_values_as_list_skipped(self, mem_session):
        from app.services.benchmark_assertions import evaluate_l3_db
        mem_session.execute(text("CREATE TABLE test_t5 (id INTEGER PRIMARY KEY)"))
        mem_session.execute(text("INSERT INTO test_t5 VALUES (1)"))
        mem_session.commit()

        results = evaluate_l3_db(mem_session, {
            "verify_db": [{
                "sql": "SELECT * FROM test_t5",
                "expect": {"rows": 1, "values": ["ignored"]},
            }]
        })
        assert results[0]["passed"] is True  # values as list is ignored

    def test_description_defaults_to_sql(self, mem_session):
        from app.services.benchmark_assertions import evaluate_l3_db
        mem_session.execute(text("CREATE TABLE test_t6 (id INTEGER PRIMARY KEY)"))
        mem_session.commit()

        results = evaluate_l3_db(mem_session, {
            "verify_db": [{
                "sql": "SELECT * FROM test_t6",
                "expect": {"rows": 0},
            }]
        })
        assert "SELECT" in results[0]["description"]

    def test_non_string_value_comparison(self, mem_session):
        from app.services.benchmark_assertions import evaluate_l3_db
        mem_session.execute(text("CREATE TABLE test_num (id INTEGER PRIMARY KEY, count INTEGER)"))
        mem_session.execute(text("INSERT INTO test_num VALUES (1, 42)"))
        mem_session.commit()

        results = evaluate_l3_db(mem_session, {
            "verify_db": [{
                "sql": "SELECT * FROM test_num WHERE id = 1",
                "expect": {"values": {"count": 42}},
            }]
        })
        assert results[0]["passed"] is True


# ============== evaluate_l4_response ==============


class TestEvaluateL4Response:
    def test_response_contains_found(self):
        from app.services.benchmark_assertions import evaluate_l4_response
        results = evaluate_l4_response("Hello World", {
            "response_contains": ["Hello"]
        })
        assert len(results) == 1
        assert results[0]["passed"] is True

    def test_response_contains_not_found(self):
        from app.services.benchmark_assertions import evaluate_l4_response
        results = evaluate_l4_response("Hello World", {
            "response_contains": ["Goodbye"]
        })
        assert results[0]["passed"] is False

    def test_response_contains_multiple(self):
        from app.services.benchmark_assertions import evaluate_l4_response
        results = evaluate_l4_response("Hello World", {
            "response_contains": ["Hello", "World"]
        })
        assert len(results) == 2
        assert all(r["passed"] for r in results)

    def test_response_not_contains_absent(self):
        from app.services.benchmark_assertions import evaluate_l4_response
        results = evaluate_l4_response("Hello World", {
            "response_not_contains": ["Error"]
        })
        assert results[0]["passed"] is True

    def test_response_not_contains_present(self):
        from app.services.benchmark_assertions import evaluate_l4_response
        results = evaluate_l4_response("Error occurred", {
            "response_not_contains": ["Error"]
        })
        assert results[0]["passed"] is False

    def test_message_contains_or_any_found(self):
        from app.services.benchmark_assertions import evaluate_l4_response
        results = evaluate_l4_response("Room 201 is available", {
            "message_contains": ["201", "404"]
        })
        assert len(results) == 1
        assert results[0]["passed"] is True

    def test_message_contains_or_none_found(self):
        from app.services.benchmark_assertions import evaluate_l4_response
        results = evaluate_l4_response("Hello World", {
            "message_contains": ["Foo", "Bar"]
        })
        assert results[0]["passed"] is False

    def test_message_not_contains_absent(self):
        from app.services.benchmark_assertions import evaluate_l4_response
        results = evaluate_l4_response("OK", {
            "message_not_contains": ["Error", "Failed"]
        })
        assert len(results) == 2
        assert all(r["passed"] for r in results)

    def test_message_not_contains_present(self):
        from app.services.benchmark_assertions import evaluate_l4_response
        results = evaluate_l4_response("Error occurred", {
            "message_not_contains": ["Error"]
        })
        assert results[0]["passed"] is False

    def test_empty_assertions(self):
        from app.services.benchmark_assertions import evaluate_l4_response
        results = evaluate_l4_response("Hello", {})
        assert results == []

    def test_empty_response_contains(self):
        from app.services.benchmark_assertions import evaluate_l4_response
        results = evaluate_l4_response("Hello", {"response_contains": []})
        assert results == []


# ============== evaluate_query_result ==============


class TestEvaluateQueryResult:
    def test_expect_query_result_with_query_result(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {"query_result": {"rows": [{"id": 1}]}, "message": "", "suggested_actions": []},
            {"expect_query_result": True}
        )
        assert len(results) == 1
        assert results[0]["passed"] is True

    def test_expect_query_result_with_message(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {"message": "Here are the results", "suggested_actions": []},
            {"expect_query_result": True}
        )
        assert results[0]["passed"] is True

    def test_expect_query_result_with_actions(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {"message": "", "suggested_actions": [{"action_type": "query"}]},
            {"expect_query_result": True}
        )
        assert results[0]["passed"] is True

    def test_expect_query_result_all_empty(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {"message": "", "suggested_actions": []},
            {"expect_query_result": True}
        )
        assert results[0]["passed"] is False

    def test_has_query_result_with_data(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {"query_result": {"rows": [1]}, "message": "", "suggested_actions": []},
            {"has_query_result": True}
        )
        assert results[0]["passed"] is True

    def test_has_query_result_with_long_message(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {"message": "A" * 25, "suggested_actions": []},
            {"has_query_result": True}
        )
        assert results[0]["passed"] is True

    def test_has_query_result_short_message(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {"message": "short", "suggested_actions": []},
            {"has_query_result": True}
        )
        assert results[0]["passed"] is False

    def test_min_rows_pass(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {"query_result": {"rows": [1, 2, 3]}, "message": "", "suggested_actions": []},
            {"min_rows": 2}
        )
        assert results[0]["passed"] is True

    def test_min_rows_fail(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {"query_result": {"rows": [1]}, "message": "", "suggested_actions": []},
            {"min_rows": 5}
        )
        assert results[0]["passed"] is False

    def test_min_rows_no_query_result(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {"message": "test", "suggested_actions": []},
            {"min_rows": 1}
        )
        assert len(results) == 0  # No assertion added when no query_result

    def test_columns_contain_pass(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {
                "query_result": {
                    "rows": [{"id": 1}],
                    "columns": ["id", "name"],
                    "column_keys": ["status"],
                },
                "message": "",
                "suggested_actions": [],
            },
            {"columns_contain": ["id", "status"]}
        )
        assert len(results) == 2
        assert all(r["passed"] for r in results)

    def test_columns_contain_fail(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {
                "query_result": {
                    "rows": [{"id": 1}],
                    "columns": ["id"],
                    "column_keys": [],
                },
                "message": "",
                "suggested_actions": [],
            },
            {"columns_contain": ["nonexistent"]}
        )
        assert results[0]["passed"] is False

    def test_no_assertions(self):
        from app.services.benchmark_assertions import evaluate_query_result
        results = evaluate_query_result(
            {"message": "test", "suggested_actions": []},
            {}
        )
        assert results == []


# ============== evaluate_exec_result ==============


class TestEvaluateExecResult:
    def test_no_expect_result(self):
        from app.services.benchmark_assertions import evaluate_exec_result
        results = evaluate_exec_result({"success": True}, {})
        assert results == []

    def test_success_true_match(self):
        from app.services.benchmark_assertions import evaluate_exec_result
        results = evaluate_exec_result(
            {"success": True},
            {"expect_result": {"success": True}}
        )
        assert results[0]["passed"] is True

    def test_success_false_match(self):
        from app.services.benchmark_assertions import evaluate_exec_result
        results = evaluate_exec_result(
            {"success": False},
            {"expect_result": {"success": False}}
        )
        assert results[0]["passed"] is True

    def test_success_mismatch(self):
        from app.services.benchmark_assertions import evaluate_exec_result
        results = evaluate_exec_result(
            {"success": True},
            {"expect_result": {"success": False}}
        )
        assert results[0]["passed"] is False

    def test_error_message_contain_found(self):
        from app.services.benchmark_assertions import evaluate_exec_result
        results = evaluate_exec_result(
            {"success": False, "message": "Room not found"},
            {"expect_result": {"error_message_contain": "not found"}}
        )
        assert results[0]["passed"] is True

    def test_error_message_contain_not_found(self):
        from app.services.benchmark_assertions import evaluate_exec_result
        results = evaluate_exec_result(
            {"success": False, "message": "Unknown error"},
            {"expect_result": {"error_message_contain": "not found"}}
        )
        assert results[0]["passed"] is False

    def test_error_message_in_data(self):
        from app.services.benchmark_assertions import evaluate_exec_result
        results = evaluate_exec_result(
            {"success": False, "message": "", "data": "Room is occupied"},
            {"expect_result": {"error_message_contain": "occupied"}}
        )
        assert results[0]["passed"] is True

    def test_combined_assertions(self):
        from app.services.benchmark_assertions import evaluate_exec_result
        results = evaluate_exec_result(
            {"success": False, "message": "Room not available"},
            {"expect_result": {"success": False, "error_message_contain": "not available"}}
        )
        assert len(results) == 2
        assert all(r["passed"] for r in results)


# ============== evaluate_all ==============


class TestEvaluateAll:
    def test_all_passed(self, mem_session):
        from app.services.benchmark_assertions import evaluate_all
        result = evaluate_all(
            action={"action_type": "checkin"},
            ai_result={"message": "OK", "suggested_actions": []},
            exec_result=None,
            assertions={"expect_action": {"action_type": "checkin"}},
            db=mem_session,
        )
        assert result["all_passed"] is True
        assert len(result["l2_results"]) == 1

    def test_some_failed(self, mem_session):
        from app.services.benchmark_assertions import evaluate_all
        result = evaluate_all(
            action={"action_type": "checkout"},
            ai_result={"message": "OK", "suggested_actions": []},
            exec_result=None,
            assertions={"expect_action": {"action_type": "checkin"}},
            db=mem_session,
        )
        assert result["all_passed"] is False

    def test_no_assertions_all_passed(self, mem_session):
        from app.services.benchmark_assertions import evaluate_all
        result = evaluate_all(
            action=None,
            ai_result={"message": "OK", "suggested_actions": []},
            exec_result=None,
            assertions={},
            db=mem_session,
        )
        assert result["all_passed"] is True

    def test_no_action_skips_l2(self, mem_session):
        from app.services.benchmark_assertions import evaluate_all
        result = evaluate_all(
            action=None,
            ai_result={"message": "OK", "suggested_actions": []},
            exec_result=None,
            assertions={"expect_action": {"action_type": "checkin"}},
            db=mem_session,
        )
        assert result["l2_results"] == []

    def test_no_db_skips_l3(self):
        from app.services.benchmark_assertions import evaluate_all
        result = evaluate_all(
            action=None,
            ai_result={"message": "OK", "suggested_actions": []},
            exec_result=None,
            assertions={"verify_db": [{"sql": "SELECT 1", "expect": {"rows": 1}}]},
            db=None,
        )
        assert result["l3_results"] == []

    def test_no_exec_skips_exec(self, mem_session):
        from app.services.benchmark_assertions import evaluate_all
        result = evaluate_all(
            action=None,
            ai_result={"message": "OK", "suggested_actions": []},
            exec_result=None,
            assertions={"expect_result": {"success": True}},
            db=mem_session,
        )
        assert result["exec_results"] == []

    def test_with_exec_result(self, mem_session):
        from app.services.benchmark_assertions import evaluate_all
        result = evaluate_all(
            action={"action_type": "checkin"},
            ai_result={"message": "OK", "suggested_actions": []},
            exec_result={"success": True, "message": "Done"},
            assertions={
                "expect_action": {"action_type": "checkin"},
                "expect_result": {"success": True},
            },
            db=mem_session,
        )
        assert result["all_passed"] is True
        assert len(result["exec_results"]) == 1
