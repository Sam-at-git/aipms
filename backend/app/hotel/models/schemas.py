"""
Hotel domain Pydantic schemas for API request/response validation.
"""
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Union, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.hotel.models.ontology import (
    RoomStatus, ReservationStatus, StayRecordStatus,
    TaskType, TaskStatus, PaymentMethod, EmployeeRole, GuestTier
)

# 手机号格式验证正则
PHONE_REGEX = r'^1[3-9]\d{9}$'


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
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


class RoomStatusUpdate(BaseModel):
    status: RoomStatus


# ============== 客人 Schemas ==============

class GuestBase(BaseModel):
    name: str = Field(..., max_length=100)
    id_type: Optional[str] = Field(None, max_length=20)
    id_number: Optional[str] = Field(None, max_length=50)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """验证手机号格式（中国手机号：11位，1开头，第二位3-9）"""
        if v is None or v == "":
            return v
        import re
        if not re.match(PHONE_REGEX, v):
            raise ValueError(f"手机号格式无效：{v}。应为11位数字，以1开头，第二位为3-9")
        return v


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

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """验证手机号格式（中国手机号：11位，1开头，第二位3-9）"""
        if v is None or v == "":
            return v
        import re
        if not re.match(PHONE_REGEX, v):
            raise ValueError(f"手机号格式无效：{v}。应为11位数字，以1开头，第二位为3-9")
        return v


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
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


# ============== 入住 Schemas ==============

class CheckInFromReservation(BaseModel):
    reservation_id: int
    room_id: int
    deposit_amount: Decimal = Field(default=0, ge=0)
    guest_id_number: Optional[str] = None


class WalkInCheckIn(BaseModel):
    guest_name: str
    guest_phone: str
    guest_id_type: str = '身份证'
    guest_id_number: str = ''
    room_id: int
    expected_check_out: Union[date, str]  # 支持日期对象或字符串
    deposit_amount: Decimal = Field(default=0, ge=0)

    @field_validator('expected_check_out')
    @classmethod
    def parse_expected_check_out(cls, v: Any) -> date:
        """解析离店日期，支持相对日期字符串"""
        if isinstance(v, date):
            # 已经是 date 对象，直接返回
            return v

        if isinstance(v, str):
            v = v.strip()
            today = date.today()

            # 解析 ISO 格式
            try:
                return date.fromisoformat(v)
            except ValueError:
                pass

            # 解析相对日期
            relative_dates = {
                '今天': 0,
                '明日': 0, '明天': 0, '明': 0,
                '后天': 1, '后日': 1,
                '大后天': 2,
                '昨': -1, '昨日': -1,
            }
            for keyword, offset in relative_dates.items():
                if keyword in v:
                    result_date = today + timedelta(days=offset)
                    # 验证日期必须晚于今天
                    if result_date <= today:
                        raise ValueError(f"离店日期必须晚于今天（解析为：{result_date.isoformat()}）")
                    return result_date

            # 解析偏移量 (+3天)
            import re
            offset_match = re.search(r'([+-]?\d+)\s*(天|日)', v)
            if offset_match:
                offset = int(offset_match.group(1))
                result_date = today + timedelta(days=offset)
                if result_date <= today:
                    raise ValueError(f"离店日期必须晚于今天（解析为：{result_date.isoformat()}）")
                return result_date

        # 如果是其他类型，尝试转换
        return date(v)


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
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    id: int
    amount: Decimal
    method: PaymentMethod
    payment_time: datetime
    remark: Optional[str]
    operator_name: Optional[str]
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


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
