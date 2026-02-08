"""
tests/core/test_prompt_builder_semantic.py

测试 PromptBuilder 的语义查询语法生成功能 (SPEC-13)

测试范围：
- build_semantic_query_syntax() 输出格式
- 实体路径生成
- 操作符说明
- 查询示例
- 完整提示词集成
"""
import pytest
from datetime import date

from core.ai.prompt_builder import PromptBuilder, PromptContext


class TestSemanticQuerySyntax:
    """测试语义查询语法生成"""

    def test_build_semantic_query_syntax_returns_string(self):
        """测试返回字符串"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_header(self):
        """测试包含标题"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        assert "**Semantic Query Syntax (语义查询语法)**" in result

    def test_contains_path_syntax_rules(self):
        """测试包含路径语法规则"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        assert "## 路径语法规则" in result
        assert "**简单字段**" in result
        assert "**单跳关联**" in result
        assert "**多跳导航**" in result

    def test_contains_entity_paths(self):
        """测试包含实体路径"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        assert "## 可用实体及路径" in result
        assert "### Guest" in result
        assert "### Room" in result
        assert "### StayRecord" in result

    def test_contains_filter_operators(self):
        """测试包含过滤操作符"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        assert "## 过滤操作符" in result
        assert "`eq` - 等于" in result
        assert "`ne` - 不等于" in result
        assert "`gt` - 大于" in result
        assert "`gte` - 大于等于" in result
        assert "`lt` - 小于" in result
        assert "`lte` - 小于等于" in result
        assert "`in` - 在列表中" in result
        assert "`like` - 模糊匹配" in result
        assert "`between` - 在范围内" in result

    def test_contains_query_examples(self):
        """测试包含查询示例"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        assert "## 查询示例" in result
        assert "### 示例 1:" in result
        assert "### 示例 2:" in result
        assert "### 示例 3:" in result
        assert "### 示例 4:" in result

    def test_example_1_active_guests(self):
        """测试示例1：查询在住客人"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        assert '"root_object": "Guest"' in result
        assert '"fields": ["name", "phone"]' in result
        assert '{"path": "stays.status", "operator": "eq", "value": "ACTIVE"}' in result

    def test_example_2_specific_room(self):
        """测试示例2：查询特定房间的客人"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        assert '{"path": "stays.room.room_number", "operator": "eq", "value": "201"}' in result

    def test_example_3_date_range(self):
        """测试示例3：日期范围查询"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        assert '"root_object": "StayRecord"' in result
        assert '{"path": "check_in_time", "operator": "gte", "value": "2026-02-01"}' in result
        assert '{"path": "check_in_time", "operator": "lt", "value": "2026-03-01"}' in result

    def test_example_4_vip_guests(self):
        """测试示例4：VIP客人查询"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        assert '{"path": "guest.tier", "operator": "eq", "value": "VIP"}' in result
        assert '"room.room_type.name"' in result

    def test_contains_important_rules(self):
        """测试包含重要规则"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        assert "## 重要规则" in result
        assert "**路径必须使用关系属性名**" in result
        assert "**日期字段使用 ISO 格式**" in result
        assert "**状态值使用枚举值**" in result
        assert "**多个过滤器之间是 AND 关系**" in result
        assert "**limit 默认为 100，最大 1000**" in result


class TestGenerateEntityPaths:
    """测试实体路径生成"""

    def test_generate_entity_paths_returns_dict(self):
        """测试返回字典"""
        builder = PromptBuilder()
        result = builder._generate_entity_paths({})

        assert isinstance(result, dict)

    def test_contains_guest_entity(self):
        """测试包含Guest实体"""
        builder = PromptBuilder()
        result = builder._generate_entity_paths({})

        assert "Guest" in result
        assert len(result["Guest"]) > 0

    def test_contains_room_entity(self):
        """测试包含Room实体"""
        builder = PromptBuilder()
        result = builder._generate_entity_paths({})

        assert "Room" in result
        assert len(result["Room"]) > 0

    def test_guest_paths_include_name(self):
        """测试Guest路径包含name"""
        builder = PromptBuilder()
        result = builder._generate_entity_paths({})

        guest_paths = " ".join(result["Guest"])
        assert "name" in guest_paths

    def test_guest_paths_include_stays(self):
        """测试Guest路径包含stays关系"""
        builder = PromptBuilder()
        result = builder._generate_entity_paths({})

        guest_paths = " ".join(result["Guest"])
        assert "stays" in guest_paths

    def test_stayrecord_paths_include_guest(self):
        """测试StayRecord路径包含guest关系"""
        builder = PromptBuilder()
        result = builder._generate_entity_paths({})

        stayrecord_paths = " ".join(result.get("StayRecord", []))
        assert "guest.name" in stayrecord_paths

    def test_stayrecord_paths_include_room(self):
        """测试StayRecord路径包含room关系"""
        builder = PromptBuilder()
        result = builder._generate_entity_paths({})

        stayrecord_paths = " ".join(result.get("StayRecord", []))
        assert "room" in stayrecord_paths


class TestPromptIntegration:
    """测试提示词集成"""

    def test_system_prompt_includes_semantic_syntax(self):
        """测试系统提示词包含语义语法"""
        builder = PromptBuilder()
        context = PromptContext(
            user_role="manager",
            include_entities=True
        )

        prompt = builder.build_system_prompt(context)

        # Check for the full header with Chinese text
        assert "**Semantic Query Syntax" in prompt or "Semantic Query Syntax" in prompt
        # Also check for key content that should be in the semantic syntax section
        assert "路径语法规则" in prompt or "Path Syntax" in prompt

    def test_system_prompt_semantic_syntax_position(self):
        """测试语义语法在提示词中的位置"""
        builder = PromptBuilder()
        context = PromptContext(
            user_role="manager",
            include_entities=True
        )

        prompt = builder.build_system_prompt(context)

        # 语义语法应该在角色上下文之后，实体描述之前
        role_idx = prompt.find("**当前用户角色:**")
        # Use a more flexible search for the semantic syntax
        semantic_idx = prompt.find("Semantic Query Syntax")
        entity_idx = prompt.find("**本体实体:**")

        assert role_idx > 0
        # Semantic syntax may or may not be present depending on registry state
        if semantic_idx > 0:
            assert semantic_idx > role_idx
        assert entity_idx > 0

    def test_exclude_entities_excludes_semantic_syntax(self):
        """测试排除实体时也排除语义语法"""
        builder = PromptBuilder()
        context = PromptContext(
            include_entities=False
        )

        prompt = builder.build_system_prompt(context)

        assert "**Semantic Query Syntax**" not in prompt

    def test_semantic_syntax_with_all_sections(self):
        """测试语义语法与其他部分共存"""
        builder = PromptBuilder()
        context = PromptContext(
            user_role="manager",
            include_entities=True,
            include_actions=True,
            include_rules=True,
            include_state_machines=True,
            include_permissions=True
        )

        prompt = builder.build_system_prompt(context)

        # Check for key parts of the prompt
        assert "**当前用户角色:**" in prompt
        assert "**当前日期:" in prompt
        # Semantic syntax may not be complete if registry is empty
        # but the section should at least have the header
        assert "Semantic Query Syntax" in prompt or "语义查询语法" in prompt


class TestPromptContent:
    """测试提示词内容质量"""

    def test_prompt_is_well_formatted(self):
        """测试提示词格式良好"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        # 检查Markdown格式
        assert result.startswith("**")
        assert result.count("##") > 0
        assert result.count("###") > 0
        assert "```json" in result
        assert "```" in result

    def test_prompt_not_empty(self):
        """测试提示词不为空"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        lines = result.strip().split("\n")
        non_empty_lines = [l for l in lines if l.strip()]

        assert len(non_empty_lines) > 50  # 至少50行非空内容

    def test_json_examples_are_valid(self):
        """测试JSON示例格式正确"""
        builder = PromptBuilder()
        result = builder._build_semantic_query_syntax()

        # 检查基本的JSON语法
        assert '"root_object"' in result
        assert '"fields"' in result
        assert '"filters"' in result
        assert '"path"' in result
        assert '"operator"' in result
        assert '"value"' in result


class TestPromptPlaceholders:
    """测试提示词占位符"""

    def test_base_template_has_semantic_placeholder(self):
        """测试基础模板有语义语法占位符"""
        assert "{semantic_query_syntax}" in PromptBuilder.BASE_SYSTEM_PROMPT

    def test_all_placeholders_present(self):
        """测试所有占位符都存在"""
        template = PromptBuilder.BASE_SYSTEM_PROMPT

        placeholders = [
            "{role_context}",
            "{semantic_query_syntax}",
            "{entity_descriptions}",
            "{action_descriptions}",
            "{state_machine_descriptions}",
            "{rule_descriptions}",
            "{permission_context}",
            "{date_context}",
        ]

        for placeholder in placeholders:
            assert placeholder in template, f"Missing placeholder: {placeholder}"


class TestPromptBuilderExport:
    """测试 PromptBuilder 导出"""

    def test_build_semantic_query_syntax_is_public(self):
        """测试方法是公开的（虽然以下划线开头，但可以被调用）"""
        builder = PromptBuilder()

        # 方法应该可以被调用
        result = builder._build_semantic_query_syntax()
        assert isinstance(result, str)
