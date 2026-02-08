"""
测试 core.ai.prompt_builder PromptBuilder 增强功能 (SPEC-02.5.5)
"""
import pytest
from datetime import date
from core.ai.prompt_builder import PromptBuilder, PromptContext, build_system_prompt
from core.ontology.registry import OntologyRegistry
from core.ontology.metadata import (
    EntityMetadata,
    ActionMetadata,
    ParamType,
    ActionParam,
    StateMachine,
    StateTransition,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """每个测试前清空注册表"""
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


@pytest.fixture
def populated_registry(clean_registry):
    """包含数据的注册表"""
    clean_registry.register_entity(EntityMetadata(
        name="Room",
        description="酒店房间",
        table_name="rooms",
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
    clean_registry.register_action("Room", ActionMetadata(
        action_type="check_out",
        entity="Room",
        method_name="check_out",
        description="办理退房",
        requires_confirmation=True,
    ))
    clean_registry.register_state_machine(StateMachine(
        entity="Room",
        states=["vacant_clean", "occupied", "vacant_dirty"],
        transitions=[
            StateTransition(from_state="vacant_clean", to_state="occupied", trigger="check_in"),
            StateTransition(from_state="occupied", to_state="vacant_dirty", trigger="check_out"),
        ],
        initial_state="vacant_clean",
    ))

    # 注册接口
    class MockBookable:
        """可预订资源"""
        required_properties = {"status": ParamType.STRING}
        required_actions = ["check_in", "check_out"]

    clean_registry.register_interface(MockBookable)
    clean_registry.register_interface_implementation("MockBookable", "Room")

    return clean_registry


class TestPromptBuilderBasic:
    """PromptBuilder 基本功能测试"""

    def test_build_system_prompt_empty_registry(self, clean_registry):
        """空注册表也能构建提示词"""
        builder = PromptBuilder(clean_registry)
        prompt = builder.build_system_prompt()
        assert len(prompt) > 0
        assert "AIPMS" in prompt

    def test_build_system_prompt_with_entities(self, populated_registry):
        """包含实体信息的提示词"""
        builder = PromptBuilder(populated_registry)
        prompt = builder.build_system_prompt()
        assert "Room" in prompt

    def test_build_system_prompt_with_context(self, populated_registry):
        """使用上下文构建提示词"""
        builder = PromptBuilder(populated_registry)
        context = PromptContext(
            user_role="manager",
            current_date=date(2026, 2, 5),
        )
        prompt = builder.build_system_prompt(context)
        assert "manager" in prompt
        assert "2026" in prompt

    def test_build_system_prompt_with_date(self, clean_registry):
        """日期上下文正确注入"""
        builder = PromptBuilder(clean_registry)
        context = PromptContext(current_date=date(2026, 1, 15))
        prompt = builder.build_system_prompt(context)
        assert "2026年1月15日" in prompt
        assert "2026-01-16" in prompt  # 明天
        assert "2026-01-17" in prompt  # 后天


class TestBuildEntityDescription:
    """build_entity_description() 测试"""

    def test_entity_not_found(self, clean_registry):
        """实体不存在时返回提示信息"""
        builder = PromptBuilder(clean_registry)
        desc = builder.build_entity_description("NonExistent")
        assert "NonExistent" in desc
        assert "不存在" in desc

    def test_entity_with_actions(self, populated_registry):
        """实体描述包含动作列表"""
        builder = PromptBuilder(populated_registry)
        desc = builder.build_entity_description("Room")
        assert "Room" in desc or "酒店房间" in desc
        assert "check_in" in desc
        assert "check_out" in desc

    def test_entity_with_interfaces(self, populated_registry):
        """实体描述包含接口信息"""
        builder = PromptBuilder(populated_registry)
        desc = builder.build_entity_description("Room")
        assert "MockBookable" in desc


class TestBuildInterfaceDescription:
    """build_interface_description() 测试"""

    def test_interface_not_found(self, clean_registry):
        """接口不存在时返回提示信息"""
        builder = PromptBuilder(clean_registry)
        desc = builder.build_interface_description("NonExistent")
        assert "NonExistent" in desc
        assert "不存在" in desc

    def test_interface_with_implementations(self, populated_registry):
        """接口描述包含实现列表"""
        builder = PromptBuilder(populated_registry)
        desc = builder.build_interface_description("MockBookable")
        assert "Room" in desc

    def test_interface_with_required_actions(self, populated_registry):
        """接口描述包含必需动作"""
        builder = PromptBuilder(populated_registry)
        desc = builder.build_interface_description("MockBookable")
        assert "check_in" in desc
        assert "check_out" in desc


class TestSchemaCache:
    """Schema 缓存测试"""

    def test_cache_works(self, populated_registry):
        """schema 缓存正常工作"""
        builder = PromptBuilder(populated_registry)

        # 第一次调用会构建缓存
        desc1 = builder.build_entity_description("Room")
        # 第二次应该使用缓存
        desc2 = builder.build_entity_description("Room")
        assert desc1 == desc2

    def test_invalidate_cache(self, populated_registry):
        """invalidate_cache 清除缓存"""
        builder = PromptBuilder(populated_registry)

        # 构建缓存
        builder.build_entity_description("Room")
        assert builder._schema_cache is not None

        # 清除缓存
        builder.invalidate_cache()
        assert builder._schema_cache is None


class TestConvenienceFunction:
    """便捷函数测试"""

    def test_build_system_prompt_function(self, clean_registry):
        """build_system_prompt() 便捷函数工作正常"""
        prompt = build_system_prompt(user_role="manager")
        assert len(prompt) > 0
        assert "manager" in prompt

    def test_build_system_prompt_with_date(self, clean_registry):
        """便捷函数支持日期参数"""
        prompt = build_system_prompt(current_date=date(2026, 3, 1))
        assert "2026年3月1日" in prompt


class TestPromptBuilderPerformance:
    """性能测试"""

    def test_build_system_prompt_performance(self, populated_registry):
        """构建提示词在 200ms 内完成（含首次初始化）"""
        import time
        builder = PromptBuilder(populated_registry)

        # 热身一次
        builder.build_system_prompt()

        start = time.time()
        builder.build_system_prompt()
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 200, f"build_system_prompt() took {elapsed_ms:.1f}ms, expected < 200ms"

    def test_entity_description_performance(self, populated_registry):
        """实体描述在 10ms 内完成"""
        import time
        builder = PromptBuilder(populated_registry)

        start = time.time()
        builder.build_entity_description("Room")
        elapsed_ms = (time.time() - start) * 1000

        assert elapsed_ms < 10, f"build_entity_description() took {elapsed_ms:.1f}ms, expected < 10ms"
