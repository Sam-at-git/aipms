"""
Tests for app/services/benchmark_runner.py

Covers:
- _is_query_action
- _resolve_placeholders
- list_init_scripts
- run_single_suite
- _execute_case
- run_suites
"""
import json
import os
import pytest
from datetime import date, timedelta, datetime
from unittest.mock import patch, MagicMock, PropertyMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.benchmark import BenchmarkSuite, BenchmarkCase, BenchmarkRun, BenchmarkCaseResult
from app.hotel.models.ontology import Employee, EmployeeRole
from app.security.auth import get_password_hash


# ============== Utility function tests ==============


class TestIsQueryAction:
    def test_known_query_actions(self):
        from app.services.benchmark_runner import _is_query_action
        assert _is_query_action("ontology_query") is True
        assert _is_query_action("query_smart") is True
        assert _is_query_action("view") is True
        assert _is_query_action("semantic_query") is True
        assert _is_query_action("query_reports") is True

    def test_query_prefix(self):
        from app.services.benchmark_runner import _is_query_action
        assert _is_query_action("query_custom") is True
        assert _is_query_action("query_") is True

    def test_non_query_actions(self):
        from app.services.benchmark_runner import _is_query_action
        assert _is_query_action("checkin") is False
        assert _is_query_action("checkout") is False
        assert _is_query_action("create_reservation") is False
        assert _is_query_action("walkin_checkin") is False


class TestResolvePlaceholders:
    def test_today(self):
        from app.services.benchmark_runner import _resolve_placeholders
        today = date.today().isoformat()
        assert _resolve_placeholders("check in $today") == f"check in {today}"

    def test_tomorrow(self):
        from app.services.benchmark_runner import _resolve_placeholders
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        assert _resolve_placeholders("arrive $tomorrow") == f"arrive {tomorrow}"

    def test_day_after_tomorrow(self):
        from app.services.benchmark_runner import _resolve_placeholders
        dat = (date.today() + timedelta(days=2)).isoformat()
        assert _resolve_placeholders("leave $day_after_tomorrow") == f"leave {dat}"

    def test_yesterday(self):
        from app.services.benchmark_runner import _resolve_placeholders
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        assert _resolve_placeholders("from $yesterday") == f"from {yesterday}"

    def test_no_placeholders(self):
        from app.services.benchmark_runner import _resolve_placeholders
        assert _resolve_placeholders("no placeholders here") == "no placeholders here"

    def test_multiple_placeholders(self):
        from app.services.benchmark_runner import _resolve_placeholders
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        result = _resolve_placeholders("from $today to $tomorrow")
        assert result == f"from {today} to {tomorrow}"


class TestListInitScripts:
    def test_returns_list(self):
        from app.services.benchmark_runner import list_init_scripts
        result = list_init_scripts()
        assert isinstance(result, list)

    @patch("app.services.benchmark_runner.os.path.isdir")
    @patch("app.services.benchmark_runner.os.listdir")
    def test_filters_python_files(self, mock_listdir, mock_isdir):
        mock_isdir.return_value = True
        mock_listdir.return_value = ["init_a.py", "init_b.py", "__init__.py", "readme.md"]
        from app.services.benchmark_runner import list_init_scripts
        result = list_init_scripts()
        assert "init_a.py" in result
        assert "init_b.py" in result
        assert "__init__.py" not in result
        assert "readme.md" not in result

    @patch("app.services.benchmark_runner.os.path.isdir")
    def test_no_directory(self, mock_isdir):
        mock_isdir.return_value = False
        from app.services.benchmark_runner import list_init_scripts
        result = list_init_scripts()
        assert result == []


# ============== Integration-like tests with mocked AI ==============


@pytest.fixture
def bench_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def bench_session(bench_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=bench_engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def bench_user(bench_session):
    user = Employee(
        username="manager",
        password_hash=get_password_hash("123456"),
        name="Manager",
        role=EmployeeRole.MANAGER,
        is_active=True
    )
    bench_session.add(user)
    bench_session.commit()
    bench_session.refresh(user)
    return user


@pytest.fixture
def bench_suite(bench_session):
    suite = BenchmarkSuite(
        name="Test Suite",
        category="basic",
        description="A test benchmark suite",
        init_script="none",
    )
    bench_session.add(suite)
    bench_session.commit()
    bench_session.refresh(suite)
    return suite


def _make_case(bench_session, suite, name, input_text, assertions_dict, seq=1, follow_up=None, run_as=None):
    case = BenchmarkCase(
        suite_id=suite.id,
        sequence_order=seq,
        name=name,
        input=input_text,
        assertions=json.dumps(assertions_dict),
        follow_up_fields=json.dumps(follow_up) if follow_up else None,
        run_as=run_as,
    )
    bench_session.add(case)
    bench_session.commit()
    bench_session.refresh(case)
    return case


class TestRunSingleSuite:
    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_basic_query_case_passes(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        # Add a simple query case
        _make_case(bench_session, bench_suite, "Query rooms", "查看房态", {
            "expect_action": {"action_type": "ontology_query"},
        })

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {
            "message": "房态查询结果",
            "suggested_actions": [
                {"action_type": "ontology_query", "params": {"entity": "Room"}}
            ],
            "debug_session_id": "sess-1",
        }

        run = run_single_suite(bench_suite, bench_session, bench_user)
        assert run.status == "passed"
        assert run.total_cases == 1
        assert run.passed == 1

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_case_with_failed_assertion(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        _make_case(bench_session, bench_suite, "Wrong action", "入住", {
            "expect_action": {"action_type": "walkin_checkin"},
        })

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {
            "message": "OK",
            "suggested_actions": [
                {"action_type": "ontology_query", "params": {}}
            ],
        }

        run = run_single_suite(bench_suite, bench_session, bench_user)
        assert run.status == "failed"
        assert run.failed == 1

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_case_with_exception(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        _make_case(bench_session, bench_suite, "Error case", "crash", {})

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.side_effect = Exception("Unexpected error")

        run = run_single_suite(bench_suite, bench_session, bench_user)
        assert run.error_count == 1

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_setup_case_always_passes(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        _make_case(bench_session, bench_suite, "Setup", "setup data", {
            "is_setup": True,
            "expect_action": {"action_type": "walkin_checkin"},  # This assertion would fail
        })

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {
            "message": "OK",
            "suggested_actions": [
                {"action_type": "ontology_query", "params": {}}
            ],
        }

        run = run_single_suite(bench_suite, bench_session, bench_user)
        assert run.passed == 1  # Setup case always passes

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_mutation_action_executed(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        _make_case(bench_session, bench_suite, "Checkin", "办理散客入住", {
            "expect_action": {"action_type": "walkin_checkin"},
        })

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {
            "message": "办理入住",
            "suggested_actions": [
                {"action_type": "walkin_checkin", "params": {"guest_name": "Test", "room_number": "101"}}
            ],
        }
        mock_ai.execute_action.return_value = {
            "success": True,
            "message": "入住成功"
        }

        run = run_single_suite(bench_suite, bench_session, bench_user)
        mock_ai.execute_action.assert_called_once()

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_skip_execute_flag(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        _make_case(bench_session, bench_suite, "Skip exec", "do something", {
            "skip_execute": True,
            "expect_action": {"action_type": "walkin_checkin"},
        })

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {
            "message": "OK",
            "suggested_actions": [
                {"action_type": "walkin_checkin", "params": {}}
            ],
        }

        run = run_single_suite(bench_suite, bench_session, bench_user)
        mock_ai.execute_action.assert_not_called()

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_follow_up_fields(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        _make_case(bench_session, bench_suite, "With followup", "create reservation", {
            "expect_action": {"action_type": "create_reservation"},
        }, follow_up={"room_type_id": 1})

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai

        # First call returns missing fields
        mock_ai.process_message.side_effect = [
            {
                "message": "Need more info",
                "suggested_actions": [{
                    "action_type": "create_reservation",
                    "params": {"guest_name": "Zhang"},
                    "missing_fields": [{"field_name": "room_type_id"}]
                }],
            },
            {
                "message": "Created",
                "suggested_actions": [{
                    "action_type": "create_reservation",
                    "params": {"guest_name": "Zhang", "room_type_id": 1},
                }],
            }
        ]
        mock_ai.execute_action.return_value = {"success": True, "message": "Created"}

        run = run_single_suite(bench_suite, bench_session, bench_user)
        assert mock_ai.process_message.call_count == 2

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_run_as_user(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        # Create another user
        front1 = Employee(
            username="front1",
            password_hash=get_password_hash("123456"),
            name="Front Desk",
            role=EmployeeRole.RECEPTIONIST,
            is_active=True
        )
        bench_session.add(front1)
        bench_session.commit()

        _make_case(bench_session, bench_suite, "As front1", "hello", {}, run_as="front1")

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {
            "message": "OK",
            "suggested_actions": [],
        }

        run = run_single_suite(bench_suite, bench_session, bench_user)
        assert run.passed == 1

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_run_as_unknown_user(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        _make_case(bench_session, bench_suite, "Unknown user", "hello", {}, run_as="nonexistent")

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {
            "message": "OK",
            "suggested_actions": [],
        }

        run = run_single_suite(bench_suite, bench_session, bench_user)
        assert run.passed == 1

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_checkout_adds_defaults(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        _make_case(bench_session, bench_suite, "Checkout", "退房", {
            "expect_action": {"action_type": "checkout"},
        })

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {
            "message": "退房",
            "suggested_actions": [{
                "action_type": "checkout",
                "params": {"room_number": "101"},
            }],
        }
        mock_ai.execute_action.return_value = {"success": True, "message": "退房成功"}

        run = run_single_suite(bench_suite, bench_session, bench_user)
        call_args = mock_ai.execute_action.call_args[0][0]
        assert call_args["params"].get("allow_unsettled") is True

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_expect_result_failure(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        _make_case(bench_session, bench_suite, "Expect fail", "do impossible", {
            "expect_action": {"action_type": "walkin_checkin"},
            "expect_result": {"success": False},
        })

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {
            "message": "OK",
            "suggested_actions": [{
                "action_type": "walkin_checkin",
                "params": {},
            }],
        }
        mock_ai.execute_action.return_value = {
            "success": False,
            "message": "Room not available"
        }

        run = run_single_suite(bench_suite, bench_session, bench_user)
        # The exec_result assertion should pass since we expected failure
        results = bench_session.query(BenchmarkCaseResult).filter_by(run_id=run.id).all()
        assert len(results) == 1

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_exec_failure_message(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        _make_case(bench_session, bench_suite, "Exec fail", "do thing", {
            "expect_action": {"action_type": "create_guest"},
        })

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {
            "message": "OK",
            "suggested_actions": [{
                "action_type": "create_guest",
                "params": {"name": "test"},
            }],
        }
        mock_ai.execute_action.return_value = {
            "success": False,
            "message": "Validation failed"
        }

        run = run_single_suite(bench_suite, bench_session, bench_user)
        results = bench_session.query(BenchmarkCaseResult).filter_by(run_id=run.id).all()
        assert "执行失败" in (results[0].actual_response or "")

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_existing_run_replaced(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        _make_case(bench_session, bench_suite, "Test", "hello", {})

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {
            "message": "OK", "suggested_actions": [],
        }

        # Run twice
        run1 = run_single_suite(bench_suite, bench_session, bench_user)
        run2 = run_single_suite(bench_suite, bench_session, bench_user)

        runs = bench_session.query(BenchmarkRun).filter_by(suite_id=bench_suite.id).all()
        assert len(runs) == 1
        assert runs[0].id == run2.id


class TestRunSuites:
    @patch("app.services.benchmark_runner.run_single_suite")
    def test_runs_multiple(self, mock_run_single, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_suites

        mock_run = MagicMock()
        mock_run_single.return_value = mock_run

        runs = run_suites([bench_suite.id], bench_session, bench_user)
        assert len(runs) == 1
        mock_run_single.assert_called_once()

    @patch("app.services.benchmark_runner.run_single_suite")
    def test_skips_nonexistent_suite(self, mock_run_single, bench_session, bench_user):
        from app.services.benchmark_runner import run_suites

        runs = run_suites([9999], bench_session, bench_user)
        assert len(runs) == 0
        mock_run_single.assert_not_called()

    @patch("app.services.benchmark_runner.run_single_suite")
    def test_mixed_existing_and_nonexistent(self, mock_run_single, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_suites

        mock_run = MagicMock()
        mock_run_single.return_value = mock_run

        runs = run_suites([bench_suite.id, 9999], bench_session, bench_user)
        assert len(runs) == 1


class TestInitScriptExecution:
    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_init_script_none_skips_reset(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        bench_suite.init_script = "none"
        bench_session.commit()

        _make_case(bench_session, bench_suite, "Test", "hello", {})

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {"message": "OK", "suggested_actions": []}

        run_single_suite(bench_suite, bench_session, bench_user)
        mock_reset.assert_not_called()

    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_init_script_empty_runs_default(self, mock_reset, mock_ai_cls, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        bench_suite.init_script = ""
        bench_session.commit()

        _make_case(bench_session, bench_suite, "Test", "hello", {})

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {"message": "OK", "suggested_actions": []}

        run_single_suite(bench_suite, bench_session, bench_user)
        mock_reset.assert_called_once()

    @patch("app.services.benchmark_runner.os.path.isfile")
    @patch("app.hotel.services.ai_service.AIService")
    @patch("init_data.reset_business_data")
    def test_init_script_not_found(self, mock_reset, mock_ai_cls, mock_isfile, bench_session, bench_user, bench_suite):
        from app.services.benchmark_runner import run_single_suite

        bench_suite.init_script = "nonexistent.py"
        bench_session.commit()
        mock_isfile.return_value = False

        _make_case(bench_session, bench_suite, "Test", "hello", {})

        mock_ai = MagicMock()
        mock_ai_cls.return_value = mock_ai
        mock_ai.process_message.return_value = {"message": "OK", "suggested_actions": []}

        run_single_suite(bench_suite, bench_session, bench_user)
        mock_reset.assert_called_once()
