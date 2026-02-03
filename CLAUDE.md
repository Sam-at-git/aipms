# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AIPMS is a smart hotel management system built on **Palantir-inspired ontology-driven architecture**. All operations go through domain objects (Room, Guest, Reservation, StayRecord, etc.) rather than direct database access. The system combines a digital twin display (left panel) with an AI conversational interface (right panel).

## Build & Run Commands

### Backend (FastAPI + SQLite)
```bash
cd backend
uv sync                              # Install dependencies
uv run python init_data.py           # Initialize database with seed data
uv run uvicorn app.main:app --reload --port 8000

# Run tests
uv run pytest                        # Run all tests
uv run pytest tests/test_file.py     # Run specific test file
uv run pytest -k "test_name"         # Run tests matching pattern
```

### Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev                          # Dev server on http://localhost:3000
npm run build                        # TypeScript check + production build
npm run preview                      # Preview production build
```

### Combined
```bash
./start.sh                           # Starts both backend and frontend
```

### Default Credentials
- manager / 123456 (full access)
- front1 / 123456 (receptionist)
- cleaner1 / 123456 (cleaner - tasks only)

## Architecture

### Backend Structure
```
backend/app/
├── models/
│   ├── ontology.py     # Domain objects (Room, Guest, Reservation, StayRecord, Bill, Task, Employee, RatePlan)
│   ├── schemas.py      # Pydantic models for API I/O
│   ├── events.py       # Domain event definitions (EventType enum, event data classes)
│   └── snapshots.py    # OperationSnapshot and ConfigHistory models for undo
├── services/           # Business logic layer (one service per domain)
│   ├── llm_service.py        # OpenAI-compatible LLM integration with robust JSON extraction
│   ├── ai_service.py         # OODA loop: LLM优先，规则兜底
│   ├── conversation_service.py # Chat history persistence (JSONL per user/day)
│   ├── param_parser_service.py # Extracts entities (rooms, guests, dates) from natural language
│   ├── audit_service.py      # Tracks all operations for compliance
│   ├── event_bus.py          # In-memory pub/sub event bus (singleton)
│   ├── event_handlers.py     # Event handlers (auto-create cleaning task, update room status)
│   ├── undo_service.py       # Operation snapshot creation and rollback logic
│   └── config_history_service.py # Configuration version management
├── routers/            # FastAPI endpoints (one router per domain)
├── security/auth.py    # JWT authentication + role-based access
├── config.py           # Environment-based settings (LLM API config)
├── database.py         # SQLAlchemy session management
└── main.py             # App initialization
```

### Frontend Structure
```
frontend/src/
├── pages/              # Route pages (Dashboard, Rooms, Reservations, etc.)
├── components/         # Reusable UI (Layout, ChatPanel, Modal, RoomCard, UndoButton)
├── services/api.ts     # Axios HTTP client organized by domain (includes undoApi)
├── store/index.ts      # Zustand stores (auth, chat, dashboard, ui)
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

**LLM Integration** (`llm_service.py`):
- OpenAI-compatible API support (DeepSeek, OpenAI, Azure, Ollama, etc.)
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
- Services publish domain events (e.g., `GUEST_CHECKED_OUT`, `TASK_COMPLETED`)
- Event handlers subscribe to events and trigger side effects:
  - `GUEST_CHECKED_OUT` → auto-creates cleaning task
  - `TASK_COMPLETED` (cleaning) → room becomes VACANT_CLEAN
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
- `/reservations/*` - CRUD, search, today's arrivals
- `/checkin/*` - From reservation, walk-in, extend stay, change room
- `/checkout/*` - Execute checkout, expected/overdue lists
- `/billing/*` - Bills, payments, adjustments (manager only)
- `/tasks/*` - CRUD, assignment, start/complete
- `/reports/*` - Dashboard stats, occupancy, revenue
- `/ai/*` - Chat with context, execute confirmed actions
- `/conversations/*` - Chat history persistence, search, pagination
- `/settings/*` - LLM configuration (manager only)
- `/audit-logs/*` - Audit trail (manager only)
- `/guests/*` - Guest CRM (tier, preferences, blacklist)
- `/undo/*` - Operation undo (list undoable operations, execute undo)

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
- `create_reservation` - Create new booking (requires: guest_name, guest_phone, room_type_id, dates)
- `cancel_reservation` - Cancel booking (requires: reservation_id, cancel_reason)

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

## UI Conventions

- Dark theme: bg-dark-950, borders dark-800, accent primary-400
- No `window.alert()` - use Modal component or inline feedback
- Room status colors: green (vacant_clean), red (occupied), yellow (vacant_dirty), gray (out_of_order)
- All modals managed via `useUIStore.openModal(name, data)`
- Icons from `lucide-react`

## Development Notes

- Backend uses `uv` package manager (python 3.10+)
- Frontend uses npm with Vite
- Database file: `backend/aipms.db` (SQLite)
- Type validation: Pydantic v2 on both frontend and backend
- State management: Zustand for frontend, global `settings` instance for backend config
