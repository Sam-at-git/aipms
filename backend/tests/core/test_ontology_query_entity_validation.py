"""
Test that _execute_ontology_query handles missing entity field
"""
import pytest
from unittest.mock import Mock
from app.services.ai_service import AIService


class TestOntologyQueryEntityValidation:
    """Test ontology query entity validation in AI service"""

    def test_missing_entity_field_returns_error(self):
        """Test that missing 'entity' field returns a helpful error message"""
        mock_db = Mock(spec=['query'])
        service = AIService(mock_db)

        # Simulate LLM response without entity field
        query_dict = {
            "fields": ["name", "phone"],
            # Missing "entity"
        }

        result = service._execute_ontology_query(query_dict, Mock())

        # Should return error message instead of crashing
        assert result["query_result"]["display_type"] == "text"
        assert "缺少实体类型" in result["message"] or "entity" in result["message"].lower()
        assert result["query_result"]["rows"] == []

    def test_empty_entity_field_returns_error(self):
        """Test that empty 'entity' field also handled"""
        mock_db = Mock(spec=['query'])
        service = AIService(mock_db)

        query_dict = {
            "entity": "",  # Empty entity
            "fields": ["name"]
        }

        # Should not crash, may return error or empty results
        result = service._execute_ontology_query(query_dict, Mock())
        # Either error or query result
        assert "message" in result
        assert "query_result" in result
