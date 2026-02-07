# NL2OntologyQuery 设计文档

## 目录

1. [设计思想](#1-设计思想)
2. [系统架构](#2-系统架构)
3. [核心组件](#3-核心组件)
4. [LLM 与 Ontology 元数据集成](#4-llm-与-ontology-元数据集成)
5. [改进措施](#5-改进措施)
6. [关键代码](#6-关键代码)

---

## 1. 设计思想

### 1.1 核心理念

NL2OntologyQuery 实现了 **"Schema-First, Type-Safe, LLM-Guided"** 的自然语言查询系统：

| 原则 | 说明 |
|------|------|
| **Schema-First** | 所有查询基于运行时导出的 Ontology Schema，而非硬编码 |
| **Type-Safe** | 通过多层次验证确保字段名和类型正确 |
| **LLM-Guided** | LLM 负责理解意图，但受 Schema 约束 |
| **Self-Correcting** | 自动纠正 LLM 的常见错误 |

### 1.2 设计目标

1. **无硬编码查询逻辑** - 实体、字段、关系全部从 ORM 动态提取
2. **强类型保障** - 字段名、类型、关系有明确的验证机制
3. **LLM 友好** - 提供清晰的 Schema 定义和示例
4. **可扩展** - 新增实体时自动纳入查询系统

### 1.3 与传统方案对比

| 方面 | 传统方案 | NL2OntologyQuery |
|------|---------|-------------------|
| 查询定义 | 硬编码 API 端点 | Schema 驱动动态查询 |
| 字段验证 | 后端手动校验 | 自动纠正 + 模糊匹配 |
| LLM 约束 | 靠 Prompt 文本描述 | 结构化 Schema JSON |
| 扩展性 | 每个查询写代码 | 自动支持新实体 |

---

## 2. 系统架构

### 2.1 整体流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户输入                                │
│                  "2026年1月住宿最多的客户"                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AIService.process_message()               │
│  - 检测 follow_up 模式                                          │
│  - 检查话题相关性                                               │
│  - 构建 LLM 上下文                                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LLMService.chat()                         │
│  - 接收用户消息 + 上下文                                         │
│  - 注入 Query Schema                                           │
│  - 返回 structured_query                                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   _validate_and_correct_fields()                │
│  - 字段名验证                                                   │
│  - 自动纠正常见错误                                             │
│  - 模糊匹配不明确字段                                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    QueryEngine.execute()                       │
│  - 解析 StructuredQuery                                         │
│  - 动态构建 SQLAlchemy 查询                                     │
│  - 执行并映射结果                                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              _format_query_result_with_llm()                     │
│  - 构建数据摘要                                                 │
│  - LLM 生成自然语言回复                                         │
│  - 返回格式化结果                                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      用户响应                                   │
│         "根据查询结果，2026年1月住宿最多的客户是：黄敏..."         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 三层保障机制

```
┌─────────────────────────────────────────────────────────────┐
│                  第一层：Schema 导出（预防）                   │
│  OntologyRegistry.export_query_schema()                       │
│  - 从 SQLAlchemy 动态提取字段                                 │
│  - 标注 filterable/aggregatable                                │
│  - 导出关系映射                                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  第二层：Prompt 引导（指导）                   │
│  PromptBuilder.build_query_schema()                          │
│  - 生成结构化的字段定义                                         │
│  - 强调精确字段名要求                                          │
│  - 提供正确的查询示例                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  第三层：执行纠正（补救）                      │
│  _validate_and_correct_fields()                              │
│  - 验证字段名是否存在                                          │
│  - 纠正常见错误映射                                             │
│  - 模糊匹配相似字段                                            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 核心组件

### 3.1 数据结构 (`core/ontology/query.py`)

#### StructuredQuery

```python
@dataclass
class StructuredQuery:
    """结构化查询 - NL2OntologyQuery 的核心数据结构"""
    entity: str                       # 目标实体名 (如 "Guest", "Room")
    fields: List[str]                 # 动态字段选择 ["name", "phone", "guest.name"]
    filters: List[FilterClause] = field(default_factory=list)
    joins: List[JoinClause] = field(default_factory=list)
    order_by: List[str] = field(default_factory=list)
    limit: int = 100
    offset: int = 0
    distinct: bool = False
    aggregate: Optional[AggregateClause] = None  # 聚合查询
    group_by: Optional[List[str]] = None

    def is_simple(self) -> bool:
        """判断是否为简单查询（可用 Service 优化）"""
        return (
            not self.joins and
            len(self.filters) <= 1 and
            len(self.fields) <= 3 and
            not self.aggregate
        )
```

#### FilterClause - 过滤条件

```python
@dataclass
class FilterClause:
    field: str                       # 字段路径 "stay_records.status"
    operator: FilterOperator = FilterOperator.EQ
    value: Any = None

    # 支持的操作符
    class FilterOperator(str, Enum):
        EQ = "eq"          # 等于
        NE = "ne"          # 不等于
        GT = "gt"          # 大于
        GTE = "gte"        # 大于等于
        LT = "lt"          # 小于
        LTE = "lte"        # 小于等于
        IN = "in"          # 在列表中
        LIKE = "like"      # 模糊匹配
        BETWEEN = "between"
```

#### AggregateClause - 聚合查询

```python
@dataclass
class AggregateClause:
    field: str                       # 聚合字段
    function: str                      # COUNT, SUM, AVG, MAX, MIN
    alias: Optional[str] = None        # 结果别名
    group_by: Optional[List[str]] = None  # GROUP BY 字段
```

### 3.2 查询引擎 (`core/ontology/query_engine.py`)

```python
class QueryEngine:
    """
    Ontology 查询引擎 - 将 StructuredQuery 转换为 SQLAlchemy 查询

    特性：
    - 动态字段选择
    - 关联查询支持
    - 聚合查询支持
    - 自动处理关系映射（.any() / .has()）
    """

    def execute(self, query: StructuredQuery, user=None) -> Dict[str, Any]:
        # 1. 聚合查询分支
        if query.aggregate or query.group_by:
            return self._execute_aggregate_query(model_class, query)

        # 2. 常规查询
        db_query = self._build_query(model_class, query)
        results = db_query.limit(query.limit).offset(query.offset).all()

        # 3. 结果映射
        rows = self._map_results(results, query)
        columns = self._get_column_names(query)

        return {
            "display_type": "table",
            "columns": columns,
            "column_keys": query.fields,
            "rows": rows,
            "summary": f"共 {len(results)} 条记录"
        }
```

**关键方法 - 关系处理：**

```python
def _parse_filter(self, model_class: Type, filter_clause: FilterClause):
    """
    解析过滤条件 - 支持嵌套字段路径

    "stay_records.status" → model.stay_records.any(status=...)
    "room_type.name" → model.room_type.has(name=...)
    """
    parts = field_path.split(".")

    if len(parts) > 1:
        # 嵌套字段 - 使用 relationship.any() 或 has()
        for part in parts[:-1]:
            rel_attr = getattr(current_model, part, None)
            # 检查关系类型
            is_collection = rel_attr.property.uselist
            if is_collection:
                # 一对多：使用 any()
                return rel_attr.any(**{target_field: value})
            else:
                # 多对一：使用 has()
                return rel_attr.has(**{target_field: value})
```

### 3.3 Schema 导出 (`core/ontology/registry.py`)

```python
def export_query_schema(self) -> Dict[str, Any]:
    """
    导出查询专用的 Schema - 为 LLM 提供精确的实体/属性/关系定义

    Returns:
        {
            "entities": {
                "StayRecord": {
                    "table": "stay_records",
                    "fields": {
                        "id": {"type": "int", "primary_key": True, "aggregatable": True},
                        "check_in_time": {"type": "datetime", "filterable": True},
                        "guest.name": {"type": "relationship", "path": "guest.name", "target_entity": "Guest"}
                    },
                    "relationships": {
                        "guest": {"entity": "Guest", "type": "many_to_one"}
                    }
                }
            },
            "aggregate_functions": ["COUNT", "SUM", "AVG", "MAX", "MIN"],
            "filter_operators": ["eq", "ne", "gt", "gte", "lt", "lte", "in", "like", "between"]
        }
    """
    schema = {"entities": {}, "aggregate_functions": [...], "filter_operators": [...]}

    # 从 SQLAlchemy 模型动态提取
    for entity_name, model_class in entity_models.items():
        for column in model_class.__table__.columns:
            field_info = {
                "type": str(column.type.python_type.__name__),
                "filterable": field_name not in ["id", "created_at", "updated_at"],
                "aggregatable": python_type in (int, float)
            }
            entity_info["fields"][field_name] = field_info

        # 添加关系字段 (guest.name)
        for rel_name, rel_info in relationships.items():
            for col in target_model.__table__.columns[:3]:
                if col.name in ["name", "phone", "room_number", "status"]:
                    entity_info["fields"][f"{rel_name}.{col.name}"] = {
                        "type": "relationship",
                        "path": f"{rel_name}.{col.name}",
                        "target_entity": rel_info["entity"]
                    }
```

---

## 4. LLM 与 Ontology 元数据集成

### 4.1 Schema 注入流程

```
OntologyRegistry (运行时元数据)
        │
        │ export_query_schema()
        ▼
PromptBuilder.build_query_schema()
        │
        │ 格式化为 LLM Prompt
        ▼
LLMService.chat() 的 context
        │
        │ include_query_schema=True
        ▼
LLM 的 System Prompt
```

### 4.2 Prompt 结构

```python
**Ontology Query Schema (精确字段定义)**

**重要: 必须使用下面定义的精确字段名，不要猜测或创造新字段名**

## 可查询实体及字段

### StayRecord
- 表名: stay_records
- 字段:
  - `id` (int) [主键] [可聚合]
  - `check_in_time` (datetime) [可过滤]      ← 强调精确字段名
  - `guest.name` (relationship) [可过滤] → 关联到 Guest
  - `room.room_number` (relationship) [可过滤]

## 聚合查询
- 支持的聚合函数: COUNT, SUM, AVG, MAX, MIN
- 支持的过滤操作符: eq, ne, gt, gte, lt, lte, in, like, between

**重要规则:**
1. 使用 field="id" + function="COUNT" 进行计数统计
2. 日期过滤使用 check_in_time 字段（不是 check_in_date）
3. 关联字段使用点号路径: guest.name, room.room_number
```

### 4.3 LLM 返回示例

**用户输入：** "2026年1月住宿最多的客户"

**LLM 返回：**
```json
{
  "action_type": "ontology_query",
  "params": {
    "entity": "StayRecord",
    "fields": ["guest.name", "stay_count"],
    "aggregate": {
      "field": "id",
      "function": "COUNT",
      "alias": "stay_count"
    },
    "filters": [
      {"field": "check_in_time", "operator": "gte", "value": "2026-01-01"},
      {"field": "check_in_time", "operator": "lt", "value": "2026-02-01"}
    ],
    "order_by": ["stay_count DESC"],
    "limit": 3
  }
}
```

---

## 5. 改进措施

### 5.1 当前已实现的保障机制

| 机制 | 位置 | 效果 |
|------|------|------|
| Schema 动态导出 | `registry.py:export_query_schema()` | 字段名与 ORM 同步 |
| Prompt 精确引导 | `prompt_builder.py:build_query_schema()` | LLM 知道正确字段名 |
| 字段名自动纠正 | `ai_service.py:_validate_and_correct_fields()` | 修正 LLM 错误 |
| 结果 LLM 格式化 | `ai_service.py:_format_query_result_with_llm()` | 自然语言回复 |

### 5.2 待实现的改进措施

#### 改进 1：自动关系推导

**当前问题：** 关系映射手动维护

```python
# 当前（手动维护）
relationship_map = {
    "StayRecord": {
        "guest": {"entity": "Guest", "type": "many_to_one", "foreign_key": "guest_id"},
    }
}
```

**改进方案：**

```python
def _extract_relationships_from_orm(model_class):
    """从 SQLAlchemy 关系属性自动推导"""
    relationships = {}
    for rel_name, rel_property in model_class.__mapper__.relationships.items():
        target_model = rel_property.mapper.class_
        relationships[rel_name] = {
            "entity": target_model.__name__,
            "type": "many_to_one" if not rel_property.uselist else "one_to_many",
            "foreign_key": rel_property.local_remote_pairs[0][0] if rel_property.local_remote_pairs else None
        }
    return relationships
```

#### 改进 2：智能模糊匹配

**当前问题：** 简单的字符串包含匹配

```python
# 当前
def _find_similar_field(self, field: str, valid_fields: set) -> str:
    for valid in valid_fields:
        if field_lower in valid.lower():
            return valid
```

**改进方案：**

```python
from difflib import SequenceMatcher, get_close_matches

def _find_similar_field_enhanced(self, field: str, valid_fields: set) -> str:
    """使用编辑距离算法进行模糊匹配"""

    # 1. 精确匹配（考虑缩写、大小写）
    for valid in valid_fields:
        if field.lower().replace("_", "") == valid.lower().replace("_", ""):
            return valid

    # 2. 编辑距离匹配（相似度 > 0.7）
    matches = get_close_matches(field, valid_fields, n=1, cutoff=0.7)
    if matches:
        return matches[0]

    # 3. 语义映射（常见错误模式）
    semantic_map = {
        "date": ["time", "_date", "_at"],
        "name": ["_name", ".name"],
        "id": ["_id", ".id"],
    }
    # ... 语义匹配逻辑

    return ""
```

#### 改进 3：类型感知验证

**当前问题：** 只检查字段名存在性，不验证值类型

```python
# 当前：只检查字段名
if field not in valid_fields:
    corrected_field = field_mappings.get(field)
```

**改进方案：**

```python
def _validate_and_correct_fields_enhanced(self, query_dict: dict) -> dict:
    """增强版验证：字段名 + 类型 + 操作符兼容性"""

    corrected = copy.deepcopy(query_dict)
    entity_name = corrected.get("entity", "")

    # 获取字段 Schema
    schema = registry.export_query_schema()
    entity_schema = schema.get("entities", {}).get(entity_name, {})

    # 验证每个过滤器
    for f in corrected.get("filters", []):
        field_name = f["field"]
        field_schema = entity_schema.get("fields", {}).get(field_name)

        if field_schema:
            # 1. 字段名正确，验证类型
            field_type = field_schema.get("type")
            value = f.get("value")
            operator = f.get("operator")

            # 2. 类型检查和转换
            corrected_value = self._coerce_value_type(value, field_type, operator)
            if corrected_value != value:
                f["value"] = corrected_value
                logger.info(f"Type coercion: {value} -> {corrected_value} for {field_name}")

            # 3. 操作符兼容性检查
            if not self._is_operator_compatible(operator, field_type):
                # 建议正确的操作符
                suggested = self._suggest_compatible_operator(field_type, operator)
                if suggested:
                    f["operator"] = suggested

def _coerce_value_type(self, value: Any, field_type: str, operator: str) -> Any:
    """类型强制转换"""
    if field_type == "datetime" or field_type == "date":
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except:
                # 尝试其他格式
                pass
    # ... 其他类型处理
    return value
```

#### 改进 4：示例驱动提示

**当前问题：** Prompt 只有字段定义，缺少查询示例

**改进方案：**

```python
def build_query_schema(self) -> str:
    # ... 现有 Schema ...

    # 添加成功查询示例（从历史记录）
    examples = self._get_successful_query_examples()
    lines.append("\n**查询示例（参考）:**")

    for i, ex in enumerate(examples[:5], 1):
        lines.append(f"\n示例 {i}: {ex['question']}")
        lines.append(f"查询: {ex['query_json']}")
        lines.append(f"说明: {ex['explanation']}")

def _get_successful_query_examples(self) -> List[Dict]:
    """从历史记录获取成功的查询示例"""
    # 可以从数据库或日志中提取
    return [
        {
            "question": "2026年1月住宿最多的客户",
            "query_json": '{"entity": "StayRecord", "fields": ["guest.name", "stay_count"], ...}',
            "explanation": "使用 COUNT 聚合，按 guest 分组，过滤 check_in_time 范围"
        },
        # ... 更多示例
    ]
```

#### 改进 5：查询复杂度评估

**当前问题：** 无法预判查询执行成本

**改进方案：**

```python
def estimate_query_cost(self, query: StructuredQuery) -> Dict[str, Any]:
    """评估查询执行成本"""
    cost = 0

    # 基础成本
    cost += 10

    # JOIN 成本
    cost += len(query.joins) * 20

    # 聚合成本
    if query.aggregate:
        cost += 30
    if query.group_by:
        cost += len(query.group_by) * 15

    # 过滤条件收益
    for f in query.filters:
        if f.operator in ["eq", "in"]:
            cost -= 5  # 等值查询减少扫描

    # 返回评估结果
    if cost > 100:
        return {
            "level": "high",
            "cost": cost,
            "suggestion": "建议添加更严格的过滤条件以减少查询时间"
        }
    elif cost > 50:
        return {"level": "medium", "cost": cost}
    return {"level": "low", "cost": cost}
```

#### 改进 6：结果缓存

**当前问题：** 相同查询重复执行

**改进方案：**

```python
from functools import lru_cache
import hashlib
import json

class QueryEngine:
    def __init__(self, db: Session, registry=None):
        self.db = db
        self.registry = registry
        self._cache = {}
        self._cache_ttl = 300  # 5分钟缓存

    @lru_cache(maxsize=100)
    def _get_cached_result(self, query_hash: str, query: StructuredQuery):
        """缓存查询结果"""
        return None  # 由外部调用

    def execute(self, query: StructuredQuery, user=None) -> Dict[str, Any]:
        # 生成查询哈希
        query_str = json.dumps(query.to_dict(), sort_keys=True)
        query_hash = hashlib.md5(query_str.encode()).hexdigest()

        # 检查缓存
        if query_hash in self._cache:
            cached = self._cache[query_hash]
            if time.time() - cached["timestamp"] < self._cache_ttl:
                logger.info(f"Cache hit for query: {query.entity}")
                return cached["result"]

        # 执行查询
        result = self._execute_uncached(query, user)

        # 存入缓存
        self._cache[query_hash] = {
            "result": result,
            "timestamp": time.time()
        }

        return result
```

#### 改进 7：细粒度异常处理

**当前问题：** 捕获所有异常，隐藏具体错误类型

**改进方案：**

```python
class QueryValidationError(Exception):
    """查询验证错误"""
    def __init__(self, field: str, message: str, suggestions: List[str] = None):
        self.field = field
        self.message = message
        self.suggestions = suggestions or []

class FieldNotFoundError(QueryValidationError):
    """字段不存在错误"""

class TypeMismatchError(QueryValidationError):
    """类型不匹配错误"""

class RelationshipError(QueryValidationError):
    """关系错误"""

# 使用
try:
    result = engine.execute(query)
except FieldNotFoundError as e:
    return {
        "error": "field_not_found",
        "field": e.field,
        "valid_fields": list(valid_fields),
        "suggestions": e.suggestions
    }
except TypeMismatchError as e:
    return {
        "error": "type_mismatch",
        "field": e.field,
        "expected_type": e.expected_type,
        "actual_value": e.actual_value
    }
```

---

## 6. 关键代码

### 6.1 Schema 导出核心代码

**文件：** `core/ontology/registry.py:703-847`

```python
def export_query_schema(self) -> Dict[str, Any]:
    """
    导出查询专用的 Schema - 为 LLM 提供精确的实体/属性/关系定义
    """
    schema = {
        "entities": {},
        "aggregate_functions": ["COUNT", "SUM", "AVG", "MAX", "MIN"],
        "filter_operators": ["eq", "ne", "gt", "gte", "lt", "lte", "in", "like", "between"]
    }

    # 从 SQLAlchemy 模型动态提取
    for entity_name, model_class in entity_models.items():
        entity_info = {"fields": {}, "relationships": {}}

        # 获取表名
        entity_info["table"] = model_class.__tablename__

        # 遍历所有列
        for column in model_class.__table__.columns:
            field_info = {
                "type": str(column.type.python_type.__name__),
                "nullable": column.nullable,
                "primary_key": column.primary_key,
                "filterable": column.name not in ["id", "created_at", "updated_at"],
                "aggregatable": column.type.python_type in (int, float)
            }
            entity_info["fields"][column.name] = field_info

        # 添加关系字段
        for rel_name, rel_info in relationships.items():
            target_entity = rel_info["entity"]
            if target_entity in entity_models:
                target_model = entity_models[target_entity]
                for col in target_model.__table__.columns[:3]:
                    if col.name in ["name", "phone", "room_number", "status"]:
                        entity_info["fields"][f"{rel_name}.{col.name}"] = {
                            "type": "relationship",
                            "path": f"{rel_name}.{col.name}",
                            "relationship": rel_name,
                            "target_entity": target_entity,
                            "filterable": True
                        }

        schema["entities"][entity_name] = entity_info

    return schema
```

### 6.2 字段验证核心代码

**文件：** `app/services/ai_service.py:1806-1951`

```python
def _validate_and_correct_fields(self, query_dict: dict) -> dict:
    """
    验证和纠正 LLM 返回的字段名

    常见错误映射：
    - check_in_date -> check_in_time
    - guest_name -> guest.name
    - room_number -> room.room_number
    """
    corrected = copy.deepcopy(query_dict)
    entity_name = corrected.get("entity", "")

    # 获取有效字段
    schema = registry.export_query_schema()
    entity_schema = schema.get("entities", {}).get(entity_name, {})
    valid_fields = set(entity_schema.get("fields", {}).keys())

    # 字段名映射表
    field_mappings = {
        "check_in_date": "check_in_time",
        "check_out_date": "check_out_time",
        "guest_name": "guest.name",
        "guest_phone": "guest.phone",
        "room_number": "room.room_number",
        # ...
    }

    # 纠正 filters
    for f in corrected.get("filters", []):
        field = f.get("field", "")
        if field not in valid_fields:
            corrected_field = field_mappings.get(field)
            if corrected_field and corrected_field in valid_fields:
                f["field"] = corrected_field
                logger.info(f"Corrected filter field: {field} -> {corrected_field}")
            elif self._find_similar_field(field, valid_fields):
                f["field"] = self._find_similar_field(field, valid_fields)

    # 纠正 fields
    # 纠正 aggregate
    # 纠正 order_by

    return corrected
```

### 6.3 聚合查询执行代码

**文件：** `core/ontology/query_engine.py:514-650`

```python
def _execute_aggregate_query(self, model_class: Type, query: StructuredQuery):
    """
    执行聚合查询

    支持 GROUP BY、COUNT、SUM、AVG、MAX、MIN
    支持嵌套字段（如 guest.name）
    """
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

    # 构建选择字段（分组字段 + 聚合字段）
    select_columns = []
    column_labels = []

    # 从 fields 中提取分组字段和关联字段
    for field in query.fields:
        if query.aggregate and query.aggregate.alias == field:
            continue

        if "." in field:  # 嵌套字段
            parts = field.split(".")
            rel_name = parts[0]
            target_field = parts[-1]

            # 添加 JOIN
            if rel_name not in joined_models:
                rel_attr = getattr(model_class, rel_name, None)
                related_model = rel_attr.property.mapper.class_
                base_query = base_query.join(related_model)
                joined_models[rel_name] = (related_model, rel_attr)

            # 获取最终字段
            related_model = joined_models[rel_name][0]
            target_attr = getattr(related_model, target_field, None)
            if target_attr is not None:
                label = field.replace(".", "_")
                select_columns.append(target_attr.label(label))
                column_labels.append((label, field))
                group_by_expressions.append(target_attr)

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
                agg_expr = func.count(attr).label(agg_alias)
            elif agg_func == "sum":
                agg_expr = func.sum(attr).label(agg_alias)
            # ...

            select_columns.append(agg_expr)
            column_labels.append((agg_alias, agg_alias))

    # 构建 GROUP BY 查询
    if group_by_expressions:
        aggregate_query = base_query.with_entities(*select_columns)
        aggregate_query = aggregate_query.group_by(*group_by_expressions)
    else:
        aggregate_query = base_query.with_entities(*select_columns)

    # 执行查询
    results = aggregate_query.limit(query.limit).offset(query.offset).all()

    return {"rows": results, "columns": columns, ...}
```

### 6.4 结果格式化代码

**文件：** `app/services/ai_service.py:1153-1199`

```python
def _format_query_result_with_llm(self, original_result: Dict, query_result: Dict, user: Employee):
    """
    使用 LLM 格式化查询结果，生成更友好的回复
    """
    query_data = query_result.get("query_result", {})
    rows = query_data.get("rows", [])
    columns = query_data.get("columns", [])
    summary = query_data.get("summary", "")

    # 构建数据摘要
    data_summary = self._build_data_summary(rows, columns)

    # 构建 LLM 提示
    format_prompt = f"""用户的问题：{original_result.get('message', '')}

查询结果摘要：{summary}

详细数据：
{data_summary}

请根据查询结果，用自然语言回答用户的问题。
要求：
1. 直接回答问题，列出关键信息
2. 如果是人名，只列出名字即可
3. 保持简洁，不要啰嗦
4. 不要添加 JSON 格式，直接用自然语言回答

请直接给出回答："""

    # 调用 LLM 格式化
    formatted_message = self.llm_service.chat(
        format_prompt,
        {"user_role": user.role.value, "user_name": user.name},
        language='zh'
    ).get("message", summary)

    query_result["message"] = formatted_message
    return query_result
```

---

## 附录：快速参考

### A.1 文件结构

```
backend/
├── core/
│   ├── ontology/
│   │   ├── query.py              # StructuredQuery 数据结构
│   │   ├── query_engine.py       # QueryEngine 查询引擎
│   │   └── registry.py           # OntologyRegistry (export_query_schema)
│   └── ai/
│       └── prompt_builder.py      # LLM Prompt 构建
└── app/
    └── services/
        └── ai_service.py          # AI 服务 (_validate_and_correct_fields)
```

### A.2 API 流程

```
1. LLM 返回 ontology_query
2. _handle_query_action 识别为查询操作
3. _execute_ontology_query:
   a. _validate_and_correct_fields 纠正字段
   b. QueryEngine.execute 执行查询
   c. _format_query_result_with_llm 格式化结果
4. 返回自然语言回复
```

### A.3 测试文件

```
tests/
├── core/
│   └── test_ontology_query.py   # QueryEngine 单元测试
└── api/
    ├── test_smart_query.py       # API 查询测试
    └── test_natural_language_queries.py  # LLM 查询测试
```

---

**文档版本:** 1.0
**最后更新:** 2026-02-07
**作者:** Claude Opus 4.6
