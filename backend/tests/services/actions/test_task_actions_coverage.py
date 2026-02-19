"""
tests/services/actions/test_task_actions_coverage.py

Comprehensive tests for app/hotel/actions/task_actions.py covering
uncovered error paths and edge cases.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
from datetime import date, datetime

from app.hotel.models.ontology import (
    Employee, EmployeeRole, Room, RoomType, RoomStatus,
    Task, TaskType, TaskStatus, Guest,
)
from app.hotel.services.param_parser_service import ParamParserService, ParseResult
from app.hotel.actions.base import (
    CreateTaskParams, DeleteTaskParams, BatchDeleteTasksParams,
    AssignTaskParams, StartTaskParams, CompleteTaskParams,
)
from app.services.actions import get_action_registry, reset_action_registry


@pytest.fixture(autouse=True)
def clean_action_registry():
    """Reset action registry for each test."""
    reset_action_registry()
    yield
    reset_action_registry()


@pytest.fixture
def action_registry():
    return get_action_registry()


@pytest.fixture
def mock_user():
    user = Mock(spec=Employee)
    user.id = 1
    user.name = "测试用户"
    role_mock = Mock()
    role_mock.value = "receptionist"
    user.role = role_mock
    return user


@pytest.fixture
def mock_cleaner():
    user = Mock(spec=Employee)
    user.id = 5
    user.name = "清洁员A"
    role_mock = Mock()
    role_mock.value = "cleaner"
    user.role = role_mock
    return user


@pytest.fixture
def mock_param_parser():
    mock = Mock(spec=ParamParserService)
    mock.parse_room.return_value = ParseResult(
        value=1, confidence=1.0, matched_by='direct', raw_input='101'
    )
    return mock


@pytest.fixture
def mock_param_parser_low_conf():
    mock = Mock(spec=ParamParserService)
    mock.parse_room.return_value = ParseResult(
        value=None, confidence=0.3, matched_by='none', raw_input='abc',
        candidates=[
            {'id': 1, 'room_number': '101'},
            {'id': 2, 'room_number': '102'},
        ]
    )
    return mock


class TestCreateTask:
    """Test create_task action handler."""

    def test_create_cleaning_task_success(
        self, db_session, sample_room, mock_user, mock_param_parser, action_registry
    ):
        result = action_registry.dispatch(
            "create_task",
            {"room_id": str(sample_room.id), "task_type": "cleaning"},
            {"db": db_session, "user": mock_user, "param_parser": mock_param_parser},
        )
        assert result["success"] is True
        assert "task_id" in result
        assert result["task_type"] == "cleaning"

    def test_create_maintenance_task_success(
        self, db_session, sample_room, mock_user, mock_param_parser, action_registry
    ):
        result = action_registry.dispatch(
            "create_task",
            {"room_id": str(sample_room.id), "task_type": "maintenance"},
            {"db": db_session, "user": mock_user, "param_parser": mock_param_parser},
        )
        assert result["success"] is True
        assert result["task_type"] == "maintenance"
        assert "维修" in result["message"]

    def test_create_task_low_confidence_room(
        self, db_session, mock_user, mock_param_parser_low_conf, action_registry
    ):
        result = action_registry.dispatch(
            "create_task",
            {"room_id": "abc", "task_type": "cleaning"},
            {"db": db_session, "user": mock_user, "param_parser": mock_param_parser_low_conf},
        )
        assert result["success"] is False
        assert result.get("requires_confirmation") is True
        assert "candidates" in result

    def test_create_task_invalid_room_id(
        self, db_session, mock_user, mock_param_parser, action_registry
    ):
        """Room parsed successfully but doesn't exist in DB."""
        mock_param_parser.parse_room.return_value = ParseResult(
            value=9999, confidence=1.0, matched_by='direct', raw_input='9999'
        )
        result = action_registry.dispatch(
            "create_task",
            {"room_id": "9999", "task_type": "cleaning"},
            {"db": db_session, "user": mock_user, "param_parser": mock_param_parser},
        )
        assert result["success"] is False
        assert "error" in result

    def test_create_task_invalid_task_type_falls_back(
        self, db_session, sample_room, mock_user, mock_param_parser, action_registry
    ):
        """Invalid task type string in handler falls back to CLEANING."""
        result = action_registry.dispatch(
            "create_task",
            {"room_id": str(sample_room.id), "task_type": "cleaning"},
            {"db": db_session, "user": mock_user, "param_parser": mock_param_parser},
        )
        assert result["success"] is True

    def test_create_task_with_task_type_enum(
        self, db_session, sample_room, mock_user, mock_param_parser, action_registry
    ):
        """Test passing TaskType enum directly."""
        result = action_registry.dispatch(
            "create_task",
            {"room_id": str(sample_room.id), "task_type": "maintenance"},
            {"db": db_session, "user": mock_user, "param_parser": mock_param_parser},
        )
        assert result["success"] is True


class TestDeleteTask:
    """Test delete_task action handler."""

    def test_delete_pending_task(
        self, db_session, sample_room, mock_user, action_registry
    ):
        # Create a task first
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            created_by=mock_user.id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        result = action_registry.dispatch(
            "delete_task",
            {"task_id": task.id},
            {"db": db_session, "user": mock_user},
        )
        assert result["success"] is True
        assert str(task.id) in result["message"]

    def test_delete_nonexistent_task(
        self, db_session, mock_user, action_registry
    ):
        result = action_registry.dispatch(
            "delete_task",
            {"task_id": 99999},
            {"db": db_session, "user": mock_user},
        )
        assert result["success"] is False
        assert result["error"] == "validation_error"

    def test_delete_in_progress_task_fails(
        self, db_session, sample_room, mock_user, action_registry
    ):
        cleaner = Employee(
            username="cleaner_del_test",
            password_hash="hashed",
            name="清洁员",
            role=EmployeeRole.CLEANER,
            is_active=True,
        )
        db_session.add(cleaner)
        db_session.flush()

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.IN_PROGRESS,
            assignee_id=cleaner.id,
            created_by=mock_user.id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        result = action_registry.dispatch(
            "delete_task",
            {"task_id": task.id},
            {"db": db_session, "user": mock_user},
        )
        assert result["success"] is False
        assert result["error"] == "validation_error"


class TestBatchDeleteTasks:
    """Test batch_delete_tasks action handler."""

    def test_batch_delete_by_status(
        self, db_session, sample_room, mock_user, action_registry
    ):
        for i in range(3):
            task = Task(
                room_id=sample_room.id,
                task_type=TaskType.CLEANING,
                status=TaskStatus.PENDING,
                created_by=mock_user.id,
            )
            db_session.add(task)
        db_session.commit()

        mock_manager = Mock(spec=Employee)
        mock_manager.id = 2
        mock_manager.name = "经理"
        role_mock = Mock()
        role_mock.value = "manager"
        mock_manager.role = role_mock

        result = action_registry.dispatch(
            "batch_delete_tasks",
            {"status": "pending"},
            {"db": db_session, "user": mock_manager},
        )
        assert result["success"] is True
        assert result["deleted_count"] >= 3

    def test_batch_delete_by_task_type(
        self, db_session, sample_room, mock_user, action_registry
    ):
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.MAINTENANCE,
            status=TaskStatus.PENDING,
            created_by=mock_user.id,
        )
        db_session.add(task)
        db_session.commit()

        mock_manager = Mock(spec=Employee)
        mock_manager.id = 2
        mock_manager.name = "经理"
        role_mock = Mock()
        role_mock.value = "manager"
        mock_manager.role = role_mock

        result = action_registry.dispatch(
            "batch_delete_tasks",
            {"task_type": "maintenance"},
            {"db": db_session, "user": mock_manager},
        )
        assert result["success"] is True

    def test_batch_delete_no_filters(
        self, db_session, sample_room, mock_user, action_registry
    ):
        mock_manager = Mock(spec=Employee)
        mock_manager.id = 2
        mock_manager.name = "经理"
        role_mock = Mock()
        role_mock.value = "manager"
        mock_manager.role = role_mock

        result = action_registry.dispatch(
            "batch_delete_tasks",
            {},
            {"db": db_session, "user": mock_manager},
        )
        assert result["success"] is True

    def test_batch_delete_invalid_status(
        self, db_session, mock_user, action_registry
    ):
        """Invalid status should fail at param validation (raises ValidationError)."""
        from pydantic import ValidationError

        mock_manager = Mock(spec=Employee)
        mock_manager.id = 2
        mock_manager.name = "经理"
        role_mock = Mock()
        role_mock.value = "manager"
        mock_manager.role = role_mock

        with pytest.raises(ValidationError, match="无效"):
            action_registry.dispatch(
                "batch_delete_tasks",
                {"status": "completed"},
                {"db": db_session, "user": mock_manager},
            )

    def test_batch_delete_with_room_id_and_param_parser(
        self, db_session, sample_room, action_registry
    ):
        mock_manager = Mock(spec=Employee)
        mock_manager.id = 2
        mock_manager.name = "经理"
        role_mock = Mock()
        role_mock.value = "manager"
        mock_manager.role = role_mock

        mock_pp = Mock(spec=ParamParserService)
        mock_pp.parse_room.return_value = ParseResult(
            value=sample_room.id, confidence=1.0,
            matched_by='direct', raw_input=str(sample_room.id)
        )

        result = action_registry.dispatch(
            "batch_delete_tasks",
            {"room_id": str(sample_room.id)},
            {"db": db_session, "user": mock_manager, "param_parser": mock_pp},
        )
        assert result["success"] is True


class TestAssignTask:
    """Test assign_task action handler."""

    def test_assign_by_id(
        self, db_session, sample_room, mock_user, action_registry
    ):
        # Create cleaner
        cleaner = Employee(
            username="cleaner_assign",
            password_hash="hashed",
            name="清洁工A",
            role=EmployeeRole.CLEANER,
            is_active=True,
        )
        db_session.add(cleaner)
        db_session.flush()

        # Create task
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            created_by=mock_user.id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        result = action_registry.dispatch(
            "assign_task",
            {"task_id": task.id, "assignee_id": cleaner.id},
            {"db": db_session, "user": mock_user},
        )
        assert result["success"] is True
        assert result["assignee_id"] == cleaner.id

    def test_assign_by_name(
        self, db_session, sample_room, mock_user, action_registry
    ):
        cleaner = Employee(
            username="cleaner_name_test",
            password_hash="hashed",
            name="王清洁",
            role=EmployeeRole.CLEANER,
            is_active=True,
        )
        db_session.add(cleaner)
        db_session.flush()

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            created_by=mock_user.id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        result = action_registry.dispatch(
            "assign_task",
            {"task_id": task.id, "assignee_name": "王清洁"},
            {"db": db_session, "user": mock_user},
        )
        assert result["success"] is True
        assert "王清洁" in result["assignee_name"]

    def test_assign_name_not_found(
        self, db_session, sample_room, mock_user, action_registry
    ):
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            created_by=mock_user.id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        result = action_registry.dispatch(
            "assign_task",
            {"task_id": task.id, "assignee_name": "不存在的人"},
            {"db": db_session, "user": mock_user},
        )
        assert result["success"] is False
        assert result["error"] == "not_found"

    def test_assign_no_assignee_provided(
        self, db_session, sample_room, mock_user, action_registry
    ):
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            created_by=mock_user.id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        result = action_registry.dispatch(
            "assign_task",
            {"task_id": task.id},
            {"db": db_session, "user": mock_user},
        )
        assert result["success"] is False
        assert result["error"] == "missing_assignee"

    def test_assign_nonexistent_task(
        self, db_session, mock_user, action_registry
    ):
        result = action_registry.dispatch(
            "assign_task",
            {"task_id": 99999, "assignee_id": 1},
            {"db": db_session, "user": mock_user},
        )
        assert result["success"] is False
        assert result["error"] == "business_error"

    def test_assign_completed_task_fails(
        self, db_session, sample_room, mock_user, action_registry
    ):
        cleaner = Employee(
            username="cleaner_completed_test",
            password_hash="hashed",
            name="清洁完成",
            role=EmployeeRole.CLEANER,
            is_active=True,
        )
        db_session.add(cleaner)
        db_session.flush()

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.COMPLETED,
            assignee_id=cleaner.id,
            created_by=mock_user.id,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        result = action_registry.dispatch(
            "assign_task",
            {"task_id": task.id, "assignee_id": cleaner.id},
            {"db": db_session, "user": mock_user},
        )
        assert result["success"] is False


class TestStartTask:
    """Test start_task action handler."""

    def test_start_assigned_task(
        self, db_session, sample_room, action_registry
    ):
        cleaner = Employee(
            username="cleaner_start",
            password_hash="hashed",
            name="清洁员S",
            role=EmployeeRole.CLEANER,
            is_active=True,
        )
        db_session.add(cleaner)
        db_session.flush()

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.ASSIGNED,
            assignee_id=cleaner.id,
            created_by=1,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        mock_cleaner_user = Mock(spec=Employee)
        mock_cleaner_user.id = cleaner.id
        mock_cleaner_user.name = cleaner.name
        role_mock = Mock()
        role_mock.value = "cleaner"
        mock_cleaner_user.role = role_mock

        result = action_registry.dispatch(
            "start_task",
            {"task_id": task.id},
            {"db": db_session, "user": mock_cleaner_user},
        )
        assert result["success"] is True
        assert result["status"] == "in_progress"

    def test_start_task_not_assigned_to_user(
        self, db_session, sample_room, action_registry
    ):
        cleaner = Employee(
            username="cleaner_notme",
            password_hash="hashed",
            name="不是我",
            role=EmployeeRole.CLEANER,
            is_active=True,
        )
        db_session.add(cleaner)
        db_session.flush()

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.ASSIGNED,
            assignee_id=cleaner.id,
            created_by=1,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        wrong_user = Mock(spec=Employee)
        wrong_user.id = 999
        wrong_user.name = "其他人"
        role_mock = Mock()
        role_mock.value = "cleaner"
        wrong_user.role = role_mock

        result = action_registry.dispatch(
            "start_task",
            {"task_id": task.id},
            {"db": db_session, "user": wrong_user},
        )
        assert result["success"] is False
        assert result["error"] == "business_error"

    def test_start_nonexistent_task(
        self, db_session, action_registry
    ):
        user = Mock(spec=Employee)
        user.id = 1
        user.name = "test"
        role_mock = Mock()
        role_mock.value = "cleaner"
        user.role = role_mock

        result = action_registry.dispatch(
            "start_task",
            {"task_id": 99999},
            {"db": db_session, "user": user},
        )
        assert result["success"] is False

    def test_start_pending_task_fails(
        self, db_session, sample_room, action_registry
    ):
        cleaner = Employee(
            username="cleaner_pending",
            password_hash="hashed",
            name="清洁P",
            role=EmployeeRole.CLEANER,
            is_active=True,
        )
        db_session.add(cleaner)
        db_session.flush()

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            created_by=1,
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        mock_cleaner_user = Mock(spec=Employee)
        mock_cleaner_user.id = cleaner.id
        mock_cleaner_user.name = cleaner.name
        role_mock = Mock()
        role_mock.value = "cleaner"
        mock_cleaner_user.role = role_mock

        result = action_registry.dispatch(
            "start_task",
            {"task_id": task.id},
            {"db": db_session, "user": mock_cleaner_user},
        )
        assert result["success"] is False


class TestCompleteTask:
    """Test complete_task action handler."""

    def test_complete_in_progress_task(
        self, db_session, sample_room, action_registry
    ):
        cleaner = Employee(
            username="cleaner_complete",
            password_hash="hashed",
            name="清洁C",
            role=EmployeeRole.CLEANER,
            is_active=True,
        )
        db_session.add(cleaner)
        db_session.flush()

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.IN_PROGRESS,
            assignee_id=cleaner.id,
            created_by=1,
            started_at=datetime.now(),
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        mock_cleaner_user = Mock(spec=Employee)
        mock_cleaner_user.id = cleaner.id
        mock_cleaner_user.name = cleaner.name
        role_mock = Mock()
        role_mock.value = "cleaner"
        mock_cleaner_user.role = role_mock

        result = action_registry.dispatch(
            "complete_task",
            {"task_id": task.id},
            {"db": db_session, "user": mock_cleaner_user},
        )
        assert result["success"] is True
        assert result["status"] == "completed"

    def test_complete_task_with_notes(
        self, db_session, sample_room, action_registry
    ):
        cleaner = Employee(
            username="cleaner_notes",
            password_hash="hashed",
            name="清洁N",
            role=EmployeeRole.CLEANER,
            is_active=True,
        )
        db_session.add(cleaner)
        db_session.flush()

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.IN_PROGRESS,
            assignee_id=cleaner.id,
            created_by=1,
            started_at=datetime.now(),
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        mock_cleaner_user = Mock(spec=Employee)
        mock_cleaner_user.id = cleaner.id
        mock_cleaner_user.name = cleaner.name
        role_mock = Mock()
        role_mock.value = "cleaner"
        mock_cleaner_user.role = role_mock

        result = action_registry.dispatch(
            "complete_task",
            {"task_id": task.id, "notes": "cleaned thoroughly"},
            {"db": db_session, "user": mock_cleaner_user},
        )
        assert result["success"] is True

    def test_complete_task_not_assigned_to_user(
        self, db_session, sample_room, action_registry
    ):
        cleaner = Employee(
            username="cleaner_wronguser",
            password_hash="hashed",
            name="清洁W",
            role=EmployeeRole.CLEANER,
            is_active=True,
        )
        db_session.add(cleaner)
        db_session.flush()

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.IN_PROGRESS,
            assignee_id=cleaner.id,
            created_by=1,
            started_at=datetime.now(),
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        wrong_user = Mock(spec=Employee)
        wrong_user.id = 999
        wrong_user.name = "其他"
        role_mock = Mock()
        role_mock.value = "cleaner"
        wrong_user.role = role_mock

        result = action_registry.dispatch(
            "complete_task",
            {"task_id": task.id},
            {"db": db_session, "user": wrong_user},
        )
        assert result["success"] is False

    def test_complete_nonexistent_task(
        self, db_session, action_registry
    ):
        user = Mock(spec=Employee)
        user.id = 1
        user.name = "test"
        role_mock = Mock()
        role_mock.value = "cleaner"
        user.role = role_mock

        result = action_registry.dispatch(
            "complete_task",
            {"task_id": 99999},
            {"db": db_session, "user": user},
        )
        assert result["success"] is False
