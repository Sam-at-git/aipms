"""
tests/core/test_prompt_shaper.py

Unit tests for PromptShaper — prompt schema selection strategy dispatcher.
"""
import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass

from core.ai.prompt_shaper import (
    PromptShaper,
    ShapingResult,
    register_role_filter,
    _role_filter_registry,
)


@dataclass
class FakeAction:
    """Minimal action stub for testing."""
    name: str
    entity: str
    category: str


@dataclass
class FakeRoutingResult:
    """Minimal RoutingResult stub for testing Phase 2."""
    action: str = None
    candidates: list = None
    confidence: float = 0.0
    reasoning: str = ""

    def __post_init__(self):
        if self.candidates is None:
            self.candidates = []


@pytest.fixture(autouse=True)
def clean_role_filter_registry():
    """Reset the module-level role filter registry between tests."""
    _role_filter_registry.clear()
    yield
    _role_filter_registry.clear()


@pytest.fixture
def mock_registry():
    """Mock OntologyRegistry."""
    reg = MagicMock()
    reg.get_related_entities.side_effect = AttributeError("not implemented yet")
    return reg


@pytest.fixture
def mock_action_registry():
    """Mock ActionRegistry with hotel-like actions."""
    ar = MagicMock()
    ar._search_engine = None  # Prevent Phase 3 discovery from activating
    ar.list_actions.return_value = [
        FakeAction("checkin", "StayRecord", "mutation"),
        FakeAction("checkout", "StayRecord", "mutation"),
        FakeAction("create_guest", "Guest", "mutation"),
        FakeAction("create_task", "Task", "mutation"),
        FakeAction("complete_task", "Task", "mutation"),
        FakeAction("add_payment", "Bill", "billing"),
        FakeAction("adjust_bill", "Bill", "billing"),
        FakeAction("create_reservation", "Reservation", "reservation"),
        FakeAction("create_employee", "Employee", "admin"),
        FakeAction("update_price", "RatePlan", "pricing"),
        FakeAction("ontology_query", "general", "query"),
    ]
    return ar


class TestShapingResult:
    """Test ShapingResult dataclass."""

    def test_defaults(self):
        result = ShapingResult()
        assert result.actions is None
        assert result.entities is None
        assert result.include_query_schema is True
        assert result.strategy == "full"
        assert result.metadata == {}

    def test_with_values(self):
        result = ShapingResult(
            actions=["checkin"],
            entities=["Guest", "Room"],
            include_query_schema=False,
            strategy="inference",
            metadata={"key": "val"},
        )
        assert result.actions == ["checkin"]
        assert result.entities == ["Guest", "Room"]
        assert result.include_query_schema is False
        assert result.strategy == "inference"


class TestRegisterRoleFilter:
    """Test module-level register_role_filter()."""

    def test_register_and_read(self):
        register_role_filter("cleaner", {"admin", "billing"})
        assert "cleaner" in _role_filter_registry
        assert _role_filter_registry["cleaner"] == {"admin", "billing"}

    def test_overwrite(self):
        register_role_filter("cleaner", {"admin"})
        register_role_filter("cleaner", {"admin", "billing"})
        assert _role_filter_registry["cleaner"] == {"admin", "billing"}


class TestPromptShaperRoleFilter:
    """Test Phase 1: role-based filtering."""

    def test_role_filter_cleaner(self, mock_registry, mock_action_registry):
        """Cleaner should not see billing/reservation/admin/pricing/query actions."""
        register_role_filter("cleaner", {
            "admin", "billing", "reservation", "pricing", "query",
        })
        shaper = PromptShaper(mock_registry, mock_action_registry)
        result = shaper.shape("创建清洁任务", "cleaner")

        assert result.strategy == "role_filter"
        # Only mutation actions remain (checkin, checkout, create_guest, create_task, complete_task)
        assert "create_task" in result.actions
        assert "complete_task" in result.actions
        assert "checkin" in result.actions
        # Excluded:
        assert "add_payment" not in result.actions
        assert "create_reservation" not in result.actions
        assert "create_employee" not in result.actions
        assert "update_price" not in result.actions
        assert "ontology_query" not in result.actions

    def test_role_filter_receptionist(self, mock_registry, mock_action_registry):
        """Receptionist should not see admin/pricing/employee_management actions."""
        register_role_filter("receptionist", {"admin", "pricing"})
        shaper = PromptShaper(mock_registry, mock_action_registry)
        result = shaper.shape("帮客人办入住", "receptionist")

        assert result.strategy == "role_filter"
        assert "checkin" in result.actions
        assert "add_payment" in result.actions  # billing allowed
        assert "create_reservation" in result.actions  # reservation allowed
        assert "create_employee" not in result.actions  # admin excluded
        assert "update_price" not in result.actions  # pricing excluded

    def test_role_filter_manager_no_filter(self, mock_registry, mock_action_registry):
        """Manager has no filter registered — gets full injection."""
        shaper = PromptShaper(mock_registry, mock_action_registry)
        result = shaper.shape("查看今日营收", "manager")

        assert result.strategy == "full"
        assert result.actions is None  # None = inject all
        assert result.entities is None

    def test_role_filter_unknown_role(self, mock_registry, mock_action_registry):
        """Unknown role with no filter → full injection."""
        shaper = PromptShaper(mock_registry, mock_action_registry)
        result = shaper.shape("hello", "unknown_role")

        assert result.strategy == "full"
        assert result.actions is None
        assert result.entities is None

    def test_metadata_contains_counts(self, mock_registry, mock_action_registry):
        """Metadata should include action counts when filtering is applied."""
        register_role_filter("cleaner", {"admin", "billing", "reservation", "pricing", "query"})
        shaper = PromptShaper(mock_registry, mock_action_registry)
        result = shaper.shape("test", "cleaner")

        assert "actions_total" in result.metadata
        assert "actions_injected" in result.metadata
        assert "actions_removed" in result.metadata
        assert result.metadata["actions_total"] == 11
        assert result.metadata["actions_removed"] > 0

    def test_entities_derived_from_actions(self, mock_registry, mock_action_registry):
        """Entities should be derived from the remaining actions' entity fields."""
        register_role_filter("cleaner", {"admin", "billing", "reservation", "pricing", "query"})
        shaper = PromptShaper(mock_registry, mock_action_registry)
        result = shaper.shape("test", "cleaner")

        # After filtering, remaining actions are on StayRecord, Guest, Task
        assert result.entities is not None
        entities_set = set(result.entities)
        assert "StayRecord" in entities_set
        assert "Guest" in entities_set
        assert "Task" in entities_set
        # Excluded entities:
        assert "Bill" not in entities_set
        assert "Reservation" not in entities_set
        assert "Employee" not in entities_set


class TestPromptShaperFallbackChain:
    """Test the full fallback chain."""

    def test_fallback_to_full_when_no_filters(self, mock_registry, mock_action_registry):
        """With no role filters registered, shape() should return full strategy."""
        shaper = PromptShaper(mock_registry, mock_action_registry)
        result = shaper.shape("test", "manager")

        assert result.strategy == "full"
        assert result.actions is None
        assert result.entities is None
        assert result.include_query_schema is True

    def test_shaping_result_always_has_include_query_schema(self, mock_registry, mock_action_registry):
        """Phase 1 always includes query schema (filtering by Phase 2 will change this)."""
        register_role_filter("cleaner", {"admin"})
        shaper = PromptShaper(mock_registry, mock_action_registry)
        result = shaper.shape("test", "cleaner")
        assert result.include_query_schema is True

    def test_no_action_registry(self, mock_registry):
        """When no ActionRegistry is available, role filter returns empty actions."""
        register_role_filter("cleaner", {"admin"})
        shaper = PromptShaper(mock_registry, action_registry=None)
        result = shaper.shape("test", "cleaner")

        # No actions available → filtered list is empty → all actions removed
        assert result.strategy == "role_filter"
        assert result.actions == []


# ============================================================
# Phase 2: Intent-Driven Schema Inference tests (SPEC-P03)
# ============================================================


@pytest.fixture
def registry_with_relationships():
    """OntologyRegistry mock that supports get_related_entities."""
    reg = MagicMock()

    # Define a relationship graph for hotel entities
    _graph = {
        "StayRecord": {"StayRecord", "Guest", "Room", "Bill"},
        "Guest": {"Guest", "Reservation", "StayRecord"},
        "Room": {"Room", "RoomType", "StayRecord"},
        "Bill": {"Bill", "StayRecord", "Payment"},
        "Reservation": {"Reservation", "Guest"},
        "Task": {"Task", "Room"},
        "Employee": {"Employee"},
        "RoomType": {"RoomType", "Room"},
        "RatePlan": {"RatePlan"},
        "Payment": {"Payment", "Bill"},
    }

    def _get_related(entity_name, depth=1):
        if depth <= 0:
            return {entity_name}
        return _graph.get(entity_name, {entity_name})

    reg.get_related_entities.side_effect = _get_related
    return reg


@pytest.fixture
def action_registry_with_lookup():
    """ActionRegistry mock that supports list_actions() and get_action()."""
    actions = [
        FakeAction("checkin", "StayRecord", "mutation"),
        FakeAction("checkout", "StayRecord", "mutation"),
        FakeAction("create_guest", "Guest", "mutation"),
        FakeAction("create_task", "Task", "mutation"),
        FakeAction("complete_task", "Task", "mutation"),
        FakeAction("add_payment", "Bill", "billing"),
        FakeAction("adjust_bill", "Bill", "billing"),
        FakeAction("create_reservation", "Reservation", "reservation"),
        FakeAction("create_employee", "Employee", "admin"),
        FakeAction("update_price", "RatePlan", "pricing"),
        FakeAction("ontology_query", "general", "query"),
        FakeAction("semantic_query", "general", "query"),
    ]

    action_map = {a.name: a for a in actions}

    ar = MagicMock()
    ar._search_engine = None  # Prevent Phase 3 discovery from activating
    ar.list_actions.return_value = actions
    ar.get_action.side_effect = lambda name: action_map.get(name)
    return ar


class TestIntentInference:
    """Test Phase 2: intent-driven schema inference (SPEC-P03)."""

    def test_inference_checkin_intent(
        self, registry_with_relationships, action_registry_with_lookup,
    ):
        """Checkin intent should include Guest, Room, StayRecord, RoomType entities."""
        intent = FakeRoutingResult(
            action="checkin",
            candidates=[
                {"name": "checkin", "score": 0.95, "reason": "exact match"},
            ],
            confidence=0.95,
        )

        shaper = PromptShaper(registry_with_relationships, action_registry_with_lookup)
        result = shaper.shape("帮客人办入住", "receptionist", intent=intent)

        assert result.strategy == "inference"
        entities = set(result.entities)
        # StayRecord is the checkin action entity, expanded to include
        # Guest, Room, Bill via relationships
        assert "StayRecord" in entities
        assert "Guest" in entities
        assert "Room" in entities
        assert "Bill" in entities
        # checkin action should be included
        assert "checkin" in result.actions

    def test_inference_billing_intent(
        self, registry_with_relationships, action_registry_with_lookup,
    ):
        """Billing intent should include Bill, StayRecord entities."""
        intent = FakeRoutingResult(
            action="add_payment",
            candidates=[
                {"name": "add_payment", "score": 0.9, "reason": "keyword match"},
                {"name": "adjust_bill", "score": 0.6, "reason": "entity match"},
            ],
            confidence=0.6,
        )

        shaper = PromptShaper(registry_with_relationships, action_registry_with_lookup)
        result = shaper.shape("收款", "receptionist", intent=intent)

        assert result.strategy == "inference"
        entities = set(result.entities)
        assert "Bill" in entities
        assert "StayRecord" in entities
        # Payment is related to Bill
        assert "Payment" in entities

    def test_inference_query_intent(
        self, registry_with_relationships, action_registry_with_lookup,
    ):
        """Query intent should set include_query_schema=True."""
        intent = FakeRoutingResult(
            action="ontology_query",
            candidates=[
                {"name": "ontology_query", "score": 0.9, "reason": "keyword match"},
            ],
            confidence=0.9,
        )

        shaper = PromptShaper(registry_with_relationships, action_registry_with_lookup)
        result = shaper.shape("查询今日入住", "manager", intent=intent)

        assert result.strategy == "inference"
        assert result.include_query_schema is True

    def test_inference_mutation_intent(
        self, registry_with_relationships, action_registry_with_lookup,
    ):
        """Non-query intent should set include_query_schema=False."""
        intent = FakeRoutingResult(
            action="checkin",
            candidates=[
                {"name": "checkin", "score": 0.95, "reason": "exact match"},
            ],
            confidence=0.95,
        )

        shaper = PromptShaper(registry_with_relationships, action_registry_with_lookup)
        result = shaper.shape("办入住", "receptionist", intent=intent)

        assert result.strategy == "inference"
        assert result.include_query_schema is False

    def test_inference_low_confidence_fallback(
        self, registry_with_relationships, action_registry_with_lookup,
    ):
        """Confidence < 0.3 should fall through to Phase 1."""
        intent = FakeRoutingResult(
            action="checkin",
            candidates=[
                {"name": "checkin", "score": 0.2, "reason": "weak match"},
            ],
            confidence=0.2,
        )

        shaper = PromptShaper(registry_with_relationships, action_registry_with_lookup)
        # No role filter registered for manager → should fall to "full"
        result = shaper.shape("不确定的请求", "manager", intent=intent)

        assert result.strategy == "full"
        assert "inference_failed" in result.metadata.get("fallback_chain", [])

    def test_inference_no_candidates_fallback(
        self, registry_with_relationships, action_registry_with_lookup,
    ):
        """Empty candidates should fall through to Phase 1."""
        intent = FakeRoutingResult(
            action=None,
            candidates=[],
            confidence=0.5,
        )

        shaper = PromptShaper(registry_with_relationships, action_registry_with_lookup)
        result = shaper.shape("模糊的请求", "manager", intent=intent)

        assert result.strategy == "full"
        assert "inference_failed" in result.metadata.get("fallback_chain", [])

    def test_inference_includes_related_entities(
        self, registry_with_relationships, action_registry_with_lookup,
    ):
        """Relationship expansion should bring in related entities."""
        intent = FakeRoutingResult(
            action="create_task",
            candidates=[
                {"name": "create_task", "score": 0.95, "reason": "exact match"},
            ],
            confidence=0.95,
        )

        shaper = PromptShaper(registry_with_relationships, action_registry_with_lookup)
        result = shaper.shape("创建清洁任务", "receptionist", intent=intent)

        assert result.strategy == "inference"
        entities = set(result.entities)
        # Task is the primary entity, Room is related via depth=1
        assert "Task" in entities
        assert "Room" in entities

    def test_inference_respects_role_filter(
        self, registry_with_relationships, action_registry_with_lookup,
    ):
        """Phase 2 should still apply role-based category exclusions."""
        register_role_filter("cleaner", {"admin", "billing", "reservation", "pricing"})

        # Intent matches create_task (mutation category, allowed for cleaner)
        intent = FakeRoutingResult(
            action="create_task",
            candidates=[
                {"name": "create_task", "score": 0.9, "reason": "exact match"},
            ],
            confidence=0.9,
        )

        shaper = PromptShaper(registry_with_relationships, action_registry_with_lookup)
        result = shaper.shape("创建清洁任务", "cleaner", intent=intent)

        assert result.strategy == "inference"
        # admin category actions should be excluded by role filter
        assert "create_employee" not in result.actions
        # billing category should be excluded
        assert "add_payment" not in result.actions
        # create_task itself should be included
        assert "create_task" in result.actions

    def test_inference_metadata_content(
        self, registry_with_relationships, action_registry_with_lookup,
    ):
        """Inference result metadata should contain diagnostic info."""
        intent = FakeRoutingResult(
            action="checkin",
            candidates=[
                {"name": "checkin", "score": 0.95, "reason": "exact match"},
            ],
            confidence=0.95,
        )

        shaper = PromptShaper(registry_with_relationships, action_registry_with_lookup)
        result = shaper.shape("办入住", "manager", intent=intent)

        assert result.metadata["confidence"] == 0.95
        assert "checkin" in result.metadata["candidate_actions"]
        assert "StayRecord" in result.metadata["candidate_entities"]
        assert len(result.metadata["expanded_entities"]) > len(
            result.metadata["candidate_entities"]
        )
        assert "actions_total" in result.metadata
        assert "actions_injected" in result.metadata

    def test_inference_takes_priority_over_role_filter(
        self, registry_with_relationships, action_registry_with_lookup,
    ):
        """When Phase 2 succeeds, it should be used instead of Phase 1."""
        register_role_filter("cleaner", {"admin", "billing"})

        intent = FakeRoutingResult(
            action="create_task",
            candidates=[
                {"name": "create_task", "score": 0.9, "reason": "exact match"},
            ],
            confidence=0.9,
        )

        shaper = PromptShaper(registry_with_relationships, action_registry_with_lookup)
        result = shaper.shape("创建任务", "cleaner", intent=intent)

        # Phase 2 wins over Phase 1
        assert result.strategy == "inference"

    def test_inference_semantic_query_sets_query_schema(
        self, registry_with_relationships, action_registry_with_lookup,
    ):
        """semantic_query in candidates should trigger include_query_schema."""
        intent = FakeRoutingResult(
            action="semantic_query",
            candidates=[
                {"name": "semantic_query", "score": 0.8, "reason": "keyword match"},
            ],
            confidence=0.8,
        )

        shaper = PromptShaper(registry_with_relationships, action_registry_with_lookup)
        result = shaper.shape("查询客人信息", "manager", intent=intent)

        assert result.strategy == "inference"
        assert result.include_query_schema is True
