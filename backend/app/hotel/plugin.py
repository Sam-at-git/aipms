"""
Hotel Domain Plugin.

Encapsulates all hotel-specific bootstrap logic for the generic framework.
"""
import logging
from typing import List, Optional, Callable

logger = logging.getLogger(__name__)


class HotelPlugin:
    """Hotel domain plugin — registers all hotel-specific resources."""

    @property
    def name(self) -> str:
        return "hotel"

    def get_routers(self) -> List:
        """Return all hotel domain routers."""
        from app.hotel.routers import get_hotel_routers
        return get_hotel_routers()

    def register_actions(self, action_registry) -> None:
        """Register hotel action handlers."""
        from app.hotel.actions import register_hotel_actions
        register_hotel_actions(action_registry)

        # SPEC-P01: Register role-based prompt filters
        # Cleaners only need task-related actions; exclude everything else
        # Receptionists don't need admin/pricing/employee management
        from core.ai.prompt_shaper import register_role_filter
        register_role_filter("cleaner", {
            "admin", "billing", "reservation", "pricing",
            "employee_management", "query", "front_desk",
        })
        register_role_filter("receptionist", {
            "admin", "pricing", "employee_management",
        })

        # SPEC-P05: Attach ActionSearchEngine for keyword-based action discovery
        from core.ai.action_search import ActionSearchEngine
        search_engine = ActionSearchEngine()
        action_registry.set_search_engine(search_engine)
        action_registry.populate_search_engine()

    def register_ontology(self, ont_registry) -> None:
        """Register hotel domain ontology: entities, relationships, rules, adapter."""
        # Register domain relationships
        from core.domain.relationships import relationship_registry
        from app.hotel.domain.relationships import register_hotel_relationships
        register_hotel_relationships(relationship_registry)

        # Register business rules
        from app.hotel.domain.rules import register_all_rules
        from core.engine.rule_engine import rule_engine
        register_all_rules(rule_engine)

        # Bootstrap HotelDomainAdapter
        from app.hotel.hotel_domain_adapter import HotelDomainAdapter
        adapter = HotelDomainAdapter()
        adapter.register_ontology(ont_registry)
        logger.info(f"Hotel ontology registered ({len(ont_registry.get_entities())} entities)")

        # Initialize hotel business rules (domain layer)
        from app.hotel.business_rules import init_hotel_business_rules
        init_hotel_business_rules()

    def register_events(self) -> None:
        """Register hotel event handlers and alert handlers."""
        from app.hotel.services.event_handlers import register_event_handlers
        register_event_handlers()

        from app.services.alert_service import register_alert_handlers
        register_alert_handlers()

    def register_security(self) -> None:
        """Register hotel ACL permissions and role permissions."""
        # Configure admin roles
        from core.security.context import SecurityContext
        SecurityContext.set_admin_roles({"sysadmin", "manager"})

        # Register hotel role permissions
        from app.hotel.security import register_hotel_role_permissions
        register_hotel_role_permissions()

        # Register hotel domain ACL permissions
        from core.security.attribute_acl import AttributeACL, AttributePermission, SecurityLevel
        acl = AttributeACL()
        acl.register_domain_permissions([
            AttributePermission("Guest", "phone", SecurityLevel.CONFIDENTIAL),
            AttributePermission("Guest", "id_card", SecurityLevel.RESTRICTED),
            AttributePermission("Guest", "blacklist_reason", SecurityLevel.RESTRICTED),
            AttributePermission("Guest", "tier", SecurityLevel.INTERNAL),
            AttributePermission("Room", "price", SecurityLevel.INTERNAL),
            AttributePermission("Employee", "salary", SecurityLevel.RESTRICTED, allow_write=False),
            AttributePermission("Employee", "password_hash", SecurityLevel.RESTRICTED, allow_read=False),
            AttributePermission("Bill", "total_amount", SecurityLevel.INTERNAL),
        ])

    def get_seed_function(self) -> Optional[Callable]:
        """Return hotel seed data function."""
        return None  # Hotel seed data handled by init_data.py for now
