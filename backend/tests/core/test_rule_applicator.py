"""
Tests for SPEC-11: RuleApplicator

Tests:
- Alias replacement (single value, list value, no match)
- Expansion rules (keyword match, no match, field mismatch)
- No-op when no matching rules exist
- Integration with BusinessRuleRegistry
"""
import pytest

from core.ontology.business_rules import (
    BusinessRule,
    BusinessRuleRegistry,
    RuleType,
)
from core.ontology.query import FilterClause, FilterOperator
from core.ontology.rule_applicator import RuleApplicator


@pytest.fixture
def fresh_registry():
    """Create a fresh BusinessRuleRegistry with cleared state."""
    reg = BusinessRuleRegistry()
    # Save original state
    original_rules = dict(reg._rules)
    original_by_entity = dict(reg._rules_by_entity)
    original_by_type = dict(reg._rules_by_type)

    # Clear for test
    reg._rules.clear()
    reg._rules_by_entity.clear()
    reg._rules_by_type.clear()

    yield reg

    # Restore original state
    reg._rules.clear()
    reg._rules_by_entity.clear()
    reg._rules_by_type.clear()
    reg._rules.update(original_rules)
    reg._rules_by_entity.update(original_by_entity)
    reg._rules_by_type.update(original_by_type)


@pytest.fixture
def registry_with_alias_rules(fresh_registry):
    """Registry with alias rules for Room status and Reservation status."""
    fresh_registry.register(BusinessRule(
        id="room_status_aliases",
        name="Room status aliases",
        rule_type=RuleType.ALIAS_DEFINITION,
        entity="Room",
        alias_mapping={
            "净房": "vacant_clean",
            "空净房": "vacant_clean",
            "脏房": "vacant_dirty",
            "空脏房": "vacant_dirty",
            "已入住": "occupied",
            "入住": "occupied",
            "维修中": "out_of_order",
            "停用": "out_of_order",
        },
        description="Room status Chinese-English alias mapping",
    ))

    fresh_registry.register(BusinessRule(
        id="reservation_status_aliases",
        name="Reservation status aliases",
        rule_type=RuleType.ALIAS_DEFINITION,
        entity="Reservation",
        alias_mapping={
            "已确认": "confirmed",
            "待确认": "pending",
            "已取消": "cancelled",
        },
        description="Reservation status alias mapping",
    ))

    return fresh_registry


@pytest.fixture
def registry_with_expansion_rules(fresh_registry):
    """Registry with expansion rules for Room."""
    fresh_registry.register(BusinessRule(
        id="vacant_room_expansion",
        name="Vacant room query expansion",
        rule_type=RuleType.QUERY_EXPANSION,
        entity="Room",
        trigger_keywords=["空闲", "可住", "可用", "空房", "空闲房间"],
        condition={
            "field": "status",
            "operator": "in",
            "value": ["vacant_clean", "vacant_dirty"],
        },
        description="Vacant room query should include both clean and dirty",
    ))

    return fresh_registry


@pytest.fixture
def registry_with_both(registry_with_alias_rules):
    """Registry with both alias and expansion rules."""
    registry_with_alias_rules.register(BusinessRule(
        id="vacant_room_expansion",
        name="Vacant room query expansion",
        rule_type=RuleType.QUERY_EXPANSION,
        entity="Room",
        trigger_keywords=["空闲", "可住", "可用", "空房"],
        condition={
            "field": "status",
            "operator": "in",
            "value": ["vacant_clean", "vacant_dirty"],
        },
        description="Vacant room query should include both clean and dirty",
    ))

    return registry_with_alias_rules


class TestApplyAliasRules:
    """Test alias replacement via apply_alias_rules."""

    def test_alias_replaces_known_value(self, registry_with_alias_rules):
        applicator = RuleApplicator(registry_with_alias_rules)
        result = applicator.apply_alias_rules("Room", "status", "净房")
        assert result == "vacant_clean"

    def test_alias_replaces_another_value(self, registry_with_alias_rules):
        applicator = RuleApplicator(registry_with_alias_rules)
        result = applicator.apply_alias_rules("Room", "status", "脏房")
        assert result == "vacant_dirty"

    def test_alias_replaces_occupied(self, registry_with_alias_rules):
        applicator = RuleApplicator(registry_with_alias_rules)
        result = applicator.apply_alias_rules("Room", "status", "已入住")
        assert result == "occupied"

    def test_alias_no_match_returns_original(self, registry_with_alias_rules):
        applicator = RuleApplicator(registry_with_alias_rules)
        result = applicator.apply_alias_rules("Room", "status", "vacant_clean")
        assert result == "vacant_clean"

    def test_alias_different_entity(self, registry_with_alias_rules):
        applicator = RuleApplicator(registry_with_alias_rules)
        result = applicator.apply_alias_rules("Reservation", "status", "已确认")
        assert result == "confirmed"

    def test_alias_entity_without_rules(self, registry_with_alias_rules):
        applicator = RuleApplicator(registry_with_alias_rules)
        result = applicator.apply_alias_rules("Guest", "name", "张三")
        assert result == "张三"

    def test_alias_none_value(self, registry_with_alias_rules):
        applicator = RuleApplicator(registry_with_alias_rules)
        result = applicator.apply_alias_rules("Room", "status", None)
        assert result is None

    def test_alias_list_value(self, registry_with_alias_rules):
        applicator = RuleApplicator(registry_with_alias_rules)
        result = applicator.apply_alias_rules("Room", "status", ["净房", "脏房"])
        assert result == ["vacant_clean", "vacant_dirty"]

    def test_alias_list_mixed(self, registry_with_alias_rules):
        """List with mix of alias and standard values."""
        applicator = RuleApplicator(registry_with_alias_rules)
        result = applicator.apply_alias_rules(
            "Room", "status", ["净房", "occupied", "维修中"]
        )
        assert result == ["vacant_clean", "occupied", "out_of_order"]

    def test_alias_non_string_value(self, registry_with_alias_rules):
        applicator = RuleApplicator(registry_with_alias_rules)
        result = applicator.apply_alias_rules("Room", "status", 42)
        assert result == 42

    def test_alias_empty_registry(self, fresh_registry):
        applicator = RuleApplicator(fresh_registry)
        result = applicator.apply_alias_rules("Room", "status", "净房")
        assert result == "净房"


class TestApplyExpansionRules:
    """Test query expansion via apply_expansion_rules."""

    def test_expansion_keyword_match(self, registry_with_expansion_rules):
        applicator = RuleApplicator(registry_with_expansion_rules)
        filters = [
            FilterClause(field="status", operator=FilterOperator.EQ, value="空闲")
        ]
        result = applicator.apply_expansion_rules("Room", filters)

        assert len(result) == 1
        assert result[0].field == "status"
        assert result[0].operator == FilterOperator.IN
        assert result[0].value == ["vacant_clean", "vacant_dirty"]

    def test_expansion_different_keyword(self, registry_with_expansion_rules):
        applicator = RuleApplicator(registry_with_expansion_rules)
        filters = [
            FilterClause(field="status", operator=FilterOperator.EQ, value="可用")
        ]
        result = applicator.apply_expansion_rules("Room", filters)

        assert len(result) == 1
        assert result[0].operator == FilterOperator.IN
        assert result[0].value == ["vacant_clean", "vacant_dirty"]

    def test_expansion_no_match_returns_original(self, registry_with_expansion_rules):
        applicator = RuleApplicator(registry_with_expansion_rules)
        original = FilterClause(
            field="status", operator=FilterOperator.EQ, value="occupied"
        )
        result = applicator.apply_expansion_rules("Room", [original])

        assert len(result) == 1
        assert result[0] is original

    def test_expansion_preserves_non_matching_filters(
        self, registry_with_expansion_rules
    ):
        applicator = RuleApplicator(registry_with_expansion_rules)
        filters = [
            FilterClause(
                field="room_number", operator=FilterOperator.EQ, value="201"
            ),
            FilterClause(field="status", operator=FilterOperator.EQ, value="空闲"),
        ]
        result = applicator.apply_expansion_rules("Room", filters)

        assert len(result) == 2
        # First filter unchanged
        assert result[0].field == "room_number"
        assert result[0].value == "201"
        # Second filter expanded
        assert result[1].field == "status"
        assert result[1].operator == FilterOperator.IN

    def test_expansion_wrong_entity(self, registry_with_expansion_rules):
        applicator = RuleApplicator(registry_with_expansion_rules)
        filters = [
            FilterClause(field="status", operator=FilterOperator.EQ, value="空闲")
        ]
        result = applicator.apply_expansion_rules("Guest", filters)

        assert len(result) == 1
        # No expansion for Guest entity - filter unchanged
        assert result[0].value == "空闲"
        assert result[0].operator == FilterOperator.EQ

    def test_expansion_empty_filters(self, registry_with_expansion_rules):
        applicator = RuleApplicator(registry_with_expansion_rules)
        result = applicator.apply_expansion_rules("Room", [])
        assert result == []

    def test_expansion_none_value_filter(self, registry_with_expansion_rules):
        applicator = RuleApplicator(registry_with_expansion_rules)
        filters = [
            FilterClause(field="status", operator=FilterOperator.IS_NULL, value=None)
        ]
        result = applicator.apply_expansion_rules("Room", filters)

        assert len(result) == 1
        # None value - no expansion
        assert result[0].operator == FilterOperator.IS_NULL

    def test_expansion_empty_registry(self, fresh_registry):
        applicator = RuleApplicator(fresh_registry)
        original = FilterClause(
            field="status", operator=FilterOperator.EQ, value="空闲"
        )
        result = applicator.apply_expansion_rules("Room", [original])

        assert len(result) == 1
        assert result[0] is original

    def test_expansion_field_mismatch_no_expand(self, registry_with_expansion_rules):
        """Expansion rule has field=status, but filter is on a different field."""
        applicator = RuleApplicator(registry_with_expansion_rules)
        filters = [
            FilterClause(
                field="room_type", operator=FilterOperator.EQ, value="空闲"
            )
        ]
        result = applicator.apply_expansion_rules("Room", filters)

        assert len(result) == 1
        # Field mismatch - no expansion
        assert result[0].value == "空闲"
        assert result[0].operator == FilterOperator.EQ

    def test_expansion_case_insensitive_keyword(self, fresh_registry):
        """Trigger keywords should match case-insensitively."""
        fresh_registry.register(BusinessRule(
            id="test_expansion",
            name="Test expansion",
            rule_type=RuleType.QUERY_EXPANSION,
            entity="Item",
            trigger_keywords=["Active", "LIVE"],
            condition={
                "field": "status",
                "operator": "in",
                "value": ["active", "pending"],
            },
        ))

        applicator = RuleApplicator(fresh_registry)
        filters = [
            FilterClause(field="status", operator=FilterOperator.EQ, value="active")
        ]
        result = applicator.apply_expansion_rules("Item", filters)

        assert len(result) == 1
        assert result[0].operator == FilterOperator.IN
        assert result[0].value == ["active", "pending"]


class TestCombinedRules:
    """Test scenarios using both alias and expansion rules together."""

    def test_alias_then_expansion(self, registry_with_both):
        """Typical pipeline: alias first, then expansion."""
        applicator = RuleApplicator(registry_with_both)

        # Step 1: apply alias
        value = applicator.apply_alias_rules("Room", "status", "净房")
        assert value == "vacant_clean"

        # Step 2: apply expansion (no expansion for standard values)
        filters = [
            FilterClause(field="status", operator=FilterOperator.EQ, value=value)
        ]
        result = applicator.apply_expansion_rules("Room", filters)
        assert result[0].value == "vacant_clean"
        assert result[0].operator == FilterOperator.EQ

    def test_expansion_takes_priority_over_alias(self, registry_with_both):
        """When value is a trigger keyword, expansion should replace it."""
        applicator = RuleApplicator(registry_with_both)

        filters = [
            FilterClause(field="status", operator=FilterOperator.EQ, value="空闲")
        ]
        result = applicator.apply_expansion_rules("Room", filters)

        assert result[0].operator == FilterOperator.IN
        assert "vacant_clean" in result[0].value
        assert "vacant_dirty" in result[0].value


class TestRuleApplicatorInit:
    """Test RuleApplicator initialization."""

    def test_default_registry(self):
        """Uses singleton when no registry provided."""
        applicator = RuleApplicator()
        assert applicator._registry is BusinessRuleRegistry()

    def test_custom_registry(self, fresh_registry):
        """Accepts custom registry."""
        applicator = RuleApplicator(fresh_registry)
        assert applicator._registry is fresh_registry

    def test_returns_new_list_from_expansion(self, fresh_registry):
        """apply_expansion_rules returns a new list, not mutating the input."""
        applicator = RuleApplicator(fresh_registry)
        original_filters = [
            FilterClause(field="status", operator=FilterOperator.EQ, value="active")
        ]
        result = applicator.apply_expansion_rules("Room", original_filters)
        assert result is not original_filters
