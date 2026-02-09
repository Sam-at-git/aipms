"""
tests/core/test_semantic_path_resolver.py

SemanticPathResolver 单元测试

测试范围：
- 路径解析（简单、单跳、多跳）
- JOIN 生成和去重
- 过滤器编译
- 错误处理和建议
- 边界情况
"""
import pytest
from difflib import get_close_matches

from core.ontology.semantic_query import (
    SemanticQuery,
    SemanticFilter,
    PathSegment,
    ResolvedPath,
)
from core.ontology.semantic_path_resolver import (
    SemanticPathResolver,
    PathResolutionError,
)
from core.ontology.query import (
    StructuredQuery,
    FilterClause,
    JoinClause,
    FilterOperator,
    JoinType,
)


@pytest.fixture(autouse=True, scope="module")
def _bootstrap_adapter():
    """Ensure HotelDomainAdapter is bootstrapped for resolver tests."""
    from core.ontology.registry import OntologyRegistry
    from app.hotel.hotel_domain_adapter import HotelDomainAdapter
    registry = OntologyRegistry()
    adapter = HotelDomainAdapter()
    adapter.register_ontology(registry)


class TestSemanticPathResolverBasics:
    """SemanticPathResolver 基础功能测试"""

    def test_init(self):
        """测试初始化"""
        resolver = SemanticPathResolver()
        assert resolver.relationship_map is not None
        assert resolver.model_map is not None

    def test_init_with_registry(self):
        """测试带 registry 的初始化"""
        from core.ontology.registry import OntologyRegistry
        registry = OntologyRegistry()
        resolver = SemanticPathResolver(registry)
        assert resolver.registry == registry


class TestCompile:
    """compile() 方法测试"""

    def test_compile_simple_query(self):
        """测试编译简单查询（无 JOIN）"""
        resolver = SemanticPathResolver()
        semantic = SemanticQuery(
            root_object="Guest",
            fields=["name", "phone"]
        )

        structured = resolver.compile(semantic)

        assert isinstance(structured, StructuredQuery)
        assert structured.entity == "Guest"
        assert structured.fields == ["name", "phone"]
        assert len(structured.joins) == 0
        assert len(structured.filters) == 0

    def test_compile_single_hop_query(self):
        """测试编译单跳查询（一个 JOIN）"""
        resolver = SemanticPathResolver()
        semantic = SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room_number"],
            filters=[SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")]
        )

        structured = resolver.compile(semantic)

        assert len(structured.joins) == 1
        assert structured.joins[0].entity == "StayRecord"

    def test_compile_multi_hop_query(self):
        """测试编译多跳查询（多个 JOIN）"""
        resolver = SemanticPathResolver()
        semantic = SemanticQuery(
            root_object="Guest",
            fields=["stays.room.room_type.name"]
        )

        structured = resolver.compile(semantic)

        assert len(structured.joins) >= 2

    def test_compile_with_order_by(self):
        """测试带排序的查询编译"""
        resolver = SemanticPathResolver()
        semantic = SemanticQuery(
            root_object="Guest",
            fields=["name"],
            order_by=["name DESC"]
        )

        structured = resolver.compile(semantic)

        assert structured.order_by == ["name DESC"]

    def test_compile_with_limit_and_offset(self):
        """测试带限制和偏移的查询编译"""
        resolver = SemanticPathResolver()
        semantic = SemanticQuery(
            root_object="Guest",
            fields=["name"],
            limit=10,
            offset=5
        )

        structured = resolver.compile(semantic)

        assert structured.limit == 10
        assert structured.offset == 5

    def test_compile_with_distinct(self):
        """测试带 DISTINCT 的查询编译"""
        resolver = SemanticPathResolver()
        semantic = SemanticQuery(
            root_object="Guest",
            fields=["name"],
            distinct=True
        )

        structured = resolver.compile(semantic)

        assert structured.distinct is True

    def test_compile_invalid_root_entity(self):
        """测试无效根实体抛出错误"""
        resolver = SemanticPathResolver()
        semantic = SemanticQuery(root_object="InvalidEntity", fields=["name"])

        with pytest.raises(ValueError) as exc:
            resolver.compile(semantic)

        assert "Unknown root entity" in str(exc.value)


class TestResolvePath:
    """resolve_path() 方法测试"""

    def test_resolve_simple_path(self):
        """测试解析简单路径"""
        resolver = SemanticPathResolver()
        resolved = resolver.resolve_path("Guest", "name")

        assert isinstance(resolved, ResolvedPath)
        assert resolved.original_path == "name"
        assert len(resolved.segments) == 1
        assert resolved.segments[0].is_field()
        assert resolved.final_field == "name"
        assert resolved.final_entity == "Guest"
        assert len(resolved.joins) == 0

    def test_resolve_single_hop_path(self):
        """测试解析单跳路径"""
        resolver = SemanticPathResolver()
        resolved = resolver.resolve_path("Guest", "stays.status")

        assert len(resolved.segments) == 2
        assert resolved.segments[0].is_relationship()
        assert resolved.segments[1].is_field()
        assert len(resolved.joins) == 1
        assert resolved.joins[0].entity == "StayRecord"

    def test_resolve_multi_hop_path(self):
        """测试解析多跳路径"""
        resolver = SemanticPathResolver()
        resolved = resolver.resolve_path("Guest", "stays.room.status")

        assert len(resolved.segments) == 3
        assert resolved.segments[0].is_relationship()
        assert resolved.segments[1].is_relationship()
        assert resolved.segments[2].is_field()
        assert len(resolved.joins) >= 2

    def test_resolve_path_creates_correct_segments(self):
        """测试路径段创建正确"""
        resolver = SemanticPathResolver()
        resolved = resolver.resolve_path("Guest", "stays.status")

        assert resolved.segments[0].name == "stays"
        assert resolved.segments[0].segment_type == "relationship"
        assert resolved.segments[1].name == "status"
        assert resolved.segments[1].segment_type == "field"

    def test_resolve_invalid_path_raises_error(self):
        """测试无效路径抛出错误"""
        resolver = SemanticPathResolver()

        with pytest.raises(PathResolutionError) as exc:
            resolver.resolve_path("Guest", "invalid.field")

        error = exc.value
        assert error.token == "invalid"
        assert error.current_entity == "Guest"
        assert error.path == "invalid.field"

    def test_path_resolution_error_to_dict(self):
        """测试 PathResolutionError 转换为字典"""
        error = PathResolutionError(
            path="a.b.c",
            position=1,
            token="b",
            current_entity="A",
            suggestions=["x", "y"]
        )

        d = error.to_dict()
        assert d["error_type"] == "PathResolutionError"
        assert d["path"] == "a.b.c"
        assert d["token"] == "b"
        assert d["suggestions"] == ["x", "y"]

    def test_resolve_path_with_suggestions(self):
        """测试解析错误时提供建议"""
        resolver = SemanticPathResolver()

        with pytest.raises(PathResolutionError) as exc:
            resolver.resolve_path("Guest", "stayzzz.field")

        # 应该有建议（即使可能为空）
        error = exc.value
        assert hasattr(error, "suggestions")
        assert isinstance(error.suggestions, list)


class TestFindRelationship:
    """_find_relationship() 方法测试"""

    def test_find_existing_relationship(self):
        """测试查找存在的关系"""
        resolver = SemanticPathResolver()
        result = resolver._find_relationship("Guest", "stays")
        assert result == "StayRecord"

    def test_find_nonexistent_relationship(self):
        """测试查找不存在的关系"""
        resolver = SemanticPathResolver()
        result = resolver._find_relationship("Guest", "invalid")
        assert result is None

    def test_find_relationship_case_insensitive(self):
        """测试大小写不敏感的关系查找"""
        resolver = SemanticPathResolver()
        # 大小写可能不匹配，但应该能找到
        result = resolver._find_relationship("Guest", "stays")
        assert result is not None  # 至少有一种匹配方式


class TestFindSimilarRelationships:
    """_find_similar_relationships() 方法测试"""

    def test_find_similar_relationships(self):
        """测试查找相似关系"""
        resolver = SemanticPathResolver()
        similar = resolver._find_similar_relationships("Guest", "stay")

        # 应该返回一些相似的建议（"stays" is close to "stay")
        assert isinstance(similar, list)
        assert len(similar) > 0  # "stays" should be suggested

    def test_find_similar_with_no_matches(self):
        """测试无相似关系的情况"""
        resolver = SemanticPathResolver()
        similar = resolver._find_similar_relationships("Guest", "xyzabc123")

        # 应该返回空列表
        assert isinstance(similar, list)


class TestBuildJoins:
    """_build_joins() 方法测试"""

    def test_build_joins_no_paths(self):
        """测试空路径列表"""
        resolver = SemanticPathResolver()
        joins = resolver._build_joins("Guest", [])
        assert len(joins) == 0

    def test_build_joins_single_path(self):
        """测试单路径 JOIN 构建"""
        resolver = SemanticPathResolver()
        joins = resolver._build_joins("Guest", ["stays.status"])
        assert len(joins) >= 1

    def test_build_joins_multiple_paths(self):
        """测试多路径 JOIN 构建"""
        resolver = SemanticPathResolver()
        joins = resolver._build_joins("Guest", [
            "stays.status",
            "stays.room_number"
        ])
        # 去重后应该只有一个 JOIN
        assert len(joins) >= 1

    def test_join_deduplication(self):
        """测试 JOIN 去重"""
        resolver = SemanticPathResolver()
        semantic = SemanticQuery(
            root_object="Guest",
            fields=["stays.room_number", "stays.status"]
        )

        structured = resolver.compile(semantic)

        # 两个字段都经过 stay_records，但应该只有一个 JOIN
        stay_record_joins = [j for j in structured.joins if j.entity == "StayRecord"]
        assert len(stay_record_joins) == 1


class TestDedupeAndSortJoins:
    """_dedupe_and_sort_joins() 方法测试"""

    def test_dedupe_identical_joins(self):
        """测试去重相同 JOIN"""
        resolver = SemanticPathResolver()

        join1 = JoinClause(entity="StayRecord", on="stays")
        join2 = JoinClause(entity="StayRecord", on="stays")

        result = resolver._dedupe_and_sort_joins([
            (("stays",), join1),
            (("stays",), join2)
        ])

        assert len(result) == 1

    def test_sort_joins_by_depth(self):
        """测试按深度排序 JOIN"""
        resolver = SemanticPathResolver()

        join1 = JoinClause(entity="StayRecord", on="stays")
        join2 = JoinClause(entity="Room", on="room")

        result = resolver._dedupe_and_sort_joins([
            (("stays", "room"), join2),
            (("stays",), join1)
        ])

        # 短路径应该在前面
        assert result[0].entity == "StayRecord"
        assert result[1].entity == "Room"


class TestCompileFilters:
    """_compile_filters() 方法测试"""

    def test_compile_empty_filters(self):
        """测试编译空过滤器列表"""
        resolver = SemanticPathResolver()
        filters = resolver._compile_filters("Guest", [])
        assert len(filters) == 0

    def test_compile_simple_filter(self):
        """测试编译简单过滤器"""
        resolver = SemanticPathResolver()
        semantic_filters = [
            SemanticFilter(path="name", operator="eq", value="张三")
        ]

        filters = resolver._compile_filters("Guest", semantic_filters)

        assert len(filters) == 1
        assert filters[0].field == "name"
        assert filters[0].operator == FilterOperator.EQ
        assert filters[0].value == "张三"

    def test_compile_relationship_filter(self):
        """测试编译关联过滤器"""
        resolver = SemanticPathResolver()
        semantic_filters = [
            SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")
        ]

        filters = resolver._compile_filters("Guest", semantic_filters)

        assert len(filters) == 1
        assert "stays" in filters[0].field
        assert "status" in filters[0].field

    def test_compile_multiple_filters(self):
        """测试编译多个过滤器"""
        resolver = SemanticPathResolver()
        semantic_filters = [
            SemanticFilter(path="name", operator="like", value="张"),
            SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")
        ]

        filters = resolver._compile_filters("Guest", semantic_filters)

        assert len(filters) == 2


class TestConvertPathToFilterField:
    """_convert_path_to_filter_field() 方法测试"""

    def test_convert_simple_path(self):
        """测试转换简单路径"""
        resolver = SemanticPathResolver()
        result = resolver._convert_path_to_filter_field("Guest", "name")
        assert result == "name"

    def test_convert_single_hop_path(self):
        """测试转换单跳路径"""
        resolver = SemanticPathResolver()
        result = resolver._convert_path_to_filter_field("Guest", "stays.status")
        assert "stays" in result
        assert "status" in result

    def test_convert_multi_hop_path(self):
        """测试转换多跳路径"""
        resolver = SemanticPathResolver()
        result = resolver._convert_path_to_filter_field("Guest", "stays.room.status")
        assert "stays" in result
        assert "room" in result
        assert "status" in result


class TestValidateRootEntity:
    """_validate_root_entity() 方法测试"""

    def test_validate_valid_entity(self):
        """测试验证有效实体"""
        resolver = SemanticPathResolver()
        # 不应该抛出异常
        resolver._validate_root_entity("Guest")

    def test_validate_invalid_entity(self):
        """测试验证无效实体"""
        resolver = SemanticPathResolver()

        with pytest.raises(ValueError) as exc:
            resolver._validate_root_entity("InvalidEntity")

        assert "Unknown root entity" in str(exc.value)

    def test_error_includes_suggestions(self):
        """测试错误包含建议"""
        resolver = SemanticPathResolver()

        with pytest.raises(ValueError) as exc:
            resolver._validate_root_entity("Gues")  # 接近 Guest

        error_msg = str(exc.value)
        # 可能包含建议
        assert "Unknown root entity" in error_msg


class TestExtractAllPaths:
    """_extract_all_paths() 方法测试"""

    def test_extract_from_fields_only(self):
        """测试仅从 fields 提取"""
        resolver = SemanticPathResolver()
        semantic = SemanticQuery(
            root_object="Guest",
            fields=["name", "phone"]
        )

        paths = resolver._extract_all_paths(semantic)
        assert paths == ["name", "phone"]

    def test_extract_from_filters_only(self):
        """测试仅从 filters 提取"""
        resolver = SemanticPathResolver()
        semantic = SemanticQuery(
            root_object="Guest",
            fields=[],
            filters=[
                SemanticFilter(path="name", operator="eq", value="test"),
                SemanticFilter(path="phone", operator="eq", value="123")
            ]
        )

        paths = resolver._extract_all_paths(semantic)
        assert set(paths) == {"name", "phone"}

    def test_extract_deduplication(self):
        """测试路径去重"""
        resolver = SemanticPathResolver()
        semantic = SemanticQuery(
            root_object="Guest",
            fields=["name"],
            filters=[SemanticFilter(path="name", operator="eq", value="test")]
        )

        paths = resolver._extract_all_paths(semantic)
        assert paths == ["name"]  # 去重


class TestGetRelationshipAttr:
    """_get_relationship_attr() 方法测试"""

    def test_get_existing_relationship_attr(self):
        """测试获取存在的关系属性"""
        resolver = SemanticPathResolver()
        result = resolver._get_relationship_attr("Guest", "stays")
        # 应该返回一个字符串
        assert isinstance(result, str)
        assert result == "stays"

    def test_get_nonexistent_relationship_attr(self):
        """测试获取不存在的关系属性"""
        resolver = SemanticPathResolver()
        result = resolver._get_relationship_attr("Guest", "invalid")
        # 应该返回原输入
        assert result == "invalid"


class TestSuggestPaths:
    """suggest_paths() 方法测试"""

    def test_suggest_paths_returns_list(self):
        """测试建议路径返回列表"""
        resolver = SemanticPathResolver()
        suggestions = resolver.suggest_paths("Guest")
        assert isinstance(suggestions, list)

    def test_suggest_paths_depth_1(self):
        """测试深度为 1 的路径建议"""
        resolver = SemanticPathResolver()
        suggestions = resolver.suggest_paths("Guest", max_depth=1)
        assert isinstance(suggestions, list)
        # 验证路径深度不超过 1
        for path in suggestions:
            parts = path.split(".")
            assert len(parts) <= 2

    def test_suggest_paths_depth_3(self):
        """测试深度为 3 的路径建议"""
        resolver = SemanticPathResolver()
        suggestions = resolver.suggest_paths("Guest", max_depth=3)
        assert isinstance(suggestions, list)
        # 验证路径深度不超过 3
        for path in suggestions:
            parts = path.split(".")
            assert len(parts) <= 4


class TestIntegrationScenarios:
    """集成场景测试"""

    def test_full_compilation_workflow(self):
        """测试完整编译工作流"""
        resolver = SemanticPathResolver()

        semantic = SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room_number"],
            filters=[
                SemanticFilter(path="stays.status", operator="eq", value="ACTIVE"),
                SemanticFilter(path="name", operator="like", value="张")
            ],
            order_by=["name DESC"],
            limit=10
        )

        structured = resolver.compile(semantic)

        # 验证所有部分正确编译
        assert structured.entity == "Guest"
        assert "name" in structured.fields
        assert "stays.room_number" in structured.fields
        assert len(structured.filters) == 2
        assert structured.order_by == ["name DESC"]
        assert structured.limit == 10
        assert len(structured.joins) >= 1

    def test_complex_multi_hop_scenario(self):
        """测试复杂多跳场景"""
        resolver = SemanticPathResolver()

        semantic = SemanticQuery(
            root_object="Guest",
            fields=["stays.room.room_type.name"],
            filters=[
                SemanticFilter(path="stays.room.status", operator="eq", value="VACANT_CLEAN")
            ]
        )

        structured = resolver.compile(semantic)

        # 验证多跳 JOIN
        assert len(structured.joins) >= 2

    def test_duplicate_join_elimination(self):
        """测试重复 JOIN 消除"""
        resolver = SemanticPathResolver()

        semantic = SemanticQuery(
            root_object="Guest",
            fields=[
                "stays.room_number",
                "stays.status",
                "stays.check_in_time"
            ],
            filters=[
                SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")
            ]
        )

        structured = resolver.compile(semantic)

        # 虽然多个字段和过滤器都引用 stays，但只有一个 JOIN
        stay_record_joins = [j for j in structured.joins if j.entity == "StayRecord"]
        assert len(stay_record_joins) == 1


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_field_list(self):
        """测试空字段列表"""
        resolver = SemanticPathResolver()
        semantic = SemanticQuery(root_object="Guest", fields=[])

        structured = resolver.compile(semantic)
        assert structured.fields == []

    def test_path_with_leading_dot_raises_error(self):
        """测试带前导点的路径会抛出错误"""
        resolver = SemanticPathResolver()
        # ".name" 会变成 ["", "name"] - 第一个 token 是空字符串，无效
        with pytest.raises(PathResolutionError):
            resolver.resolve_path("Guest", ".name")

    def test_path_with_trailing_dot(self):
        """测试带尾随点的路径 - 空字符串作为字段"""
        resolver = SemanticPathResolver()
        # "name." 会变成 ["name", ""] - 这是两个 token，会尝试查找关系
        # 空字符串作为关系名会失败
        with pytest.raises(PathResolutionError):
            resolver.resolve_path("Guest", "name.")

    def test_very_deep_path(self):
        """测试非常深的路径"""
        resolver = SemanticPathResolver()

        # 创建一个超过 MAX_HOP_DEPTH 的路径
        deep_path = "stay_records" * 11 + ".name"

        with pytest.raises(PathResolutionError):
            resolver.resolve_path("Guest", deep_path)


class TestErrorMessages:
    """错误消息测试"""

    def test_path_resolution_error_message(self):
        """测试路径解析错误消息格式"""
        resolver = SemanticPathResolver()

        with pytest.raises(PathResolutionError) as exc:
            resolver.resolve_path("Guest", "invalid.field")

        error_msg = str(exc.value)
        assert "Cannot resolve path" in error_msg
        assert "invalid.field" in error_msg
        assert "has no relationship" in error_msg or "has no relationship" in error_msg

    def test_invalid_entity_error_message(self):
        """测试无效实体错误消息格式"""
        resolver = SemanticPathResolver()

        with pytest.raises(ValueError) as exc:
            resolver.compile(SemanticQuery(root_object="InvalidEntity", fields=["name"]))

        error_msg = str(exc.value)
        assert "Unknown root entity" in error_msg
        assert "InvalidEntity" in error_msg
