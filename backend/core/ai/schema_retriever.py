"""
core/ai/schema_retriever.py

Schema retrieval service with semantic search and relationship expansion.

Provides semantic search over ontology schema with automatic relationship
expansion to include related entities (e.g., Guest → StayRecord).
"""
from typing import Dict, List, Any, Optional, Set
import logging

from core.ontology.registry import OntologyRegistry
from core.ai import VectorStore, SchemaItem


logger = logging.getLogger(__name__)


class SchemaRetriever:
    """
    Schema retriever with semantic search and relationship expansion

    Provides dynamic schema retrieval based on user queries.
    Automatically expands selected entities to include their related entities.

    Example:
        >>> retriever = SchemaRetriever()
        >>> result = retriever.retrieve_for_query("查询在住客人姓名")
        >>> print(result["entities"])  # ["Guest", "StayRecord"]
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        registry: Optional[OntologyRegistry] = None
    ):
        """
        Initialize schema retriever

        Args:
            vector_store: VectorStore instance (creates default if None)
            registry: OntologyRegistry instance (uses global singleton if None)
        """
        from core.ai import get_embedding_service

        self.vector_store = vector_store or VectorStore(
            db_path="backend/data/schema_index.db",
            embedding_service=get_embedding_service()
        )
        self.registry = registry or OntologyRegistry()
        self._relationship_map_cache: Optional[Dict[str, Dict[str, tuple]]] = None

    @property
    def relationship_map(self) -> Dict[str, Dict[str, tuple]]:
        """Build relationship map dynamically from OntologyRegistry."""
        if self._relationship_map_cache is None:
            result: Dict[str, Dict[str, tuple]] = {}
            for entity in self.registry.get_entities():
                rels = self.registry.get_relationships(entity.name)
                if rels:
                    result[entity.name] = {
                        r.name: (r.target_entity, r.cardinality)
                        for r in rels
                    }
            self._relationship_map_cache = result
        return self._relationship_map_cache

    def retrieve_for_query(
        self,
        user_query: str,
        top_k: int = 5,
        expand_relationships: bool = True
    ) -> Dict[str, Any]:
        """
        Retrieve relevant schema for a user query

        Performs semantic search to find relevant entities/properties/actions,
        then expands to include related entities.

        Args:
            user_query: Natural language query
            top_k: Number of top results to return
            expand_relationships: Whether to automatically expand relationships

        Returns:
            {
                "query": user_query,
                "entities": ["Guest", "StayRecord"],
                "fields": ["Guest.name", "StayRecord.status"],
                "schema_json": {
                    "Guest": {
                        "description": "...",
                        "fields": {...},
                        "relationships": {...}
                    },
                    ...
                },
                "search_metadata": {
                    "total_entities": 30,
                    "selected_count": 2,
                    "expansion_reason": "Guest -> StayRecord (one_to_many)"
                }
            }
        """
        logger.info(f"Retrieving schema for query: {user_query}")

        # Step 1: Semantic search
        search_results = self.vector_store.search(user_query, top_k=top_k)

        if not search_results:
            logger.warning(f"No schema items found for query: {user_query}")
            return self._empty_result(user_query)

        # Step 2: Extract entities from results
        entities = self._extract_entities(search_results)
        fields = self._extract_fields(search_results)

        # Step 3: Expand relationships
        expansion_reasons = []
        if expand_relationships:
            entities, expansion_reasons = self._expand_relationships(entities)

        # Step 4: Build schema JSON
        schema_json = self._build_schema_json(entities)

        # Step 5: Gather metadata
        search_metadata = {
            "total_entities": len(self.registry.get_entities()),
            "selected_count": len(entities),
            "field_count": len(fields),
            "expansion_reasons": expansion_reasons
        }

        return {
            "query": user_query,
            "entities": list(entities),
            "fields": fields,
            "schema_json": schema_json,
            "search_metadata": search_metadata
        }

    def retrieve_by_entity(
        self,
        entity_names: List[str]
    ) -> Dict[str, Any]:
        """
        Retrieve schema for specific entities

        Args:
            entity_names: List of entity names to retrieve

        Returns:
            Schema JSON for the specified entities
        """
        entities = set(entity_names)
        schema_json = self._build_schema_json(entities)

        return {
            "entities": list(entities),
            "schema_json": schema_json,
            "search_metadata": {
                "total_entities": len(self.registry.get_entities()),
                "selected_count": len(entities),
                "requested": True
            }
        }

    def _extract_entities(self, results: List[SchemaItem]) -> Set[str]:
        """Extract unique entity names from search results"""
        entities = set()
        for item in results:
            if item.type == "entity":
                entities.add(item.entity)
            elif item.type in ["property", "action"]:
                entities.add(item.entity)
        return entities

    def _extract_fields(self, results: List[SchemaItem]) -> List[str]:
        """Extract field identifiers from search results"""
        fields = []
        for item in results:
            if item.type == "property":
                fields.append(item.id)
        return fields

    def _expand_relationships(
        self,
        entities: Set[str]
    ) -> tuple[Set[str], List[str]]:
        """
        Expand entities to include their related entities

        Args:
            entities: Initial set of entity names

        Returns:
            Tuple of (expanded_entities, expansion_reasons)
        """
        expanded = set(entities)
        reasons = []
        visited = set(entities)  # Track visited to prevent infinite loops

        # Single-hop expansion
        for entity in list(entities):
            if entity in self.relationship_map:
                for rel_name, (target_entity, cardinality) in self.relationship_map[entity].items():
                    if target_entity not in visited:
                        expanded.add(target_entity)
                        visited.add(target_entity)
                        reasons.append(
                            f"{entity} -> {target_entity} ({rel_name}, {cardinality})"
                        )

        return expanded, reasons

    def _build_schema_json(self, entities: Set[str]) -> Dict[str, Any]:
        """
        Build JSON schema for the specified entities

        Args:
            entities: Set of entity names

        Returns:
            JSON schema dict with entity descriptions, fields, and relationships
        """
        schema = {}

        for entity_name in entities:
            entity_metadata = self.registry.get_entity(entity_name)

            if not entity_metadata:
                # Build minimal schema from relationship map
                schema[entity_name] = self._build_minimal_schema(entity_name)
                continue

            # Build full schema from metadata
            entity_schema = {
                "description": entity_metadata.description,
                "table_name": entity_metadata.table_name,
                "fields": {},
                "relationships": {}
            }

            # Add fields
            for prop_name, prop in entity_metadata.properties.items():
                field_info = {
                    "type": prop.type.value if hasattr(prop.type, 'value') else str(prop.type),
                    "required": prop.is_required
                }
                if hasattr(prop, 'description') and prop.description:
                    field_info["description"] = prop.description
                if hasattr(prop, 'display_name') and prop.display_name:
                    field_info["display_name"] = prop.display_name

                entity_schema["fields"][prop_name] = field_info

            # Add relationships
            if entity_name in self.relationship_map:
                for rel_name, (target_entity, cardinality) in self.relationship_map[entity_name].items():
                    entity_schema["relationships"][rel_name] = {
                        "target_entity": target_entity,
                        "cardinality": cardinality
                    }

            # Add actions
            actions = self.registry.get_actions(entity_name)
            if actions:
                entity_schema["actions"] = [
                    {
                        "name": action.action_type,
                        "description": action.description,
                        "requires_confirmation": action.requires_confirmation
                    }
                    for action in actions
                ]

            schema[entity_name] = entity_schema

        return schema

    def _build_minimal_schema(self, entity_name: str) -> Dict[str, Any]:
        """Build minimal schema for entities without full metadata"""
        return {
            "description": f"{entity_name} entity",
            "fields": {},
            "relationships": {}
        }

    def _empty_result(self, query: str) -> Dict[str, Any]:
        """Return empty result when no matches found"""
        return {
            "query": query,
            "entities": [],
            "fields": [],
            "schema_json": {},
            "search_metadata": {
                "total_entities": len(self.registry.get_entities()),
                "selected_count": 0,
                "field_count": 0,
                "message": "No relevant schema items found"
            }
        }

    def get_index_stats(self) -> Dict[str, Any]:
        """Get statistics about the schema index"""
        return self.vector_store.get_stats()


__all__ = ["SchemaRetriever"]
