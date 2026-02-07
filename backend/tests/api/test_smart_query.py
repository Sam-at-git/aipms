"""Tests for _execute_smart_query()"""
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


class TestExecuteSmartQuery:
    def test_query_rooms(self, ai_service, manager_user, setup_rooms):
        result = ai_service._execute_smart_query("room", "list", {}, manager_user)
        assert "query_result" in result
        assert result["query_result"]["display_type"] == "table"
        assert len(result["query_result"]["rows"]) >= 1
        assert result["query_result"]["rows"][0]["room_number"] == "101"

    def test_query_tasks(self, ai_service, manager_user):
        result = ai_service._execute_smart_query("task", "list", {}, manager_user)
        assert "query_result" in result
        assert result["query_result"]["display_type"] == "table"

    def test_query_reports(self, ai_service, manager_user, setup_rooms):
        result = ai_service._execute_smart_query("report", "summary", {}, manager_user)
        assert "query_result" in result
        assert result["query_result"]["display_type"] == "chart"

    def test_unknown_entity(self, ai_service, manager_user):
        result = ai_service._execute_smart_query("unknown_entity", "list", {}, manager_user)
        assert "不支持" in result["message"]

    def test_query_guests(self, ai_service, manager_user):
        result = ai_service._execute_smart_query("客人", "list", {}, manager_user)
        assert "query_result" in result
        assert result["query_result"]["display_type"] == "table"

    def test_query_reservations(self, ai_service, manager_user, setup_rooms):
        result = ai_service._execute_smart_query("reservation", "list", {}, manager_user)
        assert "query_result" in result
        assert result["query_result"]["display_type"] == "table"
