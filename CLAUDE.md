# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Quick Reference

### Backend Commands
```bash
cd backend
uv sync                                    # Install dependencies
uv run python init_data.py                 # Initialize database
uv run uvicorn app.main:app --reload --port 8020  # Start server

# Testing
uv run pytest                              # All tests
uv run pytest tests/api/ -v                # API tests only
uv run pytest tests/core/ -v               # Core framework tests
uv run pytest tests/services/actions/ -v    # Action handlers tests
uv run pytest -k "test_name"               # Single test by name
```

### Frontend Commands
```bash
cd frontend
npm install && npm run dev                 # Dev server on http://localhost:3020
npm run build                              # Production build
```

### Combined
```bash
./start.sh                                 # Starts both backend and frontend
```

### Default Credentials
- sysadmin / 123456 (system admin - full access + system management)
- manager / 123456 (manager - business operations, no system settings)
- front1 / 123456 (receptionist)
- cleaner1 / 123456 (cleaner - tasks only)

---

## Semantique AI Architecture (New)

This system has evolved into a **semantic operating system** inspired by Palantir Foundry and AIP Logic, with four-layer architecture:

### Layer 1: Vector Semantic Search (`core/ai/vector_store.py`, `schema_retriever.py`)
- **VectorStore**: Pure-Python cosine similarity search (no external extension)
- **SchemaRetriever**: Retrieves relevant schema items by semantic similarity
- **EmbeddingService**: OpenAI-compatible embedding generation with caching
- Supports Top-K retrieval for entities, properties, and actions

### Layer 2: Action Registry (`core/ai/actions.py`, `app/services/actions/`)
- **ActionRegistry**: Declarative action registration replacing monolithic if/else chains
- **ActionDefinition**: Complete metadata (name, entity, description, parameters_schema, handler)
- Actions organized by domain: `guest_actions.py`, `stay_actions.py`, `task_actions.py`, `reservation_actions.py`, `query_actions.py`
- All actions use Pydantic models for validation (`app/services/actions/base.py`)
- Handler signature: `handler(params: BaseModel, db: Session, user: Employee, param_parser: ParamParserService) -> Dict`

### Layer 3: Semantic Path Compiler (`core/ontology/semantic_path_resolver.py`)
- **SemanticPathResolver**: Compiles LLM-friendly dot-notation paths into SQL JOINs
- Input: `SemanticQuery(root_object="Guest", fields=["stays.room.room_number"])`
- Output: `StructuredQuery` with auto-generated JoinClause list
- Error messages include "Did you mean?" suggestions for typos
- Uses SQLAlchemy Inspection API for automatic relationship discovery

### Layer 4: Reflexion Loop (`core/ai/reflexion.py`)
- **ReflexionLoop**: Self-healing execution with LLM-based error analysis
- Max retries: 2, then falls back to rule-based engine
- Error types: validation_error, not_found, permission_denied, value_error, state_error

### Key Design Patterns
- **Two-tier query**: LLM outputs `SemanticQuery` → Resolver compiles to `StructuredQuery` → QueryEngine executes SQL
- **Handler functions are NOT directly exported** - access via `ActionRegistry.dispatch(action_name, params, context)`
- **Date context injection**: LLM receives current_date, tomorrow, day-after for relative date parsing

---

## Ralph Loop 重构模式 (Active Refactoring)

本项目正在进行 **Ralph Loop** 模式架构重构，将系统重构为 **本体运行时框架 (core)** + **酒店业务本体 (domain)** 两层架构。

### 核心文件
- `docs/ralphloop/RALPH_LOOP_EXPERIENCE.md` - 双阶段分离模式和经验总结
- `docs/ralphloop/progress.txt` - 进度日志、坑点记录和迭代历史
- `docs/ontology-architecture-guide.md` - 完整的本体架构设计文档

### 行为约束

**🚨 挣扎信号 (STRUGGLE_SIGNAL)** - 必须立即停止并发出 `[STRUGGLE_SIGNAL]`：
- 在修复同一个 Bug 上失败了 2 次
- 开始"猜测" API 用法
- 连续 3 次尝试无法通过测试

**🛡️ 消除警觉性税** - 方案可行但有风险时，明确说明风险

### 工作流程

**Architect Phase**: 读取 progress.txt → 确认 SPEC → 探索代码 → 输出设计 → `<ARCHITECT_COMPLETE>`

**Editor Phase**: 读取设计文档 → 运行测试基准 → 精确修改 → 验证测试 → 更新 progress.txt → `<EDITOR_COMPLETE>` 或 `[STRUGGLE_SIGNAL]`

### 禁止事项
- ❌ 跳过测试验证
- ❌ 修改测试文件来让测试通过（除非任务明确要求）
- ❌ 一次性修改超过 3 个文件
- ❌ 重写整个文件（必须使用 SEARCH/REPLACE 块）

---

## Architecture

### Backend Structure
```
backend/
├── app/                          # Hotel business domain
│   ├── models/
│   │   ├── ontology.py           # Domain objects (Room, Guest, Reservation, StayRecord, Bill, Task, Employee)
│   │   ├── schemas.py            # Pydantic models for API I/O
│   │   ├── events.py             # Domain event definitions
│   │   └── snapshots.py          # OperationSnapshot for undo
│   ├── services/
│   │   ├── actions/              # NEW: Action handlers (guest, stay, task, reservation, query)
│   │   │   ├── base.py           # Pydantic parameter models
│   │   │   ├── __init__.py       # get_action_registry()
│   │   ├── ai_service.py         # OODA loop: LLM优先，规则兜底
│   │   ├── llm_service.py        # LLM integration
│   │   ├── event_bus.py          # Pub/sub event bus
│   │   └── ...                   # Other domain services
│   ├── routers/                  # FastAPI endpoints
│   ├── security/auth.py          # JWT + role-based access
│   └── main.py                   # App initialization
│
├── core/                         # Ontology runtime framework (domain-agnostic)
│   ├── ai/                       # NEW: AI core abstractions
│   │   ├── actions.py            # ActionRegistry, ActionDefinition
│   │   ├── vector_store.py       # VectorStore for semantic search
│   │   ├── schema_retriever.py   # SchemaRetriever for dynamic context
│   │   ├── embedding.py          # EmbeddingService
│   │   ├── reflexion.py          # ReflexionLoop for self-healing
│   │   ├── debug_logger.py       # DebugLogger with replay support
│   │   ├── hitl.py               # Human-in-the-loop strategies
│   │   └── prompt_builder.py     # Prompt construction
│   ├── ontology/                 # Entity abstractions
│   │   ├── base.py               # BaseEntity, ObjectProxy
│   │   ├── metadata.py           # EntityMetadata, ActionMetadata
│   │   ├── registry.py           # OntologyRegistry singleton
│   │   ├── query.py              # StructuredQuery, FilterClause, JoinClause
│   │   ├── query_engine.py       # QueryEngine for dynamic SQLAlchemy
│   │   ├── semantic_query.py     # NEW: SemanticQuery, SemanticFilter
│   │   └── semantic_path_resolver.py  # NEW: Path compiler (dot-notation → JOINs)
│   └── reasoning/                # NEW: Constraint and relationship reasoning
│       ├── planner.py            # Query planning
│       ├── constraint_engine.py  # Business rule validation
│       └── relationship_graph.py # Entity relationship graph
│
├── tests/
│   ├── api/                      # API integration tests (1000+ tests)
│   ├── core/                     # Core framework tests (600+ tests)
│   ├── services/actions/         # NEW: Action handler tests (190+ tests)
│   └── integration/             # End-to-end tests
│
└── aipms.db                      # SQLite database
```

### Three-Dimensional Metadata System
- **Semantic**: Entity attributes, types, constraints, relationships (via SQLAlchemy reflection)
- **Kinetic**: Executable operations/actions grouped by entity
- **Dynamic**: State machines, permission matrix, business rules

### Key Patterns

**Service Layer**: Each service class wraps a domain object family. Services handle validation, state transitions with side effects, and related object updates.

**OODA Loop (AI Service)**: `ai_service.process_message()` implements:
1. Observe: Capture natural language input
2. Orient: Identify intent + extract entities
3. Decide: Generate suggested actions with `requires_confirmation` flag
4. Act: Execute confirmed actions via domain services

**Event-Driven Architecture**: In-memory pub/sub with domain events (`GUEST_CHECKED_OUT`, `TASK_COMPLETED`) that trigger side effects.

**Operation Undo**: `OperationSnapshot` stores before/after state with 24-hour expiry. Supported: check_in, check_out, extend_stay, change_room, complete_task, add_payment.

---

## Query Action Handling (Critical)

**Bug Alert**: `ontology_query` and `query_smart` must be recognized as query actions to bypass parameter enhancement.

In `app/services/ai_service.py`, query actions are identified by:
```python
is_query_action = (
    action_type.startswith("query_") or
    action_type == "view" or
    action_type in ["ontology_query", "query_smart"]  # IMPORTANT
)
```

---

## Adding New Features

### Adding a New Action Handler

1. Create parameter model in `app/services/actions/base.py`:
```python
class MyActionParams(BaseModel):
    field_name: str = Field(..., description="Description")
```

2. Create handler in `app/services/actions/my_actions.py`:
```python
def register_my_actions(registry: ActionRegistry):
    @registry.register(
        name="my_action",
        entity="MyEntity",
        description="Does something",
        category="mutation",
        requires_confirmation=True,
        undoable=True
    )
    def handle_my_action(params: MyActionParams, db: Session, user: Employee, **context) -> Dict:
        # Implementation
        return {"success": True, "message": "..."}
```

3. Register in `app/services/actions/__init__.py`:
```python
from app.services.actions import my_actions
my_actions.register_my_actions(registry)
```

### Testing Actions

```bash
uv run pytest tests/services/actions/test_base.py -v     # Parameter models
uv run pytest tests/services/actions/test_my_actions.py -v  # Handler tests
```

---

## API Organization

All endpoints require JWT authentication. Key groups:
- `/auth/*` - Login, current user, password change
- `/rooms/*` - Room types, rooms, status updates, availability
- `/reservations/*` - CRUD, search, today's arrivals/departures
- `/checkin/*`, `/checkout/*` - Check-in/out operations
- `/tasks/*` - Task CRUD and workflow
- `/ai/*` - Chat with context, execute confirmed actions
- `/ontology/*` - Schema, stats, semantic/kinetic/dynamic metadata
- `/security/*` - Security events and alerts
- `/undo/*` - Operation undo

---

## AI Action Types

**Query:**
- `ontology_query` - Dynamic field-level query (entity, fields, filters, joins)
- `semantic_query` - Semantic path-based query (dot-notation paths)

**Mutation:**
- `walkin_checkin`, `checkin`, `checkout`, `extend_stay`, `change_room`
- `create_reservation`, `cancel_reservation`
- `create_task`, `assign_task`, `start_task`, `complete_task`
- `add_payment`, `adjust_bill`

---

## LLM Integration

- OpenAI-compatible API (DeepSeek, OpenAI, Azure, Ollama)
- Date context injection for relative date parsing ("明天" → ISO date)
- Robust JSON extraction with fallback parsing
- Topic relevance detection for context management

---

## UI Conventions

- Dark theme: bg-dark-950, borders dark-800, accent primary-400
- Room status colors: green (vacant_clean), red (occupied), yellow (vacant_dirty), gray (out_of_order)
- Modals via `useUIStore.openModal(name, data)`
- Icons from `lucide-react`

---

## Development Notes

- Backend: `uv` package manager (Python 3.12+)
- Frontend: npm with Vite
- Database: SQLite at `backend/aipms.db`
- Type validation: Pydantic v2
- State management: Zustand

---

## Test Statistics

- **Total tests**: 1200+
- **API tests**: `tests/api/` (1070+)
- **Core framework tests**: `tests/core/` (600+)
- **Action handler tests**: `tests/services/actions/` (190+)
- **Integration tests**: `tests/integration/`

**Test Patterns:**
- Use `db_session` fixture for database operations
- Event handlers don't work in test environment
- OntologyRegistry is a singleton - use `clean_registry` fixture
