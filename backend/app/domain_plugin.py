"""
Domain Plugin Protocol.

Defines the interface that domain-specific plugins must implement
to integrate with the generic application framework.
"""
from typing import Protocol, List, Optional, Callable, Any, runtime_checkable


@runtime_checkable
class DomainPlugin(Protocol):
    """Protocol for domain-specific plugin modules.

    A DomainPlugin encapsulates all domain-specific bootstrap logic:
    ontology registration, action handlers, routers, events, security, and seed data.
    """

    @property
    def name(self) -> str:
        """Domain plugin name (e.g., 'hotel')."""
        ...

    def get_routers(self) -> List:
        """Return list of FastAPI APIRouter instances for this domain."""
        ...

    def register_actions(self, action_registry) -> None:
        """Register domain-specific action handlers with the ActionRegistry."""
        ...

    def register_ontology(self, ont_registry) -> None:
        """Register domain entities, relationships, and metadata with OntologyRegistry."""
        ...

    def register_events(self) -> None:
        """Register domain-specific event handlers and alert handlers."""
        ...

    def register_security(self) -> None:
        """Register domain-specific ACL permissions and role permissions."""
        ...

    def get_seed_function(self) -> Optional[Callable]:
        """Return a callable for seeding domain-specific data, or None."""
        ...
