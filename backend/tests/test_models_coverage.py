"""
tests/test_models_coverage.py

Coverage tests for models/ontology.py and models/schemas.py.
"""
import pytest
from datetime import datetime, date
from pydantic import ValidationError


class TestSecurityLevelEnum:
    """Cover app/models/ontology.py (6 lines): SecurityLevel enum."""

    def test_security_level_values(self):
        """Exercise all SecurityLevel enum values."""
        from app.models.ontology import SecurityLevel

        assert SecurityLevel.PUBLIC == 1
        assert SecurityLevel.INTERNAL == 2
        assert SecurityLevel.CONFIDENTIAL == 3
        assert SecurityLevel.RESTRICTED == 4

    def test_security_level_from_int(self):
        """Construct SecurityLevel from int."""
        from app.models.ontology import SecurityLevel

        assert SecurityLevel(1) == SecurityLevel.PUBLIC
        assert SecurityLevel(4) == SecurityLevel.RESTRICTED

    def test_security_level_comparison(self):
        """SecurityLevel supports integer comparison."""
        from app.models.ontology import SecurityLevel

        assert SecurityLevel.PUBLIC < SecurityLevel.RESTRICTED
        assert SecurityLevel.CONFIDENTIAL > SecurityLevel.INTERNAL


class TestAIActionNormalizeMissingFields:
    """Cover app/models/schemas.py lines 56-79: normalize_missing_fields validator."""

    def test_missing_fields_none(self):
        """None missing_fields stays None."""
        from app.models.schemas import AIAction

        action = AIAction(
            action_type="test",
            entity_type="Room",
            description="Test action",
            missing_fields=None,
        )
        assert action.missing_fields is None

    def test_missing_fields_with_strings(self):
        """String items get converted to MissingField objects (lines 65-72)."""
        from app.models.schemas import AIAction, MissingField

        action = AIAction(
            action_type="test",
            entity_type="Room",
            description="Test action",
            missing_fields=["guest_name", "room_number"],
        )
        assert action.missing_fields is not None
        assert len(action.missing_fields) == 2
        assert isinstance(action.missing_fields[0], MissingField)
        assert action.missing_fields[0].field_name == "guest_name"
        assert action.missing_fields[0].field_type == "text"

    def test_missing_fields_with_dicts(self):
        """Dict items get converted to MissingField objects (lines 73-75)."""
        from app.models.schemas import AIAction, MissingField

        action = AIAction(
            action_type="test",
            entity_type="Room",
            description="Test action",
            missing_fields=[
                {"field_name": "phone", "display_name": "电话", "field_type": "text"},
            ],
        )
        assert action.missing_fields is not None
        assert len(action.missing_fields) == 1
        assert action.missing_fields[0].field_name == "phone"

    def test_missing_fields_with_mixed_types(self):
        """Mix of strings, dicts, and MissingField objects."""
        from app.models.schemas import AIAction, MissingField

        mf = MissingField(field_name="email", display_name="Email", field_type="text")
        action = AIAction(
            action_type="test",
            entity_type="Room",
            description="Test action",
            missing_fields=[
                "guest_name",
                {"field_name": "phone", "display_name": "Phone", "field_type": "text"},
                mf,
            ],
        )
        assert action.missing_fields is not None
        assert len(action.missing_fields) == 3

    def test_missing_fields_not_list(self):
        """Non-list value gets converted to None (line 58-59)."""
        from app.models.schemas import AIAction

        action = AIAction(
            action_type="test",
            entity_type="Room",
            description="Test action",
            missing_fields="not_a_list",
        )
        assert action.missing_fields is None

    def test_missing_fields_unrecognized_type(self):
        """Unrecognized item types get skipped (lines 76-78)."""
        from app.models.schemas import AIAction

        action = AIAction(
            action_type="test",
            entity_type="Room",
            description="Test action",
            missing_fields=[12345, None],  # Neither str, dict, nor MissingField
        )
        # All items skipped → normalized to None
        assert action.missing_fields is None

    def test_missing_fields_empty_list(self):
        """Empty list results in None."""
        from app.models.schemas import AIAction

        action = AIAction(
            action_type="test",
            entity_type="Room",
            description="Test action",
            missing_fields=[],
        )
        assert action.missing_fields is None


class TestFollowUpInfoSchema:
    """Test FollowUpInfo schema."""

    def test_follow_up_info_creation(self):
        from app.models.schemas import FollowUpInfo

        info = FollowUpInfo(
            action_type="create_reservation",
            message="请提供入住日期",
            collected_fields={"guest_name": "张三"},
        )
        assert info.action_type == "create_reservation"
        assert info.collected_fields["guest_name"] == "张三"


class TestAIResponseSchema:
    """Test AIResponse schema."""

    def test_ai_response_creation(self):
        from app.models.schemas import AIResponse

        response = AIResponse(
            message="已完成",
            topic_id="topic-123",
            reasoning_trace={"steps": ["step1"]},
        )
        assert response.message == "已完成"
        assert response.topic_id == "topic-123"
        assert response.reasoning_trace is not None
