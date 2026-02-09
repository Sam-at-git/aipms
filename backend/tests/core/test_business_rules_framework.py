"""
Tests for SPEC-05: Business rules framework separation
"""
import pytest
from core.ontology.business_rules import (
    BusinessRule,
    BusinessRuleRegistry,
    RuleType,
    business_rules,
    init_default_business_rules,
)


class TestBusinessRuleRegistryFramework:
    """Test that BusinessRuleRegistry is a clean framework class"""

    def test_registry_is_singleton(self):
        r1 = BusinessRuleRegistry()
        r2 = BusinessRuleRegistry()
        assert r1 is r2

    def test_register_and_get_rule(self):
        reg = BusinessRuleRegistry()
        # Clear any existing rules
        reg._rules.clear()
        reg._rules_by_entity.clear()
        reg._rules_by_type.clear()

        rule = BusinessRule(
            id="test_rule",
            name="Test Rule",
            rule_type=RuleType.VALIDATION,
            entity="TestEntity",
            description="A test rule",
        )
        reg.register(rule)
        assert reg.get("test_rule") is rule
        assert len(reg.get_by_entity("TestEntity")) == 1

        # Cleanup
        reg._rules.clear()
        reg._rules_by_entity.clear()
        reg._rules_by_type.clear()

    def test_rule_type_enum(self):
        assert RuleType.QUERY_EXPANSION.value == "query_expansion"
        assert RuleType.VALUE_MAPPING.value == "value_mapping"
        assert RuleType.ALIAS_DEFINITION.value == "alias_definition"
        assert RuleType.VALIDATION.value == "validation"


class TestHotelBusinessRules:
    """Test that hotel-specific rules are in app/hotel/business_rules.py"""

    def test_init_hotel_business_rules_importable(self):
        from app.hotel.business_rules import init_hotel_business_rules
        assert callable(init_hotel_business_rules)

    def test_init_default_delegates_to_hotel(self):
        """init_default_business_rules should delegate to hotel layer"""
        reg = BusinessRuleRegistry()
        reg._rules.clear()
        reg._rules_by_entity.clear()
        reg._rules_by_type.clear()

        init_default_business_rules()

        # Should have registered hotel-specific rules
        assert reg.get("vacant_room_expansion") is not None
        assert reg.get("guest_name_aliases") is not None
        assert reg.get("reservation_status_aliases") is not None

        # Cleanup
        reg._rules.clear()
        reg._rules_by_entity.clear()
        reg._rules_by_type.clear()

    def test_hotel_rules_are_not_in_core(self):
        """Core business_rules.py should not contain hotel-specific rule text"""
        import inspect
        import core.ontology.business_rules as module
        source = inspect.getsource(module.init_default_business_rules)
        # Should NOT contain hotel-specific keywords
        assert "vacant_room_expansion" not in source
        assert "guest_name_aliases" not in source
        assert "净房" not in source
