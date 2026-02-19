"""
core/ai/prompt_shaper.py

Prompt schema selection strategy dispatcher with fallback chain.

Implements a three-phase optimization strategy for controlling prompt size:
- Phase 3: Dynamic Tool Discovery (search_actions → describe → execute)
- Phase 2: Intent-Driven Schema Inference (from RoutingResult)
- Phase 1: Role-Based Filtering (by action category)
- Fallback: Full injection (current behavior)

Each phase degrades gracefully to the next when it cannot produce a result.

IMPORTANT: This module is in core/ and must NOT import any app-layer modules.
All domain-specific knowledge is injected via register_role_filter() and similar APIs.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from core.ontology.registry import OntologyRegistry
    from core.ai.actions import ActionRegistry

logger = logging.getLogger(__name__)


# Class-level registry for role filters.
# Domain plugins call register_role_filter() at startup (before any PromptShaper
# instance exists). PromptShaper instances read from this shared store.
_role_filter_registry: Dict[str, Set[str]] = {}


def register_role_filter(role: str, excluded_categories: Set[str]) -> None:
    """Register a role-level action category filter (module-level API).

    Called by domain plugins at startup to declare which action categories
    a given role should NOT see in the prompt.

    This is a module-level function so it can be called before any PromptShaper
    instance is created (plugins register during app startup, PromptShaper is
    lazily created per-request).

    Args:
        role: User role name (e.g., "cleaner", "receptionist")
        excluded_categories: Set of action category strings to exclude
                            (e.g., {"admin", "billing", "reservation"})
    """
    _role_filter_registry[role] = excluded_categories
    logger.info(f"PromptShaper: registered role filter for '{role}', "
                f"excluding categories: {excluded_categories}")


@dataclass
class ShapingResult:
    """Output of the prompt shaping strategy.

    Attributes:
        actions: List of action names to inject into the prompt.
                 Empty list means no actions should be injected (Phase 3 mode).
                 None means inject all actions (no filtering).
        entities: List of entity names to inject into the prompt.
                  None means inject all entities (no filtering).
        include_query_schema: Whether to append the query schema section.
        strategy: Name of the strategy that produced this result.
                  One of: "discovery", "inference", "role_filter", "full"
        metadata: Diagnostic information for debug UI.
    """
    actions: Optional[List[str]] = None
    entities: Optional[List[str]] = None
    include_query_schema: bool = True
    strategy: str = "full"
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptShaper:
    """Prompt schema selection strategy dispatcher.

    Tries Phase 3 → Phase 2 → Phase 1 → Full, returning the first
    successful result. Each phase can return None to signal degradation
    to the next phase.

    This is a core-layer component with zero domain knowledge. Domain-specific
    configuration is injected via the module-level register_role_filter() function.
    """

    def __init__(
        self,
        ontology_registry: "OntologyRegistry",
        action_registry: Optional["ActionRegistry"] = None,
    ):
        self._registry = ontology_registry
        self._action_registry = action_registry

        # SPEC-P05: Pick up search engine from ActionRegistry if available
        self._search_engine = getattr(action_registry, '_search_engine', None)

    def shape(
        self,
        message: str,
        user_role: str,
        intent=None,
    ) -> ShapingResult:
        """Main entry point: select the best prompt shaping strategy.

        Tries each phase in order, falling back to the next on failure:
        Phase 3 (dynamic discovery) → Phase 2 (intent inference) →
        Phase 1 (role filter) → Full injection.

        Args:
            message: The user's input message.
            user_role: The current user's role.
            intent: Optional RoutingResult from IntentRouter (used by Phase 2).

        Returns:
            ShapingResult with the selected actions/entities and strategy name.
        """
        fallback_chain = []

        # Phase 3: Dynamic Tool Discovery (SPEC-P06)
        result = self._dynamic_discovery(message, user_role)
        if result is not None:
            result.metadata["fallback_chain"] = fallback_chain
            return result
        fallback_chain.append("discovery_unavailable")

        # Phase 2: Intent-Driven Schema Inference (SPEC-P03)
        if intent is not None:
            result = self._intent_inference(message, user_role, intent)
            if result is not None:
                result.metadata["fallback_chain"] = fallback_chain
                return result
            fallback_chain.append("inference_failed")

        # Phase 1: Role-Based Filtering
        result = self._role_filter(user_role)
        if result.strategy != "full":
            result.metadata["fallback_chain"] = fallback_chain
            return result

        # Ultimate fallback: full injection
        fallback_chain.append("role_filter_passthrough")
        return ShapingResult(
            actions=None,  # None = inject all
            entities=None,  # None = inject all
            include_query_schema=True,
            strategy="full",
            metadata={
                "reason": "no_filters_applied",
                "fallback_chain": fallback_chain,
            },
        )

    def _dynamic_discovery(
        self,
        message: str,
        user_role: str,
    ) -> Optional[ShapingResult]:
        """Phase 3: Dynamic Tool Discovery (SPEC-P06).

        If an ActionSearchEngine is available, return a ShapingResult that
        instructs the orchestrator to use the tool calling protocol instead
        of injecting action definitions into the prompt.

        Returns:
            ShapingResult with strategy="discovery" and actions=[] if search
            engine is available, None to trigger fallback to Phase 2.
        """
        if self._search_engine is None:
            logger.debug("PromptShaper Phase 3: no search engine, falling back")
            return None

        # Verify the search engine has indexed actions
        if not self._search_engine._action_meta:
            logger.debug("PromptShaper Phase 3: search engine empty, falling back")
            return None

        logger.info(
            f"PromptShaper Phase 3 (discovery): search engine has "
            f"{len(self._search_engine._action_meta)} indexed actions"
        )

        return ShapingResult(
            actions=[],  # Empty list = don't inject any actions into prompt
            entities=None,  # Entities still injected for context
            include_query_schema=True,  # Include for now; LLM may need it
            strategy="discovery",
            metadata={
                "indexed_actions": len(self._search_engine._action_meta),
            },
        )

    def _role_filter(self, user_role: str) -> ShapingResult:
        """Phase 1: Filter actions by role-excluded categories.

        If the user's role has registered exclusions, filter out actions
        in those categories and derive the entity set from remaining actions.

        Returns:
            ShapingResult with strategy="role_filter" if filtering applied,
            or strategy="full" if no filter is registered for this role.
        """
        excluded = _role_filter_registry.get(user_role)

        if not excluded:
            # No filter registered for this role → full injection
            return ShapingResult(
                actions=None,
                entities=None,
                include_query_schema=True,
                strategy="full",
                metadata={"reason": "no_role_filter_registered"},
            )

        # Get all actions and filter by category
        all_actions = self._list_actions()
        filtered_actions = [a for a in all_actions if a.category not in excluded]
        filtered_action_names = [a.name for a in filtered_actions]

        # Derive entities from filtered actions
        relevant_entities = self._collect_entities_from_actions(filtered_actions)

        return ShapingResult(
            actions=filtered_action_names,
            entities=list(relevant_entities) if relevant_entities else None,
            include_query_schema=True,
            strategy="role_filter",
            metadata={
                "excluded_categories": list(excluded),
                "actions_total": len(all_actions),
                "actions_injected": len(filtered_action_names),
                "actions_removed": len(all_actions) - len(filtered_action_names),
            },
        )

    def _intent_inference(
        self,
        message: str,
        user_role: str,
        intent,
    ) -> Optional[ShapingResult]:
        """Phase 2: From RoutingResult, infer relevant entity/action subset.

        Uses the IntentRouter's routing result to select only the actions and
        entities relevant to the user's intent, reducing prompt size.

        Algorithm:
        1. If intent confidence is too low (< 0.3), return None (trigger fallback).
        2. If no candidates, return None.
        3. Collect entity names from candidate actions (via ActionRegistry lookup).
        4. Expand entities via get_related_entities(depth=1).
        5. Filter actions: include candidate actions + any actions whose entity
           is in the expanded set (also apply role filter).
        6. Determine include_query_schema based on whether any candidate is a
           query action.
        7. Return ShapingResult with strategy="inference".

        Args:
            message: The user's input message.
            user_role: The current user's role.
            intent: RoutingResult from IntentRouter (duck-typed: needs
                    .confidence, .candidates, .action attributes).

        Returns:
            ShapingResult if inference succeeds, None to trigger fallback.
        """
        # Guard: check confidence threshold
        confidence = getattr(intent, "confidence", 0.0)
        if confidence < 0.3:
            logger.debug(
                f"PromptShaper Phase 2: confidence {confidence} < 0.3, "
                f"falling back"
            )
            return None

        # Guard: check for candidates
        candidates = getattr(intent, "candidates", [])
        if not candidates:
            logger.debug("PromptShaper Phase 2: no candidates, falling back")
            return None

        # Collect candidate action names
        candidate_action_names = {
            c["name"] if isinstance(c, dict) else getattr(c, "name", "")
            for c in candidates
        }

        # Collect entity names from candidate actions via ActionRegistry
        candidate_entities = set()
        for action_name in candidate_action_names:
            if self._action_registry is not None:
                action_def = self._action_registry.get_action(action_name)
                if action_def and hasattr(action_def, "entity") and action_def.entity:
                    candidate_entities.add(action_def.entity)

        # Expand entities via relationships (depth=1)
        expanded_entities = set()
        for entity_name in candidate_entities:
            expanded_entities.add(entity_name)
            try:
                related = self._registry.get_related_entities(
                    entity_name, depth=1
                )
                expanded_entities |= related
            except (AttributeError, TypeError):
                pass

        # Get role exclusions for filtering
        excluded_categories = _role_filter_registry.get(user_role, set())

        # Filter all actions: include candidates + actions whose entity is
        # in the expanded set, applying role filter
        all_actions = self._list_actions()
        filtered_action_names = []
        for action in all_actions:
            # Apply role filter
            if action.category in excluded_categories:
                continue

            action_name = action.name
            action_entity = getattr(action, "entity", "")

            # Include if it's a candidate action or its entity is in expanded set
            if action_name in candidate_action_names:
                filtered_action_names.append(action_name)
            elif action_entity in expanded_entities:
                filtered_action_names.append(action_name)

        # Determine include_query_schema: True if any candidate is a query action
        include_query_schema = any(
            "query" in name or "semantic" in name
            for name in candidate_action_names
        )

        # Determine entity list from expanded set
        entity_list = sorted(expanded_entities) if expanded_entities else None

        logger.info(
            f"PromptShaper Phase 2 (inference): "
            f"{len(filtered_action_names)} actions, "
            f"{len(expanded_entities) if expanded_entities else 'all'} entities, "
            f"query_schema={include_query_schema}, "
            f"confidence={confidence}"
        )

        return ShapingResult(
            actions=filtered_action_names,
            entities=entity_list,
            include_query_schema=include_query_schema,
            strategy="inference",
            metadata={
                "confidence": confidence,
                "candidate_actions": sorted(candidate_action_names),
                "candidate_entities": sorted(candidate_entities),
                "expanded_entities": sorted(expanded_entities),
                "actions_total": len(all_actions),
                "actions_injected": len(filtered_action_names),
            },
        )

    def _list_actions(self):
        """Get all registered actions from ActionRegistry."""
        if self._action_registry is not None:
            return self._action_registry.list_actions()
        return []

    def _collect_entities_from_actions(self, actions) -> Optional[Set[str]]:
        """Collect unique entity names from a list of action definitions.

        Returns None if no entities can be determined (meaning inject all).
        """
        entities = set()
        for action in actions:
            if hasattr(action, 'entity') and action.entity:
                entities.add(action.entity)

        if not entities:
            return None  # Can't determine entities → inject all

        # Always include entities that have no actions (like RoomType, Payment)
        # by expanding via relationships
        try:
            expanded = set()
            for entity_name in entities:
                expanded.add(entity_name)
                related = self._registry.get_related_entities(entity_name, depth=1)
                expanded |= related
            return expanded
        except (AttributeError, TypeError):
            # get_related_entities not available yet (SPEC-P02)
            return entities


__all__ = ["PromptShaper", "ShapingResult", "register_role_filter"]
