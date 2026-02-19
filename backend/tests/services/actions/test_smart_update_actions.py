"""
tests/services/actions/test_smart_update_actions.py

Tests for the generic smart update factory in
app/services/actions/smart_update_actions.py
"""
import json
import pytest
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

from sqlalchemy.orm import Session

from core.ai.actions import ActionRegistry
from core.ontology.registry import OntologyRegistry
from app.hotel.hotel_domain_adapter import HotelDomainAdapter
from app.models.ontology import Employee, EmployeeRole, Guest, RoomType
from app.services.actions.base import SmartUpdateParams, UpdateGuestSmartParams
from app.services.actions.smart_update_actions import (
    SmartUpdateConfig,
    parse_smart_update_config,
    build_smart_update_prompt,
    register_smart_update_actions,
    _find_entity,
    _execute_smart_update,
)


# ============== Fixtures ==============

@pytest.fixture
def ontology_registry():
    """Create a populated OntologyRegistry."""
    registry = OntologyRegistry()
    adapter = HotelDomainAdapter()
    adapter.register_ontology(registry)
    return registry


@pytest.fixture
def action_registry():
    """Create a fresh ActionRegistry."""
    return ActionRegistry()


@pytest.fixture
def mock_manager():
    """Mock manager user."""
    user = Mock(spec=Employee)
    user.id = 2
    user.username = "test_manager"
    user.name = "测试经理"
    role_mock = Mock()
    role_mock.value = "manager"
    user.role = role_mock
    return user


@pytest.fixture
def mock_receptionist():
    """Mock receptionist user."""
    user = Mock(spec=Employee)
    user.id = 1
    user.username = "test_front"
    user.name = "测试前台"
    role_mock = Mock()
    role_mock.value = "receptionist"
    user.role = role_mock
    return user


@pytest.fixture
def guest_config():
    """SmartUpdateConfig for Guest entity."""
    return SmartUpdateConfig(
        entity_name="Guest",
        name_column="name",
        editable_fields=["name", "phone", "email"],
        update_schema="GuestUpdate",
        service_class="app.services.guest_service.GuestService",
        service_method="update_guest",
        allowed_roles={"receptionist", "manager"},
        display_name="客人",
    )


# ============== SmartUpdateParams Tests ==============

class TestSmartUpdateParams:
    """Test the generic SmartUpdateParams model."""

    def test_basic_params(self):
        """Test basic entity_id + instructions."""
        params = SmartUpdateParams(entity_id=1, instructions="改电话")
        assert params.entity_id == 1
        assert params.instructions == "改电话"

    def test_entity_name_params(self):
        """Test entity_name + instructions."""
        params = SmartUpdateParams(entity_name="张三", instructions="改电话")
        assert params.entity_name == "张三"

    def test_guest_id_alias(self):
        """Test guest_id resolves to entity_id."""
        params = SmartUpdateParams(guest_id=5, instructions="改电话")
        assert params.entity_id == 5

    def test_guest_name_alias(self):
        """Test guest_name resolves to entity_name."""
        params = SmartUpdateParams(guest_name="李四", instructions="改邮箱")
        assert params.entity_name == "李四"

    def test_employee_id_alias(self):
        """Test employee_id resolves to entity_id."""
        params = SmartUpdateParams(employee_id=3, instructions="改电话")
        assert params.entity_id == 3

    def test_employee_name_alias(self):
        """Test employee_name resolves to entity_name."""
        params = SmartUpdateParams(employee_name="张经理", instructions="改名")
        assert params.entity_name == "张经理"

    def test_room_type_id_alias(self):
        """Test room_type_id resolves to entity_id."""
        params = SmartUpdateParams(room_type_id=2, instructions="改价格")
        assert params.entity_id == 2

    def test_room_type_name_alias(self):
        """Test room_type_name resolves to entity_name."""
        params = SmartUpdateParams(room_type_name="标间", instructions="改描述")
        assert params.entity_name == "标间"

    def test_entity_id_takes_priority_over_alias(self):
        """entity_id explicitly set takes priority over aliases."""
        params = SmartUpdateParams(entity_id=10, guest_id=5, instructions="改电话")
        assert params.entity_id == 10

    def test_empty_instructions_raises(self):
        """Empty instructions should raise validation error."""
        with pytest.raises(Exception):
            SmartUpdateParams(entity_id=1, instructions="")

    def test_whitespace_instructions_raises(self):
        """Whitespace-only instructions should raise."""
        with pytest.raises(Exception):
            SmartUpdateParams(entity_id=1, instructions="   ")

    def test_backward_compat_alias(self):
        """UpdateGuestSmartParams is an alias for SmartUpdateParams."""
        assert UpdateGuestSmartParams is SmartUpdateParams


# ============== Config Parsing Tests ==============

class TestParseSmartUpdateConfig:
    """Test config parsing from entity extensions."""

    def test_parse_enabled(self):
        raw = {
            "enabled": True,
            "identifier_fields": {"name_column": "name"},
            "editable_fields": ["name", "phone"],
            "update_schema": "GuestUpdate",
            "service_class": "app.services.guest_service.GuestService",
            "service_method": "update_guest",
            "allowed_roles": {"receptionist", "manager"},
            "display_name": "客人",
        }
        config = parse_smart_update_config("Guest", raw)
        assert config is not None
        assert config.entity_name == "Guest"
        assert config.editable_fields == ["name", "phone"]
        assert config.display_name == "客人"

    def test_parse_disabled(self):
        raw = {"enabled": False}
        config = parse_smart_update_config("Guest", raw)
        assert config is None

    def test_parse_none(self):
        config = parse_smart_update_config("Guest", None)
        assert config is None

    def test_parse_empty(self):
        config = parse_smart_update_config("Guest", {})
        assert config is None


# ============== Factory Registration Tests ==============

class TestFactoryRegistration:
    """Test that the factory auto-registers correct actions."""

    def test_registers_guest_smart(self, action_registry, ontology_registry):
        """Guest entity should get update_guest_smart registered."""
        register_smart_update_actions(action_registry, ontology_registry)
        action = action_registry.get_action("update_guest_smart")
        assert action is not None
        assert action.entity == "Guest"
        assert action.category == "front_desk"

    def test_registers_employee_smart(self, action_registry, ontology_registry):
        """Employee entity should get update_employee_smart registered."""
        register_smart_update_actions(action_registry, ontology_registry)
        action = action_registry.get_action("update_employee_smart")
        assert action is not None
        assert action.entity == "Employee"

    def test_registers_roomtype_smart(self, action_registry, ontology_registry):
        """RoomType entity should get update_roomtype_smart registered."""
        register_smart_update_actions(action_registry, ontology_registry)
        action = action_registry.get_action("update_roomtype_smart")
        assert action is not None
        assert action.entity == "RoomType"

    def test_non_smart_entities_skipped(self, action_registry, ontology_registry):
        """Entities without smart_update config should not get registered."""
        register_smart_update_actions(action_registry, ontology_registry)
        # Room has no smart_update config
        assert action_registry.get_action("update_room_smart") is None
        # Bill has no smart_update config
        assert action_registry.get_action("update_bill_smart") is None

    def test_allowed_roles_set(self, action_registry, ontology_registry):
        """Allowed roles should be set from config."""
        register_smart_update_actions(action_registry, ontology_registry)
        guest_action = action_registry.get_action("update_guest_smart")
        assert "receptionist" in guest_action.allowed_roles
        assert "manager" in guest_action.allowed_roles

        employee_action = action_registry.get_action("update_employee_smart")
        assert "manager" in employee_action.allowed_roles
        assert "receptionist" not in employee_action.allowed_roles


# ============== Prompt Building Tests ==============

class TestBuildSmartUpdatePrompt:
    """Test dynamic prompt building from PropertyMetadata."""

    def test_guest_prompt_contains_fields(self, guest_config, ontology_registry):
        """Prompt should contain all editable field labels and current values."""
        guest = Mock()
        guest.name = "张三"
        guest.phone = "13800138000"
        guest.email = "zhangsan@test.com"

        prompt = build_smart_update_prompt(guest_config, guest, "改电话后两位为77", ontology_registry)

        assert "张三" in prompt
        assert "13800138000" in prompt
        assert "zhangsan@test.com" in prompt
        assert "改电话后两位为77" in prompt
        # Should contain field labels
        assert "姓名" in prompt or "name" in prompt
        assert "手机号" in prompt or "phone" in prompt

    def test_prompt_with_none_values(self, guest_config, ontology_registry):
        """None values should appear as '无' in prompt."""
        guest = Mock()
        guest.name = "张三"
        guest.phone = None
        guest.email = None

        prompt = build_smart_update_prompt(guest_config, guest, "设置邮箱", ontology_registry)
        assert "无" in prompt

    def test_prompt_json_template(self, guest_config, ontology_registry):
        """Prompt should include JSON response template with new_ prefix."""
        guest = Mock()
        guest.name = "张三"
        guest.phone = "13800138000"
        guest.email = None

        prompt = build_smart_update_prompt(guest_config, guest, "改电话", ontology_registry)
        assert "new_name" in prompt
        assert "new_phone" in prompt
        assert "new_email" in prompt
        assert "explanation" in prompt


# ============== Entity Lookup Tests ==============

class TestFindEntity:
    """Test entity lookup by id and name."""

    def test_find_by_id(self, db_session, ontology_registry, guest_config):
        """Find entity by ID."""
        guest = Guest(name="张三", phone="13800138000")
        db_session.add(guest)
        db_session.commit()

        params = SmartUpdateParams(entity_id=guest.id, instructions="改电话")
        result = _find_entity(guest_config, params, db_session, ontology_registry)
        assert "entity" in result
        assert result["entity"].name == "张三"

    def test_find_by_id_not_found(self, db_session, ontology_registry, guest_config):
        """Entity not found by ID returns error."""
        params = SmartUpdateParams(entity_id=999, instructions="改电话")
        result = _find_entity(guest_config, params, db_session, ontology_registry)
        assert "error" in result
        assert "999" in result["error"]

    def test_find_by_exact_name(self, db_session, ontology_registry, guest_config):
        """Find entity by exact name match."""
        guest = Guest(name="张三", phone="13800138000")
        db_session.add(guest)
        db_session.commit()

        params = SmartUpdateParams(entity_name="张三", instructions="改电话")
        result = _find_entity(guest_config, params, db_session, ontology_registry)
        assert "entity" in result
        assert result["entity"].name == "张三"

    def test_find_by_fuzzy_name(self, db_session, ontology_registry, guest_config):
        """Find entity by fuzzy name match (LIKE)."""
        guest = Guest(name="张三丰", phone="13800138000")
        db_session.add(guest)
        db_session.commit()

        params = SmartUpdateParams(entity_name="三丰", instructions="改电话")
        result = _find_entity(guest_config, params, db_session, ontology_registry)
        assert "entity" in result
        assert result["entity"].name == "张三丰"

    def test_find_by_name_not_found(self, db_session, ontology_registry, guest_config):
        """Name not found returns error."""
        params = SmartUpdateParams(entity_name="不存在的人", instructions="改电话")
        result = _find_entity(guest_config, params, db_session, ontology_registry)
        assert "error" in result
        assert "not_found" in result.get("error_code", "")

    def test_find_by_name_ambiguous(self, db_session, ontology_registry, guest_config):
        """Multiple fuzzy matches returns ambiguous error with candidates."""
        db_session.add(Guest(name="张三哥", phone="13800138001"))
        db_session.add(Guest(name="张三弟", phone="13800138002"))
        db_session.commit()

        # No exact match, fuzzy "张三" matches both
        params = SmartUpdateParams(entity_name="张三", instructions="改电话")
        result = _find_entity(guest_config, params, db_session, ontology_registry)
        assert "error" in result
        assert "ambiguous" in result.get("error_code", "")
        assert "candidates" in result
        assert len(result["candidates"]) == 2

    def test_find_missing_identifier(self, db_session, ontology_registry, guest_config):
        """No id or name returns missing_identifier error."""
        params = SmartUpdateParams(instructions="改电话")
        result = _find_entity(guest_config, params, db_session, ontology_registry)
        assert "error" in result
        assert "missing_identifier" in result.get("error_code", "")


# ============== Smart Update Execution Tests ==============

class TestExecuteSmartUpdate:
    """Test the full smart update execution flow."""

    @patch("app.services.actions.smart_update_actions.LLMService")
    def test_successful_update(self, MockLLMService, db_session, ontology_registry, guest_config, mock_receptionist):
        """Successful smart update with mocked LLM."""
        # Setup guest
        guest = Guest(name="张三", phone="13800138000")
        db_session.add(guest)
        db_session.commit()

        # Mock LLM
        mock_llm = MockLLMService.return_value
        mock_llm.is_enabled.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "new_name": None,
            "new_phone": "13800138077",
            "new_email": None,
            "explanation": "将电话号码后两位改为77",
        })
        mock_llm.client.chat.completions.create.return_value = mock_response
        mock_llm.model = "test-model"

        params = SmartUpdateParams(entity_id=guest.id, instructions="电话号码后两位改为77")
        result = _execute_smart_update(params, db_session, mock_receptionist, guest_config, ontology_registry)

        assert result["success"] is True
        assert "13800138077" in result["message"]
        assert result["updated_fields"]["phone"] == "13800138077"

    @patch("app.services.actions.smart_update_actions.LLMService")
    def test_llm_disabled(self, MockLLMService, db_session, ontology_registry, guest_config, mock_receptionist):
        """LLM disabled returns appropriate error."""
        guest = Guest(name="张三", phone="13800138000")
        db_session.add(guest)
        db_session.commit()

        mock_llm = MockLLMService.return_value
        mock_llm.is_enabled.return_value = False

        params = SmartUpdateParams(entity_id=guest.id, instructions="改电话")
        result = _execute_smart_update(params, db_session, mock_receptionist, guest_config, ontology_registry)

        assert result["success"] is False
        assert "llm_disabled" in result.get("error", "")

    @patch("app.services.actions.smart_update_actions.LLMService")
    def test_no_updates_parsed(self, MockLLMService, db_session, ontology_registry, guest_config, mock_receptionist):
        """LLM returns all nulls → no_updates error."""
        guest = Guest(name="张三", phone="13800138000")
        db_session.add(guest)
        db_session.commit()

        mock_llm = MockLLMService.return_value
        mock_llm.is_enabled.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "new_name": None,
            "new_phone": None,
            "new_email": None,
            "explanation": "没有明确修改指令",
        })
        mock_llm.client.chat.completions.create.return_value = mock_response
        mock_llm.model = "test-model"

        params = SmartUpdateParams(entity_id=guest.id, instructions="什么都不改")
        result = _execute_smart_update(params, db_session, mock_receptionist, guest_config, ontology_registry)

        assert result["success"] is False
        assert "no_updates" in result.get("error", "")

    @patch("app.services.actions.smart_update_actions.LLMService")
    def test_entity_not_found(self, MockLLMService, db_session, ontology_registry, guest_config, mock_receptionist):
        """Entity not found returns error without calling LLM."""
        params = SmartUpdateParams(entity_id=999, instructions="改电话")
        result = _execute_smart_update(params, db_session, mock_receptionist, guest_config, ontology_registry)

        assert result["success"] is False
        assert "999" in result["message"]
        # LLM should not have been called
        MockLLMService.return_value.client.chat.completions.create.assert_not_called()

    @patch("app.services.actions.smart_update_actions.LLMService")
    def test_constraint_violation(self, MockLLMService, db_session, ontology_registry, guest_config, mock_receptionist):
        """Constraint violation (e.g., invalid phone format) blocks update."""
        guest = Guest(name="张三", phone="13800138000")
        db_session.add(guest)
        db_session.commit()

        mock_llm = MockLLMService.return_value
        mock_llm.is_enabled.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "new_name": None,
            "new_phone": "abc",  # Invalid phone format
            "new_email": None,
            "explanation": "改为abc",
        })
        mock_llm.client.chat.completions.create.return_value = mock_response
        mock_llm.model = "test-model"

        params = SmartUpdateParams(entity_id=guest.id, instructions="电话改为abc")
        result = _execute_smart_update(params, db_session, mock_receptionist, guest_config, ontology_registry)

        # Constraint engine should reject invalid phone format
        assert result["success"] is False

    @patch("app.services.actions.smart_update_actions.LLMService")
    def test_llm_call_fails(self, MockLLMService, db_session, ontology_registry, guest_config, mock_receptionist):
        """LLM API error returns llm_error."""
        guest = Guest(name="张三", phone="13800138000")
        db_session.add(guest)
        db_session.commit()

        mock_llm = MockLLMService.return_value
        mock_llm.is_enabled.return_value = True
        mock_llm.client.chat.completions.create.side_effect = Exception("API timeout")
        mock_llm.model = "test-model"

        params = SmartUpdateParams(entity_id=guest.id, instructions="改电话")
        result = _execute_smart_update(params, db_session, mock_receptionist, guest_config, ontology_registry)

        assert result["success"] is False
        assert "llm_error" in result.get("error", "")

    @patch("app.services.actions.smart_update_actions.LLMService")
    def test_update_multiple_fields(self, MockLLMService, db_session, ontology_registry, guest_config, mock_receptionist):
        """Update multiple fields at once."""
        guest = Guest(name="张三", phone="13800138000", email="old@test.com")
        db_session.add(guest)
        db_session.commit()

        mock_llm = MockLLMService.return_value
        mock_llm.is_enabled.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "new_name": "张三丰",
            "new_phone": None,
            "new_email": "new@test.com",
            "explanation": "改名和邮箱",
        })
        mock_llm.client.chat.completions.create.return_value = mock_response
        mock_llm.model = "test-model"

        params = SmartUpdateParams(entity_id=guest.id, instructions="名字改为张三丰，邮箱改为new@test.com")
        result = _execute_smart_update(params, db_session, mock_receptionist, guest_config, ontology_registry)

        assert result["success"] is True
        assert "张三丰" in result["message"]
        assert "new@test.com" in result["message"]
        assert result["updated_fields"]["name"] == "张三丰"
        assert result["updated_fields"]["email"] == "new@test.com"


# ============== Integration via ActionRegistry.dispatch ==============

class TestSmartUpdateDispatch:
    """Test dispatching via ActionRegistry (integration-level)."""

    @patch("app.services.actions.smart_update_actions.LLMService")
    def test_dispatch_update_guest_smart(self, MockLLMService, db_session, ontology_registry):
        """Dispatch update_guest_smart through ActionRegistry."""
        registry = ActionRegistry()
        register_smart_update_actions(registry, ontology_registry)

        # Setup guest
        guest = Guest(name="张三", phone="13800138000")
        db_session.add(guest)
        db_session.commit()

        # Mock LLM
        mock_llm = MockLLMService.return_value
        mock_llm.is_enabled.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "new_name": None,
            "new_phone": "13900139000",
            "new_email": None,
            "explanation": "更新电话",
        })
        mock_llm.client.chat.completions.create.return_value = mock_response
        mock_llm.model = "test-model"

        # Create mock user
        user = Mock(spec=Employee)
        user.id = 1
        role_mock = Mock()
        role_mock.value = "receptionist"
        user.role = role_mock

        result = registry.dispatch(
            "update_guest_smart",
            {"guest_id": guest.id, "instructions": "电话改为13900139000"},
            {"db": db_session, "user": user},
        )

        assert result["success"] is True
        assert "13900139000" in result["message"]

    @patch("app.services.actions.smart_update_actions.LLMService")
    def test_dispatch_with_entity_name(self, MockLLMService, db_session, ontology_registry):
        """Dispatch with entity_name (via guest_name alias)."""
        registry = ActionRegistry()
        register_smart_update_actions(registry, ontology_registry)

        guest = Guest(name="李四", phone="13900139000")
        db_session.add(guest)
        db_session.commit()

        mock_llm = MockLLMService.return_value
        mock_llm.is_enabled.return_value = True
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "new_name": None,
            "new_phone": None,
            "new_email": "lisi@test.com",
            "explanation": "设置邮箱",
        })
        mock_llm.client.chat.completions.create.return_value = mock_response
        mock_llm.model = "test-model"

        user = Mock(spec=Employee)
        user.id = 1
        role_mock = Mock()
        role_mock.value = "manager"
        user.role = role_mock

        result = registry.dispatch(
            "update_guest_smart",
            {"guest_name": "李四", "instructions": "邮箱设为lisi@test.com"},
            {"db": db_session, "user": user},
        )

        assert result["success"] is True
        assert "lisi@test.com" in result["message"]
