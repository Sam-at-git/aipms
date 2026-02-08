"""
本体 AI 集成测试 (SPEC-02.5.6)

验证:
1. Schema 导出 JSON 可序列化
2. PromptBuilder 生成有效提示词
3. 接口系统与注册中心集成
4. 实体描述包含完整信息
5. 性能基准
"""
import json
import time
import pytest

from core.ontology.registry import OntologyRegistry, registry
from core.ontology.metadata import (
    EntityMetadata,
    ActionMetadata,
    ParamType,
    ActionParam,
    StateMachine,
    StateTransition,
    PropertyMetadata,
)
from core.ontology.interface import OntologyInterface, implements
from core.ai.prompt_builder import PromptBuilder
from core.domain.interfaces import BookableResource, Maintainable, Billable, Trackable


@pytest.fixture(autouse=True)
def clean_registry():
    """每个测试前清空并重建注册表"""
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


@pytest.fixture
def full_registry(clean_registry):
    """构建完整的测试注册表"""
    # 注册 Room 实体
    clean_registry.register_entity(EntityMetadata(
        name="Room",
        description="酒店物理房间，数字孪生核心实体",
        table_name="rooms",
        is_aggregate_root=False,
        related_entities=["RoomType", "StayRecord", "Task"],
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
            ActionParam(name="expected_check_out", type=ParamType.STRING, required=False, description="预计退房日期"),
        ],
    ))
    clean_registry.register_action("Room", ActionMetadata(
        action_type="check_out",
        entity="Room",
        method_name="check_out",
        description="办理退房",
        requires_confirmation=True,
        allowed_roles={"manager", "receptionist"},
        params=[
            ActionParam(name="stay_record_id", type=ParamType.INTEGER, required=True, description="住宿记录ID"),
        ],
    ))
    clean_registry.register_action("Room", ActionMetadata(
        action_type="mark_clean",
        entity="Room",
        method_name="mark_clean",
        description="标记为已清洁",
        requires_confirmation=False,
        allowed_roles={"manager", "cleaner"},
    ))

    # 注册 Guest 实体
    clean_registry.register_entity(EntityMetadata(
        name="Guest",
        description="客人信息管理",
        table_name="guests",
    ))

    # 注册 Reservation 实体
    clean_registry.register_entity(EntityMetadata(
        name="Reservation",
        description="预订管理",
        table_name="reservations",
        related_entities=["Guest", "Room"],
    ))
    clean_registry.register_action("Reservation", ActionMetadata(
        action_type="create_reservation",
        entity="Reservation",
        method_name="create",
        description="创建预订",
        requires_confirmation=True,
        allowed_roles={"manager", "receptionist"},
        params=[
            ActionParam(name="guest_name", type=ParamType.STRING, required=True),
            ActionParam(name="room_type_id", type=ParamType.INTEGER, required=True),
            ActionParam(name="check_in_date", type=ParamType.DATE, required=True),
            ActionParam(name="check_out_date", type=ParamType.DATE, required=True),
        ],
    ))

    # 注册状态机
    clean_registry.register_state_machine(StateMachine(
        entity="Room",
        states=["vacant_clean", "occupied", "vacant_dirty", "out_of_order"],
        transitions=[
            StateTransition(from_state="vacant_clean", to_state="occupied", trigger="check_in"),
            StateTransition(from_state="occupied", to_state="vacant_dirty", trigger="check_out"),
            StateTransition(from_state="vacant_dirty", to_state="vacant_clean", trigger="mark_clean"),
        ],
        initial_state="vacant_clean",
    ))

    # 注册接口
    clean_registry.register_interface(BookableResource)
    clean_registry.register_interface_implementation("BookableResource", "Room")
    clean_registry.register_interface(Maintainable)
    clean_registry.register_interface_implementation("Maintainable", "Room")

    return clean_registry


class TestSchemaExportIntegration:
    """Schema 导出集成测试"""

    def test_schema_export_is_json_serializable(self, full_registry):
        """验证导出的 schema 可以 JSON 序列化"""
        schema = full_registry.export_schema()

        json_str = json.dumps(schema, ensure_ascii=False)
        assert len(json_str) > 0

        parsed = json.loads(json_str)
        assert parsed == schema

    def test_schema_contains_all_entities(self, full_registry):
        """验证 schema 包含所有注册的实体"""
        schema = full_registry.export_schema()

        assert "Room" in schema["entity_types"]
        assert "Guest" in schema["entity_types"]
        assert "Reservation" in schema["entity_types"]

    def test_schema_contains_actions(self, full_registry):
        """验证 schema 包含动作信息"""
        schema = full_registry.export_schema()

        room = schema["entity_types"]["Room"]
        assert "check_in" in room["actions"]
        assert "check_out" in room["actions"]
        assert "mark_clean" in room["actions"]

    def test_schema_contains_interfaces(self, full_registry):
        """验证 schema 包含接口信息"""
        schema = full_registry.export_schema()

        assert "BookableResource" in schema["interfaces"]
        assert "Room" in schema["interfaces"]["BookableResource"]["implementations"]

    def test_schema_contains_state_machines(self, full_registry):
        """验证 schema 包含状态机信息"""
        schema = full_registry.export_schema()

        assert "Room" in schema["state_machines"]
        sm = schema["state_machines"]["Room"]
        assert sm["initial_state"] == "vacant_clean"
        assert len(sm["transitions"]) == 3

    def test_schema_entity_has_related_entities(self, full_registry):
        """验证实体包含相关实体信息"""
        schema = full_registry.export_schema()

        room = schema["entity_types"]["Room"]
        assert "RoomType" in room["related_entities"]
        assert "StayRecord" in room["related_entities"]


class TestPromptBuilderIntegration:
    """PromptBuilder 集成测试"""

    def test_prompt_builder_generates_valid_prompt(self, full_registry):
        """验证 PromptBuilder 生成有效的提示词"""
        builder = PromptBuilder(full_registry)
        prompt = builder.build_system_prompt()

        assert len(prompt) > 0
        assert "AIPMS" in prompt

    def test_prompt_contains_entity_info(self, full_registry):
        """验证提示词包含实体信息"""
        builder = PromptBuilder(full_registry)
        prompt = builder.build_system_prompt()

        assert "Room" in prompt
        assert "Guest" in prompt

    def test_prompt_contains_action_info(self, full_registry):
        """验证提示词包含操作信息"""
        builder = PromptBuilder(full_registry)
        prompt = builder.build_system_prompt()

        assert "check_in" in prompt
        assert "check_out" in prompt

    def test_entity_description_contains_actions(self, full_registry):
        """验证实体描述包含可用操作"""
        builder = PromptBuilder(full_registry)
        description = builder.build_entity_description("Room")

        assert "check_in" in description
        assert "check_out" in description

    def test_entity_description_contains_interfaces(self, full_registry):
        """验证实体描述包含接口信息"""
        builder = PromptBuilder(full_registry)
        description = builder.build_entity_description("Room")

        assert "BookableResource" in description

    def test_interface_description_shows_implementations(self, full_registry):
        """验证接口描述显示实现类"""
        builder = PromptBuilder(full_registry)
        description = builder.build_interface_description("BookableResource")

        assert "Room" in description

    def test_nonexistent_entity_description(self, full_registry):
        """验证不存在的实体描述"""
        builder = PromptBuilder(full_registry)
        description = builder.build_entity_description("NonExistent")

        assert "不存在" in description

    def test_nonexistent_interface_description(self, full_registry):
        """验证不存在的接口描述"""
        builder = PromptBuilder(full_registry)
        description = builder.build_interface_description("NonExistent")

        assert "不存在" in description


class TestInterfaceIntegration:
    """接口系统集成测试"""

    def test_interface_validates_correctly(self):
        """接口验证机制正确工作"""
        class TestInterface(OntologyInterface):
            required_properties = {"name": ParamType.STRING}
            required_actions = ["do_work"]

        class Good:
            __ontology_properties__ = {"name": "string"}
            __ontology_actions__ = ["do_work"]

        class Bad:
            pass

        assert TestInterface.validate_implementation(Good) == []
        errors = TestInterface.validate_implementation(Bad)
        assert len(errors) == 2

    def test_implements_registers_correctly(self, clean_registry):
        """@implements 装饰器正确注册"""
        class TestIface(OntologyInterface):
            """测试接口"""
            required_properties = {"status": ParamType.STRING}

        @implements(TestIface)
        class TestEntity:
            @property
            def status(self):
                return "active"

        # 验证注册
        assert "TestEntity" in clean_registry.get_implementations("TestIface")
        assert clean_registry.get_interface("TestIface") is TestIface

        # 验证 schema 导出
        schema = clean_registry.export_schema()
        assert "TestIface" in schema["interfaces"]
        assert "TestEntity" in schema["interfaces"]["TestIface"]["implementations"]

    def test_business_interfaces_defined_correctly(self):
        """业务接口定义正确"""
        # BookableResource
        assert "status" in BookableResource.required_properties
        assert "check_in" in BookableResource.required_actions

        # Maintainable
        assert "status" in Maintainable.required_properties
        assert "mark_maintenance" in Maintainable.required_actions

        # Billable
        assert "total_amount" in Billable.required_properties
        assert "add_payment" in Billable.required_actions

        # Trackable
        assert "status" in Trackable.required_properties
        assert "created_at" in Trackable.required_properties


class TestPerformanceBenchmarks:
    """性能基准测试"""

    def test_export_schema_performance(self, full_registry):
        """验证 schema 导出性能 < 100ms"""
        # 热身
        full_registry.export_schema()

        start = time.time()
        schema = full_registry.export_schema()
        elapsed = (time.time() - start) * 1000

        assert elapsed < 100, f"export_schema() took {elapsed:.1f}ms, expected < 100ms"
        assert len(schema["entity_types"]) > 0

    def test_describe_type_performance(self, full_registry):
        """验证 describe_type 性能 < 10ms"""
        # 热身
        full_registry.describe_type("Room")

        start = time.time()
        result = full_registry.describe_type("Room")
        elapsed = (time.time() - start) * 1000

        assert elapsed < 10, f"describe_type() took {elapsed:.1f}ms, expected < 10ms"
        assert result.get("description") == "酒店物理房间，数字孪生核心实体"

    def test_prompt_build_performance(self, full_registry):
        """验证提示词构建性能 < 200ms"""
        builder = PromptBuilder(full_registry)

        # 热身
        builder.build_system_prompt()

        start = time.time()
        prompt = builder.build_system_prompt()
        elapsed = (time.time() - start) * 1000

        assert elapsed < 200, f"build_system_prompt() took {elapsed:.1f}ms, expected < 200ms"
        assert len(prompt) > 0


class TestEndToEnd:
    """端到端测试"""

    def test_full_workflow(self, clean_registry):
        """完整工作流：注册 → 导出 → 构建提示词"""
        # 1. 注册实体和动作
        clean_registry.register_entity(EntityMetadata(
            name="Task",
            description="任务管理",
            table_name="tasks",
        ))
        clean_registry.register_action("Task", ActionMetadata(
            action_type="create_task",
            entity="Task",
            method_name="create",
            description="创建任务",
            requires_confirmation=False,
        ))

        # 2. 注册接口和实现
        class TaskTracking(OntologyInterface):
            """任务追踪"""
            required_properties = {}
            required_actions = []

        clean_registry.register_interface(TaskTracking)
        clean_registry.register_interface_implementation("TaskTracking", "Task")

        # 3. 导出 schema
        schema = clean_registry.export_schema()
        assert "Task" in schema["entity_types"]
        assert "TaskTracking" in schema["interfaces"]

        # 4. JSON 序列化
        json_str = json.dumps(schema, ensure_ascii=False)
        assert len(json_str) > 0

        # 5. 构建提示词
        builder = PromptBuilder(clean_registry)
        prompt = builder.build_system_prompt()
        assert "Task" in prompt

        # 6. 实体描述
        desc = builder.build_entity_description("Task")
        assert "任务管理" in desc
        assert "create_task" in desc

        # 7. 接口描述
        iface_desc = builder.build_interface_description("TaskTracking")
        assert "Task" in iface_desc
