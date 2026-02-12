"""
app/services/actions/base.py

Base module for action parameter models.

Provides Pydantic models for action parameter validation.
These models define the expected parameters for each AI-executable action.
"""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
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
        except (ValueError, TypeError, InvalidOperation) as e:
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


class UpdateGuestParams(BaseModel):
    """
    更新客人信息参数

    用于 update_guest 动作，更新客人的联系方式、等级等信息。
    支持通过 guest_id 或 guest_name 定位客人。
    """
    guest_id: Optional[int] = Field(default=None, description="客人ID", gt=0)
    guest_name: Optional[str] = Field(default=None, description="客人姓名（用于查找客人）")
    name: Optional[str] = Field(default=None, description="新姓名", max_length=100)
    phone: Optional[str] = Field(default=None, description="新手机号", max_length=20)
    email: Optional[str] = Field(default=None, description="新邮箱", max_length=100)
    id_type: Optional[str] = Field(default=None, description="证件类型", max_length=20)
    id_number: Optional[str] = Field(default=None, description="证件号码", max_length=50)
    tier: Optional[str] = Field(default=None, description="客户等级: normal, silver, gold, platinum")
    is_blacklisted: Optional[bool] = Field(default=None, description="是否黑名单")
    blacklist_reason: Optional[str] = Field(default=None, description="黑名单原因")
    notes: Optional[str] = Field(default=None, description="备注信息")


class SmartUpdateParams(BaseModel):
    """
    通用智能更新参数

    用于 update_{entity}_smart 动作，支持自然语言式的部分修改指令。
    例如：'把电话号码后两位改为77'、'将邮箱改为新邮箱@qq.com'

    通过 entity_id/entity_name 通用字段定位实体，
    同时支持 guest_id/guest_name/employee_id/employee_name 等别名字段以兼容 LLM 输出。
    """
    entity_id: Optional[int] = Field(default=None, description="实体ID", gt=0)
    entity_name: Optional[str] = Field(default=None, description="实体名称（用于查找）")
    instructions: str = Field(..., description="自然语言修改指令，如: '电话号码后两位改为77'")

    # Alias fields for backward LLM compatibility
    guest_id: Optional[int] = Field(default=None, description="客人ID（别名→entity_id）", gt=0, exclude=True)
    guest_name: Optional[str] = Field(default=None, description="客人姓名（别名→entity_name）", exclude=True)
    employee_id: Optional[int] = Field(default=None, description="员工ID（别名→entity_id）", gt=0, exclude=True)
    employee_name: Optional[str] = Field(default=None, description="员工姓名（别名→entity_name）", exclude=True)
    room_type_id: Optional[int] = Field(default=None, description="房型ID（别名→entity_id）", gt=0, exclude=True)
    room_type_name: Optional[str] = Field(default=None, description="房型名称（别名→entity_name）", exclude=True)

    @field_validator('instructions')
    @classmethod
    def validate_instructions(cls, v: str) -> str:
        """验证修改指令不为空"""
        if not v or not v.strip():
            raise ValueError("修改指令不能为空")
        return v.strip()

    def model_post_init(self, __context: Any) -> None:
        """Resolve alias fields to generic entity_id/entity_name."""
        if self.entity_id is None:
            for alias in ('guest_id', 'employee_id', 'room_type_id'):
                val = getattr(self, alias, None)
                if val is not None:
                    self.entity_id = val
                    break
        if self.entity_name is None:
            for alias in ('guest_name', 'employee_name', 'room_type_name'):
                val = getattr(self, alias, None)
                if val is not None:
                    self.entity_name = val
                    break


# Backward compatibility alias
UpdateGuestSmartParams = SmartUpdateParams


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


class DeleteTaskParams(BaseModel):
    """
    删除单个任务参数

    用于 delete_task 动作，删除指定任务（仅 pending/assigned 状态可删除）。
    """
    task_id: int = Field(..., description="任务 ID", gt=0)


class BatchDeleteTasksParams(BaseModel):
    """
    批量删除任务参数

    用于 batch_delete_tasks 动作，按条件批量删除任务。
    仅删除 pending/assigned 状态的任务。
    """
    status: Optional[str] = Field(default=None, description="按状态过滤: pending, assigned")
    task_type: Optional[str] = Field(default=None, description="按类型过滤: cleaning, maintenance")
    room_id: Optional[Union[int, str]] = Field(default=None, description="按房间过滤（房间 ID 或房间号）")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """验证状态值"""
        if v is None:
            return v
        valid = {'pending', 'assigned'}
        v_lower = v.lower().strip()
        if v_lower not in valid:
            raise ValueError(f"无效的状态: {v}. 仅支持: pending, assigned")
        return v_lower

    @field_validator('task_type')
    @classmethod
    def validate_task_type(cls, v: Optional[str]) -> Optional[str]:
        """验证任务类型"""
        if v is None:
            return v
        aliases = {
            'cleaning': ['cleaning', '清洁', '打扫', 'clean'],
            'maintenance': ['maintenance', '维修', '修理', 'fix']
        }
        v_lower = v.lower().strip()
        for task_type, alias_list in aliases.items():
            if v_lower in alias_list:
                return task_type
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


# ============== Webhook Action Parameters ==============

class SyncOTAParams(BaseModel):
    """同步OTA房态参数"""
    channel: str = Field(default="all", description="OTA渠道: ctrip, meituan, all")
    room_type: Optional[str] = Field(default=None, description="房型名称（空则同步所有）")


class FetchChannelReservationsParams(BaseModel):
    """拉取渠道预订参数"""
    channel: str = Field(..., description="渠道名称: ctrip, meituan, booking")
    date_from: Optional[date] = Field(default=None, description="起始日期")
    date_to: Optional[date] = Field(default=None, description="截止日期")


# ============== Notification Action Parameters ==============

class NotificationParams(BaseModel):
    """通知参数"""
    target: Optional[str] = Field(default=None, description="通知目标（房间号或员工名）")
    message: Optional[str] = Field(default=None, description="自定义消息")
    channel: str = Field(default="system", description="通知渠道: system, sms, wechat")


# ============== Interface Action Parameters ==============

class BookResourceParams(BaseModel):
    """预订资源参数（通用接口动作）"""
    resource_type: str = Field(default="Room", description="资源类型")
    resource_id: Optional[Union[int, str]] = Field(default=None, description="资源ID或编号")
    guest_name: Optional[str] = Field(default=None, description="客人姓名")
    start_date: Optional[date] = Field(default=None, description="开始日期")
    end_date: Optional[date] = Field(default=None, description="结束日期")


# ============== Task Workflow Parameters ==============

class AssignTaskParams(BaseModel):
    """分配任务参数"""
    task_id: int = Field(..., description="任务ID", gt=0)
    assignee_id: Optional[int] = Field(default=None, description="清洁员ID", gt=0)
    assignee_name: Optional[str] = Field(default=None, description="清洁员姓名")


class StartTaskParams(BaseModel):
    """开始任务参数"""
    task_id: int = Field(..., description="任务ID", gt=0)


class CompleteTaskParams(BaseModel):
    """完成任务参数"""
    task_id: int = Field(..., description="任务ID", gt=0)
    notes: Optional[str] = Field(default=None, description="完成备注")


# ============== Checkin / Stay Workflow Parameters ==============

class CheckinParams(BaseModel):
    """预订入住参数"""
    reservation_id: Optional[int] = Field(default=None, description="预订ID", gt=0)
    reservation_no: Optional[str] = Field(default=None, description="预订号")
    room_number: Optional[str] = Field(default=None, description="入住房间号（覆盖预订房型）")


class ExtendStayParams(BaseModel):
    """续住参数"""
    stay_record_id: int = Field(..., description="住宿记录ID", gt=0)
    new_check_out_date: Union[date, str] = Field(..., description="新退房日期")

    @field_validator('new_check_out_date')
    @classmethod
    def parse_new_check_out(cls, v: Union[date, str]) -> date:
        if isinstance(v, date):
            return v
        try:
            return date.fromisoformat(v)
        except ValueError as e:
            raise ValueError(f"无效的日期格式: {v}. 请使用 YYYY-MM-DD 格式") from e


class ChangeRoomParams(BaseModel):
    """换房参数"""
    stay_record_id: int = Field(..., description="住宿记录ID", gt=0)
    new_room_number: str = Field(..., description="新房间号")


# ============== Reservation Workflow Parameters ==============

class CancelReservationParams(BaseModel):
    """取消预订参数"""
    reservation_id: Optional[int] = Field(default=None, description="预订ID", gt=0)
    reservation_no: Optional[str] = Field(default=None, description="预订号")
    reason: Optional[str] = Field(default="客人要求取消", description="取消原因")


class ModifyReservationParams(BaseModel):
    """修改预订参数"""
    reservation_id: Optional[int] = Field(default=None, description="预订ID", gt=0)
    reservation_no: Optional[str] = Field(default=None, description="预订号")
    check_in_date: Optional[Union[date, str]] = Field(default=None, description="新入住日期")
    check_out_date: Optional[Union[date, str]] = Field(default=None, description="新退房日期")
    room_type_id: Optional[int] = Field(default=None, description="新房型ID")
    adult_count: Optional[int] = Field(default=None, description="成人数", ge=1)
    special_requests: Optional[str] = Field(default=None, description="特殊要求")

    @field_validator('check_in_date', 'check_out_date')
    @classmethod
    def parse_dates(cls, v):
        if v is None:
            return v
        if isinstance(v, date):
            return v
        try:
            return date.fromisoformat(v)
        except ValueError as e:
            raise ValueError(f"无效的日期格式: {v}") from e


# ============== Billing Parameters ==============

class AddPaymentParams(BaseModel):
    """添加支付参数"""
    bill_id: Optional[int] = Field(default=None, description="账单ID", gt=0)
    stay_record_id: Optional[int] = Field(default=None, description="住宿记录ID", gt=0)
    amount: Union[str, int, float, Decimal] = Field(..., description="支付金额")
    payment_method: str = Field(..., description="支付方式: cash/card")

    @field_validator('amount')
    @classmethod
    def parse_amount(cls, v) -> Decimal:
        try:
            amount = Decimal(str(v))
            if amount <= 0:
                raise ValueError("金额必须大于0")
            return amount
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的金额: {v}") from e


class AdjustBillParams(BaseModel):
    """调整账单参数"""
    bill_id: Optional[int] = Field(default=None, description="账单ID", gt=0)
    stay_record_id: Optional[int] = Field(default=None, description="住宿记录ID", gt=0)
    amount: Union[str, int, float, Decimal] = Field(..., description="调整金额（正数加价，负数减价）")
    reason: str = Field(..., description="调整原因")

    @field_validator('amount')
    @classmethod
    def parse_amount(cls, v) -> Decimal:
        try:
            return Decimal(str(v))
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的金额: {v}") from e


class RefundPaymentParams(BaseModel):
    """退款参数"""
    payment_id: int = Field(..., description="支付记录ID", gt=0)
    amount: Optional[Union[str, int, float, Decimal]] = Field(default=None, description="退款金额（空则全额退款）")
    reason: str = Field(..., description="退款原因")

    @field_validator('amount')
    @classmethod
    def parse_amount(cls, v):
        if v is None:
            return v
        try:
            amount = Decimal(str(v))
            if amount <= 0:
                raise ValueError("退款金额必须大于0")
            return amount
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的金额: {v}") from e


# ============== Room & RoomType Parameters ==============

class UpdateRoomStatusParams(BaseModel):
    """更新房间状态参数"""
    room_number: str = Field(..., description="房间号")
    status: str = Field(..., description="目标状态: vacant_clean, vacant_dirty, out_of_order")


class CreateRoomTypeParams(BaseModel):
    """创建房型参数"""
    name: str = Field(..., description="房型名称", max_length=50)
    base_price: Union[str, int, float, Decimal] = Field(..., description="基础价格")
    description: Optional[str] = Field(default=None, description="房型描述")
    max_occupancy: int = Field(default=2, description="最大入住人数", ge=1)

    @field_validator('base_price')
    @classmethod
    def parse_price(cls, v) -> Decimal:
        try:
            price = Decimal(str(v))
            if price < 0:
                raise ValueError("价格不能为负数")
            return price
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的价格: {v}") from e


class UpdateRoomTypeParams(BaseModel):
    """更新房型参数"""
    room_type_id: Optional[int] = Field(default=None, description="房型ID", gt=0)
    room_type_name: Optional[str] = Field(default=None, description="房型名称（用于查找）")
    name: Optional[str] = Field(default=None, description="新名称", max_length=50)
    base_price: Optional[Union[str, int, float, Decimal]] = Field(default=None, description="新基础价格")
    description: Optional[str] = Field(default=None, description="新描述")

    @field_validator('base_price')
    @classmethod
    def parse_price(cls, v):
        if v is None:
            return v
        try:
            price = Decimal(str(v))
            if price < 0:
                raise ValueError("价格不能为负数")
            return price
        except (ValueError, TypeError) as e:
            raise ValueError(f"无效的价格: {v}") from e


# ============== Guest Parameters ==============

class CreateGuestParams(BaseModel):
    """创建客人参数"""
    name: str = Field(..., description="客人姓名", min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, description="手机号", max_length=20)
    id_type: Optional[str] = Field(default=None, description="证件类型")
    id_number: Optional[str] = Field(default=None, description="证件号码")
    email: Optional[str] = Field(default=None, description="邮箱")


# ============== Employee Parameters ==============

class CreateEmployeeParams(BaseModel):
    """创建员工参数"""
    username: str = Field(..., description="登录账号", min_length=1, max_length=50)
    name: str = Field(..., description="姓名", min_length=1, max_length=100)
    role: str = Field(..., description="角色: receptionist, cleaner, manager, sysadmin")
    phone: Optional[str] = Field(default=None, description="手机号", max_length=20)
    password: Optional[str] = Field(default=None, description="密码（默认123456）")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid = {'receptionist', 'cleaner', 'manager', 'sysadmin'}
        v_lower = v.lower().strip()
        if v_lower not in valid:
            raise ValueError(f"无效的角色: {v}. 支持: {', '.join(valid)}")
        return v_lower


class UpdateEmployeeParams(BaseModel):
    """更新员工参数"""
    employee_id: int = Field(..., description="员工ID", gt=0)
    name: Optional[str] = Field(default=None, description="新姓名", max_length=100)
    phone: Optional[str] = Field(default=None, description="新手机号", max_length=20)
    role: Optional[str] = Field(default=None, description="新角色")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        if v is None:
            return v
        valid = {'receptionist', 'cleaner', 'manager', 'sysadmin'}
        v_lower = v.lower().strip()
        if v_lower not in valid:
            raise ValueError(f"无效的角色: {v}. 支持: {', '.join(valid)}")
        return v_lower


class DeactivateEmployeeParams(BaseModel):
    """停用员工参数"""
    employee_id: int = Field(..., description="员工ID", gt=0)


__all__ = [
    "WalkInCheckInParams",
    "UpdateGuestParams",
    "CheckoutParams",
    "CreateTaskParams",
    "DeleteTaskParams",
    "BatchDeleteTasksParams",
    "CreateReservationParams",
    "FilterClauseParams",
    "JoinClauseParams",
    "OntologyQueryParams",
    "SemanticFilterParams",
    "SemanticQueryParams",
    "ActionResult",
    "UpdatePriceParams",
    "CreateRatePlanParams",
    "SyncOTAParams",
    "FetchChannelReservationsParams",
    "NotificationParams",
    "BookResourceParams",
    # Task workflow
    "AssignTaskParams",
    "StartTaskParams",
    "CompleteTaskParams",
    # Stay workflow
    "CheckinParams",
    "ExtendStayParams",
    "ChangeRoomParams",
    # Reservation workflow
    "CancelReservationParams",
    "ModifyReservationParams",
    # Billing
    "AddPaymentParams",
    "AdjustBillParams",
    "RefundPaymentParams",
    # Room & RoomType
    "UpdateRoomStatusParams",
    "CreateRoomTypeParams",
    "UpdateRoomTypeParams",
    # Guest
    "CreateGuestParams",
    # Employee
    "CreateEmployeeParams",
    "UpdateEmployeeParams",
    "DeactivateEmployeeParams",
    # Smart Update (generic)
    "SmartUpdateParams",
    "UpdateGuestSmartParams",
]
