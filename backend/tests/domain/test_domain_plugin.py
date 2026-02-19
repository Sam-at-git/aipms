"""
tests/domain/test_domain_plugin.py

Tests for app/domain_plugin.py - DomainPlugin Protocol.
"""
import pytest
from typing import runtime_checkable

from app.domain_plugin import DomainPlugin


class TestDomainPluginProtocol:
    """Test that DomainPlugin is a proper Protocol."""

    def test_domain_plugin_is_runtime_checkable(self):
        """DomainPlugin should be decorated with @runtime_checkable."""
        assert hasattr(DomainPlugin, '__protocol_attrs__') or hasattr(DomainPlugin, '__abstractmethods__') or isinstance(DomainPlugin, type)
        # Verify it is runtime_checkable by using isinstance
        # If not runtime_checkable, isinstance would raise TypeError
        class Dummy:
            @property
            def name(self):
                return "test"
            def get_routers(self):
                return []
            def register_actions(self, registry):
                pass
            def register_ontology(self, ont_registry):
                pass
            def register_events(self):
                pass
            def register_security(self):
                pass
            def get_seed_function(self):
                return None

        assert isinstance(Dummy(), DomainPlugin)

    def test_hotel_plugin_satisfies_protocol(self):
        """HotelPlugin should satisfy the DomainPlugin protocol."""
        from app.hotel.plugin import HotelPlugin
        plugin = HotelPlugin()
        assert isinstance(plugin, DomainPlugin)

    def test_incomplete_class_does_not_satisfy(self):
        """A class missing methods should not satisfy the protocol."""
        class Incomplete:
            @property
            def name(self):
                return "test"
            # Missing: get_routers, register_actions, etc.

        assert not isinstance(Incomplete(), DomainPlugin)

    def test_protocol_requires_name_property(self):
        """DomainPlugin protocol defines 'name' as a property."""
        from app.hotel.plugin import HotelPlugin
        plugin = HotelPlugin()
        # name should be accessible as a property
        assert plugin.name == "hotel"

    def test_protocol_defines_get_routers(self):
        """Protocol should define get_routers method."""
        from app.hotel.plugin import HotelPlugin
        plugin = HotelPlugin()
        result = plugin.get_routers()
        assert isinstance(result, list)

    def test_protocol_defines_register_actions(self):
        """Protocol should define register_actions method."""
        from app.hotel.plugin import HotelPlugin
        plugin = HotelPlugin()
        assert callable(plugin.register_actions)

    def test_protocol_defines_register_ontology(self):
        """Protocol should define register_ontology method."""
        from app.hotel.plugin import HotelPlugin
        plugin = HotelPlugin()
        assert callable(plugin.register_ontology)

    def test_protocol_defines_register_events(self):
        """Protocol should define register_events method."""
        from app.hotel.plugin import HotelPlugin
        plugin = HotelPlugin()
        assert callable(plugin.register_events)

    def test_protocol_defines_register_security(self):
        """Protocol should define register_security method."""
        from app.hotel.plugin import HotelPlugin
        plugin = HotelPlugin()
        assert callable(plugin.register_security)

    def test_protocol_defines_get_seed_function(self):
        """Protocol should define get_seed_function method."""
        from app.hotel.plugin import HotelPlugin
        plugin = HotelPlugin()
        result = plugin.get_seed_function()
        assert result is None or callable(result)


class TestDomainPluginCustomImplementation:
    """Test that custom implementations can satisfy the protocol."""

    def test_minimal_implementation(self):
        """A minimal implementation should satisfy the protocol."""
        class MinimalPlugin:
            @property
            def name(self):
                return "minimal"

            def get_routers(self):
                return []

            def register_actions(self, registry):
                pass

            def register_ontology(self, ont_registry):
                pass

            def register_events(self):
                pass

            def register_security(self):
                pass

            def get_seed_function(self):
                return None

        plugin = MinimalPlugin()
        assert isinstance(plugin, DomainPlugin)
        assert plugin.name == "minimal"
        assert plugin.get_routers() == []
        assert plugin.get_seed_function() is None

    def test_implementation_with_seed_function(self):
        """Implementation returning a seed function."""
        def seed_fn():
            pass

        class SeededPlugin:
            @property
            def name(self):
                return "seeded"

            def get_routers(self):
                return []

            def register_actions(self, registry):
                pass

            def register_ontology(self, ont_registry):
                pass

            def register_events(self):
                pass

            def register_security(self):
                pass

            def get_seed_function(self):
                return seed_fn

        plugin = SeededPlugin()
        assert isinstance(plugin, DomainPlugin)
        assert plugin.get_seed_function() is seed_fn
