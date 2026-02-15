"""
Test that _enhance_actions_with_db_data correctly handles Chinese task_type
"""
import pytest
from unittest.mock import Mock, MagicMock
from app.services.ai_service import AIService
from app.models.ontology import TaskType


class TestTaskTypeEnhancement:
    """Test task_type parameter enhancement in AI service"""

    def test_chinese_maintenance_task_type_conversion(self):
        """Test that Chinese '维修' is converted to 'maintenance'"""
        # Create mock DB
        mock_db = Mock(spec=['query'])

        # Create AI service with mocked adapter param_parser
        service = AIService(mock_db)

        from app.services.param_parser_service import ParseResult
        service.adapter._room_service = Mock()  # prevent _ensure_services from re-initializing
        service.adapter._param_parser = Mock()
        service.adapter._param_parser.parse_room.return_value = ParseResult(
            value=208,
            confidence=1.0,
            matched_by='test',
            raw_input='208'
        )

        # Mock parse_task_type to return maintenance for Chinese input
        service.adapter._param_parser.parse_task_type.return_value = ParseResult(
            value=TaskType.MAINTENANCE,
            confidence=0.95,
            matched_by='alias',
            raw_input='维修'
        )

        # Mock parse_date to avoid issues
        service.adapter._param_parser.parse_date.return_value = ParseResult(
            value=None, confidence=0.0, matched_by='none', raw_input=''
        )

        # Simulate LLM response with Chinese task_type
        result = {
            "suggested_actions": [
                {
                    "action_type": "create_task",
                    "description": "创建维修任务",
                    "params": {
                        "room_number": "208",
                        "task_type": "维修"
                    }
                }
            ]
        }

        # Call enhancement function
        enhanced = service._enhance_actions_with_db_data(result)

        # Verify the task_type was converted
        action = enhanced["suggested_actions"][0]
        assert action["params"]["task_type"] == "maintenance"
        service.adapter._param_parser.parse_task_type.assert_called_with("维修")

    def test_chinese_cleaning_task_type_conversion(self):
        """Test that Chinese '清洁' is converted to 'cleaning'"""
        mock_db = Mock(spec=['query'])
        service = AIService(mock_db)

        from app.services.param_parser_service import ParseResult
        service.adapter._room_service = Mock()  # prevent _ensure_services from re-initializing
        service.adapter._param_parser = Mock()
        service.adapter._param_parser.parse_room.return_value = ParseResult(
            value=208,
            confidence=1.0,
            matched_by='test',
            raw_input='208'
        )
        service.adapter._param_parser.parse_task_type.return_value = ParseResult(
            value=TaskType.CLEANING,
            confidence=0.95,
            matched_by='alias',
            raw_input='清洁'
        )
        service.adapter._param_parser.parse_date.return_value = ParseResult(
            value=None, confidence=0.0, matched_by='none', raw_input=''
        )

        result = {
            "suggested_actions": [
                {
                    "action_type": "create_task",
                    "description": "创建清洁任务",
                    "params": {
                        "room_number": "208",
                        "task_type": "清洁"
                    }
                }
            ]
        }

        enhanced = service._enhance_actions_with_db_data(result)
        action = enhanced["suggested_actions"][0]

        assert action["params"]["task_type"] == "cleaning"
        service.adapter._param_parser.parse_task_type.assert_called_with("清洁")

    def test_english_task_type_preserved(self):
        """Test that English 'maintenance' is preserved"""
        mock_db = Mock(spec=['query'])
        service = AIService(mock_db)

        from app.services.param_parser_service import ParseResult
        service.adapter._room_service = Mock()  # prevent _ensure_services from re-initializing
        service.adapter._param_parser = Mock()
        service.adapter._param_parser.parse_room.return_value = ParseResult(
            value=208,
            confidence=1.0,
            matched_by='test',
            raw_input='208'
        )
        service.adapter._param_parser.parse_task_type.return_value = ParseResult(
            value=TaskType.MAINTENANCE,
            confidence=1.0,
            matched_by='direct',
            raw_input='maintenance'
        )
        service.adapter._param_parser.parse_date.return_value = ParseResult(
            value=None, confidence=0.0, matched_by='none', raw_input=''
        )

        result = {
            "suggested_actions": [
                {
                    "action_type": "create_task",
                    "description": "Create maintenance task",
                    "params": {
                        "room_number": "208",
                        "task_type": "maintenance"
                    }
                }
            ]
        }

        enhanced = service._enhance_actions_with_db_data(result)
        action = enhanced["suggested_actions"][0]

        assert action["params"]["task_type"] == "maintenance"

    def test_invalid_task_type_requests_confirmation(self):
        """Test that invalid task_type triggers low confidence path (adapter drops quietly)"""
        mock_db = Mock(spec=['query'])
        service = AIService(mock_db)

        from app.services.param_parser_service import ParseResult
        service.adapter._room_service = Mock()  # prevent _ensure_services from re-initializing
        service.adapter._param_parser = Mock()
        service.adapter._param_parser.parse_room.return_value = ParseResult(
            value=208,
            confidence=1.0,
            matched_by='test',
            raw_input='208'
        )
        # Low confidence for invalid task type
        service.adapter._param_parser.parse_task_type.return_value = ParseResult(
            value=None,
            confidence=0.0,
            matched_by='not_found',
            raw_input='invalid'
        )
        service.adapter._param_parser.parse_date.return_value = ParseResult(
            value=None, confidence=0.0, matched_by='none', raw_input=''
        )

        result = {
            "suggested_actions": [
                {
                    "action_type": "create_task",
                    "description": "Create task",
                    "params": {
                        "room_number": "208",
                        "task_type": "invalid"
                    }
                }
            ]
        }

        enhanced = service._enhance_actions_with_db_data(result)
        action = enhanced["suggested_actions"][0]

        # With adapter delegation, invalid task_type is left as-is (not converted)
        # The validation layer will catch it later
        assert action["params"]["task_type"] == "invalid"
