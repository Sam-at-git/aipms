"""
tests/services/actions/test_room_actions.py

Tests for room and room type action handlers.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
from sqlalchemy.orm import Session

import app.services.actions.room_actions as room_actions
from app.services.actions.base import (
    UpdateRoomStatusParams, CreateRoomTypeParams, UpdateRoomTypeParams,
)
from app.models.ontology import Employee, EmployeeRole, Room, RoomStatus, RoomType


@pytest.fixture
def mock_db():
    return Mock(spec=Session)


@pytest.fixture
def mock_user():
    user = Mock(spec=Employee)
    user.id = 1
    user.username = "manager"
    user.role = EmployeeRole.MANAGER
    return user


@pytest.fixture
def sample_room():
    room = Mock(spec=Room)
    room.id = 1
    room.room_number = "101"
    room.status = RoomStatus.VACANT_DIRTY
    return room


@pytest.fixture
def sample_room_type():
    rt = Mock(spec=RoomType)
    rt.id = 1
    rt.name = "标准间"
    rt.base_price = Decimal("300.00")
    return rt


class TestRegisterRoomActions:
    def test_registers_all_actions(self):
        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        room_actions.register_room_actions(registry)

        assert registry.get_action("update_room_status") is not None
        assert registry.get_action("mark_room_clean") is not None
        assert registry.get_action("mark_room_dirty") is not None
        assert registry.get_action("create_room_type") is not None
        assert registry.get_action("update_room_type") is not None

    def test_action_metadata(self):
        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        room_actions.register_room_actions(registry)

        action = registry.get_action("update_room_status")
        assert action.entity == "Room"
        assert action.category == "mutation"

        action = registry.get_action("create_room_type")
        assert action.entity == "RoomType"


class TestHandleUpdateRoomStatus:
    def test_successful_status_update(self, mock_db, mock_user, sample_room):
        from core.ai.actions import ActionRegistry

        sample_room.status = RoomStatus.VACANT_CLEAN
        mock_db.query.return_value.filter.return_value.first.return_value = sample_room
        mock_service = MagicMock()
        mock_service.update_room_status.return_value = sample_room

        params = UpdateRoomStatusParams(room_number="101", status="vacant_clean")

        with patch('app.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("update_room_status")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True

    def test_room_not_found(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = UpdateRoomStatusParams(room_number="999", status="vacant_clean")

        registry = ActionRegistry()
        room_actions.register_room_actions(registry)
        action = registry.get_action("update_room_status")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_invalid_status(self, mock_db, mock_user, sample_room):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = sample_room

        params = UpdateRoomStatusParams(room_number="101", status="invalid_status")

        registry = ActionRegistry()
        room_actions.register_room_actions(registry)
        action = registry.get_action("update_room_status")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "validation_error"

    def test_occupied_room_error(self, mock_db, mock_user, sample_room):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = sample_room
        mock_service = MagicMock()
        mock_service.update_room_status.side_effect = ValueError("入住中的房间不能手动更改状态")

        params = UpdateRoomStatusParams(room_number="101", status="vacant_clean")

        with patch('app.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("update_room_status")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "business_error"


class TestHandleMarkRoomClean:
    def test_successful_mark_clean(self, mock_db, mock_user, sample_room):
        from core.ai.actions import ActionRegistry

        sample_room.status = RoomStatus.VACANT_CLEAN
        mock_db.query.return_value.filter.return_value.first.return_value = sample_room
        mock_service = MagicMock()
        mock_service.update_room_status.return_value = sample_room

        params = UpdateRoomStatusParams(room_number="101", status="vacant_clean")

        with patch('app.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("mark_room_clean")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True
        assert "已标记为已清洁" in result["message"]


class TestHandleMarkRoomDirty:
    def test_successful_mark_dirty(self, mock_db, mock_user, sample_room):
        from core.ai.actions import ActionRegistry

        sample_room.status = RoomStatus.VACANT_DIRTY
        mock_db.query.return_value.filter.return_value.first.return_value = sample_room
        mock_service = MagicMock()
        mock_service.update_room_status.return_value = sample_room

        params = UpdateRoomStatusParams(room_number="101", status="vacant_dirty")

        with patch('app.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("mark_room_dirty")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True
        assert "已标记为待清洁" in result["message"]


class TestHandleCreateRoomType:
    def test_successful_create(self, mock_db, mock_user, sample_room_type):
        from core.ai.actions import ActionRegistry

        mock_service = MagicMock()
        mock_service.create_room_type.return_value = sample_room_type

        params = CreateRoomTypeParams(name="标准间", base_price="300")

        with patch('app.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("create_room_type")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True
        assert result["name"] == "标准间"

    def test_duplicate_name_error(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        mock_service = MagicMock()
        mock_service.create_room_type.side_effect = ValueError("房型名称已存在")

        params = CreateRoomTypeParams(name="标准间", base_price="300")

        with patch('app.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("create_room_type")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "business_error"


class TestHandleUpdateRoomType:
    def test_successful_update_by_id(self, mock_db, mock_user, sample_room_type):
        from core.ai.actions import ActionRegistry

        mock_service = MagicMock()
        mock_service.update_room_type.return_value = sample_room_type

        params = UpdateRoomTypeParams(room_type_id=1, base_price="350")

        with patch('app.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("update_room_type")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True

    def test_update_by_name(self, mock_db, mock_user, sample_room_type):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = sample_room_type
        mock_service = MagicMock()
        mock_service.update_room_type.return_value = sample_room_type

        params = UpdateRoomTypeParams(room_type_name="标准间", base_price="350")

        with patch('app.services.room_service.RoomService', return_value=mock_service):
            registry = ActionRegistry()
            room_actions.register_room_actions(registry)
            action = registry.get_action("update_room_type")
            result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is True

    def test_update_missing_identifier(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        params = UpdateRoomTypeParams(base_price="350")

        registry = ActionRegistry()
        room_actions.register_room_actions(registry)
        action = registry.get_action("update_room_type")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "missing_identifier"

    def test_update_no_fields(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        params = UpdateRoomTypeParams(room_type_id=1)

        registry = ActionRegistry()
        room_actions.register_room_actions(registry)
        action = registry.get_action("update_room_type")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "no_updates"

    def test_update_name_not_found(self, mock_db, mock_user):
        from core.ai.actions import ActionRegistry

        mock_db.query.return_value.filter.return_value.first.return_value = None

        params = UpdateRoomTypeParams(room_type_name="不存在的房型", base_price="350")

        registry = ActionRegistry()
        room_actions.register_room_actions(registry)
        action = registry.get_action("update_room_type")
        result = action.handler(params=params, db=mock_db, user=mock_user)

        assert result["success"] is False
        assert result["error"] == "not_found"


class TestRoomActionsModule:
    def test_module_all(self):
        assert "register_room_actions" in room_actions.__all__
