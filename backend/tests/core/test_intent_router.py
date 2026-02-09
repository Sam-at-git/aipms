"""
tests/core/test_intent_router.py

Unit tests for IntentRouter - rule-based intent-to-action routing.
"""
import pytest
from unittest.mock import MagicMock, Mock
from pydantic import BaseModel, Field

from core.ai.actions import ActionDefinition, ActionRegistry
from core.ai.intent_router import ExtractedIntent, RoutingResult, IntentRouter


# --------------- Test Parameter Models ---------------

class CheckInParams(BaseModel):
    guest_name: str = Field(..., description="Guest name")
    room_id: int = Field(..., description="Room ID")


class CheckOutParams(BaseModel):
    stay_id: int = Field(..., description="Stay record ID")


class CreateTaskParams(BaseModel):
    task_type: str = Field(..., description="Task type")
    room_id: int = Field(..., description="Room ID")


class QueryParams(BaseModel):
    entity: str = Field(..., description="Entity to query")


class ReservationParams(BaseModel):
    guest_name: str = Field(..., description="Guest name")
    room_type: str = Field(..., description="Room type")


# --------------- Fixtures ---------------

def _make_action(
    name, entity, description="", category="mutation",
    allowed_roles=None, search_keywords=None, handler=None,
    params_model=None,
):
    """Helper to create ActionDefinition without going through the registry decorator."""
    if handler is None:
        handler = lambda params, **kw: {"success": True}
    if params_model is None:
        params_model = QueryParams

    return ActionDefinition(
        name=name,
        entity=entity,
        description=description or f"Action {name}",
        category=category,
        parameters_schema=params_model,
        handler=handler,
        allowed_roles=set(allowed_roles) if allowed_roles else set(),
        search_keywords=search_keywords or [],
    )


@pytest.fixture
def action_registry():
    """Create a minimal ActionRegistry with no vector store and register test actions."""
    registry = ActionRegistry(vector_store=None)

    # Manually inject actions (bypass decorator to avoid handler signature detection)
    actions = [
        _make_action(
            "walkin_checkin", "Guest",
            description="Walk-in guest check-in",
            search_keywords=["checkin", "check_in", "walk-in", "入住"],
            allowed_roles=["admin", "receptionist"],
            params_model=CheckInParams,
        ),
        _make_action(
            "checkout", "Guest",
            description="Guest check-out",
            search_keywords=["check_out", "退房"],
            allowed_roles=["admin", "receptionist"],
            params_model=CheckOutParams,
        ),
        _make_action(
            "create_task", "Task",
            description="Create a cleaning or maintenance task",
            search_keywords=["task", "clean", "maintenance", "任务"],
            allowed_roles=["admin", "manager", "receptionist"],
            params_model=CreateTaskParams,
        ),
        _make_action(
            "complete_task", "Task",
            description="Mark a task as completed",
            search_keywords=["complete", "done", "finish", "完成"],
            allowed_roles=["admin", "manager", "cleaner"],
            params_model=CreateTaskParams,
        ),
        _make_action(
            "create_reservation", "Reservation",
            description="Create a new reservation",
            search_keywords=["reserve", "book", "预订"],
            allowed_roles=["admin", "receptionist", "manager"],
            params_model=ReservationParams,
        ),
        _make_action(
            "cancel_reservation", "Reservation",
            description="Cancel an existing reservation",
            search_keywords=["cancel", "取消"],
            allowed_roles=["admin", "manager"],
            params_model=ReservationParams,
        ),
        _make_action(
            "ontology_query", "Query",
            description="Dynamic ontology query",
            category="query",
            search_keywords=["query", "search", "find", "查询"],
            allowed_roles=[],  # open to all
            params_model=QueryParams,
        ),
    ]

    for action_def in actions:
        registry._actions[action_def.name] = action_def

    return registry


@pytest.fixture
def router(action_registry):
    """Create an IntentRouter with the test registry."""
    return IntentRouter(action_registry=action_registry)


# --------------- Test Classes ---------------


class TestExtractedIntent:
    """Tests for the ExtractedIntent dataclass."""

    def test_default_values(self):
        """ExtractedIntent should have sensible defaults."""
        intent = ExtractedIntent()
        assert intent.entity_mentions == []
        assert intent.action_hints == []
        assert intent.extracted_params == {}
        assert intent.time_references == []

    def test_custom_values(self):
        """ExtractedIntent should accept custom values."""
        intent = ExtractedIntent(
            entity_mentions=["Guest"],
            action_hints=["checkin"],
            extracted_params={"guest_name": "Zhang"},
            time_references=["tomorrow"],
        )
        assert intent.entity_mentions == ["Guest"]
        assert intent.action_hints == ["checkin"]
        assert intent.extracted_params == {"guest_name": "Zhang"}
        assert intent.time_references == ["tomorrow"]


class TestRoutingResult:
    """Tests for the RoutingResult dataclass."""

    def test_default_values(self):
        """RoutingResult should have sensible defaults."""
        result = RoutingResult()
        assert result.action is None
        assert result.candidates == []
        assert result.confidence == 0.0
        assert result.reasoning == ""


class TestKeywordExactMatch:
    """Test Stage 1: keyword exact match routing."""

    def test_exact_name_match(self, router):
        """Action hint exactly matching an action name should score 1.0."""
        intent = ExtractedIntent(action_hints=["checkout"])
        result = router.route(intent)

        assert result.action == "checkout"
        assert result.confidence == 0.95
        assert any(c["name"] == "checkout" and c["score"] == 1.0 for c in result.candidates)

    def test_substring_match_in_action_name(self, router):
        """Action hint that is a substring of an action name should match."""
        intent = ExtractedIntent(action_hints=["checkin"])
        result = router.route(intent)

        # "checkin" should match "walkin_checkin" via substring
        assert result.action is not None
        matched_names = [c["name"] for c in result.candidates]
        assert "walkin_checkin" in matched_names

    def test_search_keywords_match(self, router):
        """Action hint matching a search_keyword should be found."""
        intent = ExtractedIntent(action_hints=["reserve"])
        result = router.route(intent)

        assert result.action == "create_reservation"
        assert result.confidence == 0.95
        assert any(c["score"] == 0.9 for c in result.candidates)

    def test_chinese_keyword_match(self, router):
        """Chinese keywords in search_keywords should match."""
        intent = ExtractedIntent(action_hints=["入住"])
        result = router.route(intent)

        assert result.action == "walkin_checkin"
        assert result.confidence == 0.95

    def test_multiple_keyword_matches(self, router):
        """Multiple action_hints can produce multiple candidates."""
        intent = ExtractedIntent(action_hints=["checkin", "task"])
        result = router.route(intent)

        matched_names = {c["name"] for c in result.candidates}
        # Should find both walkin_checkin (from "checkin") and create_task (from "task")
        assert "walkin_checkin" in matched_names
        assert "create_task" in matched_names
        assert result.confidence == 0.6  # 2-3 candidates

    def test_no_keyword_match_falls_through_to_entity(self, router):
        """If no keyword matches, should fall through to entity-based filtering."""
        intent = ExtractedIntent(
            action_hints=["nonexistent_action"],
            entity_mentions=["Task"],
        )
        result = router.route(intent)

        # Should fall through to entity filter
        matched_names = {c["name"] for c in result.candidates}
        assert "create_task" in matched_names or "complete_task" in matched_names


class TestEntityBasedFiltering:
    """Test Stage 2: entity-based filtering."""

    def test_single_entity_filter(self, router):
        """Filtering by a single entity should return only its actions."""
        intent = ExtractedIntent(entity_mentions=["Task"])
        result = router.route(intent)

        matched_names = {c["name"] for c in result.candidates}
        assert matched_names == {"create_task", "complete_task"}
        assert result.confidence == 0.6  # 2 candidates

    def test_multiple_entity_filter(self, router):
        """Filtering by multiple entities should return actions for all of them."""
        intent = ExtractedIntent(entity_mentions=["Task", "Reservation"])
        result = router.route(intent)

        matched_names = {c["name"] for c in result.candidates}
        assert "create_task" in matched_names
        assert "complete_task" in matched_names
        assert "create_reservation" in matched_names
        assert "cancel_reservation" in matched_names
        assert result.confidence == 0.3  # 4+ candidates

    def test_unknown_entity_no_results(self, router):
        """Filtering by an unknown entity should produce no candidates."""
        intent = ExtractedIntent(entity_mentions=["UnknownEntity"])
        result = router.route(intent)

        assert result.action is None
        assert result.candidates == []
        assert result.confidence == 0.0


class TestRolePermissionFiltering:
    """Test Stage 4: role permission filtering."""

    def test_admin_sees_all(self, router):
        """Admin role should pass all role filters."""
        intent = ExtractedIntent(entity_mentions=["Reservation"])
        result = router.route(intent, user_role="admin")

        matched_names = {c["name"] for c in result.candidates}
        assert "create_reservation" in matched_names
        assert "cancel_reservation" in matched_names

    def test_role_filters_out_actions(self, router):
        """A restricted role should not see actions outside its allowed_roles."""
        intent = ExtractedIntent(entity_mentions=["Reservation"])
        result = router.route(intent, user_role="receptionist")

        matched_names = {c["name"] for c in result.candidates}
        # receptionist can create but not cancel reservations
        assert "create_reservation" in matched_names
        assert "cancel_reservation" not in matched_names

    def test_cleaner_limited_actions(self, router):
        """Cleaner role should only see task completion."""
        intent = ExtractedIntent(entity_mentions=["Task"])
        result = router.route(intent, user_role="cleaner")

        matched_names = {c["name"] for c in result.candidates}
        assert "complete_task" in matched_names
        assert "create_task" not in matched_names
        assert result.confidence == 0.95  # single candidate

    def test_open_action_visible_to_all(self, router):
        """Actions with empty allowed_roles should be visible to all roles."""
        intent = ExtractedIntent(action_hints=["query"])
        result = router.route(intent, user_role="cleaner")

        matched_names = {c["name"] for c in result.candidates}
        assert "ontology_query" in matched_names


class TestConfidenceScoring:
    """Test confidence scoring logic."""

    def test_single_candidate_high_confidence(self, router):
        """Single candidate after filtering should have 0.95 confidence."""
        intent = ExtractedIntent(action_hints=["checkout"])
        result = router.route(intent, user_role="admin")

        assert result.confidence == 0.95

    def test_two_candidates_medium_confidence(self, router):
        """Two to three candidates should have 0.6 confidence."""
        intent = ExtractedIntent(entity_mentions=["Task"])
        result = router.route(intent, user_role="admin")

        assert len(result.candidates) == 2
        assert result.confidence == 0.6

    def test_many_candidates_low_confidence(self, router):
        """Four or more candidates should have 0.3 confidence."""
        intent = ExtractedIntent(entity_mentions=["Task", "Reservation"])
        result = router.route(intent, user_role="admin")

        assert len(result.candidates) >= 4
        assert result.confidence == 0.3

    def test_no_candidates_zero_confidence(self, router):
        """No candidates should have 0.0 confidence."""
        intent = ExtractedIntent(entity_mentions=["UnknownEntity"])
        result = router.route(intent)

        assert result.confidence == 0.0
        assert result.action is None


class TestEmptyIntentHandling:
    """Test handling of empty or minimal intents."""

    def test_completely_empty_intent(self, router):
        """An intent with no hints, entities, or params should return all actions as fallback."""
        intent = ExtractedIntent()
        result = router.route(intent, user_role="admin")

        # All 7 actions are candidates as fallback
        assert len(result.candidates) == 7
        assert result.confidence == 0.3  # many candidates

    def test_empty_hints_with_entity(self, router):
        """Empty action_hints with entity_mentions should use entity filtering."""
        intent = ExtractedIntent(entity_mentions=["Guest"])
        result = router.route(intent, user_role="admin")

        matched_names = {c["name"] for c in result.candidates}
        assert "walkin_checkin" in matched_names
        assert "checkout" in matched_names
        assert "create_task" not in matched_names

    def test_empty_intent_role_filtered(self, router):
        """Empty intent should still apply role filtering."""
        intent = ExtractedIntent()
        result = router.route(intent, user_role="cleaner")

        matched_names = {c["name"] for c in result.candidates}
        # Cleaner should only see complete_task and ontology_query (open)
        assert "complete_task" in matched_names
        assert "ontology_query" in matched_names
        assert "walkin_checkin" not in matched_names


class TestNoRegistry:
    """Test behavior when no action registry is provided."""

    def test_no_registry_returns_empty(self):
        """IntentRouter with no registry should return empty results."""
        router = IntentRouter(action_registry=None)
        intent = ExtractedIntent(action_hints=["checkin"])
        result = router.route(intent)

        assert result.action is None
        assert result.candidates == []
        assert result.confidence == 0.0
        assert "No action registry" in result.reasoning

    def test_empty_registry(self):
        """IntentRouter with empty registry should return empty results."""
        registry = ActionRegistry(vector_store=None)
        router = IntentRouter(action_registry=registry)
        intent = ExtractedIntent(action_hints=["checkin"])
        result = router.route(intent)

        assert result.action is None
        assert result.candidates == []
        assert result.confidence == 0.0


class TestStateMachineFeasibility:
    """Test Stage 3: state machine feasibility check."""

    def test_state_machine_filtering_with_mock(self, action_registry):
        """State machine executor should filter infeasible transitions."""
        # Create a mock ontology registry with a state machine
        mock_ontology = MagicMock()
        mock_sm = MagicMock()
        mock_sm.get_valid_transitions.return_value = []  # No valid transitions
        mock_ontology.get_state_machine.return_value = mock_sm

        mock_executor = MagicMock()

        router = IntentRouter(
            action_registry=action_registry,
            ontology_registry=mock_ontology,
            state_machine_executor=mock_executor,
        )

        intent = ExtractedIntent(
            entity_mentions=["Guest"],
            extracted_params={"current_state": "checked_out"},
        )
        result = router.route(intent, user_role="admin")

        # Should still return candidates but with lowered scores
        assert len(result.candidates) > 0

    def test_no_state_machine_keeps_all(self, action_registry):
        """Without state_machine_executor, all candidates should pass."""
        router = IntentRouter(
            action_registry=action_registry,
            state_machine_executor=None,
        )

        intent = ExtractedIntent(entity_mentions=["Guest"])
        result = router.route(intent, user_role="admin")

        matched_names = {c["name"] for c in result.candidates}
        assert "walkin_checkin" in matched_names
        assert "checkout" in matched_names


class TestRoutingReasoning:
    """Test that routing produces meaningful reasoning strings."""

    def test_keyword_match_reasoning(self, router):
        """Keyword match should produce reasoning mentioning keyword match."""
        intent = ExtractedIntent(action_hints=["checkout"])
        result = router.route(intent)

        assert "Keyword match" in result.reasoning

    def test_entity_filter_reasoning(self, router):
        """Entity filter should produce reasoning mentioning entity filter."""
        intent = ExtractedIntent(entity_mentions=["Task"])
        result = router.route(intent)

        assert "Entity filter" in result.reasoning

    def test_role_filter_reasoning(self, router):
        """Role filtering that reduces candidates should mention role filter."""
        intent = ExtractedIntent(entity_mentions=["Reservation"])
        result = router.route(intent, user_role="receptionist")

        assert "Role filter" in result.reasoning


class TestCandidateSorting:
    """Test that candidates are sorted by score."""

    def test_best_candidate_is_first(self, router):
        """The highest scoring candidate should be the selected action."""
        intent = ExtractedIntent(action_hints=["walkin_checkin"])
        result = router.route(intent)

        assert result.action == "walkin_checkin"
        # First candidate should have highest score
        if len(result.candidates) > 1:
            scores = [c["score"] for c in result.candidates]
            assert scores == sorted(scores, reverse=True)

    def test_exact_match_preferred_over_substring(self, router):
        """Exact name match (1.0) should rank above substring match (0.8)."""
        intent = ExtractedIntent(action_hints=["checkout"])
        result = router.route(intent)

        assert result.candidates[0]["name"] == "checkout"
        assert result.candidates[0]["score"] == 1.0
