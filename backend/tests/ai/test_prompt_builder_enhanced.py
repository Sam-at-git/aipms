"""
tests/ai/test_prompt_builder_enhanced.py

增强版 PromptBuilder 单元测试 (SPEC-51, 52)
"""
import pytest
from datetime import date

from core.ai.prompt_builder import (
    PromptBuilder,
    PromptContext,
    build_system_prompt,
)


class TestPromptContextEnhanced:
    """增强版 PromptContext 测试"""

    def test_with_user_id(self):
        """测试带用户 ID 的上下文"""
        context = PromptContext(user_role="manager", user_id=1)
        assert context.user_id == 1
        assert context.user_role == "manager"

    def test_with_state_machines_flag(self):
        """测试状态机标志"""
        context = PromptContext(include_state_machines=True)
        assert context.include_state_machines is True

    def test_with_permissions_flag(self):
        """测试权限标志"""
        context = PromptContext(include_permissions=True)
        assert context.include_permissions is True

    def test_default_field_factory(self):
        """测试字段默认值工厂"""
        context = PromptContext()
        assert isinstance(context.custom_variables, dict)
        assert context.custom_variables == {}


class TestEnhancedPromptBuilder:
    """增强版 PromptBuilder 测试 (SPEC-51, 52)"""

    def test_build_with_role_context(self):
        """测试构建带角色上下文的提示词"""
        builder = PromptBuilder()
        context = PromptContext(user_role="manager", user_id=1)
        prompt = builder.build_system_prompt(context)

        assert "**当前用户角色:** manager" in prompt
        assert "**用户ID:** 1" in prompt

    def test_build_with_state_machines(self):
        """测试构建包含状态机的提示词"""
        builder = PromptBuilder()
        context = PromptContext(include_state_machines=True)
        prompt = builder.build_system_prompt(context)

        # 即使没有注册状态机，也应该有标题
        assert "**状态机定义:**" in prompt or "暂无" in prompt

    def test_build_with_permissions_for_manager(self):
        """测试为管理员构建包含权限的提示词"""
        builder = PromptBuilder()
        context = PromptContext(user_role="manager", include_permissions=True)
        prompt = builder.build_system_prompt(context)

        # 权限矩阵可能为空，但应该包含标题
        # 检查是否包含权限矩阵相关内容
        assert "权限矩阵" in prompt

    def test_build_without_permissions_for_receptionist(self):
        """测试为前台构建不包含权限的提示词"""
        builder = PromptBuilder()
        context = PromptContext(user_role="receptionist", include_permissions=True)
        prompt = builder.build_system_prompt(context)

        # 非管理员不显示权限矩阵
        assert "**权限矩阵**" not in prompt

    def test_get_dynamic_context(self):
        """测试获取动态上下文 (SPEC-51)"""
        builder = PromptBuilder()
        context = builder.get_dynamic_context("manager")

        assert "user_role" in context
        assert context["user_role"] == "manager"
        assert "timestamp" in context
        assert "registered_entities" in context
        assert "registered_actions" in context
        assert "registered_rules" in context

    def test_get_dynamic_context_with_db(self):
        """测试获取带数据库的动态上下文"""
        from sqlalchemy.orm import Session

        builder = PromptBuilder()
        # 不传数据库会话
        context = builder.get_dynamic_context("manager", db_session=None)

        assert "room_stats" not in context

    def test_enhanced_build_system_prompt(self):
        """测试增强的系统提示词构建 (SPEC-52)"""
        prompt = build_system_prompt(
            user_role="manager",
            include_entities=True,
            include_actions=True,
            include_rules=True
        )

        assert "AIPMS" in prompt
        assert "**当前用户角色:** manager" in prompt

    def test_prompt_with_all_features(self):
        """测试启用所有功能的提示词"""
        builder = PromptBuilder()
        context = PromptContext(
            user_role="manager",
            user_id=1,
            include_entities=True,
            include_actions=True,
            include_rules=True,
            include_state_machines=True,
            include_permissions=True,
            custom_variables={"hotel_name": "AIPMS 酒店"}
        )
        prompt = builder.build_system_prompt(context)

        assert "AIPMS" in prompt
        assert "manager" in prompt
        assert "AIPMS 酒店" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
