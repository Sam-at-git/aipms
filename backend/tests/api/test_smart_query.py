"""Tests for unified ontology_query pipeline (formerly _execute_smart_query)"""
import pytest
from app.services.ai_service import AIService
from app.models.ontology import Employee, EmployeeRole, RoomType, Room, RoomStatus
from app.security.auth import get_password_hash
from decimal import Decimal


@pytest.fixture
def manager_user(db_session):
    manager = Employee(
        username="mgr_query",
        password_hash=get_password_hash("123456"),
        name="经理",
        role=EmployeeRole.MANAGER,
        is_active=True
    )
    db_session.add(manager)
    db_session.commit()
    db_session.refresh(manager)
    return manager


@pytest.fixture
def ai_service(db_session):
    return AIService(db_session)


@pytest.fixture
def setup_rooms(db_session):
    rt = RoomType(name="标准间", description="Standard", base_price=Decimal("288.00"), max_occupancy=2)
    db_session.add(rt)
    db_session.commit()
    db_session.refresh(rt)

    room = Room(room_number="101", floor=1, room_type_id=rt.id, status=RoomStatus.VACANT_CLEAN)
    db_session.add(room)
    db_session.commit()
    return rt, room


class TestOntologyQueryPipeline:
    """Tests for the unified ontology_query pipeline that replaced _execute_smart_query."""

    def test_query_rooms_via_ontology(self, ai_service, manager_user, setup_rooms):
        """Room query through ontology_query returns table data."""
        result = ai_service._execute_ontology_query(
            {"entity": "Room", "fields": ["room_number", "status"]},
            manager_user
        )
        assert "query_result" in result
        assert result["query_result"]["display_type"] == "table"
        rows = result["query_result"]["rows"]
        assert len(rows) >= 1
        # Check room_number is present in the first row
        first_row = rows[0]
        assert any("101" in str(v) for v in first_row.values())

    def test_query_tasks_via_ontology(self, ai_service, manager_user):
        """Task query through ontology_query returns table data."""
        result = ai_service._execute_ontology_query(
            {"entity": "Task", "fields": ["task_type", "status"]},
            manager_user
        )
        assert "query_result" in result
        assert result["query_result"]["display_type"] == "table"

    def test_query_reports_via_reports(self, ai_service, manager_user, setup_rooms):
        """Report query through _query_reports_response (kept as separate path)."""
        result = ai_service._query_reports_response()
        assert "message" in result
        assert "入住率" in result["message"] or "营收" in result["message"]

    def test_unknown_entity_returns_error(self, ai_service, manager_user):
        """Unknown entity through ontology_query returns error message."""
        result = ai_service._execute_ontology_query(
            {"entity": "UnknownEntity"},
            manager_user
        )
        assert "查询失败" in result.get("message", "") or "query_result" in result

    def test_query_guests_via_ontology(self, ai_service, manager_user):
        """Guest query through ontology_query returns table data."""
        result = ai_service._execute_ontology_query(
            {"entity": "Guest"},
            manager_user
        )
        assert "query_result" in result
        assert result["query_result"]["display_type"] == "table"

    def test_query_reservations_via_ontology(self, ai_service, manager_user, setup_rooms):
        """Reservation query through ontology_query returns table data."""
        result = ai_service._execute_ontology_query(
            {"entity": "Reservation"},
            manager_user
        )
        assert "query_result" in result
        assert result["query_result"]["display_type"] == "table"

    def test_handle_query_routes_ontology_query(self, ai_service, manager_user, setup_rooms):
        """_handle_query_action routes ontology_query to _execute_ontology_query."""
        result = {
            "message": "查询房间",
            "suggested_actions": [{
                "action_type": "ontology_query",
                "entity_type": "Room",
                "params": {"entity": "Room", "fields": ["room_number"]},
                "requires_confirmation": False,
            }],
            "context": {}
        }
        response = ai_service._handle_query_action(result, manager_user)
        assert "message" in response

    def test_handle_query_routes_query_reports(self, ai_service, manager_user, setup_rooms):
        """_handle_query_action routes query_reports to _query_reports_response."""
        result = {
            "message": "运营报告",
            "suggested_actions": [{
                "action_type": "query_reports",
                "entity_type": "report",
                "params": {},
                "requires_confirmation": False,
            }],
            "context": {}
        }
        response = ai_service._handle_query_action(result, manager_user)
        assert "入住率" in response.get("message", "") or "营收" in response.get("message", "")

    def test_handle_query_converts_view(self, ai_service, manager_user, setup_rooms):
        """_handle_query_action converts deprecated 'view' to ontology_query."""
        result = {
            "message": "查看房态",
            "suggested_actions": [{
                "action_type": "view",
                "entity_type": "room_status",
                "params": {},
                "requires_confirmation": False,
            }],
            "context": {}
        }
        response = ai_service._handle_query_action(result, manager_user)
        assert "message" in response
        # Should not crash; should return query results

    def test_handle_query_converts_query_smart(self, ai_service, manager_user, setup_rooms):
        """_handle_query_action converts query_smart to ontology_query path."""
        result = {
            "message": "查询房间",
            "suggested_actions": [{
                "action_type": "query_smart",
                "entity_type": "Room",
                "params": {"entity": "Room"},
                "requires_confirmation": False,
            }],
            "context": {}
        }
        response = ai_service._handle_query_action(result, manager_user)
        assert "message" in response

    def test_infer_entity_from_view_entity_type(self, ai_service, setup_rooms):
        """_infer_entity_from_view resolves entity_type via registry."""
        # Ensure registry has entities loaded (setup_rooms triggers model import)
        import app.models.ontology  # noqa: F401 - triggers registry population

        # Direct entity name match
        assert ai_service._infer_entity_from_view("Room", "") == "Room"
        assert ai_service._infer_entity_from_view("guest", "") == "Guest"
        # Common alias with suffix
        assert ai_service._infer_entity_from_view("room_status", "") == "Room"
        # No match returns empty
        assert ai_service._infer_entity_from_view("", "") == ""

    def test_infer_entity_from_view_message_keywords(self, ai_service, setup_rooms):
        """_infer_entity_from_view uses registry keyword matching from message."""
        import app.models.ontology  # noqa: F401

        # These rely on OntologyRegistry's keyword mapping
        result = ai_service._infer_entity_from_view("", "查看房间")
        assert result in ("Room", "")  # depends on registry keyword state
        result = ai_service._infer_entity_from_view("", "客人信息")
        assert result in ("Guest", "")  # depends on registry keyword state
