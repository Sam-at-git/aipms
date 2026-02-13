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
uv run pytest                              # All tests (95% coverage required)
uv run pytest tests/api/ -v                # API tests only
uv run pytest tests/core/ -v               # Core framework tests
uv run pytest tests/services/actions/ -v   # Action handler tests
uv run pytest tests/integration/ -v        # Integration tests
uv run pytest -k "test_name"               # Single test by name

# Benchmark (real LLM, no mocking — requires API key)
OPENAI_API_KEY=sk-xxx uv run pytest tests/benchmark/ -v -s --no-cov
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

## Two-Layer Architecture

The system is split into a **domain-agnostic ontology runtime** (`core/`) and a **hotel business domain** (`app/`). This separation enables the core framework to be reused for any business domain by swapping the domain adapter.

### Layer 1: `core/` — Ontology Runtime Framework (domain-agnostic)

The framework provides reusable abstractions. No hotel-specific logic belongs here. **Enforced**: `grep -r "from app\." backend/core/` must return zero results; an architecture guard test (`tests/domain/test_domain_separation.py::test_core_has_no_app_imports`) verifies this.

- **`core/domain/`** — Generic relationship types only
  - `relationships.py`: `LinkType`, `Cardinality`, `EntityLink`, `RelationshipRegistry` — domain-agnostic infrastructure for expressing entity relationships. All hotel-specific entity code lives in `app/hotel/domain/`.

- **`core/ontology/`** — Entity abstractions and metadata
  - `base.py`: `BaseEntity`, `ObjectProxy` (attribute-level interception for security/audit)
  - `metadata.py`: Three-dimensional metadata types — `EntityMetadata`, `PropertyMetadata`, `ActionMetadata`, `StateMachine`, `BusinessRule`, `ConstraintMetadata`, `RelationshipMetadata`, `EventMetadata`
  - `registry.py`: `OntologyRegistry` singleton — central store for all metadata (entities, actions, state machines, rules, permissions, relationships)
  - `domain_adapter.py`: `IDomainAdapter` abstract interface — each business domain implements this to register its ontology
  - `query.py` / `query_engine.py`: `StructuredQuery` → SQLAlchemy query builder with dynamic filters, joins, sorting
  - `semantic_query.py` / `semantic_path_resolver.py`: `SemanticQuery` (LLM-friendly dot-notation like `stays.room.room_number`) → compiled to `StructuredQuery` with auto-discovered JOINs
  - `business_rules.py`: `BusinessRuleRegistry` for declarative rule definitions
  - `rule_applicator.py`: Apply constraints to query results
  - `state_machine_executor.py`: Execute validated state transitions

- **`core/ai/`** — AI pipeline abstractions
  - `__init__.py`: Exports + `configure_embedding_service()` — app layer injects embedding config at startup (no direct `app.config` import)
  - `actions.py`: `ActionRegistry` + `ActionDefinition` — declarative action registration replacing if/else chains
  - `prompt_builder.py`: `PromptBuilder` dynamically injects ontology metadata (entities, actions, state machines, rules, permissions, date context) into LLM prompts. Uses `registry.get_model()` for DB stats (no hardcoded model imports).
  - `reflexion.py`: `ReflexionLoop` — self-healing execution with LLM error analysis (max 2 retries, then fallback)
  - `llm_client.py`: `OpenAICompatibleClient` — supports OpenAI, DeepSeek, Azure, Ollama
  - `vector_store.py` / `schema_retriever.py` / `embedding.py`: Pure-Python cosine similarity semantic search for schema retrieval
  - `hitl.py`: Human-in-the-loop confirmation strategies (by-risk, by-policy, by-threshold, composite)
  - `intent_router.py`: Intent classification (query, mutation, system, tool)
  - `query_compiler.py`: LLM output → `SemanticQuery` compilation
  - `response_generator.py`: Query results → natural language
  - `debug_logger.py` / `replay.py`: Execution tracing, replay, A/B testing

- **`core/ooda/`** — OODA loop phases
  - `observe.py` → `orient.py` → `decide.py` → `act.py`, orchestrated by `loop.py`
  - `intent.py`: `IntentRecognitionService` with pluggable strategies

- **`core/engine/`** — Infrastructure
  - `event_bus.py`: Domain event pub/sub
  - `rule_engine.py`: Business rule evaluation
  - `state_machine.py`: State machine definitions
  - `audit.py`: Audit logging
  - `snapshot.py`: Operation undo snapshots

- **`core/security/`** — Security framework
  - `context.py`: User security context with role/permissions
  - `attribute_acl.py`: Attribute-level access control + `register_domain_permissions()` — app layer injects domain-specific ACL rules at startup (no hardcoded hotel permissions)
  - `masking.py`: PII data masking
  - `checker.py`: Permission checking

- **`core/reasoning/`** — Constraint reasoning
  - `constraint_engine.py`: Business rule constraint validation
  - `planner.py`: Query planning
  - `relationship_graph.py`: Entity relationship graph

### Layer 2: `app/` — Hotel Business Domain

All hotel-specific logic lives here.

- **`app/hotel/`** — Domain adapter and domain entities
  - `hotel_domain_adapter.py`: `HotelDomainAdapter(IDomainAdapter)` — registers all hotel entities, relationships, state machines, actions, constraints, events into `OntologyRegistry`
  - `business_rules.py`: Hotel-specific rules (auto-task on checkout, pricing, guest tiers)
  - **`domain/`** — Hotel domain entities, interfaces, rules, and metadata:
    - `room.py`, `guest.py`, `reservation.py`, `stay_record.py`, `bill.py`, `task.py`, `employee.py`: Domain entities wrapping ORM models (Entity + State + Repository pattern)
    - `interfaces.py`: `BookableResource`, `Maintainable`, `Billable`, `Trackable` — cross-entity business interfaces
    - `relationships.py`: Hotel-specific relationship constants (ROOM_RELATIONSHIPS, GUEST_RELATIONSHIPS, etc.) + `register_hotel_relationships()` function
    - `rules/`: `room_rules.py`, `guest_rules.py`, `pricing_rules.py` + `register_all_rules()`
    - `metadata/`: `security_levels.yaml`, `hitl_policies.yaml` + loaders

- **`app/models/`** — SQLAlchemy ORM + Pydantic schemas
  - `ontology.py`: Domain objects — `Room`, `Guest`, `Reservation`, `StayRecord`, `Bill`, `Task`, `Employee`, `RoomType`, `RatePlan`, `Payment`
  - `schemas.py`: Pydantic I/O models for API validation
  - `events.py`: Domain event definitions
  - `snapshots.py`: `OperationSnapshot` for undo (24-hour expiry)

- **`app/services/`** — Business logic
  - `actions/`: AI-executable action handlers organized by domain (12 modules: `guest_actions`, `stay_actions`, `task_actions`, `reservation_actions`, `query_actions`, `bill_actions`, `room_actions`, `employee_actions`, `price_actions`, `webhook_actions`, `notification_actions`, `interface_actions`)
  - `actions/base.py`: Pydantic parameter models for all actions
  - `ai_service.py`: OODA loop controller — LLM-first with rule-based fallback
  - `llm_service.py`: LLM integration with date context injection
  - Domain services: `room_service.py`, `guest_service.py`, `reservation_service.py`, `checkin_service.py`, `checkout_service.py`, `task_service.py`, `billing_service.py`
  - V2 services: `room_service_v2.py`, `guest_service_v2.py` — integrate domain entities with repositories
  - `event_bus.py` + `event_handlers.py`: In-memory pub/sub (checkout → cleaning task, task completion → room status)
  - `undo_service.py`: Operation undo with snapshots

- **`app/routers/`** — FastAPI endpoints (all require JWT)
- **`app/security/auth.py`** — JWT + role-based access

---

## Key Design Patterns

### Two-Tier Query Pipeline
```
LLM output → SemanticQuery (dot-notation paths)
           → SemanticPathResolver compiles to StructuredQuery (SQL-ready)
           → QueryEngine executes via SQLAlchemy
```

### Domain Adapter Registration
```python
class HotelDomainAdapter(IDomainAdapter):
    def register_ontology(self, registry: OntologyRegistry):
        registry.register_entity(EntityMetadata(...))
        registry.register_relationship("Room", RelationshipMetadata(...))
        registry.register_state_machine("Room", StateMachine(...))
```

### Bootstrap Sequence (`app/main.py` lifespan)
At startup, the app layer injects all domain-specific configuration into the core framework:
1. Register event handlers and alerts
2. Register hotel relationships → `register_hotel_relationships(relationship_registry)`
3. Register business rules → `register_all_rules(rule_engine)`
4. Bootstrap `HotelDomainAdapter` → `adapter.register_ontology(registry)` (entities, state machines, constraints, events)
5. Configure embedding service → `configure_embedding_service(api_key=..., base_url=..., model=...)`
6. Register domain ACL permissions → `acl.register_domain_permissions([AttributePermission(...), ...])`
7. Initialize hotel business rules → `init_hotel_business_rules()`
8. Sync ActionRegistry to OntologyRegistry → `action_registry.set_ontology_registry(registry)`

### Action Dispatch
Handler functions are NOT directly exported — access via `ActionRegistry.dispatch(action_name, params, context)`. All handlers use Pydantic models for parameter validation.

Handler signature: `handler(params: BaseModel, db: Session, user: Employee, **context) -> Dict`

### Three-Dimensional Metadata
- **Semantic**: Entity attributes, types, constraints, relationships (via SQLAlchemy reflection)
- **Kinetic**: Executable operations/actions grouped by entity
- **Dynamic**: State machines, permission matrix, business rules

### OODA Loop (`ai_service.process_message()`)
1. Observe: Capture natural language input
2. Orient: Identify intent + extract entities
3. Decide: Generate suggested actions with `requires_confirmation` flag
4. Act: Execute confirmed actions via domain services

---

## Query Action Handling (Critical)

`ontology_query` and `query_smart` must be recognized as query actions to bypass parameter enhancement.

In `app/services/ai_service.py`:
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
- Coverage scope: `--cov=app` (only measures `app/` code)
- Markers: `slow`, `integration`
- asyncio_mode: auto

### Key Fixtures (`tests/conftest.py`)
- `db_engine` / `db_session`: In-memory SQLite per test function
- `client`: FastAPI `TestClient` with DB override
- `manager_token` / `receptionist_token` / `cleaner_token` / `sysadmin_token`: Pre-created users with JWT tokens
- `clean_registry`: Resets `OntologyRegistry` singleton between tests (required when testing registry operations)

### Benchmark Tests (`tests/benchmark/`)
- YAML-driven end-to-end tests with real LLM calls (no mocking)
- `benchmark_data.yaml`: Declarative test cases with `expect_action`, `expect_query_result`, `follow_up_fields`, `verify_db`
- Each group runs in an independent in-memory SQLite with seeded init_data
- Tests within a group execute sequentially (support cross-test dependencies)
- `_resolve_action_params` auto-resolves entity IDs (task_id, bill_id, stay_record_id, reservation_id) from DB context before execution

### Important Constraints
- Event handlers (pub/sub) don't fire in test environment
- `OntologyRegistry` is a singleton — tests that modify it must use the `clean_registry` fixture to avoid cross-test pollution
- DB enum values are stored UPPERCASE (e.g., `OCCUPIED`, `CONFIRMED`, `PENDING`) — use case-insensitive comparison

---

## API Organization

All endpoints require JWT authentication. Key groups:
- `/auth/*` — Login, current user, password change
- `/rooms/*` — Room types, rooms, status updates, availability
- `/reservations/*` — CRUD, search, today's arrivals/departures
- `/checkin/*`, `/checkout/*` — Check-in/out operations
- `/tasks/*` — Task CRUD and workflow
- `/ai/*` — Chat with context, execute confirmed actions
- `/ontology/*` — Schema, stats, semantic/kinetic/dynamic metadata
- `/security/*` — Security events and alerts
- `/undo/*` — Operation undo

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

`ai_service.py` defines `ACTION_REQUIRED_PARAMS` for actions that need mandatory fields:
```python
ACTION_REQUIRED_PARAMS = {
    'walkin_checkin': ['room_number', 'guest_name', 'guest_phone', 'expected_check_out'],
    'create_reservation': ['guest_name', 'guest_phone', 'room_type_id', 'check_in_date', 'check_out_date'],
    'checkin': ['reservation_id', 'room_number'],
    'checkout': ['stay_record_id'],
    'extend_stay': ['stay_record_id', 'new_check_out_date'],
    'change_room': ['stay_record_id', 'new_room_number'],
    'create_task': ['room_number', 'task_type'],
}
```

When `_validate_action_params()` finds missing fields, it returns `missing_fields` with UI form definitions (select dropdowns with DB options, text inputs, date pickers). The frontend presents these to the user, who fills them in. The response is sent back via `follow_up_context` in the next `process_message()` call, which bypasses LLM and goes straight to action execution.

Actions NOT in this dict (e.g., `complete_task`, `add_payment`, `mark_room_clean`) skip validation and go directly to the handler, which must have all required params from the LLM extraction.

---

## LLM Integration

- OpenAI-compatible API (DeepSeek, OpenAI, Azure, Ollama)
- Date context injection: LLM receives `current_date`, `tomorrow`, `day_after` for relative date parsing ("明天" → ISO date)
- Robust JSON extraction with fallback parsing
- Topic relevance detection for context management

---

## UI Conventions

- Dark theme: `bg-dark-950`, borders `dark-800`, accent `primary-400`
- Room status colors: green (vacant_clean), red (occupied), yellow (vacant_dirty), gray (out_of_order)
- Modals via `useUIStore.openModal(name, data)`
- Icons from `lucide-react`
- State management: Zustand

---

## Development Notes

- Backend: `uv` package manager, Python 3.10+ (3.12+ recommended)
- Frontend: npm with Vite, React 18 + TypeScript
- Database: SQLite at `backend/pms.db`
- Type validation: Pydantic v2
- ORM: SQLAlchemy 2.0+

### Seed Data Reference (`init_data.py`)

**Room layout (40 rooms):**
- 2F: 201–205 标间, 206–210 大床房
- 3F: 301–305 标间, 306–310 大床房
- 4F: 401–405 标间, 406–408 大床房, 409–410 豪华间
- 5F: 501–502 大床房, 503–510 豪华间

**Employees:** sysadmin (系统管理员), manager (张经理), front1/front2/front3 (李前台/王前台/赵前台), cleaner1/cleaner2 (刘阿姨/陈阿姨)

**Room types:** 标间 ¥288, 大床房 ¥328, 豪华间 ¥458

---

## Development Guides

- `docs/add-entity-guide.md` — 新增 Entity 完整开发指南（13 步 checklist，含代码模板）
- `docs/ontology-architecture-guide.md` — Ontology architecture design doc

---

## Ralph Loop / Sam Loop Refactoring Process

This project uses structured AI-assisted development loops with Architect→Editor phases. Key references:
- `docs/ralphloop/RALPH_LOOP_EXPERIENCE.md` — Methodology and lessons learned

### Behavioral Constraints
- **STRUGGLE_SIGNAL**: Stop immediately if same bug fails 2x, guessing APIs, or 3 consecutive test failures
- Never modify test files to make tests pass (unless the task explicitly requires it)
- Never skip test verification
- Prefer minimal, precise edits over rewriting entire files
- **Critical**: Always validate field name consistency between `ACTION_REQUIRED_PARAMS`, `_get_field_definition`, `param_parser`, and LLM prompt examples

### Resolved Issues

#### Field Name Mismatch (Resolved)
LLM returned `room_type_id`/`room_type_name` but `ACTION_REQUIRED_PARAMS` expected `room_type`. Fixed by unifying all components to use `room_type_id`:
- `ACTION_REQUIRED_PARAMS`: uses `room_type_id`
- `_get_field_definition`: returns `room_type_id` options
- `param_parser.parse_room_type()`: accepts `room_type_id` (int) or `room_type` (string name)
- LLM prompts: updated to use `room_type_id`

---
