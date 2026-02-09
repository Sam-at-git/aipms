"""
Test price action handlers
"""
import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import Mock
from app.services.actions.price_actions import register_price_actions
from core.ai.actions import ActionRegistry
from app.models.ontology import Employee, RoomType, RoomStatus


class TestRegisterPriceActions:
    """Test price action registration"""

    def test_register_price_actions(self, clean_registry):
        """Test that price actions can be registered"""
        registry = ActionRegistry()
        register_price_actions(registry)

        actions = registry.list_actions()
        action_names = [a.name for a in actions]

        assert "update_price" in action_names
        assert "create_rate_plan" in action_names

        # Check update_price action metadata
        update_action = registry.get_action("update_price")
        assert update_action is not None
        assert update_action.entity == "RatePlan"
        assert update_action.category == "mutation"
        assert update_action.requires_confirmation is True


class TestHandleUpdatePrice:
    """Test update_price handler"""

    def test_update_base_price_with_room_type_id(self, db_session, sample_room_type_luxury, mock_manager, clean_registry):
        """Test updating base price with room_type_id"""
        from app.services.actions.price_actions import register_price_actions
        from app.services.param_parser_service import ParamParserService

        registry = ActionRegistry()
        register_price_actions(registry)

        param_parser = ParamParserService(db_session)

        params = {
            "room_type": sample_room_type_luxury.id,
            "price": Decimal("660.00"),
            "update_type": "base_price"
        }

        context = {
            "db": db_session,
            "user": mock_manager,
            "param_parser": param_parser
        }

        result = registry.dispatch("update_price", params, context)

        assert result["success"] is True
        assert "660" in result["message"] or "660" in str(result.get("new_price", ""))

        # Verify database was updated
        db_session.refresh(sample_room_type_luxury)
        assert sample_room_type_luxury.base_price == Decimal("660.00")

    def test_update_weekend_price_with_chinese(self, db_session, sample_room_type_luxury, mock_manager, clean_registry):
        """Test updating weekend price with Chinese input"""
        from app.services.actions.price_actions import register_price_actions
        from app.services.param_parser_service import ParamParserService

        registry = ActionRegistry()
        register_price_actions(registry)

        param_parser = ParamParserService(db_session)

        params = {
            "room_type": "豪华",  # Using room type name
            "price": Decimal("880.00"),
            "update_type": "rate_plan",
            "price_type": "周末"  # Chinese for weekend
        }

        context = {
            "db": db_session,
            "user": mock_manager,
            "param_parser": param_parser
        }

        result = registry.dispatch("update_price", params, context)

        assert result["success"] is True
        assert result["room_type_name"] == "豪华间"
        assert "880" in result["message"]

    def test_update_price_standard_type(self, db_session, sample_room_type_luxury, mock_manager, clean_registry):
        """Test updating standard price type"""
        from app.services.actions.price_actions import register_price_actions
        from app.services.param_parser_service import ParamParserService

        registry = ActionRegistry()
        register_price_actions(registry)

        param_parser = ParamParserService(db_session)

        params = {
            "room_type": sample_room_type_luxury.id,
            "price": Decimal("550.00"),
            "update_type": "rate_plan",
            "price_type": "standard"
        }

        context = {
            "db": db_session,
            "user": mock_manager,
            "param_parser": param_parser
        }

        result = registry.dispatch("update_price", params, context)

        assert result["success"] is True


class TestHandleCreateRatePlan:
    """Test create_rate_plan handler"""

    def test_create_rate_plan_success(self, db_session, sample_room_type_luxury, mock_manager, clean_registry):
        """Test creating a rate plan"""
        from app.services.actions.price_actions import register_price_actions
        from app.services.param_parser_service import ParamParserService

        registry = ActionRegistry()
        register_price_actions(registry)

        param_parser = ParamParserService(db_session)

        start_date = date.today()
        end_date = date(start_date.year, start_date.month + 1, 1)

        params = {
            "room_type": sample_room_type_luxury.id,
            "name": "春节期间特惠",
            "price": Decimal("999.00"),
            "start_date": start_date,
            "end_date": end_date,
            "is_weekend": False
        }

        context = {
            "db": db_session,
            "user": mock_manager,
            "param_parser": param_parser
        }

        result = registry.dispatch("create_rate_plan", params, context)

        assert result["success"] is True
        assert "rate_plan_id" in result
        assert result["room_type_name"] == "豪华间"
