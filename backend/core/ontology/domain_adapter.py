"""
core/ontology/domain_adapter.py

Domain adapter interface - Allows any business domain to integrate with the framework
Part of the universal ontology-driven LLM reasoning framework
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.ontology.registry import OntologyRegistry


class IDomainAdapter(ABC):
    """
    领域适配器接口

    每个业务领域需要实现此接口，将其领域特定的本体
    注册到框架中。

    Example:
        ```python
        class HotelDomainAdapter(IDomainAdapter):
            def get_domain_name(self) -> str:
                return "Hotel Management System"

            def register_ontology(self, registry: OntologyRegistry) -> None:
                registry.register_entity(EntityMetadata(...))
                registry.register_action("Room", ActionMetadata(...))

            def get_current_state(self) -> Dict[str, Any]:
                return {"total_rooms": 100, "occupied": 65}

            def execute_action(self, action_type: str, params: Dict, context: Dict) -> Dict:
                # Delegate to domain-specific services
                if action_type == "checkin":
                    return CheckInService().check_in(**params)
                return {"error": "Unknown action"}
        ```
    """

    @abstractmethod
    def get_domain_name(self) -> str:
        """
        获取领域名称

        Returns:
            领域的人类可读名称
        """
        pass

    @abstractmethod
    def register_ontology(self, registry: "OntologyRegistry") -> None:
        """
        注册领域本体到框架

        Args:
            registry: 本体注册表实例
        """
        pass

    @abstractmethod
    def get_current_state(self) -> Dict[str, Any]:
        """
        获取当前系统状态 (用于注入上下文)

        Returns:
            包含当前系统状态的字典，例如:
            {
                "total_rooms": 100,
                "occupied_rooms": 65,
                "occupancy_rate": "65%"
            }
        """
        pass

    @abstractmethod
    def execute_action(
        self,
        action_type: str,
        params: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行领域特定的操作

        Args:
            action_type: 操作类型 (如 "checkin", "checkout")
            params: 操作参数
            context: 执行上下文 (如用户信息)

        Returns:
            操作结果字典，例如:
            {
                "success": True,
                "message": "Check-in successful",
                "result": {...}
            }
        """
        pass

    def get_llm_system_prompt_additions(self) -> str:
        """
        获取领域特定的 LLM 提示词补充 (可选)

        Returns:
            领域特定的系统提示词内容，用于补充框架默认提示
        """
        return ""

    def get_entity_display_name(self, entity_type: str, entity_id: Any) -> str:
        """
        获取实体的显示名称 (可选)

        Args:
            entity_type: 实体类型名称
            entity_id: 实体ID

        Returns:
            实体的人类可读显示名称
        """
        return f"{entity_type}:{entity_id}"

    # ========== OODA Orchestrator Support Methods ==========
    # These methods allow the domain adapter to inject domain-specific logic
    # into the generic OODA orchestrator without the orchestrator knowing
    # about any specific business domain.

    def build_llm_context(self, db) -> Dict[str, Any]:
        """Build domain-specific context for LLM prompts.

        Returns context data the LLM needs to make informed decisions,
        e.g., available inventory, active transactions, pending tasks.
        """
        return {}

    def enhance_action_params(self, action_type: str, params: Dict[str, Any],
                              message: str, db) -> Dict[str, Any]:
        """Enhance LLM-extracted params with DB lookups.

        Resolves fuzzy references (e.g., room name → room_id) and fills
        in derived fields that the LLM cannot know.
        """
        return params

    def enhance_single_action_params(self, action_type: str, params: Dict[str, Any],
                                     db) -> Dict[str, Any]:
        """Simplified param enhancement for follow-up mode (single action)."""
        return params

    def get_field_definition(self, param_name: str, action_type: str,
                             current_params: Dict[str, Any], db) -> Optional[Any]:
        """Get UI field definition for a missing parameter.

        Returns a MissingField-like object with field type, options, etc.
        for the frontend to render an input form.
        """
        return None

    def get_report_data(self, db) -> Dict[str, Any]:
        """Get domain-specific dashboard/report data."""
        return {}

    def get_help_text(self, language: str = "zh") -> str:
        """Get domain-specific help text for the AI assistant."""
        return ""

    def get_display_names(self) -> Dict[str, str]:
        """Get field name → display name mapping for follow-up messages."""
        return {}

    # ========== SPEC-04: Classification & HITL Support ==========

    def get_admin_roles(self) -> List[str]:
        """Return list of role names considered admin/manager level."""
        return []

    def get_query_examples(self) -> List[Dict[str, Any]]:
        """Return LLM prompt query examples for this domain."""
        return []

    def get_context_summary(self, db, additional_context: Dict[str, Any]) -> List[str]:
        """Format business context as user message lines for the LLM."""
        return []

    def get_hitl_risk_overrides(self) -> Dict[str, Any]:
        """Return action_name → ConfirmationLevel overrides for HITL."""
        return {}

    def get_hitl_custom_rules(self) -> List[Callable]:
        """Return custom HITL rule functions for domain-specific confirmation logic."""
        return []


# Export
__all__ = ["IDomainAdapter"]
