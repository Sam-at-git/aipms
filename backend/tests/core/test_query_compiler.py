"""
Tests for SPEC-17: OntologyQueryCompiler

Tests:
- Entity resolution by name (case-insensitive)
- Entity resolution by display_name / description
- Field resolution by property name
- Chinese display_name field matching
- Alias replacement via RuleApplicator
- Confidence scoring (all resolved, partial, entity not found)
- Empty query handling
- Condition compilation to SemanticFilter
"""
import pytest
from unittest.mock import MagicMock

from core.ai.query_compiler import (
    ExtractedQuery,
    CompilationResult,
    OntologyQueryCompiler,
)
from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import EntityMetadata, PropertyMetadata
from core.ontology.semantic_query import SemanticQuery, SemanticFilter, FilterOperator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_registry():
    """
    Create a fresh OntologyRegistry with cleared state, restored after test.

    We save the singleton's internal dictionaries, clear them for the test,
    and restore them after the test finishes.
    """
    registry = OntologyRegistry()
    # Save original state
    saved_entities = dict(registry._entities)
    saved_actions = dict(registry._actions)
    saved_state_machines = dict(registry._state_machines)
    saved_business_rules = dict(registry._business_rules)
    saved_constraints = dict(registry._constraints)
    saved_permission_matrix = dict(registry._permission_matrix)
    saved_interface_implementations = dict(registry._interface_implementations)
    saved_interfaces = dict(registry._interfaces)
    saved_models = dict(registry._models)
    saved_relationships = dict(registry._relationships)

    registry.clear()
    yield registry

    # Restore original state
    registry.clear()
    registry._entities.update(saved_entities)
    registry._actions.update(saved_actions)
    registry._state_machines.update(saved_state_machines)
    registry._business_rules.update(saved_business_rules)
    registry._constraints.update(saved_constraints)
    registry._permission_matrix.update(saved_permission_matrix)
    registry._interface_implementations.update(saved_interface_implementations)
    registry._interfaces.update(saved_interfaces)
    registry._models.update(saved_models)
    registry._relationships.update(saved_relationships)


@pytest.fixture
def room_entity():
    """EntityMetadata for Room with several properties."""
    entity = EntityMetadata(
        name="Room",
        description="Hotel room entity",
        table_name="rooms",
        is_aggregate_root=True,
    )
    entity.add_property(PropertyMetadata(
        name="room_number",
        type="string",
        python_type="str",
        display_name="房间号",
        description="Room number identifier",
        is_required=True,
    ))
    entity.add_property(PropertyMetadata(
        name="status",
        type="string",
        python_type="str",
        display_name="房态",
        description="Current room status",
        enum_values=["vacant_clean", "vacant_dirty", "occupied", "out_of_order"],
    ))
    entity.add_property(PropertyMetadata(
        name="floor",
        type="integer",
        python_type="int",
        display_name="楼层",
        description="Floor number",
    ))
    return entity


@pytest.fixture
def guest_entity():
    """EntityMetadata for Guest with several properties."""
    entity = EntityMetadata(
        name="Guest",
        description="Hotel guest / 酒店客人",
        table_name="guests",
        is_aggregate_root=True,
    )
    entity.add_property(PropertyMetadata(
        name="name",
        type="string",
        python_type="str",
        display_name="姓名",
        description="Guest full name",
        is_required=True,
    ))
    entity.add_property(PropertyMetadata(
        name="phone",
        type="string",
        python_type="str",
        display_name="电话",
        description="Contact phone number",
    ))
    entity.add_property(PropertyMetadata(
        name="id_number",
        type="string",
        python_type="str",
        display_name="证件号",
        description="ID card number",
        pii=True,
    ))
    return entity


@pytest.fixture
def registry_with_entities(clean_registry, room_entity, guest_entity):
    """Registry populated with Room and Guest entities."""
    clean_registry.register_entity(room_entity)
    clean_registry.register_entity(guest_entity)
    return clean_registry


@pytest.fixture
def compiler(registry_with_entities):
    """OntologyQueryCompiler using the populated registry."""
    return OntologyQueryCompiler(registry=registry_with_entities)


# ---------------------------------------------------------------------------
# Test: Entity resolution by name
# ---------------------------------------------------------------------------

class TestEntityResolutionByName:
    """Entity resolution should match by exact name (case-insensitive)."""

    def test_exact_name_match(self, compiler):
        eq = ExtractedQuery(target_entity_hint="Room", target_fields_hint=["status"])
        result = compiler.compile(eq)
        assert result.query is not None
        assert result.query.root_object == "Room"
        assert result.confidence > 0.0

    def test_case_insensitive_name_match(self, compiler):
        eq = ExtractedQuery(target_entity_hint="room", target_fields_hint=["status"])
        result = compiler.compile(eq)
        assert result.query is not None
        assert result.query.root_object == "Room"

    def test_uppercase_name_match(self, compiler):
        eq = ExtractedQuery(target_entity_hint="GUEST", target_fields_hint=["name"])
        result = compiler.compile(eq)
        assert result.query is not None
        assert result.query.root_object == "Guest"


# ---------------------------------------------------------------------------
# Test: Entity resolution by description / display_name
# ---------------------------------------------------------------------------

class TestEntityResolutionByDescription:
    """Entity resolution falls back to description matching."""

    def test_description_match(self, compiler):
        """Should resolve 'guest' from the description '酒店客人'."""
        eq = ExtractedQuery(
            target_entity_hint="酒店客人",
            target_fields_hint=["name"],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert result.query.root_object == "Guest"

    def test_display_name_in_extensions(self, clean_registry):
        """Should resolve entity via display_name stored in extensions."""
        entity = EntityMetadata(
            name="RatePlan",
            description="Rate plan definition",
            table_name="rate_plans",
            extensions={"display_name": "价格方案"},
        )
        clean_registry.register_entity(entity)
        compiler = OntologyQueryCompiler(registry=clean_registry)

        eq = ExtractedQuery(target_entity_hint="价格方案")
        result = compiler.compile(eq)
        assert result.query is not None
        assert result.query.root_object == "RatePlan"


# ---------------------------------------------------------------------------
# Test: Field resolution
# ---------------------------------------------------------------------------

class TestFieldResolution:
    """Field resolution matches by property name (case-insensitive)."""

    def test_exact_field_match(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["room_number", "status"],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert "room_number" in result.query.fields
        assert "status" in result.query.fields
        assert result.confidence == 0.9

    def test_case_insensitive_field_match(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["Room_Number", "STATUS"],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert "room_number" in result.query.fields
        assert "status" in result.query.fields

    def test_partial_field_resolution(self, compiler):
        """Some fields resolve, some don't -> confidence 0.7."""
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["status", "nonexistent_field"],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert "status" in result.query.fields
        assert "nonexistent_field" not in result.query.fields
        assert result.confidence == 0.7

    def test_no_fields_resolved(self, compiler):
        """No fields resolve -> confidence 0.5."""
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["xyz", "abc"],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert result.query.fields == []
        assert result.confidence == 0.5


# ---------------------------------------------------------------------------
# Test: Chinese display_name field matching
# ---------------------------------------------------------------------------

class TestChineseDisplayNameFieldMatching:
    """Fields can be resolved via PropertyMetadata.display_name (Chinese)."""

    def test_chinese_display_name_match(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["房间号", "房态"],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert "room_number" in result.query.fields
        assert "status" in result.query.fields
        assert result.confidence == 0.9

    def test_mixed_name_and_display_name(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Guest",
            target_fields_hint=["姓名", "phone"],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert "name" in result.query.fields
        assert "phone" in result.query.fields
        assert result.confidence == 0.9


# ---------------------------------------------------------------------------
# Test: Alias replacement via RuleApplicator
# ---------------------------------------------------------------------------

class TestAliasReplacement:
    """Alias replacement delegates to RuleApplicator.apply_alias_rules."""

    def test_alias_replacement_applied(self, registry_with_entities):
        mock_applicator = MagicMock()
        mock_applicator.apply_alias_rules.return_value = "vacant_clean"

        compiler = OntologyQueryCompiler(
            registry=registry_with_entities,
            rule_applicator=mock_applicator,
        )
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["status"],
            conditions=[
                {"field": "status", "operator": "eq", "value": "净房"},
            ],
        )
        result = compiler.compile(eq)

        # RuleApplicator was called
        mock_applicator.apply_alias_rules.assert_called_once_with(
            "Room", "status", "净房"
        )
        # Filter uses the replaced value
        assert result.query is not None
        assert len(result.query.filters) == 1
        assert result.query.filters[0].value == "vacant_clean"

    def test_no_applicator_skips_alias(self, compiler):
        """Without rule_applicator, values pass through unchanged."""
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["status"],
            conditions=[
                {"field": "status", "operator": "eq", "value": "净房"},
            ],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert result.query.filters[0].value == "净房"


# ---------------------------------------------------------------------------
# Test: Confidence scoring
# ---------------------------------------------------------------------------

class TestConfidenceScoring:
    """Confidence scoring reflects resolution completeness."""

    def test_all_resolved_confidence_0_9(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["room_number", "status", "floor"],
        )
        result = compiler.compile(eq)
        assert result.confidence == 0.9
        assert not result.fallback_needed

    def test_partial_resolved_confidence_0_7(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["status", "missing_field"],
        )
        result = compiler.compile(eq)
        assert result.confidence == 0.7
        assert not result.fallback_needed

    def test_no_fields_confidence_0_5(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=[],
        )
        result = compiler.compile(eq)
        assert result.confidence == 0.5
        assert not result.fallback_needed

    def test_entity_not_found_confidence_0(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="UnknownEntity",
            target_fields_hint=["field"],
        )
        result = compiler.compile(eq)
        assert result.confidence == 0.0
        assert result.fallback_needed
        assert result.query is None

    def test_no_fields_resolved_confidence_0_5(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["nonexistent1", "nonexistent2"],
        )
        result = compiler.compile(eq)
        assert result.confidence == 0.5


# ---------------------------------------------------------------------------
# Test: Empty query handling
# ---------------------------------------------------------------------------

class TestEmptyQueryHandling:
    """Edge cases with empty or missing input."""

    def test_no_entity_hint(self, compiler):
        eq = ExtractedQuery(target_entity_hint=None, target_fields_hint=["name"])
        result = compiler.compile(eq)
        assert result.confidence == 0.0
        assert result.fallback_needed
        assert result.query is None
        assert "No target entity hint" in result.reasoning

    def test_empty_entity_hint(self, compiler):
        eq = ExtractedQuery(target_entity_hint="", target_fields_hint=["name"])
        result = compiler.compile(eq)
        assert result.confidence == 0.0
        assert result.fallback_needed
        assert result.query is None

    def test_empty_fields_and_conditions(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=[],
            conditions=[],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert result.query.root_object == "Room"
        assert result.query.fields == []
        assert result.query.filters == []
        assert result.confidence == 0.5

    def test_completely_empty_query(self, compiler):
        eq = ExtractedQuery()
        result = compiler.compile(eq)
        assert result.confidence == 0.0
        assert result.fallback_needed
        assert result.query is None


# ---------------------------------------------------------------------------
# Test: Condition compilation to SemanticFilter
# ---------------------------------------------------------------------------

class TestConditionCompilation:
    """Conditions are compiled into SemanticFilter objects."""

    def test_single_condition_to_filter(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["room_number"],
            conditions=[
                {"field": "status", "operator": "eq", "value": "occupied"},
            ],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert len(result.query.filters) == 1

        f = result.query.filters[0]
        assert isinstance(f, SemanticFilter)
        assert f.path == "status"
        assert f.operator == FilterOperator.EQ
        assert f.value == "occupied"

    def test_multiple_conditions(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["room_number"],
            conditions=[
                {"field": "status", "operator": "eq", "value": "vacant_clean"},
                {"field": "floor", "operator": "gte", "value": 3},
            ],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert len(result.query.filters) == 2

        assert result.query.filters[0].path == "status"
        assert result.query.filters[0].operator == FilterOperator.EQ
        assert result.query.filters[0].value == "vacant_clean"

        assert result.query.filters[1].path == "floor"
        assert result.query.filters[1].operator == FilterOperator.GTE
        assert result.query.filters[1].value == 3

    def test_invalid_operator_defaults_to_eq(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["status"],
            conditions=[
                {"field": "status", "operator": "invalid_op", "value": "occupied"},
            ],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert result.query.filters[0].operator == FilterOperator.EQ

    def test_condition_without_field_skipped(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["status"],
            conditions=[
                {"field": "", "operator": "eq", "value": "test"},
                {"field": "status", "operator": "eq", "value": "occupied"},
            ],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        # Empty field condition is skipped
        assert len(result.query.filters) == 1
        assert result.query.filters[0].path == "status"

    def test_like_operator(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Guest",
            target_fields_hint=["name"],
            conditions=[
                {"field": "name", "operator": "like", "value": "%张%"},
            ],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert result.query.filters[0].operator == FilterOperator.LIKE

    def test_in_operator(self, compiler):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["status"],
            conditions=[
                {
                    "field": "status",
                    "operator": "in",
                    "value": ["vacant_clean", "vacant_dirty"],
                },
            ],
        )
        result = compiler.compile(eq)
        assert result.query is not None
        assert result.query.filters[0].operator == FilterOperator.IN
        assert result.query.filters[0].value == ["vacant_clean", "vacant_dirty"]


# ---------------------------------------------------------------------------
# Test: Time context passthrough
# ---------------------------------------------------------------------------

class TestTimeContext:
    """ExtractedQuery preserves time_context (informational)."""

    def test_time_context_stored(self):
        eq = ExtractedQuery(
            target_entity_hint="Guest",
            target_fields_hint=["name"],
            time_context={
                "current_date": "2026-02-08",
                "tomorrow": "2026-02-09",
            },
        )
        assert eq.time_context is not None
        assert eq.time_context["current_date"] == "2026-02-08"
        assert eq.time_context["tomorrow"] == "2026-02-09"


# ---------------------------------------------------------------------------
# Test: CompilationResult dataclass
# ---------------------------------------------------------------------------

class TestCompilationResult:
    """CompilationResult default values and structure."""

    def test_default_values(self):
        result = CompilationResult()
        assert result.query is None
        assert result.confidence == 0.0
        assert result.fallback_needed is False
        assert result.reasoning == ""

    def test_custom_values(self):
        sq = SemanticQuery(root_object="Room", fields=["status"])
        result = CompilationResult(
            query=sq,
            confidence=0.9,
            fallback_needed=False,
            reasoning="All resolved",
        )
        assert result.query is sq
        assert result.confidence == 0.9
        assert result.reasoning == "All resolved"


# ---------------------------------------------------------------------------
# Test: ExtractedQuery dataclass
# ---------------------------------------------------------------------------

class TestExtractedQuery:
    """ExtractedQuery default values and structure."""

    def test_default_values(self):
        eq = ExtractedQuery()
        assert eq.target_entity_hint is None
        assert eq.target_fields_hint == []
        assert eq.conditions == []
        assert eq.time_context is None

    def test_custom_values(self):
        eq = ExtractedQuery(
            target_entity_hint="Room",
            target_fields_hint=["status"],
            conditions=[{"field": "status", "operator": "eq", "value": "clean"}],
            time_context={"current_date": "2026-02-08"},
        )
        assert eq.target_entity_hint == "Room"
        assert eq.target_fields_hint == ["status"]
        assert len(eq.conditions) == 1
        assert eq.time_context["current_date"] == "2026-02-08"
