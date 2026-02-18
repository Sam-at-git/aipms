"""
core/engine/rule_engine.py

Rule engine - decorator-registered business rule execution.
Supports runtime rule definitions, condition evaluation, and side-effect triggers.
"""
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


@dataclass
class RuleContext:
    """
    Rule execution context.

    Attributes:
        entity: Current entity object
        entity_type: Entity type name
        action: Action being executed
        parameters: Action parameters
        metadata: Additional metadata
    """

    entity: Any
    entity_type: str
    action: str
    parameters: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Get a parameter value."""
        return self.parameters.get(name, default)

    def has_parameter(self, name: str) -> bool:
        """Check whether a parameter exists."""
        return name in self.parameters


class RuleCondition(ABC):
    """Rule condition interface."""

    @abstractmethod
    def evaluate(self, context: RuleContext) -> bool:
        """
        Evaluate whether the condition is satisfied.

        Args:
            context: Rule execution context.

        Returns:
            True if the condition is met.
        """
        raise NotImplementedError


class FunctionCondition(RuleCondition):
    """Function condition - evaluates using a callable."""

    def __init__(self, func: Callable[[RuleContext], bool], description: str = ""):
        self._func = func
        self._description = description

    def evaluate(self, context: RuleContext) -> bool:
        return self._func(context)

    def __repr__(self) -> str:
        return f"FunctionCondition({self._description or self._func.__name__})"


class ExpressionCondition(RuleCondition):
    """Expression condition - evaluates using string expressions (simplified, no eval)."""

    def __init__(self, expression: str):
        self._expression = expression

    def evaluate(self, context: RuleContext) -> bool:
        # Simplified expression parsing: only supports simple == / != checks
        # e.g. "status == 'active'" or "count > 5"
        # A full implementation should use a safe expression parser

        # Helper to get attribute value (supports both dict and object)
        def get_attr_value(entity, attr_name):
            if isinstance(entity, dict):
                return entity.get(attr_name)
            return getattr(entity, attr_name, None)

        # Currently only supports simple attribute checks
        if " == " in self._expression:
            attr, value = self._expression.split(" == ", 1)
            attr_value = get_attr_value(context.entity, attr.strip())
            expected = value.strip().strip("'\"")
            return str(attr_value) == expected

        if " != " in self._expression:
            attr, value = self._expression.split(" != ", 1)
            attr_value = get_attr_value(context.entity, attr.strip())
            expected = value.strip().strip("'\"")
            return str(attr_value) != expected

        logger.warning(f"Unsupported expression: {self._expression}")
        return False

    def __repr__(self) -> str:
        return f"ExpressionCondition({self._expression})"


@dataclass
class Rule:
    """
    Business rule definition.

    Attributes:
        rule_id: Unique rule identifier
        name: Rule name
        description: Rule description
        condition: Rule condition
        action: Triggered action (callable)
        priority: Priority (higher number = higher priority)
        enabled: Whether the rule is enabled
    """

    rule_id: str
    name: str
    description: str
    condition: RuleCondition
    action: Callable[[RuleContext], None]
    priority: int = 0
    enabled: bool = True


class RuleEngine:
    """
    Rule engine - manages and executes business rules.

    Features:
    - Rule registration and unregistration
    - Condition evaluation
    - Action execution
    - Priority-based ordering

    Example:
        >>> engine = RuleEngine()
        >>> def check_status(ctx):
        ...     return ctx.entity.status == "active"
        >>> def log_action(ctx):
        ...     logger.info(f"Action on {ctx.entity}")
        >>> engine.register_rule(Rule(
        ...     rule_id="r1",
        ...     name="Active Entity Rule",
        ...     description="Log when entity is active",
        ...     condition=FunctionCondition(check_status),
        ...     action=log_action
        ... ))
        >>> engine.evaluate(RuleContext(...))
    """

    def __init__(self):
        self._rules: Dict[str, Rule] = {}
        self._entity_rules: Dict[str, List[str]] = {}  # entity_type -> rule_ids

    def register_rule(self, rule: Rule) -> None:
        """
        Register a rule.

        Args:
            rule: The rule to register.

        Raises:
            ValueError: If the rule_id already exists.
        """
        if rule.rule_id in self._rules:
            raise ValueError(f"Rule {rule.rule_id} already exists")

        self._rules[rule.rule_id] = rule

        # Index rules by entity type (extracted from rule_id prefix)
        entity_type = rule.rule_id.split("_")[0] if "_" in rule.rule_id else None
        if entity_type:
            if entity_type not in self._entity_rules:
                self._entity_rules[entity_type] = []
            self._entity_rules[entity_type].append(rule.rule_id)

        logger.info(f"Rule {rule.rule_id} registered")

    def unregister_rule(self, rule_id: str) -> None:
        """
        Unregister a rule.

        Args:
            rule_id: Rule ID.
        """
        if rule_id in self._rules:
            rule = self._rules[rule_id]

            # Remove from entity index
            for entity_type, rule_ids in self._entity_rules.items():
                if rule_id in rule_ids:
                    rule_ids.remove(rule_id)

            del self._rules[rule_id]
            logger.info(f"Rule {rule_id} unregistered")

    def get_rule(self, rule_id: str) -> Optional[Rule]:
        """Get a rule by ID."""
        return self._rules.get(rule_id)

    def get_rules_for_entity(self, entity_type: str) -> List[Rule]:
        """
        Get all rules for an entity type.

        Args:
            entity_type: Entity type name.

        Returns:
            List of rules sorted by priority (highest first).
        """
        rule_ids = self._entity_rules.get(entity_type, [])
        rules = [self._rules[rid] for rid in rule_ids if rid in self._rules and self._rules[rid].enabled]
        return sorted(rules, key=lambda r: r.priority, reverse=True)

    def evaluate(self, context: RuleContext) -> List[Rule]:
        """
        Evaluate rules and execute matching rule actions.

        Args:
            context: Rule execution context.

        Returns:
            List of triggered rules.
        """
        triggered = []

        for rule in self.get_rules_for_entity(context.entity_type):
            try:
                if rule.condition.evaluate(context):
                    rule.action(context)
                    triggered.append(rule)
                    logger.info(f"Rule {rule.rule_id} triggered for {context.entity_type}")
            except Exception as e:
                logger.error(f"Error executing rule {rule.rule_id}: {e}", exc_info=True)

        return triggered

    def enable_rule(self, rule_id: str) -> None:
        """Enable a rule."""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True

    def disable_rule(self, rule_id: str) -> None:
        """Disable a rule."""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False

    def clear(self) -> None:
        """Clear all rules (for testing)."""
        self._rules.clear()
        self._entity_rules.clear()


# Global rule engine instance
rule_engine = RuleEngine()


__all__ = [
    "RuleContext",
    "RuleCondition",
    "FunctionCondition",
    "ExpressionCondition",
    "Rule",
    "RuleEngine",
    "rule_engine",
]
