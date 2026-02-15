# core/domain 职责分离修复 — 完整重构记录

**日期**: 2026-02-15
**基线**: 2614 tests passed, 5 skipped
**最终**: 2622 tests passed, 5 skipped (+8 新增测试)
**涉及模块**: `core/security/`, `core/ai/`, `core/reasoning/`, `app/hotel/`, `app/services/actions/`, `app/main.py`

---

## 背景与动机

上一轮 `ai_service.py` 解耦（SPEC-1~14）完成后，对架构进行深度评估发现三类问题：

### 问题 1：core 层领域泄漏（3 处）

`core/` 作为领域无关的 ontology 运行时框架，不应包含任何酒店业务逻辑。但以下 3 处存在硬编码：

| 位置 | 泄漏内容 |
|------|----------|
| `core/security/checker.py:124-153` | `RECEPTIONIST_PERMISSIONS`、`CLEANER_PERMISSIONS`、`MANAGER_PERMISSIONS` 硬编码了 `room`、`guest`、`reservation` 等酒店资源名 |
| `core/ai/query_keywords.py:18-28` | `ACTION_KEYWORDS` 包含 `入住`、`退房`、`预订`、`换房`、`续住`、`清洁` 等酒店操作关键词 |
| `core/reasoning/constraint_engine.py:195-251` | `PhoneUniquenessValidator` 硬编码 `OntologyRegistry().get_model("Guest")` |

### 问题 2：实体注册内聚性差

`hotel_domain_adapter.py` 长达 1280 行，新增一个实体需要在 6 个方法中分别插入代码：
- `_register_entities()` — 实体元数据
- `_register_state_machines()` — 状态机定义
- `_register_constraints()` — 约束定义
- `_register_events()` — 事件定义
- `_register_relationships()` — 关系定义
- `_register_models()` — ORM 类注册

### 问题 3：参数增强 switch-case

`enhance_action_params()` 方法 100+ 行 if/elif 混合了所有实体的参数解析逻辑，每个新 action 都要在这里加分支，违反开闭原则。

### 重构目标

1. `core/` 层零酒店业务泄漏（通过架构守卫测试 + grep 验证）
2. 新增实体 = 新建 1 个注册文件 + `__init__.py` 加 1 行导入（强内聚）
3. 参数增强与 action handler 共定位（`ActionDefinition.param_enhancer`）

---

## Phase 1：修复 core 层领域泄漏（P0）

### SPEC-1：移除 checker.py 硬编码酒店角色权限

**问题分析**

`core/security/checker.py` 在类级别定义了三个权限常量：

```python
# 修改前 — core/security/checker.py
MANAGER_PERMISSIONS = [Permission("*", "*")]
RECEPTIONIST_PERMISSIONS = [
    Permission("room", "read"),
    Permission("room", "update_status"),
    Permission("guest", "read"),
    Permission("guest", "create"),
    # ... 酒店特定资源
]
CLEANER_PERMISSIONS = [
    Permission("room", "read"),
    Permission("task", "read"),
    Permission("task", "update"),
]
```

`_role_permissions` 字典在 `__init__` 中直接用这些常量预填充。虽然 `register_role_permissions()` 方法已存在（`checker.py:155-166`），但 `app/main.py` 从未调用它。

**解决方案**

采用启动注入模式：`core/` 只提供空容器和注册接口，`app/` 在启动时注入具体权限。

**修改文件**

#### 1. `core/security/checker.py`

删除 `MANAGER_PERMISSIONS`、`RECEPTIONIST_PERMISSIONS`、`CLEANER_PERMISSIONS` 三个类级别常量。`_role_permissions` 初始化改为空字典：

```python
# 修改后
def __init__(self):
    self._role_permissions: Dict[str, Set[Permission]] = {}
```

#### 2. `app/hotel/security/__init__.py`（新建）

将酒店角色权限定义迁移到 app 层：

```python
from typing import Dict, List
from core.security.checker import Permission

HOTEL_ROLE_PERMISSIONS: Dict[str, List[Permission]] = {
    "manager": [Permission("*", "*")],
    "receptionist": [
        Permission("room", "read"),
        Permission("room", "update_status"),
        Permission("guest", "read"),
        Permission("guest", "create"),
        Permission("guest", "update"),
        Permission("reservation", "read"),
        Permission("reservation", "create"),
        Permission("reservation", "update"),
        Permission("checkin", "create"),
        Permission("checkout", "create"),
        Permission("bill", "read"),
        Permission("bill", "create"),
        Permission("task", "read"),
        Permission("task", "create"),
    ],
    "cleaner": [
        Permission("room", "read"),
        Permission("task", "read"),
        Permission("task", "update"),
    ],
}

def register_hotel_role_permissions() -> None:
    from core.security.checker import permission_checker
    for role, permissions in HOTEL_ROLE_PERMISSIONS.items():
        permission_checker.register_role_permissions(role, permissions)
```

#### 3. `app/main.py`

在 startup lifespan 中添加注册调用：

```python
from app.hotel.security import register_hotel_role_permissions
register_hotel_role_permissions()
```

#### 4. `tests/security/test_checker.py`

测试原来依赖硬编码权限自动存在。改为先注册再断言：

```python
def _register_hotel_permissions(rule):
    """Register hotel permissions for testing."""
    rule.register_role_permissions("manager", [Permission("*", "*")])
    rule.register_role_permissions("receptionist", [
        Permission("room", "read"), Permission("room", "update_status"),
        # ...
    ])
    rule.register_role_permissions("cleaner", [
        Permission("room", "read"), Permission("task", "read"), Permission("task", "update"),
    ])
```

每个相关测试方法开头调用 `_register_hotel_permissions()`。

**验证**

```bash
grep -rn "receptionist\|cleaner\|RECEPTIONIST\|CLEANER" backend/core/security/checker.py
# 零结果 ✓
```

---

### SPEC-2：移除 query_keywords.py 硬编码酒店关键词

**问题分析**

`core/ai/query_keywords.py` 的 `ACTION_KEYWORDS` 集合包含酒店特定操作词：

```python
# 修改前
ACTION_KEYWORDS = {
    '入住', '退房', '预订', '换房', '续住', '清洁',
    '创建', '修改', '删除', '取消', '执行', '分配', '完成', '启动',
    # ...
}
```

这些关键词在 `OodaOrchestrator._identify_intent()` 中作为 fallback 判断用户意图是否为 mutation。

**解决方案**

`ACTION_KEYWORDS` 仅保留通用动词，酒店关键词通过构造器注入。

**修改文件**

#### 1. `core/ai/query_keywords.py`

```python
# 修改后 — 仅保留通用动词
ACTION_KEYWORDS = {
    '创建', '修改', '删除', '取消', '执行', '分配', '完成', '启动',
    '新建', '添加', '更新', '移除',
    'create', 'update', 'delete', 'cancel', 'execute', 'assign',
    'complete', 'start', 'add', 'remove', 'modify',
}
```

#### 2. `core/ai/ooda_orchestrator.py`

`__init__` 新增 `domain_action_keywords` 参数：

```python
def __init__(self, ..., domain_action_keywords=None):
    # ...
    self._domain_action_keywords = domain_action_keywords or []
```

`_identify_intent()` 的 fallback 检查合并通用 + 领域关键词：

```python
all_action_keywords = list(ACTION_KEYWORDS) + list(self._domain_action_keywords)
if any(kw in message for kw in all_action_keywords):
    return "mutation"
```

#### 3. `app/services/ai_service.py`

`AIService.__init__` 传入酒店关键词：

```python
hotel_action_keywords = [
    '入住', '办理入住', 'checkin', 'check in',
    '退房', '结账', 'checkout', 'check out',
    '预订', '预约', '订房', 'reserve', 'booking',
    '换房', '转房', '续住', '延期',
    '清洁', '打扫', 'cleaning',
]
super().__init__(..., domain_action_keywords=hotel_action_keywords)
```

**验证**

```bash
grep -rn '入住\|退房\|预订\|换房\|续住\|清洁' backend/core/ai/query_keywords.py
# 零结果 ✓
```

---

### SPEC-3：泛化 PhoneUniquenessValidator

**问题分析**

`core/reasoning/constraint_engine.py` 中的 `PhoneUniquenessValidator` 硬编码了 `"Guest"` 实体名：

```python
# 修改前
class PhoneUniquenessValidator:
    def validate(self, value, db, exclude_id=None):
        model = OntologyRegistry().get_model("Guest")  # 硬编码
        query = db.query(model).filter(model.phone == value)
```

**解决方案**

重命名为 `FieldUniquenessValidator`，通过构造器参数指定实体和字段。

**修改文件**

#### 1. `core/reasoning/constraint_engine.py`

```python
# 修改后
class FieldUniquenessValidator:
    """Validates field uniqueness for any entity."""

    def __init__(self, entity_name: str, field_name: str):
        self._entity_name = entity_name
        self._field_name = field_name

    def validate(self, value, db, exclude_id=None):
        model = OntologyRegistry().get_model(self._entity_name)
        if model is None:
            return True
        field_attr = getattr(model, self._field_name, None)
        if field_attr is None:
            return True
        query = db.query(model).filter(field_attr == value)
        # ...
```

注意：`entity_name` 和 `field_name` 均为必填参数，无默认值。此前考虑过保留 `PhoneUniquenessValidator` 作为向后兼容别名（使用默认参数 `entity_name="Guest"`），但这会导致 `"Guest"` 仍然出现在 core 层代码中，因此直接删除别名。经检查无外部调用者依赖旧名称。

#### 2. `app/hotel/hotel_domain_adapter.py`

实例化时显式传入参数：

```python
FieldUniquenessValidator(entity_name="Guest", field_name="phone")
```

**验证**

```bash
grep -rn '"Guest"' backend/core/reasoning/constraint_engine.py
# 零结果 ✓
```

---

### Phase 1 完成验证

```
Tests: 2614 passed, 5 skipped
Architecture guard: grep -r "from app." backend/core/ → 零结果 ✓
```

---

## Phase 2：实体注册文件级拆分（P1）

### SPEC-4：创建 entities/ 目录结构和注册协议

**设计思路**

定义 `EntityRegistration` 数据类，将每个实体的元数据、状态机、约束、事件封装为一个完整的注册单元。每个实体一个文件，导出 `get_registration()` 函数。

**新建文件结构**

```
app/hotel/entities/
├── __init__.py            # EntityRegistration 数据类 + 汇总函数
├── room.py                # Room: metadata + state_machine + 4 constraints + 2 events
├── guest.py               # Guest: metadata + 3 constraints + 1 event
├── reservation.py         # Reservation: metadata + state_machine + 4 constraints + 2 events
├── stay_record.py         # StayRecord: metadata + state_machine + 3 constraints + 2 events
├── task.py                # Task: metadata + state_machine + 3 constraints + 2 events
├── bill.py                # Bill: metadata + 3 constraints
├── payment.py             # Payment: metadata
├── employee.py            # Employee: metadata
├── room_type.py           # RoomType: metadata
├── rate_plan.py           # RatePlan: metadata
└── relationships.py       # 15 对双向关系
```

**核心数据结构**

```python
# app/hotel/entities/__init__.py
@dataclass
class EntityRegistration:
    """单个实体的完整注册信息"""
    metadata: EntityMetadata
    model_class: type
    state_machine: Optional[StateMachine] = None
    constraints: List[ConstraintMetadata] = field(default_factory=list)
    events: List[EventMetadata] = field(default_factory=list)

def get_all_entity_registrations() -> List[EntityRegistration]:
    """汇总所有实体的注册信息"""
    return [
        room.get_registration(),
        guest.get_registration(),
        reservation.get_registration(),
        stay_record.get_registration(),
        task.get_registration(),
        bill.get_registration(),
        payment.get_registration(),
        employee.get_registration(),
        room_type.get_registration(),
        rate_plan.get_registration(),
    ]

def get_all_relationships() -> List[Tuple[str, RelationshipMetadata]]:
    """汇总所有关系定义"""
    return relationships.get_relationships()
```

**实体文件示例（room.py）**

```python
# app/hotel/entities/room.py
def get_registration() -> EntityRegistration:
    return EntityRegistration(
        metadata=EntityMetadata(
            name="Room",
            display_name="客房",
            description="酒店客房",
            category="resource",
            importance=10,
        ),
        model_class=Room,
        state_machine=StateMachine(
            entity="Room",
            states=["vacant_clean", "vacant_dirty", "occupied", "out_of_order", "maintenance"],
            transitions=[
                StateTransition(from_state="vacant_clean", to_state="occupied", action="check_in", ...),
                # ...
            ],
        ),
        constraints=[
            ConstraintMetadata(entity="Room", field="room_number", constraint_type="unique", ...),
            ConstraintMetadata(entity="Room", field="status", constraint_type="state_valid", ...),
            # ...
        ],
        events=[
            EventMetadata(entity="Room", event_name="room_status_changed", ...),
            EventMetadata(entity="Room", event_name="room_maintenance_requested", ...),
        ],
    )
```

**数据提取统计**

从 `hotel_domain_adapter.py` 的 5 个注册方法中提取：

| 类型 | 数量 |
|------|------|
| 实体元数据 | 10 |
| 状态机 | 4（Room, Reservation, StayRecord, Task） |
| 约束 | 20 |
| 事件 | 9 |
| 关系对 | 15 |

---

### SPEC-5：重构 HotelDomainAdapter 使用 entities/ 模块

**修改文件**: `app/hotel/hotel_domain_adapter.py`

**修改前**

```python
class HotelDomainAdapter(IDomainAdapter):
    def register_ontology(self, registry):
        self._register_models(registry)       # ~30 行
        self._register_entities(registry)      # ~150 行（10 个实体的 metadata）
        self._register_relationships(registry) # ~100 行（15 对关系）
        self._register_state_machines(registry)# ~120 行（4 个状态机）
        self._register_constraints(registry)   # ~150 行（20 个约束）
        self._register_events(registry)        # ~80 行（9 个事件）
        self._auto_register_properties(registry)
```

**修改后**

```python
class HotelDomainAdapter(IDomainAdapter):
    def register_ontology(self, registry):
        self._register_models(registry)
        self._register_entities(registry)
        self._register_relationships(registry)
        self._auto_register_properties(registry)

    def _register_entities(self, registry):
        """Register all hotel entities from entity registration files."""
        from app.hotel.entities import get_all_entity_registrations
        for reg in get_all_entity_registrations():
            registry.register_entity(reg.metadata)
            if reg.state_machine:
                registry.register_state_machine(reg.metadata.name, reg.state_machine)
            for constraint in reg.constraints:
                registry.register_constraint(reg.metadata.name, constraint)
            for event in reg.events:
                registry.register_event(reg.metadata.name, event)

    def _register_relationships(self, registry):
        """Register all hotel entity relationships."""
        from app.hotel.entities import get_all_relationships
        for entity_name, rel_meta in get_all_relationships():
            registry.register_relationship(entity_name, rel_meta)
```

**删除的方法**：`_register_state_machines()`、`_register_constraints()`、`_register_events()`

**删除的导入**：`StateMachine`、`StateTransition`、`ConstraintMetadata`、`EventMetadata` 等（从 `core/ontology/metadata.py`）

**效果**：1280 行 → 652 行（删减约 630 行）

**注意事项**

在这一步遇到了一个编辑陷阱：尝试一次性替换 500+ 行的代码块时，Edit 工具产生了混乱的"PLACEHOLDER"伪代码，需要多次清理。教训是大块替换应拆分为多次小编辑。

---

### SPEC-6：验证 + 新增测试

**新建文件**: `tests/domain/test_entity_registrations.py`

新增 8 个测试用例验证 EntityRegistration 协议完整性：

| 测试 | 验证内容 |
|------|----------|
| `test_all_entities_registered` | 10 个实体全部注册 |
| `test_entity_names_match_metadata` | metadata.name 与文件定义一致 |
| `test_state_machines_present` | Room/Reservation/StayRecord/Task 有状态机 |
| `test_constraints_count` | 约束总数 ≥ 15 |
| `test_events_count` | 事件总数 ≥ 5 |
| `test_relationships_count` | 关系对数 ≥ 10 |
| `test_model_classes_have_tablename` | 所有 model_class 有 `__tablename__` |
| `test_registration_protocol_completeness` | metadata 和 model_class 非 None |

**测试结果**: 2622 passed（2614 + 8 新增），5 skipped

---

### Phase 2 完成验证

```
Tests: 2622 passed, 5 skipped
adapter 行数: 652（从 1280 减少）
entity 文件数: 12
```

---

## Phase 3：参数增强注册表驱动（P2）

### SPEC-7：ActionDefinition 新增 param_enhancer 字段

**设计思路**

在 `ActionDefinition` 数据类中新增可选的 `param_enhancer` 字段，允许每个 action 注册自己的参数增强函数，而不是全部堆在 adapter 的 `enhance_action_params()` 里。

**修改文件**: `core/ai/actions.py`

```python
# ActionDefinition 新增字段
@dataclass
class ActionDefinition:
    name: str
    entity: str
    description: str
    # ... 其他字段 ...
    param_enhancer: Optional[Callable[[Dict[str, Any], Any], Dict[str, Any]]] = None

# register() 装饰器接受 param_enhancer 参数
def register(self, ..., param_enhancer=None):
    # ...
    definition = ActionDefinition(
        # ...
        param_enhancer=param_enhancer,
    )
```

**函数签名约定**

```python
def my_enhancer(params: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """接收参数字典和数据库会话，返回增强后的参数字典"""
    # 执行 DB 查询解析参数
    return params
```

---

### SPEC-8：OodaOrchestrator 使用 param_enhancer 管道

**设计决策**

关键决策：param_enhancer 和 adapter.enhance_action_params 的关系是**管道（pipeline）**而非**二选一（either/or）**。

- **action-level enhancer**：处理 action 特有的 DB 查询（如 `guest_name → stay_record_id`）
- **adapter-level enhancement**：处理通用逻辑（日期解析、`room_number → room_id`、`reservation_no → reservation_id`）

两者按顺序执行，action-level 先跑，adapter-level 后跑。

**修改文件**: `core/ai/ooda_orchestrator.py`

```python
def _enhance_actions_with_db_data(self, result: Dict) -> Dict:
    registry = self.get_action_registry()
    for action in result.get("suggested_actions", []):
        params = action.get("params", {})
        action_type = action.get("action_type", "")

        # Step 1: Action-level enhancer (action-specific DB lookups)
        if registry:
            action_def = registry.get_action(action_type)
            if action_def and action_def.param_enhancer:
                try:
                    params = action_def.param_enhancer(params, self.db)
                except Exception as e:
                    logger.warning(f"param_enhancer failed for {action_type}: {e}")

        # Step 2: Adapter-level enhancement (generic field parsing)
        params = self.adapter.enhance_action_params(action_type, params, "", self.db)
        action["params"] = params
    return result
```

**为什么不用 either/or**

如果用 either/or，action-level enhancer 执行后，adapter 的通用逻辑（日期解析、`room_number → room_id` 等）会被跳过，导致参数不完整。管道模式确保两层增强都执行。

---

### SPEC-9：将酒店参数增强逻辑迁移到 action handler 文件

**迁移清单**

从 `hotel_domain_adapter.py` 的 `enhance_action_params()` 中提取 3 组 action-specific 逻辑：

#### 1. stay_actions.py — `_enhance_stay_params`

```python
def _enhance_stay_params(params: Dict[str, Any], db) -> Dict[str, Any]:
    """Enhance stay action params: resolve guest_name → stay_record_id."""
    if "guest_name" in params and "stay_record_id" not in params:
        checkin_svc = CheckInService(db)
        stays = checkin_svc.search_active_stays(params["guest_name"])
        if stays:
            params["stay_record_id"] = stays[0].id
    return params
```

注册到 3 个 action：`checkout`、`extend_stay`、`change_room`

```python
@registry.register(
    name="checkout",
    # ...
    param_enhancer=_enhance_stay_params,
)
```

#### 2. reservation_actions.py — `_enhance_reservation_params`

```python
def _enhance_reservation_params(params: Dict[str, Any], db) -> Dict[str, Any]:
    """Enhance reservation action params: resolve guest_name → reservation_id."""
    if "guest_name" in params and "reservation_id" not in params and "reservation_no" not in params:
        res_svc = ReservationService(db)
        reservations = res_svc.search_reservations(params["guest_name"])
        confirmed = [r for r in reservations if r.status.value.upper() == "CONFIRMED"]
        if confirmed:
            params["reservation_id"] = confirmed[0].id
    return params
```

注册到 2 个 action：`cancel_reservation`、`modify_reservation`

#### 3. bill_actions.py — `_enhance_bill_params`

```python
def _enhance_bill_params(params: Dict[str, Any], db) -> Dict[str, Any]:
    """Enhance bill action params: resolve room_number → stay_record_id."""
    if "room_number" in params and "stay_record_id" not in params and "bill_id" not in params:
        from app.services.checkin_service import CheckInService
        checkin_svc = CheckInService(db)
        stays = checkin_svc.search_active_stays(params["room_number"])
        if stays:
            params["stay_record_id"] = stays[0].id
    return params
```

注册到 2 个 action：`add_payment`、`adjust_bill`

#### 4. hotel_domain_adapter.py — 删除迁移走的代码

从 `enhance_action_params()` 中删除以下 3 个 if-block（共约 18 行）：

```python
# 删除：guest_name → stay_record_id for checkout/extend_stay/change_room
if "guest_name" in params and action_type in ["checkout", "extend_stay", "change_room"]:
    stays = self.checkin_service.search_active_stays(params["guest_name"])
    if stays and "stay_record_id" not in params:
        params["stay_record_id"] = stays[0].id

# 删除：guest_name → reservation_id for cancel/modify reservation
if "guest_name" in params and action_type in ["cancel_reservation", "modify_reservation"]:
    if "reservation_id" not in params and "reservation_no" not in params:
        reservations = self.reservation_service.search_reservations(params["guest_name"])
        confirmed = [r for r in reservations if r.status.value.upper() == "CONFIRMED"]
        if confirmed:
            params["reservation_id"] = confirmed[0].id

# 删除：room_number → stay_record_id for add_payment/adjust_bill
if "room_number" in params and action_type in ["add_payment", "adjust_bill"]:
    if "stay_record_id" not in params and "bill_id" not in params:
        stays = self.checkin_service.search_active_stays(params["room_number"])
        if stays:
            params["stay_record_id"] = stays[0].id
```

**adapter 中保留的通用逻辑**

以下逻辑不属于特定 action，继续保留在 adapter 的 `enhance_action_params()` 中：

| 逻辑 | 说明 |
|------|------|
| `room_type` 解析 | 名称/ID 模糊匹配，多个 action 共用 |
| `room_status` 别名 | 中文状态名映射 |
| `task_type` 别名 | 中文任务类型映射 |
| `assignee_name → assignee_id` | 员工名查找 |
| `price_type` 别名 | 价格类型映射 |
| `room_number → room_id` | 通用房间号查找 |
| `reservation_no → reservation_id` | 通用预订号查找 |
| 日期解析 | 相对日期（明天、后天）→ ISO 日期 |

---

### SPEC-10：最终验证

**全量测试**

```
2622 passed, 5 skipped ✓
```

**架构守卫验证**

| 检查项 | 命令 | 结果 |
|--------|------|------|
| core 无 app 导入 | `grep -r "from app\." backend/core/ --include="*.py"` | 零结果 ✓ |
| checker.py 无酒店角色 | `grep -rn "receptionist\|cleaner\|RECEPTIONIST\|CLEANER" backend/core/security/checker.py` | 零结果 ✓ |
| query_keywords.py 无酒店词 | `grep -rn '入住\|退房\|预订\|换房\|续住\|清洁' backend/core/ai/query_keywords.py` | 零结果 ✓ |
| constraint_engine.py 无 Guest | `grep -rn '"Guest"' backend/core/reasoning/constraint_engine.py` | 零结果 ✓ |
| param_enhancer 注册数 | `grep -rn "param_enhancer=" backend/app/services/actions/*.py \| wc -l` | 6 ✓ |
| entity 文件数 | `ls backend/app/hotel/entities/*.py \| wc -l` | 12 ✓ |
| adapter 行数 | `wc -l backend/app/hotel/hotel_domain_adapter.py` | 634 ✓ |

---

## 变更文件总览

### 新建文件（15 个）

| 文件 | 说明 |
|------|------|
| `app/hotel/security/__init__.py` | 酒店角色权限定义 + 注册函数 |
| `app/hotel/entities/__init__.py` | EntityRegistration 数据类 + 汇总入口 |
| `app/hotel/entities/room.py` | Room 实体注册 |
| `app/hotel/entities/guest.py` | Guest 实体注册 |
| `app/hotel/entities/reservation.py` | Reservation 实体注册 |
| `app/hotel/entities/stay_record.py` | StayRecord 实体注册 |
| `app/hotel/entities/task.py` | Task 实体注册 |
| `app/hotel/entities/bill.py` | Bill 实体注册 |
| `app/hotel/entities/payment.py` | Payment 实体注册 |
| `app/hotel/entities/employee.py` | Employee 实体注册 |
| `app/hotel/entities/room_type.py` | RoomType 实体注册 |
| `app/hotel/entities/rate_plan.py` | RatePlan 实体注册 |
| `app/hotel/entities/relationships.py` | 实体关系定义 |
| `tests/domain/test_entity_registrations.py` | EntityRegistration 协议测试（8 tests） |

### 修改文件（10 个）

| 文件 | 变更类型 |
|------|----------|
| `core/security/checker.py` | 删除硬编码权限常量 |
| `core/ai/query_keywords.py` | 清理 ACTION_KEYWORDS |
| `core/ai/ooda_orchestrator.py` | 新增 `domain_action_keywords`、param_enhancer 管道 |
| `core/ai/actions.py` | ActionDefinition 新增 `param_enhancer` |
| `core/reasoning/constraint_engine.py` | 重命名 + 参数化 |
| `app/hotel/hotel_domain_adapter.py` | 实体注册重构 + 删除 action-specific 增强（1280→634 行） |
| `app/services/ai_service.py` | 传入 `domain_action_keywords` |
| `app/services/actions/stay_actions.py` | 新增 `_enhance_stay_params` |
| `app/services/actions/reservation_actions.py` | 新增 `_enhance_reservation_params` |
| `app/services/actions/bill_actions.py` | 新增 `_enhance_bill_params` |
| `app/main.py` | 添加角色权限注册调用 |
| `tests/security/test_checker.py` | 适配权限注入 |

---

## 经验总结

### 设计模式

1. **启动注入模式（Startup Injection）**：core 提供空容器 + 注册接口，app 在启动时注入领域配置。适用于权限、关键词等领域特定数据。

2. **注册协议模式（Registration Protocol）**：定义 `EntityRegistration` 数据类作为实体注册的标准协议，每个实体文件导出 `get_registration()` 函数。新增实体只需新建文件 + `__init__.py` 加一行导入。

3. **增强管道模式（Enhancement Pipeline）**：`param_enhancer`（action 级）→ `enhance_action_params`（adapter 级）按顺序执行，而非二选一。action 级处理特定 DB 查询，adapter 级处理通用解析。

### 踩坑记录

| 坑 | 触发场景 | 解决方案 |
|----|----------|----------|
| 大块代码替换混乱 | 用 Edit 工具替换 500+ 行 | 拆分为多次小编辑，每次 ≤ 100 行 |
| 向后兼容别名泄漏 | 在 core 中保留 `PhoneUniquenessValidator` 带默认 `"Guest"` | 确认无调用者后直接删除，必填参数无默认值 |
| 增强逻辑丢失 | enhancer 设计为 either/or | 改为管道模式，两层都执行 |

### 量化成果

| 指标 | 修改前 | 修改后 |
|------|--------|--------|
| core 层酒店引用 | 3 处 | 0 处 |
| hotel_domain_adapter.py 行数 | 1280 行 | 634 行 |
| 新增实体所需修改文件数 | 6 个方法 | 1 个文件 + 1 行导入 |
| enhance_action_params 中 action-specific 分支 | 3 个 if-block | 0（迁移到 handler） |
| 测试数 | 2614 | 2622 (+8) |
