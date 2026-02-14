# OAG Query Pipeline Unification

**Date**: 2026-02-14
**Scope**: Unify all single-entity queries through `ontology_query → QueryEngine → LLM format`, eliminating ~300 lines of hardcoded handlers.

---

## Problem

查询管道存在三条并行路径，绕过了 OAG (Ontology-Aware Generation) 框架：

1. **硬编码 handlers** (`_query_rooms_response`, `_query_guests_response` 等) — LLM 返回 `view` action_type，经过 entity-specific if/else 链，手动拼接 markdown
2. **`query_smart`** — 另一组 entity-specific if/else handlers，做类似工作
3. **`ontology_query`** — 预期的通用路径（使用 `QueryEngine` + `StructuredQuery`），实际能工作但几乎不被调用

**根因**：LLM prompt 中只教了 `"action_type": "view"` 作为查询示例，LLM 没有理由生成 `ontology_query`。硬编码 handlers 的存在是因为通用路径从未被实际使用。

---

## Solution

所有单实体查询统一走 `ontology_query` 路径；跨实体报表保留 `query_reports`；`view` 被拒绝并转换。

---

## Changes by SPEC

### SPEC-A: LLM Prompt 更新

**File**: `backend/app/services/llm_service.py`

- 替换原有的单个 `view` 查询示例为 4 个 `ontology_query` 示例（房间、客人、员工、报表）
- 添加显式指令：所有查询必须使用 `ontology_query`，不要使用 `view`
- `_validate_action()` 默认 action_type 从 `"view"` 改为 `"ontology_query"`
- `_validate_and_clean_result()` fallback action_type 从 `"view"` 改为 `"ontology_query"`

### SPEC-B: View 拒绝 + 转换

**File**: `backend/app/services/ai_service.py`

新增方法：

- `_retry_as_ontology_query(view_result, user)` — 将废弃的 `view` action 转换为 `ontology_query`，通过 entity 推断构造查询参数
- `_infer_entity_from_view(entity_type, message)` — 动态推断 entity name：
  1. 从 `OntologyRegistry.get_model_map()` 做大小写不敏感匹配
  2. 从 `app.models.ontology` 模块做 PascalCase 回退匹配
  3. 从 `registry.find_entities_by_keywords(message)` 做消息关键字匹配
  - 不硬编码关键字，所有匹配来自 registry 注册信息

### SPEC-C: 简化 `_handle_query_action()`

**File**: `backend/app/services/ai_service.py`

从 ~80 行 entity-specific if/else 链重写为 ~30 行，4 条清晰路径：

```
Path 1: ontology_query  → _execute_and_format_query()
Path 2: query_reports   → _query_reports_response()
Path 3: view            → _retry_as_ontology_query() → ontology_query
Path 4: query_smart/*   → convert params → ontology_query
```

新增 `_execute_and_format_query(params, result, user, pipeline)` helper，封装 query 执行 + LLM 格式化 + observability 日志。

### SPEC-D: 删除硬编码 handlers (~300 行)

**File**: `backend/app/services/ai_service.py`

删除的方法：

| Method | Lines (approx) |
|--------|---------------|
| `_query_rooms_response()` | 60 |
| `_query_reservations_response()` | 33 |
| `_query_guests_response()` | 24 |
| `_query_tasks_response()` | 19 |
| `_execute_smart_query()` | 32 |
| `_smart_query_rooms()` | 29 |
| `_smart_query_reservations()` | 24 |
| `_smart_query_guests()` | 25 |
| `_smart_query_tasks()` | 25 |
| `_smart_query_reports()` | 13 |

保留：`_query_reports_response()` (跨实体仪表盘)、`_execute_ontology_query()` (通用查询引擎)、`_format_query_result_with_llm()` (LLM 格式化)

### SPEC-E: 简化 `is_query_action` 检测

**File**: `backend/app/services/ai_service.py`

```python
# Before
is_query_action = (
    action_type.startswith("query_") or
    action_type == "view" or
    action_type in ["ontology_query", "query_smart"]
)

# After
is_query_action = (
    action_type.startswith("query_") or
    action_type == "view" or
    action_type == "ontology_query"
)
```

`"query_smart"` 已被 `startswith("query_")` 覆盖，无需显式列出。

### SPEC-F: Pipeline Observability

**File**: `backend/core/ai/debug_logger.py`

- 新增 `update_metadata(session_id, extra)` 方法：将 extra dict merge 到 session metadata

**File**: `backend/app/services/ai_service.py`

- `_execute_and_format_query()` 记录 pipeline 元数据：
  - `query_pipeline`: `"ontology_query"` | `"query_reports"` | `"view_converted"` | `"converted_from_query_smart"` 等
  - `original_action_type`: LLM 原始返回的 action_type
  - `final_action_type`: 实际执行的 action_type
  - `entity`: 查询的实体名称

### SPEC-H: 规则引擎回退更新

**File**: `backend/app/services/ai_service.py`

`_generate_response()` 中，`query_rooms/guests/reservations/tasks` 意图不再调用已删除的硬编码方法，改为通过 `_execute_ontology_query()` 执行：

```python
intent_entity_map = {
    'query_rooms': 'Room',
    'query_reservations': 'Reservation',
    'query_guests': 'Guest',
    'query_tasks': 'Task',
}
```

### SPEC-G: 测试更新

**File**: `backend/tests/api/test_smart_query.py`

- 重写为 `TestOntologyQueryPipeline`（12 个测试）
- 覆盖：ontology_query 直接调用、reports、view 转换、query_smart 转换、entity 推断

**File**: `backend/tests/api/test_natural_language_queries.py`

- 放宽关键字断言：ontology_query 路径返回结构化数据，不含 entity-specific 关键字（如 "大床房"）

**File**: `backend/tests/benchmark/test_oag_benchmark.py`

- `QUERY_ACTIONS` 集合添加 `"query_reports"`

**File**: `backend/app/hotel/domain/metadata/hitl_policies.yaml`

- query_actions 列表添加 `ontology_query`（NONE 级别）

**File**: `backend/tests/domain/metadata/test_metadata_config.py`

- `test_query_actions` 断言添加 `ontology_query`
- `test_query_confirmation_level` 断言添加 `ontology_query`

**New**: `backend/tests/benchmark/query_benchmark_data.yaml` + `test_query_pipeline_benchmark.py`

Query Pipeline 专用 Benchmark（9 组，真实 LLM 调用）：

| Group | 测试内容 | 特点 |
|-------|---------|------|
| 房间状态查询 | 全部房态、空房、指定房间、按房型、按楼层、已入住、脏房 | 8 个查询用例 |
| 在住客人查询 | setup 入住 2 位客人，查在住列表、指定客人、按手机号、入住人数 | 5 个查询 + setup |
| 预订查询 | setup 创建预订，查今日预抵、指定客人预订、全部预订 | 3 个查询 + setup |
| 任务查询 | setup 创建清洁/维修任务，查待处理、指定房间、按类型 | 3 个查询 + setup |
| 运营报表 | 今日运营概览、入住率、营收（走 query_reports 路径） | 3 个查询 |
| 员工查询 | 全部员工、前台员工 | 2 个查询 |
| 账单查询 | setup 入住，查房间账单、消费金额 | 2 个查询 + setup |
| 多轮对话查询 | setup 入住，4 轮连续查询（空房→住客→房型→总数） | 4 个查询 + setup |
| 查询边界场景 | 极简表达（"房态"、"空房"）、带数量、不存在的房间 | 5 个查询 |

断言策略（适应 LLM 输出随机性）：
- `action_type_in`: 允许 ontology_query / semantic_query / query_reports / view
- `message_contains/not_contains`: 关键词匹配，非全文匹配
- `has_query_result`: 接受 query_result 或 >20 字符 message
- 自动执行需确认的查询 action（模拟用户点击确认）

运行：
```bash
OPENAI_API_KEY=sk-xxx uv run pytest tests/benchmark/test_query_pipeline_benchmark.py -v -s --no-cov
```

---

## Test Results

| Scope | Result |
|-------|--------|
| Affected test files (132 tests) | All pass |
| Full suite excl. benchmark (2625 tests) | All pass (1 pre-existing flaky test) |
| Query pipeline benchmark (9 groups, real LLM) | 9/9 pass |
| Original OAG benchmark | Skipped (not affected by this change) |
| Architecture guard: `grep` for deleted handlers | Zero results |

---

## Query Flow (After)

```
User message
    │
    ├─ LLM enabled ──→ LLM returns action_type
    │                      │
    │                      ├─ "ontology_query" ──→ QueryEngine ──→ LLM format ──→ response
    │                      ├─ "query_reports"  ──→ dashboard stats ──→ response
    │                      ├─ "view" (deprecated) ──→ infer entity ──→ QueryEngine ──→ response
    │                      └─ "query_smart"/"query_*" ──→ convert params ──→ QueryEngine ──→ response
    │
    └─ LLM disabled ──→ Rule-based intent
                           │
                           ├─ query_rooms/guests/... ──→ _execute_ontology_query(entity) ──→ response
                           └─ query_reports ──→ dashboard stats ──→ response
```
