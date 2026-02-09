"""
Tests for SPEC-16: LLM extract_intent + extract_params
Tests the rule-based fallback paths (no real LLM needed)
"""
import pytest
from unittest.mock import patch, MagicMock
from app.services.llm_service import LLMService


@pytest.fixture
def llm_service():
    """Create LLMService with LLM disabled (uses rule-based fallback)"""
    with patch.object(LLMService, '__init__', lambda self: None):
        svc = LLMService.__new__(LLMService)
        svc.enabled = False
        svc.client = None
        svc._prompt_builder = None
        svc._query_schema_cache = None
        svc.api_key = None
        return svc


class TestExtractIntent:
    """Test extract_intent method (SPEC-16)"""

    def test_extract_intent_returns_structure(self, llm_service):
        """extract_intent returns proper structure"""
        result = llm_service.extract_intent("查询房间状态")
        assert "entity_mentions" in result
        assert "action_hints" in result
        assert "extracted_values" in result
        assert "time_references" in result

    def test_extract_intent_entity_detection(self, llm_service):
        """Detects entity mentions in Chinese"""
        result = llm_service.extract_intent("查看所有客人信息")
        assert "Guest" in result["entity_mentions"]

    def test_extract_intent_room_entity(self, llm_service):
        """Detects Room entity"""
        result = llm_service.extract_intent("201房间什么状态")
        assert "Room" in result["entity_mentions"]

    def test_extract_intent_action_detection_checkin(self, llm_service):
        """Detects checkin action"""
        result = llm_service.extract_intent("办理入住")
        assert "checkin" in result["action_hints"]

    def test_extract_intent_action_detection_checkout(self, llm_service):
        """Detects checkout action"""
        result = llm_service.extract_intent("退房")
        assert "checkout" in result["action_hints"]

    def test_extract_intent_action_detection_query(self, llm_service):
        """Detects query action"""
        result = llm_service.extract_intent("查询预订")
        assert "query" in result["action_hints"]
        assert "Reservation" in result["entity_mentions"]

    def test_extract_intent_time_references(self, llm_service):
        """Detects time references"""
        result = llm_service.extract_intent("查询今天入住的客人")
        assert "今天" in result["time_references"]

    def test_extract_intent_room_number(self, llm_service):
        """Extracts room number from message"""
        result = llm_service.extract_intent("301号房间需要清洁")
        assert result["extracted_values"].get("room_number") == "301"

    def test_extract_intent_multiple_entities(self, llm_service):
        """Detects multiple entity types"""
        result = llm_service.extract_intent("查看客人的账单")
        assert "Guest" in result["entity_mentions"]
        assert "Bill" in result["entity_mentions"]

    def test_extract_intent_empty_message(self, llm_service):
        """Handles empty message gracefully"""
        result = llm_service.extract_intent("")
        assert result["entity_mentions"] == []
        assert result["action_hints"] == []

    def test_extract_intent_task_detection(self, llm_service):
        """Detects task-related entities"""
        result = llm_service.extract_intent("分配清洁任务")
        assert "Task" in result["entity_mentions"]
        assert "assign" in result["action_hints"]


class TestExtractParams:
    """Test extract_params method (SPEC-16)"""

    def test_extract_params_disabled_llm(self, llm_service):
        """When LLM is disabled, returns known values with all required as missing"""
        schema = {
            "properties": {
                "room_number": {"type": "string", "description": "房间号"},
                "guest_name": {"type": "string", "description": "客人姓名"},
            },
            "required": ["room_number", "guest_name"]
        }
        result = llm_service.extract_params("入住201", schema)
        assert result["params"] == {}
        assert "room_number" in result["missing"]
        assert "guest_name" in result["missing"]
        assert result["confidence"] == 0.0

    def test_extract_params_with_known_values(self, llm_service):
        """Known values are preserved"""
        schema = {
            "properties": {
                "room_number": {"type": "string"},
                "guest_name": {"type": "string"},
            },
            "required": ["room_number", "guest_name"]
        }
        result = llm_service.extract_params(
            "入住",
            schema,
            known_values={"room_number": "201"}
        )
        assert result["params"]["room_number"] == "201"

    def test_extract_params_all_known(self, llm_service):
        """When all required fields are known, confidence is high"""
        schema = {
            "properties": {
                "room_number": {"type": "string"},
            },
            "required": ["room_number"]
        }
        result = llm_service.extract_params(
            "入住201房",
            schema,
            known_values={"room_number": "201"}
        )
        # All fields provided via known_values, no fields to extract
        assert result["confidence"] == 1.0
        assert result["missing"] == []

    def test_extract_params_empty_schema(self, llm_service):
        """Empty schema means no params needed"""
        schema = {"properties": {}, "required": []}
        result = llm_service.extract_params("hello", schema)
        assert result["missing"] == []


class TestRuleBasedExtractIntent:
    """Test _extract_intent_rule_based directly"""

    def test_cancel_action(self, llm_service):
        """Detects cancel action"""
        result = llm_service._extract_intent_rule_based("取消预订")
        assert "cancel" in result["action_hints"]
        assert "Reservation" in result["entity_mentions"]

    def test_create_action(self, llm_service):
        """Detects create action"""
        result = llm_service._extract_intent_rule_based("创建新任务")
        assert "create" in result["action_hints"]
        assert "Task" in result["entity_mentions"]

    def test_tomorrow_reference(self, llm_service):
        """Detects tomorrow time reference"""
        result = llm_service._extract_intent_rule_based("明天入住")
        assert "明天" in result["time_references"]

    def test_english_input(self, llm_service):
        """Handles English keywords"""
        result = llm_service._extract_intent_rule_based("show me the guest list")
        assert "Guest" in result["entity_mentions"]
        assert "query" in result["action_hints"]
