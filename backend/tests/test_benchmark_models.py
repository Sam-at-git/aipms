"""
Tests for benchmark models and reset_business_data functionality.
"""
import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.benchmark import (
    BenchmarkSuite, BenchmarkCase, BenchmarkRun, BenchmarkCaseResult
)
from app.hotel.models.ontology import Room, RoomType, Guest, Employee, RoomStatus


@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db(db_engine):
    Session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = Session()
    yield session
    session.close()


# ---- Model CRUD Tests ----

class TestBenchmarkSuite:
    def test_create_suite(self, db):
        suite = BenchmarkSuite(
            name="散客入住流程",
            category="入住",
            description="测试散客直接入住的完整流程",
        )
        db.add(suite)
        db.commit()
        db.refresh(suite)

        assert suite.id is not None
        assert suite.name == "散客入住流程"
        assert suite.category == "入住"
        assert suite.created_at is not None
        assert suite.updated_at is not None

    def test_suite_with_init_script(self, db):
        suite = BenchmarkSuite(
            name="自定义重置",
            category="高级",
            init_script="init_with_guests.py",
        )
        db.add(suite)
        db.commit()
        db.refresh(suite)

        assert suite.init_script == "init_with_guests.py"


class TestBenchmarkCase:
    def test_create_case(self, db):
        suite = BenchmarkSuite(name="Test Suite", category="test")
        db.add(suite)
        db.commit()

        case = BenchmarkCase(
            suite_id=suite.id,
            sequence_order=1,
            name="单人入住标间",
            input="帮张三办理201房间的入住",
            assertions=json.dumps({
                "verify_db": [
                    {
                        "description": "201房间变为占用",
                        "sql": "SELECT status FROM rooms WHERE room_number = '201'",
                        "expect": {"rows": 1, "values": {"status": "OCCUPIED"}},
                    }
                ],
                "response_contains": ["入住", "201"],
            }),
            follow_up_fields=json.dumps({"guest_name": "张三", "room_number": "201"}),
        )
        db.add(case)
        db.commit()
        db.refresh(case)

        assert case.id is not None
        assert case.suite_id == suite.id
        assert case.sequence_order == 1
        assertions = json.loads(case.assertions)
        assert len(assertions["verify_db"]) == 1

    def test_case_ordering_via_relationship(self, db):
        suite = BenchmarkSuite(name="Ordered", category="test")
        db.add(suite)
        db.commit()

        for i in [3, 1, 2]:
            db.add(BenchmarkCase(
                suite_id=suite.id,
                sequence_order=i,
                name=f"Case {i}",
                input=f"Input {i}",
                assertions="{}",
            ))
        db.commit()

        db.refresh(suite)
        orders = [c.sequence_order for c in suite.cases]
        assert orders == [1, 2, 3]


class TestBenchmarkRun:
    def test_create_run(self, db):
        suite = BenchmarkSuite(name="Run Suite", category="test")
        db.add(suite)
        db.commit()

        run = BenchmarkRun(
            suite_id=suite.id,
            status="running",
            total_cases=5,
            started_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        assert run.id is not None
        assert run.status == "running"
        assert run.total_cases == 5
        assert run.passed == 0
        assert run.failed == 0

    def test_unique_suite_constraint(self, db):
        suite = BenchmarkSuite(name="Unique", category="test")
        db.add(suite)
        db.commit()

        run1 = BenchmarkRun(
            suite_id=suite.id, status="passed",
            total_cases=3, passed=3,
            started_at=datetime.utcnow(),
        )
        db.add(run1)
        db.commit()

        # Adding a second run for the same suite should fail
        run2 = BenchmarkRun(
            suite_id=suite.id, status="failed",
            total_cases=3, failed=1,
            started_at=datetime.utcnow(),
        )
        db.add(run2)
        with pytest.raises(Exception):  # IntegrityError
            db.commit()
        db.rollback()


class TestBenchmarkCaseResult:
    def test_create_case_result(self, db):
        suite = BenchmarkSuite(name="Result Suite", category="test")
        db.add(suite)
        db.commit()

        case = BenchmarkCase(
            suite_id=suite.id, sequence_order=1,
            name="Test Case", input="test input", assertions="{}",
        )
        db.add(case)

        run = BenchmarkRun(
            suite_id=suite.id, status="running",
            total_cases=1, started_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()

        result = BenchmarkCaseResult(
            run_id=run.id,
            case_id=case.id,
            status="passed",
            debug_session_id="sess-abc-123",
            actual_response="入住成功！张三已入住201房间。",
            assertion_details=json.dumps({"verify_db": [{"passed": True}]}),
            executed_at=datetime.utcnow(),
        )
        db.add(result)
        db.commit()
        db.refresh(result)

        assert result.id is not None
        assert result.status == "passed"
        assert result.debug_session_id == "sess-abc-123"


# ---- Cascade Delete Tests ----

class TestCascadeDeletes:
    def test_delete_suite_cascades_to_cases(self, db):
        suite = BenchmarkSuite(name="Cascade", category="test")
        db.add(suite)
        db.commit()

        for i in range(3):
            db.add(BenchmarkCase(
                suite_id=suite.id, sequence_order=i + 1,
                name=f"Case {i}", input=f"Input {i}", assertions="{}",
            ))
        db.commit()

        assert db.query(BenchmarkCase).filter_by(suite_id=suite.id).count() == 3

        db.delete(suite)
        db.commit()

        assert db.query(BenchmarkCase).count() == 0

    def test_delete_suite_cascades_to_runs_and_results(self, db):
        suite = BenchmarkSuite(name="Full Cascade", category="test")
        db.add(suite)
        db.commit()

        case = BenchmarkCase(
            suite_id=suite.id, sequence_order=1,
            name="Case", input="input", assertions="{}",
        )
        db.add(case)

        run = BenchmarkRun(
            suite_id=suite.id, status="passed",
            total_cases=1, passed=1,
            started_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()

        result = BenchmarkCaseResult(
            run_id=run.id, case_id=case.id,
            status="passed", executed_at=datetime.utcnow(),
        )
        db.add(result)
        db.commit()

        db.delete(suite)
        db.commit()

        assert db.query(BenchmarkRun).count() == 0
        assert db.query(BenchmarkCaseResult).count() == 0
        assert db.query(BenchmarkCase).count() == 0


# ---- reset_business_data Tests ----

class TestResetBusinessData:
    def test_reset_clears_and_reseeds(self, db):
        from init_data import init_business_data, reset_business_data

        # Seed initial data
        init_business_data(db)

        assert db.query(RoomType).count() == 3
        assert db.query(Room).count() == 40

        # Add a guest (business data that should be cleared)
        guest = Guest(name="测试客人", phone="13900000000", id_type="身份证", id_number="123456")
        db.add(guest)
        db.commit()
        assert db.query(Guest).count() == 1

        # Reset
        reset_business_data(db)

        # Business data re-seeded
        assert db.query(RoomType).count() == 3
        assert db.query(Room).count() == 40
        # Guest cleared
        assert db.query(Guest).count() == 0

    def test_reset_preserves_benchmark_data(self, db):
        from init_data import init_business_data, reset_business_data

        init_business_data(db)

        # Add benchmark data
        suite = BenchmarkSuite(name="Preserved", category="test")
        db.add(suite)
        db.commit()

        reset_business_data(db)

        # Benchmark data still exists
        assert db.query(BenchmarkSuite).count() == 1
        assert db.query(BenchmarkSuite).first().name == "Preserved"
