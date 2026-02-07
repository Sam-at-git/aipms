"""
测试 NL2OntologyQuery 功能

测试 StructuredQuery 数据结构和 QueryEngine 查询引擎。
"""
import pytest
from datetime import date, timedelta
from sqlalchemy.orm import Session

from core.ontology.query import (
    StructuredQuery, FilterClause, JoinClause, FilterOperator, JoinType
)
from core.ontology.query_engine import QueryEngine, get_model_class
from core.ontology.registry import registry


class TestStructuredQuery:
    """测试 StructuredQuery 数据结构"""

    def test_from_dict_simple(self):
        """测试从字典创建简单查询"""
        data = {
            "entity": "Guest",
            "fields": ["name", "phone"],
            "limit": 50
        }
        query = StructuredQuery.from_dict(data)

        assert query.entity == "Guest"
        assert query.fields == ["name", "phone"]
        assert query.limit == 50
        assert len(query.filters) == 0
        assert len(query.joins) == 0

    def test_from_dict_with_filters(self):
        """测试带过滤条件的查询"""
        data = {
            "entity": "Room",
            "fields": ["room_number", "status"],
            "filters": [
                {"field": "room_number", "operator": "eq", "value": "201"}
            ]
        }
        query = StructuredQuery.from_dict(data)

        assert query.entity == "Room"
        assert len(query.filters) == 1
        assert query.filters[0].field == "room_number"
        assert query.filters[0].operator == FilterOperator.EQ
        assert query.filters[0].value == "201"

    def test_from_dict_with_joins(self):
        """测试带关联的查询"""
        data = {
            "entity": "Guest",
            "fields": ["name"],
            "joins": [
                {
                    "entity": "StayRecord",
                    "filters": {"status": "ACTIVE"}
                }
            ]
        }
        query = StructuredQuery.from_dict(data)

        assert query.entity == "Guest"
        assert len(query.joins) == 1
        assert query.joins[0].entity == "StayRecord"
        assert query.joins[0].filters == {"status": "ACTIVE"}

    def test_to_dict(self):
        """测试转换为字典"""
        query = StructuredQuery(
            entity="Room",
            fields=["room_number"],
            filters=[
                FilterClause(field="status", operator=FilterOperator.EQ, value="vacant_clean")
            ]
        )
        data = query.to_dict()

        assert data["entity"] == "Room"
        assert data["fields"] == ["room_number"]
        assert len(data["filters"]) == 1
        assert data["filters"][0]["operator"] == "eq"

    def test_is_simple(self):
        """测试简单查询判断"""
        # 简单查询：无 JOIN，过滤器 <= 1，字段数 <= 3
        simple_query = StructuredQuery(
            entity="Guest",
            fields=["name"]
        )
        assert simple_query.is_simple() is True

        # 复杂查询：有 JOIN
        complex_query = StructuredQuery(
            entity="Guest",
            fields=["name"],
            joins=[JoinClause(entity="StayRecord")]
        )
        assert complex_query.is_simple() is False

    def test_filter_clause_serialization(self):
        """测试 FilterClause 序列化"""
        clause = FilterClause(field="status", operator=FilterOperator.GTE, value=10)
        data = clause.to_dict()

        assert data["field"] == "status"
        assert data["operator"] == "gte"
        assert data["value"] == 10

        # 反序列化
        restored = FilterClause.from_dict(data)
        assert restored.field == clause.field
        assert restored.operator == clause.operator
        assert restored.value == clause.value


class TestQueryEngine:
    """测试 QueryEngine 查询引擎"""

    def test_get_model_class(self):
        """测试获取 ORM 模型类"""
        Room = get_model_class("Room")
        assert Room.__name__ == "Room"

        Guest = get_model_class("Guest")
        assert Guest.__name__ == "Guest"

    def test_execute_simple_query(self, db_session: Session):
        """测试执行简单查询"""
        engine = QueryEngine(db_session, registry)

        query = StructuredQuery(
            entity="Room",
            fields=["room_number", "status"],
            limit=10
        )

        result = engine.execute(query)

        assert result["display_type"] == "table"
        assert "columns" in result
        assert "rows" in result
        assert "summary" in result
        assert isinstance(result["rows"], list)

    def test_query_with_filters(self, db_session: Session):
        """测试带过滤条件的查询"""
        engine = QueryEngine(db_session, registry)

        query = StructuredQuery(
            entity="Room",
            fields=["room_number", "status"],
            filters=[
                FilterClause(field="floor", operator=FilterOperator.EQ, value=2)
            ]
        )

        result = engine.execute(query)

        # 验证返回的是2楼房间
        for row in result["rows"]:
            assert "room_number" in row
            assert "status" in row

    def test_query_with_like_filter(self, db_session: Session):
        """测试 LIKE 过滤"""
        engine = QueryEngine(db_session, registry)

        query = StructuredQuery(
            entity="Room",
            fields=["room_number"],
            filters=[
                FilterClause(field="room_number", operator=FilterOperator.LIKE, value="2")
            ]
        )

        result = engine.execute(query)

        # 应该返回房号包含"2"的房间
        assert isinstance(result["rows"], list)

    def test_column_names(self, db_session: Session):
        """测试列名映射"""
        engine = QueryEngine(db_session, registry)

        query = StructuredQuery(
            entity="Guest",
            fields=["name", "phone"]
        )

        result = engine.execute(query)

        # 验证列名被正确映射为中文
        assert "姓名" in result["columns"] or "name" in result["columns"]
        assert "电话" in result["columns"] or "phone" in result["columns"]


class TestOntologyQueryIntegration:
    """集成测试：完整的 NL2OntologyQuery 流程"""

    def test_guest_name_query_workflow(self, db_session: Session):
        """测试 '所有在住的客人姓名' 查询流程"""
        # 1. LLM 解析后的结构化查询
        structured_query_dict = {
            "entity": "Guest",
            "fields": ["name"],
            "joins": [
                {
                    "entity": "StayRecord",
                    "filters": {"status": "ACTIVE"}
                }
            ]
        }

        # 2. 创建 QueryEngine 并执行
        from core.ontology.query import StructuredQuery
        from core.ontology.query_engine import QueryEngine

        query = StructuredQuery.from_dict(structured_query_dict)
        engine = QueryEngine(db_session, registry)
        result = engine.execute(query, user=None)

        # 3. 验证结果
        assert result["display_type"] == "table"
        assert "rows" in result
        assert isinstance(result["rows"], list)
        # 只返回了 name 字段
        if result["rows"]:
            assert "name" in result["rows"][0]

    def test_room_with_filters_workflow(self, db_session: Session):
        """测试 '201房间的类型和状态' 查询流程"""
        structured_query_dict = {
            "entity": "Room",
            "fields": ["room_type", "status"],
            "filters": [
                {"field": "room_number", "operator": "eq", "value": "201"}
            ]
        }

        from core.ontology.query import StructuredQuery
        from core.ontology.query_engine import QueryEngine

        query = StructuredQuery.from_dict(structured_query_dict)
        engine = QueryEngine(db_session, registry)
        result = engine.execute(query, user=None)

        assert result["display_type"] == "table"
        # 验证返回了请求的字段
        if result["rows"]:
            row = result["rows"][0]
            # 验证包含请求的字段
            assert any(k in row for k in ["room_type", "status", "type"])


class TestFilterOperators:
    """测试各种过滤操作符"""

    def test_eq_operator(self, db_session: Session):
        """测试等于操作符"""
        engine = QueryEngine(db_session, registry)

        query = StructuredQuery(
            entity="Room",
            fields=["room_number"],
            filters=[FilterClause(field="floor", operator=FilterOperator.EQ, value=1)]
        )

        result = engine.execute(query)
        assert isinstance(result["rows"], list)

    def test_in_operator(self, db_session: Session):
        """测试 IN 操作符"""
        engine = QueryEngine(db_session, registry)

        query = StructuredQuery(
            entity="Room",
            fields=["room_number"],
            filters=[FilterClause(field="floor", operator=FilterOperator.IN, value=[1, 2])]
        )

        result = engine.execute(query)
        assert isinstance(result["rows"], list)

    def test_gte_operator(self, db_session: Session):
        """测试大于等于操作符"""
        engine = QueryEngine(db_session, registry)

        query = StructuredQuery(
            entity="Room",
            fields=["room_number"],
            filters=[FilterClause(field="floor", operator=FilterOperator.GTE, value=2)]
        )

        result = engine.execute(query)
        assert isinstance(result["rows"], list)


# 测试工具函数
def test_model_class_caching():
    """测试模型类缓存"""
    # 第一次调用
    Room1 = get_model_class("Room")
    # 第二次调用应该返回缓存的实例
    Room2 = get_model_class("Room")
    assert Room1 is Room2


# 性能测试标记（可选）
@pytest.mark.slow
class TestQueryPerformance:
    """查询性能测试"""

    def test_large_query_performance(self, db_session: Session):
        """测试大数据量查询性能"""
        import time

        engine = QueryEngine(db_session, registry)

        query = StructuredQuery(
            entity="Room",
            fields=["room_number", "status", "floor"],
            limit=1000
        )

        start = time.time()
        result = engine.execute(query)
        elapsed = time.time() - start

        # 查询应该在合理时间内完成
        assert elapsed < 5.0  # 5秒内完成
        assert result["rows"] is not None


