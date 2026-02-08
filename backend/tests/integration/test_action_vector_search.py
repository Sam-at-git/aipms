"""
Integration tests for ActionRegistry semantic search with VectorStore.

SPEC-09: Tests end-to-end semantic tool discovery functionality.
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from core.ai.actions import ActionRegistry, ActionDefinition
from core.ai.vector_store import VectorStore, SchemaItem
from core.ai import create_embedding_service_for_test
from pydantic import BaseModel


# Test parameter models
class SimpleParams(BaseModel):
    value: str


class EmptyParams(BaseModel):
    pass


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_vector_store():
    """Create a temporary VectorStore for testing"""
    # Create test embedding service (doesn't call real API)
    embedding_service = create_embedding_service_for_test()

    # Create temp directory for database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_vectors.db")

        store = VectorStore(
            db_path=db_path,
            embedding_service=embedding_service
        )

        yield store

        # Cleanup
        store.close()


@pytest.fixture
def mock_user():
    """Create a mock user for context"""
    user = Mock()
    user.id = 1
    user.role = Mock()
    user.role.value = "manager"
    return user


# ============================================================================
# End-to-end semantic search tests
# ============================================================================

def test_semantic_search_finds_relevant_actions(temp_vector_store):
    """Test that semantic search finds relevant actions based on query"""
    registry = ActionRegistry(vector_store=temp_vector_store)

    # Register multiple actions with different purposes
    @registry.register(
        name="walkin_checkin",
        entity="Guest",
        description="处理无预订客人的直接入住，分配房间并录入系统",
        search_keywords=["散客入住", "临时入住", "无预订入住", "walk in"]
    )
    def checkin(params: SimpleParams, db) -> dict:
        return {"success": True}

    @registry.register(
        name="checkout",
        entity="StayRecord",
        description="办理客人退房手续，结算账单，释放房间状态",
        search_keywords=["退房", "结账", "离店"]
    )
    def checkout(params: SimpleParams, db) -> dict:
        return {"success": True}

    @registry.register(
        name="create_task",
        entity="Task",
        description="创建清洁或维修任务，分配给员工",
        search_keywords=["打扫", "维修", "清洁"]
    )
    def create_task(params: SimpleParams, db) -> dict:
        return {"success": True}

    @registry.register(
        name="create_reservation",
        entity="Reservation",
        description="创建新的客房预订，记录客人信息和预订详情",
        search_keywords=["预订", "预约", "booking"]
    )
    def create_reservation(params: SimpleParams, db) -> dict:
        return {"success": True}

    # Semantic search for check-in related queries
    tools = registry.get_relevant_tools("我要给客人办理入住", top_k=3)

    # Verify results
    assert len(tools) > 0
    tool_names = [t["function"]["name"] for t in tools]

    # Should include checkin related action
    assert "walkin_checkin" in tool_names


def test_semantic_search_checkout_queries(temp_vector_store):
    """Test semantic search for checkout related queries"""
    registry = ActionRegistry(vector_store=temp_vector_store)

    @registry.register(
        name="checkout",
        entity="StayRecord",
        description="办理客人退房手续，结算账单",
        search_keywords=["退房", "结账", "离店", "退宿"]
    )
    def checkout(params: SimpleParams, db) -> dict:
        return {"success": True}

    @registry.register(
        name="walkin_checkin",
        entity="Guest",
        description="处理无预订客人的直接入住",
        search_keywords=["散客入住", "临时入住"]
    )
    def checkin(params: SimpleParams, db) -> dict:
        return {"success": True}

    @registry.register(
        name="create_task",
        entity="Task",
        description="创建清洁或维修任务",
        search_keywords=["打扫", "维修"]
    )
    def create_task(params: SimpleParams, db) -> dict:
        return {"success": True}

    # Test various checkout related queries
    queries = [
        "客人要退房",
        "办理退房手续",
        "结账离店",
        "客人退宿"
    ]

    for query in queries:
        tools = registry.get_relevant_tools(query, top_k=2)

        # At least one result should be checkout
        tool_names = [t["function"]["name"] for t in tools]
        assert "checkout" in tool_names, f"Query '{query}' should find checkout action"


def test_semantic_search_task_queries(temp_vector_store):
    """Test semantic search for task related queries"""
    registry = ActionRegistry(vector_store=temp_vector_store)

    @registry.register(
        name="create_task",
        entity="Task",
        description="创建清洁或维修任务",
        search_keywords=["打扫", "维修", "清洁", "维护"]
    )
    def create_task(params: SimpleParams, db) -> dict:
        return {"success": True}

    @registry.register(
        name="checkout",
        entity="StayRecord",
        description="办理客人退房手续",
    )
    def checkout(params: SimpleParams, db) -> dict:
        return {"success": True}

    @registry.register(
        name="complete_task",
        entity="Task",
        description="标记任务为已完成",
        search_keywords=["完成", "结束", "任务完成"]
    )
    def complete_task(params: SimpleParams, db) -> dict:
        return {"success": True}

    # Test task related queries
    queries = [
        "房间需要打扫",
        "创建维修任务",
        "安排清洁工作"
    ]

    for query in queries:
        tools = registry.get_relevant_tools(query, top_k=3)

        # Should find create_task
        tool_names = [t["function"]["name"] for t in tools]
        assert "create_task" in tool_names, f"Query '{query}' should find create_task"


def test_semantic_search_with_english_queries(temp_vector_store):
    """Test semantic search with English queries"""
    registry = ActionRegistry(vector_store=temp_vector_store)

    @registry.register(
        name="walkin_checkin",
        entity="Guest",
        description="Handle walk-in guest check-in without reservation",
        search_keywords=["walk in", "no reservation", "direct checkin"]
    )
    def checkin(params: SimpleParams, db) -> dict:
        return {"success": True}

    @registry.register(
        name="checkout",
        entity="StayRecord",
        description="Process guest checkout and settle bills",
        search_keywords=["check out", "departure", "settle bill"]
    )
    def checkout(params: SimpleParams, db) -> dict:
        return {"success": True}

    # Test English queries
    queries = [
        "check in a walk-in guest",
        "guest wants to check in",
        "process check out",
        "guest is leaving"
    ]

    for query in queries:
        tools = registry.get_relevant_tools(query, top_k=2)

        # Should find relevant action
        assert len(tools) > 0, f"Query '{query}' should return results"


# ============================================================================
# Tests with large action sets
# ============================================================================

def test_semantic_search_with_many_actions(temp_vector_store):
    """Test semantic search when there are many actions (above threshold)"""
    registry = ActionRegistry(vector_store=temp_vector_store)

    # Register 25 actions (above the 20-action threshold)
    entities = ["Guest", "Room", "Reservation", "StayRecord", "Task", "Bill", "Employee"]
    actions = [
        ("walkin_checkin", "办理散客入住", ["入住", "checkin"]),
        ("checkout", "办理退房", ["退房", "checkout"]),
        ("create_reservation", "创建预订", ["预订", "booking"]),
        ("cancel_reservation", "取消预订", ["取消", "cancel"]),
        ("extend_stay", "延长住宿", ["续住", "extend"]),
        ("change_room", "更换房间", ["换房", "change"]),
        ("create_task", "创建任务", ["任务", "task"]),
        ("assign_task", "分配任务", ["分配", "assign"]),
        ("complete_task", "完成任务", ["完成", "complete"]),
        ("add_payment", "添加支付", ["支付", "payment"]),
        ("adjust_bill", "调整账单", ["账单", "bill"]),
        ("update_room_status", "更新房间状态", ["房间", "room"]),
        ("view_guests", "查看客人列表", ["客人", "guest"]),
        ("view_rooms", "查看房间列表", ["房间", "room"]),
        ("view_tasks", "查看任务列表", ["任务", "task"]),
        ("view_reservations", "查看预订列表", ["预订", "reservation"]),
        ("search_guests", "搜索客人", ["搜索", "search"]),
        ("get_guest_details", "获取客人详情", ["详情", "details"]),
        ("get_room_details", "获取房间详情", ["详情", "details"]),
        ("get_bill_details", "获取账单详情", ["账单", "bill"]),
        ("validate_coupon", "验证优惠券", ["优惠券", "coupon"]),
        ("apply_discount", "应用折扣", ["折扣", "discount"]),
        ("print_receipt", "打印收据", ["打印", "print"]),
        ("send_notification", "发送通知", ["通知", "notify"]),
        ("export_report", "导出报表", ["报表", "report"]),
    ]

    for i, (name, desc, keywords) in enumerate(actions):
        entity = entities[i % len(entities)]
        registry._actions[name] = ActionDefinition(
            name=name,
            entity=entity,
            description=desc,
            category="mutation",
            parameters_schema=SimpleParams,
            handler=lambda p, **kwargs: {"success": True},
            search_keywords=keywords
        )
        # Index the action
        registry._index_action(registry._actions[name])

    # Test semantic search
    tools = registry.get_relevant_tools("客人要办理入住", top_k=5)

    # Should find walkin_checkin
    tool_names = [t["function"]["name"] for t in tools]
    assert "walkin_checkin" in tool_names

    # Should not return all 25 tools
    assert len(tools) <= 5


# ============================================================================
# Reindex tests
# ============================================================================

def test_reindex_all_actions(temp_vector_store):
    """Test reindexing all actions to VectorStore"""
    registry = ActionRegistry(vector_store=temp_vector_store)

    # Register actions
    @registry.register(
        name="action1",
        entity="Entity",
        description="First action",
        search_keywords=["one", "first"]
    )
    def action1(params: SimpleParams, db) -> dict:
        return {"success": True}

    @registry.register(
        name="action2",
        entity="Entity",
        description="Second action",
        search_keywords=["two", "second"]
    )
    def action2(params: SimpleParams, db) -> dict:
        return {"success": True}

    # Clear the vector store to simulate a reset
    temp_vector_store.clear()

    # Verify actions are no longer indexed
    items = temp_vector_store.list_items(item_type="action")
    assert len(items) == 0

    # Reindex all actions
    result = registry.reindex_all_actions()

    # Verify result
    assert result["indexed"] == 2
    assert result["failed"] == 0
    assert result["total"] == 2

    # Verify actions are re-indexed
    items = temp_vector_store.list_items(item_type="action")
    assert len(items) == 2
    item_ids = {item.id for item in items}
    assert item_ids == {"action1", "action2"}


def test_reindex_updates_action_metadata(temp_vector_store):
    """Test that reindexing updates action metadata"""
    registry = ActionRegistry(vector_store=temp_vector_store)

    # Register action
    @registry.register(
        name="test_action",
        entity="Entity",
        description="Original description",
        search_keywords=["original"]
    )
    def test_action(params: SimpleParams, db) -> dict:
        return {"success": True}

    # Verify initial index
    items = temp_vector_store.list_items(item_type="action")
    assert len(items) == 1
    # SPEC-09: Entity name is included in description
    assert "Original description" in items[0].description
    assert "original" in items[0].description
    assert "实体: Entity" in items[0].description

    # Update the action definition
    action_def = registry._actions["test_action"]
    action_def.description = "Updated description"
    action_def.search_keywords = ["updated", "new"]

    # Reindex
    result = registry.reindex_all_actions()
    assert result["indexed"] == 1

    # Verify updated index
    items = temp_vector_store.list_items(item_type="action")
    assert len(items) == 1
    assert "Updated description" in items[0].description
    assert "updated" in items[0].synonyms or "new" in items[0].synonyms
    assert "实体: Entity" in items[0].description  # Entity should still be present


# ============================================================================
# Fallback tests
# ============================================================================

def test_get_relevant_tools_falls_back_gracefully(temp_vector_store):
    """Test that get_relevant_tools falls back gracefully on error"""
    registry = ActionRegistry(vector_store=temp_vector_store)

    # Register actions
    for i in range(25):
        registry._actions[f"action{i}"] = ActionDefinition(
            name=f"action{i}",
            entity="Entity",
            description=f"Action {i}",
            category="mutation",
            parameters_schema=SimpleParams,
            handler=lambda p, **kwargs: {"success": True}
        )

    # Mock search to fail
    original_search = temp_vector_store.search
    temp_vector_store.search = Mock(side_effect=Exception("Search failed"))

    # Should fall back to all tools
    tools = registry.get_relevant_tools("query", top_k=5)

    # Should return all tools as fallback
    assert len(tools) == 25

    # Restore original method
    temp_vector_store.search = original_search


def test_registry_works_without_vector_store():
    """Test that ActionRegistry works normally when VectorStore is unavailable"""
    # Create registry without VectorStore
    registry = ActionRegistry(vector_store=None)

    # Register actions
    @registry.register(
        name="test_action",
        entity="Entity",
        description="Test action"
    )
    def test_action(params: SimpleParams, db) -> dict:
        return {"success": True}

    # Verify action is registered
    assert "test_action" in registry._actions

    # get_relevant_tools should still work
    tools = registry.get_relevant_tools("query", top_k=5)
    assert len(tools) == 1
    assert tools[0]["function"]["name"] == "test_action"
