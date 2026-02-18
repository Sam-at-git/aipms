"""
app/services/schema_index_service.py

Schema indexing service - bridges OntologyRegistry and VectorStore.

Extracts schema items (entities, properties, actions) from the OntologyRegistry
and indexes them in the VectorStore for semantic search.
"""
from typing import Dict, List, Any, Optional
import logging

from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import EntityMetadata, ActionMetadata, PropertyMetadata
from core.ai import VectorStore, SchemaItem, get_embedding_service


logger = logging.getLogger(__name__)


class SchemaIndexService:
    """
    Schema indexing service

    Builds and maintains the semantic search index for ontology items.
    Extracts entities, properties, and actions from OntologyRegistry
    and creates SchemaItems with embeddings for VectorStore.

    Example:
        >>> service = SchemaIndexService()
        >>> service.build_index()
        >>> stats = service.get_stats()
        >>> print(stats["total_items"])
    """

    # Manual relationship map for entities that don't have explicit relationship metadata
    # Format: {entity_name: {relationship_name: (target_entity, cardinality)}}
    _RELATIONSHIP_MAP = {
        "Guest": {
            "stay_records": ("StayRecord", "one_to_many"),
        },
        "StayRecord": {
            "guest": ("Guest", "many_to_one"),
            "room": ("Room", "many_to_one"),
            "bill": ("Bill", "one_to_one"),
        },
        "Room": {
            "stay_records": ("StayRecord", "one_to_many"),
            "tasks": ("Task", "one_to_many"),
            "room_type": ("RoomType", "many_to_one"),
        },
        "Reservation": {
            "guest": ("Guest", "many_to_one"),
            "room_type": ("RoomType", "many_to_one"),
        },
        "Task": {
            "room": ("Room", "many_to_one"),
            "assignee": ("Employee", "many_to_one"),
        },
        "Bill": {
            "stay_record": ("StayRecord", "one_to_one"),
        },
    }

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        registry: Optional[OntologyRegistry] = None
    ):
        """
        Initialize schema index service

        Args:
            vector_store: VectorStore instance (creates default if None)
            registry: OntologyRegistry instance (uses global singleton if None)
        """
        self.vector_store = vector_store or VectorStore(
            db_path="backend/data/schema_index.db",
            embedding_service=get_embedding_service()
        )
        self.registry = registry or OntologyRegistry()

    def build_index(self) -> None:
        """
        Build the initial index from OntologyRegistry

        Extracts all entities, properties, and actions and creates
        corresponding SchemaItems with embeddings.
        """
        logger.info("Building schema index from OntologyRegistry")

        items: List[SchemaItem] = []

        # Index entities
        for entity_metadata in self.registry.get_entities():
            items.extend(self._extract_from_entity(entity_metadata))

        # Index actions
        for action_metadata in self.registry.get_actions():
            items.append(self._extract_from_action(action_metadata))

        # Batch index all items
        if items:
            self.vector_store.index_items(items)
            logger.info(f"Indexed {len(items)} schema items")
        else:
            logger.warning("No schema items found to index")

    def rebuild_index(self) -> None:
        """Clear and rebuild the index"""
        logger.info("Rebuilding schema index")
        self.vector_store.clear()
        self.build_index()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get index statistics

        Returns:
            Dict with index size, breakdown by type/entity, etc.
        """
        return self.vector_store.get_stats()

    def _extract_from_entity(self, entity: EntityMetadata) -> List[SchemaItem]:
        """
        Extract SchemaItems from an EntityMetadata

        Creates:
        - One SchemaItem for the entity itself
        - One SchemaItem for each property

        Args:
            entity: EntityMetadata object

        Returns:
            List of SchemaItem objects
        """
        items = []

        # Entity item
        items.append(SchemaItem(
            id=entity.name,
            type="entity",
            entity=entity.name,
            name=entity.name,
            description=entity.description,
            synonyms=self._get_entity_synonyms(entity),
            metadata={
                "table_name": entity.table_name,
                "is_aggregate_root": entity.is_aggregate_root,
                "category": entity.category
            }
        ))

        # Property items
        for prop_name, prop in entity.properties.items():
            items.append(SchemaItem(
                id=f"{entity.name}.{prop_name}",
                type="property",
                entity=entity.name,
                name=prop_name,
                description=self._get_property_description(entity.name, prop),
                synonyms=self._get_property_synonyms(prop_name, prop),
                metadata={
                    "property_type": prop.type.value if hasattr(prop.type, 'value') else str(prop.type),
                    "is_required": prop.is_required,
                    "is_searchable": prop.searchable if hasattr(prop, 'searchable') else False,
                }
            ))

        return items

    def _extract_from_action(self, action: ActionMetadata) -> SchemaItem:
        """
        Extract SchemaItem from an ActionMetadata

        Args:
            action: ActionMetadata object

        Returns:
            SchemaItem object
        """
        return SchemaItem(
            id=action.action_type,
            type="action",
            entity=action.entity,
            name=action.action_type,
            description=action.description,
            synonyms=self._get_action_synonyms(action),
            metadata={
                "requires_confirmation": action.requires_confirmation,
                "allowed_roles": list(action.allowed_roles) if action.allowed_roles else [],
            }
        )

    def _get_entity_synonyms(self, entity: EntityMetadata) -> List[str]:
        """Get synonyms for an entity (Chinese and English)"""
        synonyms = [entity.name.lower()]

        # Add common Chinese translations
        translations = {
            "Guest": ["客人", "住客", "旅客"],
            "Room": ["房间", "客房"],
            "Reservation": ["预订", "订单"],
            "StayRecord": ["入住记录", "住宿记录"],
            "Bill": ["账单", "费用"],
            "Task": ["任务", "工单"],
            "Employee": ["员工", "工作人员"],
            "RoomType": ["房型", "房间类型"],
        }
        if entity.name in translations:
            synonyms.extend(translations[entity.name])

        return synonyms

    def _get_property_synonyms(self, prop_name: str, prop: PropertyMetadata) -> List[str]:
        """Get synonyms for a property"""
        synonyms = [prop_name.lower()]

        # Add common Chinese translations
        translations = {
            "name": ["姓名", "名字"],
            "phone": ["电话", "手机"],
            "status": ["状态"],
            "room_number": ["房间号", "房号"],
            "check_in_time": ["入住时间", "入住日期"],
            "check_out_time": ["退房时间", "退房日期"],
            "price": ["价格", "费用"],
            "task_type": ["任务类型"],
        }
        if prop_name in translations:
            synonyms.extend(translations[prop_name])

        # Add display name synonym if available
        if hasattr(prop, 'display_name') and prop.display_name:
            synonyms.append(prop.display_name.lower())

        return synonyms

    def _get_action_synonyms(self, action: ActionMetadata) -> List[str]:
        """Get synonyms for an action"""
        synonyms = [action.action_type.lower()]

        # Add common Chinese translations
        translations = {
            "walkin_checkin": ["散客入住", "直接入住", "无预订入住"],
            "checkin": ["办理入住", "入住登记"],
            "checkout": ["办理退房", "退房"],
            "create_reservation": ["创建预订", "新建订单"],
            "cancel_reservation": ["取消预订", "取消订单"],
            "create_task": ["创建任务", "新建工单"],
            "complete_task": ["完成任务", "任务完成"],
        }
        if action.action_type in translations:
            synonyms.extend(translations[action.action_type])

        return synonyms

    def _get_property_description(self, entity_name: str, prop: PropertyMetadata) -> str:
        """Generate a description for a property"""
        parts = [f"{entity_name}的{prop.name}"]

        if hasattr(prop, 'description') and prop.description:
            parts.append(prop.description)

        if prop.is_required:
            parts.append("(必填)")

        return " ".join(parts)

    @classmethod
    def get_relationships(cls, entity_name: str) -> Dict[str, tuple]:
        """
        Get relationships for an entity

        Args:
            entity_name: Name of the entity

        Returns:
            Dict mapping relationship names to (target_entity, cardinality) tuples
        """
        return cls._RELATIONSHIP_MAP.get(entity_name, {})


__all__ = ["SchemaIndexService"]
