"""
Tests for SPEC-20: QueryCompiler integration into ai_service
"""
import pytest
from unittest.mock import patch, MagicMock
from core.ai.intent_router import RoutingResult


class TestOAGQueryPath:
    """Test _oag_handle_query method"""

    def test_query_returns_none_without_compiler(self):
        """Without QueryCompiler, returns None"""
        from app.services.ai_service import AIService
        with patch.object(AIService, '__init__', lambda self, *a: None):
            svc = AIService.__new__(AIService)
            svc._query_compiler = False
            svc._response_generator = None
            svc._action_registry = None

            from core.ai.intent_router import ExtractedIntent
            intent = ExtractedIntent(entity_mentions=["Room"], action_hints=["query"])
            routing = RoutingResult(action="query_rooms", confidence=0.95, reasoning="match")

            result = svc._oag_handle_query(intent, routing, MagicMock())
            assert result is None

    def test_query_falls_through_on_low_compile_confidence(self):
        """Low compilation confidence falls through"""
        from app.services.ai_service import AIService
        with patch.object(AIService, '__init__', lambda self, *a: None):
            svc = AIService.__new__(AIService)
            svc._response_generator = None
            svc._action_registry = None
            svc.db = MagicMock()

            mock_compiler = MagicMock()
            mock_compilation = MagicMock()
            mock_compilation.confidence = 0.3
            mock_compilation.fallback_needed = True
            mock_compiler.compile.return_value = mock_compilation
            svc._query_compiler = mock_compiler

            from core.ai.intent_router import ExtractedIntent
            intent = ExtractedIntent(entity_mentions=["Unknown"], action_hints=["query"])
            routing = RoutingResult(action="query", confidence=0.95, reasoning="match")

            result = svc._oag_handle_query(intent, routing, MagicMock())
            assert result is None

    def test_get_query_compiler_lazy_init(self):
        """QueryCompiler is lazily initialized"""
        from app.services.ai_service import AIService
        with patch.object(AIService, '__init__', lambda self, *a: None):
            svc = AIService.__new__(AIService)
            svc._query_compiler = None
            svc._action_registry = None
            compiler = svc._get_query_compiler()
            # Should be initialized (or marked as unavailable)
            assert svc._query_compiler is not None
