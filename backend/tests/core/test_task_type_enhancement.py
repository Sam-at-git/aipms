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

        # Create AI service with mocked param_parser
        service = AIService(mock_db)
        service.param_parser = Mock()

        # Mock parse_room to avoid DB query
        from app.services.param_parser_service import ParseResult
        service.param_parser.parse_room.return_value = ParseResult(
            value=208,
            confidence=1.0,
            matched_by='test',
            raw_input='208'
        )

        # Mock parse_task_type to return maintenance for Chinese input
        service.param_parser.parse_task_type.return_value = ParseResult(
            value=TaskType.MAINTENANCE,
            confidence=0.95,
            matched_by='alias',
            raw_input='维修'
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
        service.param_parser.parse_task_type.assert_called_with("维修")

    def test_chinese_cleaning_task_type_conversion(self):
        """Test that Chinese '清洁' is converted to 'cleaning'"""
        mock_db = Mock(spec=['query'])
        service = AIService(mock_db)
        service.param_parser = Mock()

        from app.services.param_parser_service import ParseResult
        service.param_parser.parse_room.return_value = ParseResult(
            value=208,
            confidence=1.0,
            matched_by='test',
            raw_input='208'
        )
        service.param_parser.parse_task_type.return_value = ParseResult(
            value=TaskType.CLEANING,
            confidence=0.95,
            matched_by='alias',
            raw_input='清洁'
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
        service.param_parser.parse_task_type.assert_called_with("清洁")

    def test_english_task_type_preserved(self):
        """Test that English 'maintenance' is preserved"""
        mock_db = Mock(spec=['query'])
        service = AIService(mock_db)
        service.param_parser = Mock()

        from app.services.param_parser_service import ParseResult
        service.param_parser.parse_room.return_value = ParseResult(
            value=208,
            confidence=1.0,
            matched_by='test',
            raw_input='208'
        )
        service.param_parser.parse_task_type.return_value = ParseResult(
            value=TaskType.MAINTENANCE,
            confidence=1.0,
            matched_by='direct',
            raw_input='maintenance'
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
        """Test that invalid task_type triggers confirmation flow"""
        mock_db = Mock(spec=['query'])
        service = AIService(mock_db)
        service.param_parser = Mock()

        from app.services.param_parser_service import ParseResult
        service.param_parser.parse_room.return_value = ParseResult(
            value=208,
            confidence=1.0,
            matched_by='test',
            raw_input='208'
        )
        # Low confidence for invalid task type
        service.param_parser.parse_task_type.return_value = ParseResult(
            value=None,
            confidence=0.0,
            matched_by='not_found',
            raw_input='invalid'
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

        # Should require confirmation with candidates
        assert action["requires_confirmation"] is True
        assert "candidates" in action
        assert len(action["candidates"]) == 2  # CLEANING and MAINTENANCE
