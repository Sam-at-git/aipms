"""
tests/ai/test_prompt_builder.py

PromptBuilder 单元测试
"""
import pytest
from datetime import date, timedelta

from core.ai.prompt_builder import (
    PromptBuilder,
    PromptContext,
    build_system_prompt,
)

# 导入模型以触发 registry 注册
import app.models.ontology


class TestPromptContext:
    """PromptContext 测试"""

    def test_default_values(self):
        """测试默认值"""
        context = PromptContext()
        assert context.user_role == ""
        assert context.current_date == date.today()
        assert context.include_entities is True
        assert context.include_actions is True
        assert context.include_rules is True
        assert context.custom_variables == {}

    def test_with_values(self):
        """测试设置值"""
        test_date = date(2025, 2, 4)
        context = PromptContext(
            user_role="manager",
            current_date=test_date,
            include_entities=False,
            include_actions=False,
            include_rules=False,
            custom_variables={"key": "value"}
        )
        assert context.user_role == "manager"
        assert context.current_date == test_date
        assert context.include_entities is False
        assert context.include_actions is False
        assert context.include_rules is False
        assert context.custom_variables == {"key": "value"}


class TestPromptBuilder:
    """PromptBuilder 测试"""

    def test_build_system_prompt_default(self):
        """测试默认系统提示词构建"""
        builder = PromptBuilder()
        prompt = builder.build_system_prompt()

        # 检查包含关键部分
        assert "Ontology" in prompt or "AIPMS" in prompt
        assert "**当前日期:" in prompt
        assert "**明天:" in prompt
        assert "**后天:" in prompt

    def test_build_system_prompt_with_context(self):
        """测试带上下文的系统提示词构建"""
        context = PromptContext(
            user_role="manager",
            include_entities=False,
            include_actions=False,
            include_rules=False
        )
        builder = PromptBuilder()
        prompt = builder.build_system_prompt(context)

        assert "Ontology" in prompt or "AIPMS" in prompt

    def test_build_entity_descriptions(self):
        """测试实体描述构建"""
        builder = PromptBuilder()
        description = builder._build_entity_descriptions()

        # 应该包含实体标题
        assert "**本体实体:**" in description

    def test_build_action_descriptions(self):
        """测试操作描述构建"""
        builder = PromptBuilder()
        description = builder._build_action_descriptions()

        # 应该包含操作标题（可能是空列表或实际列表）
        assert "**支持的操作" in description or "**支持的操作类型" in description

    def test_build_date_context(self):
        """测试日期上下文构建"""
        builder = PromptBuilder()
        test_date = date(2025, 2, 4)
        context = builder._build_date_context(test_date)

        assert "2025年2月4日" in context
        assert "2025-02-05" in context  # 明天
        assert "2025-02-06" in context  # 后天

    def test_apply_custom_variables(self):
        """测试自定义变量替换"""
        builder = PromptBuilder()
        text = "Hello {name}, today is {day}"
        result = builder._apply_custom_variables(
            text,
            {"name": "Alice", "day": "Monday"}
        )
        assert result == "Hello Alice, today is Monday"

    def test_build_user_message_basic(self):
        """测试基本用户消息构建"""
        builder = PromptBuilder()
        message = builder.build_user_message("你好")

        assert "用户输入: 你好" in message

    def test_build_user_message_with_context(self):
        """测试带上下文的用户消息构建"""
        builder = PromptBuilder()
        context = {
            "room_summary": {"total": 100, "vacant_clean": 50, "occupied": 40},
            "room_types": [
                {"id": 1, "name": "标间", "price": 288}
            ]
        }
        message = builder.build_user_message("你好", additional_context=context)

        assert "**当前状态:**" in message
        assert "总房间: 100" in message

    def test_format_conversation_history(self):
        """测试对话历史格式化"""
        builder = PromptBuilder()
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！有什么可以帮您？"}
        ]
        formatted = builder.format_conversation_history(history, max_rounds=1)

        assert "**最近对话历史：**" in formatted
        assert "用户: 你好" in formatted
        assert "助手: 你好！" in formatted

    def test_format_empty_history(self):
        """测试空历史格式化"""
        builder = PromptBuilder()
        formatted = builder.format_conversation_history([])
        assert formatted == ""


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_build_system_prompt_function(self):
        """测试便捷函数"""
        prompt = build_system_prompt(
            user_role="manager",
            include_entities=True,
            include_actions=True,
            include_rules=False
        )

        assert "Ontology" in prompt or "AIPMS" in prompt

    def test_build_system_prompt_with_date(self):
        """测试带日期的便捷函数"""
        test_date = date(2025, 2, 4)
        prompt = build_system_prompt(current_date=test_date)

        assert "2025年2月4日" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
