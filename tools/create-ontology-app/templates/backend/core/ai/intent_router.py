"""
core/ai/intent_router.py

Intent Router - Rule-based intent-to-action routing.

Routes extracted intents to the best matching action using a multi-stage
filtering pipeline: keyword match -> entity filter -> state feasibility -> role permission.

No vector store or LLM required - purely rule-based.

Key components:
- ExtractedIntent: Structured representation of parsed user intent
- RoutingResult: Action routing decision with confidence score
- IntentRouter: Multi-stage routing pipeline
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExtractedIntent:
    """
    Structured representation of a parsed user intent.

    Produced by an upstream intent extraction step (e.g., LLM or NLU parser)
    and consumed by IntentRouter to find the best matching action.

    Attributes:
        entity_mentions: Extracted entity names (e.g., ["Guest", "Room"])
        action_hints: Extracted action keywords (e.g., ["checkin", "check_in"])
        extracted_params: Extracted parameter values (e.g., {"guest_name": "Zhang"})
        time_references: Time-related mentions (e.g., ["tomorrow", "2024-01-15"])
    """
    entity_mentions: List[str] = field(default_factory=list)
    action_hints: List[str] = field(default_factory=list)
    extracted_params: Dict[str, Any] = field(default_factory=dict)
    time_references: List[str] = field(default_factory=list)


@dataclass
class RoutingResult:
    """
    Result of intent routing.

    Contains the best matched action, all candidate actions with scores,
    a confidence level, and reasoning for the decision.

    Attributes:
        action: Best matched action name, or None if no match
        candidates: List of candidate actions with scores
                    Each entry: {"name": str, "score": float, "reason": str}
        confidence: Routing confidence from 0.0 (no match) to 1.0 (certain)
        reasoning: Human-readable explanation of the routing decision
    """
    action: Optional[str] = None
    candidates: List[Dict] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""


class IntentRouter:
    """
    Rule-based intent-to-action router.

    Uses a multi-stage filtering pipeline to find the best action for a given intent:

    1. Keyword exact match: Check action_hints against action names and search_keywords
    2. Entity-based filtering: Filter actions by entity_mentions
    3. State machine feasibility check: If executor available, filter by valid transitions
    4. Role permission check: Filter by allowed_roles

    Confidence scoring:
    - Single candidate after filtering: 0.95
    - Multiple candidates (2-3): 0.6
    - Many candidates (4+): 0.3
    - No candidates: 0.0

    Example:
        >>> from core.ai.actions import ActionRegistry
        >>> registry = ActionRegistry(vector_store=None)
        >>> router = IntentRouter(action_registry=registry)
        >>> intent = ExtractedIntent(
        ...     entity_mentions=["Guest"],
        ...     action_hints=["checkin"]
        ... )
        >>> result = router.route(intent)
        >>> print(result.action, result.confidence)
    """

    def __init__(
        self,
        action_registry=None,
        ontology_registry=None,
        state_machine_executor=None,
    ):
        """
        Initialize the IntentRouter.

        Args:
            action_registry: ActionRegistry instance for action lookup.
                            If None, routing will always return no candidates.
            ontology_registry: OntologyRegistry instance (reserved for future use).
            state_machine_executor: StateMachineExecutor for state transition validation.
                                   If None, state feasibility check is skipped.
        """
        self._action_registry = action_registry
        self._ontology_registry = ontology_registry
        self._state_machine_executor = state_machine_executor

    def route(self, intent: ExtractedIntent, user_role: str = "admin") -> RoutingResult:
        """
        Route an extracted intent to the best matching action.

        Applies filters in order: keyword match -> entity filter ->
        state feasibility -> role permission. Returns the best candidate
        with a confidence score.

        Args:
            intent: The extracted intent to route
            user_role: The role of the user making the request (default: "admin")

        Returns:
            RoutingResult with best action, candidates, confidence, and reasoning
        """
        if self._action_registry is None:
            return RoutingResult(
                action=None,
                candidates=[],
                confidence=0.0,
                reasoning="No action registry configured",
            )

        all_actions = self._action_registry.list_actions()
        if not all_actions:
            return RoutingResult(
                action=None,
                candidates=[],
                confidence=0.0,
                reasoning="No actions registered in the registry",
            )

        # Build candidate list with scores
        candidates = []
        reasoning_parts = []

        # Stage 1: Keyword exact match
        keyword_matches = self._match_by_keywords(intent.action_hints, all_actions)
        if keyword_matches:
            candidates = keyword_matches
            reasoning_parts.append(
                f"Keyword match found {len(keyword_matches)} candidate(s) "
                f"from hints {intent.action_hints}"
            )
        else:
            # Stage 2: Entity-based filtering
            if intent.entity_mentions:
                entity_matches = self._filter_by_entity(intent.entity_mentions, all_actions)
                if entity_matches:
                    candidates = entity_matches
                    reasoning_parts.append(
                        f"Entity filter found {len(entity_matches)} candidate(s) "
                        f"for entities {intent.entity_mentions}"
                    )
                else:
                    reasoning_parts.append(
                        f"No actions found for entities {intent.entity_mentions}"
                    )
            else:
                # No hints and no entity mentions - all actions are candidates
                candidates = [
                    {"name": a.name, "score": 0.1, "reason": "fallback (no filters matched)"}
                    for a in all_actions
                ]
                reasoning_parts.append("No keyword hints or entity mentions; all actions are candidates")

        # Stage 3: State machine feasibility check
        if self._state_machine_executor and candidates:
            before_count = len(candidates)
            candidates = self._filter_by_state_feasibility(candidates, intent)
            if len(candidates) < before_count:
                reasoning_parts.append(
                    f"State feasibility reduced candidates from {before_count} to {len(candidates)}"
                )

        # Stage 4: Role permission check
        if candidates:
            before_count = len(candidates)
            candidates = self._filter_by_role(candidates, user_role)
            if len(candidates) < before_count:
                reasoning_parts.append(
                    f"Role filter ({user_role}) reduced candidates from {before_count} to {len(candidates)}"
                )

        # Calculate confidence and select best action
        confidence = self._calculate_confidence(len(candidates))
        best_action = None

        if candidates:
            # Sort by score descending to pick the best
            candidates.sort(key=lambda c: c.get("score", 0), reverse=True)
            best_action = candidates[0]["name"]

        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "No routing filters applied"

        return RoutingResult(
            action=best_action,
            candidates=candidates,
            confidence=confidence,
            reasoning=reasoning,
        )

    def _match_by_keywords(self, action_hints: List[str], actions) -> List[Dict]:
        """
        Stage 1: Match action_hints against action names and search_keywords.

        Checks each hint against:
        - Exact action name match
        - Substring match in action name (e.g., "checkin" matches "walkin_checkin")
        - Exact match in action's search_keywords list

        Args:
            action_hints: Keywords extracted from user intent
            actions: List of ActionDefinition objects

        Returns:
            List of candidate dicts with name, score, and reason
        """
        if not action_hints:
            return []

        candidates = {}  # Use dict to deduplicate by action name

        for hint in action_hints:
            hint_lower = hint.lower()

            for action in actions:
                action_name_lower = action.name.lower()

                # Exact name match - highest score
                if hint_lower == action_name_lower:
                    if action.name not in candidates or candidates[action.name]["score"] < 1.0:
                        candidates[action.name] = {
                            "name": action.name,
                            "score": 1.0,
                            "reason": f"Exact name match for '{hint}'",
                        }
                    continue

                # Substring match in action name
                if hint_lower in action_name_lower or action_name_lower in hint_lower:
                    if action.name not in candidates or candidates[action.name]["score"] < 0.8:
                        candidates[action.name] = {
                            "name": action.name,
                            "score": 0.8,
                            "reason": f"Substring match: '{hint}' in action name '{action.name}'",
                        }
                    continue

                # Match in search_keywords
                keywords_lower = [kw.lower() for kw in action.search_keywords]
                if hint_lower in keywords_lower:
                    if action.name not in candidates or candidates[action.name]["score"] < 0.9:
                        candidates[action.name] = {
                            "name": action.name,
                            "score": 0.9,
                            "reason": f"Keyword match: '{hint}' in search_keywords of '{action.name}'",
                        }

        return list(candidates.values())

    def _filter_by_entity(self, entity_mentions: List[str], actions) -> List[Dict]:
        """
        Stage 2: Filter actions by entity_mentions.

        Uses ActionRegistry.list_actions_by_entity() for each mentioned entity.

        Args:
            entity_mentions: Entity names extracted from user intent
            actions: List of all ActionDefinition objects (unused, kept for API consistency)

        Returns:
            List of candidate dicts with name, score, and reason
        """
        candidates = {}

        for entity in entity_mentions:
            entity_actions = self._action_registry.list_actions_by_entity(entity)
            for action in entity_actions:
                if action.name not in candidates:
                    candidates[action.name] = {
                        "name": action.name,
                        "score": 0.5,
                        "reason": f"Entity match: action belongs to entity '{entity}'",
                    }

        return list(candidates.values())

    def _filter_by_state_feasibility(
        self, candidates: List[Dict], intent: ExtractedIntent
    ) -> List[Dict]:
        """
        Stage 3: Filter candidates by state machine feasibility.

        If a state_machine_executor is available, checks whether the action's
        entity has valid transitions available. Only filters if the executor
        can provide useful information.

        Args:
            candidates: Current candidate list
            intent: The extracted intent (may contain state context)

        Returns:
            Filtered candidate list (may be unchanged if no filtering applies)
        """
        if not self._state_machine_executor:
            return candidates

        # We need current_state from the intent's extracted_params
        current_state = intent.extracted_params.get("current_state")
        if not current_state:
            return candidates

        filtered = []
        for candidate in candidates:
            action_name = candidate["name"]
            action_def = self._action_registry.get_action(action_name)
            if action_def is None:
                continue

            # Check if the entity has a state machine with valid transitions
            entity = action_def.entity
            try:
                # Get valid transitions from current state
                sm = None
                if self._ontology_registry:
                    sm = self._ontology_registry.get_state_machine(entity)

                if sm is None:
                    # No state machine for this entity - keep the candidate
                    filtered.append(candidate)
                    continue

                valid_transitions = sm.get_valid_transitions(current_state)
                if valid_transitions:
                    # Check if any transition trigger matches this action
                    triggers = {t.trigger for t in valid_transitions}
                    if action_name in triggers or not triggers:
                        filtered.append(candidate)
                else:
                    # No valid transitions - still include but lower score
                    candidate_copy = dict(candidate)
                    candidate_copy["score"] = candidate.get("score", 0.5) * 0.5
                    candidate_copy["reason"] += " (no valid state transitions)"
                    filtered.append(candidate_copy)

            except Exception as e:
                logger.warning(f"State feasibility check failed for {action_name}: {e}")
                filtered.append(candidate)

        return filtered

    def _filter_by_role(self, candidates: List[Dict], user_role: str) -> List[Dict]:
        """
        Stage 4: Filter candidates by role permission.

        Removes candidates where the action has allowed_roles defined
        and the user_role is not in that set.

        If allowed_roles is empty, the action is considered open to all roles.

        Args:
            candidates: Current candidate list
            user_role: The user's role string

        Returns:
            Filtered candidate list
        """
        filtered = []
        for candidate in candidates:
            action_name = candidate["name"]
            action_def = self._action_registry.get_action(action_name)
            if action_def is None:
                continue

            # If no role restriction, allow everyone
            if not action_def.allowed_roles:
                filtered.append(candidate)
                continue

            # Check if user role is in allowed roles
            if user_role in action_def.allowed_roles:
                filtered.append(candidate)

        return filtered

    def _calculate_confidence(self, candidate_count: int) -> float:
        """
        Calculate routing confidence based on number of remaining candidates.

        Args:
            candidate_count: Number of candidates after all filtering stages

        Returns:
            Confidence score from 0.0 to 1.0
        """
        if candidate_count == 0:
            return 0.0
        elif candidate_count == 1:
            return 0.95
        elif candidate_count <= 3:
            return 0.6
        else:
            return 0.3


__all__ = [
    "ExtractedIntent",
    "RoutingResult",
    "IntentRouter",
]
