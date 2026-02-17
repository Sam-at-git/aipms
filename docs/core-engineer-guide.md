# Core 代码维护工程师指南

> **适用范围**：AIPMS core/ 层（Ontology Runtime Framework）
> **读者**：有 Python 开发经验但不熟悉本系统的工程师
> **配套文档**：[Domain Developer Guide](domain-developer-guide.md) · [Domain BA Guide](domain-ba-guide.md) · [Benchmark Designer Guide](benchmark-designer-guide.md)

---

## 目录

1. [架构总览](#1-架构总览)
2. [核心约束：domain-agnostic](#2-核心约束domain-agnostic)
3. [模块地图：core/ 全景](#3-模块地图core-全景)
4. [core/ontology/ — 本体元数据层](#4-coreontology--本体元数据层)
5. [core/ai/ — AI 编排层](#5-coreai--ai-编排层)
6. [core/ooda/ — OODA 循环抽象层](#6-coreooda--ooda-循环抽象层)
7. [core/engine/ — 引擎基础设施](#7-coreengine--引擎基础设施)
8. [core/security/ — 安全与权限](#8-coresecurity--安全与权限)
9. [core/reasoning/ — 推理与约束](#9-corereasoning--推理与约束)
10. [数据流全景](#10-数据流全景)
11. [测试体系](#11-测试体系)
12. [常见维护任务 Cookbook](#12-常见维护任务-cookbook)
13. [Bug 排查手册](#13-bug-排查手册)
14. [性能调优](#14-性能调优)
15. [版本演进与兼容性](#15-版本演进与兼容性)
16. [附录 A：文件速查表](#附录-a文件速查表)
17. [附录 B：单例与全局状态清单](#附录-b单例与全局状态清单)
18. [附录 C：环境变量参考](#附录-c环境变量参考)

---

## 1. 架构总览

### 1.1 三层架构

```
┌─────────────────────────────────────────────────┐
│  Layer 3: app/system/     系统管理域              │
│  Layer 2: app/hotel/      酒店业务域              │
├─────────────────────────────────────────────────┤
│  Layer 1: core/           本体运行时框架 ← 你在这里│
└─────────────────────────────────────────────────┘
```

**core/ 的职责**：提供可复用的、与业务领域无关的基础框架。如果把 AIPMS 比作操作系统：

- `core/` = 内核（调度器、文件系统、驱动接口）
- `app/hotel/` = 应用程序（酒店前台、客房管理）
- `app/system/` = 系统工具（用户管理、权限配置）

### 1.2 core/ 的设计原则

| 原则 | 含义 | 违反后果 |
|------|------|---------|
| **Domain-Agnostic** | core/ 中不能出现任何酒店/业务特定逻辑 | 架构守卫测试失败 |
| **Dependency Inversion** | core/ 定义接口，app/ 实现接口 | 通过 `IDomainAdapter` 注入 |
| **Metadata-Driven** | 行为由元数据（OntologyRegistry）驱动，不硬编码 | 新实体无需修改 core/ |
| **Singleton + DI** | Registry/Engine 用单例，Orchestrator 用依赖注入 | 见附录 B |

### 1.3 代码规模

| 子模块 | 文件数 | 代码行数 | 核心职责 |
|--------|--------|---------|---------|
| `core/ai/` | 17 | ~11,300 | AI 编排、LLM 调用、Prompt 构建、Debug |
| `core/ontology/` | 15 | ~6,200 | 元数据模型、Registry、查询引擎 |
| `core/ooda/` | 7 | ~2,000 | OODA 循环四阶段抽象 |
| `core/reasoning/` | 6 | ~2,000 | 约束引擎、规划器、关系图 |
| `core/engine/` | 6 | ~1,600 | 事件总线、规则引擎、状态机、审计 |
| `core/security/` | 6 | ~1,500 | ACL、数据脱敏、权限检查 |
| **合计** | **~60** | **~24,600** | |

---

## 2. 核心约束：domain-agnostic

### 2.1 架构守卫测试

`tests/domain/test_domain_separation.py::test_core_has_no_app_imports` 会扫描 `core/` 下所有 `.py` 文件，确保没有 `from app.` 或 `import app.` 语句。

```python
# ❌ 在 core/ 的任何文件中写这些都会导致测试失败
from app.models.ontology import Room
from app.services.ai_service import AIService
import app.hotel.hotel_domain_adapter

# ✅ 正确方式：通过注入获取
class OodaOrchestrator:
    def __init__(self, db, adapter, *, model_resolver=None, ...):
        self.adapter = adapter          # IDomainAdapter 接口
        self._model_resolver = model_resolver  # callable(name) → ORM model
```

### 2.2 如何判断代码应该放在 core/ 还是 app/

| 问题 | 如果是 → core/ | 如果否 → app/ |
|------|---------------|--------------|
| 换一个完全不同的业务域（如医院、仓库），这段逻辑还有用吗？ | ✅ | ❌ |
| 逻辑依赖具体的数据库表名、列名或枚举值吗？ | ❌ | ✅ |
| 逻辑操作的是 `EntityMetadata`、`ActionMetadata` 等抽象概念吗？ | ✅ | - |
| 逻辑操作的是 `Room`、`Guest`、`Reservation` 等具体模型吗？ | - | ✅ |

---

## 3. 模块地图：core/ 全景

```
core/
├── __init__.py                    # Root 导出（185 行）
│
├── ontology/                      # ⭐ 本体元数据层（6,200 行）
│   ├── registry.py                # OntologyRegistry 单例（1,033 行）
│   ├── metadata.py                # 元数据模型定义（753 行）
│   ├── query_engine.py            # StructuredQuery → SQLAlchemy（711 行）
│   ├── semantic_path_resolver.py  # SemanticQuery → StructuredQuery（663 行）
│   ├── semantic_query.py          # 语义查询数据结构（400 行）
│   ├── query.py                   # StructuredQuery 数据结构（252 行）
│   ├── base.py                    # BaseEntity + ObjectProxy（362 行）
│   ├── domain_adapter.py          # IDomainAdapter 接口（196 行）
│   ├── guard_executor.py          # 约束守卫执行器（263 行）
│   ├── business_rules.py          # 业务规则注册表（201 行）
│   ├── rule_applicator.py         # 规则应用引擎（193 行）
│   ├── interface.py               # 本体接口契约（205 行）
│   ├── link.py                    # Link/LinkCollection（164 行）
│   ├── state_machine_executor.py  # 状态机校验（141 行）
│   └── security.py                # SecurityLevel 枚举（59 行）
│
├── ai/                            # ⭐ AI 编排层（11,300 行）
│   ├── ooda_orchestrator.py       # OODA 主编排器（1,923 行）⭐⭐ 最大文件
│   ├── debug_logger.py            # LLM 会话追踪（1,122 行）
│   ├── replay.py                  # 会话回放引擎（1,091 行）
│   ├── prompt_builder.py          # 动态 Prompt 构建（1,035 行）
│   ├── reflexion.py               # 自修复执行循环（913 行）
│   ├── actions.py                 # ActionRegistry 注册与分发（908 行）
│   ├── vector_store.py            # 向量存储（506 行）
│   ├── hitl.py                    # 人在回路确认策略（462 行）
│   ├── llm_client.py              # LLM 抽象层（438 行）
│   ├── intent_router.py           # 意图路由（423 行）
│   ├── query_compiler.py          # 意图 → SemanticQuery（407 行）
│   ├── response_generator.py      # 查询结果 → 自然语言（321 行）
│   ├── schema_retriever.py        # Schema 检索（309 行）
│   ├── embedding.py               # Embedding 服务（249 行）
│   ├── llm_call_context.py        # 线程本地上下文（90 行）
│   └── query_keywords.py          # 查询/操作关键词表（34 行）
│
├── ooda/                          # OODA 循环抽象层（2,000 行）
│   ├── loop.py                    # OodaLoop 编排（340 行）
│   ├── observe.py                 # 输入验证与归一化（389 行）
│   ├── orient.py                  # 上下文注入 + 意图识别（305 行）
│   ├── decide.py                  # 决策生成 + 参数校验（445 行）
│   ├── act.py                     # 执行 + 结果格式化（338 行）
│   └── intent.py                  # IntentResult 模型（149 行）
│
├── reasoning/                     # 推理与约束（2,000 行）
│   ├── constraint_engine.py       # 约束验证引擎（746 行）
│   ├── planner.py                 # 规划引擎（456 行）
│   ├── dag_executor.py            # DAG 执行器（315 行）
│   ├── relationship_graph.py      # 实体关系图（309 行）
│   └── plan_templates.py          # 复合操作模板（173 行）
│
├── engine/                        # 引擎基础设施（1,600 行）
│   ├── event_bus.py               # 事件总线 Pub/Sub（391 行）
│   ├── audit.py                   # 审计日志（285 行）
│   ├── rule_engine.py             # 规则引擎（276 行）
│   ├── state_machine.py           # 状态机实现（264 行）
│   └── snapshot.py                # 操作快照（撤销支持）（255 行）
│
├── security/                      # 安全与权限（1,500 行）
│   ├── checker.py                 # 权限检查器（436 行）
│   ├── masking.py                 # 数据脱敏（338 行）
│   ├── attribute_acl.py           # 属性级 ACL（287 行）
│   ├── context.py                 # 安全上下文管理（261 行）
│   └── permission.py              # PermissionProvider 接口（89 行）
│
├── domain/                        # 向后兼容存根（122 行）
├── notification/                  # 通知渠道接口（100 行）
└── scheduler/                     # 调度器接口（105 行）
```

---

## 4. core/ontology/ — 本体元数据层

本体层是整个系统的**数据模型中枢**。所有实体的结构、关系、状态机、业务规则都注册在这里。

### 4.1 OntologyRegistry 单例

`registry.py` 定义了全局唯一的 `OntologyRegistry`，它是 core/ 层最重要的数据结构。

**内部存储**：

```python
_entities: Dict[str, EntityMetadata]           # 实体元数据
_actions: Dict[str, List[ActionMetadata]]      # 按实体分组的 Action
_state_machines: Dict[str, StateMachine]       # 状态机定义
_business_rules: Dict[str, List[BusinessRule]] # 业务规则
_constraints: Dict[str, ConstraintMetadata]    # 约束定义
_permission_matrix: Dict[str, Set[str]]        # Action → 允许的角色
_models: Dict[str, Any]                        # ORM model class
_relationships: Dict[str, List[RelationshipMetadata]]  # 关系定义
_interfaces: Dict[str, Any]                    # 接口定义
_events: Dict[str, EventMetadata]              # 领域事件
```

**注册 API**（全部返回 `self`，支持链式调用）：

```python
registry.register_entity(metadata: EntityMetadata)
registry.register_action(entity: str, metadata: ActionMetadata)
registry.register_state_machine(metadata: StateMachine)
registry.register_business_rule(entity: str, rule: BusinessRule)
registry.register_constraint(constraint: ConstraintMetadata)
registry.register_permission(action_type: str, roles: Set[str])
registry.register_model(entity_name: str, model_class: Any)
registry.register_relationship(entity_name: str, rel: RelationshipMetadata)
registry.register_event(metadata: EventMetadata)
registry.register_interface(interface_cls: Any)
```

**查询 API**（最常用的几个）：

```python
registry.get_entity(name) → EntityMetadata | None
registry.get_entities() → List[EntityMetadata]
registry.get_actions(entity=None) → List[ActionMetadata]
registry.get_action_by_name(action_name) → ActionMetadata | None
registry.get_state_machine(entity) → StateMachine | None
registry.get_constraints_for_entity_action(entity, action) → List[ConstraintMetadata]
registry.get_model(entity_name) → ORM class | None
registry.get_relationships(entity_name) → List[RelationshipMetadata]
registry.get_relationship_map() → Dict  # 用于查询引擎的 JOIN 发现
```

**导出 API**（用于 LLM Prompt 注入和 Debug）：

```python
registry.export_schema() → Dict         # JSON-serializable 完整 schema
registry.export_query_schema() → Dict   # 查询专用 schema
registry.to_llm_knowledge_base() → str  # Markdown 格式，注入 LLM Prompt
registry.describe_type(entity_name) → Dict
registry.find_entities_by_keywords(message) → List[str]
```

### 4.2 元数据模型

`metadata.py` 定义了所有元数据的 dataclass：

**EntityMetadata** — 实体定义：

```python
@dataclass
class EntityMetadata:
    name: str                                  # "Room"
    description: str                           # "酒店房间"
    table_name: str                            # "rooms"
    properties: Dict[str, PropertyMetadata]    # 字段定义
    relationships: List[RelationshipMetadata]  # 关系
    category: str                              # "transactional" | "master_data" | "dimension"
    implements: List[str]                      # 实现的接口
    lifecycle_states: List[str]                # 可能的状态
    extensions: Dict[str, Any]                 # 扩展钩子
    # ... 更多字段
```

**PropertyMetadata** — 属性定义：

```python
@dataclass
class PropertyMetadata:
    name: str                      # "phone"
    type: str                      # "string"
    is_required: bool
    is_unique: bool
    enum_values: List[str]         # ["active", "pending", ...]
    security_level: str            # "PUBLIC" | "INTERNAL" | "CONFIDENTIAL" | "RESTRICTED"
    pii_type: PIIType              # NONE | NAME | PHONE | EMAIL | ...
    display_name: str              # "联系电话"（用于 LLM 和 UI）
    mutable: bool                  # 是否可修改
    updatable_by: List[str]        # 允许修改的角色
    format_regex: str              # 格式校验正则
    # ... 更多字段
```

**ActionMetadata** — 操作定义：

```python
@dataclass
class ActionMetadata:
    action_type: str               # "walkin_checkin"
    entity: str                    # "StayRecord"
    description: str               # "散客入住"
    params: List[ActionParam]      # 参数列表
    requires_confirmation: bool    # 是否需要用户确认
    allowed_roles: Set[str]        # {"receptionist", "manager"}
    category: str                  # "query" | "mutation" | "system" | "tool"
    risk_level: str                # "none" | "low" | "medium" | "high" | "critical"
    is_financial: bool             # 涉及金额
    undoable: bool                 # 可撤销
    side_effects: List[str]        # 副作用描述
    # ... 更多字段
```

**StateMachine** — 状态机：

```python
@dataclass
class StateMachine:
    entity: str                    # "Room"
    states: List[str]              # ["vacant_clean", "occupied", "vacant_dirty", ...]
    transitions: List[StateTransition]
    initial_state: str             # "vacant_clean"
    final_states: Set[str]         # {"decommissioned"}

@dataclass
class StateTransition:
    from_state: str
    to_state: str
    trigger: str                   # 触发 Action
    condition: str                 # 条件表达式
    side_effects: List[str]        # 转换后的副作用
```

**RelationshipMetadata** — 关系定义：

```python
@dataclass
class RelationshipMetadata:
    name: str                      # 属性名（如 "stays"）
    target_entity: str             # 目标实体（如 "StayRecord"）
    cardinality: str               # "one_to_many" | "many_to_one" | "one_to_one"
    foreign_key: str               # FK 列名
    foreign_key_entity: str        # FK 所在实体
    inverse_name: str              # 反向导航名
```

**ConstraintMetadata** — 约束定义：

```python
@dataclass
class ConstraintMetadata:
    id: str                        # "room_must_be_vacant_for_checkin"
    entity: str                    # "Room"（或 "*" 表示全局）
    action: str                    # "checkin"（或 "*" 表示所有操作）
    constraint_type: ConstraintType  # STATE | BUSINESS_RULE | REFERENCE | CUSTOM
    severity: ConstraintSeverity   # INFO | WARNING | ERROR | CRITICAL
    condition_text: str            # 自然语言条件（LLM 可读）
    condition_code: str            # 可执行的条件表达式
    error_message: str             # 违反时的错误消息
    suggestion_message: str        # 建议操作
    validator: IConstraintValidator # 自定义校验器（可选）
```

### 4.3 两级查询管道

查询管道是 core/ 层最精密的部分，分两步完成：

```
Step 1: SemanticQuery（LLM 友好的点表示法）
        ↓  SemanticPathResolver.compile()
Step 2: StructuredQuery（SQL-ready 结构）
        ↓  QueryEngine.execute()
Step 3: 结果 Dict
```

**SemanticQuery**（`semantic_query.py`）— LLM 输出格式：

```python
SemanticQuery(
    root_object="Guest",
    fields=["name", "phone", "stays.room.room_number"],
    filters=[
        SemanticFilter(path="stays.status", operator=FilterOperator.EQ, value="ACTIVE")
    ],
    order_by=["name"],
    limit=50
)
```

点表示法 `stays.room.room_number` 自动解析为：Guest → StayRecord → Room → room_number。

**SemanticPathResolver**（`semantic_path_resolver.py`）— 路径编译器：

```python
resolver = SemanticPathResolver()
structured = resolver.compile(semantic_query)
# 自动发现 JOIN 路径：Guest → StayRecord → Room
# 生成 StructuredQuery with joins
```

关键方法：
- `compile(semantic_query) → StructuredQuery` — 主入口
- `resolve_path(root_entity, path) → ResolvedPath` — 解析单条路径
- `suggest_paths(entity, max_depth) → List[str]` — 自动推荐可用路径

路径解析失败时抛出 `PathResolutionError`，包含 fuzzy 匹配的建议。

**StructuredQuery**（`query.py`）— SQL-ready 查询：

```python
StructuredQuery(
    entity="Guest",
    fields=["name", "phone", "stay_records.room_number"],
    filters=[FilterClause(field="stay_records.status", operator=FilterOperator.EQ, value="ACTIVE")],
    joins=[JoinClause(entity="StayRecord", join_type=JoinType.LEFT)],
    order_by=["name"],
    limit=50
)
```

**QueryEngine**（`query_engine.py`）— SQL 执行器：

```python
engine = QueryEngine(db_session=db, registry=registry)
result = engine.execute(structured_query, user=current_user)
# result = {
#     "display_type": "table",
#     "columns": ["姓名", "电话", "房间号"],
#     "column_keys": ["name", "phone", "room_number"],
#     "rows": [{"name": "张三", "phone": "138...", "room_number": "201"}, ...],
#     "summary": "共 3 条记录"
# }
```

关键方法：
- `execute(query, user) → Dict` — 主入口
- `_build_query(model_class, query) → SQLAlchemy Query` — 构建 SQLAlchemy 查询
- `_apply_join(query, base_model, join_clause) → Query` — 应用 JOIN
- `_parse_filter(model_class, filter_clause) → BinaryExpression` — 解析过滤条件
- `_get_default_fields(entity_name) → List[str]` — 自动选择返回字段

### 4.4 IDomainAdapter 接口

`domain_adapter.py` 定义了 core/ 与 app/ 之间的契约：

```python
class IDomainAdapter(ABC):
    @abstractmethod
    def get_domain_name(self) -> str: ...

    @abstractmethod
    def register_ontology(self, registry: OntologyRegistry) -> None: ...

    @abstractmethod
    def get_current_state(self) -> Dict[str, Any]: ...

    @abstractmethod
    def execute_action(self, action_type, params, context) -> Dict: ...
```

可选的增强方法（OodaOrchestrator 会探测是否存在）：

```python
def build_llm_context(self, db) -> Dict          # 注入 LLM 上下文
def enhance_action_params(self, action_type, params, message, db) -> Dict  # 参数增强
def get_field_definition(self, param_name, action_type, ...) -> MissingField  # 字段 UI 定义
def get_report_data(self, db) -> Dict             # 报表数据
def get_admin_roles(self) -> List[str]            # 管理员角色列表
def get_query_examples(self) -> List[Dict]        # LLM Prompt 示例
```

### 4.5 Guard 系统

**GuardExecutor**（`guard_executor.py`）在 Action 执行前做统一预检查：

```
dispatch(action) → GuardExecutor.check() → [状态机校验, 约束校验, 角色校验] → 执行
```

```python
guard = GuardExecutor(ontology_registry, state_machine_executor)
result = guard.check(
    entity="Room",
    action="checkin",
    params={"room_id": 201},
    context={"current_state": "OCCUPIED", "user": user}
)
if not result.allowed:
    # result.violations 包含所有违规信息
    # result.suggestions 包含建议操作
```

**StateMachineExecutor**（`state_machine_executor.py`）校验状态转换：

```python
executor = StateMachineExecutor(registry)
result = executor.validate_transition("Room", "OCCUPIED", "VACANT_CLEAN")
# result.allowed = False
# result.reason = "No transition from OCCUPIED to VACANT_CLEAN"
# result.valid_alternatives = ["VACANT_DIRTY"]
```

---

## 5. core/ai/ — AI 编排层

AI 编排层是 core/ 中**最大**也是**最复杂**的模块，处理从用户输入到 AI 响应的完整流程。

### 5.1 OodaOrchestrator — 主编排器

`ooda_orchestrator.py`（1,923 行）是整个 AI 管道的入口。

**核心方法**：

```python
class OodaOrchestrator:
    def process_message(self, message, user, conversation_history,
                        topic_id, follow_up_context, language) -> Dict:
        """主入口 — 包装 _process_message_inner() 并管理会话生命周期"""
        # 1. LLMCallContext.begin_session()
        # 2. 创建 DebugSession
        # 3. 调用 _process_message_inner()
        # 4. finally: LLMCallContext.end_session()

    def _process_message_inner(self, message, user, ...) -> Dict:
        """OODA 循环的核心实现"""
        # OBSERVE: 捕获输入
        # ORIENT:  话题相关性检查（LLM 调用或规则）
        # DECIDE:  生成 Action（OAG 快速路径 or LLM chat）
        # ACT:     执行 Action，格式化结果
```

**依赖注入**（构造函数参数）：

| 参数 | 类型 | 作用 |
|------|------|------|
| `db` | Session | SQLAlchemy 数据库会话 |
| `adapter` | IDomainAdapter | 领域操作接口 |
| `llm_service` | LLMService | LLM 调用（来自 app 层） |
| `system_command_handler` | Handler | 系统命令处理 |
| `action_registry_factory` | Callable | 延迟获取 ActionRegistry |
| `missing_field_class` | Class | MissingField 构造器 |
| `descriptive_summary_fn` | Callable | 查询结果摘要生成 |
| `model_resolver` | Callable | ORM model 解析 |
| `domain_rules_init` | Callable | 业务规则初始化 |
| `domain_action_keywords` | List | 额外的关键词列表 |

**OAG 快速路径**（不走完整 LLM 对话，延迟更低）：

```python
def _try_oag_path(self, message, user) -> Dict | None:
    """OAG = Ontology-Action-Generation"""
    # 1. IntentRouter: 基于关键词和注册表的意图路由
    # 2. 如果是查询 → _oag_handle_query() → QueryCompiler → QueryEngine
    # 3. 如果是变更 → _oag_handle_mutation() → LLM 参数提取 → 执行
    # 4. 置信度 < 0.7 → 返回 None，降级到完整 LLM 路径
```

### 5.2 ActionRegistry — Action 注册与分发

`actions.py` 提供声明式的 Action 注册和类型安全的分发。

**注册**：

```python
registry = ActionRegistry()

@registry.register(
    name="create_task",
    entity="Task",
    description="创建任务",
    category="mutation",
    requires_confirmation=False,
    allowed_roles={"receptionist", "manager"},
    risk_level="low",
    undoable=True,
    side_effects=["notify_assignee"],
    search_keywords=["任务", "清洁", "维修", "打扫"],
)
def handle_create_task(params: CreateTaskParams, db: Session, user, **context) -> Dict:
    # 实现逻辑
    return {"success": True, "message": "任务已创建"}
```

**分发**：

```python
result = registry.dispatch("create_task", {"room_number": "301"}, context)
# 1. 查找 ActionDefinition
# 2. Pydantic 参数验证
# 3. GuardExecutor 预检查
# 4. 调用 handler 函数
```

**ActionDefinition 关键字段**：

| 字段 | 类型 | 用途 |
|------|------|------|
| `name` | str | Action 注册名 |
| `parameters_schema` | Pydantic BaseModel | 参数验证模型 |
| `handler` | Callable | 处理函数 |
| `param_enhancer` | Callable | 可选的参数增强（DB 数据填充） |
| `search_keywords` | List[str] | 向量搜索关键词 |
| `semantic_category` | str | 语义分类 |
| `glossary_examples` | List[str] | 领域术语示例 |

**同步到 OntologyRegistry**：

```python
registry.set_ontology_registry(ontology_registry)
# 自动将所有 ActionDefinition 转换为 ActionMetadata 注册到 OntologyRegistry
```

### 5.3 PromptBuilder — 动态 Prompt 构建

`prompt_builder.py` 从 OntologyRegistry 动态生成 LLM 系统提示。

```python
builder = PromptBuilder(ontology_registry)
context = PromptContext(
    user_role="receptionist",
    current_date=date.today(),
    include_actions=True,
    include_rules=True,
)
system_prompt = builder.build_system_prompt(context)
```

**Prompt 组成部分**：

1. 基础系统模板
2. 角色上下文（user_role, user_id）
3. 实体描述（属性、关系，来自 Registry）
4. Action 描述（参数来自 Pydantic schema）
5. 状态机定义
6. 业务规则
7. 权限矩阵（仅管理员可见）
8. 日期上下文（今天、明天、后天）
9. 语义查询语法指南
10. 领域术语表（来自 ActionRegistry）

**系统实体过滤**：非管理员用户不注入系统实体（角色、权限、部门等），除非消息中包含系统关键词。

### 5.4 LLMClient — LLM 抽象

`llm_client.py` 提供统一的 LLM 调用接口：

```python
class LLMClient(ABC):
    @abstractmethod
    def chat(self, messages, temperature, max_tokens, response_format, stream) -> LLMResponse: ...

class OpenAICompatibleClient(LLMClient):
    """兼容 OpenAI、DeepSeek、Azure、Ollama"""
```

`extract_json_from_text(text)` 是一个重要的工具函数，从 LLM 的自由文本响应中提取 JSON：
- 处理 markdown 代码块 (\`\`\`json ... \`\`\`)
- 容忍尾部逗号、单引号、注释
- 容忍转义的换行符

### 5.5 LLMCallContext — 线程本地上下文

`llm_call_context.py` 使用 `threading.local()` 在 OODA 流程中传递调试上下文，无需修改函数签名：

```python
# process_message() 入口
LLMCallContext.begin_session(session_id, debug_logger)

# 每次 LLM 调用前
LLMCallContext.before_call("orient", "topic_relevance")

# LLM 服务内部自动获取上下文
ctx = LLMCallContext.get_current()
# ctx = {"session_id": "...", "ooda_phase": "orient", "call_type": "topic_relevance", ...}

# process_message() finally 块
LLMCallContext.end_session()
```

### 5.6 DebugLogger — 会话追踪

`debug_logger.py` 使用 SQLite 持久化存储所有 AI 会话的完整追踪信息。

**三张表**：

| 表 | 内容 |
|----|------|
| `debug_sessions` | 会话生命周期（输入、用户、结果、状态、耗时） |
| `attempt_logs` | 执行尝试记录 |
| `llm_interactions` | 单次 LLM API 调用详情（OODA 阶段、延迟、Token 用量、Prompt/Response） |

**关键 API**：

```python
logger = DebugLogger("data/debug_logs.db")
session_id = logger.create_session("查看空房", user)
logger.log_llm_interaction(session_id, sequence=0, ooda_phase="orient", ...)
logger.log_attempt(session_id, action_name="ontology_query", ...)
logger.complete_session(session_id, result, status="completed", execution_time=1.23)
```

**注意**：DebugLogger 使用**文件 SQLite**，不能用 `:memory:`。因为 `_get_conn()` 每次创建新连接，`:memory:` 的每个连接看到的是不同的空数据库。测试中使用 `tempfile.mkstemp()`。

### 5.7 ReflexionLoop — 自修复执行

`reflexion.py` 在 Action 执行失败时自动尝试修复：

```
首次执行 → 失败
  ↓
自动修正（规则）：日期格式、枚举大小写、数字转换
  ↓ 如果修正失败
LLM 反思：分析错误原因，生成修正参数
  ↓
重试执行（最多 2 次）
  ↓ 如果仍失败
规则引擎降级
```

**自动修正示例**：
- 日期格式：`"2026-2-8"` → `"2026-02-08"`
- 枚举规范：`"active"` → `"ACTIVE"`，`"vacant clean"` → `"vacant_clean"`
- 数字字符串：`"301"` → `301`

### 5.8 IntentRouter — 意图路由

`intent_router.py` 提供不走 LLM 的快速意图识别：

```
Stage 1: 关键词精确匹配 → 候选列表
Stage 2: 实体类型过滤
Stage 3: 状态机可行性检查
Stage 4: 角色权限过滤
→ 置信度评分（1 候选=0.95，2-3=0.6，4+=0.3）
```

### 5.9 QueryCompiler — 查询编译

`query_compiler.py` 将意图提取结果编译为 SemanticQuery：

```
ExtractedQuery（实体提示 + 条件 + 时间上下文）
  ↓ OntologyQueryCompiler.compile()
CompilationResult（SemanticQuery + 置信度 + 推理过程）
```

四步编译：
1. 实体解析（名称 → 描述 → display_name 模糊匹配）
2. 字段解析（hint → PropertyMetadata）
3. 别名替换（"空房" → status=vacant_clean）
4. 构建 SemanticFilter

### 5.10 ResponseGenerator — 响应生成

`response_generator.py` 是**不调用 LLM** 的模板格式化器，用于确定性输出：

```python
generator = ResponseGenerator()
text = generator.generate(OntologyResult(
    result_type="query_result",
    data={"rows": [...], "columns": [...]},
    entity_type="Room"
))
```

支持的 result_type：`query_result`、`action_confirmed`、`action_needs_confirm`、`missing_fields`、`constraint_violation`、`state_violation`、`error`。

---

## 6. core/ooda/ — OODA 循环抽象层

core/ooda/ 提供 OODA 四阶段的**纯抽象实现**，与 core/ai/ooda_orchestrator.py 中的**实际编排逻辑**互补。

### 6.1 四阶段

**ObservePhase**（`observe.py`）— 输入验证与归一化：

```python
# 可组合的 Validator 和 Normalizer
observe_phase.add_validator(NotEmptyValidator())
observe_phase.add_validator(MaxLengthValidator(500))
observe_phase.add_normalizer(TrimNormalizer())
observe_phase.add_normalizer(CollapseWhitespaceNormalizer())

observation = observe_phase.observe("  Hello World  ", context)
# observation.normalized_input = "Hello World"
# observation.is_valid = True
```

扩展点：实现自定义 `InputValidator` 或 `InputNormalizer` 子类。

**OrientPhase**（`orient.py`）— 上下文注入：

```python
orient.add_context_provider(SecurityContextProvider())    # 安全上下文
orient.add_context_provider(StaticContextProvider({...})) # 静态数据
orient.add_context_provider(CompositeContextProvider([...]))

orientation = orient.orient(observation)
# orientation.intent = IntentResult(action_type="checkin", confidence=0.95, ...)
# orientation.context = {"user_role": "receptionist", ...}
```

扩展点：实现自定义 `ContextProvider` 子类。

**DecidePhase**（`decide.py`）— 决策生成：

```python
decide.add_rule(IntentBasedRule(
    action_type="checkin",
    required_params=["reservation_id", "room_id"]
))
decision = decide.decide(orientation)
# decision.action_type = "checkin"
# decision.missing_fields = [{"field_name": "room_id", ...}]
# decision.requires_confirmation = True（高风险操作）
```

扩展点：实现自定义 `DecisionRule` 子类。

**ActPhase**（`act.py`）— 执行：

```python
act.add_handler(DelegatingActionHandler({
    "checkin": checkin_service.execute,
    "checkout": checkout_service.execute
}))
result = act.act(decision, skip_confirmation=False)
```

扩展点：实现自定义 `ActionHandler` 子类。

### 6.2 OodaLoop 编排

```python
loop = OodaLoop(observe_phase, orient_phase, decide_phase, act_phase)
result = loop.execute("帮客人办理入住", context={"hotel_id": 1})
# result.observation  — Observe 阶段输出
# result.orientation  — Orient 阶段输出
# result.decision     — Decide 阶段输出
# result.action_result — Act 阶段输出
# result.success
# result.requires_confirmation
```

**注意**：实际生产中使用的是 `core/ai/ooda_orchestrator.py` 中的 `OodaOrchestrator`，它是更实际的编排实现。`core/ooda/` 更多用于结构化抽象和测试。

---

## 7. core/engine/ — 引擎基础设施

### 7.1 EventBus（`event_bus.py`）

线程安全的发布/订阅事件系统：

```python
from core.engine import event_bus

# 订阅
event_bus.subscribe("ROOM_STATUS_CHANGED", handle_room_change)

# 发布
event_bus.publish(Event(
    event_type="ROOM_STATUS_CHANGED",
    data={"room_id": 201, "old_status": "occupied", "new_status": "vacant_dirty"}
))
```

**关键特性**：
- 错误隔离：一个 handler 抛异常不影响其他 handler
- 事件历史：可配置的环形缓冲区
- 统计信息：按事件类型的发布/处理/失败计数
- 线程安全：RLock 保护订阅管理

**注意**：测试环境中事件不会自动触发。需要手动调用 `EventHandlers.register_handlers()`。

### 7.2 RuleEngine（`rule_engine.py`）

基于条件的规则引擎：

```python
from core.engine import rule_engine

rule_engine.register_rule(Rule(
    rule_id="late_checkout_penalty",
    name="逾期退房加收",
    entity_type="StayRecord",
    condition=FunctionCondition(lambda ctx: ctx.metadata.get("hours_late", 0) > 2),
    action=lambda ctx: {"penalty": ctx.metadata["hours_late"] * 50},
    priority=10
))

results = rule_engine.evaluate(RuleContext(
    entity_type="StayRecord",
    action="checkout",
    params={"stay_id": 123},
    metadata={"hours_late": 3}
))
```

### 7.3 StateMachine（`state_machine.py`）

状态机引擎（实例级）：

```python
from core.engine import state_machine_engine, StateMachine, StateMachineConfig, StateTransition

config = StateMachineConfig(
    name="room_lifecycle",
    states=["VACANT_CLEAN", "OCCUPIED", "VACANT_DIRTY"],
    transitions=[
        StateTransition("VACANT_CLEAN", "OCCUPIED", trigger="check_in"),
        StateTransition("OCCUPIED", "VACANT_DIRTY", trigger="check_out"),
        StateTransition("VACANT_DIRTY", "VACANT_CLEAN", trigger="clean"),
    ],
    initial_state="VACANT_CLEAN"
)

machine = StateMachine(config)
machine.transition_to("OCCUPIED", trigger="check_in")
# 成功：当前状态变为 OCCUPIED
```

### 7.4 SnapshotEngine（`snapshot.py`）

操作快照，支持撤销：

```python
from core.engine import snapshot_engine

snapshot = snapshot_engine.create_snapshot(
    operation_type="checkin",
    entity_type="StayRecord",
    entity_id=123,
    before_state={"status": "pending"},
    rollback_func=lambda: undo_checkin(123)
)

# 撤销
snapshot_engine.undo(snapshot.id)
```

### 7.5 AuditEngine（`audit.py`）

审计日志：

```python
from core.engine import audit_engine, AuditSeverity

audit_engine.log(
    operator_id=user.id,
    action="room.update_status",
    entity_type="Room",
    entity_id=201,
    old_value='{"status": "vacant_clean"}',
    new_value='{"status": "occupied"}',
    severity=AuditSeverity.INFO
)
```

---

## 8. core/security/ — 安全与权限

### 8.1 SecurityContext（`context.py`）

线程本地的安全上下文，支持嵌套：

```python
from core.security import security_context_manager, SecurityContext

ctx = SecurityContext(user_id=1, username="alice", role="manager",
                      security_level=SecurityLevel.RESTRICTED)
security_context_manager.set_context(ctx)

# 嵌套上下文（如 sudo 模式）
with security_context_manager.enter_context(admin_ctx):
    sensitive_operation()  # 以 admin 身份执行
# 自动恢复到 alice 的上下文
```

### 8.2 AttributeACL（`attribute_acl.py`）

属性级访问控制，基于安全等级层级：

```python
from core.security import attribute_acl, AttributePermission, SecurityLevel

attribute_acl.register_attribute(AttributePermission(
    entity_type="Guest",
    attribute="phone",
    security_level=SecurityLevel.CONFIDENTIAL,
    allow_read=True,
    allow_write=False
))

can_read = attribute_acl.can_read("Guest", "phone", context)
filtered = attribute_acl.filter_attributes("Guest", all_attrs, context)
```

### 8.3 PermissionChecker（`checker.py`）

基于规则链的权限检查，支持通配符和 LRU 缓存：

```python
from core.security import permission_checker, Permission

permission_checker.register_role_permissions("manager", [
    Permission(resource="room", action="*"),    # 通配符
    Permission(resource="guest", action="read"),
])

# 检查
permission_checker.check_permission("room:update_status")

# 装饰器
@permission_checker.require_permission("room:delete")
def delete_room(room_id): ...
```

### 8.4 DataMasker（`masking.py`）

PII 数据自动脱敏：

```python
from core.security import data_masker

masked = data_masker.mask("phone", "13800138000", context)
# 如果用户安全等级不够："138****8000"

masked_dict = data_masker.mask_dict(guest_data, context)
# 递归脱敏 dict 中所有敏感字段
```

预注册规则：phone、email、id_card、name、address、bank_card。

### 8.5 IPermissionProvider（`permission.py`）

app 层实现的 RBAC 提供器接口：

```python
class IPermissionProvider(ABC):
    def has_permission(self, user_id, permission_code) -> bool: ...
    def get_user_permissions(self, user_id) -> Set[str]: ...
    def get_user_roles(self, user_id) -> List[str]: ...
```

---

## 9. core/reasoning/ — 推理与约束

### 9.1 ConstraintEngine（`constraint_engine.py`）

约束验证引擎，从 OntologyRegistry 自动加载约束：

```python
engine = ConstraintEngine(registry)

# Action 级验证
result = engine.validate_action(
    entity_type="Guest",
    action_type="create",
    params={"phone": "12345"},
    current_state=system_state,
    user_context={"role": "receptionist"}
)
# result.is_valid = False
# result.violations = [{"constraint_name": "phone_format", ...}]

# 属性级验证（OAG 决策模型）
decision = engine.validate_property_update(
    entity_type="Guest",
    property_name="phone",
    old_value="13800000000",
    new_value="12345",
    user_context=user,
    db=session,
    entity_id=guest_id
)
```

**条件表达式**使用 AST 安全评估（不用 `eval()`）：

```python
# 支持的表达式格式
"state.guest.is_vip == True"
"param.room_count > 0"
"user.role in ['manager', 'admin']"
```

**自定义校验器**：

```python
class PhoneFormatValidator(IConstraintValidator):
    def validate(self, context: ConstraintEvaluationContext) -> Tuple[bool, Optional[str]]:
        phone = context.params.get("phone", "")
        if not re.match(r"^1[3-9]\d{9}$", phone):
            return False, "手机号格式不正确"
        return True, None
```

### 9.2 RelationshipGraph（`relationship_graph.py`）

实体关系图，支持 BFS/DFS 路径发现：

```python
graph = RelationshipGraph(registry)

# BFS 遍历
related = graph.get_related_nodes("Room", max_depth=2)

# 最短路径
path = graph.find_path("Guest", "Bill")

# 所有路径
all_paths = graph.get_all_paths("Guest", "Bill", max_length=5)

# LLM 可读的关系描述
desc = graph.get_relationships_for_llm("Room")
```

### 9.3 PlannerEngine（`planner.py`）

多步骤规划引擎（三级策略）：

```
1. 模板匹配（确定性，已注册的复合操作）
2. 本体推理（基于前置条件/效果的图搜索）[未来]
3. LLM 规划（通用降级）
```

```python
# 注册复合操作模板
template_registry.register(CompositeTemplate(
    name="change_room",
    trigger_action="change_room",
    steps=[
        TemplateStep(step_id="verify", action_type="verify_available", ...),
        TemplateStep(step_id="checkout", action_type="checkout", dependencies=["verify"]),
        TemplateStep(step_id="checkin", action_type="walkin_checkin", dependencies=["checkout"]),
    ]
))

# 展开模板
plan = template_registry.expand("change_room", {"stay_id": 1, "new_room": "305"})
```

### 9.4 DAGExecutor（`dag_executor.py`）

DAG 执行器（拓扑排序 + 快照回滚）：

```python
executor = DAGExecutor(
    action_dispatcher=registry.dispatch,
    guard_executor=guard,
    snapshot_engine=snapshot_engine
)
result = executor.execute(plan, context)
# 失败时自动反向回滚已完成步骤
```

---

## 10. 数据流全景

### 10.1 process_message() 完整流程

```
用户输入 (message, user, history, follow_up_context)
  │
  ├─── LLMCallContext.begin_session()
  ├─── DebugLogger.create_session()
  │
  │    ┌── OBSERVE ──────────────────────────────┐
  │    │ 捕获输入，创建调试会话                      │
  │    └─────────────────────────────────────────┘
  │
  │    ┌── ORIENT ───────────────────────────────┐
  │    │ 话题相关性检查                              │
  │    │ ├─ LLM: orient/topic_relevance          │
  │    │ └─ 结果: continuation | followup_answer  │
  │    │          | new_topic                     │
  │    └─────────────────────────────────────────┘
  │
  │    ┌── DECIDE ───────────────────────────────┐
  │    │ 生成 Action                               │
  │    │ ├─ OAG 快速路径（IntentRouter + QueryCompiler）│
  │    │ │  └─ 置信度 ≥ 0.7 → 直接执行               │
  │    │ ├─ LLM: decide/chat                     │
  │    │ └─ 规则降级（无 LLM 时）                     │
  │    └─────────────────────────────────────────┘
  │
  │    ┌── ACT ──────────────────────────────────┐
  │    │ 执行 + 格式化                               │
  │    │ ├─ 查询: QueryEngine.execute()           │
  │    │ ├─ 变更: ActionRegistry.dispatch()       │
  │    │ │  └─ GuardExecutor → Handler → DB       │
  │    │ └─ LLM: act/format_result（可选）          │
  │    └─────────────────────────────────────────┘
  │
  ├─── DebugLogger.complete_session()
  ├─── LLMCallContext.end_session()  [finally]
  │
  └─── 返回结果 Dict
```

### 10.2 查询管道

```
自然语言 "还有空房吗"
  ↓ OodaOrchestrator._try_oag_path()
  ↓ IntentRouter.route() → RoutingResult(action="ontology_query", confidence=0.95)
  ↓ QueryCompiler.compile(ExtractedQuery) → SemanticQuery
  ↓ SemanticPathResolver.compile(SemanticQuery) → StructuredQuery
  ↓ QueryEngine.execute(StructuredQuery) → {"rows": [...], "columns": [...]}
  ↓ ResponseGenerator.generate() 或 LLM format_result
  ↓ 返回给用户
```

### 10.3 Action 分发管道

```
ActionRegistry.dispatch("walkin_checkin", params, context)
  ↓ 查找 ActionDefinition
  ↓ Pydantic 参数验证（parameters_schema）
  ↓ param_enhancer（可选，DB 数据填充）
  ↓ GuardExecutor.check()
  │  ├─ StateMachineExecutor.validate_transition()
  │  ├─ ConstraintEngine.validate_action()
  │  └─ 角色权限检查
  ↓ handler(params, db, user, **context)
  ↓ 返回 {"success": True, "message": "..."}
```

### 10.4 LLM 可观测性链路

```
LLMCallContext.begin_session(session_id, debug_logger)
  ↓
每次 LLM 调用前:
  LLMCallContext.before_call("orient", "topic_relevance")
  ↓
  llm_service._instrumented_completion()
    ↓ OpenAICompatibleClient.chat()
    ↓ debug_logger.log_llm_interaction(session_id, sequence, phase, ...)
    ↓ LLMCallContext.next_sequence()
  ↓
debug_logger.complete_session()
LLMCallContext.end_session()  [finally]
```

---

## 11. 测试体系

### 11.1 测试文件分布

| 目录 | 文件数 | 行数 | 聚焦 |
|------|--------|------|------|
| `tests/core/` | ~51 | ~17,000 | core/ 层的单元和集成测试 |
| `tests/domain/` | ~20 | ~3,000 | 领域模型、关系、状态机 |
| `tests/services/actions/` | - | - | Action Handler 测试 |
| `tests/api/` | - | - | API 端点测试 |
| `tests/benchmark/` | - | - | 真实 LLM 端到端测试 |

### 11.2 关键 Fixture 模式

**模式 1：Clean Registry**（用于元数据/注册表测试）

```python
@pytest.fixture(autouse=True)
def clean_registry():
    """每个测试前后清理 OntologyRegistry 单例"""
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()
```

**模式 2：Populated Registry**（需要预注册数据的测试）

```python
@pytest.fixture
def populated_registry(clean_registry):
    clean_registry.register_entity(EntityMetadata(name="Room", ...))
    clean_registry.register_action("Room", ActionMetadata(...))
    clean_registry.register_state_machine(StateMachine(...))
    return clean_registry
```

**模式 3：Bootstrap Adapter**（需要完整 Hotel 元数据的测试）

```python
@pytest.fixture(autouse=True, scope="module")
def _bootstrap_adapter():
    from core.ontology.registry import OntologyRegistry
    from app.hotel.hotel_domain_adapter import HotelDomainAdapter
    registry = OntologyRegistry()
    adapter = HotelDomainAdapter()
    adapter.register_ontology(registry)
```

**模式 4：Tempfile Database**（DebugLogger 测试）

```python
@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass

@pytest.fixture
def logger(temp_db):
    return DebugLogger(temp_db)
```

**模式 5：线程隔离测试**（LLMCallContext）

```python
def setup_method(self):
    LLMCallContext.end_session()  # 确保干净状态

def test_thread_isolation(self):
    results = {}
    def thread_fn(thread_id, session_id):
        LLMCallContext.begin_session(session_id, f"logger_{thread_id}")
        ctx = LLMCallContext.get_current()
        results[thread_id] = ctx["session_id"]
        LLMCallContext.end_session()

    t1 = threading.Thread(target=thread_fn, args=(1, "sess-A"))
    t2 = threading.Thread(target=thread_fn, args=(2, "sess-B"))
    t1.start(); t2.start(); t1.join(); t2.join()
    assert results[1] == "sess-A"
    assert results[2] == "sess-B"
```

### 11.3 运行测试

```bash
cd backend

# core/ 全部测试
uv run pytest tests/core/ -v

# 架构守卫测试
uv run pytest tests/domain/test_domain_separation.py -v

# 单个模块
uv run pytest tests/core/test_registry.py -v
uv run pytest tests/core/test_semantic_path_resolver.py -v

# 按名称匹配
uv run pytest -k "test_compile_simple" -v

# 跳过覆盖率
uv run pytest tests/core/ --no-cov
```

### 11.4 写新测试的 Checklist

```
□ 选择正确的 Fixture 模式（Clean Registry vs Bootstrap Adapter）
□ OntologyRegistry 测试必须使用 clean_registry fixture
□ DebugLogger 测试必须使用 tempfile，不能用 :memory:
□ LLMCallContext 测试必须在 setup_method 中 end_session()
□ 不在 core/ 测试中引入 app/ 模型（除非是 Bootstrap Adapter 模式）
□ 测试文件放在 tests/core/ 目录下
□ 测试名称遵循 test_<module>_<feature>.py 模式
```

---

## 12. 常见维护任务 Cookbook

### 12.1 给 QueryEngine 添加新的 FilterOperator

**场景**：需要支持 `CONTAINS` 操作符用于数组字段查询。

**步骤**：

1. **修改 `core/ontology/query.py`**：在 `FilterOperator` 枚举中添加新值

```python
class FilterOperator(str, Enum):
    # ... 现有操作符
    CONTAINS = "contains"
```

2. **修改 `core/ontology/query_engine.py`**：在 `_apply_operator()` 中添加处理

```python
def _apply_operator(self, attr, operator, value):
    # ... 现有逻辑
    elif operator == FilterOperator.CONTAINS:
        return attr.contains(value)
```

3. **修改 `core/ai/prompt_builder.py`**：在语义查询语法指南中添加示例

4. **添加测试**：`tests/core/test_ontology_query.py`

```python
def test_contains_operator(self, ...):
    query = StructuredQuery(
        entity="Task",
        filters=[FilterClause(field="description", operator=FilterOperator.CONTAINS, value="清洁")]
    )
    result = engine.execute(query)
    assert len(result["rows"]) > 0
```

5. **运行守卫**：`uv run pytest tests/domain/test_domain_separation.py -v`

### 12.2 给 PromptBuilder 添加新的 Prompt 段

**场景**：需要在系统 Prompt 中注入"当前时段繁忙度"信息。

**步骤**：

1. **修改 `core/ai/prompt_builder.py`**：

```python
class PromptContext:
    # ... 现有字段
    include_workload: bool = False
    workload_data: Dict[str, Any] = field(default_factory=dict)

class PromptBuilder:
    def build_system_prompt(self, context=None, base_template=None):
        # ... 现有逻辑
        if context and context.include_workload and context.workload_data:
            sections.append(self._build_workload_section(context.workload_data))

    def _build_workload_section(self, data: Dict) -> str:
        return f"## 当前工作负载\n{json.dumps(data, ensure_ascii=False)}"
```

2. **app 层使用**（由 app 层工程师完成）：

```python
context = PromptContext(
    include_workload=True,
    workload_data=adapter.get_current_workload(db)
)
```

3. **测试**：`tests/core/test_prompt_builder.py`

### 12.3 给 ActionRegistry 添加新的 Action 属性

**场景**：需要给 Action 加上 `timeout_seconds` 超时配置。

**步骤**：

1. **修改 `core/ai/actions.py`**：

```python
@dataclass
class ActionDefinition:
    # ... 现有字段
    timeout_seconds: Optional[int] = None  # Action 执行超时

class ActionRegistry:
    def register(self, *, timeout_seconds=None, **kwargs):
        # ... 现有逻辑
        definition.timeout_seconds = timeout_seconds
```

2. **在 `dispatch()` 中添加超时逻辑**（如果需要强制超时）

3. **同步到 OntologyRegistry**：如果需要在 metadata 中暴露，修改 `set_ontology_registry()` 的转换逻辑

4. **测试**：`tests/core/test_actions.py`

### 12.4 给 SemanticPathResolver 添加新的路径解析能力

**场景**：支持聚合路径如 `stays.COUNT` 或 `bills.SUM(amount)`。

**步骤**：

1. **修改 `core/ontology/semantic_query.py`**：扩展 `SemanticFilter` 支持聚合表达式

2. **修改 `core/ontology/semantic_path_resolver.py`**：

```python
def _is_aggregate_path(self, path: str) -> bool:
    """检测是否为聚合路径"""
    return any(agg in path.upper() for agg in ["COUNT", "SUM", "AVG", "MAX", "MIN"])

def compile(self, semantic_query):
    # ... 现有逻辑
    # 在 compile 末尾检查聚合路径
    if any(self._is_aggregate_path(f) for f in semantic_query.fields):
        return self._compile_aggregate(semantic_query, structured)
```

3. **测试**：`tests/core/test_semantic_path_resolver.py`

### 12.5 给 ConstraintEngine 添加自定义校验器

**场景**：需要校验供应商名称不能包含特殊字符。

**步骤**：

1. **实现校验器**（放在 app/ 层，不在 core/ 中）：

```python
# app/hotel/validators/supplier_validators.py
from core.reasoning.constraint_engine import IConstraintValidator

class SupplierNameValidator(IConstraintValidator):
    def validate(self, context):
        name = context.params.get("name", "")
        if re.search(r'[<>"\'/\\]', name):
            return False, "供应商名称不能包含特殊字符"
        return True, None
```

2. **注册约束**（在 Domain Adapter 的 `register_ontology()` 中）：

```python
registry.register_constraint(ConstraintMetadata(
    id="supplier_name_no_special_chars",
    entity="Supplier",
    action="create",
    validator=SupplierNameValidator(),
    error_message="供应商名称不能包含特殊字符"
))
```

3. **不需要修改 core/**：ConstraintEngine 自动加载并执行。

### 12.6 给 DebugLogger 添加新的追踪字段

**场景**：需要在 `llm_interactions` 表中记录 `request_id` 用于关联外部 API 日志。

**步骤**：

1. **修改 `core/ai/debug_logger.py`**：

```python
# LLMInteraction dataclass
@dataclass
class LLMInteraction:
    # ... 现有字段
    request_id: Optional[str] = None

# _init_db() 中的建表 SQL
CREATE TABLE IF NOT EXISTS llm_interactions (
    -- ... 现有列
    request_id TEXT
)

# log_llm_interaction() 参数
def log_llm_interaction(self, ..., request_id=None):
    # INSERT INTO llm_interactions (..., request_id) VALUES (..., ?)

# _migrate_schema() 自动迁移
def _migrate_schema(self):
    # 检查列是否存在，不存在则 ALTER TABLE ADD COLUMN
```

2. **修改 `core/ai/llm_call_context.py`**（如果需要自动传递 request_id）

3. **测试**：`tests/core/test_debug_logger_llm.py`

---

## 13. Bug 排查手册

### 13.1 查询返回空结果

**症状**：用户说"查空房"，系统返回空列表。

**排查步骤**：

```
1. 检查 DebugLogger 中的会话记录
   → 确认 action_type 是否为 ontology_query
   → 查看 LLM 生成的 SemanticQuery JSON

2. 手动执行 SemanticQuery
   → resolver.compile(semantic_query)
   → 检查生成的 StructuredQuery 的 filters 和 joins

3. 常见原因：
   a. 字段名映射错误："空房" → 应该是 status=vacant_clean，但可能映射成了别的
   b. JOIN 路径错误：关系名在 OntologyRegistry 中未注册
   c. 枚举值大小写：数据库存的是 UPPERCASE，但 filter 用了 lowercase
   d. 默认字段缺失：_get_default_fields() 没有返回有用字段

4. 修复后验证：
   → uv run pytest tests/core/test_ontology_query.py -v
   → uv run pytest tests/core/test_semantic_path_resolver.py -v
```

### 13.2 Action 分发失败

**症状**：ActionRegistry.dispatch() 抛出异常或返回错误。

**排查步骤**：

```
1. 确认 Action 已注册
   → registry.get_action("action_name")
   → 如果是 None，检查 app/services/actions/__init__.py 的注册逻辑

2. 检查参数验证
   → Pydantic BaseModel 验证是否通过
   → 必填字段是否都提供了

3. 检查 Guard 执行
   → GuardExecutor.check() 的返回值
   → 状态机是否允许当前转换
   → 约束是否满足

4. 检查 Handler 执行
   → Handler 函数的异常堆栈
   → DB 操作是否成功
```

### 13.3 LLM 调用超时或失败

**症状**：process_message() 长时间无响应或返回错误。

**排查步骤**：

```
1. 检查环境变量
   → OPENAI_API_KEY 是否设置
   → OPENAI_BASE_URL 是否可达
   → ENABLE_LLM 是否为 true

2. 检查 LLMCallContext 状态
   → 是否有未清理的会话（end_session 未执行）
   → 线程本地存储是否泄漏

3. 检查 DebugLogger
   → llm_interactions 表中的最近记录
   → latency_ms 是否异常
   → success 字段是否为 false

4. 检查 Prompt 大小
   → PromptBuilder 生成的 system_prompt 是否过大
   → 实体/Action 数量是否导致超过 Token 限制
```

### 13.4 OntologyRegistry 状态不一致

**症状**：在测试中 Registry 包含前一个测试的残留数据。

**排查步骤**：

```
1. 确认是否使用了 clean_registry fixture
   → 必须是 autouse=True, scope="function"

2. 如果是 module scope 的 bootstrap fixture
   → 确保不会与 clean_registry 冲突
   → 一个测试文件中只用一种模式

3. 如果是并发测试
   → OntologyRegistry 是单例，不是线程安全的
   → 不同测试进程间会共享
```

### 13.5 SemanticPathResolver 路径解析失败

**症状**：`PathResolutionError: Cannot resolve 'xxx' at position N`。

**排查步骤**：

```
1. 查看错误消息中的 suggestions
   → 通常会给出 fuzzy 匹配的正确路径

2. 检查关系是否注册
   → registry.get_relationships("SourceEntity")
   → 确认目标关系名存在

3. 常见原因：
   a. 复数/单数问题："stay" vs "stays" vs "stay_records"
   b. 关系名 vs 实体名混淆
   c. 关系方向错误（应该从 Guest→StayRecord 而不是反向）

4. 使用 suggest_paths() 调试：
   → resolver.suggest_paths("Guest", max_depth=2)
```

---

## 14. 性能调优

### 14.1 查询优化

| 问题 | 优化方向 |
|------|---------|
| JOIN 过多导致慢查询 | 检查 SemanticQuery 的 hop_count，限制在 3 以内 |
| 结果集过大 | 确保 StructuredQuery.limit 有合理默认值（当前 100） |
| 聚合查询慢 | 使用 QueryEngine 的 `_execute_aggregate_query()` 专用路径 |
| 重复查询 | 考虑在 QueryEngine 上层添加缓存 |

### 14.2 Prompt 优化

| 问题 | 优化方向 |
|------|---------|
| Prompt 过长导致 Token 开销大 | 使用 PromptContext 的 include_* 开关精细控制 |
| 系统实体注入给非管理员 | 已由 SPEC-23 系统实体过滤处理 |
| Action 描述过多 | 使用 VectorStore 的 `get_relevant_tools()` 只注入相关 Action |

### 14.3 ActionRegistry 优化

| 问题 | 优化方向 |
|------|---------|
| 向量搜索慢 | `reindex_all_actions()` 重建索引 |
| 分发开销 | Pydantic 验证是主要开销，确保 schema 精简 |

### 14.4 DebugLogger 优化

| 问题 | 优化方向 |
|------|---------|
| SQLite 文件过大 | `cleanup_old_sessions(days=30)` 定期清理 |
| 写入阻塞 | SQLite WAL 模式已启用 |

---

## 15. 版本演进与兼容性

### 15.1 修改 core/ 代码时的兼容性规则

| 修改类型 | 影响范围 | 处理方式 |
|---------|---------|---------|
| 给 dataclass 添加可选字段 | 低 | 提供默认值即可 |
| 给 Registry 添加新的 register_* 方法 | 低 | 不影响现有 adapter |
| 修改 Registry 的 get_* 返回结构 | 高 | 需要检查所有调用方 |
| 修改 ActionDefinition 字段名 | 高 | 需要同步修改 app/ 层的注册代码 |
| 修改 QueryEngine 的结果格式 | 高 | 前端和测试都依赖 |
| 修改 FilterOperator 枚举 | 中 | LLM Prompt 和测试数据需要更新 |
| 修改 IDomainAdapter 的抽象方法 | 高 | 所有 adapter 实现都要改 |

### 15.2 安全的扩展模式

```python
# ✅ 安全：给现有 dataclass 添加可选字段
@dataclass
class ActionMetadata:
    # ... 现有字段
    timeout_seconds: Optional[int] = None  # 新增，有默认值

# ✅ 安全：给 Registry 添加新方法
class OntologyRegistry:
    def get_entities_by_category(self, category: str) -> List[EntityMetadata]:
        return [e for e in self._entities.values() if e.category == category]

# ❌ 危险：修改现有方法的签名
class OntologyRegistry:
    def get_entity(self, name: str, include_hidden: bool = False):  # 改了签名
        # 虽然有默认值，但可能破坏反射调用
```

### 15.3 修改前 Checklist

```
□ 运行架构守卫测试: uv run pytest tests/domain/test_domain_separation.py -v
□ 运行 core/ 全部测试: uv run pytest tests/core/ -v
□ 运行 domain/ 测试: uv run pytest tests/domain/ -v
□ 检查 app/ 层是否有使用被修改 API 的代码
□ 如果修改了查询相关代码，运行 benchmark 测试确认
□ 如果修改了 Prompt 相关代码，手动测试几轮对话确认 LLM 行为
```

---

## 附录 A：文件速查表

按**修改频率**排序（从高到低）：

| 文件 | 行数 | 修改场景 |
|------|------|---------|
| `core/ai/ooda_orchestrator.py` | 1,923 | OODA 流程调整、新增路径、参数处理 |
| `core/ai/prompt_builder.py` | 1,035 | Prompt 优化、新增注入段 |
| `core/ontology/query_engine.py` | 711 | 查询能力扩展、新操作符 |
| `core/ontology/semantic_path_resolver.py` | 663 | 路径解析 Bug、新关系类型 |
| `core/ai/actions.py` | 908 | Action 属性扩展、分发逻辑 |
| `core/ontology/metadata.py` | 753 | 元数据模型扩展 |
| `core/ontology/registry.py` | 1,033 | 注册/查询 API 扩展 |
| `core/ai/debug_logger.py` | 1,122 | 追踪字段扩展、性能优化 |
| `core/reasoning/constraint_engine.py` | 746 | 约束验证逻辑 |
| `core/ai/reflexion.py` | 913 | 自修复策略调整 |
| `core/ai/intent_router.py` | 423 | 意图识别优化 |
| `core/ai/query_compiler.py` | 407 | 查询编译逻辑 |
| `core/ai/response_generator.py` | 321 | 响应格式调整 |
| `core/ai/llm_client.py` | 438 | LLM 调用稳定性、JSON 解析 |
| `core/ai/llm_call_context.py` | 90 | 上下文传递扩展 |

---

## 附录 B：单例与全局状态清单

| 单例 | 位置 | 初始化时机 | 测试中如何重置 |
|------|------|-----------|-------------|
| `OntologyRegistry` | `core/ontology/registry.py` | 首次 `OntologyRegistry()` | `reg.clear()` |
| `event_bus` | `core/engine/__init__.py` | 模块导入时 | `event_bus.clear_subscribers()` |
| `rule_engine` | `core/engine/__init__.py` | 模块导入时 | - |
| `state_machine_engine` | `core/engine/__init__.py` | 模块导入时 | - |
| `snapshot_engine` | `core/engine/__init__.py` | 模块导入时 | - |
| `audit_engine` | `core/engine/__init__.py` | 模块导入时 | - |
| `security_context_manager` | `core/security/__init__.py` | 模块导入时 | `set_context(None)` |
| `permission_checker` | `core/security/__init__.py` | 模块导入时 | - |
| `attribute_acl` | `core/security/__init__.py` | 模块导入时 | - |
| `data_masker` | `core/security/__init__.py` | 模块导入时 | - |
| `EmbeddingService` | `core/ai/__init__.py` | `get_embedding_service()` 首次调用 | `reset_embedding_service()` |
| `LLMCallContext` | `core/ai/llm_call_context.py` | `threading.local()` 自动 | `LLMCallContext.end_session()` |
| `BusinessRuleRegistry` | `core/ontology/business_rules.py` | 模块导入时 | - |

**重要**：OntologyRegistry 是整个系统中**最关键的单例**。修改后必须确保所有测试的 `clean_registry` fixture 正常工作。

---

## 附录 C：环境变量参考

| 变量 | 默认值 | 影响的 core/ 模块 |
|------|--------|-----------------|
| `OPENAI_API_KEY` | (无) | `llm_client.py` — API 密钥 |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | `llm_client.py` — API 端点 |
| `LLM_MODEL` | `deepseek-chat` | `llm_client.py` — 模型名称 |
| `LLM_TEMPERATURE` | `0.7` | `llm_client.py` — 采样温度 |
| `LLM_MAX_TOKENS` | `2000` | `llm_client.py` — 最大输出 Token |
| `ENABLE_LLM` | `true` | `ooda_orchestrator.py` — 是否启用 LLM |
| `EMBEDDING_API_KEY` | `ollama` | `embedding.py` — Embedding 密钥 |
| `EMBEDDING_BASE_URL` | `http://localhost:11434/v1` | `embedding.py` — Embedding 端点 |
| `EMBEDDING_MODEL` | `nomic-embed-text` | `embedding.py` — Embedding 模型 |

**注意**：这些环境变量在 `core/ai/llm_client.py` 和 `core/ai/embedding.py` 中直接读取。app 层也可以通过 `backend/.env` 设置。
