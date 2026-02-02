"""
Pydantic 模式定义
用于 API 请求/响应验证
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field
from app.models.ontology import (
    RoomStatus, ReservationStatus, StayRecordStatus,
    TaskType, TaskStatus, PaymentMethod, EmployeeRole, GuestTier
)


# ============== 房型 Schemas ==============

class RoomTypeBase(BaseModel):
    name: str = Field(..., max_length=50)
    description: Optional[str] = None
    base_price: Decimal = Field(..., ge=0)
    max_occupancy: int = Field(default=2, ge=1)
    amenities: Optional[str] = None


class RoomTypeCreate(RoomTypeBase):
    pass


class RoomTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    base_price: Optional[Decimal] = Field(None, ge=0)
    max_occupancy: Optional[int] = Field(None, ge=1)
    amenities: Optional[str] = None


class RoomTypeResponse(RoomTypeBase):
    id: int
    created_at: datetime
    room_count: int = 0

    class Config:
        from_attributes = True


# ============== 房间 Schemas ==============

class RoomBase(BaseModel):
    room_number: str = Field(..., max_length=10)
    floor: int
    room_type_id: int
    features: Optional[str] = None


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    room_type_id: Optional[int] = None
    features: Optional[str] = None
    status: Optional[RoomStatus] = None
    is_active: Optional[bool] = None


class RoomResponse(RoomBase):
    id: int
    status: RoomStatus
    is_active: bool
    created_at: datetime
    room_type_name: Optional[str] = None
    current_guest: Optional[str] = None

    class Config:
        from_attributes = True


class RoomStatusUpdate(BaseModel):
    status: RoomStatus


# ============== 客人 Schemas ==============

class GuestBase(BaseModel):
    name: str = Field(..., max_length=100)
    id_type: Optional[str] = Field(None, max_length=20)
    id_number: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)


class GuestCreate(GuestBase):
    pass


class GuestUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    id_type: Optional[str] = Field(None, max_length=20)
    id_number: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    preferences: Optional[str] = None
    tier: Optional[GuestTier] = None
    is_blacklisted: Optional[bool] = None
    blacklist_reason: Optional[str] = None
    notes: Optional[str] = None


class GuestResponse(GuestBase):
    id: int
    preferences: Optional[str] = None
    tier: GuestTier
    total_stays: int
    total_amount: Decimal
    is_blacklisted: bool
    blacklist_reason: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GuestDetailResponse(GuestResponse):
    """客人详情，包含历史记录"""
    reservation_count: int = 0
    last_stay_date: Optional[date] = None
    last_room_type: Optional[str] = None


# ============== 预订 Schemas ==============

class ReservationBase(BaseModel):
    guest_name: str
    guest_phone: str
    guest_id_number: Optional[str] = None
    room_type_id: int
    check_in_date: date
    check_out_date: date
    room_count: int = Field(default=1, ge=1)
    adult_count: int = Field(default=1, ge=1)
    child_count: int = Field(default=0, ge=0)
    special_requests: Optional[str] = None
    estimated_arrival: Optional[str] = None
    prepaid_amount: Decimal = Field(default=0, ge=0)


class ReservationCreate(ReservationBase):
    pass


class ReservationUpdate(BaseModel):
    room_type_id: Optional[int] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    room_count: Optional[int] = Field(None, ge=1)
    adult_count: Optional[int] = Field(None, ge=1)
    child_count: Optional[int] = Field(None, ge=0)
    special_requests: Optional[str] = None
    estimated_arrival: Optional[str] = None


class ReservationCancel(BaseModel):
    cancel_reason: str


class ReservationResponse(BaseModel):
    id: int
    reservation_no: str
    guest_id: int
    guest_name: str
    guest_phone: str
    room_type_id: int
    room_type_name: str
    check_in_date: date
    check_out_date: date
    room_count: int
    adult_count: int
    child_count: int
    status: ReservationStatus
    total_amount: Optional[Decimal]
    prepaid_amount: Decimal
    special_requests: Optional[str]
    estimated_arrival: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============== 入住 Schemas ==============

class CheckInFromReservation(BaseModel):
    reservation_id: int
    room_id: int
    deposit_amount: Decimal = Field(default=0, ge=0)
    guest_id_number: Optional[str] = None


class WalkInCheckIn(BaseModel):
    guest_name: str
    guest_phone: str
    guest_id_type: str
    guest_id_number: str
    room_id: int
    expected_check_out: date
    deposit_amount: Decimal = Field(default=0, ge=0)


class ExtendStay(BaseModel):
    new_check_out_date: date


class ChangeRoom(BaseModel):
    new_room_id: int


class StayRecordResponse(BaseModel):
    id: int
    reservation_id: Optional[int]
    guest_id: int
    guest_name: str
    guest_phone: Optional[str]
    room_id: int
    room_number: str
    room_type_name: str
    check_in_time: datetime
    check_out_time: Optional[datetime]
    expected_check_out: date
    deposit_amount: Decimal
    status: StayRecordStatus
    bill_total: Decimal = 0
    bill_paid: Decimal = 0
    bill_balance: Decimal = 0

    class Config:
        from_attributes = True


# ============== 退房 Schemas ==============

class CheckOutRequest(BaseModel):
    stay_record_id: int
    refund_deposit: Decimal = Field(default=0, ge=0)
    allow_unsettled: bool = False
    unsettled_reason: Optional[str] = None


# ============== 账单 Schemas ==============

class PaymentCreate(BaseModel):
    bill_id: int
    amount: Decimal = Field(..., gt=0)
    method: PaymentMethod
    remark: Optional[str] = None


class BillAdjustment(BaseModel):
    bill_id: int
    adjustment_amount: Decimal
    reason: str


class BillResponse(BaseModel):
    id: int
    stay_record_id: int
    total_amount: Decimal
    paid_amount: Decimal
    adjustment_amount: Decimal
    adjustment_reason: Optional[str]
    balance: Decimal
    is_settled: bool
    payments: List["PaymentResponse"] = []

    class Config:
        from_attributes = True


class PaymentResponse(BaseModel):
    id: int
    amount: Decimal
    method: PaymentMethod
    payment_time: datetime
    remark: Optional[str]
    operator_name: Optional[str]

    class Config:
        from_attributes = True


# ============== 任务 Schemas ==============

class TaskCreate(BaseModel):
    room_id: int
    task_type: TaskType
    priority: int = Field(default=1, ge=1, le=5)
    notes: Optional[str] = None
    assignee_id: Optional[int] = None


class TaskAssign(BaseModel):
    assignee_id: int


class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    notes: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=5)


class TaskResponse(BaseModel):
    id: int
    room_id: int
    room_number: str
    task_type: TaskType
    status: TaskStatus
    assignee_id: Optional[int]
    assignee_name: Optional[str]
    priority: int
    notes: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ============== 员工 Schemas ==============

class EmployeeCreate(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., min_length=6)
    name: str = Field(..., max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    role: EmployeeRole


class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    role: Optional[EmployeeRole] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6)


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


class EmployeeResponse(BaseModel):
    id: int
    username: str
    name: str
    phone: Optional[str]
    role: EmployeeRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============== 价格策略 Schemas ==============

class RatePlanCreate(BaseModel):
    name: str = Field(..., max_length=100)
    room_type_id: int
    start_date: date
    end_date: date
    price: Decimal = Field(..., ge=0)
    priority: int = Field(default=1, ge=1)
    is_weekend: bool = False


class RatePlanUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    price: Optional[Decimal] = Field(None, ge=0)
    priority: Optional[int] = Field(None, ge=1)
    is_weekend: Optional[bool] = None
    is_active: Optional[bool] = None


class RatePlanResponse(BaseModel):
    id: int
    name: str
    room_type_id: int
    room_type_name: str
    start_date: date
    end_date: date
    price: Decimal
    priority: int
    is_weekend: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============== 登录 Schemas ==============

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    employee: EmployeeResponse


class TokenPayload(BaseModel):
    sub: int
    role: EmployeeRole
    exp: datetime


# ============== 统计报表 Schemas ==============

class DashboardStats(BaseModel):
    total_rooms: int
    vacant_clean: int
    occupied: int
    vacant_dirty: int
    out_of_order: int
    today_checkins: int
    today_checkouts: int
    occupancy_rate: float
    today_revenue: Decimal


class OccupancyReport(BaseModel):
    date: date
    total_rooms: int
    occupied_rooms: int
    occupancy_rate: float


class RevenueReport(BaseModel):
    date: date
    revenue: Decimal
    payment_count: int


# ============== AI 对话 Schemas ==============

class AIMessage(BaseModel):
    content: str


class AIAction(BaseModel):
    action_type: str
    entity_type: str
    entity_id: Optional[int] = None
    params: dict = {}
    description: str
    requires_confirmation: bool = True


class AIResponse(BaseModel):
    message: str
    suggested_actions: List[AIAction] = []
    context: dict = {}


class ActionConfirmation(BaseModel):
    action: AIAction
    confirmed: bool


# ============== 系统设置 Schemas ==============

class LLMSettings(BaseModel):
    """LLM 配置设置"""
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1000
    enable_llm: bool = True
    system_prompt: Optional[str] = None
    has_env_key: bool = False  # 是否配置了环境变量 API Key

    class Config:
        from_attributes = True


class LLMTestRequest(BaseModel):
    """LLM 连接测试请求"""
    api_key: Optional[str] = None  # 可选，为空时使用环境变量
    base_url: str
    model: str
