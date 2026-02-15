"""
core/ai/actions.py

Action registration and dispatch system.

This module provides a declarative way to register AI-executable actions,
replacing the monolithic if/else chain in ai_service.py.

Key components:
- ActionDefinition: Complete definition of an action
- ActionRegistry: Central registry for all actions
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Type, TYPE_CHECKING, Literal
import inspect
import logging

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.ai.vector_store import VectorStore
    from core.ai.reflexion import ReflexionLoop


# Category types for actions
ActionCategory = Literal["query", "mutation", "system", "tool", "webhook", "notification", "interface"]


@dataclass
class ActionDefinition:
    """
    Complete definition of an AI-executable action.

    Based on Palantir Foundry's Action Type concept and AIP Logic's action system.

    Attributes:
        name: Unique action identifier (e.g., "walkin_checkin")
        entity: The primary entity this action operates on (e.g., "Guest")
        description: Human-readable description for LLM context
        category: Type of action - query, mutation, system, or tool
        parameters_schema: Pydantic model for parameter validation
        handler: The actual function that executes the action
        requires_confirmation: Whether this action needs user confirmation
        allowed_roles: Set of roles allowed to execute this action
        undoable: Whether this action can be undone
        side_effects: List of side effects this action may cause
        search_keywords: Additional keywords for semantic search
        semantic_category: Category for domain glossary (e.g., "guest_type", "action_type")
        category_description: Human-readable description of the semantic_category (provided by domain layer)
        glossary_examples: Correct/incorrect extraction examples for LLM guidance (provided by domain layer)
    """

    # Identity
    name: str
    entity: str
    description: str

    # Classification
    category: str

    # Parameters (Pydantic model)
    parameters_schema: Type[BaseModel]

    # Execution
    handler: Callable

    # Metadata
    requires_confirmation: bool = True
    allowed_roles: Set[str] = field(default_factory=set)
    undoable: bool = False
    side_effects: List[str] = field(default_factory=list)

    # Effects declarations (SPEC-4: state changes this action produces)
    effects: List[str] = field(default_factory=list)

    # Search keywords (for semantic matching)
    search_keywords: List[str] = field(default_factory=list)

    # Semantic category (for domain glossary)
    semantic_category: Optional[str] = None
    category_description: Optional[str] = None
    glossary_examples: List[Dict[str, str]] = field(default_factory=list)

    # UI workflow: required fields for the follow-up form (overrides schema introspection)
    ui_required_fields: Optional[List[str]] = None

    def to_openai_tool(self) -> Dict[str, Any]:
        """
        Convert to OpenAI function calling format.

        Returns a dictionary compatible with OpenAI's Tools API:
        https://platform.openai.com/docs/guides/function-calling

        Returns:
            {
                "type": "function",
                "function": {
                    "name": "walkin_checkin",
                    "description": "...",
                    "parameters": {...JSON Schema...}
                }
            }
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema.model_json_schema()
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary representation.

        Useful for API responses and debugging.
        """
        return {
            "name": self.name,
            "entity": self.entity,
            "description": self.description,
            "category": self.category,
            "requires_confirmation": self.requires_confirmation,
            "allowed_roles": list(self.allowed_roles),
            "undoable": self.undoable,
            "side_effects": self.side_effects,
            "effects": self.effects,
            "search_keywords": self.search_keywords,
            "semantic_category": self.semantic_category,
            "category_description": self.category_description,
            "glossary_examples": self.glossary_examples
        }


class ActionRegistry:
    """
    Central registry for all AI-executable actions.

    Replaces the monolithic if/else chain in ai_service.py with a declarative,
    type-safe dispatch system.

    Features:
    - Decorator-based registration
    - Automatic parameter validation via Pydantic
    - Role-based access control
    - Optional vector-based semantic search (via VectorStore)

    Example:
        ```python
        registry = ActionRegistry()

        @registry.register(
            name="walkin_checkin",
            entity="Guest",
            description="Handle walk-in guest check-in",
            category="mutation"
        )
        def handle_checkin(params: CheckInParams, db: Session, user: Employee) -> Dict:
            # ... implementation
            return {"status": "success"}

        # Later
        result = registry.dispatch(
            "walkin_checkin",
            {"guest_name": "张三", "room_id": 101},
            {"db": db_session, "user": current_user}
        )
        ```
    """

    def __init__(self, vector_store: Optional["VectorStore"] = None, ontology_registry=None,
                 state_machine_executor=None, constraint_engine=None, guard_executor=None):
        """
        Initialize the action registry.

        Args:
            vector_store: Optional VectorStore for semantic search.
                         If None, attempts to create one automatically (SPEC-09).
            ontology_registry: Optional OntologyRegistry for automatic ActionMetadata sync.
            state_machine_executor: Optional StateMachineExecutor for pre-dispatch state validation.
            constraint_engine: Optional ConstraintEngine for pre-dispatch constraint validation.
            guard_executor: Optional GuardExecutor for unified pre-dispatch guard (SPEC-2).
        """
        self._actions: Dict[str, ActionDefinition] = {}
        self._ontology_registry = ontology_registry
        self._state_machine_executor = state_machine_executor
        self._constraint_engine = constraint_engine
        self._guard_executor = guard_executor

        # SPEC-09: Auto-create VectorStore if not provided
        if vector_store is None:
            self.vector_store = self._create_vector_store()
        else:
            self.vector_store = vector_store

        if self.vector_store:
            logger.info("ActionRegistry: VectorStore enabled for semantic search")
        else:
            logger.info("ActionRegistry: VectorStore unavailable, using full tool listing")

    def _create_vector_store(self) -> Optional["VectorStore"]:
        """
        Attempt to create a VectorStore for action indexing.

        SPEC-09: Auto-creates VectorStore with persistent storage when available.

        Returns:
            VectorStore instance if successful, None otherwise
        """
        try:
            from core.ai import get_embedding_service
            from core.ai.vector_store import VectorStore
            from pathlib import Path

            embedding_service = get_embedding_service()

            # Only create if embedding service is enabled
            if embedding_service and embedding_service.enabled:
                # Persistent storage to avoid re-indexing on restart
                db_path = "data/action_vectors.db"

                # Ensure directory exists
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)

                return VectorStore(
                    db_path=db_path,
                    embedding_service=embedding_service
                )
        except Exception as e:
            logger.warning(f"Failed to create VectorStore: {e}")

        return None

    def register(
        self,
        name: str,
        entity: str,
        description: str,
        category: str = "mutation",
        requires_confirmation: bool = True,
        allowed_roles: Optional[Set[str]] = None,
        undoable: bool = False,
        side_effects: Optional[List[str]] = None,
        effects: Optional[List[str]] = None,
        search_keywords: Optional[List[str]] = None,
        semantic_category: Optional[str] = None,
        category_description: Optional[str] = None,
        glossary_examples: Optional[List[Dict[str, str]]] = None,
        ui_required_fields: Optional[List[str]] = None,
    ) -> Callable:
        """
        Decorator for registering actions.

        Extracts the parameters schema from the handler function's type hints.
        The first parameter (after 'self' if present) should be a Pydantic BaseModel.

        Args:
            name: Unique action identifier
            entity: Primary entity this action operates on
            description: Human-readable description for LLM
            category: Action type - query, mutation, system, or tool
            requires_confirmation: Whether this action needs user confirmation
            allowed_roles: Set of roles allowed to execute this action
            undoable: Whether this action can be undone
            side_effects: List of side effects this action may cause
            search_keywords: Additional keywords for semantic search
            semantic_category: Category for domain glossary (e.g., "guest_type", "action_type")
            category_description: Human-readable description of the category (domain-provided)
            glossary_examples: List of {"correct": ..., "incorrect": ...} dicts for LLM guidance

        Returns:
            Decorator function that registers the handler

        Raises:
            ValueError: If handler doesn't have a Pydantic model as first parameter
        """
        def decorator(func: Callable) -> Callable:
            # Extract parameters schema from function signature
            params_model = self._extract_params_model(func)

            if params_model is None:
                raise ValueError(
                    f"Handler '{name}' must have a Pydantic BaseModel as first parameter. "
                    f"Got signature: {inspect.signature(func)}"
                )

            # Create action definition
            definition = ActionDefinition(
                name=name,
                entity=entity,
                description=description,
                category=category,
                parameters_schema=params_model,
                handler=func,
                requires_confirmation=requires_confirmation,
                allowed_roles=allowed_roles or set(),
                undoable=undoable,
                side_effects=side_effects or [],
                effects=effects or [],
                search_keywords=search_keywords or [],
                semantic_category=semantic_category,
                category_description=category_description,
                glossary_examples=glossary_examples or [],
                ui_required_fields=ui_required_fields,
            )

            # Register
            self._actions[name] = definition
            logger.info(f"Registered action: {name} (entity={entity}, category={category})")

            # Sync to OntologyRegistry if available
            if self._ontology_registry is not None:
                self._sync_to_ontology_registry(definition)

            # Index to vector store if available
            if self.vector_store:
                self._index_action(definition)

            return func

        return decorator

    def _extract_params_model(self, func: Callable) -> Optional[Type[BaseModel]]:
        """
        Extract Pydantic model from handler signature.

        The handler should have signature like:
            def handle(params: MyParams, db: Session, user: Employee) -> Dict

        Returns:
            The Pydantic model class, or None if not found
        """
        sig = inspect.signature(func)
        parameters = list(sig.parameters.values())

        # Skip 'self' parameter if present (method)
        start_idx = 1 if parameters and parameters[0].name == "self" else 0

        if len(parameters) > start_idx:
            first_param = parameters[start_idx]
            annotation = first_param.annotation

            # Check if it's a Pydantic BaseModel
            if (
                inspect.isclass(annotation)
                and issubclass(annotation, BaseModel)
            ):
                return annotation

        return None

    def _sync_to_ontology_registry(self, definition: ActionDefinition) -> None:
        """
        Sync an ActionDefinition to OntologyRegistry as ActionMetadata.

        Eliminates the dual-registration problem by auto-creating ActionMetadata
        from ActionDefinition when an OntologyRegistry is configured.
        """
        try:
            from core.ontology.metadata import ActionMetadata, ActionParam, ParamType

            # Convert Pydantic schema fields to ActionParam list
            params = []
            if definition.parameters_schema:
                schema = definition.parameters_schema.model_json_schema()
                properties = schema.get("properties", {})
                required_fields = set(schema.get("required", []))

                type_mapping = {
                    "string": ParamType.STRING,
                    "integer": ParamType.INTEGER,
                    "number": ParamType.NUMBER,
                    "boolean": ParamType.BOOLEAN,
                    "array": ParamType.ARRAY,
                    "object": ParamType.OBJECT,
                }

                for field_name, field_info in properties.items():
                    field_type = field_info.get("type", "string")
                    # Handle anyOf patterns (Optional fields)
                    if "anyOf" in field_info:
                        for opt in field_info["anyOf"]:
                            if opt.get("type") != "null":
                                field_type = opt.get("type", "string")
                                break
                    param = ActionParam(
                        name=field_name,
                        type=type_mapping.get(field_type, ParamType.STRING),
                        required=field_name in required_fields,
                        description=field_info.get("description", ""),
                        enum_values=field_info.get("enum"),
                    )
                    params.append(param)

            metadata = ActionMetadata(
                action_type=definition.name,
                entity=definition.entity,
                method_name=definition.name,
                description=definition.description,
                params=params,
                requires_confirmation=definition.requires_confirmation,
                undoable=definition.undoable,
                side_effects=definition.side_effects,
                post_conditions=definition.effects,
                allowed_roles=definition.allowed_roles,
            )

            self._ontology_registry.register_action(definition.entity, metadata)
            logger.debug(f"Synced action '{definition.name}' to OntologyRegistry")

        except Exception as e:
            logger.warning(f"Failed to sync action '{definition.name}' to OntologyRegistry: {e}")

    def set_ontology_registry(self, ontology_registry) -> None:
        """
        Set the OntologyRegistry and sync all already-registered actions.

        SPEC-R11: Enables late-binding when ActionRegistry is created before
        OntologyRegistry is populated.

        Args:
            ontology_registry: The OntologyRegistry instance to sync actions to.
        """
        self._ontology_registry = ontology_registry
        # Sync all existing actions
        for definition in self._actions.values():
            self._sync_to_ontology_registry(definition)
        logger.info(f"ActionRegistry: Synced {len(self._actions)} actions to OntologyRegistry")

    def _index_action(self, definition: ActionDefinition) -> None:
        """
        Index action for semantic search.

        Creates a SchemaItem and adds it to the vector store.
        This enables get_relevant_tools() to work.

        SPEC-09: Enhanced with better search keywords and metadata.

        Args:
            definition: The action definition to index
        """
        if self.vector_store is None:
            logger.debug(f"ActionRegistry: No VectorStore, skipping index for {definition.name}")
            return

        from core.ai.vector_store import SchemaItem

        # Create searchable text (description + keywords + entity)
        # SPEC-09: Include entity name for better semantic matching
        searchable_parts = [definition.description]
        if definition.search_keywords:
            searchable_parts.extend(definition.search_keywords)
        searchable_parts.append(f"实体: {definition.entity}")
        searchable_text = " ".join(searchable_parts)

        item = SchemaItem(
            id=definition.name,
            type="action",
            entity=definition.entity,
            name=definition.name,
            description=searchable_text,
            synonyms=definition.search_keywords,
            metadata={
                "category": definition.category,
                "requires_confirmation": definition.requires_confirmation,
                "allowed_roles": list(definition.allowed_roles),
                "undoable": definition.undoable
            }
        )

        try:
            self.vector_store.index_items([item])
            logger.info(f"ActionRegistry: Indexed action '{definition.name}' to VectorStore")
        except Exception as e:
            logger.warning(f"Failed to index action {definition.name}: {e}")

    def get_action(self, name: str) -> Optional[ActionDefinition]:
        """
        Get action definition by name.

        Args:
            name: Action name

        Returns:
            ActionDefinition if found, None otherwise
        """
        return self._actions.get(name)

    def list_actions(self) -> List[ActionDefinition]:
        """
        List all registered actions.

        Returns:
            List of all ActionDefinitions
        """
        return list(self._actions.values())

    def list_actions_by_entity(self, entity: str) -> List[ActionDefinition]:
        """
        List actions for a specific entity.

        Args:
            entity: Entity name (e.g., "Guest")

        Returns:
            List of ActionDefinitions for the entity
        """
        return [
            action for action in self._actions.values()
            if action.entity == entity
        ]

    def list_actions_by_category(self, category: str) -> List[ActionDefinition]:
        """
        List actions by category.

        Args:
            category: Category - query, mutation, system, or tool

        Returns:
            List of ActionDefinitions in the category
        """
        return [
            action for action in self._actions.values()
            if action.category == category
        ]

    def dispatch(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute an action with parameter validation.

        Replaces the if/else chain in ai_service.py's execute_action().

        Args:
            action_name: Name of the action to execute
            params: Raw parameters dictionary (will be validated)
            context: Execution context (db, user, etc.)

        Returns:
            Result dictionary from the handler

        Raises:
            ValueError: If action is not found
            ValidationError: If parameters don't match schema
            PermissionError: If user role not in allowed_roles
        """
        action_def = self.get_action(action_name)

        if action_def is None:
            available = ", ".join(self._actions.keys())
            raise ValueError(
                f"Unknown action: {action_name}. "
                f"Available actions: {available}"
            )

        # Validate parameters
        try:
            validated_params = action_def.parameters_schema(**params)
        except ValidationError as e:
            logger.warning(f"Parameter validation failed for {action_name}: {e}")
            raise

        # Guard 2: State machine validation (if executor available)
        guard_result = self._run_guards(action_def, params, context)
        if guard_result is not None:
            return guard_result

        # Guard 4: Check permissions if allowed_roles is set
        user = context.get("user")
        if action_def.allowed_roles and user:
            user_role = getattr(user, "role", None)
            if user_role and user_role.value not in action_def.allowed_roles:
                raise PermissionError(
                    f"Role '{user_role.value}' not allowed for action '{action_name}'. "
                    f"Allowed roles: {action_def.allowed_roles}"
                )

        # Execute handler
        logger.info(f"Dispatching action: {action_name} with params: {validated_params.model_dump()}")
        result = action_def.handler(validated_params, **context)

        return result

    def _run_guards(
        self,
        action_def: ActionDefinition,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Run pre-dispatch guards (SPEC-12, SPEC-2).

        Returns None if all guards pass, or a structured error dict if a guard fails.
        Uses GuardExecutor (SPEC-2) when available, falls back to legacy guards.
        """
        # SPEC-2: Use GuardExecutor if available
        if self._guard_executor and action_def.entity:
            result = self._guard_executor.check(
                entity=action_def.entity,
                action=action_def.name,
                params=params,
                context=context
            )
            if not result.allowed:
                violations = result.violations
                return {
                    "success": False,
                    "error_code": "guard_violation",
                    "message": violations[0].message if violations else "Guard check failed",
                    "violations": [v.__dict__ for v in violations],
                    "warnings": [w.__dict__ for w in result.warnings],
                    "suggestions": result.suggestions,
                }

        # Legacy guards (used when GuardExecutor is not configured)

        # Guard 2: State machine validation
        if self._state_machine_executor:
            current_state = context.get("current_state")
            target_state = context.get("target_state")
            if current_state and target_state:
                user_role = None
                user = context.get("user")
                if user:
                    role = getattr(user, "role", None)
                    user_role = role.value if hasattr(role, "value") else str(role) if role else None
                result = self._state_machine_executor.validate_transition(
                    action_def.entity, current_state, target_state, user_role
                )
                if not result.allowed:
                    return {
                        "success": False,
                        "error_code": "state_error",
                        "message": result.reason,
                        "valid_alternatives": result.valid_alternatives,
                    }

        # Guard 3: Constraint validation (only if entity_state provided)
        if self._constraint_engine and "entity_state" in context:
            current_state_dict = context.get("entity_state", {})
            user_context = context.get("user_context", {})
            constraint_result = self._constraint_engine.validate_action(
                entity_type=action_def.entity,
                action_type=action_def.name,
                params=params,
                current_state=current_state_dict,
                user_context=user_context,
            )
            if not constraint_result.is_valid:
                return {
                    "success": False,
                    "error_code": "constraint_violation",
                    "message": constraint_result.to_llm_feedback() or "Constraint violation",
                    "violated_constraints": constraint_result.violated_constraints,
                    "suggestions": constraint_result.suggestions,
                }

        return None

    def dispatch_with_reflexion(
        self,
        action_name: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
        reflexion_loop: Optional["ReflexionLoop"] = None,
    ) -> Dict[str, Any]:
        """
        Dispatch with optional reflexion loop for self-healing.

        When a ReflexionLoop is provided, delegates to its execute_with_reflexion
        method which handles retry logic, auto-correction, and LLM-based reflection.
        Without a ReflexionLoop, falls back to standard dispatch.

        Args:
            action_name: Name of the action to execute
            params: Raw parameters dictionary
            context: Execution context (db, user, etc.)
            reflexion_loop: Optional ReflexionLoop for self-healing retry

        Returns:
            Result dictionary from the handler (or wrapped result from ReflexionLoop)
        """
        if reflexion_loop:
            return reflexion_loop.execute_with_reflexion(action_name, params, context)
        return self.dispatch(action_name, params, context)

    def get_relevant_tools(
        self,
        query: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get relevant tools via semantic search.

        For small action counts (< 20), returns all tools.
        For larger counts, uses vector search to find top-K relevant actions.

        SPEC-09: Enhanced with true vector search when VectorStore available.

        Args:
            query: Natural language query
            top_k: Maximum number of tools to return

        Returns:
            List of OpenAI tool format dictionaries
        """
        # No VectorStore: return all tools
        if self.vector_store is None:
            logger.debug(f"get_relevant_tools: No VectorStore, returning all {len(self._actions)} tools")
            return [
                action.to_openai_tool()
                for action in self._actions.values()
            ]

        # Small scale: return all (vector search not worth it)
        if len(self._actions) <= 20:
            logger.debug(f"get_relevant_tools: Only {len(self._actions)} actions, returning all")
            return [
                action.to_openai_tool()
                for action in self._actions.values()
            ]

        # Large scale: use vector search
        try:
            search_results = self.vector_store.search(
                query,
                top_k=top_k,
                item_type="action"
            )

            # Convert results to OpenAI tools (preserving search order)
            tools = []
            for result in search_results:
                if result.id in self._actions:
                    tools.append(self._actions[result.id].to_openai_tool())

            logger.debug(f"get_relevant_tools: Found {len(tools)} relevant tools for query: {query}")
            return tools

        except Exception as e:
            logger.warning(f"Vector search failed: {e}, falling back to all tools")
            return [
                action.to_openai_tool()
                for action in self._actions.values()
            ]

    def export_all_tools(self) -> List[Dict[str, Any]]:
        """
        Export all actions as OpenAI tools.

        Useful for initializing LLM context with all available tools.

        Returns:
            List of all tools in OpenAI format
        """
        return [
            action.to_openai_tool()
            for action in self._actions.values()
        ]

    def reindex_all_actions(self) -> Dict[str, Any]:
        """
        Re-index all registered actions to VectorStore.

        SPEC-09: Useful when:
        - VectorStore was unavailable during registration
        - Action definitions were updated
        - VectorStore database was reset

        Returns:
            {
                "indexed": 5,
                "failed": 0,
                "total": 5
            }
        """
        if self.vector_store is None:
            return {
                "indexed": 0,
                "failed": len(self._actions),
                "total": len(self._actions),
                "error": "VectorStore not available"
            }

        indexed = 0
        failed = 0

        for action_def in self._actions.values():
            try:
                self._index_action(action_def)
                # Only increment indexed after successful indexing
                indexed += 1
            except Exception as e:
                logger.warning(f"Failed to re-index {action_def.name}: {e}")
                failed += 1

        logger.info(f"ActionRegistry: Re-indexed {indexed}/{len(self._actions)} actions")

        return {
            "indexed": indexed,
            "failed": failed,
            "total": len(self._actions)
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with counts and breakdowns
        """
        total = len(self._actions)
        by_entity: Dict[str, int] = {}
        by_category: Dict[str, int] = {}

        for action in self._actions.values():
            by_entity[action.entity] = by_entity.get(action.entity, 0) + 1
            by_category[action.category] = by_category.get(action.category, 0) + 1

        return {
            "total_actions": total,
            "by_entity": by_entity,
            "by_category": by_category
        }

    def get_domain_glossary(self) -> Dict[str, Dict[str, Any]]:
        """
        Build domain glossary from all registered actions.

        Collects and categorizes search_keywords to help the LLM distinguish
        between semantic signals (domain keywords) and parameter values.

        All domain-specific knowledge (category descriptions, examples) comes
        from action registration metadata — the framework itself is domain-agnostic.

        Returns:
            Dictionary mapping semantic categories to their definitions:
            {
                "checkin_type": {
                    "keywords": ["散客", "直接入住"],
                    "meaning": "入住方式（预订入住 vs 直接入住）",
                    "examples": [
                        {"correct": "...", "incorrect": "..."}
                    ]
                }
            }
        """
        glossary: Dict[str, Dict[str, Any]] = {}

        for action_def in self._actions.values():
            if not action_def.semantic_category or not action_def.search_keywords:
                continue

            category = action_def.semantic_category

            if category not in glossary:
                glossary[category] = {
                    "keywords": [],
                    "meaning": action_def.category_description or category,
                    "examples": []
                }
            elif action_def.category_description and glossary[category]["meaning"] == category:
                # Upgrade from bare category name if a description is now available
                glossary[category]["meaning"] = action_def.category_description

            # Add keywords (avoid duplicates)
            for kw in action_def.search_keywords:
                if kw not in glossary[category]["keywords"]:
                    glossary[category]["keywords"].append(kw)

            # Add examples from registration (avoid duplicates)
            for ex in action_def.glossary_examples:
                if ex not in glossary[category]["examples"]:
                    glossary[category]["examples"].append(ex)

        return glossary


__all__ = [
    "ActionDefinition",
    "ActionRegistry",
    "ActionCategory",
]
