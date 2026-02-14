"""
测试自然语言查询功能

测试各种复杂的自然语言查询场景，模拟真实用户提问。
这些测试使用 AIService 的完整流程，包括意图识别和查询执行。
"""
import pytest
from datetime import date, timedelta
from sqlalchemy.orm import Session

from app.models.ontology import (
    Room, RoomType, RoomStatus, Guest, StayRecord, Task, TaskStatus, TaskType
)
from app.services.ai_service import AIService
from app.models.ontology import Employee, EmployeeRole
from app.security.auth import get_password_hash
from decimal import Decimal

# 导入模型以触发装饰器注册
import app.models.ontology
from core.ontology.registry import registry


@pytest.fixture
def query_user(db_session):
    """创建测试用户"""
    user = Employee(
        username="query_test_user",
        password_hash=get_password_hash("123456"),
        name="查询测试用户",
        role=EmployeeRole.MANAGER,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def ai_service(db_session):
    """创建 AIService 实例"""
    return AIService(db_session)


@pytest.fixture
def setup_query_data(db_session):
    """设置查询测试数据"""
    # 创建房型
    room_types = []
    room_type_data = [
        {"name": "标间", "description": "标准双床房", "base_price": Decimal("288.00"), "max_occupancy": 2},
        {"name": "大床房", "description": "大床房", "base_price": Decimal("328.00"), "max_occupancy": 2},
        {"name": "豪华间", "description": "豪华间", "base_price": Decimal("458.00"), "max_occupancy": 3},
    ]
    for rt_data in room_type_data:
        rt = RoomType(**rt_data)
        db_session.add(rt)
        room_types.append(rt)
    db_session.commit()

    # 刷新以获取ID
    for rt in room_types:
        db_session.refresh(rt)

    rt_map = {rt.name: rt for rt in room_types}

    # 创建房间
    rooms = []
    # 标间 - 一些空闲一些占用
    for i in range(1, 6):
        room = Room(
            room_number=f"{i:02d}",
            floor=1,
            room_type_id=rt_map["标间"].id,
            status=RoomStatus.VACANT_CLEAN if i <= 3 else RoomStatus.OCCUPIED
        )
        rooms.append(room)

    # 大床房 - 一些空闲一些占用
    for i in range(6, 10):
        room = Room(
            room_number=f"{i:02d}",
            floor=1,
            room_type_id=rt_map["大床房"].id,
            status=RoomStatus.VACANT_CLEAN if i <= 7 else RoomStatus.OCCUPIED
        )
        rooms.append(room)

    # 豪华间 - 一些空闲一些占用
    for i in range(10, 13):
        room = Room(
            room_number=f"{i:02d}",
            floor=1,
            room_type_id=rt_map["豪华间"].id,
            status=RoomStatus.VACANT_CLEAN if i <= 11 else RoomStatus.OCCUPIED
        )
        rooms.append(room)

    for room in rooms:
        db_session.add(room)
    db_session.commit()

    # 创建一些测试任务
    for room in rooms[:3]:
        task = Task(
            room_id=room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING
        )
        db_session.add(task)
    db_session.commit()

    return {"rooms": rooms, "room_types": room_types}


class TestNaturalLanguageQueries:
    """测试自然语言查询的各种场景"""

    def test_query_vacant_king_rooms(self, ai_service, query_user, setup_query_data):
        """测试1: '查询目前有多少间大床房空闲？'"""
        result = ai_service.process_message(
            message="查询目前有多少间大床房空闲",
            user=query_user,
            conversation_history=[],
            topic_id=None,
            follow_up_context=None,
            language='zh'
        )

        # 验证响应 - ontology_query pipeline returns structured data
        assert "message" in result
        assert len(result["message"]) > 0

    def test_query_vacant_standard_rooms(self, ai_service, query_user, setup_query_data):
        """测试2: '空闲标间有多少间？'"""
        result = ai_service.process_message(
            message="空闲标间有多少间",
            user=query_user,
            conversation_history=[],
            topic_id=None,
            follow_up_context=None,
            language='zh'
        )

        assert "message" in result
        assert len(result["message"]) > 0

    def test_query_vacant_deluxe_rooms(self, ai_service, query_user, setup_query_data):
        """测试3: '豪华间还有空房吗？'"""
        result = ai_service.process_message(
            message="豪华间还有空房吗",
            user=query_user,
            conversation_history=[],
            topic_id=None,
            follow_up_context=None,
            language='zh'
        )

        assert "message" in result
        # 豪华间可能不被识别，至少应该有响应
        assert len(result["message"]) > 0

    def test_query_current_guests(self, ai_service, query_user, setup_query_data):
        """测试4: '现在有哪些客人在住？'"""
        result = ai_service.process_message(
            message="现在有哪些客人在住",
            user=query_user,
            conversation_history=[],
            topic_id=None,
            follow_up_context=None,
            language='zh'
        )

        assert "message" in result
        # 可能包含客人信息或提示没有客人
        assert len(result["message"]) > 0

    def test_query_room_status_summary(self, ai_service, query_user, setup_query_data):
        """测试5: '房间状态汇总'"""
        result = ai_service.process_message(
            message="房间状态汇总",
            user=query_user,
            conversation_history=[],
            topic_id=None,
            follow_up_context=None,
            language='zh'
        )

        assert "message" in result
        # 应该包含统计信息
        assert any(kw in result["message"] for kw in ["空闲", "入住", "间", "房间"])

    def test_query_pending_tasks(self, ai_service, query_user, setup_query_data):
        """测试6: '有哪些待处理的任务？'"""
        result = ai_service.process_message(
            message="有哪些待处理的任务",
            user=query_user,
            conversation_history=[],
            topic_id=None,
            follow_up_context=None,
            language='zh'
        )

        assert "message" in result

    def test_query_occupied_rooms(self, ai_service, query_user, setup_query_data):
        """测试7: '已入住房间有哪些？'"""
        result = ai_service.process_message(
            message="已入住房间有哪些",
            user=query_user,
            conversation_history=[],
            topic_id=None,
            follow_up_context=None,
            language='zh'
        )

        assert "message" in result

    def test_query_total_rooms(self, ai_service, query_user, setup_query_data):
        """测试8: '总共有多少间房？'"""
        result = ai_service.process_message(
            message="房间总数",
            user=query_user,
            conversation_history=[],
            topic_id=None,
            follow_up_context=None,
            language='zh'
        )

        assert "message" in result
        # 应该有房间相关的响应
        assert len(result["message"]) > 0

    def test_query_standard_room_count(self, ai_service, query_user, setup_query_data):
        """测试9: '标间有多少间？'（不带空闲关键词）"""
        result = ai_service.process_message(
            message="标间有多少间",
            user=query_user,
            conversation_history=[],
            topic_id=None,
            follow_up_context=None,
            language='zh'
        )

        assert "message" in result
        assert len(result["message"]) > 0

    def test_query_room_availability_short(self, ai_service, query_user, setup_query_data):
        """测试10: '空房'（简短查询）"""
        result = ai_service.process_message(
            message="空房",
            user=query_user,
            conversation_history=[],
            topic_id=None,
            follow_up_context=None,
            language='zh'
        )

        assert "message" in result
        # 应该返回房间相关信息或帮助提示
        assert len(result["message"]) > 0


class TestStructuredQueryAdvanced:
    """测试高级结构化查询场景"""

    def test_query_vacant_king_rooms_structure(self, db_session, setup_query_data):
        """测试11: 通过结构化查询直接查询空闲大床房"""
        from core.ontology.query import StructuredQuery
        from core.ontology.query_engine import QueryEngine

        query_dict = {
            "entity": "Room",
            "fields": ["room_number", "status"],
            "filters": [
                {"field": "status", "operator": "eq", "value": "vacant_clean"}
            ],
            "joins": [
                {
                    "entity": "RoomType",
                    "filters": {"name": "大床房"}
                }
            ],
            "limit": 100
        }

        query = StructuredQuery.from_dict(query_dict)
        engine = QueryEngine(db_session, registry)
        result = engine.execute(query)

        assert result["display_type"] == "table"
        assert "rows" in result
        assert isinstance(result["rows"], list)

    def test_query_multiple_room_types(self, db_session, setup_query_data):
        """测试12: 查询多种房型的状态"""
        from core.ontology.query import StructuredQuery
        from core.ontology.query_engine import QueryEngine

        query_dict = {
            "entity": "Room",
            "fields": ["room_number", "room_type", "status"],
            "limit": 100
        }

        query = StructuredQuery.from_dict(query_dict)
        engine = QueryEngine(db_session, registry)
        result = engine.execute(query)

        assert result["display_type"] == "table"
        assert isinstance(result["rows"], list)
        # 应该有测试数据
        assert len(result["rows"]) > 0

    def test_query_with_multiple_filters(self, db_session, setup_query_data):
        """测试13: 多条件过滤查询"""
        from core.ontology.query import StructuredQuery, FilterClause, FilterOperator
        from core.ontology.query_engine import QueryEngine

        query = StructuredQuery(
            entity="Room",
            fields=["room_number", "status"],
            filters=[
                FilterClause(field="status", operator=FilterOperator.EQ, value="vacant_clean"),
                FilterClause(field="floor", operator=FilterOperator.EQ, value=1)
            ],
            limit=50
        )

        engine = QueryEngine(db_session, registry)
        result = engine.execute(query)

        assert isinstance(result["rows"], list)

    def test_query_tasks_pending(self, db_session, setup_query_data):
        """测试14: 查询待处理任务"""
        from core.ontology.query import StructuredQuery, FilterClause, FilterOperator
        from core.ontology.query_engine import QueryEngine

        query = StructuredQuery(
            entity="Task",
            fields=["task_type", "status"],
            filters=[
                FilterClause(field="status", operator=FilterOperator.EQ, value="pending")
            ],
            limit=50
        )

        engine = QueryEngine(db_session, registry)
        result = engine.execute(query)

        assert result["display_type"] == "table"
        assert isinstance(result["rows"], list)

    def test_query_with_order_and_limit(self, db_session, setup_query_data):
        """测试15: 带排序和限制的查询"""
        from core.ontology.query import StructuredQuery
        from core.ontology.query_engine import QueryEngine

        query_dict = {
            "entity": "Room",
            "fields": ["room_number"],
            "order_by": ["room_number ASC"],
            "limit": 5
        }

        query = StructuredQuery.from_dict(query_dict)
        engine = QueryEngine(db_session, registry)
        result = engine.execute(query)

        assert isinstance(result["rows"], list)
        assert len(result["rows"]) <= 5

    def test_query_like_pattern(self, db_session, setup_query_data):
        """测试16: 模糊匹配查询"""
        from core.ontology.query import StructuredQuery, FilterClause, FilterOperator
        from core.ontology.query_engine import QueryEngine

        query = StructuredQuery(
            entity="Room",
            fields=["room_number"],
            filters=[
                FilterClause(field="room_number", operator=FilterOperator.LIKE, value="0")
            ],
            limit=50
        )

        engine = QueryEngine(db_session, registry)
        result = engine.execute(query)

        assert isinstance(result["rows"], list)

    def test_query_in_operator(self, db_session, setup_query_data):
        """测试17: IN 操作符查询"""
        from core.ontology.query import StructuredQuery, FilterClause, FilterOperator
        from core.ontology.query_engine import QueryEngine

        query = StructuredQuery(
            entity="Room",
            fields=["room_number", "status"],
            filters=[
                FilterClause(field="room_number", operator=FilterOperator.IN, value=["01", "02", "03"])
            ],
            limit=50
        )

        engine = QueryEngine(db_session, registry)
        result = engine.execute(query)

        assert isinstance(result["rows"], list)

    def test_query_range_filter(self, db_session, setup_query_data):
        """测试18: 范围过滤查询"""
        from core.ontology.query import StructuredQuery, FilterClause, FilterOperator
        from core.ontology.query_engine import QueryEngine

        query = StructuredQuery(
            entity="Room",
            fields=["room_number", "floor"],
            filters=[
                FilterClause(field="floor", operator=FilterOperator.GTE, value=1),
                FilterClause(field="floor", operator=FilterOperator.LTE, value=2)
            ],
            limit=50
        )

        engine = QueryEngine(db_session, registry)
        result = engine.execute(query)

        assert isinstance(result["rows"], list)

    def test_query_all_fields(self, db_session, setup_query_data):
        """测试19: 查询所有字段"""
        from core.ontology.query import StructuredQuery
        from core.ontology.query_engine import QueryEngine

        query = StructuredQuery(
            entity="Room",
            fields=["room_number", "status", "floor"],
            limit=10
        )

        engine = QueryEngine(db_session, registry)
        result = engine.execute(query)

        assert result["display_type"] == "table"
        if result["rows"]:
            # 验证返回了请求的字段
            row = result["rows"][0]
            assert any(k in row for k in ["room_number", "status", "floor"])

    def test_query_empty_result(self, db_session):
        """测试20: 查询无结果的情况"""
        from core.ontology.query import StructuredQuery, FilterClause, FilterOperator
        from core.ontology.query_engine import QueryEngine

        # 查询不存在的房间
        query = StructuredQuery(
            entity="Room",
            fields=["room_number"],
            filters=[
                FilterClause(field="room_number", operator=FilterOperator.EQ, value="999")
            ],
            limit=10
        )

        engine = QueryEngine(db_session, registry)
        result = engine.execute(query)

        assert result["display_type"] == "table"
        assert isinstance(result["rows"], list)
        assert len(result["rows"]) == 0

    def test_ontology_query_action_handling(self, ai_service, query_user, setup_query_data):
        """测试21: ontology_query 操作被正确识别为查询类操作

        这个测试验证 ontology_query 不会被错误地经过参数增强逻辑，
        该逻辑会修改 params 并可能破坏 StructuredQuery 的结构。
        """
        from unittest.mock import patch

        # 模拟 LLM 返回 ontology_query action
        llm_response = {
            "message": "查询空闲大床房",
            "suggested_actions": [{
                "action_type": "ontology_query",
                "params": {
                    "entity": "Room",
                    "fields": ["room_number"],
                    "filters": [{
                        "field": "room_type_id",
                        "operator": "eq",
                        "value": "大床房"  # LLM 可能返回房型名称而不是 ID
                    }]
                },
                "requires_confirmation": False
            }],
            "context": {}
        }

        # Mock LLM service 返回预设响应
        with patch.object(ai_service.llm_service, 'chat', return_value=llm_response):
            with patch.object(ai_service.llm_service, 'is_enabled', return_value=True):
                result = ai_service.process_message(
                    message="查询空闲大床房",
                    user=query_user,
                    conversation_history=[],
                    topic_id=None,
                    follow_up_context=None,
                    language='zh'
                )

        # 验证结果
        assert "message" in result
        # ontology_query 应该被正确处理，返回查询结果
        # 如果没有被正确处理，可能会报错或返回错误消息
        assert "查询失败" not in result.get("message", "")
        assert "error" not in result.get("context", {})
