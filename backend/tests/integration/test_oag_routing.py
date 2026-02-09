"""
Tests for SPEC-19: IntentRouter integration into ai_service
Tests the OAG fast path in process_message
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from core.ai.intent_router import IntentRouter, ExtractedIntent, RoutingResult


class TestOAGFastPath:
    """Test _try_oag_path method"""

    def test_oag_returns_none_when_no_router(self):
        """When IntentRouter is not available, returns None"""
        from app.services.ai_service import AIService
        with patch.object(AIService, '__init__', lambda self, *a: None):
            svc = AIService.__new__(AIService)
            svc._intent_router = False
            svc._query_compiler = None
            svc._response_generator = None
            svc._action_registry = None
            svc.llm_service = MagicMock()
            result = svc._try_oag_path("test", MagicMock())
            assert result is None

    def test_oag_returns_none_on_low_confidence(self):
        """Low confidence routing falls through to LLM"""
        from app.services.ai_service import AIService
        with patch.object(AIService, '__init__', lambda self, *a: None):
            svc = AIService.__new__(AIService)
            svc._action_registry = None

            mock_router = MagicMock()
            mock_router.route.return_value = RoutingResult(
                action=None, candidates=[], confidence=0.3, reasoning="low"
            )
            svc._intent_router = mock_router
            svc._query_compiler = None
            svc._response_generator = None

            svc.llm_service = MagicMock()
            svc.llm_service.extract_intent.return_value = {
                "entity_mentions": [], "action_hints": [],
                "extracted_values": {}, "time_references": [],
            }

            user = MagicMock()
            user.role = "admin"
            result = svc._try_oag_path("hello", user)
            assert result is None

    def test_oag_high_confidence_mutation(self):
        """High confidence mutation returns action for confirmation"""
        from app.services.ai_service import AIService
        with patch.object(AIService, '__init__', lambda self, *a: None):
            svc = AIService.__new__(AIService)

            mock_router = MagicMock()
            mock_router.route.return_value = RoutingResult(
                action="checkout", candidates=[], confidence=0.95, reasoning="exact"
            )
            svc._intent_router = mock_router
            svc._query_compiler = None
            svc._response_generator = False

            # Mock action registry
            mock_action_def = MagicMock()
            mock_action_def.entity = "StayRecord"
            mock_action_def.description = "退房"
            mock_action_def.parameters_schema = None
            mock_registry = MagicMock()
            mock_registry.get_action.return_value = mock_action_def
            svc._action_registry = mock_registry

            svc.llm_service = MagicMock()
            svc.llm_service.extract_intent.return_value = {
                "entity_mentions": ["StayRecord"],
                "action_hints": ["checkout"],
                "extracted_values": {"stay_record_id": 1},
                "time_references": [],
            }
            svc.llm_service.extract_params.return_value = {
                "params": {"stay_record_id": 1},
                "missing": [],
                "confidence": 1.0,
            }

            user = MagicMock()
            user.role = "admin"
            result = svc._try_oag_path("退房", user)

            assert result is not None
            assert result["suggested_actions"][0]["action_type"] == "checkout"
            assert result["suggested_actions"][0]["requires_confirmation"] is True
            assert result["context"]["oag_path"] is True


class TestOAGComponentAccessors:
    """Test lazy initialization of OAG components"""

    def test_get_intent_router_returns_none_on_import_error(self):
        """IntentRouter accessor handles import errors"""
        from app.services.ai_service import AIService
        with patch.object(AIService, '__init__', lambda self, *a: None):
            svc = AIService.__new__(AIService)
            svc._intent_router = None
            svc._action_registry = False
            with patch('builtins.__import__', side_effect=ImportError):
                result = svc._get_intent_router()
            # After failure, it should be marked as False
            assert result is None

    def test_get_response_generator_lazy_init(self):
        """ResponseGenerator is lazily initialized"""
        from app.services.ai_service import AIService
        with patch.object(AIService, '__init__', lambda self, *a: None):
            svc = AIService.__new__(AIService)
            svc._response_generator = None
            gen = svc._get_response_generator()
            # Should have been initialized (or None if import fails)
            assert svc._response_generator is not None  # True or False (not None)


class TestOAGMissingFields:
    """Test OAG path with missing fields"""

    def test_missing_params_returns_followup(self):
        """When params are missing, OAG returns missing_fields response"""
        from app.services.ai_service import AIService
        with patch.object(AIService, '__init__', lambda self, *a: None):
            svc = AIService.__new__(AIService)

            mock_router = MagicMock()
            mock_router.route.return_value = RoutingResult(
                action="walkin_checkin", candidates=[], confidence=0.95, reasoning="exact"
            )
            svc._intent_router = mock_router
            svc._query_compiler = None
            svc._response_generator = False

            mock_action_def = MagicMock()
            mock_action_def.entity = "Guest"
            mock_action_def.description = "散客入住"
            mock_action_def.parameters_schema = None
            mock_registry = MagicMock()
            mock_registry.get_action.return_value = mock_action_def
            svc._action_registry = mock_registry

            svc.llm_service = MagicMock()
            svc.llm_service.extract_intent.return_value = {
                "entity_mentions": ["Guest"],
                "action_hints": ["checkin"],
                "extracted_values": {"room_number": "301"},
                "time_references": [],
            }
            svc.llm_service.extract_params.return_value = {
                "params": {"room_number": "301"},
                "missing": ["guest_name", "guest_phone"],
                "confidence": 0.3,
            }

            user = MagicMock()
            user.role = "admin"
            result = svc._try_oag_path("入住301房", user)

            assert result is not None
            assert result["suggested_actions"][0]["requires_confirmation"] is False
            assert "guest_name" in result["suggested_actions"][0]["missing_fields"]
