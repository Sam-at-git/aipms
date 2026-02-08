"""
app/services/actions/query_actions.py

Query-related action handlers using ActionRegistry.

SPEC-15: 语义查询编译器集成
- 新增 semantic_query 动作
- 集成 SemanticPathResolver 和 QueryEngine
- LLM 友好的点分路径查询
"""
from typing import Dict, Any, List, Optional, Union
from sqlalchemy.orm import Session

from core.ai.actions import ActionRegistry
from app.models.ontology import Employee
from app.services.actions.base import (
    OntologyQueryParams,
    FilterClauseParams,
    JoinClauseParams,
    SemanticQueryParams,
    SemanticFilterParams,
)
from app.services.param_parser_service import ParamParserService

import logging

logger = logging.getLogger(__name__)


def _convert_filter_params(filters: Optional[List[FilterClauseParams]]) -> List[dict]:
    """Convert FilterClauseParams to dicts for QueryEngine."""
    if not filters:
        return []
    return [
        {
            "field": f.field,
            "operator": f.operator,
            "value": f.value
        }
        for f in filters
    ]


def _convert_join_params(joins: Optional[List[JoinClauseParams]]) -> List[dict]:
    """Convert JoinClauseParams to dicts for QueryEngine."""
    if not joins:
        return []
    return [
        {
            "entity": j.entity,
            "on": j.on
        }
        for j in joins
    ]


def register_query_actions(
    registry: ActionRegistry
) -> None:
    """
    Register all query-related actions.

    Args:
        registry: The ActionRegistry instance to register actions with
    """

    @registry.register(
        name="ontology_query",
        entity="Query",
        description="执行动态本体查询。支持字段选择、过滤条件、JOIN 连接、排序和聚合。可查询任意实体及其关联数据。",
        category="query",
        requires_confirmation=False,
        allowed_roles=set(),  # All roles can query
        undoable=False,
        side_effects=[],
        search_keywords=["查询", "搜索", "数据", "列表", "query", "search", "list"]
    )
    def handle_ontology_query(
        params: OntologyQueryParams,
        db: Session,
        user: Employee,
        param_parser: Optional[ParamParserService] = None
    ) -> Dict[str, Any]:
        """
        Execute ontology query.

        This handler:
        1. Validates the entity exists
        2. Validates field names
        3. Converts filters and joins
        4. Executes the query via QueryEngine
        5. Returns formatted results

        Args:
            params: Validated ontology query parameters
            db: Database session
            user: Current user (employee)

        Returns:
            Result dict with query_result containing table data
        """
        from core.ontology.query import (
            StructuredQuery,
            FilterClause,
            JoinClause,
            FilterOperator,
            JoinType
        )
        from core.ontology.query_engine import QueryEngine
        from core.ontology.registry import registry as ontology_registry

        try:
            # Validate entity exists
            entity_metadata = ontology_registry.get_entity(params.entity)
            if not entity_metadata:
                available = ", ".join(e.name for e in ontology_registry.get_entities())
                return {
                    "success": False,
                    "message": f"未知的实体: {params.entity}。可用实体: {available}",
                    "error": "unknown_entity"
                }

            # Build filter clauses
            filter_clauses = []
            if params.filters:
                for f in params.filters:
                    try:
                        operator = FilterOperator(f.operator)
                    except ValueError:
                        # Default to eq if invalid
                        operator = FilterOperator.EQ

                    filter_clauses.append(
                        FilterClause(
                            field=f.field,
                            operator=operator,
                            value=f.value
                        )
                    )

            # Build join clauses
            join_clauses = []
            if params.joins:
                for j in params.joins:
                    join_clauses.append(
                        JoinClause(
                            entity=j.entity,
                            join_type=JoinType.LEFT,
                            on=j.on
                        )
                    )

            # Handle aggregates
            aggregates = []
            if params.aggregates:
                for agg in params.aggregates:
                    aggregates.append({
                        "function": agg.get("function", "count"),
                        "field": agg.get("field", ""),
                        "alias": agg.get("alias", "")
                    })

            # Create structured query
            structured_query = StructuredQuery(
                entity=params.entity,
                fields=params.fields or list(entity_metadata.properties.keys()),
                filters=filter_clauses,
                joins=join_clauses,
                order_by=params.order_by or [],
                limit=params.limit,
                aggregates=aggregates
            )

            # Execute query
            engine = QueryEngine(db, ontology_registry)
            result = engine.execute(structured_query, user)

            # Format response
            return {
                "success": True,
                "message": result.get("summary", f"共 {len(result.get('rows', []))} 条记录"),
                "query_result": result
            }

        except ValueError as e:
            logger.error(f"Validation error in ontology_query: {e}")
            return {
                "success": False,
                "message": f"查询参数错误: {str(e)}",
                "error": "validation_error"
            }
        except Exception as e:
            logger.error(f"Error in ontology_query: {e}")
            return {
                "success": False,
                "message": f"查询失败: {str(e)}",
                "error": "execution_error"
            }

    @registry.register(
        name="semantic_query",
        entity="Query",
        description=(
            "执行语义查询。使用点分路径（如 Guest.stays.room_number）查询关联数据，"
            "自动生成 JOIN。支持多跳导航（如 Guest.stays.room.room_type.name）。"
        ),
        category="query",
        requires_confirmation=False,
        allowed_roles=set(),  # All roles can query
        undoable=False,
        side_effects=[],
        search_keywords=[
            "查询", "搜索", "数据", "列表", "语义", "关联",
            "query", "search", "list", "semantic", "relation"
        ]
    )
    def handle_semantic_query(
        params: SemanticQueryParams,
        db: Session,
        user: Employee
    ) -> Dict[str, Any]:
        """
        执行语义查询

        SPEC-15: 语义查询编译器集成

        流程：
        1. 接收 SemanticQuery (from LLM)
        2. 创建 SemanticPathResolver
        3. 编译: SemanticQuery → StructuredQuery
        4. 执行: QueryEngine.execute(StructuredQuery)
        5. 格式化: 返回 query_result

        Args:
            params: 语义查询参数（LLM 友好）
            db: 数据库会话
            user: 当前用户

        Returns:
            结果字典，包含 query_result 表格数据

        Example:
            LLM 输入:
            {
                "root_object": "Guest",
                "fields": ["name", "stays.room_number"],
                "filters": [{"path": "stays.status", "operator": "eq", "value": "ACTIVE"}]
            }

            编译为:
            StructuredQuery(
                entity="Guest",
                fields=["name", "stay_records.room_number"],
                joins=[JoinClause(entity="StayRecord", on="stay_records")],
                filters=[FilterClause(field="stay_records.status", operator=eq, value="ACTIVE")]
            )
        """
        from core.ontology.semantic_query import (
            SemanticQuery,
            SemanticFilter,
        )
        from core.ontology.semantic_path_resolver import (
            SemanticPathResolver,
            PathResolutionError,
        )
        from core.ontology.query_engine import QueryEngine
        from core.ontology.registry import registry as ontology_registry

        try:
            # 1. 构建 SemanticQuery
            filters = [
                SemanticFilter(
                    path=f.path,
                    operator=f.operator,
                    value=f.value
                )
                for f in params.filters
            ]

            semantic_query = SemanticQuery(
                root_object=params.root_object,
                fields=params.fields,
                filters=filters,
                order_by=params.order_by,
                limit=params.limit,
                offset=params.offset,
                distinct=params.distinct
            )

            # 验证语义查询
            validation_errors = semantic_query.validate()
            if validation_errors:
                return {
                    "success": False,
                    "message": f"查询验证失败: {', '.join(validation_errors)}",
                    "error": "validation_error",
                    "details": {"errors": validation_errors}
                }

            # 2. 创建解析器并编译
            resolver = SemanticPathResolver(ontology_registry)

            try:
                structured_query = resolver.compile(semantic_query)
            except PathResolutionError as e:
                # 路径解析错误 - 返回友好的错误信息
                return {
                    "success": False,
                    "message": str(e),
                    "error": "path_resolution_error",
                    "details": e.to_dict()
                }
            except ValueError as e:
                # 实体不存在等错误
                return {
                    "success": False,
                    "message": f"查询编译错误: {str(e)}",
                    "error": "compilation_error"
                }

            # 3. 执行查询
            engine = QueryEngine(db, ontology_registry)
            result = engine.execute(structured_query, user)

            # 4. 返回结果
            return {
                "success": True,
                "message": result.get("summary", f"共 {len(result.get('rows', []))} 条记录"),
                "query_result": result
            }

        except ValueError as e:
            logger.error(f"Validation error in semantic_query: {e}")
            return {
                "success": False,
                "message": f"查询参数错误: {str(e)}",
                "error": "validation_error"
            }
        except Exception as e:
            logger.error(f"Error in semantic_query: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"查询失败: {str(e)}",
                "error": "execution_error"
            }


__all__ = ["register_query_actions"]
