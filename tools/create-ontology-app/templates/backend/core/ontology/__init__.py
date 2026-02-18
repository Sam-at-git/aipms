"""Ontology framework: entity metadata, query engine, semantic resolution"""
from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import (
    EntityMetadata,
    PropertyMetadata,
    ActionMetadata,
    StateMachine,
    BusinessRule,
    ConstraintMetadata,
    RelationshipMetadata,
    EventMetadata,
)
from core.ontology.query import StructuredQuery, FilterOperator
from core.ontology.query_engine import QueryEngine
from core.ontology.semantic_query import SemanticQuery
from core.ontology.semantic_path_resolver import SemanticPathResolver
from core.ontology.domain_adapter import IDomainAdapter
from core.ontology.base import BaseEntity

__all__ = [
    "OntologyRegistry",
    "EntityMetadata", "PropertyMetadata", "ActionMetadata",
    "StateMachine", "BusinessRule", "ConstraintMetadata",
    "RelationshipMetadata", "EventMetadata",
    "StructuredQuery", "FilterOperator",
    "QueryEngine",
    "SemanticQuery",
    "SemanticPathResolver",
    "IDomainAdapter",
    "BaseEntity",
]
