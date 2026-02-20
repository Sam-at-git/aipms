# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Quick Reference

### Backend Commands
```bash
cd backend
uv sync                                    # Install dependencies
uv run python init_data.py                 # Initialize database with seed data
uv run uvicorn app.main:app --reload --port 8020  # Start server

# Testing
uv run pytest                              # All tests (95% coverage on app/)
uv run pytest tests/api/ -v                # API tests only
uv run pytest tests/core/ -v               # Core framework tests
uv run pytest tests/services/actions/ -v   # Action handler tests
uv run pytest tests/integration/ -v        # Integration tests
uv run pytest -k "test_name"               # Single test by name
uv run pytest --no-cov                     # Skip coverage check

# Benchmark (real LLM, no mocking — requires API key)
OPENAI_API_KEY=sk-xxx uv run pytest tests/benchmark/ -v -s --no-cov
```

### Frontend Commands
```bash
cd frontend
npm install && npm run dev                 # Dev server on http://localhost:3020
npm run build                              # Production build (TS errors in build are pre-existing)
```

### Combined
```bash
./start.sh                                 # Starts both backend and frontend
```

### Default Credentials
Multi-branch chain hotel setup with two branches:

| Username | Password | Role | Branch |
|----------|----------|------|--------|
| sysadmin | 123456 | System admin | Global (all branches) |
| manager | 123456 | Branch manager | 杭州西湖店 |
| sh_manager | 123456 | Branch manager | 上海外滩店 |
| front1 | 123456 | Receptionist | 杭州西湖店 |
| sh_front1 | 123456 | Receptionist | 上海外滩店 |
| cleaner1 | 123456 | Cleaner | 杭州西湖店 |
| sh_cleaner1 | 123456 | Cleaner | 上海外滩店 |

### Environment Variables
Set via environment or `backend/.env`:
| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (none) | LLM API key. Without this, LLM is disabled and rule-based fallback is used. |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | LLM API endpoint (OpenAI-compatible) |
| `LLM_MODEL` | `deepseek-chat` | Model name |
| `LLM_TEMPERATURE` | `0.7` | LLM temperature |
| `LLM_MAX_TOKENS` | `2000` | Max output tokens |
| `ENABLE_LLM` | `true` | Feature toggle |
| `EMBEDDING_API_KEY` | `ollama` | Embedding service key |
| `EMBEDDING_BASE_URL` | `http://localhost:11434/v1` | Embedding endpoint (Ollama default) |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |

---

## Architecture Overview

The system is an AI-powered hotel PMS (Property Management System) with natural language interface. It has three layers:

### Layer 1: `core/` — Ontology Runtime Framework (domain-agnostic)

Reusable abstractions with **zero hotel-specific logic**. Enforced by architecture guard test: `tests/domain/test_domain_separation.py::test_core_has_no_app_imports`.

- **`core/ontology/`** — Entity metadata, registry, query engine
  - `registry.py`: `OntologyRegistry` singleton — central store for all metadata
  - `domain_adapter.py`: `IDomainAdapter` abstract interface
  - `query.py` / `query_engine.py`: `StructuredQuery` → SQLAlchemy query builder
  - `semantic_query.py` / `semantic_path_resolver.py`: `SemanticQuery` (dot-notation like `stays.room.room_number`) → compiled to `StructuredQuery` with auto-discovered JOINs
  - `metadata.py`: Three-dimensional metadata — `EntityMetadata`, `PropertyMetadata`, `ActionMetadata`, `StateMachine`, `BusinessRule`, `ConstraintMetadata`, `RelationshipMetadata`

- **`core/ai/`** — AI pipeline
  - `actions.py`: `ActionRegistry` + declarative action registration
  - `ooda_orchestrator.py`: Main orchestrator — `process_message()` wraps `_process_message_inner()` with try/finally for context lifecycle
  - `prompt_builder.py`: Dynamic prompt injection from ontology metadata
  - `llm_client.py`: `OpenAICompatibleClient` — OpenAI, DeepSeek, Azure, Ollama
  - `debug_logger.py`: SQLite-backed session tracking with `DebugSession`, `AttemptLog`, `LLMInteraction` tables
  - `llm_call_context.py`: Thread-local `LLMCallContext` — passes debug session context to LLM call sites without threading through signatures
  - `reflexion.py`: `ReflexionLoop` — self-healing execution with LLM error analysis (max 2 retries)
  - `replay.py`: `ReplayEngine` — session replay with parameter overrides and A/B comparison
  - `intent_router.py`: Intent classification (query, mutation, system, tool)
  - `query_compiler.py`: LLM output → `SemanticQuery` compilation
  - `response_generator.py`: Query results → natural language
  - `hitl.py`: Human-in-the-loop confirmation strategies

- **`core/ooda/`** — OODA loop phases: `observe.py` → `orient.py` → `decide.py` → `act.py` → `loop.py`
- **`core/engine/`** — `event_bus.py`, `rule_engine.py`, `state_machine.py`, `audit.py`, `snapshot.py`
- **`core/security/`** — `attribute_acl.py`, `context.py`, `masking.py`, `checker.py`, `data_scope.py` (data isolation types & interfaces)
- **`core/reasoning/`** — `constraint_engine.py`, `planner.py`, `relationship_graph.py`

### Layer 2: `app/hotel/` — Hotel Business Domain

All hotel-specific logic.

- `hotel_domain_adapter.py`: `HotelDomainAdapter(IDomainAdapter)` — registers entities, relationships, state machines, actions, constraints into `OntologyRegistry`
- `domain/`: Entity classes (room, guest, reservation, stay_record, bill, task, employee), interfaces, rules, metadata YAML

### Layer 3: `app/system/` — System Management Domain

RBAC, menus, data dictionary, config, organization, messaging, scheduler — also registered via `SystemDomainAdapter(IDomainAdapter)` into the same `OntologyRegistry`.

- **Organization**: 3-level hierarchy: Group → Branch → Department (`SysDepartment.dept_type`)
- **RBAC**: Dynamic roles (`SysRole`) with permissions (`SysPermission`), data_scope levels (ALL, DEPT_AND_BELOW, DEPT, SELF)
- **Data Scope Resolver**: `app/system/services/data_scope_resolver.py` — `BranchDataScopeResolver` resolves user branch visibility

### Shared App Infrastructure

- **`app/models/ontology.py`** — SQLAlchemy ORM models (Room, Guest, Reservation, StayRecord, Bill, Task, Employee, RoomType, RatePlan, Payment)
- **`app/models/schemas.py`** — Pydantic I/O schemas
- **`app/services/`** — Business logic services + `actions/` (12 action handler modules)
- **`app/services/llm_service.py`** — LLM integration with `_instrumented_completion()` wrapper that auto-records each call via `LLMCallContext`
- **`app/routers/`** — FastAPI endpoints (all require JWT)
- **`app/security/auth.py`** — JWT + dynamic RBAC (`require_permission()` decorator)
- **`app/security/permissions.py`** — Permission code constants (e.g., `ROOM_READ`, `EMPLOYEE_WRITE`)

---

## Key Design Patterns

### Two-Tier Query Pipeline
```
LLM output → SemanticQuery (dot-notation paths)
           → SemanticPathResolver compiles to StructuredQuery (SQL-ready)
           → QueryEngine executes via SQLAlchemy
```

### Bootstrap Sequence (`app/main.py` lifespan)
1. Register event handlers and alerts
2. Register hotel relationships → `register_hotel_relationships()`
3. Register business rules → `register_all_rules()`
4. Bootstrap `HotelDomainAdapter` → `adapter.register_ontology(registry)`
5. Bootstrap `SystemDomainAdapter` → `sys_adapter.register_ontology(registry)`
6. Configure embedding service → `configure_embedding_service()`
7. Register domain ACL permissions → `acl.register_domain_permissions()`
8. Initialize hotel business rules → `init_hotel_business_rules()`
9. Sync ActionRegistry to OntologyRegistry → `action_registry.set_ontology_registry(registry)`
10. Initialize RBAC seed data, menus, system config

### Multi-Branch Data Isolation
- **SCOPED entities** (Room, Reservation, Task, Bill, etc.) have `branch_id` column — data is filtered per branch
- **GLOBAL entities** (Guest) have no branch_id — shared across all branches
- Frontend sends `X-Branch-Id` header via axios interceptor for branch context
- `BranchSwitcher` component in sidebar: sysadmin can switch branches, branch staff see their branch only
- `require_permission()` replaces old `require_role()` / `require_manager` decorators
- Permission checks: sysadmin → RBAC provider → legacy role fallback

### Action Dispatch
Handler functions accessed via `ActionRegistry.dispatch(action_name, params, context)`. All handlers use Pydantic parameter models.

Handler signature: `handler(params: BaseModel, db: Session, user: Employee, **context) -> Dict`

### OODA Loop (`ooda_orchestrator.process_message()`)
1. **Observe**: Capture input, create debug session, initialize `LLMCallContext`
2. **Orient**: Topic relevance check (LLM call: `orient/topic_relevance`)
3. **Decide**: Generate actions via LLM (call: `decide/chat`) or rule-based fallback
4. **Act**: Execute action, optionally format results (call: `act/format_result`)
5. **Cleanup**: `LLMCallContext.end_session()` in `finally` block

### LLM Observability Pipeline
```
LLMCallContext.begin_session()          # start of process_message
  → LLMCallContext.before_call(phase, type)  # before each LLM call
  → llm_service._instrumented_completion()   # wraps client.chat.completions.create()
  → debug_logger.log_llm_interaction()       # auto-records timing, tokens, prompt/response
  → debug_logger.complete_session()          # end of process_message
LLMCallContext.end_session()            # in finally block
```

---

## Query Action Handling (Critical)

`ontology_query` and `query_smart` must be recognized as query actions to bypass parameter enhancement:

```python
is_query_action = (
    action_type.startswith("query_") or
    action_type == "view" or
    action_type in ["ontology_query", "query_smart"]
)
```

---

## Adding a New Action Handler

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
        return {"success": True, "message": "..."}
```

3. Register in `app/services/actions/__init__.py`:
```python
from app.services.actions import my_actions
my_actions.register_my_actions(registry)
```

---

## Testing

### Configuration (`pyproject.toml`)
- Coverage minimum: 95% (`--cov-fail-under=95`)
- Coverage scope: `--cov=app` (only measures `app/` code, not `core/`)
- Markers: `slow`, `integration`
- asyncio_mode: auto

### Key Fixtures (`tests/conftest.py`)
- `db_engine` / `db_session`: In-memory SQLite per test function
- `client`: FastAPI `TestClient` with DB override
- `manager_token` / `receptionist_token` / `cleaner_token` / `sysadmin_token`: Pre-created users with JWT tokens
- `clean_registry`: Resets `OntologyRegistry` singleton between tests

### Benchmark Tests (`tests/benchmark/`)
- YAML-driven end-to-end tests with real LLM calls (no mocking)
- `benchmark_data.yaml`: Declarative test cases with `expect_action`, `expect_query_result`, `follow_up_fields`, `verify_db`
- Each group runs in an independent in-memory SQLite with seeded init_data
- `_resolve_action_params` auto-resolves entity IDs from DB context before execution

### Important Constraints
- Event handlers (pub/sub) don't fire in test environment
- `OntologyRegistry` is a singleton — tests that modify it must use `clean_registry` fixture
- DB enum values are stored UPPERCASE (e.g., `OCCUPIED`, `CONFIRMED`, `PENDING`)
- `DebugLogger` uses file-backed SQLite (`:memory:` doesn't work because `_get_conn()` creates new connections); use `tempfile.mkstemp()` in tests

---

## API Organization

All endpoints require JWT authentication (no `/api` prefix — frontend Vite proxy at `/api` rewrites to `/`).

| Prefix | Description |
|--------|-------------|
| `/auth/*` | Login, current user, password change |
| `/rooms/*` | Room types, rooms, status, availability |
| `/reservations/*` | CRUD, search, today's arrivals/departures |
| `/checkin/*`, `/checkout/*` | Check-in/out operations |
| `/tasks/*` | Task CRUD and workflow |
| `/ai/*` | Chat with context (`POST /ai/chat` body: `{content, topic_id?, follow_up_context?}`) |
| `/ontology/*` | Schema, stats, semantic/kinetic/dynamic metadata |
| `/debug/*` | Debug sessions, replay, analytics (sysadmin only) |
| `/security/*` | Security events and alerts |
| `/undo/*` | Operation undo |
| `/sys-dict/*`, `/sys-config/*`, `/sys-roles/*`, `/sys-menus/*`, `/sys-dept/*`, `/sys-msg/*`, `/scheduler/*` | System management |

---

## AI Action Types

**Query:** `ontology_query` (dynamic field-level), `semantic_query` (dot-notation paths)

**Guest/Stay:** `walkin_checkin`, `checkin`, `checkout`, `extend_stay`, `change_room`, `create_guest`, `update_guest`

**Reservation:** `create_reservation`, `cancel_reservation`, `modify_reservation`

**Task:** `create_task`, `assign_task`, `start_task`, `complete_task`, `delete_task`

**Bill/Payment:** `add_payment`, `adjust_bill`, `refund_payment`

**Room:** `mark_room_clean`, `mark_room_dirty`, `update_room_status`

**Admin:** `create_employee`, `update_employee`, `deactivate_employee`, `update_price`, `create_rate_plan`

### Parameter Validation Flow (Critical)

`ACTION_REQUIRED_PARAMS` in `ooda_orchestrator.py` defines mandatory fields for key actions. When `_validate_action_params()` finds missing fields, it returns `missing_fields` with UI form definitions. The frontend collects input and sends it back via `follow_up_context`, which bypasses LLM and goes straight to execution.

**Critical consistency rule**: Field names must match across `ACTION_REQUIRED_PARAMS`, `_get_field_definition`, `param_parser`, and LLM prompt examples.

---

## Frontend Architecture

- **Stack**: React 18, TypeScript, Vite, Zustand, TailwindCSS
- **Proxy**: `vite.config.ts` proxies `/api/*` → `http://localhost:8020/` (strips `/api` prefix)
- **Dark theme**: `bg-dark-950`, borders `dark-800`, accent `primary-400`
- **Room status colors**: green (vacant_clean), red (occupied), yellow (vacant_dirty), gray (out_of_order)
- **OODA phase colors**: sky (observe), violet (orient), amber (decide), emerald (act) — used in `DualTrackTimeline` and `OodaPipeline`
- **Modals**: `useUIStore.openModal(name, data)`
- **Icons**: `lucide-react`

### Debug Panel Components
- `DualTrackTimeline.tsx`: Upper track (OODA phases) + lower track (LLM calls grouped by phase), with dashed connection lines and clickable nodes
- `LLMInteractionDetail.tsx`: Expandable detail panel for individual LLM calls (prompt, response, tokens, errors)
- `SessionDetail.tsx`: Renders `DualTrackTimeline` when `llm_interactions` is non-empty, falls back to `OodaPipeline` for old sessions

---

## Seed Data Reference (`init_data.py`)

**Organization:**
- 集团总部 (GROUP) → 杭州西湖店 (BRANCH) + 上海外滩店 (BRANCH)
- Each branch has: 前台部, 客房部, 财务部 departments

**Room layout (40 rooms, 20 per branch):**
- 杭州西湖店: 2F 201–210, 3F 301–310 (标间/大床房)
- 上海外滩店: 2F 201–210, 3F 301–310 (标间/大床房)

**Employees:**
- sysadmin (系统管理员, global), manager/张经理 (杭州), sh_manager/王经理 (上海)
- front1/李前台 (杭州), sh_front1/赵前台 (上海)
- cleaner1/刘阿姨 (杭州), sh_cleaner1/陈阿姨 (上海)

**Room types:** 标间 ¥288, 大床房 ¥328, 豪华间 ¥458

**Dynamic RBAC roles:** sysadmin (ALL), branch_manager (DEPT_AND_BELOW), receptionist (DEPT_AND_BELOW), cleaner (DEPT_AND_BELOW)

---

## Development Guides

- `docs/add-entity-guide.md` — Adding new entities (13-step checklist with code templates)
- `docs/ontology-architecture-guide.md` — Ontology architecture design doc
- `docs/ralphloop/RALPH_LOOP_EXPERIENCE.md` — AI-assisted dev loop methodology

---

## Behavioral Constraints

- **STRUGGLE_SIGNAL**: Stop immediately if same bug fails 2x, guessing APIs, or 3 consecutive test failures
- Never modify test files to make tests pass (unless the task explicitly requires it)
- Prefer minimal, precise edits over rewriting entire files
- **Critical**: Always validate field name consistency between `ACTION_REQUIRED_PARAMS`, `_get_field_definition`, `param_parser`, and LLM prompt examples
