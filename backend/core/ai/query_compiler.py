"""
core/ai/query_compiler.py

OntologyQueryCompiler - Compiles extracted query intent into SemanticQuery objects.

SPEC-17: Bridge between raw user intent extraction and the semantic query layer.

Responsibilities:
1. Entity resolution: match target_entity_hint to registry entities
2. Field resolution: match field hints to entity properties (by name or display_name)
3. Alias replacement: apply alias rules to condition values via RuleApplicator
4. Build SemanticQuery with resolved entity, fields, and filters
5. Confidence scoring based on resolution completeness

Usage:
    compiler = OntologyQueryCompiler(registry=registry)
    extracted = ExtractedQuery(
        target_entity_hint="Room",
        target_fields_hint=["room_number", "status"],
        conditions=[{"field": "status", "operator": "eq", "value": "vacant_clean"}],
    )
    result = compiler.compile(extracted)
    # result.query => SemanticQuery(root_object="Room", fields=["room_number", "status"], ...)
    # result.confidence => 0.9
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import EntityMetadata, PropertyMetadata
from core.ontology.semantic_query import SemanticQuery, SemanticFilter, FilterOperator


@dataclass
class ExtractedQuery:
    """
    Intermediate representation of user intent before compilation.

    Populated by an intent extractor (LLM or rule-based) and fed into the
    OntologyQueryCompiler to produce a SemanticQuery.

    Attributes:
        target_entity_hint: entity name hint from user intent (e.g. "Room", "guest")
        target_fields_hint: requested field hints (e.g. ["room_number", "status"])
        conditions: extracted filter conditions as dicts with keys:
            - field (str): field name or hint
            - operator (str): filter operator (eq, gt, like, etc.)
            - value (Any): filter value
        time_context: time context dict (e.g. {"current_date": "2026-02-08", "tomorrow": "2026-02-09"})
    """
    target_entity_hint: Optional[str] = None
    target_fields_hint: List[str] = field(default_factory=list)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    time_context: Optional[Dict[str, str]] = None


@dataclass
class CompilationResult:
    """
    Result of compiling an ExtractedQuery into a SemanticQuery.

    Attributes:
        query: compiled SemanticQuery, or None if compilation failed
        confidence: compilation confidence (0.0 to 1.0)
        fallback_needed: whether LLM fallback should be used
        reasoning: human-readable explanation of the compilation outcome
    """
    query: Optional[SemanticQuery] = None
    confidence: float = 0.0
    fallback_needed: bool = False
    reasoning: str = ""


class OntologyQueryCompiler:
    """
    Compiles extracted query intent into SemanticQuery objects.

    Bridges the gap between raw intent extraction and the semantic query
    execution layer by resolving entity names, field names, and applying
    business rule aliases.

    Args:
        registry: OntologyRegistry instance for entity/field resolution.
                  If None, uses the singleton.
        rule_applicator: RuleApplicator instance for alias replacement.
                        Optional; if None, alias replacement is skipped.
    """

    def __init__(self, registry: Optional[OntologyRegistry] = None, rule_applicator=None):
        self._registry = registry or OntologyRegistry()
        self._rule_applicator = rule_applicator

    def compile(self, extracted_query: ExtractedQuery) -> CompilationResult:
        """
        Main compilation method: transforms ExtractedQuery into CompilationResult.

        Compilation steps:
        a. Entity resolution: match target_entity_hint to registry entities
        b. Field resolution: match each field hint to entity properties
        c. Alias replacement: apply alias rules to condition values
        d. Build SemanticQuery with resolved entity, fields, and filters

        Confidence scoring:
        - Entity resolved + all fields resolved: 0.9
        - Entity resolved + some fields resolved: 0.7
        - Entity resolved but no fields: 0.5
        - Entity not resolved: 0.0, fallback_needed = True

        Args:
            extracted_query: the extracted query intent

        Returns:
            CompilationResult with compiled query, confidence, and reasoning
        """
        # Handle empty/null entity hint
        if not extracted_query.target_entity_hint:
            return CompilationResult(
                query=None,
                confidence=0.0,
                fallback_needed=True,
                reasoning="No target entity hint provided",
            )

        # Step a: Entity resolution
        resolved_entity = self._resolve_entity(extracted_query.target_entity_hint)
        if resolved_entity is None:
            return CompilationResult(
                query=None,
                confidence=0.0,
                fallback_needed=True,
                reasoning=(
                    f"Could not resolve entity hint "
                    f"'{extracted_query.target_entity_hint}' "
                    f"to any registered entity"
                ),
            )

        # Step b: Field resolution
        resolved_fields, unresolved_fields = self._resolve_fields(
            resolved_entity, extracted_query.target_fields_hint
        )

        # Step c: Alias replacement on conditions
        processed_conditions = self._apply_aliases(
            resolved_entity.name, extracted_query.conditions
        )

        # Step d: Build filters from conditions
        filters = self._build_filters(
            resolved_entity, processed_conditions
        )

        # Determine confidence
        confidence, reasoning = self._compute_confidence(
            resolved_entity,
            extracted_query.target_fields_hint,
            resolved_fields,
            unresolved_fields,
        )

        # Build SemanticQuery
        # Use resolved field names; if no fields resolved, leave empty
        query_fields = resolved_fields if resolved_fields else []

        query = SemanticQuery(
            root_object=resolved_entity.name,
            fields=query_fields,
            filters=filters,
        )

        return CompilationResult(
            query=query,
            confidence=confidence,
            fallback_needed=(confidence < 0.3),
            reasoning=reasoning,
        )

    def _resolve_entity(self, hint: str) -> Optional[EntityMetadata]:
        """
        Resolve an entity hint to an EntityMetadata from the registry.

        Matching strategy (case-insensitive):
        1. Exact name match
        2. Description match (hint contained in description)
        3. display_name on entity (if present in extensions or as attr)

        Args:
            hint: entity name hint string

        Returns:
            EntityMetadata if resolved, None otherwise
        """
        hint_lower = hint.lower()
        entities = self._registry.get_entities()

        # Pass 1: exact name match (case-insensitive)
        for entity in entities:
            if entity.name.lower() == hint_lower:
                return entity

        # Pass 2: description contains hint
        for entity in entities:
            if entity.description and hint_lower in entity.description.lower():
                return entity

        # Pass 3: check display_name in extensions or as attribute
        for entity in entities:
            display_name = getattr(entity, "display_name", None)
            if display_name and hint_lower == display_name.lower():
                return entity
            # Also check extensions dict
            ext_display = entity.extensions.get("display_name", "")
            if ext_display and hint_lower == ext_display.lower():
                return entity

        return None

    def _resolve_fields(
        self, entity: EntityMetadata, field_hints: List[str]
    ) -> tuple:
        """
        Resolve field hints to actual property names on the entity.

        Matching strategy (case-insensitive):
        1. Exact property name match
        2. PropertyMetadata.display_name match

        Args:
            entity: resolved EntityMetadata
            field_hints: list of field name hints

        Returns:
            (resolved_fields, unresolved_fields) tuple of lists
        """
        resolved: List[str] = []
        unresolved: List[str] = []

        properties = entity.properties if entity.properties else {}

        for hint in field_hints:
            resolved_name = self._resolve_single_field(properties, hint)
            if resolved_name is not None:
                resolved.append(resolved_name)
            else:
                unresolved.append(hint)

        return resolved, unresolved

    def _resolve_single_field(
        self, properties: Dict[str, PropertyMetadata], hint: str
    ) -> Optional[str]:
        """
        Resolve a single field hint to a property name.

        Args:
            properties: dict of property name -> PropertyMetadata
            hint: field name hint

        Returns:
            resolved property name, or None
        """
        hint_lower = hint.lower()

        # Pass 1: exact name match (case-insensitive)
        for prop_name, prop_meta in properties.items():
            if prop_name.lower() == hint_lower:
                return prop_name

        # Pass 2: display_name match (case-insensitive)
        for prop_name, prop_meta in properties.items():
            if prop_meta.display_name and prop_meta.display_name.lower() == hint_lower:
                return prop_name

        return None

    def _apply_aliases(
        self, entity_name: str, conditions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Apply alias rules to condition values using the RuleApplicator.

        If no rule_applicator is set, returns conditions unchanged.

        Args:
            entity_name: resolved entity name
            conditions: list of condition dicts

        Returns:
            list of condition dicts with alias-replaced values
        """
        if not self._rule_applicator:
            return conditions

        result = []
        for cond in conditions:
            new_cond = dict(cond)
            field_name = cond.get("field", "")
            value = cond.get("value")
            if value is not None and field_name:
                new_cond["value"] = self._rule_applicator.apply_alias_rules(
                    entity_name, field_name, value
                )
            result.append(new_cond)
        return result

    def _build_filters(
        self,
        entity: EntityMetadata,
        conditions: List[Dict[str, Any]],
    ) -> List[SemanticFilter]:
        """
        Build SemanticFilter objects from condition dicts.

        Each condition dict should have: field, operator, value.

        Args:
            entity: resolved EntityMetadata
            conditions: list of processed condition dicts

        Returns:
            list of SemanticFilter objects
        """
        filters: List[SemanticFilter] = []
        for cond in conditions:
            field_name = cond.get("field", "")
            operator_str = cond.get("operator", "eq")
            value = cond.get("value")

            if not field_name:
                continue

            # Normalize operator
            try:
                operator = FilterOperator(operator_str)
            except ValueError:
                operator = FilterOperator.EQ

            filters.append(
                SemanticFilter(
                    path=field_name,
                    operator=operator,
                    value=value,
                )
            )
        return filters

    def _compute_confidence(
        self,
        entity: EntityMetadata,
        original_hints: List[str],
        resolved_fields: List[str],
        unresolved_fields: List[str],
    ) -> tuple:
        """
        Compute confidence score and reasoning string.

        Scoring:
        - Entity resolved + all fields resolved: 0.9
        - Entity resolved + some fields resolved: 0.7
        - Entity resolved but no fields requested or none resolved: 0.5
        - Entity not resolved: 0.0 (handled before this method is called)

        Args:
            entity: resolved EntityMetadata
            original_hints: original field hints
            resolved_fields: successfully resolved field names
            unresolved_fields: field hints that could not be resolved

        Returns:
            (confidence, reasoning) tuple
        """
        if not original_hints:
            # No fields requested
            return 0.5, (
                f"Entity '{entity.name}' resolved, "
                f"but no fields were requested"
            )

        if not resolved_fields:
            # Fields requested but none resolved
            return 0.5, (
                f"Entity '{entity.name}' resolved, "
                f"but none of the requested fields could be resolved: "
                f"{unresolved_fields}"
            )

        if not unresolved_fields:
            # All fields resolved
            return 0.9, (
                f"Entity '{entity.name}' resolved with all "
                f"{len(resolved_fields)} field(s): {resolved_fields}"
            )

        # Partial resolution
        return 0.7, (
            f"Entity '{entity.name}' resolved with "
            f"{len(resolved_fields)}/{len(original_hints)} field(s). "
            f"Resolved: {resolved_fields}, "
            f"Unresolved: {unresolved_fields}"
        )


__all__ = [
    "ExtractedQuery",
    "CompilationResult",
    "OntologyQueryCompiler",
]
