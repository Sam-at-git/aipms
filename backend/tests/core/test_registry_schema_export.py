"""
测试 core.ontology.registry Schema 导出功能 (SPEC-02.5.1)
"""
import json
import pytest
from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import (
    EntityMetadata,
    ActionMetadata,
    StateMachine,
    StateTransition,
    BusinessRule,
    ActionParam,
    ParamType,
    PropertyMetadata,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """每个测试前清空注册表"""
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


class TestExportSchema:
    """export_schema() 测试"""

    def test_export_empty_schema(self, clean_registry):
        """空注册表导出空 schema"""
        schema = clean_registry.export_schema()
        assert schema["entity_types"] == {}
        assert schema["interfaces"] == {}
        assert schema["actions"] == {}
        assert schema["state_machines"] == {}

    def test_export_schema_with_entity(self, clean_registry):
        """导出包含实体的 schema"""
        clean_registry.register_entity(EntityMetadata(
            name="Room",
            description="酒店房间",
            table_name="rooms",
            is_aggregate_root=False,
        ))

        schema = clean_registry.export_schema()
        assert "Room" in schema["entity_types"]
        room = schema["entity_types"]["Room"]
        assert room["description"] == "酒店房间"
        assert room["table_name"] == "rooms"
        assert room["is_aggregate_root"] is False

    def test_export_schema_with_actions(self, clean_registry):
        """导出包含动作的 schema"""
        clean_registry.register_entity(EntityMetadata(
            name="Room", description="", table_name="rooms"
        ))
        clean_registry.register_action("Room", ActionMetadata(
            action_type="check_in",
            entity="Room",
            method_name="check_in",
            description="办理入住",
            requires_confirmation=False,
            allowed_roles={"manager", "receptionist"},
            params=[
                ActionParam(name="guest_id", type=ParamType.INTEGER, required=True, description="客人ID"),
            ],
        ))

        schema = clean_registry.export_schema()

        # entity_types 中应包含 actions 列表
        assert "check_in" in schema["entity_types"]["Room"]["actions"]

        # actions 中应包含详细信息
        assert "Room.check_in" in schema["actions"]
        action = schema["actions"]["Room.check_in"]
        assert action["description"] == "办理入住"
        assert action["requires_confirmation"] is False
        assert "manager" in action["allowed_roles"]
        assert len(action["params"]) == 1
        assert action["params"][0]["name"] == "guest_id"

    def test_export_schema_with_state_machine(self, clean_registry):
        """导出包含状态机的 schema"""
        clean_registry.register_entity(EntityMetadata(
            name="Room", description="", table_name="rooms"
        ))
        clean_registry.register_state_machine(StateMachine(
            entity="Room",
            states=["vacant_clean", "occupied", "vacant_dirty"],
            transitions=[
                StateTransition(
                    from_state="vacant_clean",
                    to_state="occupied",
                    trigger="check_in",
                ),
                StateTransition(
                    from_state="occupied",
                    to_state="vacant_dirty",
                    trigger="check_out",
                    side_effects=["create_cleaning_task"],
                ),
            ],
            initial_state="vacant_clean",
        ))

        schema = clean_registry.export_schema()

        # entity_types 中应包含 state_machine
        sm = schema["entity_types"]["Room"]["state_machine"]
        assert sm["initial_state"] == "vacant_clean"
        assert "vacant_clean" in sm["states"]
        assert len(sm["transitions"]) == 2
        assert sm["transitions"][1]["side_effects"] == ["create_cleaning_task"]

        # state_machines 顶层也包含
        assert "Room" in schema["state_machines"]

    def test_export_schema_with_interface(self, clean_registry):
        """导出包含接口的 schema"""
        class MockBookable:
            """可预订资源"""
            required_properties = {"name": ParamType.STRING, "status": ParamType.STRING}
            required_actions = ["check_availability", "book"]

        clean_registry.register_interface(MockBookable)
        clean_registry.register_interface_implementation("MockBookable", "Room")

        schema = clean_registry.export_schema()
        assert "MockBookable" in schema["interfaces"]
        iface = schema["interfaces"]["MockBookable"]
        assert "Room" in iface["implementations"]
        assert iface["required_properties"]["name"] == "string"
        assert "check_availability" in iface["required_actions"]

    def test_export_schema_json_serializable(self, clean_registry):
        """验证导出的 schema 可以 JSON 序列化"""
        clean_registry.register_entity(EntityMetadata(
            name="Room", description="酒店房间", table_name="rooms"
        ))
        clean_registry.register_action("Room", ActionMetadata(
            action_type="check_in", entity="Room", method_name="check_in",
            description="入住", allowed_roles={"manager"},
            params=[ActionParam(name="id", type=ParamType.INTEGER, required=True)],
        ))
        clean_registry.register_state_machine(StateMachine(
            entity="Room",
            states=["s1", "s2"],
            transitions=[StateTransition(from_state="s1", to_state="s2", trigger="t1")],
            initial_state="s1",
        ))

        schema = clean_registry.export_schema()
        json_str = json.dumps(schema, ensure_ascii=False)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["entity_types"]["Room"]["description"] == "酒店房间"

    def test_export_schema_related_entities(self, clean_registry):
        """导出包含相关实体的 schema"""
        clean_registry.register_entity(EntityMetadata(
            name="Room", description="", table_name="rooms",
            related_entities=["RoomType", "StayRecord"],
        ))

        schema = clean_registry.export_schema()
        assert schema["entity_types"]["Room"]["related_entities"] == ["RoomType", "StayRecord"]


class TestDescribeType:
    """describe_type() 测试"""

    def test_describe_existing_type(self, clean_registry):
        """描述已注册的实体"""
        clean_registry.register_entity(EntityMetadata(
            name="Room", description="酒店房间", table_name="rooms"
        ))
        clean_registry.register_action("Room", ActionMetadata(
            action_type="check_in", entity="Room", method_name="check_in", description="入住"
        ))

        result = clean_registry.describe_type("Room")
        assert result["description"] == "酒店房间"
        assert "check_in" in result["actions"]

    def test_describe_nonexistent_type(self, clean_registry):
        """描述不存在的实体返回空字典"""
        result = clean_registry.describe_type("NonExistent")
        assert result == {}

    def test_describe_type_includes_interfaces(self, clean_registry):
        """描述实体包含接口信息"""
        clean_registry.register_entity(EntityMetadata(
            name="Room", description="", table_name="rooms"
        ))
        clean_registry.register_interface_implementation("BookableResource", "Room")

        result = clean_registry.describe_type("Room")
        assert "BookableResource" in result["interfaces"]


class TestInterfaceRegistration:
    """接口注册功能测试"""

    def test_register_interface(self, clean_registry):
        """注册接口"""
        class TestInterface:
            pass

        clean_registry.register_interface(TestInterface)
        assert clean_registry.get_interface("TestInterface") is TestInterface

    def test_register_interface_implementation(self, clean_registry):
        """注册接口实现"""
        clean_registry.register_interface_implementation("Bookable", "Room")
        clean_registry.register_interface_implementation("Bookable", "MeetingRoom")

        impls = clean_registry.get_implementations("Bookable")
        assert "Room" in impls
        assert "MeetingRoom" in impls

    def test_duplicate_implementation_ignored(self, clean_registry):
        """重复注册同一实现不会重复添加"""
        clean_registry.register_interface_implementation("Bookable", "Room")
        clean_registry.register_interface_implementation("Bookable", "Room")

        impls = clean_registry.get_implementations("Bookable")
        assert len(impls) == 1

    def test_get_implementations_nonexistent(self, clean_registry):
        """获取不存在接口的实现返回空列表"""
        assert clean_registry.get_implementations("NonExistent") == []

    def test_get_interfaces(self, clean_registry):
        """获取所有注册的接口"""
        class I1:
            pass
        class I2:
            pass

        clean_registry.register_interface(I1)
        clean_registry.register_interface(I2)

        interfaces = clean_registry.get_interfaces()
        assert "I1" in interfaces
        assert "I2" in interfaces

    def test_clear_clears_interfaces(self, clean_registry):
        """清空注册表会清空接口数据"""
        class TestIface:
            pass

        clean_registry.register_interface(TestIface)
        clean_registry.register_interface_implementation("TestIface", "Room")

        clean_registry.clear()

        assert clean_registry.get_interface("TestIface") is None
        assert clean_registry.get_implementations("TestIface") == []
