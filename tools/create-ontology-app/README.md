# create-ontology-app

Scaffold generator for **Ontology Runtime** applications. Generates a complete full-stack project (FastAPI backend + React frontend) with an AI-powered natural language interface, driven by a domain-agnostic ontology framework.

## Quick Start

```bash
# Install
cd tools/create-ontology-app
pip install -e .

# Generate a new project
create-ontology-app /tmp/my-clinic --domain clinic --display-name "Clinic"

# Start the generated project
cd /tmp/my-clinic
cd backend && uv sync && uv run python init_data.py
cd backend && uv run uvicorn app.main:app --reload --port 8020
cd frontend && npm install && npm run dev
```

Login with `sysadmin / 123456`.

## CLI Options

```
create-ontology-app <project_path> [OPTIONS]

Arguments:
  project_path          Project directory path (will be created)

Options:
  --domain TEXT         Domain name in snake_case (default: my_domain)
  --display-name TEXT   Human-readable domain name (default: PascalCase of domain)
  --backend-port INT    Backend server port (default: 8020)
  --frontend-port INT   Frontend dev server port (default: 3020)
  --description TEXT    Project description
  --no-git              Skip git init
  --no-install          Skip dependency installation (uv sync, npm install)
```

### Example

```bash
# Hospital management system
create-ontology-app ./my-hospital --domain hospital --display-name "Hospital"

# Warehouse management
create-ontology-app ./my-warehouse --domain warehouse --backend-port 8030

# Skip auto-install for CI
create-ontology-app ./my-app --domain app --no-install --no-git
```

## Generated Project Structure

```
<project>/
├── backend/
│   ├── core/                          # Ontology Runtime Framework (DO NOT EDIT)
│   │   ├── ai/                        # AI pipeline (OODA, prompts, actions, search)
│   │   ├── ontology/                  # Registry, metadata, query engine
│   │   ├── ooda/                      # OODA loop phase implementations
│   │   ├── engine/                    # Event bus, rule engine, state machine
│   │   ├── reasoning/                 # Constraint engine, planner
│   │   └── security/                  # ACL, masking, permission checker
│   │
│   ├── app/
│   │   ├── <domain>/                  # YOUR DOMAIN CODE
│   │   │   ├── plugin.py              # Domain plugin (bootstrap entry)
│   │   │   ├── <domain>_domain_adapter.py  # Ontology registration
│   │   │   ├── models/                # SQLAlchemy ORM + Pydantic schemas
│   │   │   ├── actions/               # AI action handlers
│   │   │   ├── services/              # Business logic services
│   │   │   ├── routers/               # FastAPI endpoints
│   │   │   ├── domain/                # Entities, relationships, rules
│   │   │   └── security/              # Role permissions
│   │   │
│   │   ├── system/                    # System management (RBAC, config, etc.)
│   │   ├── models/                    # Shared models
│   │   ├── services/                  # Shared services (LLM, audit, etc.)
│   │   ├── routers/                   # Shared routers (AI chat, auth, etc.)
│   │   ├── main.py                    # App entry point
│   │   └── config.py                  # Settings
│   │
│   ├── tests/
│   │   ├── domain/                    # Architecture guard tests
│   │   └── test_health.py             # Smoke test
│   │
│   ├── pyproject.toml
│   └── init_data.py                   # Database seeding
│
└── frontend/
    ├── src/
    │   ├── pages/<domain>/            # Domain-specific UI pages
    │   ├── pages/system/              # System management pages
    │   ├── services/                  # API clients
    │   ├── store/                     # Zustand state management
    │   ├── types/                     # TypeScript type definitions
    │   └── components/                # Reusable UI components
    ├── package.json
    └── vite.config.ts
```

## Architecture

### Three-Layer Design

| Layer | Directory | Responsibility |
|-------|-----------|----------------|
| **Framework** | `core/` | Domain-agnostic ontology runtime. Zero business logic. |
| **Domain** | `app/<domain>/` | All business-specific code: models, actions, rules. |
| **System** | `app/system/` | Cross-cutting: RBAC, config, scheduler, messaging. |

The `core/` framework is **read-only** -- you build your application entirely in `app/<domain>/`.

### AI Pipeline

The framework implements an OODA (Observe-Orient-Decide-Act) loop with three-phase prompt optimization:

1. **Phase 3 - Dynamic Tool Discovery**: LLM discovers actions on-demand via `<tool_call>` protocol (smallest prompt)
2. **Phase 2 - Intent-Driven Inference**: Filters schema based on detected user intent
3. **Phase 1 - Role-Based Filtering**: Excludes irrelevant action categories by user role
4. **Fallback**: Full schema injection (all entities and actions)

Each phase gracefully degrades to the next if it cannot produce a result.

### Key Framework Components

| Module | Purpose |
|--------|---------|
| `core/ai/ooda_orchestrator.py` | Main orchestrator: message in, structured result out |
| `core/ai/actions.py` | `ActionRegistry` -- declarative action registration and dispatch |
| `core/ai/prompt_builder.py` | Dynamic prompt construction from ontology metadata |
| `core/ai/prompt_shaper.py` | Three-phase prompt size optimization |
| `core/ai/action_search.py` | Hybrid keyword + embedding action search |
| `core/ai/tool_call_executor.py` | Text-based tool calling protocol for Phase 3 |
| `core/ai/debug_logger.py` | SQLite-backed AI session observability |
| `core/ontology/registry.py` | `OntologyRegistry` singleton -- central metadata store |
| `core/ontology/query_engine.py` | `StructuredQuery` to SQLAlchemy execution |
| `core/ontology/semantic_query.py` | Dot-notation path queries (e.g. `stays.room.room_number`) |

## Building Your Domain

### 1. Define Models (`app/<domain>/models/ontology.py`)

```python
from sqlalchemy import Column, String, Integer, Enum
from app.database import Base

class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20))
    status = Column(Enum("ACTIVE", "DISCHARGED"), default="ACTIVE")
```

### 2. Register Ontology (`app/<domain>/<domain>_domain_adapter.py`)

Register entities, properties, state machines, relationships, and constraints into `OntologyRegistry`. The adapter implements `IDomainAdapter` and provides metadata that drives the AI pipeline.

### 3. Create Action Handlers (`app/<domain>/actions/`)

```python
from core.ai.actions import ActionRegistry
from pydantic import BaseModel, Field

class AdmitPatientParams(BaseModel):
    patient_name: str = Field(..., description="Patient name")
    ward: str = Field(..., description="Ward assignment")

def register_clinic_actions(registry: ActionRegistry):
    @registry.register(
        name="admit_patient",
        entity="Patient",
        description="Admit a patient to a ward",
        category="mutation",
        requires_confirmation=True,
        search_keywords=["admit", "check in", "register patient"],
    )
    def handle_admit(params: AdmitPatientParams, db, user, **ctx):
        # Business logic here
        return {"success": True, "message": f"Patient {params.patient_name} admitted"}
```

### 4. Configure Plugin (`app/<domain>/plugin.py`)

The plugin is the bootstrap entry point. It registers actions, ontology, events, and security:

```python
class ClinicPlugin:
    name = "clinic"

    def register_actions(self, action_registry):
        register_clinic_actions(action_registry)

    def register_ontology(self, ont_registry):
        ClinicDomainAdapter().register_ontology(ont_registry)

    def register_events(self):
        pass  # Event handlers

    def register_security(self):
        pass  # Role permissions
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | (none) | LLM API key. Without it, rule-based fallback is used. |
| `OPENAI_BASE_URL` | `https://api.deepseek.com` | LLM endpoint (OpenAI-compatible) |
| `LLM_MODEL` | `deepseek-chat` | Model name |
| `LLM_TEMPERATURE` | `0.7` | LLM temperature |
| `LLM_MAX_TOKENS` | `2000` | Max output tokens |
| `ENABLE_LLM` | `true` | Feature toggle |
| `EMBEDDING_API_KEY` | `ollama` | Embedding service key |
| `EMBEDDING_BASE_URL` | `http://localhost:11434/v1` | Embedding endpoint |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model |

## Testing

The generated project includes architecture guard tests that enforce the layer boundaries:

```bash
cd backend
uv run pytest tests/ -v
```

- `test_scaffold_guard.py` -- Ensures `core/` has no imports from `app/`
- `test_domain_separation.py` -- Validates domain isolation
- `test_health.py` -- Basic health check

Coverage target: 95% on `app/` code (configurable in `pyproject.toml`).

## Default Credentials

| Username | Password | Role |
|----------|----------|------|
| sysadmin | 123456 | System admin (full access + debug panel) |
| manager | 123456 | Manager (business operations) |

## Dependencies

- **Python**: >= 3.10
- **Backend**: FastAPI, SQLAlchemy, Pydantic, uvicorn
- **Frontend**: React 18, TypeScript, Vite, Zustand, TailwindCSS
- **Package manager**: [uv](https://github.com/astral-sh/uv) (backend), npm (frontend)
- **Generator**: Typer, Jinja2, Rich
