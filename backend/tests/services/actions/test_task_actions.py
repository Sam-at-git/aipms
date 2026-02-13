"""
tests/services/actions/test_task_actions.py

Tests for task action handlers in app/services/actions/task_actions.py
"""
import pytest
from unittest.mock import Mock, MagicMock, patch

from sqlalchemy.orm import Session

import app.services.actions.task_actions as task_actions
from app.services.actions.base import CreateTaskParams
from app.models.ontology import Employee, EmployeeRole, Task, TaskType, TaskStatus, Room
from app.services.param_parser_service import ParseResult


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def mock_user():
    """Mock current user"""
    user = Mock(spec=Employee)
    user.id = 1
    user.username = "cleaner"
    user.role = EmployeeRole.CLEANER
    return user


@pytest.fixture
def mock_param_parser():
    """Mock parameter parser service"""
    parser = Mock()
    parser.parse_room = Mock()
    return parser


@pytest.fixture
def sample_room():
    """Sample room"""
    room = Mock(spec=Room)
    room.id = 101
    room.room_number = "101"
    return room


@pytest.fixture
def sample_task(sample_room):
    """Sample task"""
    task = Mock(spec=Task)
    task.id = 1
    task.room_id = sample_room.id
    task.task_type = TaskType.CLEANING
    task.status = TaskStatus.PENDING
    return task


# ==================== register_task_actions Tests ====================

class TestRegisterTaskActions:
    """Test register_task_actions function"""

    def test_register_task_actions(self):
        """Test that register_task_actions registers create_task action"""
        from core.ai.actions import ActionRegistry

        registry = ActionRegistry()
        task_actions.register_task_actions(registry)

        action = registry.get_action("create_task")
        assert action is not None
        assert action.name == "create_task"
        assert action.entity == "Task"
        assert action.category == "mutation"
        assert "cleaner" in action.allowed_roles


# ==================== handle_create_task Tests ====================

class TestHandleCreateTask:
    """Test handle_create_task handler via ActionRegistry"""

    @pytest.fixture
    def task_action(self, mock_db, mock_user, mock_param_parser, sample_task):
        """Fixture that provides the task action handler"""
        def execute_task(params):
            mock_param_parser.parse_room.return_value = ParseResult(
                value=101,
                confidence=1.0,
                matched_by='direct',
                raw_input="101",
                candidates=None
            )

            mock_task_service = MagicMock()
            mock_task_service.create_task.return_value = sample_task

            with patch('app.services.actions.task_actions.TaskService', return_value=mock_task_service):
                from core.ai.actions import ActionRegistry
                registry = ActionRegistry()
                task_actions.register_task_actions(registry)

                action_def = registry.get_action("create_task")
                return action_def.handler(
                    params=params,
                    db=mock_db,
                    user=mock_user,
                    param_parser=mock_param_parser
                )
        return execute_task

    def test_successful_task_creation_with_room_id(
        self, task_action, sample_task
    ):
        """Test successful task creation with room ID"""
        params = CreateTaskParams(room_id=101, task_type=TaskType.CLEANING)

        result = task_action(params)

        assert result["success"] is True
        assert result["task_id"] == sample_task.id

    def test_successful_task_creation_with_room_number(
        self, mock_db, mock_user, mock_param_parser, sample_task
    ):
        """Test successful task creation with room number string"""
        mock_param_parser.parse_room.return_value = ParseResult(
            value=201,
            confidence=1.0,
            matched_by='room_number',
            raw_input="201",
            candidates=None
        )

        mock_task_service = MagicMock()
        mock_task_service.create_task.return_value = sample_task

        params = CreateTaskParams(room_id="201", task_type="cleaning")

        with patch('app.services.actions.task_actions.TaskService', return_value=mock_task_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            task_actions.register_task_actions(registry)

            action_def = registry.get_action("create_task")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is True
        mock_param_parser.parse_room.assert_called_once_with("201")

    def test_successful_maintenance_task_creation(
        self, mock_db, mock_user, mock_param_parser, sample_task
    ):
        """Test successful maintenance task creation"""
        sample_task.task_type = TaskType.MAINTENANCE

        mock_param_parser.parse_room.return_value = ParseResult(
            value=101,
            confidence=1.0,
            matched_by='direct',
            raw_input="101",
            candidates=None
        )

        mock_task_service = MagicMock()
        mock_task_service.create_task.return_value = sample_task

        params = CreateTaskParams(room_id=101, task_type=TaskType.MAINTENANCE)

        with patch('app.services.actions.task_actions.TaskService', return_value=mock_task_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            task_actions.register_task_actions(registry)

            action_def = registry.get_action("create_task")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is True
        assert "维修任务已创建" in result["message"]

    def test_task_creation_with_chinese_type(
        self, mock_db, mock_user, mock_param_parser, sample_task
    ):
        """Test task creation with Chinese task type"""
        mock_param_parser.parse_room.return_value = ParseResult(
            value=101,
            confidence=1.0,
            matched_by='direct',
            raw_input="101",
            candidates=None
        )

        mock_task_service = MagicMock()
        mock_task_service.create_task.return_value = sample_task

        params = CreateTaskParams(room_id=101, task_type="清洁")

        with patch('app.services.actions.task_actions.TaskService', return_value=mock_task_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            task_actions.register_task_actions(registry)

            action_def = registry.get_action("create_task")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is True

    def test_task_creation_low_confidence_returns_candidates(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test task creation with low confidence returns candidates"""
        mock_param_parser.parse_room.return_value = ParseResult(
            value=None,
            confidence=0.5,
            matched_by='fuzzy',
            raw_input="10",
            candidates=[
                {"id": 101, "room_number": "101"},
                {"id": 102, "room_number": "102"}
            ]
        )

        params = CreateTaskParams(room_id="10", task_type="cleaning")

        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        task_actions.register_task_actions(registry)

        action_def = registry.get_action("create_task")
        result = action_def.handler(
            params=params,
            db=mock_db,
            user=mock_user,
            param_parser=mock_param_parser
        )

        assert result["success"] is False
        assert result["requires_confirmation"] is True
        assert result["action"] == "select_room"

    def test_task_creation_invalid_type_rejected_by_pydantic(
        self, mock_db, mock_user, mock_param_parser, sample_task
    ):
        """Test task creation with invalid type is rejected at Pydantic validation level"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="无效的任务类型"):
            CreateTaskParams(room_id=101, task_type="invalid_type")

    def test_task_creation_validation_error(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test task creation with validation error returns error result"""
        from pydantic import ValidationError

        mock_param_parser.parse_room.return_value = ParseResult(
            value=101,
            confidence=1.0,
            matched_by='direct',
            raw_input="101",
            candidates=None
        )

        mock_task_service = MagicMock()
        mock_task_service.create_task.side_effect = ValidationError.from_exception_data(
            title="TaskCreate",
            line_errors=[{"type": "value_error", "loc": ("room_id",), "msg": "Room not found", "input": 101, "ctx": {"error": ValueError("Room not found")}}]
        )

        params = CreateTaskParams(room_id=101, task_type="cleaning")

        with patch('app.services.actions.task_actions.TaskService', return_value=mock_task_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            task_actions.register_task_actions(registry)

            action_def = registry.get_action("create_task")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "validation_error"

    def test_task_creation_generic_error(
        self, mock_db, mock_user, mock_param_parser
    ):
        """Test task creation with generic error returns error result"""
        mock_param_parser.parse_room.return_value = ParseResult(
            value=101,
            confidence=1.0,
            matched_by='direct',
            raw_input="101",
            candidates=None
        )

        mock_task_service = MagicMock()
        mock_task_service.create_task.side_effect = Exception("数据库错误")

        params = CreateTaskParams(room_id=101, task_type="cleaning")

        with patch('app.services.actions.task_actions.TaskService', return_value=mock_task_service):
            from core.ai.actions import ActionRegistry
            registry = ActionRegistry()
            task_actions.register_task_actions(registry)

            action_def = registry.get_action("create_task")
            result = action_def.handler(
                params=params,
                db=mock_db,
                user=mock_user,
                param_parser=mock_param_parser
            )

        assert result["success"] is False
        assert result["error"] == "execution_error"


# ==================== Integration Tests ====================

class TestTaskActionsIntegration:
    """Integration tests for task actions"""

    def test_action_registration_and_metadata(self):
        """Test create_task action registration and metadata"""
        from core.ai.actions import ActionRegistry

        registry = ActionRegistry()
        task_actions.register_task_actions(registry)

        action = registry.get_action("create_task")
        assert action is not None
        assert "创建任务" in action.search_keywords

    def test_module_exports(self):
        """Test that task_actions module exports correctly"""
        assert hasattr(task_actions, "register_task_actions")
        from core.ai.actions import ActionRegistry
        registry = ActionRegistry()
        task_actions.register_task_actions(registry)
        assert registry.get_action("create_task") is not None

    def test_module_all(self):
        """Test __all__ export"""
        assert "register_task_actions" in task_actions.__all__
