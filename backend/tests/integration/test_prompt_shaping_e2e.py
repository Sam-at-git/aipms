"""
tests/integration/test_prompt_shaping_e2e.py

Integration test verifying that the PromptShaper pipeline reduces prompt size
when intent inference (Phase 2) is active vs. full injection fallback.
"""
import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass

from core.ai.prompt_shaper import (
    PromptShaper,
    register_role_filter,
    _role_filter_registry,
)


@dataclass
class FakeAction:
    """Minimal action stub."""
    name: str
    entity: str
    category: str


@dataclass
class FakeRoutingResult:
    """Minimal RoutingResult stub."""
    action: str = None
    candidates: list = None
    confidence: float = 0.0
    reasoning: str = ""

    def __post_init__(self):
        if self.candidates is None:
            self.candidates = []


@pytest.fixture(autouse=True)
def clean_role_filters():
    """Reset role filter registry between tests."""
    _role_filter_registry.clear()
    yield
    _role_filter_registry.clear()


def _build_large_action_set():
    """Build a realistic action set with many entities and categories."""
    actions = [
        FakeAction("checkin", "StayRecord", "mutation"),
        FakeAction("checkout", "StayRecord", "mutation"),
        FakeAction("extend_stay", "StayRecord", "mutation"),
        FakeAction("change_room", "StayRecord", "mutation"),
        FakeAction("create_guest", "Guest", "mutation"),
        FakeAction("update_guest", "Guest", "mutation"),
        FakeAction("create_task", "Task", "mutation"),
        FakeAction("assign_task", "Task", "mutation"),
        FakeAction("complete_task", "Task", "mutation"),
        FakeAction("start_task", "Task", "mutation"),
        FakeAction("delete_task", "Task", "mutation"),
        FakeAction("add_payment", "Bill", "billing"),
        FakeAction("adjust_bill", "Bill", "billing"),
        FakeAction("refund_payment", "Bill", "billing"),
        FakeAction("create_reservation", "Reservation", "reservation"),
        FakeAction("cancel_reservation", "Reservation", "reservation"),
        FakeAction("modify_reservation", "Reservation", "reservation"),
        FakeAction("create_employee", "Employee", "admin"),
        FakeAction("update_employee", "Employee", "admin"),
        FakeAction("deactivate_employee", "Employee", "admin"),
        FakeAction("update_price", "RatePlan", "pricing"),
        FakeAction("create_rate_plan", "RatePlan", "pricing"),
        FakeAction("mark_room_clean", "Room", "mutation"),
        FakeAction("mark_room_dirty", "Room", "mutation"),
        FakeAction("update_room_status", "Room", "mutation"),
        FakeAction("ontology_query", "general", "query"),
        FakeAction("semantic_query", "general", "query"),
    ]
    return actions


def _build_registries(actions):
    """Build mock registries from action list."""
    action_map = {a.name: a for a in actions}

    ar = MagicMock()
    ar._search_engine = None  # Prevent Phase 3 discovery from activating
    ar.list_actions.return_value = actions
    ar.get_action.side_effect = lambda name: action_map.get(name)

    # Simple relationship graph
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

    reg = MagicMock()
    reg.get_related_entities.side_effect = lambda e, depth=1: (
        _graph.get(e, {e}) if depth > 0 else {e}
    )

    return reg, ar


class TestPromptShapingPipelineE2E:
    """End-to-end integration test for the shaping pipeline."""

    def test_inference_reduces_action_count_vs_full(self):
        """Phase 2 inference should inject fewer actions than full injection."""
        actions = _build_large_action_set()
        reg, ar = _build_registries(actions)

        shaper = PromptShaper(reg, ar)

        # Full injection (no intent, no role filter)
        full_result = shaper.shape("hello", "manager", intent=None)
        assert full_result.strategy == "full"
        assert full_result.actions is None  # None = all actions

        # Inference with a checkin intent
        intent = FakeRoutingResult(
            action="checkin",
            candidates=[{"name": "checkin", "score": 0.95, "reason": "exact"}],
            confidence=0.95,
        )
        inference_result = shaper.shape("帮客人办入住", "manager", intent=intent)
        assert inference_result.strategy == "inference"

        # Inference should inject a subset, not all
        assert inference_result.actions is not None
        assert len(inference_result.actions) < len(actions)

    def test_inference_reduces_entity_count_vs_full(self):
        """Phase 2 inference should inject fewer entities than full injection."""
        actions = _build_large_action_set()
        reg, ar = _build_registries(actions)

        shaper = PromptShaper(reg, ar)

        # Task-specific intent
        intent = FakeRoutingResult(
            action="create_task",
            candidates=[{"name": "create_task", "score": 0.9, "reason": "exact"}],
            confidence=0.9,
        )
        result = shaper.shape("创建任务", "manager", intent=intent)

        assert result.strategy == "inference"
        assert result.entities is not None
        # Task entity + Room (related) but not Employee, RatePlan, etc.
        entities = set(result.entities)
        assert "Task" in entities
        assert "Room" in entities
        # Entities far from Task should not be included
        assert "RatePlan" not in entities
        assert "Payment" not in entities

    def test_full_pipeline_phase2_then_phase1_fallback(self):
        """Low confidence intent falls through Phase 2 to Phase 1 role filter."""
        actions = _build_large_action_set()
        reg, ar = _build_registries(actions)

        register_role_filter("cleaner", {"admin", "billing", "reservation", "pricing", "query"})

        low_confidence_intent = FakeRoutingResult(
            action="checkin",
            candidates=[{"name": "checkin", "score": 0.1, "reason": "weak"}],
            confidence=0.1,
        )

        shaper = PromptShaper(reg, ar)
        result = shaper.shape("不确定", "cleaner", intent=low_confidence_intent)

        # Phase 2 fails (confidence < 0.3), falls to Phase 1 (role filter)
        assert result.strategy == "role_filter"
        assert "inference_failed" in result.metadata.get("fallback_chain", [])
        # admin actions should be excluded by role filter
        assert "create_employee" not in result.actions

    def test_none_intent_skips_phase2(self):
        """When intent is None, Phase 2 is skipped entirely."""
        actions = _build_large_action_set()
        reg, ar = _build_registries(actions)

        register_role_filter("cleaner", {"admin"})

        shaper = PromptShaper(reg, ar)
        result = shaper.shape("test", "cleaner", intent=None)

        # Should go straight to Phase 1
        assert result.strategy == "role_filter"
        # No inference_failed in fallback chain since Phase 2 was skipped
        assert "inference_failed" not in result.metadata.get("fallback_chain", [])
