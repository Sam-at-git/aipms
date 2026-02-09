"""
Tests for SPEC-06: Prompt builder domain-agnostic cleanup
"""
import pytest
from core.ai.prompt_builder import PromptBuilder, PromptContext
from core.ontology.registry import OntologyRegistry


@pytest.fixture
def clean_registry():
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


class TestBasePromptIsDomainAgnostic:
    """Verify BASE_SYSTEM_PROMPT has no hotel-specific content"""

    def test_no_hotel_reference_in_base_prompt(self):
        assert "AIPMS" not in PromptBuilder.BASE_SYSTEM_PROMPT
        assert "酒店管理" not in PromptBuilder.BASE_SYSTEM_PROMPT

    def test_base_prompt_is_generic(self):
        assert "Ontology 驱动" in PromptBuilder.BASE_SYSTEM_PROMPT

    def test_base_prompt_has_domain_prompt_placeholder(self):
        assert "{domain_prompt}" in PromptBuilder.BASE_SYSTEM_PROMPT


class TestDomainPromptInjection:
    """Test that domain_prompt is injected from PromptContext"""

    def test_domain_prompt_field_exists(self):
        ctx = PromptContext()
        assert hasattr(ctx, "domain_prompt")
        assert ctx.domain_prompt == ""

    def test_domain_prompt_injection(self, clean_registry):
        builder = PromptBuilder(ontology_registry=clean_registry)
        ctx = PromptContext(
            domain_prompt="这是一个酒店管理系统的智能助手。优先使用 room_number 而非 room_id。",
            include_entities=False,
            include_actions=False,
            include_rules=False,
            include_state_machines=False,
        )
        prompt = builder.build_system_prompt(context=ctx)
        assert "酒店管理系统" in prompt
        assert "room_number" in prompt

    def test_empty_domain_prompt(self, clean_registry):
        builder = PromptBuilder(ontology_registry=clean_registry)
        ctx = PromptContext(
            include_entities=False,
            include_actions=False,
            include_rules=False,
            include_state_machines=False,
        )
        prompt = builder.build_system_prompt(context=ctx)
        assert "Ontology 驱动" in prompt
        # No hotel-specific content
        assert "AIPMS" not in prompt

    def test_build_system_prompt_default_no_crash(self, clean_registry):
        """Default build should not crash"""
        builder = PromptBuilder(ontology_registry=clean_registry)
        prompt = builder.build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0
