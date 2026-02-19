"""
tests/hotel/test_action_keywords.py

Verify that all hotel domain actions have search keywords registered
and that the ActionSearchEngine can find them.

Uses the conftest client fixture to ensure proper model loading,
then accesses the global ActionRegistry singleton.
"""
import pytest
from core.ai.action_search import ActionSearchEngine


@pytest.fixture
def populated_engine(client):
    """Create an ActionSearchEngine populated from the global ActionRegistry.

    The 'client' fixture (from conftest.py) triggers full app bootstrap,
    ensuring all hotel actions are registered in the global ActionRegistry.
    """
    from app.services.actions import get_action_registry

    registry = get_action_registry()

    engine = ActionSearchEngine()
    for name, defn in registry._actions.items():
        if defn.search_keywords:
            engine.register_keywords(
                action_name=name,
                keywords=defn.search_keywords,
                entity=defn.entity,
                description=defn.description,
            )

    return engine, registry


class TestAllHotelActionsHaveKeywords:

    def test_all_actions_have_search_keywords(self, populated_engine):
        """Every hotel action should have at least 2 search keywords."""
        engine, registry = populated_engine
        for name, defn in registry._actions.items():
            assert len(defn.search_keywords) >= 2, (
                f"Action '{name}' has only {len(defn.search_keywords)} keywords: "
                f"{defn.search_keywords}. Expected at least 2."
            )

    def test_all_actions_indexed_in_search_engine(self, populated_engine):
        """Every hotel action with keywords should be indexed in the search engine."""
        engine, registry = populated_engine
        indexed_actions = set(engine._action_meta.keys())
        for name, defn in registry._actions.items():
            if defn.search_keywords:
                assert name in indexed_actions, (
                    f"Action '{name}' has keywords but is not indexed in search engine"
                )


class TestKeywordsAreSearchable:

    def test_checkin_searchable(self, populated_engine):
        """'入住' should find checkin action."""
        engine, _ = populated_engine
        results = engine.search("入住")
        names = [r.name for r in results]
        assert "checkin" in names

    def test_checkout_searchable(self, populated_engine):
        """'退房' should find checkout action."""
        engine, _ = populated_engine
        results = engine.search("退房")
        names = [r.name for r in results]
        assert "checkout" in names

    def test_reservation_searchable(self, populated_engine):
        """'订房' should find create_reservation action."""
        engine, _ = populated_engine
        results = engine.search("订房")
        names = [r.name for r in results]
        assert "create_reservation" in names

    def test_cleaning_task_searchable(self, populated_engine):
        """'清洁' should find create_task action."""
        engine, _ = populated_engine
        results = engine.search("清洁任务")
        names = [r.name for r in results]
        assert "create_task" in names

    def test_payment_searchable(self, populated_engine):
        """'付款' should find add_payment action."""
        engine, _ = populated_engine
        results = engine.search("付款")
        names = [r.name for r in results]
        assert "add_payment" in names

    def test_employee_searchable(self, populated_engine):
        """'创建员工' should find create_employee action."""
        engine, _ = populated_engine
        results = engine.search("创建员工")
        names = [r.name for r in results]
        assert "create_employee" in names


class TestChineseKeywords:

    def test_chinese_synonyms_walkin(self, populated_engine):
        """'散客' and '临时入住' should both find walkin_checkin."""
        engine, _ = populated_engine
        for query in ["散客", "临时入住"]:
            results = engine.search(query)
            names = [r.name for r in results]
            assert "walkin_checkin" in names, f"'{query}' did not find walkin_checkin"

    def test_chinese_synonyms_refund(self, populated_engine):
        """'退款' and '退钱' should both find refund_payment."""
        engine, _ = populated_engine
        for query in ["退款", "退钱"]:
            results = engine.search(query)
            names = [r.name for r in results]
            assert "refund_payment" in names, f"'{query}' did not find refund_payment"

    def test_chinese_room_clean(self, populated_engine):
        """'清洁完成' should find mark_room_clean."""
        engine, _ = populated_engine
        results = engine.search("清洁完成")
        names = [r.name for r in results]
        assert "mark_room_clean" in names
