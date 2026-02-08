"""
core/ontology/semantic_query.py

语义查询数据结构 - LLM 友好的查询表示

关键创新：
- LLM 使用点分路径（dot-notation）而非 SQL JOIN 语法
- 例如：Guest.stays.room.room_number 代替多表 JOIN
- SemanticPathResolver 将 SemanticQuery 编译为 StructuredQuery

这是 Phase 3 的核心组件（SPEC-11），为语义路径编译器提供基础。
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum


class FilterOperator(str, Enum):
    """过滤操作符 - 与 StructuredQuery 兼容"""
    EQ = "eq"          # 等于
    NE = "ne"          # 不等于
    GT = "gt"          # 大于
    GTE = "gte"        # 大于等于
    LT = "lt"          # 小于
    LTE = "lte"        # 小于等于
    IN = "in"          # 在列表中
    NOT_IN = "not_in"  # 不在列表中
    LIKE = "like"      # 模糊匹配
    NOT_LIKE = "not_like"
    BETWEEN = "between"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


@dataclass
class SemanticFilter:
    """
    语义过滤器 - 使用点分路径表达过滤条件

    路径语法：
    - "status" - 直接字段
    - "stays.status" - 一跳关联（通过关系属性）
    - "stays.room.status" - 多跳关联
    - "stays.room.room_type.name" - 深度导航

    Examples:
        # 简单过滤
        SemanticFilter(path="status", operator=FilterOperator.EQ, value="ACTIVE")

        # 一跳关联
        SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")

        # 多跳导航
        SemanticFilter(
            path="stays.room.room_number",
            operator="eq",
            value="201"
        )

        # 日期范围
        SemanticFilter(
            path="stays.check_in_time",
            operator="gte",
            value="2026-02-01"
        )
    """
    path: str                              # 点分路径，如 "stays.room.status"
    operator: FilterOperator = FilterOperator.EQ
    value: Any = None

    def __post_init__(self):
        """解析路径为 tokens"""
        self.tokens = self.path.split(".")
        # 规范化操作符（支持字符串输入）
        if isinstance(self.operator, str):
            self.operator = FilterOperator(self.operator)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "path": self.path,
            "operator": self.operator.value if isinstance(self.operator, FilterOperator) else self.operator,
            "value": self.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticFilter":
        """从字典创建"""
        return cls(
            path=data["path"],
            operator=data.get("operator", "eq"),
            value=data.get("value")
        )

    def is_simple(self) -> bool:
        """判断是否为简单字段（无点号）"""
        return len(self.tokens) == 1

    def is_single_hop(self) -> bool:
        """判断是否为一跳关联"""
        return len(self.tokens) == 2

    def is_multi_hop(self) -> bool:
        """判断是否为多跳关联"""
        return len(self.tokens) > 2

    def hop_count(self) -> int:
        """返回跳数（关系数量）"""
        return max(0, len(self.tokens) - 1)

    def relationship_path(self) -> List[str]:
        """
        返回关系路径（不包括最后一个字段）

        Examples:
            "stays.status" → ["stays"]
            "stays.room.room_number" → ["stays", "room"]
        """
        return self.tokens[:-1]

    def field_name(self) -> str:
        """
        返回最终字段名

        Examples:
            "stays.status" → "status"
            "stays.room.room_number" → "room_number"
        """
        return self.tokens[-1] if self.tokens else ""


@dataclass
class PathSegment:
    """
    路径段 - 表示路径中的一段

    用于 SemanticPathResolver 解析路径

    Examples:
        "stays.room.room_number" 解析为：
        [
            PathSegment(name="stays", type="relationship", target_entity="StayRecord"),
            PathSegment(name="room", type="relationship", target_entity="Room"),
            PathSegment(name="room_number", type="field")
        ]
    """
    name: str
    segment_type: Literal["relationship", "field"]
    target_entity: Optional[str] = None  # 对于 relationship，目标实体名

    def is_relationship(self) -> bool:
        """是否为关系段"""
        return self.segment_type == "relationship"

    def is_field(self) -> bool:
        """是否为字段段"""
        return self.segment_type == "field"

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "name": self.name,
            "type": self.segment_type,
            "target_entity": self.target_entity
        }


@dataclass
class ResolvedPath:
    """
    解析后的路径 - 包含完整的导航信息

    由 SemanticPathResolver 返回，包含：
    - 原始路径
    - 解析后的段
    - 需要的 JOIN 子句
    - 最终字段信息
    """
    original_path: str                    # 原始路径
    segments: List[PathSegment]           # 解析后的段
    final_field: str                      # 最终字段名
    final_entity: str                     # 最终实体名
    joins: List[str] = field(default_factory=list)  # 需要的 JOIN（实体名列表）

    def join_depth(self) -> int:
        """返回 JOIN 深度"""
        return len([s for s in self.segments if s.is_relationship()])

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "original_path": self.original_path,
            "segments": [s.to_dict() for s in self.segments],
            "final_field": self.final_field,
            "final_entity": self.final_entity,
            "joins": self.joins
        }


@dataclass
class SemanticQuery:
    """
    语义查询 - LLM 输出的查询表示

    与 StructuredQuery 的关键区别：
    - SemanticQuery: LLM 层（意图表达），使用点分路径
    - StructuredQuery: 执行层（SQL 生成），使用 JOIN 子句

    LLM 无需理解：
    - JOIN 类型（INNER/LEFT/OUTER）
    - JOIN 顺序
    - 关系方向（一对多/多对一）

    LLM 只需表达：
    - "我要 Guest 的 stays 中的 room 的 room_number"

    Examples:
        # 简单查询 - 所有客人姓名
        SemanticQuery(root_object="Guest", fields=["name"])

        # 一跳关联 - 在住客人的姓名和房间号
        SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room_number"],
            filters=[SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")]
        )

        # 多跳导航 - 客人入住的房间类型名称
        SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room.room_type.name"],
            filters=[SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")]
        )

        # 复杂过滤 - 特定房间的在住客人
        SemanticQuery(
            root_object="Guest",
            fields=["name", "phone"],
            filters=[
                SemanticFilter(path="stays.status", operator="eq", value="ACTIVE"),
                SemanticFilter(path="stays.room.room_number", operator="eq", value="201")
            ],
            limit=10
        )
    """
    root_object: str                       # 根实体名，如 "Guest"
    fields: List[str] = field(default_factory=list)  # 字段列表，支持点分路径
    filters: List[SemanticFilter] = field(default_factory=list)
    order_by: List[str] = field(default_factory=list)
    limit: int = 100
    offset: int = 0
    distinct: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（用于 JSON 传输）"""
        return {
            "root_object": self.root_object,
            "fields": self.fields,
            "filters": [f.to_dict() for f in self.filters],
            "order_by": self.order_by,
            "limit": self.limit,
            "offset": self.offset,
            "distinct": self.distinct
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticQuery":
        """从字典反序列化"""
        filters = [
            SemanticFilter.from_dict(f) if isinstance(f, dict) else f
            for f in data.get("filters", [])
        ]
        return cls(
            root_object=data["root_object"],
            fields=data.get("fields", []),
            filters=filters,
            order_by=data.get("order_by", []),
            limit=data.get("limit", 100),
            offset=data.get("offset", 0),
            distinct=data.get("distinct", False)
        )

    def is_simple(self) -> bool:
        """判断是否为简单查询（直接字段，无关联）"""
        all_simple = all(
            "." not in field
            for field in self.fields
        )
        all_filters_simple = all(
            f.is_simple()
            for f in self.filters
        )
        return all_simple and all_filters_simple

    def max_hop_count(self) -> int:
        """返回最大跳数"""
        max_hops = 0
        for field in self.fields:
            hops = field.count(".")
            max_hops = max(max_hops, hops)
        for filter_obj in self.filters:
            max_hops = max(max_hops, filter_obj.hop_count())
        return max_hops

    def has_multi_hop(self) -> bool:
        """是否有任何多跳路径"""
        return self.max_hop_count() > 1

    def get_all_paths(self) -> List[str]:
        """获取所有路径（字段 + 过滤器）"""
        paths = []
        paths.extend(self.fields)
        paths.extend([f.path for f in self.filters])
        return paths

    def validate(self) -> List[str]:
        """
        基本验证

        Returns:
            错误列表，如果为空则验证通过
        """
        errors = []

        if not self.root_object:
            errors.append("root_object is required")

        if not self.fields:
            errors.append("fields cannot be empty")

        # 检查路径格式
        for field in self.fields:
            if not field:
                errors.append(f"Invalid field: empty string")

        for filter_obj in self.filters:
            if not filter_obj.path:
                errors.append("Filter path cannot be empty")
            if filter_obj.operator in (FilterOperator.IN, FilterOperator.NOT_IN, FilterOperator.BETWEEN):
                if not isinstance(filter_obj.value, (list, tuple)):
                    errors.append(f"Filter {filter_obj.path}: operator {filter_obj.operator.value} requires list value")

        return errors

    def __repr__(self) -> str:
        """字符串表示"""
        filters_str = ", ".join([f"{f.path}={f.value}" for f in self.filters[:3]])
        if len(self.filters) > 3:
            filters_str += f" ... ({len(self.filters)} total)"
        return (
            f"SemanticQuery(root_object={self.root_object}, "
            f"fields={self.fields[:3]}{'...' if len(self.fields) > 3 else ''}, "
            f"filters=[{filters_str}], limit={self.limit})"
        )


# 辅助函数

def semantic_filter_from_dict(data: Dict[str, Any]) -> SemanticFilter:
    """
    从字典创建 SemanticFilter 的便捷函数

    支持多种输入格式：
    - {"path": "status", "operator": "eq", "value": "ACTIVE"}
    - {"field": "status", "op": "eq", "value": "ACTIVE"}  # 兼容格式
    """
    # 兼容不同的字段名
    path = data.get("path") or data.get("field", "")
    operator = data.get("operator") or data.get("op", "eq")
    value = data.get("value")

    return SemanticFilter(path=path, operator=operator, value=value)


def semantic_query_from_dict(data: Dict[str, Any]) -> SemanticQuery:
    """
    从字典创建 SemanticQuery 的便捷函数

    支持多种输入格式：
    - 标准：{"root_object": "Guest", "fields": ["name"]}
    - 简化：{"entity": "Guest", "select": ["name"]}
    """
    # 兼容不同的字段名
    root_object = data.get("root_object") or data.get("entity", "")
    fields = data.get("fields") or data.get("select", [])

    # 处理过滤器
    filters_data = data.get("filters", [])
    filters = []
    for f in filters_data:
        if isinstance(f, dict):
            filters.append(semantic_filter_from_dict(f))
        elif isinstance(f, SemanticFilter):
            filters.append(f)

    return SemanticQuery(
        root_object=root_object,
        fields=fields,
        filters=filters,
        order_by=data.get("order_by", []),
        limit=data.get("limit", 100),
        offset=data.get("offset", 0),
        distinct=data.get("distinct", False)
    )


# 导出
__all__ = [
    "SemanticQuery",
    "SemanticFilter",
    "PathSegment",
    "ResolvedPath",
    "FilterOperator",
    "semantic_filter_from_dict",
    "semantic_query_from_dict",
]
