"""
app/services/actions/base.py

Base module for action parameter models.

Provides Pydantic models for action parameter validation.
These models define the expected parameters for each AI-executable action.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, List, Union
from pydantic import BaseModel, Field, field_validator

from app.models.ontology import TaskType


# ============== Guest Action Parameters ==============

class WalkInCheckInParams(BaseModel):
    """
    散客入住参数

    用于 walkin_checkin 动作，处理无预订客人的直接入住。
    """
    guest_name: str = Field(..., description="客人姓名", min_length=1, max_length=100)
    guest_phone: str = Field(default="", description="客人电话")
    guest_id_type: str = Field(default="身份证", description="证件类型")
    guest_id_number: str = Field(default="", description="证件号码")
    room_id: Union[int, str] = Field(..., description="房间 ID 或房间号")
    expected_check_out: Union[date, str] = Field(..., description="预期退房日期")
    deposit_amount: Union[str, int, float, Decimal] = Field(
        default=0, description="押金金额"
    )

    @field_validator('deposit_amount')
    @classmethod
    def parse_deposit_amount(cls, v: Union[str, int, float, Decimal]) -> Decimal:
        """解析并转换押金金额"""
        if isinstance(v, Decimal):
            if v < 0:
                raise ValueError("押金金额不能为负数")
            return v
        try:
            amount = Decimal(str(v or 0))
            if amount < 0:
                raise ValueError("押金金额不能为负数")
            return amount
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的押金金额: {v}") from e

    @field_validator('expected_check_out')
    @classmethod
    def parse_check_out(cls, v: Union[date, str]) -> date:
        """解析退房日期"""
        if isinstance(v, date):
            if v <= date.today():
                raise ValueError("退房日期必须晚于今天")
            return v
        if isinstance(v, str):
            try:
                parsed = date.fromisoformat(v)
                if parsed <= date.today():
                    raise ValueError("退房日期必须晚于今天")
                return parsed
            except ValueError as e:
                raise ValueError(f"无效的日期格式: {v}. 请使用 YYYY-MM-DD 格式") from e
        raise ValueError(f"无效的日期类型: {type(v)}")


# ============== Stay Action Parameters ==============

class CheckoutParams(BaseModel):
    """
    退房参数

    用于 checkout 动作，办理客人退房手续。
    """
    stay_record_id: int = Field(..., description="住宿记录 ID", gt=0)
    refund_deposit: Union[str, int, float, Decimal] = Field(
        default=0, description="退还押金金额"
    )
    allow_unsettled: bool = Field(default=False, description="是否允许未结清退房")
    unsettled_reason: Optional[str] = Field(default=None, description="未结清原因")

    @field_validator('refund_deposit')
    @classmethod
    def parse_refund_deposit(cls, v: Union[str, int, float, Decimal]) -> Decimal:
        """解析并转换退还押金金额"""
        if isinstance(v, Decimal):
            if v < 0:
                raise ValueError("退还金额不能为负数")
            return v
        try:
            amount = Decimal(str(v or 0))
            if amount < 0:
                raise ValueError("退还金额不能为负数")
            return amount
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的金额: {v}") from e


# ============== Task Action Parameters ==============

class CreateTaskParams(BaseModel):
    """
    创建任务参数

    用于 create_task 动作，创建清洁或维修任务。
    """
    room_id: Union[int, str] = Field(..., description="房间 ID 或房间号")
    task_type: Union[str, TaskType] = Field(
        default="cleaning",
        description="任务类型 (cleaning 或 maintenance)"
    )

    @field_validator('task_type')
    @classmethod
    def normalize_task_type(cls, v: Union[str, TaskType]) -> TaskType:
        """标准化任务类型"""
        if isinstance(v, TaskType):
            return v
        if isinstance(v, str):
            v_lower = v.lower().strip()
            # 映射常见别名
            aliases = {
                'cleaning': ['cleaning', '清洁', '打扫', 'clean', '清洁任务'],
                'maintenance': ['maintenance', '维修', '修理', 'maintain', 'fix']
            }
            for task_type, alias_list in aliases.items():
                if v_lower in [a.lower() for a in alias_list]:
                    return TaskType(task_type)
            # 尝试直接转换
            try:
                return TaskType(v_lower)
            except ValueError:
                pass
        raise ValueError(f"无效的任务类型: {v}. 支持: cleaning, maintenance")


# ============== Reservation Action Parameters ==============

class CreateReservationParams(BaseModel):
    """
    创建预订参数

    用于 create_reservation 动作，创建新的客房预订。
    """
    guest_name: str = Field(..., description="客人姓名", min_length=1, max_length=100)
    guest_phone: str = Field(default="", description="客人电话")
    guest_id_number: Optional[str] = Field(default=None, description="证件号码")
    room_type_id: Union[int, str] = Field(..., description="房型 ID 或名称")
    check_in_date: Union[date, str] = Field(..., description="入住日期")
    check_out_date: Union[date, str] = Field(..., description="退房日期")
    adult_count: int = Field(default=1, description="成人数量", ge=1, le=10)
    child_count: int = Field(default=0, description="儿童数量", ge=0, le=10)
    room_count: int = Field(default=1, description="房间数量", ge=1)
    special_requests: Optional[str] = Field(default=None, description="特殊要求")

    @field_validator('check_in_date', 'check_out_date')
    @classmethod
    def parse_dates(cls, v: Union[date, str]) -> date:
        """解析日期"""
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            try:
                return date.fromisoformat(v)
            except ValueError as e:
                raise ValueError(f"无效的日期格式: {v}. 请使用 YYYY-MM-DD 格式") from e
        raise ValueError(f"无效的日期类型: {type(v)}")

    @field_validator('check_out_date')
    @classmethod
    def validate_check_out_after_check_in(cls, v: date, info) -> date:
        """验证退房日期晚于入住日期"""
        if 'check_in_date' in info.data:
            check_in = info.data['check_in_date']
            if isinstance(check_in, date) and v <= check_in:
                raise ValueError("退房日期必须晚于入住日期")
        return v


# ============== Query Action Parameters ==============

class FilterClauseParams(BaseModel):
    """过滤器子句参数"""
    field: str = Field(..., description="字段路径")
    operator: str = Field(default="eq", description="操作符 (eq, ne, gt, gte, lt, lte, in, like, between)")
    value: Any = Field(..., description="值")

    @field_validator('operator')
    @classmethod
    def validate_operator(cls, v: str) -> str:
        """验证操作符有效"""
        valid_operators = {'eq', 'ne', 'gt', 'gte', 'lt', 'lte', 'in', 'like', 'between'}
        if v not in valid_operators:
            raise ValueError(f"无效的操作符: {v}. 支持: {', '.join(valid_operators)}")
        return v


class JoinClauseParams(BaseModel):
    """连接子句参数"""
    entity: str = Field(..., description="连接实体名称")
    on: str = Field(..., description="连接条件（关系属性名）")


class OntologyQueryParams(BaseModel):
    """
    本体查询参数

    用于 ontology_query 动作，执行动态字段级查询。
    """
    entity: str = Field(..., description="查询实体名称")
    fields: List[str] = Field(default_factory=list, description="返回字段列表")
    filters: Optional[List[FilterClauseParams]] = Field(default=None, description="过滤条件列表")
    joins: Optional[List[JoinClauseParams]] = Field(default=None, description="连接条件列表")
    order_by: Optional[List[str]] = Field(default=None, description="排序字段列表")
    limit: int = Field(default=100, ge=1, le=1000, description="结果数量限制")
    aggregates: Optional[List[dict]] = Field(default=None, description="聚合操作列表")


# ============== Semantic Query Action Parameters (SPEC-15) ==============

class SemanticFilterParams(BaseModel):
    """
    语义过滤器参数

    用于 semantic_query 动作，使用点分路径表达过滤条件。

    SPEC-15: 语义查询编译器集成
    """
    path: str = Field(..., description="点分路径，如 stays.status 或 stays.room.room_number")
    operator: str = Field(default="eq", description="操作符: eq, ne, gt, gte, lt, lte, in, not_in, like, between")
    value: Any = Field(default=None, description="过滤值")

    @field_validator('operator')
    @classmethod
    def validate_operator(cls, v: str) -> str:
        """验证操作符有效"""
        valid_operators = {
            'eq', 'ne', 'gt', 'gte', 'lt', 'lte',
            'in', 'not_in', 'like', 'not_like',
            'between', 'is_null', 'is_not_null'
        }
        if v.lower() not in valid_operators:
            raise ValueError(
                f"无效的操作符: {v}. 支持: {', '.join(sorted(valid_operators))}"
            )
        return v.lower()


class SemanticQueryParams(BaseModel):
    """
    语义查询参数

    用于 semantic_query 动作，使用点分路径查询关联数据。

    LLM 无需理解 JOIN 语法，只需使用点分路径如：
    - Guest.name
    - Guest.stays.room_number
    - Guest.stays.room.room_type.name

    SPEC-15: 语义查询编译器集成
    """
    root_object: str = Field(..., description="根实体名，如 Guest, Room, StayRecord")
    fields: List[str] = Field(
        default_factory=list,
        description="字段列表，支持点分路径，如 ['name', 'stays.room_number']"
    )
    filters: List[SemanticFilterParams] = Field(
        default_factory=list,
        description="过滤条件列表，使用点分路径"
    )
    order_by: List[str] = Field(
        default_factory=list,
        description="排序字段列表，支持点分路径"
    )
    limit: int = Field(default=100, ge=1, le=1000, description="结果数量限制")
    offset: int = Field(default=0, ge=0, description="偏移量")
    distinct: bool = Field(default=False, description="是否去重")

    @field_validator('root_object')
    @classmethod
    def validate_root_object(cls, v: str) -> str:
        """验证根实体名"""
        # 常见实体别名映射
        entity_aliases = {
            'guest': 'Guest', 'guests': 'Guest',
            'room': 'Room', 'rooms': 'Room',
            'reservation': 'Reservation', 'reservations': 'Reservation',
            'stay': 'StayRecord', 'stayrecord': 'StayRecord',
            'stay_records': 'StayRecord', 'stays': 'StayRecord',
            'task': 'Task', 'tasks': 'Task',
            'bill': 'Bill', 'bills': 'Bill',
            'employee': 'Employee', 'employees': 'Employee',
        }
        v_lower = v.lower()
        if v_lower in entity_aliases:
            return entity_aliases[v_lower]
        return v


# ============== Result Models ==============

class ActionResult(BaseModel):
    """动作执行结果"""
    success: bool
    message: str
    data: Optional[dict] = None
    requires_confirmation: bool = False
    error: Optional[str] = None


# ============== Price Action Parameters ==============

class UpdatePriceParams(BaseModel):
    """
    更新价格参数

    用于 update_price 动作，更新房型基础价格或创建价格策略。
    """
    room_type: Union[int, str] = Field(..., description="房型 ID 或名称")
    price: Decimal = Field(..., description="新价格", ge=0)
    update_type: str = Field(
        default="base_price",
        description="更新类型: base_price(基础价格) 或 rate_plan(价格策略)"
    )
    price_type: str = Field(
        default="standard",
        description="价格类型: standard(标准/平日), weekend(周末)"
    )
    start_date: Optional[date] = Field(default=None, description="策略开始日期")
    end_date: Optional[date] = Field(default=None, description="策略结束日期")

    @field_validator('update_type')
    @classmethod
    def validate_update_type(cls, v: str) -> str:
        """验证更新类型"""
        valid_types = {'base_price', 'rate_plan'}
        v_lower = v.lower().strip()
        if v_lower not in valid_types:
            raise ValueError(f"无效的更新类型: {v}. 支持: base_price, rate_plan")
        return v_lower

    @field_validator('price_type')
    @classmethod
    def validate_price_type(cls, v: str) -> str:
        """验证价格类型"""
        valid_types = {'standard', 'weekend'}
        v_lower = v.lower().strip()

        # 支持中文别名
        price_type_aliases = {
            'weekend': ['周末', '周末价', 'weekend', '周六日', '星期六日'],
            'standard': ['平日', '标准', 'standard', '工作日', '平时']
        }

        for ptype, aliases in price_type_aliases.items():
            if v_lower in [a.lower() for a in aliases]:
                return ptype

        if v_lower not in valid_types:
            raise ValueError(f"无效的价格类型: {v}. 支持: standard, weekend")
        return v_lower


class CreateRatePlanParams(BaseModel):
    """
    创建价格策略参数

    用于 create_rate_plan 动作，创建新的价格策略。
    """
    room_type: Union[int, str] = Field(..., description="房型 ID 或名称")
    name: Optional[str] = Field(default=None, description="策略名称")
    price: Decimal = Field(..., description="策略价格", ge=0)
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")
    priority: int = Field(default=2, description="优先级", ge=1, le=10)
    is_weekend: bool = Field(default=False, description="是否仅周末有效")


__all__ = [
    "WalkInCheckInParams",
    "CheckoutParams",
    "CreateTaskParams",
    "CreateReservationParams",
    "FilterClauseParams",
    "JoinClauseParams",
    "OntologyQueryParams",
    "SemanticFilterParams",
    "SemanticQueryParams",
    "ActionResult",
    "UpdatePriceParams",
    "CreateRatePlanParams",
]
