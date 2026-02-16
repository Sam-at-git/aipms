"""
core/ontology/query.py

Ontology 结构化查询数据结构

用于 NL2OntologyQuery：
- LLM 将自然语言解析为 StructuredQuery
- QueryEngine 执行 StructuredQuery 并返回结果
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from enum import Enum


class FilterOperator(str, Enum):
    """过滤操作符"""
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


class JoinType(str, Enum):
    """关联类型"""
    INNER = "inner"
    LEFT = "left"
    OUTER = "outer"


@dataclass
class FilterClause:
    """
    过滤条件子句

    Examples:
        FilterClause(field="status", operator=FilterOperator.EQ, value="ACTIVE")
        FilterClause(field="check_in_date", operator=FilterOperator.GTE, value="2026-02-01")
        FilterClause(field="price", operator=FilterOperator.BETWEEN, value=["100", "500"])
    """
    field: str                       # 字段路径，如 "stay_records.status" 或 "room_number"
    operator: FilterOperator = FilterOperator.EQ
    value: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "operator": self.operator.value,
            "value": self.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilterClause":
        return cls(
            field=data["field"],
            operator=FilterOperator(data.get("operator", "eq")),
            value=data.get("value")
        )


@dataclass
class JoinClause:
    """
    关联查询子句

    Examples:
        JoinClause(entity="StayRecord", filters={"status": "ACTIVE"})
        JoinClause(entity="Room", join_type=JoinType.LEFT)
    """
    entity: str                      # 关联的实体名
    join_type: JoinType = JoinType.INNER
    on: Optional[str] = None         # ON 条件，通常自动推导
    filters: Dict[str, Any] = field(default_factory=dict)  # 关联表的过滤条件
    fields: Optional[List[str]] = None  # 要从关联表获取的字段

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "join_type": self.join_type.value,
            "on": self.on,
            "filters": self.filters,
            "fields": self.fields
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JoinClause":
        return cls(
            entity=data["entity"],
            join_type=JoinType(data.get("join_type", "inner")),
            on=data.get("on"),
            filters=data.get("filters", {}),
            fields=data.get("fields")
        )


@dataclass
class AggregateClause:
    """
    聚合查询子句

    Examples:
        AggregateClause(field="price", function="AVG")
        AggregateClause(field="id", function="COUNT")
        AggregateClause(field="*", function="COUNT", alias="total")

    支持的聚合函数:
        - COUNT: 计数
        - SUM: 求和
        - AVG: 平均值
        - MAX: 最大值
        - MIN: 最小值
    """
    field: str
    function: str  # COUNT, SUM, AVG, MAX, MIN
    alias: Optional[str] = None
    group_by: Optional[List[str]] = None  # GROUP BY 字段列表

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "function": self.function,
            "alias": self.alias,
            "group_by": self.group_by
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AggregateClause":
        return cls(
            field=data["field"],
            function=data["function"],
            alias=data.get("alias"),
            group_by=data.get("group_by")
        )


@dataclass
class StructuredQuery:
    """
    结构化查询 - NL2OntologyQuery 的核心数据结构

    由 LLM 解析自然语言生成，由 QueryEngine 执行。

    Examples:
        # 简单查询: "所有客人姓名"
        StructuredQuery(entity="Guest", fields=["name"])

        # 带过滤: "201房间的类型和状态"
        StructuredQuery(
            entity="Room",
            fields=["room_type", "status"],
            filters=[FilterClause(field="room_number", operator=FilterOperator.EQ, value="201")]
        )

        # 关联查询: "所有在住的客人姓名"
        StructuredQuery(
            entity="Guest",
            fields=["name"],
            joins=[JoinClause(entity="StayRecord", filters={"status": "ACTIVE"})]
        )

        # 复杂查询: "本周入住的客人姓名和房间号"
        StructuredQuery(
            entity="Guest",
            fields=["name"],
            joins=[JoinClause(
                entity="StayRecord",
                filters={"check_in_date": ("gte", "2026-02-01"), ("lte", "2026-02-07")},
                fields=["room_number"]
            )]
        )
    """
    entity: str                       # 目标实体名 (如 "Guest", "Room")
    fields: List[str]                 # 要返回的字段 ["name", "phone"]
    filters: List[FilterClause] = field(default_factory=list)
    joins: List[JoinClause] = field(default_factory=list)
    order_by: List[str] = field(default_factory=list)  # ["name DESC", "check_in_date ASC"]
    limit: int = 100
    offset: int = 0
    distinct: bool = False
    aggregate: Optional[AggregateClause] = None  # 聚合查询
    group_by: Optional[List[str]] = None  # GROUP BY 字段列表（简写形式）

    def __post_init__(self):
        """处理 aggregate 字段，支持字典输入"""
        if self.aggregate is not None and isinstance(self.aggregate, dict):
            self.aggregate = AggregateClause.from_dict(self.aggregate)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 JSON 序列化"""
        return {
            "entity": self.entity,
            "fields": self.fields,
            "filters": [f.to_dict() for f in self.filters],
            "joins": [j.to_dict() for j in self.joins],
            "order_by": self.order_by,
            "limit": self.limit,
            "offset": self.offset,
            "distinct": self.distinct,
            "aggregate": self.aggregate.to_dict() if self.aggregate else None,
            "group_by": self.group_by
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredQuery":
        """从字典创建实例"""
        filters = [FilterClause.from_dict(f) for f in data.get("filters", [])]
        joins = [JoinClause.from_dict(j) for j in data.get("joins", [])]

        aggregate_data = data.get("aggregate")
        aggregate = AggregateClause.from_dict(aggregate_data) if aggregate_data else None

        return cls(
            entity=data["entity"],
            fields=data.get("fields", []),
            filters=filters,
            joins=joins,
            order_by=data.get("order_by", []),
            limit=data.get("limit", 100),
            offset=data.get("offset", 0),
            distinct=data.get("distinct", False),
            aggregate=aggregate,
            group_by=data.get("group_by")
        )

    def is_simple(self) -> bool:
        """判断是否为简单查询（可用 Service 优化）"""
        return (
            not self.joins and
            len(self.filters) <= 1 and
            len(self.fields) <= 3 and
            not self.aggregate
        )



# 导出
__all__ = [
    "StructuredQuery",
    "FilterClause",
    "FilterOperator",
    "JoinClause",
    "JoinType",
    "AggregateClause",
]
