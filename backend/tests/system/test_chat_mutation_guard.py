"""
ChatMutationGuard 测试
"""
import pytest
from app.system.guards.chat_mutation_guard import ChatMutationGuard, GuardResult


class TestChatMutationGuard:
    """ChatMutationGuard 单元测试"""

    @pytest.fixture
    def guard(self):
        return ChatMutationGuard()

    def test_non_chat_action_allowed(self, guard):
        """非 Chat 发起的操作不拦截"""
        result = guard.check(
            action_name="create_role",
            entity="SysRole",
            category="mutation",
            params={},
            context={"via_chat": False},
        )
        assert result is None

    def test_query_action_allowed(self, guard):
        """查询操作不拦截"""
        result = guard.check(
            action_name="query_system",
            entity="SysRole",
            category="query",
            params={},
            context={"via_chat": True},
        )
        assert result is None

    def test_role_mutation_blocked(self, guard):
        """角色修改通过 Chat 被拦截"""
        result = guard.check(
            action_name="create_role",
            entity="SysRole",
            category="mutation",
            params={},
            context={"via_chat": True},
        )
        assert result is not None
        assert result.blocked is True
        assert "管理界面" in result.message

    def test_permission_mutation_blocked(self, guard):
        """权限修改通过 Chat 被拦截"""
        result = guard.check(
            action_name="assign_permission",
            entity="SysPermission",
            category="mutation",
            params={},
            context={"via_chat": True},
        )
        assert result is not None
        assert result.blocked is True

    def test_menu_mutation_blocked(self, guard):
        """菜单修改通过 Chat 被拦截"""
        result = guard.check(
            action_name="update_menu",
            entity="SysMenu",
            category="mutation",
            params={},
            context={"via_chat": True},
        )
        assert result is not None
        assert result.blocked is True

    def test_role_permission_mutation_blocked(self, guard):
        """角色权限绑定通过 Chat 被拦截"""
        result = guard.check(
            action_name="assign_role_permission",
            entity="RolePermission",
            category="mutation",
            params={},
            context={"via_chat": True},
        )
        assert result is not None
        assert result.blocked is True

    def test_sensitive_config_group_blocked(self, guard):
        """敏感配置分组修改通过 Chat 被拦截"""
        result = guard.check(
            action_name="update_config",
            entity="SysConfig",
            category="mutation",
            params={"group_code": "security"},
            context={"via_chat": True},
        )
        assert result is not None
        assert result.blocked is True
        assert "security" in result.message

    def test_llm_config_group_blocked(self, guard):
        """LLM 配置分组修改通过 Chat 被拦截"""
        result = guard.check(
            action_name="update_config",
            entity="SysConfig",
            category="mutation",
            params={"group_code": "llm"},
            context={"via_chat": True},
        )
        assert result is not None
        assert result.blocked is True

    def test_non_sensitive_config_allowed(self, guard):
        """非敏感配置分组修改通过 Chat 允许"""
        result = guard.check(
            action_name="update_config",
            entity="SysConfig",
            category="mutation",
            params={"group_code": "business"},
            context={"via_chat": True},
        )
        assert result is None

    def test_business_entity_mutation_allowed(self, guard):
        """业务实体修改通过 Chat 允许（由其他机制控制）"""
        result = guard.check(
            action_name="checkin",
            entity="Room",
            category="mutation",
            params={},
            context={"via_chat": True},
        )
        assert result is None

    def test_dict_item_mutation_allowed(self, guard):
        """字典项修改通过 Chat 允许（低风险）"""
        result = guard.check(
            action_name="create_dict_item",
            entity="SysDictItem",
            category="mutation",
            params={},
            context={"via_chat": True},
        )
        assert result is None

    def test_no_context_treated_as_non_chat(self, guard):
        """无 via_chat 标记视为非 Chat"""
        result = guard.check(
            action_name="create_role",
            entity="SysRole",
            category="mutation",
            params={},
            context={},
        )
        assert result is None
