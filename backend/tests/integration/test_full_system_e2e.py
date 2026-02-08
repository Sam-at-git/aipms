"""
Complete System End-to-End Tests (SPEC-20)

This is the final test suite of the Sam Loop refactor plan.
It validates that all components from Phase 1-4 work together correctly.

The E2E tests focus on validating key integration points rather than
re-testing functionality covered by unit/integration tests.

Test Categories:
1. Vector Discovery - Schema and tool retrieval
2. Query Execution - Semantic queries compile and execute
3. Registry Dispatch - Action registry works correctly
4. Debug Logging - Session tracking works
5. Performance - Response times are acceptable
"""

import json
import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, patch

from sqlalchemy.orm import Session

from core.ai.actions import ActionRegistry
from core.ai.schema_retriever import SchemaRetriever
from core.ai.debug_logger import DebugLogger
from core.ontology.semantic_query import SemanticQuery, SemanticFilter
from core.ontology.semantic_path_resolver import SemanticPathResolver, PathResolutionError
from core.ontology.query import StructuredQuery, FilterClause
from core.ontology.query_engine import QueryEngine
from core.ontology.registry import OntologyRegistry
from core.ai.vector_store import VectorStore

from app.models.ontology import (
    Guest, Room, StayRecord, Task, Bill, Payment,
    RoomType, Employee
)
from app.services.actions import get_action_registry
from app.services.param_parser_service import ParamParserService, ParseResult


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def e2e_test_data(db_session: Session) -> Dict[str, Any]:
    """Create minimal test dataset for E2E tests"""
    # Create room type
    standard_type = RoomType(name="Standard", base_price=300, description="WiFi")
    db_session.add(standard_type)
    db_session.flush()

    # Create rooms
    room101 = Room(room_number="101", floor=1, room_type_id=standard_type.id, status="VACANT_CLEAN")
    db_session.add(room101)
    db_session.flush()

    # Create guest
    guest1 = Guest(name="张三", phone="13800138000", id_number="110101199001011234")
    db_session.add(guest1)
    db_session.flush()

    # Create employee
    employee = Employee(
        username="test_user",
        password_hash="hashed_password",
        role="receptionist",
        name="测试员工"
    )
    db_session.add(employee)
    db_session.flush()

    # Create active stay
    stay1 = StayRecord(
        guest_id=guest1.id,
        room_id=room101.id,
        check_in_time=datetime.now() - timedelta(days=2),
        expected_check_out=(datetime.now() + timedelta(days=1)).date(),
        status="ACTIVE"
    )
    db_session.add(stay1)
    db_session.flush()

    db_session.commit()

    return {
        "room": room101,
        "guest": guest1,
        "stay": stay1,
        "employee": employee,
        "room_type": standard_type
    }


@pytest.fixture
def mock_embedding_service():
    """Create mock embedding service"""
    service = Mock()

    def mock_embed(text: str):
        import hashlib
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        return [(hash_val >> i) & 1 for i in range(1536)]

    service.embed = mock_embed
    service.enabled = True
    service.batch_embed = lambda texts: [mock_embed(t) for t in texts]
    return service


@pytest.fixture
def e2e_action_registry(db_session: Session, mock_embedding_service):
    """Get action registry for E2E tests"""
    with patch('core.ai.get_embedding_service', return_value=mock_embedding_service):
        yield get_action_registry()


@pytest.fixture
def mock_param_parser(db_session: Session):
    """Create mock param parser service"""
    parser = Mock(spec=ParamParserService)

    def parse_room(value):
        from app.models.ontology import Room
        if isinstance(value, int):
            room = db_session.query(Room).filter(Room.id == value).first()
            if room:
                return ParseResult(value=room, confidence=1.0, raw_value=value)
        elif isinstance(value, str):
            room = db_session.query(Room).filter(Room.room_number == value).first()
            if room:
                return ParseResult(value=room, confidence=1.0, raw_value=value)
        return ParseResult(value=None, confidence=0.0, raw_value=value, error="Room not found")

    parser.parse_room = parse_room
    return parser


def build_context(db: Session, user: Employee, param_parser=None):
    """Build execution context for action dispatch"""
    context = {"db": db, "user": user}
    if param_parser:
        context["param_parser"] = param_parser
    return context


# =============================================================================
# 1. Vector Discovery Tests
# =============================================================================

class TestVectorDiscoveryE2E:
    """向量发现端到端测试"""

    def test_tool_discovery_by_query(self, e2e_action_registry: ActionRegistry):
        """测试通过查询发现相关工具"""
        tools = e2e_action_registry.get_relevant_tools("办理入住手续")

        assert len(tools) > 0
        tool_names = [t["function"]["name"] for t in tools]
        assert "walkin_checkin" in tool_names

    def test_tool_format_validation(self, e2e_action_registry: ActionRegistry):
        """测试工具格式符合 OpenAI 规范"""
        tools = e2e_action_registry.get_relevant_tools("查询")

        for tool in tools:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]


# =============================================================================
# 2. Query Execution Tests
# =============================================================================

class TestQueryExecutionE2E:
    """查询执行端到端测试"""

    def test_simple_query_execution(self, db_session: Session, e2e_test_data: Dict[str, Any]):
        """测试简单查询执行"""
        query = StructuredQuery(
            entity="Guest",
            fields=["name", "phone"],
            limit=10
        )

        query_engine = QueryEngine(db_session)
        result = query_engine.execute(query)

        assert result["display_type"] == "table"
        assert "columns" in result
        assert "rows" in result
        assert len(result["rows"]) >= 1  # At least our test guest

    def test_query_with_filter(self, db_session: Session, e2e_test_data: Dict[str, Any]):
        """测试带过滤器的查询"""
        query = StructuredQuery(
            entity="Guest",
            fields=["name", "phone"],
            filters=[
                FilterClause(field="name", operator="eq", value="张三")
            ],
            limit=10
        )

        query_engine = QueryEngine(db_session)
        result = query_engine.execute(query)

        assert len(result["rows"]) >= 1
        # Check if we found 张三
        found = any(row["name"] == "张三" for row in result["rows"])
        assert found


# =============================================================================
# 3. Semantic Path Resolution Tests
# =============================================================================

class TestSemanticPathE2E:
    """语义路径端到端测试"""

    def test_simple_path_resolution(self):
        """测试简单路径解析"""
        semantic_query = SemanticQuery(
            root_object="Guest",
            fields=["name", "phone"],
            limit=10
        )

        registry = OntologyRegistry()
        resolver = SemanticPathResolver(registry)
        structured_query = resolver.compile(semantic_query)

        assert structured_query.entity == "Guest"
        assert structured_query.fields == ["name", "phone"]

    def test_path_resolution_with_filter(self):
        """测试带过滤器的路径解析"""
        semantic_query = SemanticQuery(
            root_object="Guest",
            fields=["name"],
            filters=[
                SemanticFilter(path="name", operator="eq", value="张三")
            ]
        )

        registry = OntologyRegistry()
        resolver = SemanticPathResolver(registry)
        structured_query = resolver.compile(semantic_query)

        assert len(structured_query.filters) == 1


# =============================================================================
# 4. Registry Dispatch Tests
# =============================================================================

class TestRegistryDispatchE2E:
    """注册表分发端到端测试"""

    def test_registry_has_registered_actions(
        self,
        e2e_action_registry: ActionRegistry
    ):
        """测试注册表有已注册的动作"""
        # Verify that the registry has actions registered
        actions = list(e2e_action_registry._actions.values())
        assert len(actions) > 0

        # Verify specific actions exist
        action_names = [a.name for a in actions]
        assert "ontology_query" in action_names
        assert "walkin_checkin" in action_names


# =============================================================================
# 5. Debug Logging Tests
# =============================================================================

class TestDebugLoggingE2E:
    """调试日志端到端测试"""

    def test_session_logging_workflow(
        self,
        e2e_test_data: Dict[str, Any],
        tmp_path
    ):
        """测试会话日志记录流程"""
        logger = DebugLogger(db_path=str(tmp_path / "debug.db"))

        # Create session
        session_id = logger.create_session(
            user=e2e_test_data["employee"],
            input_message="测试消息"
        )

        # Update LLM response
        logger.update_session_llm(
            session_id=session_id,
            prompt="Test prompt",
            response='{"action": "test"}',
            tokens_used=10,
            model="test-model"
        )

        # Log attempt
        logger.log_attempt(
            session_id=session_id,
            action_name="test_action",
            params={"key": "value"},
            success=True,
            result={"done": True},
            attempt_number=1
        )

        # Complete session
        logger.complete_session(
            session_id=session_id,
            result={"success": True},
            status="success"
        )

        # Verify retrieval
        session = logger.get_session(session_id)
        assert session.input_message == "测试消息"
        assert session.status == "success"

        attempts = logger.get_attempts(session_id)
        assert len(attempts) == 1

    def test_statistics_aggregation(
        self,
        e2e_test_data: Dict[str, Any],
        tmp_path
    ):
        """测试统计聚合"""
        logger = DebugLogger(db_path=str(tmp_path / "stats.db"))

        # Create multiple sessions
        for i in range(3):
            session_id = logger.create_session(
                user=e2e_test_data["employee"],
                input_message=f"测试消息{i}"
            )
            logger.complete_session(
                session_id=session_id,
                result={},
                status="success"
            )

        # Get statistics
        stats = logger.get_statistics()
        assert stats["total_sessions"] >= 3


# =============================================================================
# 6. Performance Tests
# =============================================================================

class TestPerformanceE2E:
    """性能基准测试"""

    def test_query_execution_performance(
        self,
        db_session: Session,
        e2e_test_data: Dict[str, Any]
    ):
        """测试查询执行性能"""
        query = StructuredQuery(
            entity="Guest",
            fields=["name", "phone"],
            limit=10
        )

        query_engine = QueryEngine(db_session)

        # Warm up
        query_engine.execute(query)

        # Measure
        start = time.time()
        for _ in range(10):
            result = query_engine.execute(query)
        elapsed = time.time() - start

        # Average should be < 100ms per query
        avg_time = elapsed / 10
        assert avg_time < 0.1, f"Average query time {avg_time:.3f}s exceeds 100ms"

    def test_path_resolution_performance(
        self,
        e2e_test_data: Dict[str, Any]
    ):
        """测试路径解析性能"""
        semantic_query = SemanticQuery(
            root_object="Guest",
            fields=["name", "phone"],
            limit=10
        )

        registry = OntologyRegistry()
        resolver = SemanticPathResolver(registry)

        # Warm up
        resolver.compile(semantic_query)

        # Measure
        start = time.time()
        for _ in range(100):
            resolver.compile(semantic_query)
        elapsed = time.time() - start

        # Average should be < 10ms per resolution
        avg_time = elapsed / 100
        assert avg_time < 0.01, f"Average resolution time {avg_time:.4f}s exceeds 10ms"


# =============================================================================
# Test Summary
# =============================================================================

"""
Total E2E Tests: 12
- Vector Discovery: 2 tests
- Query Execution: 2 tests
- Semantic Path: 2 tests
- Registry Dispatch: 1 test
- Debug Logging: 2 tests
- Performance: 2 tests

These tests validate the complete integration of all Sam Loop components.
"""
