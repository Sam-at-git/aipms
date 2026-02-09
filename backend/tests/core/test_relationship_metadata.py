"""
Tests for SPEC-01: RelationshipMetadata + EntityMetadata.relationships + Registry methods
"""
import pytest
from core.ontology.metadata import RelationshipMetadata, EntityMetadata
from core.ontology.registry import OntologyRegistry


@pytest.fixture
def clean_registry():
    """Provide a clean registry for each test"""
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


class TestRelationshipMetadata:
    """Tests for RelationshipMetadata dataclass"""

    def test_create_basic_relationship(self):
        rel = RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        )
        assert rel.name == "stays"
        assert rel.target_entity == "StayRecord"
        assert rel.cardinality == "one_to_many"
        assert rel.foreign_key == "guest_id"
        assert rel.foreign_key_entity == "StayRecord"
        assert rel.inverse_name is None
        assert rel.description == ""

    def test_create_relationship_with_inverse(self):
        rel = RelationshipMetadata(
            name="guest",
            target_entity="Guest",
            cardinality="many_to_one",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
            inverse_name="stays",
            description="The guest who owns this stay record",
        )
        assert rel.inverse_name == "stays"
        assert rel.description == "The guest who owns this stay record"

    def test_to_llm_description(self):
        rel = RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
            inverse_name="guest",
            description="Guest's stay records",
        )
        desc = rel.to_llm_description()
        assert "stays" in desc
        assert "StayRecord" in desc
        assert "one_to_many" in desc
        assert "guest" in desc  # inverse_name

    def test_to_llm_description_without_inverse(self):
        rel = RelationshipMetadata(
            name="room_type",
            target_entity="RoomType",
            cardinality="many_to_one",
            foreign_key="room_type_id",
            foreign_key_entity="Room",
        )
        desc = rel.to_llm_description()
        assert "room_type" in desc
        assert "RoomType" in desc
        assert "[反向:" not in desc


class TestEntityMetadataRelationships:
    """Tests for EntityMetadata.relationships and add_relationship()"""

    def test_entity_default_empty_relationships(self):
        entity = EntityMetadata(
            name="Guest",
            description="Hotel guest",
            table_name="guests",
        )
        assert entity.relationships == []

    def test_add_relationship(self):
        entity = EntityMetadata(
            name="Guest",
            description="Hotel guest",
            table_name="guests",
        )
        rel = RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        )
        result = entity.add_relationship(rel)
        assert result is entity  # fluent API
        assert len(entity.relationships) == 1
        assert entity.relationships[0].name == "stays"

    def test_add_multiple_relationships(self):
        entity = EntityMetadata(
            name="Guest",
            description="Hotel guest",
            table_name="guests",
        )
        entity.add_relationship(RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        ))
        entity.add_relationship(RelationshipMetadata(
            name="reservations",
            target_entity="Reservation",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="Reservation",
        ))
        assert len(entity.relationships) == 2

    def test_relationships_isolation_between_instances(self):
        """Ensure mutable default doesn't leak between instances"""
        e1 = EntityMetadata(name="A", description="", table_name="a")
        e2 = EntityMetadata(name="B", description="", table_name="b")
        e1.add_relationship(RelationshipMetadata(
            name="x", target_entity="X", cardinality="one_to_one",
            foreign_key="x_id", foreign_key_entity="A",
        ))
        assert len(e1.relationships) == 1
        assert len(e2.relationships) == 0


class TestRegistryModelMethods:
    """Tests for OntologyRegistry model registration and retrieval"""

    def test_register_model(self, clean_registry):
        class FakeModel:
            __tablename__ = "fake"
        clean_registry.register_model("Fake", FakeModel)
        assert clean_registry.get_model("Fake") is FakeModel

    def test_get_model_nonexistent(self, clean_registry):
        assert clean_registry.get_model("NonExistent") is None

    def test_get_model_map(self, clean_registry):
        class ModelA:
            pass
        class ModelB:
            pass
        clean_registry.register_model("A", ModelA)
        clean_registry.register_model("B", ModelB)
        model_map = clean_registry.get_model_map()
        assert model_map == {"A": ModelA, "B": ModelB}

    def test_get_model_map_returns_copy(self, clean_registry):
        class ModelA:
            pass
        clean_registry.register_model("A", ModelA)
        m1 = clean_registry.get_model_map()
        m2 = clean_registry.get_model_map()
        assert m1 is not m2  # returns new dict each time


class TestRegistryRelationshipMethods:
    """Tests for OntologyRegistry relationship registration and retrieval"""

    def test_register_relationship(self, clean_registry):
        rel = RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        )
        result = clean_registry.register_relationship("Guest", rel)
        assert result is clean_registry  # fluent API

    def test_get_relationships(self, clean_registry):
        rel = RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        )
        clean_registry.register_relationship("Guest", rel)
        rels = clean_registry.get_relationships("Guest")
        assert len(rels) == 1
        assert rels[0].name == "stays"

    def test_get_relationships_empty(self, clean_registry):
        assert clean_registry.get_relationships("NonExistent") == []

    def test_get_relationships_returns_copy(self, clean_registry):
        rel = RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        )
        clean_registry.register_relationship("Guest", rel)
        r1 = clean_registry.get_relationships("Guest")
        r2 = clean_registry.get_relationships("Guest")
        assert r1 is not r2

    def test_register_relationship_syncs_to_entity(self, clean_registry):
        """When entity is already registered, adding a relationship should sync"""
        entity = EntityMetadata(name="Guest", description="Guest", table_name="guests")
        clean_registry.register_entity(entity)
        rel = RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        )
        clean_registry.register_relationship("Guest", rel)
        # Should be synced to entity's relationships
        assert len(entity.relationships) == 1
        assert entity.relationships[0].name == "stays"

    def test_get_relationship_map_format(self, clean_registry):
        """get_relationship_map() should return query_engine compatible format"""
        clean_registry.register_relationship("Guest", RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        ))
        clean_registry.register_relationship("StayRecord", RelationshipMetadata(
            name="guest",
            target_entity="Guest",
            cardinality="many_to_one",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        ))
        rmap = clean_registry.get_relationship_map()
        assert "Guest" in rmap
        assert "StayRecord" in rmap["Guest"]
        assert rmap["Guest"]["StayRecord"]["rel_attr"] == "stays"
        assert rmap["Guest"]["StayRecord"]["foreign_key"] == "guest_id"
        assert rmap["StayRecord"]["Guest"]["rel_attr"] == "guest"

    def test_multiple_relationships_per_entity(self, clean_registry):
        clean_registry.register_relationship("Guest", RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        ))
        clean_registry.register_relationship("Guest", RelationshipMetadata(
            name="reservations",
            target_entity="Reservation",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="Reservation",
        ))
        rels = clean_registry.get_relationships("Guest")
        assert len(rels) == 2
        rmap = clean_registry.get_relationship_map()
        assert "StayRecord" in rmap["Guest"]
        assert "Reservation" in rmap["Guest"]


class TestRegistryClearIncludesNewFields:
    """Ensure clear() resets models and relationships"""

    def test_clear_resets_models(self, clean_registry):
        class FakeModel:
            pass
        clean_registry.register_model("Fake", FakeModel)
        clean_registry.clear()
        assert clean_registry.get_model("Fake") is None

    def test_clear_resets_relationships(self, clean_registry):
        clean_registry.register_relationship("Guest", RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
        ))
        clean_registry.clear()
        assert clean_registry.get_relationships("Guest") == []


class TestExportSchemaIncludesRelationships:
    """Ensure export_schema includes relationship data"""

    def test_export_schema_has_relationships_key(self, clean_registry):
        schema = clean_registry.export_schema()
        assert "relationships" in schema

    def test_export_schema_with_relationships(self, clean_registry):
        clean_registry.register_relationship("Guest", RelationshipMetadata(
            name="stays",
            target_entity="StayRecord",
            cardinality="one_to_many",
            foreign_key="guest_id",
            foreign_key_entity="StayRecord",
            inverse_name="guest",
        ))
        schema = clean_registry.export_schema()
        assert "Guest" in schema["relationships"]
        rel_list = schema["relationships"]["Guest"]
        assert len(rel_list) == 1
        assert rel_list[0]["name"] == "stays"
        assert rel_list[0]["target_entity"] == "StayRecord"
        assert rel_list[0]["cardinality"] == "one_to_many"
        assert rel_list[0]["inverse_name"] == "guest"
