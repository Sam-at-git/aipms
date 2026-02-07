"""
core/ontology/query_engine.py

Ontology 查询引擎 - 动态构建并执行 SQLAlchemy 查询

特性：
- 基于 StructuredQuery 动态构建查询
- 支持关联查询 (JOIN)
- 支持复杂过滤条件
- 字段级结果映射
- 无硬编码实体逻辑
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Any, Dict, Optional, Type
from sqlalchemy import and_, or_, not_, func, case, literal_column
from sqlalchemy.orm import Session, joinedload, lazyload
from sqlalchemy.sql.elements import BinaryExpression

from core.ontology.query import (
    StructuredQuery, FilterClause, JoinClause, FilterOperator, JoinType
)
from core.ontology.registry import OntologyRegistry

logger = logging.getLogger(__name__)


# ORM 模型映射
MODEL_MAP = {
    "Room": None,  # 延迟导入
    "Guest": None,
    "Reservation": None,
    "StayRecord": None,
    "Bill": None,
    "Task": None,
    "Employee": None,
    "RoomType": None,
    "RatePlan": None,
    "Payment": None,
}

# 实体关系映射（用于自动推导 JOIN 条件）
RELATIONSHIP_MAP = {
    "Guest": {
        "StayRecord": ("stay_records", "guest_id"),
        "Reservation": ("reservations", "guest_id"),
    },
    "Room": {
        "StayRecord": ("stay_records", "room_id"),
        "Task": ("tasks", "room_id"),
        "RoomType": ("room_type", "room_type_id"),
    },
    "StayRecord": {
        "Guest": ("guest", "guest_id"),
        "Room": ("room", "room_id"),
        "Reservation": ("reservation", "reservation_id"),
        "Bill": ("bills", "stay_record_id"),
    },
    "Reservation": {
        "Guest": ("guest", "guest_id"),
        "RoomType": ("room_type", "room_type_id"),
        "StayRecord": ("stay_records", "reservation_id"),
    },
    "Bill": {
        "StayRecord": ("stay_record", "stay_record_id"),
        "Payment": ("payments", "bill_id"),
    },
    "Task": {
        "Room": ("room", "room_id"),
        "Employee": ("assignee", "assignee_id"),
    },
    "Employee": {
        "Task": ("tasks", "assignee_id"),
    },
    "RoomType": {
        "Room": ("rooms", "id"),
        "RatePlan": ("rate_plans", "room_type_id"),
    },
}

# 字段显示名映射
DISPLAY_NAMES = {
    "name": "姓名",
    "phone": "电话",
    "room_number": "房号",
    "room_type": "房型",
    "status": "状态",
    "floor": "楼层",
    "check_in_date": "入住日期",
    "check_out_date": "退房日期",
    "task_type": "任务类型",
    "reservation_no": "预订号",
    "total_amount": "总金额",
    "is_settled": "已结清",
}


def get_model_class(entity_name: str) -> Type:
    """获取 ORM 模型类（延迟导入避免循环依赖）"""
    if MODEL_MAP[entity_name] is None:
        if entity_name == "Room":
            from app.models.ontology import Room
            MODEL_MAP["Room"] = Room
        elif entity_name == "Guest":
            from app.models.ontology import Guest
            MODEL_MAP["Guest"] = Guest
        elif entity_name == "Reservation":
            from app.models.ontology import Reservation
            MODEL_MAP["Reservation"] = Reservation
        elif entity_name == "StayRecord":
            from app.models.ontology import StayRecord
            MODEL_MAP["StayRecord"] = StayRecord
        elif entity_name == "Bill":
            from app.models.ontology import Bill
            MODEL_MAP["Bill"] = Bill
        elif entity_name == "Task":
            from app.models.ontology import Task
            MODEL_MAP["Task"] = Task
        elif entity_name == "Employee":
            from app.models.ontology import Employee
            MODEL_MAP["Employee"] = Employee
        elif entity_name == "RoomType":
            from app.models.ontology import RoomType
            MODEL_MAP["RoomType"] = RoomType
        elif entity_name == "RatePlan":
            from app.models.ontology import RatePlan
            MODEL_MAP["RatePlan"] = RatePlan
        elif entity_name == "Payment":
            from app.models.ontology import Payment
            MODEL_MAP["Payment"] = Payment
        else:
            raise ValueError(f"Unknown entity: {entity_name}")
    return MODEL_MAP[entity_name]


class QueryEngine:
    """
    Ontology 查询引擎

    将 StructuredQuery 转换为 SQLAlchemy 查询并执行，
    返回前端可用的表格数据。

    特性：
    - 无硬编码实体逻辑
    - 支持动态字段选择
    - 支持关联查询
    - 支持复杂过滤条件
    """

    def __init__(self, db: Session, registry: Optional[OntologyRegistry] = None):
        self.db = db
        self.registry = registry

    def execute(self, query: StructuredQuery, user=None) -> Dict[str, Any]:
        """
        执行结构化查询

        Args:
            query: StructuredQuery 实例
            user: 当前用户（用于权限过滤）

        Returns:
            {
                "display_type": "table",
                "columns": ["姓名", "房间"],
                "column_keys": ["name", "room_number"],
                "rows": [{"name": "张三", "room_number": "201"}],
                "summary": "共 2 条记录"
            }
        """
        try:
            # 检查是否为聚合查询
            if query.aggregate or query.group_by:
                return self._execute_aggregate_query(model_class=get_model_class(query.entity), query=query)

            # 1. 获取 ORM 模型类
            model_class = get_model_class(query.entity)

            # 2. 构建 SQLAlchemy Query
            db_query = self._build_query(model_class, query)

            # 3. 执行查询
            results = db_query.limit(query.limit).offset(query.offset).all()

            # 4. 映射结果
            rows = self._map_results(results, query)

            # 5. 构建列名
            columns = self._get_column_names(query)

            return {
                "display_type": "table",
                "columns": columns,
                "column_keys": query.fields,
                "rows": rows,
                "summary": f"共 {len(results)} 条记录"
            }

        except Exception as e:
            logger.error(f"Query execution failed: {e}", exc_info=True)
            return {
                "display_type": "text",
                "message": f"查询执行失败: {str(e)}",
                "rows": [],
                "summary": "查询失败"
            }

    def _build_query(self, model_class: Type, query: StructuredQuery):
        """构建 SQLAlchemy Query"""
        q = self.db.query(model_class)

        # 处理 DISTINCT
        if query.distinct:
            q = q.distinct()

        # 处理 JOIN
        for join_clause in query.joins:
            q = self._apply_join(q, model_class, join_clause)

        # 处理 WHERE 条件
        if query.filters:
            conditions = [self._parse_filter(model_class, f) for f in query.filters]
            if conditions:
                q = q.filter(and_(*conditions))

        # 处理 ORDER BY
        for order_expr in query.order_by:
            q = self._apply_order_by(q, model_class, order_expr)

        return q

    def _apply_join(self, query, base_model: Type, join_clause: JoinClause):
        """应用 JOIN 子句"""
        try:
            related_model = get_model_class(join_clause.entity)

            # 获取关系属性名
            rel_info = RELATIONSHIP_MAP.get(base_model.__name__, {}).get(join_clause.entity)
            if rel_info:
                rel_attr, _ = rel_info
            else:
                # 尝试反向查找
                rel_info = RELATIONSHIP_MAP.get(join_clause.entity, {}).get(base_model.__name__)
                if rel_info:
                    rel_attr = rel_info[0] + "s"  # 反向关系通常是复数
                else:
                    # 使用小写的实体名作为默认
                    rel_attr = join_clause.entity.lower()

            # 应用 JOIN
            if join_clause.join_type == JoinType.LEFT:
                query = query.outerjoin(related_model)
            else:
                query = query.join(related_model)

            # 应用关联表的过滤条件
            if join_clause.filters:
                for field, value in join_clause.filters.items():
                    if isinstance(value, (list, tuple)) and len(value) == 2:
                        op, val = value
                        filter_obj = FilterClause(field=f"{rel_attr}.{field}", operator=FilterOperator(op), value=val)
                    else:
                        filter_obj = FilterClause(field=f"{rel_attr}.{field}", operator=FilterOperator.EQ, value=value)
                    condition = self._parse_filter(base_model, filter_obj)
                    if condition is not None:
                        query = query.filter(condition)

        except Exception as e:
            logger.warning(f"Join failed for {join_clause.entity}: {e}")

        return query

    def _parse_filter(self, model_class: Type, filter_clause: FilterClause) -> Optional[BinaryExpression]:
        """
        解析过滤条件为 SQLAlchemy 表达式

        支持字段路径：
        - "status" → 直接属性比较
        - "stay_records.status" → 使用 relationship.any() 或 has() 进行过滤
        - "room_type.name" → 使用 relationship.has() 进行过滤
        """
        field_path = filter_clause.field
        operator = filter_clause.operator
        value = self._parse_value(filter_clause.value)

        # 解析字段路径
        parts = field_path.split(".")

        # 简单字段 (无点号)
        if len(parts) == 1:
            attr = getattr(model_class, parts[0], None)
            if attr is None:
                logger.warning(f"Field not found: {field_path}")
                return None
            return self._apply_operator(attr, operator, value)

        # 嵌套字段 (如 stay_records.status, room_type.name)
        rel_name = parts[0]  # 关系属性名
        target_field = parts[-1]  # 目标字段名

        # 获取关系属性
        rel_attr = getattr(model_class, rel_name, None)
        if rel_attr is None:
            logger.warning(f"Relationship not found: {rel_name}")
            return None

        # 检查关系的类型（一对多用 any()，一对多用 has()）
        # 通过检查关系的 uselist 属性来判断
        try:
            is_collection = rel_attr.property.uselist
        except (AttributeError, NotImplementedError):
            # 如果无法判断，尝试通过导入检查
            is_collection = None

        # 构建过滤条件
        if is_collection is True:
            # 一对多关系：使用 any()
            if operator == FilterOperator.EQ:
                return rel_attr.any(**{target_field: value})
            elif operator == FilterOperator.NE:
                return ~rel_attr.any(**{target_field: value})
            elif operator == FilterOperator.IN:
                return rel_attr.any(**{f"{target_field}__in": value})
            elif operator == FilterOperator.LIKE:
                # 对于 LIKE，需要使用 and_ 组合条件
                from sqlalchemy import and_
                return rel_attr.any(and_(
                    getattr(rel_attr.property.mapper.class_, target_field).like(f"%{value}%")
                ))
            else:
                # 其他操作符，尝试构建条件
                related_model = rel_attr.property.mapper.class_
                related_attr = getattr(related_model, target_field, None)
                if related_attr is not None:
                    return rel_attr.any(self._apply_operator(related_attr, operator, value))
                else:
                    logger.warning(f"Field not found in related model: {target_field}")
                    return None

        elif is_collection is False:
            # 多对一或一对一关系：使用 has()
            if operator == FilterOperator.EQ:
                return rel_attr.has(**{target_field: value})
            elif operator == FilterOperator.NE:
                return ~rel_attr.has(**{target_field: value})
            elif operator == FilterOperator.LIKE:
                from sqlalchemy import and_
                related_model = rel_attr.property.mapper.class_
                related_attr = getattr(related_model, target_field, None)
                if related_attr is not None:
                    return rel_attr.has(related_attr.like(f"%{value}%"))
                return None
            else:
                # 其他操作符
                related_model = rel_attr.property.mapper.class_
                related_attr = getattr(related_model, target_field, None)
                if related_attr is not None:
                    return rel_attr.has(self._apply_operator(related_attr, operator, value))
                else:
                    logger.warning(f"Field not found in related model: {target_field}")
                    return None

        else:
            # 无法确定关系类型，使用通用方法
            # 尝试通过 has() 处理
            try:
                related_model = rel_attr.property.mapper.class_
                related_attr = getattr(related_model, target_field, None)
                if related_attr is not None:
                    return rel_attr.has(**{target_field: value})
            except (AttributeError, TypeError):
                logger.warning(f"Cannot build filter for nested field: {field_path}")
                return None

        return None

    def _apply_operator(self, attr, operator: FilterOperator, value: Any) -> BinaryExpression:
        """应用操作符"""
        if operator == FilterOperator.EQ:
            return attr == value
        elif operator == FilterOperator.NE:
            return attr != value
        elif operator == FilterOperator.GT:
            return attr > value
        elif operator == FilterOperator.GTE:
            return attr >= value
        elif operator == FilterOperator.LT:
            return attr < value
        elif operator == FilterOperator.LTE:
            return attr <= value
        elif operator == FilterOperator.IN:
            return attr.in_(value if isinstance(value, list) else [value])
        elif operator == FilterOperator.NOT_IN:
            return attr.notin_(value if isinstance(value, list) else [value])
        elif operator == FilterOperator.LIKE:
            return attr.like(f"%{value}%")
        elif operator == FilterOperator.NOT_LIKE:
            return attr.notlike(f"%{value}%")
        elif operator == FilterOperator.BETWEEN:
            if isinstance(value, list) and len(value) == 2:
                return attr.between(value[0], value[1])
            return attr.between(value, value)
        elif operator == FilterOperator.IS_NULL:
            return attr.is_(None)
        elif operator == FilterOperator.IS_NOT_NULL:
            return attr.isnot(None)
        else:
            return attr == value

    def _parse_value(self, value: Any) -> Any:
        """解析特殊值"""
        if isinstance(value, str):
            # 处理特殊日期值
            lower_val = value.lower()
            if lower_val == "today":
                return date.today()
            elif lower_val == "tomorrow":
                return date.today() + timedelta(days=1)
            elif lower_val == "yesterday":
                return date.today() - timedelta(days=1)
            # 尝试解析日期
            try:
                return datetime.fromisoformat(value).date()
            except (ValueError, TypeError):
                pass
        return value

    def _apply_order_by(self, query, model_class: Type, order_expr: str):
        """应用排序"""
        parts = order_expr.split()
        if len(parts) < 1:
            return query

        field = parts[0]
        direction = parts[1].upper() if len(parts) > 1 else "ASC"

        # 解析字段路径
        field_parts = field.split(".")
        attr = model_class
        for part in field_parts:
            attr = getattr(attr, part, None)
            if attr is None:
                return query

        if direction == "DESC":
            return query.order_by(attr.desc())
        return query.order_by(attr.asc())

    def _map_results(self, results: List[Any], query: StructuredQuery) -> List[Dict[str, Any]]:
        """将 ORM 对象映射为字典，只提取指定的字段"""
        rows = []
        for obj in results:
            row = {}
            for field in query.fields:
                # 处理嵌套字段 "stay_records.room_number"
                value = self._get_field_value(obj, field)
                # 格式化值
                row[field] = self._format_value(value)
            rows.append(row)
        return rows

    def _get_field_value(self, obj: Any, field_path: str) -> Any:
        """获取对象字段值，支持嵌套路径"""
        parts = field_path.split(".")
        current = obj

        for part in parts:
            if current is None:
                return None

            # 处理关系属性
            if hasattr(current, part):
                current = getattr(current, part)
                # 如果是 ORM 关系对象且有 __table__ 属性，说明是模型实例
                if hasattr(current, "__table__"):
                    # 继续获取下一级属性
                    continue
            else:
                return None

        # 如果最终是模型实例，尝试获取其字符串表示
        if hasattr(current, "__table__"):
            return str(current)

        return current

    def _format_value(self, value: Any) -> Any:
        """格式化值用于显示"""
        if value is None:
            return ""
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        if hasattr(value, "value"):  # Enum
            return value.value
        if hasattr(value, "name"):  # 关联对象
            return value.name
        return value

    def _get_column_names(self, query: StructuredQuery) -> List[str]:
        """获取列显示名"""
        columns = []
        for field in query.fields:
            # 使用预定义的显示名
            display_name = DISPLAY_NAMES.get(field, field)
            # 如果是嵌套字段，只显示最后一部分的显示名
            if "." in field:
                last_part = field.split(".")[-1]
                display_name = DISPLAY_NAMES.get(last_part, last_part)
            columns.append(display_name)
        return columns

    def _execute_aggregate_query(self, model_class: Type, query: StructuredQuery) -> Dict[str, Any]:
        """
        执行聚合查询

        支持 GROUP BY、COUNT、SUM、AVG、MAX、MIN 等聚合操作
        支持嵌套字段（如 guest.name）
        """
        try:
            # 构建基础查询
            base_query = self.db.query(model_class)

            # 处理 JOIN
            for join_clause in query.joins:
                base_query = self._apply_join(base_query, model_class, join_clause)

            # 处理 WHERE 条件
            if query.filters:
                conditions = [self._parse_filter(model_class, f) for f in query.filters]
                if conditions:
                    base_query = base_query.filter(and_(*conditions))

            # 解析 fields 来确定需要哪些字段
            # fields 可能包含: ["guest.name", "stay_count"]
            # 其中 "stay_count" 是聚合别名，"guest.name" 需要从关联表获取
            select_columns = []
            column_labels = []
            group_by_expressions = []

            # 跟踪已 JOIN 的表
            joined_models = {}

            for field in query.fields:
                # 跳过聚合字段（这些会单独处理）
                if query.aggregate and query.aggregate.alias and field == query.aggregate.alias:
                    continue

                # 解析字段路径
                parts = field.split(".")

                if len(parts) > 1:
                    # 嵌套字段 (如 guest.name)
                    # 需要添加 JOIN
                    rel_name = parts[0]
                    target_field = parts[-1]

                    # 检查是否已经 JOIN
                    if rel_name not in joined_models:
                        rel_attr = getattr(model_class, rel_name, None)
                        if rel_attr is not None:
                            # 获取关联的模型类
                            try:
                                related_model = rel_attr.property.mapper.class_
                                base_query = base_query.join(related_model)
                                joined_models[rel_name] = (related_model, rel_attr)
                            except (AttributeError, NotImplementedError):
                                pass

                    # 获取最终字段
                    if rel_name in joined_models:
                        related_model, rel_attr = joined_models[rel_name]
                        target_attr = getattr(related_model, target_field, None)
                        if target_attr is not None:
                            label = field.replace(".", "_")
                            select_columns.append(target_attr.label(label))
                            column_labels.append((label, field))
                            group_by_expressions.append(target_attr)
                else:
                    # 简单字段
                    if query.group_by and field in query.group_by:
                        attr = getattr(model_class, field, None)
                        if attr is not None:
                            label = field
                            select_columns.append(attr.label(label))
                            column_labels.append((label, field))
                            group_by_expressions.append(attr)

            # 添加聚合字段
            if query.aggregate:
                agg_field = query.aggregate.field
                agg_func = query.aggregate.function.lower()
                agg_alias = query.aggregate.alias or f"{agg_field}_{agg_func}"

                # 解析聚合字段路径
                parts = agg_field.split(".")
                attr = model_class
                for part in parts:
                    attr = getattr(attr, part, None)
                    if attr is None:
                        break

                if attr is not None:
                    if agg_func == "count":
                        if agg_field == "*":
                            agg_expr = func.count().label(agg_alias)
                        else:
                            agg_expr = func.count(attr).label(agg_alias)
                    elif agg_func == "sum":
                        agg_expr = func.sum(attr).label(agg_alias)
                    elif agg_func == "avg":
                        agg_expr = func.avg(attr).label(agg_alias)
                    elif agg_func == "max":
                        agg_expr = func.max(attr).label(agg_alias)
                    elif agg_func == "min":
                        agg_expr = func.min(attr).label(agg_alias)
                    else:
                        agg_expr = func.count(attr).label(agg_alias)

                    select_columns.append(agg_expr)
                    column_labels.append((agg_alias, agg_alias))

            # 构建聚合查询
            if group_by_expressions:
                # 有 GROUP BY
                aggregate_query = base_query.with_entities(*select_columns)
                aggregate_query = aggregate_query.group_by(*group_by_expressions)
            else:
                # 无 GROUP BY，只返回聚合结果
                aggregate_query = base_query.with_entities(*select_columns)

            # 处理 ORDER BY（聚合查询）
            for order_expr in query.order_by:
                parts = order_expr.split()
                field = parts[0]
                direction = parts[1].upper() if len(parts) > 1 else "ASC"

                # 尝试在 select_columns 中找到对应字段
                for col in select_columns:
                    if hasattr(col, "name") and col.name == field:
                        if direction == "DESC":
                            aggregate_query = aggregate_query.order_by(col.desc())
                        else:
                            aggregate_query = aggregate_query.order_by(col.asc())
                        break

            # 执行查询
            results = aggregate_query.limit(query.limit).offset(query.offset).all()

            # 映射结果
            rows = []
            for row in results:
                row_dict = {}
                # Row 是 tuple，按 select_columns 顺序
                for i, (label, original_field) in enumerate(column_labels):
                    value = row[i] if i < len(row) else None
                    # 格式化值
                    if isinstance(value, date):
                        row_dict[original_field] = value.strftime("%Y-%m-%d")
                    elif isinstance(value, datetime):
                        row_dict[original_field] = value.strftime("%Y-%m-%d %H:%M")
                    elif isinstance(value, float):
                        # 保留两位小数
                        if value.is_integer():
                            row_dict[original_field] = int(value)
                        else:
                            row_dict[original_field] = round(value, 2)
                    else:
                        row_dict[original_field] = value
                rows.append(row_dict)

            # 构建列名
            columns = []
            for _, original_field in column_labels:
                display_name = DISPLAY_NAMES.get(original_field, original_field)
                columns.append(display_name)

            return {
                "display_type": "table",
                "columns": columns,
                "column_keys": [original_field for _, original_field in column_labels],
                "rows": rows,
                "summary": f"共 {len(results)} 条记录"
            }

        except Exception as e:
            logger.error(f"Aggregate query failed: {e}", exc_info=True)
            return {
                "display_type": "text",
                "message": f"聚合查询执行失败: {str(e)}",
                "rows": [],
                "summary": "查询失败"
            }


# 导出
__all__ = ["QueryEngine", "get_model_class"]
