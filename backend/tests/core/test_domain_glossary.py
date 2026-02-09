"""
Tests for domain glossary functionality.

Tests the ActionRegistry.get_domain_glossary() method and
PromptBuilder._build_domain_glossary() method to ensure LLM
can distinguish between semantic signals and parameter values.

Key architectural invariant: core/ layer is domain-agnostic.
All domain-specific knowledge (category descriptions, examples) comes
from action registration metadata, not hardcoded in the framework.
"""
import pytest
from unittest.mock import Mock

from core.ai.actions import ActionRegistry
from core.ai.prompt_builder import PromptBuilder
from pydantic import BaseModel


class DummyParams(BaseModel):
    """Dummy parameter model for testing."""
    name: str


class TestActionRegistryDomainGlossary:
    """Test ActionRegistry.get_domain_glossary() method."""

    def test_empty_registry_returns_empty_glossary(self):
        registry = ActionRegistry()
        assert registry.get_domain_glossary() == {}

    def test_glossary_uses_category_description_from_registration(self):
        """category_description must come from domain layer, not hardcoded."""
        registry = ActionRegistry()

        @registry.register(
            name="test_walkin",
            entity="Guest",
            description="Test walk-in action",
            category="mutation",
            search_keywords=["kw1", "kw2"],
            semantic_category="my_category",
            category_description="My custom category description",
        )
        def handler(params: DummyParams):
            return {}

        glossary = registry.get_domain_glossary()
        assert "my_category" in glossary
        assert glossary["my_category"]["meaning"] == "My custom category description"
        assert "kw1" in glossary["my_category"]["keywords"]
        assert "kw2" in glossary["my_category"]["keywords"]

    def test_glossary_falls_back_to_category_name_without_description(self):
        """When no category_description provided, fall back to category name."""
        registry = ActionRegistry()

        @registry.register(
            name="test_action",
            entity="Entity",
            description="Test",
            category="mutation",
            search_keywords=["kw"],
            semantic_category="some_category",
            # No category_description
        )
        def handler(params: DummyParams):
            return {}

        glossary = registry.get_domain_glossary()
        assert glossary["some_category"]["meaning"] == "some_category"

    def test_glossary_uses_examples_from_registration(self):
        """glossary_examples must come from domain layer registration."""
        registry = ActionRegistry()

        examples = [
            {"correct": "example A is correct", "incorrect": "example A is wrong"}
        ]

        @registry.register(
            name="test_action",
            entity="Guest",
            description="Test",
            category="mutation",
            search_keywords=["kw"],
            semantic_category="cat",
            category_description="Cat desc",
            glossary_examples=examples,
        )
        def handler(params: DummyParams):
            return {}

        glossary = registry.get_domain_glossary()
        assert glossary["cat"]["examples"] == examples

    def test_multiple_categories(self):
        registry = ActionRegistry()

        @registry.register(
            name="action_a", entity="E", description="A", category="mutation",
            search_keywords=["ka"], semantic_category="cat_a",
            category_description="Category A",
        )
        def h1(params: DummyParams):
            return {}

        @registry.register(
            name="action_b", entity="E", description="B", category="mutation",
            search_keywords=["kb"], semantic_category="cat_b",
            category_description="Category B",
        )
        def h2(params: DummyParams):
            return {}

        glossary = registry.get_domain_glossary()
        assert "cat_a" in glossary
        assert "cat_b" in glossary
        assert glossary["cat_a"]["meaning"] == "Category A"
        assert glossary["cat_b"]["meaning"] == "Category B"

    def test_actions_without_semantic_category_excluded(self):
        registry = ActionRegistry()

        @registry.register(
            name="no_cat", entity="E", description="X", category="mutation",
            search_keywords=["kw1", "kw2"],
        )
        def handler(params: DummyParams):
            return {}

        assert registry.get_domain_glossary() == {}

    def test_keywords_aggregated_across_actions_in_same_category(self):
        registry = ActionRegistry()

        @registry.register(
            name="a1", entity="E", description="A1", category="mutation",
            search_keywords=["kw1", "kw2"], semantic_category="shared_cat",
            category_description="Shared",
        )
        def h1(params: DummyParams):
            return {}

        @registry.register(
            name="a2", entity="E", description="A2", category="mutation",
            search_keywords=["kw3", "kw4"], semantic_category="shared_cat",
        )
        def h2(params: DummyParams):
            return {}

        glossary = registry.get_domain_glossary()
        kws = glossary["shared_cat"]["keywords"]
        assert set(kws) == {"kw1", "kw2", "kw3", "kw4"}

    def test_duplicate_keywords_deduplicated(self):
        registry = ActionRegistry()

        @registry.register(
            name="a1", entity="E", description="A1", category="mutation",
            search_keywords=["dup", "unique1"], semantic_category="cat",
            category_description="C",
        )
        def h1(params: DummyParams):
            return {}

        @registry.register(
            name="a2", entity="E", description="A2", category="mutation",
            search_keywords=["dup", "unique2"], semantic_category="cat",
        )
        def h2(params: DummyParams):
            return {}

        glossary = registry.get_domain_glossary()
        kws = glossary["cat"]["keywords"]
        assert kws.count("dup") == 1

    def test_examples_aggregated_across_actions(self):
        registry = ActionRegistry()

        @registry.register(
            name="a1", entity="E", description="A1", category="mutation",
            search_keywords=["k1"], semantic_category="cat",
            category_description="C",
            glossary_examples=[{"correct": "ex1"}],
        )
        def h1(params: DummyParams):
            return {}

        @registry.register(
            name="a2", entity="E", description="A2", category="mutation",
            search_keywords=["k2"], semantic_category="cat",
            glossary_examples=[{"correct": "ex2"}],
        )
        def h2(params: DummyParams):
            return {}

        glossary = registry.get_domain_glossary()
        examples = glossary["cat"]["examples"]
        assert len(examples) == 2
        assert {"correct": "ex1"} in examples
        assert {"correct": "ex2"} in examples

    def test_category_description_upgrade(self):
        """If first action has no description but second does, it should upgrade."""
        registry = ActionRegistry()

        @registry.register(
            name="a1", entity="E", description="A1", category="mutation",
            search_keywords=["k1"], semantic_category="cat",
            # No category_description
        )
        def h1(params: DummyParams):
            return {}

        @registry.register(
            name="a2", entity="E", description="A2", category="mutation",
            search_keywords=["k2"], semantic_category="cat",
            category_description="Proper description",
        )
        def h2(params: DummyParams):
            return {}

        glossary = registry.get_domain_glossary()
        assert glossary["cat"]["meaning"] == "Proper description"


class TestPromptBuilderDomainGlossary:
    """Test PromptBuilder._build_domain_glossary() method."""

    def test_returns_empty_without_action_registry(self):
        """No action_registry injected -> empty glossary."""
        builder = PromptBuilder()
        assert builder._build_domain_glossary() == ""

    def test_returns_empty_with_empty_glossary(self):
        """ActionRegistry with no glossary data -> empty string."""
        mock_ar = Mock()
        mock_ar.get_domain_glossary.return_value = {}
        builder = PromptBuilder(action_registry=mock_ar)
        assert builder._build_domain_glossary() == ""

    def test_glossary_format_with_injected_registry(self):
        """Test glossary output format using DI (no app import)."""
        mock_ar = Mock()
        mock_ar.get_domain_glossary.return_value = {
            "checkin_type": {
                "keywords": ["kw_a", "kw_b"],
                "meaning": "Test category meaning",
                "examples": [
                    {"correct": "kw_a -> param_x='real_value'",
                     "incorrect": "kw_a -> param_x='kw_a'"}
                ]
            }
        }

        builder = PromptBuilder(action_registry=mock_ar)
        glossary = builder._build_domain_glossary()

        assert "领域关键词表" in glossary
        assert "语义信号" in glossary
        assert "不是参数值" in glossary
        assert "kw_a" in glossary
        assert "kw_b" in glossary
        assert "Test category meaning" in glossary
        assert "参数提取规则" in glossary
        assert "param_x='real_value'" in glossary

    def test_no_hardcoded_hotel_terms_in_core_output(self):
        """Core layer glossary builder must not inject hotel-specific terms."""
        mock_ar = Mock()
        mock_ar.get_domain_glossary.return_value = {
            "cat": {
                "keywords": ["generic_kw"],
                "meaning": "Generic",
                "examples": []
            }
        }

        builder = PromptBuilder(action_registry=mock_ar)
        glossary = builder._build_domain_glossary()

        # These hotel-specific terms must NOT appear from the core layer itself
        assert "guest_name" not in glossary
        assert "room_number" not in glossary
        assert "散客" not in glossary


class TestDomainGlossaryWalkinDetection:
    """Test walk-in keyword detection logic used by _checkin_response."""

    def test_search_keywords_from_registration_detect_walkin(self):
        """Verify that registered search_keywords correctly match walkin messages."""
        registry = ActionRegistry()

        @registry.register(
            name="walkin_checkin", entity="Guest", description="Walk-in",
            category="mutation",
            search_keywords=["散客", "直接入住", "无预订", "临时入住", "walk-in"],
            semantic_category="checkin_type",
            category_description="入住方式",
        )
        def handler(params: DummyParams):
            return {}

        action = registry.get_action("walkin_checkin")
        keywords = action.search_keywords

        # Positive cases
        test_messages = [
            "有散客入住，王六儿 13122223333 明晚入住203房间",
            "直接入住301房",
            "无预订客人要入住",
            "临时入住201",
            "walk-in guest for room 101",
        ]
        for msg in test_messages:
            assert any(kw in msg for kw in keywords), f"Failed to detect walkin in: {msg}"

        # Negative case
        assert not any(kw in "帮王六儿办理入住" for kw in keywords)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
