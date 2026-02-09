"""
core/ontology/rule_applicator.py

RuleApplicator - applies business rules to query values and filters.

Responsibilities:
1. apply_alias_rules: replaces alias values with standard values
   (e.g. "净房" -> "vacant_clean")
2. apply_expansion_rules: auto-expands query conditions based on trigger keywords
   (e.g. "空闲" triggers expansion to status in [vacant_clean, vacant_dirty])

Reads rules from BusinessRuleRegistry using RuleType.ALIAS_DEFINITION
and RuleType.QUERY_EXPANSION.
"""
from typing import Any, Dict, List, Optional, Tuple

from core.ontology.business_rules import (
    BusinessRule,
    BusinessRuleRegistry,
    RuleType,
)
from core.ontology.query import FilterClause, FilterOperator


class RuleApplicator:
    """
    Applies business rules to normalize query values and expand filters.

    Usage:
        applicator = RuleApplicator()

        # Alias replacement
        normalized = applicator.apply_alias_rules("Room", "status", "净房")
        # -> "vacant_clean"

        # Query expansion
        filters = applicator.apply_expansion_rules("Room", [
            FilterClause(field="status", operator=FilterOperator.EQ, value="空闲")
        ])
        # -> [FilterClause(field="status", operator=FilterOperator.IN,
        #                   value=["vacant_clean", "vacant_dirty"])]
    """

    def __init__(self, registry: Optional[BusinessRuleRegistry] = None):
        """
        Initialize RuleApplicator.

        Args:
            registry: BusinessRuleRegistry instance. If None, uses the singleton.
        """
        self._registry = registry or BusinessRuleRegistry()

    def apply_alias_rules(self, entity: str, field: str, value: Any) -> Any:
        """
        Replace alias values with their standard counterparts.

        Looks up ALIAS_DEFINITION rules for the given entity and checks
        if the value matches any alias in any rule's alias_mapping.

        Args:
            entity: Entity name (e.g. "Room", "Guest")
            field: Field name (e.g. "status")
            value: The value to potentially replace

        Returns:
            The standard value if an alias match is found, otherwise the
            original value unchanged.
        """
        if value is None:
            return value

        # Get all alias rules for this entity
        alias_rules = self._get_rules(entity, RuleType.ALIAS_DEFINITION)

        if not alias_rules:
            return value

        # Handle list values: apply alias replacement to each element
        if isinstance(value, list):
            return [self._resolve_alias(alias_rules, v) for v in value]

        return self._resolve_alias(alias_rules, value)

    def apply_expansion_rules(
        self, entity: str, filters: List[FilterClause]
    ) -> List[FilterClause]:
        """
        Auto-expand query filters based on QUERY_EXPANSION rules.

        For each filter, checks if its value matches any trigger keyword
        in an expansion rule. If so, replaces the filter with the
        expanded condition from the rule.

        Args:
            entity: Entity name (e.g. "Room")
            filters: List of FilterClause to potentially expand

        Returns:
            New list of FilterClause with expansions applied. Filters that
            don't match any expansion rule are returned unchanged.
        """
        expansion_rules = self._get_rules(entity, RuleType.QUERY_EXPANSION)

        if not expansion_rules:
            return list(filters)

        result: List[FilterClause] = []

        for f in filters:
            expanded = self._try_expand(f, expansion_rules)
            if expanded is not None:
                result.append(expanded)
            else:
                result.append(f)

        return result

    def _get_rules(self, entity: str, rule_type: RuleType) -> List[BusinessRule]:
        """Get rules matching both entity and rule type."""
        entity_rules = self._registry.get_by_entity(entity)
        return [r for r in entity_rules if r.rule_type == rule_type]

    def _resolve_alias(self, alias_rules: List[BusinessRule], value: Any) -> Any:
        """
        Check a single value against all alias rules.

        Returns the mapped standard value if found, otherwise the original.
        """
        if not isinstance(value, str):
            return value

        for rule in alias_rules:
            if value in rule.alias_mapping:
                return rule.alias_mapping[value]

        return value

    def _try_expand(
        self, filter_clause: FilterClause, expansion_rules: List[BusinessRule]
    ) -> Optional[FilterClause]:
        """
        Try to expand a single filter clause using expansion rules.

        Matches filter value against trigger_keywords. If matched, returns
        a new FilterClause with the operator and value from the rule's condition.

        Returns None if no expansion rule matches.
        """
        filter_value = filter_clause.value

        if filter_value is None:
            return None

        # Normalize to list of values to check
        values_to_check: List[str] = []
        if isinstance(filter_value, str):
            values_to_check = [filter_value]
        elif isinstance(filter_value, list):
            values_to_check = [v for v in filter_value if isinstance(v, str)]
        else:
            return None

        for rule in expansion_rules:
            # Check if any filter value matches a trigger keyword
            trigger_set = {kw.lower() for kw in rule.trigger_keywords}

            for val in values_to_check:
                if val.lower() in trigger_set:
                    # Match found - expand using the rule's condition
                    condition = rule.condition
                    target_field = condition.get("field", filter_clause.field)
                    target_operator = condition.get("operator", "eq")
                    target_value = condition.get("value")

                    # Only expand if the rule's field matches the filter's field
                    if target_field != filter_clause.field:
                        continue

                    try:
                        op = FilterOperator(target_operator)
                    except ValueError:
                        op = FilterOperator.EQ

                    return FilterClause(
                        field=target_field,
                        operator=op,
                        value=target_value,
                    )

        return None


__all__ = ["RuleApplicator"]
