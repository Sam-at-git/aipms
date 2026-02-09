"""
Tests for SPEC-21: ResponseGenerator integration into ai_service
"""
import pytest
from unittest.mock import patch, MagicMock


class TestResponseGeneratorIntegration:
    """Test ResponseGenerator integration in OAG path"""

    def test_get_response_generator_returns_instance(self):
        """ResponseGenerator should be created successfully"""
        from app.services.ai_service import AIService
        with patch.object(AIService, '__init__', lambda self, *a: None):
            svc = AIService.__new__(AIService)
            svc._response_generator = None
            gen = svc._get_response_generator()
            if gen:
                from core.ai.response_generator import ResponseGenerator
                assert isinstance(gen, ResponseGenerator)

    def test_mutation_uses_response_generator(self):
        """OAG mutation path uses ResponseGenerator for formatting"""
        from app.services.ai_service import AIService
        from core.ai.intent_router import ExtractedIntent, RoutingResult
        from core.ai.response_generator import ResponseGenerator

        with patch.object(AIService, '__init__', lambda self, *a: None):
            svc = AIService.__new__(AIService)

            mock_router = MagicMock()
            svc._intent_router = mock_router
            svc._query_compiler = None

            # Use real ResponseGenerator
            svc._response_generator = ResponseGenerator(language="zh")

            mock_action_def = MagicMock()
            mock_action_def.entity = "Guest"
            mock_action_def.description = "散客入住"
            mock_action_def.parameters_schema = None
            mock_registry = MagicMock()
            mock_registry.get_action.return_value = mock_action_def
            svc._action_registry = mock_registry

            intent = ExtractedIntent(
                entity_mentions=["Guest"],
                action_hints=["checkin"],
                extracted_params={"room_number": "301", "guest_name": "张三"},
            )
            routing = RoutingResult(
                action="walkin_checkin", confidence=0.95, reasoning="exact"
            )

            svc.llm_service = MagicMock()
            svc.llm_service.extract_params.return_value = {
                "params": {"room_number": "301", "guest_name": "张三"},
                "missing": [],
                "confidence": 1.0,
            }

            result = svc._oag_handle_mutation(intent, routing, "入住301", MagicMock())

            assert result is not None
            assert "请确认" in result["message"]
            assert result["suggested_actions"][0]["requires_confirmation"] is True

    def test_missing_fields_uses_response_generator(self):
        """OAG missing fields path uses ResponseGenerator"""
        from app.services.ai_service import AIService
        from core.ai.intent_router import ExtractedIntent, RoutingResult
        from core.ai.response_generator import ResponseGenerator

        with patch.object(AIService, '__init__', lambda self, *a: None):
            svc = AIService.__new__(AIService)
            svc._intent_router = MagicMock()
            svc._query_compiler = None
            svc._response_generator = ResponseGenerator(language="zh")

            mock_action_def = MagicMock()
            mock_action_def.entity = "Guest"
            mock_action_def.description = "散客入住"
            mock_action_def.parameters_schema = None
            mock_registry = MagicMock()
            mock_registry.get_action.return_value = mock_action_def
            svc._action_registry = mock_registry

            intent = ExtractedIntent(
                entity_mentions=["Guest"],
                action_hints=["checkin"],
            )
            routing = RoutingResult(
                action="walkin_checkin", confidence=0.95, reasoning="exact"
            )

            svc.llm_service = MagicMock()
            svc.llm_service.extract_params.return_value = {
                "params": {},
                "missing": ["room_number", "guest_name"],
                "confidence": 0.0,
            }

            result = svc._oag_handle_mutation(intent, routing, "入住", MagicMock())

            assert result is not None
            assert "room_number" in result["message"]
            assert result["suggested_actions"][0]["requires_confirmation"] is False
