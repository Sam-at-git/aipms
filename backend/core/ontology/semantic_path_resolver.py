"""
core/ontology/semantic_path_resolver.py

SemanticPathResolver - 语义路径解析器

将 LLM 友好的 SemanticQuery 编译为 QueryEngine 可执行的 StructuredQuery。

核心功能：
- 路径编译：dot-notation → JOIN 子句
- 关系推导：根据 RELATIONSHIP_MAP 自动生成 JOIN
- 错误提示：对无效路径提供清晰的错误信息

Example:
    resolver = SemanticPathResolver()

    semantic = SemanticQuery(
        root_object="Guest",
        fields=["name", "stays.room.room_number"],
        filters=[SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")]
    )

    structured = resolver.compile(semantic)
    # structured.joins == [
    #     JoinClause(entity="StayRecord", on="stays"),
    #     JoinClause(entity="Room", on="room")
    # ]
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Set
from difflib import get_close_matches

from core.ontology.semantic_query import (
    SemanticQuery,
    SemanticFilter,
    PathSegment,
    ResolvedPath,
)
from core.ontology.query import (
    StructuredQuery,
    FilterClause,
    JoinClause,
    FilterOperator,
    JoinType,
)
from core.ontology.query_engine import MODEL_MAP, RELATIONSHIP_MAP

logger = logging.getLogger(__name__)

# 最大跳数限制（防止无限递归）
MAX_HOP_DEPTH = 10


@dataclass
class PathResolutionError(Exception):
    """
    路径解析错误（带建议）

    Attributes:
        path: 原始路径
        position: 错误位置（索引）
        token: 导致错误的 token
        current_entity: 当前实体
        suggestions: 建议的关系名
    """
    path: str
    position: int
    token: str
    current_entity: str
    suggestions: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        base = f"Cannot resolve path '{self.path}' at position {self.position}: "
        base += f"'{self.current_entity}' has no relationship '{self.token}'"
        if self.suggestions:
            base += f". Did you mean: {', '.join(self.suggestions)}?"
        return base

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": "PathResolutionError",
            "path": self.path,
            "position": self.position,
            "token": self.token,
            "current_entity": self.current_entity,
            "suggestions": self.suggestions
        }


class SemanticPathResolver:
    """
    语义路径解析器 - 编译器模式

    将 LLM 友好的 SemanticQuery 编译为 QueryEngine 可执行的 StructuredQuery。

    核心方法：
    - compile(): 主编译入口
    - resolve_path(): 解析单条路径为 ResolvedPath
    - _build_joins(): 从路径列表生成 JOIN 子句
    - _compile_filters(): 将 SemanticFilter 转换为 FilterClause

    Example:
        resolver = SemanticPathResolver()

        semantic = SemanticQuery(
            root_object="Guest",
            fields=["name", "stays.room.room_number"],
            filters=[SemanticFilter(path="stays.status", operator="eq", value="ACTIVE")]
        )

        structured = resolver.compile(semantic)
    """

    def __init__(self, registry=None):
        """
        初始化路径解析器

        Args:
            registry: OntologyRegistry 实例（可选，用于动态关系发现）
        """
        self.registry = registry
        self.relationship_map = RELATIONSHIP_MAP
        self.model_map = MODEL_MAP

    def compile(self, semantic_query: SemanticQuery) -> StructuredQuery:
        """
        编译语义查询为结构化查询

        Args:
            semantic_query: LLM 输出的语义查询

        Returns:
            QueryEngine 可执行的 StructuredQuery

        Raises:
            ValueError: 根实体不存在
            PathResolutionError: 路径无法解析（带建议）
        """
        # 1. 验证根实体
        self._validate_root_entity(semantic_query.root_object)

        # 2. 提取所有路径（fields + filters）
        all_paths = self._extract_all_paths(semantic_query)

        # 3. 解析路径并生成 JOIN
        joins = self._build_joins(semantic_query.root_object, all_paths)

        # 4. 编译过滤器
        filters = self._compile_filters(semantic_query.root_object, semantic_query.filters)

        # 5. 编译字段路径（转换为正确的关系属性名）
        fields = self._compile_field_paths(semantic_query.root_object, semantic_query.fields)

        # 6. 编译 order_by 路径
        order_by = self._compile_order_by_paths(semantic_query.root_object, semantic_query.order_by)

        # 7. 返回 StructuredQuery
        return StructuredQuery(
            entity=semantic_query.root_object,
            fields=fields,
            filters=filters,
            joins=joins,
            order_by=order_by,
            limit=semantic_query.limit,
            offset=semantic_query.offset,
            distinct=semantic_query.distinct
        )

    def resolve_path(self, root_entity: str, path: str) -> ResolvedPath:
        """
        解析单条语义路径

        Args:
            root_entity: 根实体名（如 "Guest"）
            path: 点分路径（如 "stays.room.room_number"）

        Returns:
            ResolvedPath 包含路径段、JOIN、最终字段和实体

        Raises:
            PathResolutionError: 路径无法解析

        Example:
            resolve_path("Guest", "stays.room.room_number") → ResolvedPath(
                segments=[
                    PathSegment("stays", "relationship", "StayRecord"),
                    PathSegment("room", "relationship", "Room"),
                    PathSegment("room_number", "field")
                ],
                joins=[...],
                final_field="room_number",
                final_entity="Room"
            )
        """
        tokens = path.split(".")
        if len(tokens) == 1:
            # 简单字段，无需 JOIN
            return ResolvedPath(
                original_path=path,
                segments=[PathSegment(tokens[0], "field")],
                joins=[],
                final_field=tokens[0],
                final_entity=root_entity
            )

        # 多跳路径
        segments = []
        joins = []
        current_entity = root_entity
        visited_entities = {root_entity}  # 防止循环引用

        for i, token in enumerate(tokens[:-1]):  # 除了最后一段（字段名）
            # 检查跳数限制
            if i >= MAX_HOP_DEPTH:
                raise PathResolutionError(
                    path=path,
                    position=i,
                    token=token,
                    current_entity=current_entity,
                    suggestions=[]
                )

            # 查找关系
            target_entity = self._find_relationship(current_entity, token)
            if target_entity is None:
                raise PathResolutionError(
                    path=path,
                    position=i,
                    token=token,
                    current_entity=current_entity,
                    suggestions=self._find_similar_relationships(current_entity, token)
                )

            # 检查循环引用
            if target_entity in visited_entities:
                raise PathResolutionError(
                    path=path,
                    position=i,
                    token=token,
                    current_entity=current_entity,
                    suggestions=[]
                )

            segments.append(PathSegment(token, "relationship", target_entity))

            # 获取关系属性名（用于 JOIN）
            rel_attr = self._get_relationship_attr(current_entity, token)
            joins.append(JoinClause(
                entity=target_entity,
                join_type=JoinType.LEFT,
                on=rel_attr
            ))

            visited_entities.add(target_entity)
            current_entity = target_entity

        # 最后一段是字段
        segments.append(PathSegment(tokens[-1], "field"))

        return ResolvedPath(
            original_path=path,
            segments=segments,
            joins=joins,
            final_field=tokens[-1],
            final_entity=current_entity
        )

    def _find_relationship(self, from_entity: str, relation_name: str) -> Optional[str]:
        """
        查找关系目标实体

        Args:
            from_entity: 源实体名
            relation_name: 关系属性名（如 "stays", "room"）

        Returns:
            目标实体名，如果找不到返回 None

        Example:
            _find_relationship("Guest", "stays") → "StayRecord"
            _find_relationship("StayRecord", "room") → "Room"
        """
        # 从 RELATIONSHIP_MAP 查找
        # RELATIONSHIP_MAP 格式: {"Guest": {"StayRecord": ("stay_records", "guest_id")}}
        # 所以需要遍历查找

        # 首先尝试直接匹配
        entity_rels = self.relationship_map.get(from_entity, {})
        for target_entity, (rel_attr, _) in entity_rels.items():
            # rel_attr 可能是 "stay_records" 或 "room"
            # relation_name 可能是 "stays" 或 "room"
            if rel_attr == relation_name:
                return target_entity

            # 尝试去 s 匹配（stays → stay_records）
            if relation_name.endswith("s"):
                singular = relation_name[:-1]
                if rel_attr == f"{singular}s" or rel_attr == singular:
                    return target_entity
            elif rel_attr.endswith("s"):
                if relation_name == rel_attr[:-1]:
                    return target_entity

        # 尝试反向匹配（relation_name 是目标实体名）
        if relation_name in entity_rels:
            return relation_name

        # 尝试大小写不敏感匹配
        relation_lower = relation_name.lower()
        for target_entity, (rel_attr, _) in entity_rels.items():
            if rel_attr.lower() == relation_lower:
                return target_entity
            if target_entity.lower() == relation_lower:
                return target_entity

        return None

    def _get_relationship_attr(self, from_entity: str, relation_name: str) -> str:
        """
        获取关系属性名（用于 JOIN 的 on 参数）

        Args:
            from_entity: 源实体名
            relation_name: 关系名

        Returns:
            SQLAlchemy 关系属性名
        """
        entity_rels = self.relationship_map.get(from_entity, {})

        # 遍历查找匹配的关系
        for target_entity, (rel_attr, _) in entity_rels.items():
            if rel_attr == relation_name:
                return rel_attr

            # 尝试目标实体匹配
            if target_entity.lower() == relation_name.lower():
                return rel_attr

        # 默认返回原关系名
        return relation_name

    def _find_similar_relationships(
        self,
        from_entity: str,
        relation_name: str,
        n: int = 3
    ) -> List[str]:
        """
        查找相似关系名（用于错误提示）

        Args:
            from_entity: 源实体名
            relation_name: 用户输入的关系名
            n: 返回建议数量

        Returns:
            相似关系名列表
        """
        entity_rels = self.relationship_map.get(from_entity, {})

        # 收集所有可能的关系名
        valid_rels = []
        for target_entity, (rel_attr, _) in entity_rels.items():
            valid_rels.append(rel_attr)
            valid_rels.append(target_entity)

        return get_close_matches(relation_name, valid_rels, n=n, cutoff=0.4)

    def _validate_root_entity(self, root_entity: str) -> None:
        """
        验证根实体存在

        Raises:
            ValueError: 根实体不存在
        """
        all_entities = set(self.model_map.keys()) | set(self.relationship_map.keys())

        if root_entity not in all_entities:
            suggestions = get_close_matches(
                root_entity,
                list(all_entities),
                n=3,
                cutoff=0.4
            )
            raise ValueError(
                f"Unknown root entity: {root_entity}. "
                f"Valid entities: {', '.join(sorted(all_entities))}. "
                f"Did you mean: {', '.join(suggestions)}?"
            )

    def _extract_all_paths(self, semantic_query: SemanticQuery) -> List[str]:
        """
        提取所有路径（从 fields 和 filters）

        Args:
            semantic_query: 语义查询

        Returns:
            去重后的路径列表
        """
        paths = []

        # 从 fields 提取
        for field in semantic_query.fields:
            paths.append(field)

        # 从 filters 提取
        for f in semantic_query.filters:
            paths.append(f.path)

        # 去重
        seen = set()
        unique_paths = []
        for path in paths:
            if path not in seen:
                seen.add(path)
                unique_paths.append(path)

        return unique_paths

    def _build_joins(self, root_entity: str, paths: List[str]) -> List[JoinClause]:
        """
        从路径列表构建 JOIN 子句（去重并排序）

        Args:
            root_entity: 根实体名
            paths: 所有路径列表

        Returns:
            去重后的 JOIN 子句列表（按依赖顺序）
        """
        all_joins = []  # (join_path, join_clause) 元组

        for path in paths:
            try:
                resolved = self.resolve_path(root_entity, path)
                join_path = tuple([s.name for s in resolved.segments if s.is_relationship()])
                for join in resolved.joins:
                    all_joins.append((join_path, join))
            except PathResolutionError:
                # 跳过无效路径，在 compile 阶段统一处理
                pass

        # 去重并排序
        return self._dedupe_and_sort_joins(all_joins)

    def _dedupe_and_sort_joins(
        self,
        all_joins: List[Tuple[Tuple[str, ...], JoinClause]]
    ) -> List[JoinClause]:
        """
        JOIN 去重并按依赖排序

        规则：
        1. 相同 entity + on 的 JOIN 只保留一个
        2. 短路径在前，长路径在后（保证依赖顺序）
        """
        # 去重：使用 (entity, on) 作为键
        seen = {}
        for join_path, join in all_joins:
            key = (join.entity, join.on)
            current_length = len(join_path)

            if key not in seen:
                seen[key] = (current_length, join)
            else:
                # 如果路径更短，保留短的
                if current_length < seen[key][0]:
                    seen[key] = (current_length, join)

        # 按路径长度排序
        sorted_joins = [join for _, join in sorted(seen.values(), key=lambda x: x[0])]
        return sorted_joins

    def _compile_filters(
        self,
        root_entity: str,
        semantic_filters: List[SemanticFilter]
    ) -> List[FilterClause]:
        """
        将 SemanticFilter 编译为 FilterClause

        关键转换：
        - path: "stays.status" → field: "stay_records.status"
        - operator: 保持不变（都是 FilterOperator）
        - value: 保持不变

        Args:
            root_entity: 根实体名
            semantic_filters: 语义过滤器列表

        Returns:
            FilterClause 列表
        """
        filters = []
        for sf in semantic_filters:
            tokens = sf.path.split(".")

            if len(tokens) == 1:
                # 简单字段
                field = tokens[0]
            else:
                # 关联字段：转换为 QueryEngine 可解析的格式
                field = self._convert_path_to_filter_field(root_entity, sf.path)

            filters.append(FilterClause(
                field=field,
                operator=FilterOperator(sf.operator),
                value=sf.value
            ))

        return filters

    def _compile_field_paths(self, root_entity: str, semantic_fields: List[str]) -> List[str]:
        """
        编译字段路径列表，将语义路径转换为 QueryEngine 可解析的路径

        Args:
            root_entity: 根实体名
            semantic_fields: 语义字段路径列表

        Returns:
            转换后的字段路径列表
        """
        return [
            self._convert_path_to_filter_field(root_entity, field)
            for field in semantic_fields
        ]

    def _compile_order_by_paths(self, root_entity: str, order_by: List[str]) -> List[str]:
        """
        编译 order_by 路径列表

        Args:
            root_entity: 根实体名
            order_by: 排序路径列表

        Returns:
            转换后的排序路径列表
        """
        return [
            self._convert_path_to_filter_field(root_entity, field)
            for field in order_by
        ]

    def _convert_path_to_filter_field(self, root_entity: str, semantic_path: str) -> str:
        """
        将语义路径转换为 FilterClause 可用的字段路径

        规则：
        - "status" → "status"
        - "stays.status" → "stay_records.status"（使用 RELATIONSHIP_MAP）
        - "stays.room.status" → "stay_records.room.status"

        Args:
            root_entity: 根实体名
            semantic_path: 语义路径

        Returns:
            QueryEngine 可解析的字段路径
        """
        tokens = semantic_path.split(".")
        if len(tokens) == 1:
            return tokens[0]

        result = []
        current_entity = root_entity

        # 处理关系路径
        for i, token in enumerate(tokens[:-1]):
            # 查找关系属性名
            rel_attr = self._get_relationship_attr(current_entity, token)
            result.append(rel_attr)

            # 更新当前实体
            target_entity = self._find_relationship(current_entity, token)
            if target_entity:
                current_entity = target_entity

        # 最后是字段名
        result.append(tokens[-1])

        return ".".join(result)

    def suggest_paths(self, entity: str, max_depth: int = 3) -> List[str]:
        """
        为给定实体建议可用的路径

        Args:
            entity: 实体名
            max_depth: 最大路径深度

        Returns:
            可用路径列表

        Example:
            suggest_paths("Guest") → [
                "Guest.name",
                "Guest.stays.status",
                "Guest.stays.room.room_number"
            ]
        """
        suggestions = []

        # 获取实体关系
        entity_rels = self.relationship_map.get(entity, {})

        # 添加直接字段（简单示例）
        # 实际应用中需要从模型元数据获取
        common_fields = ["id", "name", "status", "created_at"]
        for field in common_fields:
            suggestions.append(f"{entity}.{field}")

        # 添加关系路径
        for target_entity, (rel_attr, _) in entity_rels.items():
            suggestions.append(f"{entity}.{rel_attr}")

            # 二跳路径
            if max_depth >= 2:
                nested_rels = self.relationship_map.get(target_entity, {})
                for nested_target, (nested_attr, _) in nested_rels.items():
                    suggestions.append(f"{entity}.{rel_attr}.{nested_attr}")

                    # 三跳路径
                    if max_depth >= 3:
                        third_rels = self.relationship_map.get(nested_target, {})
                        for third_target, (third_attr, _) in third_rels.items():
                            suggestions.append(f"{entity}.{rel_attr}.{nested_attr}.{third_attr}")

        return suggestions


# 导出
__all__ = [
    "SemanticPathResolver",
    "PathResolutionError",
]
