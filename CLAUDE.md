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
uv run pytest tests/api/test_api_rooms.py -k "test_get_room"  # Single test
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

## Ralph Loop 重构模式 (Active Refactoring)

本项目正在进行 **Ralph Loop** 模式架构重构，将系统重构为 **本体运行时框架 (core)** + **酒店业务本体 (domain)** 两层架构。

### 核心文件
- `docs/ralphloop/refactor-plan.md` - 主控计划（80个SPEC）
- `docs/ralphloop/progress.txt` - 进度日志和坑点记录
- `docs/ralphloop/specs/SPEC-XX-design.md` - 每个 SPEC 的详细设计

### 行为约束

**🚨 挣扎信号 (STRUGGLE SIGNAL)** - 必须立即停止并发出 `[STRUGGLE_SIGNAL]`：
- 在修复同一个 Bug 上失败了 2 次
- 开始"猜测" API 用法
- 连续 3 次尝试无法通过测试

**🛡️ 消除警觉性税** - 方案可行但有风险时，明确说明风险

### 工作流程

**Architect Phase**: 读取 progress.txt → 确认 SPEC → 探索代码 → 输出设计到 specs/ → `<ARCHITECT_COMPLETE>`

**Editor Phase**: 读取设计文档 → 运行测试基准 → 精确修改 → 验证测试 → 更新 progress.txt → `<EDITOR_COMPLETE>` 或 `[STRUGGLE_SIGNAL]`

### 禁止事项
- ❌ 跳过测试验证
- ❌ 修改测试文件来让测试通过（除非任务明确要求）
- ❌ 一次性修改超过 3 个文件
- ❌ 重写整个文件（必须使用 SEARCH/REPLACE 块）

---

## Project Overview

AIPMS is a smart hotel management system built on **Palantir-inspired ontology-driven architecture**. All operations go through domain objects (Room, Guest, Reservation, StayRecord, etc.) rather than direct database access. The system combines a digital twin display (left panel) with an AI conversational interface (right panel).


## Architecture

### Backend Structure
```
backend/
├── app/                          # Current application code
│   ├── models/
│   │   ├── ontology.py           # Domain objects (Room, Guest, Reservation, StayRecord, Bill, Task, Employee)
│   │   ├── schemas.py            # Pydantic models for API I/O
│   │   ├── events.py             # Domain event definitions
│   │   └── snapshots.py          # OperationSnapshot for undo
│   ├── services/                 # Business logic layer (one service per domain)
│   │   ├── ai_service.py         # OODA loop: LLM优先，规则兜底
│   │   ├── llm_service.py        # OpenAI-compatible LLM integration
│   │   ├── event_bus.py          # In-memory pub/sub event bus
│   │   └── ...                   # Other domain services
│   ├── routers/                  # FastAPI endpoints
│   ├── security/auth.py          # JWT + role-based access
│   └── main.py                   # App initialization
│
├── core/                         # NEW: Ontology runtime framework (in development)
│   ├── ontology/                 # Entity abstractions
│   │   ├── base.py               # BaseEntity, ObjectProxy
│   │   ├── metadata.py           # EntityMetadata, ActionMetadata, PropertyMetadata
│   │   ├── registry.py           # OntologyRegistry singleton
│   │   ├── security.py           # SecurityLevel enum
│   │   └── link.py               # Link, LinkCollection
│   └── ooda/                     # OODA loop abstractions
│       └── intent.py             # IntentRecognitionService, IntentResult
│
├── tests/
│   ├── api/                      # API integration tests
│   ├── core/                     # Core framework unit tests
│   └── ooda/                     # OODA module tests
│
└── aipms.db                      # SQLite database
```

### Frontend Structure
```
frontend/src/
├── pages/              # Route pages (Dashboard, Rooms, Reservations, etc.)
├── components/         # Reusable UI (Layout, ChatPanel, Modal, RoomCard, UndoButton)
├── services/api.ts     # Axios HTTP client organized by domain
├── store/              # Zustand stores (auth, chat, dashboard, ui)
└── types/index.ts      # TypeScript interfaces matching backend schemas
```

### Key Patterns

**Service Layer**: Each service class wraps a domain object family. Services handle:
- Validation and business rules
- State transitions with side effects
- Related object updates (e.g., checkout creates cleaning task)

**Business Logic Automation**:
- Checkout → Room becomes VACANT_DIRTY → Auto-creates Task(type=CLEANING)
- Task completion → Room becomes VACANT_CLEAN
- Check-in → Creates StayRecord + Bill with calculated pricing

**OODA Loop (AI Service)**: `ai_service.process_message()` implements:
1. Observe: Capture natural language input
2. Orient: Identify intent + extract entities (room numbers, guest names, dates)
3. Decide: Generate suggested actions with `requires_confirmation` flag
4. Act: Execute confirmed actions via domain services

**Follow-up Mode**: When action parameters are incomplete:
- LLM returns `missing_fields` array with field definitions (field_name, display_name, field_type, options)
- Frontend displays a form for collecting missing information
- `process_message()` accepts `follow_up_context` to continue multi-turn conversations
- Once complete, LLM returns action with `requires_confirmation: true`

**LLM Integration** (`llm_service.py`):
- OpenAI-compatible API support (DeepSeek, OpenAI, Azure, Ollama, etc.)
- **Date Context Injection**: Current date, tomorrow, and day-after are passed to LLM for accurate relative date parsing
  ```
  **当前日期: 2026年2月3日**
  **明天: 2026-02-04**
  **后天: 2026-02-05**
  ```
- LLM instructed to convert all relative dates ("明天", "后天") to ISO format (`YYYY-MM-DD`) in response params
- Backend `param_parser_service.py` provides robust fallback parsing for:
  - ISO format: `2026-02-11`
  - Relative keywords: `今天`, `明天` (+1), `后天` (+2), `大后天` (+3)
  - Offset expressions: `+3天`
  - Week patterns: `下周二`
- Robust JSON extraction with fallback parsing:
  - Handles markdown code blocks (` ```json ... ` ```)
  - Removes comments (//, /* */)
  - Fixes trailing commas
  - Converts single quotes to double quotes
  - Extracts JSON from mixed text
- Falls back to rule-based matching when LLM fails or is disabled
- Topic relevance detection (`check_topic_relevance`) for context management

**Conversation Persistence** (`conversation_service.py`):
- JSONL storage at `backend/data/conversations/{user_id}/{YYYY-MM-DD}.jsonl`
- Paginated message retrieval with `before` timestamp for infinite scroll
- Context messages by topic_id or most recent N rounds (max 3)
- Keyword search with optional date range filtering

**Role-Based Access**:
- Backend: `require_manager`, `require_receptionist_or_manager`, `require_any_role` decorators in `security/auth.py`
- Frontend: Nav items filtered by `user.role`

**Event-Driven Architecture** (`event_bus.py`, `event_handlers.py`):
- In-memory pub/sub pattern using singleton EventBus
- Services publish domain events (e.g., `GUEST_CHECKED_OUT`, `TASK_COMPLETED`, `ROOM_CHANGED`)
- Event handlers subscribe to events and trigger side effects:
  - `GUEST_CHECKED_OUT` → auto-creates cleaning task
  - `TASK_COMPLETED` (cleaning) → room becomes VACANT_CLEAN
  - `ROOM_CHANGED` → auto-creates cleaning task for old room
- Supports dependency injection for testing via `event_publisher` parameter
- Event history retained (last 100) for debugging

**Operation Undo/Rollback** (`undo_service.py`, `snapshots.py`):
- Services create `OperationSnapshot` before executing undoable operations
- Snapshots store before/after state as JSON with 24-hour expiry window
- Supported operations: check_in, check_out, extend_stay, change_room, complete_task, add_payment
- Frontend `UndoButton` component shows recent undoable operations
- Undo API: `/undo/operations` (list), `/undo/{uuid}` (execute)

**Configuration Versioning** (`config_history_service.py`):
- Tracks system configuration changes with version history
- Supports rollback to previous config versions

**Security Events** (`security_event_service.py`, `alert_service.py`):
- Records security-relevant events (login failures, suspicious operations, etc.)
- Event types: AUTH_FAILURE, AUTH_SUCCESS, SUSPICIOUS_ACTION, PERMISSION_DENIED, etc.
- Severity levels: LOW, MEDIUM, HIGH, CRITICAL
- Automatic alerting when threshold thresholds are exceeded
- Security statistics and trend analysis

**Ontology Metadata System** (`metadata.py`, `ontology_metadata_service.py`):
- Three-dimensional ontology view: Semantic, Kinetic, Dynamic
- **Semantic**: Entity attributes, types, constraints, relationships (extracted via SQLAlchemy reflection)
- **Kinetic**: Executable operations/actions grouped by entity
- **Dynamic**: State machines, permission matrix, business rules
- Decorators available: `@ontology_entity`, `@ontology_action`, `@business_rule`, `@state_machine`
- Runtime extraction via `OntologyMetadataService` - no hardcoded schema needed
- Frontend Ontology page with 4 tabs: Data (graph), Semantic, Kinetic, Dynamic

### Aggregation Roots
- **StayRecord**: Owns Bill, represents active occupancy lifecycle
- **Reservation**: Owns booking details, transitions to StayRecord on check-in

### State Machines
- Room: VACANT_CLEAN → OCCUPIED → VACANT_DIRTY → VACANT_CLEAN
- Reservation: CONFIRMED → CHECKED_IN → COMPLETED/CANCELLED
- Task: PENDING → ASSIGNED → IN_PROGRESS → COMPLETED

## API Organization

All endpoints require JWT authentication. Main endpoint groups:
- `/auth/*` - Login, current user, password change
- `/rooms/*` - Room types, rooms, status updates, availability
- `/reservations/*` - CRUD, search, today's arrivals, today's expected departures
- `/checkin/*` - From reservation, walk-in, extend stay, change room
- `/checkout/*` - Execute checkout, expected/overdue lists
- `/billing/*` - Bills, payments, adjustments (manager only)
- `/tasks/*` - CRUD, assignment, start/complete
- `/reports/*` - Dashboard stats, occupancy, revenue
- `/ai/*` - Chat with context, execute confirmed actions
- `/conversations/*` - Chat history persistence, search, pagination
- `/settings/*` - LLM configuration (manager only)
- `/audit-logs/*` - Audit trail (manager only)
- `/guests/*` - Guest CRM (tier, preferences, blacklist, stats, history)
  - `/guests/{id}/tier` - PUT with `tier` as **query parameter**, not JSON body
  - `/guests/{id}/blacklist` - PUT with `is_blacklisted` and `reason` as **query parameters**
  - `/guests/{id}/preferences` - PUT with preferences dict as JSON body
  - `/guests/{id}/stats` - GET guest statistics (reservation_count, tier, etc.)
  - `/guests/{id}/stay-history` - GET stay records
  - `/guests/{id}/reservation-history` - GET reservations
- `/undo/*` - Operation undo (list undoable operations, execute undo)
- `/ontology/*` - Ontology schema, entity stats, relationship graph, semantic/kinetic/dynamic metadata (manager only)
  - `/ontology/schema` - Basic schema with entities and relationships
  - `/ontology/statistics` - Entity counts and distributions
  - `/ontology/semantic` - Detailed entity attributes with security levels
  - `/ontology/kinetic` - Executable operations grouped by entity
  - `/ontology/dynamic` - State machines, permission matrix, business rules
- `/security/*` - Security events, alerts, threat detection (manager only)

## AI Action Types

The `execute_action` method in `ai_service.py` supports the following action_type values:

**Check-in Operations:**
- `walkin_checkin` - Walk-in guest registration (requires: room_id, guest_name, guest_phone, expected_check_out)
- `checkin` - Check-in from reservation (requires: reservation_id, room_id)

**Check-out Operations:**
- `checkout` - Guest checkout (requires: stay_record_id)

**Room Management:**
- `update_room_status` - Manually change room status (requires: room_id, status)

**Reservation Management:**
- `create_reservation` - Create new booking (requires: `guest_name`, `guest_phone`, `room_type_id`, `check_in_date`, `check_out_date`, `adult_count`; optional: `child_count`, `room_count`, `guest_id_number`, `special_requests`)
  - Note: The API auto-creates or updates Guest from `guest_name`/`guest_phone` - don't send `guest_id`
- `cancel_reservation` - Cancel booking (requires: `reservation_id`, `cancel_reason`)

**Task Management:**
- `create_task` - Create cleaning/maintenance task (requires: room_id, task_type)
- `assign_task` - Assign task to cleaner (requires: task_id, assignee_id)
- `start_task` - Mark task as started (requires: task_id)
- `complete_task` - Mark task as completed (requires: task_id)

**Billing:**
- `add_payment` - Record payment (requires: bill_id, amount, method)
- `adjust_bill` - Adjust bill amount (manager only, requires: bill_id, adjustment_amount, reason)

**Stay Operations:**
- `extend_stay` - Extend checkout date (requires: stay_record_id, new_check_out_date)
- `change_room` - Move guest to different room (requires: stay_record_id, new_room_id)

## LLM Configuration

The system uses OpenAI-compatible APIs for LLM integration:

**Environment Variables:**
- `OPENAI_API_KEY` - API key (optional, can be set via settings UI)
- `OPENAI_BASE_URL` - API endpoint (default: https://api.deepseek.com)
- `LLM_MODEL` - Model name (default: deepseek-chat)
- `LLM_TEMPERATURE` - Response randomness 0-1 (default: 0.7)
- `LLM_MAX_TOKENS` - Max response tokens (default: 1000)
- `ENABLE_LLM` - Enable/disable LLM (default: true)

**Configuration via UI:**
- Manager role can access `/settings` page
- API Key can be entered in UI or left empty to use environment variable
- System prompt can be customized
- Test connection button validates configuration

## Adding New Features

1. Define ontology class in `models/ontology.py`
2. Add Pydantic schemas in `models/schemas.py`
3. Create service in `services/`
4. Create router in `routers/` and register in `main.py`
5. Add TypeScript types in `frontend/src/types/`
6. Add API methods in `frontend/src/services/api.ts`
7. Create page component in `frontend/src/pages/`

If adding a new AI action type:
1. Add action handler in `ai_service.py` execute_action method
2. Add intent handler in `_generate_response` if using rule-based mode
3. Update LLM system prompt in `llm_service.py` if needed

If adding a new undoable operation:
1. Add operation type to `OperationType` enum in `models/snapshots.py`
2. Call `UndoService.create_snapshot()` in the service method before `db.commit()`
3. Add rollback handler in `undo_service.py` `undo()` method
4. Add operation type label mapping in frontend `UndoButton.tsx`

**Ontology Metadata Decorators** (optional, for enhanced runtime metadata):
```python
from app.services.metadata import ontology_entity, ontology_action, business_rule

@ontology_entity(name="MyEntity", description="...", table_name="my_entities")
class MyEntity(Base):
    ...

class MyEntityService:
    @ontology_action(
        entity="MyEntity",
        action_type="do_something",
        description="...",
        params=[{"name": "id", "type": "integer", "required": True}],
        requires_confirmation=True,
        allowed_roles=["manager", "receptionist"],
        writeback=True,
        undoable=True
    )
    def do_something(self, id: int):
        ...
```

## UI Conventions

- Dark theme: bg-dark-950, borders dark-800, accent primary-400
- No `window.alert()` - use Modal component or inline feedback
- Room status colors: green (vacant_clean), red (occupied), yellow (vacant_dirty), gray (out_of_order)
- All modals managed via `useUIStore.openModal(name, data)`
- Icons from `lucide-react`

## API Response Quirks

- Payment amounts return as `float` in JSON, not strings
- Many endpoints return `{"message": "...", "reservation_id": ...}` instead of full object after state changes
- Cancel/mark-no-show endpoints return success message but don't include the updated `status` field
- Use `/billing/stay/{stay_id}` to get bill details, not `/checkout/stay/{stay_id}`
- Some endpoints return 400 (Bad Request) instead of 404 for "not found" cases

## Development Notes

- Backend uses `uv` package manager (python 3.12+)
- Frontend uses npm with Vite
- Database file: `backend/aipms.db` (SQLite)
- Type validation: Pydantic v2
- State management: Zustand for frontend

## Testing

**Test Directories:**
- `backend/tests/api/` - API integration tests (128+ tests)
- `backend/tests/core/` - Core framework unit tests (97 tests)
- `backend/tests/ooda/` - OODA module tests

**Running Tests:**
```bash
cd backend
uv run pytest tests/api/ -v           # API tests
uv run pytest tests/core/ -v          # Core framework tests
uv run pytest -k "test_name"          # Single test by name
```

**Test Patterns:**
- Use `db_session` fixture for database operations (not `SessionLocal()`)
- Use `params=` for query parameters, `json=` for JSON bodies
- Event handlers don't work in test environment - use `@pytest.mark.skip(reason="事件处理器在测试环境中未正确初始化")`

**Known Quirks:**
- Some endpoints return 400 instead of 404 for "not found" cases
- Decimal amounts often return as strings in JSON responses
