"""
tests/core/test_semantic_query.py

SemanticQuery 数据结构的单元测试

测试覆盖：
- SemanticFilter 创建和解析
- SemanticQuery 创建和序列化
- PathSegment 和 ResolvedPath
- 路径辅助方法
- 验证逻辑
"""
import pytest
from dataclasses import asdict

from core.ontology.semantic_query import (
    SemanticFilter,
    SemanticQuery,
    PathSegment,
    ResolvedPath,
    FilterOperator,
    semantic_filter_from_dict,
    semantic_query_from_dict,
)


class TestSemanticFilter:
    """测试 SemanticFilter"""

    def test_simple_filter_creation(self):
        """测试创建简单过滤器"""
        f = SemanticFilter(path="status", operator="eq", value="ACTIVE")
        assert f.path == "status"
        assert f.operator == FilterOperator.EQ
        assert f.value == "ACTIVE"
        assert f.tokens == ["status"]

    def test_single_hop_filter_creation(self):
        """测试创建一跳过滤器"""
        f = SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")
        assert f.path == "stays.status"
        assert f.tokens == ["stays", "status"]
        assert f.is_single_hop()

    def test_multi_hop_filter_creation(self):
        """测试创建多跳过滤器"""
        f = SemanticFilter(path="stays.room.room_number", operator="eq", value="201")
        assert f.path == "stays.room.room_number"
        assert f.tokens == ["stays", "room", "room_number"]
        assert f.is_multi_hop()

    def test_filter_with_string_operator(self):
        """测试使用字符串操作符"""
        f = SemanticFilter(path="status", operator="gte", value=100)
        assert f.operator == FilterOperator.GTE

    def test_filter_serialization(self):
        """测试过滤器序列化"""
        f = SemanticFilter(path="status", operator="eq", value="ACTIVE")
        d = f.to_dict()
        assert d["path"] == "status"
        assert d["operator"] == "eq"
        assert d["value"] == "ACTIVE"

    def test_filter_deserialization(self):
        """测试过滤器反序列化"""
        d = {"path": "status", "operator": "eq", "value": "ACTIVE"}
        f = SemanticFilter.from_dict(d)
        assert f.path == "status"
        assert f.operator == FilterOperator.EQ
        assert f.value == "ACTIVE"

    def test_is_simple(self):
        """测试 is_simple 方法"""
        assert SemanticFilter(path="status", operator="eq", value="ACTIVE").is_simple()
        assert not SemanticFilter(path="stays.status", operator="eq", value="ACTIVE").is_simple()

    def test_hop_count(self):
        """测试 hop_count 方法"""
        assert SemanticFilter(path="status", operator="eq", value="ACTIVE").hop_count() == 0
        assert SemanticFilter(path="stays.status", operator="eq", value="ACTIVE").hop_count() == 1
        assert SemanticFilter(path="stays.room.status", operator="eq", value="ACTIVE").hop_count() == 2

    def test_relationship_path(self):
        """测试 relationship_path 方法"""
        f1 = SemanticFilter(path="status", operator="eq", value="ACTIVE")
        assert f1.relationship_path() == []

        f2 = SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")
        assert f2.relationship_path() == ["stays"]

        f3 = SemanticFilter(path="stays.room.status", operator="eq", value="ACTIVE")
        assert f3.relationship_path() == ["stays", "room"]

    def test_field_name(self):
        """测试 field_name 方法"""
        f1 = SemanticFilter(path="status", operator="eq", value="ACTIVE")
        assert f1.field_name() == "status"

        f2 = SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")
        assert f2.field_name() == "status"

        f3 = SemanticFilter(path="stays.room.room_number", operator="eq", value="201")
        assert f3.field_name() == "room_number"

    def test_all_operators(self):
        """测试所有操作符"""
        operators = [
            FilterOperator.EQ, FilterOperator.NE, FilterOperator.GT,
            FilterOperator.GTE, FilterOperator.LT, FilterOperator.LTE,
            FilterOperator.IN, FilterOperator.NOT_IN, FilterOperator.LIKE,
            FilterOperator.NOT_LIKE, FilterOperator.BETWEEN,
            FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL
        ]
        for op in operators:
            f = SemanticFilter(path="test", operator=op, value="val")
            assert f.operator == op

    def test_complex_values(self):
        """测试复杂值类型"""
        # 列表值
        f1 = SemanticFilter(path="status", operator="in", value=["ACTIVE", "PENDING"])
        assert f1.value == ["ACTIVE", "PENDING"]

        # 日期值
        f2 = SemanticFilter(path="check_in_time", operator="gte", value="2026-02-01")
        assert f2.value == "2026-02-01"

        # None 值
        f3 = SemanticFilter(path="deleted_at", operator="is_null", value=None)
        assert f3.value is None


class TestSemanticQuery:
    """测试 SemanticQuery"""

    def test_simple_query_creation(self):
        """测试创建简单查询"""
        q = SemanticQuery(root_object="Guest", fields=["name", "phone"])
        assert q.root_object == "Guest"
        assert q.fields == ["name", "phone"]
        assert len(q.filters) == 0
        assert q.limit == 100

    def test_query_with_filters(self):
        """测试带过滤器的查询"""
        q = SemanticQuery(
            root_object="Guest",
            fields=["name"],
            filters=[
                SemanticFilter(path="status", operator="eq", value="ACTIVE")
            ]
        )
        assert len(q.filters) == 1
        assert q.filters[0].path == "status"

    def test_query_with_single_hop(self):
        """测试一跳关联查询"""
        q = SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room_number"],
            filters=[
                SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")
            ]
        )
        assert "stays.room_number" in q.fields
        assert q.filters[0].is_single_hop()

    def test_query_with_multi_hop(self):
        """测试多跳导航查询"""
        q = SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room.room_type.name"],
            filters=[
                SemanticFilter(path="stays.room.status", operator="eq", value="VACANT_CLEAN")
            ]
        )
        assert "stays.room.room_type.name" in q.fields
        assert q.has_multi_hop()

    def test_query_serialization(self):
        """测试查询序列化"""
        q = SemanticQuery(
            root_object="Guest",
            fields=["name", "phone"],
            filters=[
                SemanticFilter(path="status", operator="eq", value="ACTIVE")
            ],
            limit=10
        )
        d = q.to_dict()
        assert d["root_object"] == "Guest"
        assert d["fields"] == ["name", "phone"]
        assert len(d["filters"]) == 1
        assert d["limit"] == 10

    def test_query_deserialization(self):
        """测试查询反序列化"""
        d = {
            "root_object": "Guest",
            "fields": ["name", "phone"],
            "filters": [
                {"path": "status", "operator": "eq", "value": "ACTIVE"}
            ],
            "limit": 10
        }
        q = SemanticQuery.from_dict(d)
        assert q.root_object == "Guest"
        assert q.fields == ["name", "phone"]
        assert len(q.filters) == 1
        assert q.limit == 10

    def test_query_deserialization_with_filter_objects(self):
        """测试使用 SemanticFilter 对象反序列化"""
        d = {
            "root_object": "Guest",
            "fields": ["name"],
            "filters": [
                SemanticFilter(path="status", operator="eq", value="ACTIVE")
            ]
        }
        q = SemanticQuery.from_dict(d)
        assert len(q.filters) == 1
        assert isinstance(q.filters[0], SemanticFilter)

    def test_is_simple(self):
        """测试 is_simple 方法"""
        q1 = SemanticQuery(
            root_object="Guest",
            fields=["name", "phone"],
            filters=[
                SemanticFilter(path="status", operator="eq", value="ACTIVE")
            ]
        )
        assert q1.is_simple()

        q2 = SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room_number"]
        )
        assert not q2.is_simple()

    def test_max_hop_count(self):
        """测试 max_hop_count 方法"""
        q1 = SemanticQuery(
            root_object="Guest",
            fields=["name", "phone"]
        )
        assert q1.max_hop_count() == 0

        q2 = SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room_number"]
        )
        assert q2.max_hop_count() == 1

        q3 = SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room.room_type.name"]
        )
        assert q3.max_hop_count() == 3

    def test_get_all_paths(self):
        """测试 get_all_paths 方法"""
        q = SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room_number"],
            filters=[
                SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")
            ]
        )
        paths = q.get_all_paths()
        assert "name" in paths
        assert "stays.room_number" in paths
        assert "stays.status" in paths

    def test_validate_success(self):
        """测试验证成功"""
        q = SemanticQuery(
            root_object="Guest",
            fields=["name", "phone"]
        )
        errors = q.validate()
        assert errors == []

    def test_validate_missing_root_object(self):
        """测试验证缺少 root_object"""
        q = SemanticQuery(root_object="", fields=["name"])
        errors = q.validate()
        assert any("root_object" in e for e in errors)

    def test_validate_empty_fields(self):
        """测试验证空字段"""
        q = SemanticQuery(root_object="Guest", fields=[])
        errors = q.validate()
        assert any("fields" in e for e in errors)

    def test_validate_invalid_field(self):
        """测试验证无效字段"""
        q = SemanticQuery(root_object="Guest", fields=[""])
        errors = q.validate()
        assert any("Invalid field" in e for e in errors)

    def test_validate_filter_list_value(self):
        """测试验证过滤器列表值"""
        q = SemanticQuery(
            root_object="Guest",
            fields=["name"],
            filters=[
                SemanticFilter(path="status", operator="in", value="ACTIVE")  # 应该是列表
            ]
        )
        errors = q.validate()
        assert any("requires list value" in e for e in errors)

    def test_repr(self):
        """测试字符串表示"""
        q = SemanticQuery(
            root_object="Guest",
            fields=["name", "phone"],
            filters=[
                SemanticFilter(path="status", operator="eq", value="ACTIVE")
            ],
            limit=10
        )
        repr_str = repr(q)
        assert "Guest" in repr_str
        assert "limit=10" in repr_str

    def test_complex_query_example(self):
        """测试复杂查询示例"""
        # 模拟真实场景：查询在住客人的姓名、电话和房间号
        q = SemanticQuery(
            root_object="Guest",
            fields=["name", "phone", "stays.room.room_number"],
            filters=[
                SemanticFilter(path="stays.status", operator="eq", value="ACTIVE"),
                SemanticFilter(path="stays.room.floor", operator="eq", value=3)
            ],
            order_by=["name"],
            limit=20
        )

        assert q.root_object == "Guest"
        assert len(q.fields) == 3
        assert len(q.filters) == 2
        assert q.max_hop_count() == 2
        assert q.limit == 20


class TestPathSegment:
    """测试 PathSegment"""

    def test_relationship_segment(self):
        """测试关系段"""
        seg = PathSegment(name="stays", segment_type="relationship", target_entity="StayRecord")
        assert seg.name == "stays"
        assert seg.is_relationship()
        assert not seg.is_field()
        assert seg.target_entity == "StayRecord"

    def test_field_segment(self):
        """测试字段段"""
        seg = PathSegment(name="room_number", segment_type="field")
        assert seg.name == "room_number"
        assert seg.is_field()
        assert not seg.is_relationship()

    def test_segment_serialization(self):
        """测试段序列化"""
        seg = PathSegment(name="stays", segment_type="relationship", target_entity="StayRecord")
        d = seg.to_dict()
        assert d["name"] == "stays"
        assert d["type"] == "relationship"
        assert d["target_entity"] == "StayRecord"


class TestResolvedPath:
    """测试 ResolvedPath"""

    def test_resolved_path_creation(self):
        """测试创建解析路径"""
        segments = [
            PathSegment(name="stays", segment_type="relationship", target_entity="StayRecord"),
            PathSegment(name="room", segment_type="relationship", target_entity="Room"),
            PathSegment(name="room_number", segment_type="field")
        ]

        resolved = ResolvedPath(
            original_path="stays.room.room_number",
            segments=segments,
            final_field="room_number",
            final_entity="Room",
            joins=["StayRecord", "Room"]
        )

        assert resolved.original_path == "stays.room.room_number"
        assert len(resolved.segments) == 3
        assert resolved.final_field == "room_number"
        assert resolved.final_entity == "Room"
        assert resolved.join_depth() == 2

    def test_join_depth(self):
        """测试 join_depth 计算"""
        segments = [
            PathSegment(name="stays", segment_type="relationship", target_entity="StayRecord"),
            PathSegment(name="room_number", segment_type="field")
        ]

        resolved = ResolvedPath(
            original_path="stays.room_number",
            segments=segments,
            final_field="room_number",
            final_entity="StayRecord",
            joins=["StayRecord"]
        )

        assert resolved.join_depth() == 1

    def test_resolved_path_serialization(self):
        """测试解析路径序列化"""
        segments = [
            PathSegment(name="status", segment_type="field")
        ]

        resolved = ResolvedPath(
            original_path="status",
            segments=segments,
            final_field="status",
            final_entity="Guest",
            joins=[]
        )

        d = resolved.to_dict()
        assert d["original_path"] == "status"
        assert d["final_field"] == "status"
        assert d["joins"] == []


class TestHelperFunctions:
    """测试辅助函数"""

    def test_semantic_filter_from_dict(self):
        """测试从字典创建过滤器"""
        d = {"path": "status", "operator": "eq", "value": "ACTIVE"}
        f = semantic_filter_from_dict(d)
        assert f.path == "status"
        assert f.operator == FilterOperator.EQ
        assert f.value == "ACTIVE"

    def test_semantic_filter_from_dict_compatible(self):
        """测试兼容格式创建过滤器"""
        d = {"field": "status", "op": "eq", "value": "ACTIVE"}
        f = semantic_filter_from_dict(d)
        assert f.path == "status"
        assert f.operator == FilterOperator.EQ
        assert f.value == "ACTIVE"

    def test_semantic_query_from_dict(self):
        """测试从字典创建查询"""
        d = {
            "root_object": "Guest",
            "fields": ["name", "phone"],
            "filters": [
                {"path": "status", "operator": "eq", "value": "ACTIVE"}
            ],
            "limit": 10
        }
        q = semantic_query_from_dict(d)
        assert q.root_object == "Guest"
        assert q.fields == ["name", "phone"]
        assert len(q.filters) == 1
        assert q.limit == 10

    def test_semantic_query_from_dict_compatible(self):
        """测试兼容格式创建查询"""
        d = {
            "entity": "Guest",
            "select": ["name", "phone"]
        }
        q = semantic_query_from_dict(d)
        assert q.root_object == "Guest"
        assert q.fields == ["name", "phone"]


class TestRealWorldScenarios:
    """测试真实世界场景"""

    def test_guest_stays_query(self):
        """测试查询客人住宿记录"""
        q = SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room_number", "stays.check_in_time"],
            filters=[
                SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")
            ]
        )

        assert q.max_hop_count() == 1
        assert "stays.room_number" in q.fields

    def test_room_tasks_query(self):
        """测试查询房间任务"""
        q = SemanticQuery(
            root_object="Room",
            fields=["room_number", "tasks.task_type", "tasks.assignee.name"],
            filters=[
                SemanticFilter(path="tasks.status", operator="eq", value="PENDING")
            ]
        )

        assert q.max_hop_count() == 2  # tasks.assignee.name 是 2 跳

    def test_room_type_query(self):
        """测试查询房间类型"""
        q = SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room.room_type.name", "stays.room.room_type.price"],
            filters=[
                SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")
            ]
        )

        assert q.max_hop_count() == 3  # stays.room.room_type.name 是 3 跳

    def test_billing_query(self):
        """测试查询账单"""
        q = SemanticQuery(
            root_object="Bill",
            fields=["total_amount", "stay.guest.name", "stay.room.room_number"],
            filters=[
                SemanticFilter(path="is_settled", operator="eq", value=False)
            ]
        )

        assert q.root_object == "Bill"
        assert q.max_hop_count() == 2

    def test_reservation_query(self):
        """测试查询预订"""
        q = SemanticQuery(
            root_object="Reservation",
            fields=["reservation_no", "guest.name", "room_type.name"],
            filters=[
                SemanticFilter(path="check_in_date", operator="gte", value="2026-02-01"),
                SemanticFilter(path="status", operator="eq", value="CONFIRMED")
            ],
            order_by=["check_in_date"],
            limit=50
        )

        assert len(q.filters) == 2
        assert q.limit == 50


class TestEdgeCases:
    """测试边界情况"""

    def test_empty_path_tokens(self):
        """测试空路径"""
        f = SemanticFilter(path="", operator="eq", value="ACTIVE")
        assert f.tokens == [""]

    def test_path_with_dots_only(self):
        """测试只有点号的路径"""
        f = SemanticFilter(path="...", operator="eq", value="ACTIVE")
        # split on "." with no text produces empty strings
        assert f.tokens == ["", "", "", ""]

    def test_very_long_path(self):
        """测试很长的路径"""
        long_path = "a.b.c.d.e.f.g.h.i.j"
        f = SemanticFilter(path=long_path, operator="eq", value="test")
        assert len(f.tokens) == 10

    def test_unicode_field_names(self):
        """测试 Unicode 字段名"""
        q = SemanticQuery(
            root_object="Guest",
            fields=["name", "phone"]
        )
        # 应该能处理 Unicode 字段名（虽然实际数据库可能不支持）
        q.fields.append("姓名")
        assert len(q.fields) == 3

    def test_none_value_filter(self):
        """测试 None 值过滤器"""
        f = SemanticFilter(path="deleted_at", operator="is_null", value=None)
        assert f.value is None

    def test_empty_list_value(self):
        """测试空列表值"""
        f = SemanticFilter(path="status", operator="in", value=[])
        assert f.value == []

    def test_zero_hop_count(self):
        """测试零跳计数"""
        q = SemanticQuery(
            root_object="Guest",
            fields=["name"]
        )
        assert q.max_hop_count() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
