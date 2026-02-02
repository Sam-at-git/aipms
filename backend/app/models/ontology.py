"""
本体对象定义 (Ontology Objects)
遵循 Palantir 架构：所有业务实体通过对象、属性、链接进行建模
每个属性带有安全等级标记，支持属性级访问控制
"""
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date,
    ForeignKey, Text, Enum as SQLEnum, Boolean, Numeric
)
from sqlalchemy.orm import relationship
from app.database import Base


# ============== 枚举定义 ==============

class RoomStatus(str, Enum):
    """房间状态枚举"""
    VACANT_CLEAN = "vacant_clean"      # 空闲-已清洁
    OCCUPIED = "occupied"              # 入住中
    VACANT_DIRTY = "vacant_dirty"      # 空闲-待清洁
    OUT_OF_ORDER = "out_of_order"      # 维修中


class ReservationStatus(str, Enum):
    """预订状态枚举"""
    CONFIRMED = "confirmed"    # 已确认
    CHECKED_IN = "checked_in"  # 已入住
    COMPLETED = "completed"    # 已完成
    CANCELLED = "cancelled"    # 已取消
    NO_SHOW = "no_show"        # 未到店


class StayRecordStatus(str, Enum):
    """住宿记录状态"""
    ACTIVE = "active"          # 在住
    CHECKED_OUT = "checked_out"  # 已退房


class TaskType(str, Enum):
    """任务类型"""
    CLEANING = "cleaning"      # 清洁
    MAINTENANCE = "maintenance"  # 维修


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"        # 待分配
    ASSIGNED = "assigned"      # 已分配
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"    # 已完成


class PaymentMethod(str, Enum):
    """支付方式"""
    CASH = "cash"              # 现金
    CARD = "card"              # 刷卡


class EmployeeRole(str, Enum):
    """员工角色"""
    MANAGER = "manager"        # 经理
    RECEPTIONIST = "receptionist"  # 前台
    CLEANER = "cleaner"        # 清洁员


class SecurityLevel(int, Enum):
    """安全等级 - 用于属性级访问控制"""
    PUBLIC = 1         # 公开
    INTERNAL = 2       # 内部
    CONFIDENTIAL = 3   # 机密
    RESTRICTED = 4     # 受限


class GuestTier(str, Enum):
    """客户等级"""
    NORMAL = "normal"       # 普通
    SILVER = "silver"       # 银卡
    GOLD = "gold"           # 金卡
    PLATINUM = "platinum"   # 白金


# ============== 本体对象定义 ==============

class RoomType(Base):
    """
    房型对象
    属性安全等级：name(PUBLIC), base_price(INTERNAL)
    """
    __tablename__ = "room_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)  # 房型名称
    description = Column(Text)                               # 描述
    base_price = Column(Numeric(10, 2), nullable=False)     # 基础价格
    max_occupancy = Column(Integer, default=2)              # 最大入住人数
    amenities = Column(Text)                                # 设施列表(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 链接：一个房型对应多个房间
    rooms = relationship("Room", back_populates="room_type")
    # 链接：一个房型对应多个价格策略
    rate_plans = relationship("RatePlan", back_populates="room_type")


class Room(Base):
    """
    房间对象 - 数字孪生的核心实体
    属性安全等级：room_number(PUBLIC), status(INTERNAL), current_price(CONFIDENTIAL)
    """
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String(10), unique=True, nullable=False)  # 房间号
    floor = Column(Integer, nullable=False)                        # 楼层
    room_type_id = Column(Integer, ForeignKey("room_types.id"), nullable=False)
    status = Column(SQLEnum(RoomStatus), default=RoomStatus.VACANT_CLEAN)
    features = Column(Text)                                        # 特征(如海景)
    is_active = Column(Boolean, default=True)                      # 是否启用
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 链接
    room_type = relationship("RoomType", back_populates="rooms")
    stay_records = relationship("StayRecord", back_populates="room")
    tasks = relationship("Task", back_populates="room")


class Guest(Base):
    """
    客人对象
    属性安全等级：name(INTERNAL), id_number(RESTRICTED), phone(CONFIDENTIAL)
    """
    __tablename__ = "guests"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)           # 姓名
    id_type = Column(String(20))                         # 证件类型
    id_number = Column(String(50))                       # 证件号码
    phone = Column(String(20))                           # 手机号
    email = Column(String(100))                          # 邮箱
    preferences = Column(Text)                           # 客户偏好 (JSON)
    tier = Column(String(20), default="normal")           # 客户等级: normal, silver, gold, platinum
    total_stays = Column(Integer, default=0)             # 累计入住次数
    total_amount = Column(Numeric(10, 2), default=0)      # 累计消费金额
    is_blacklisted = Column(Boolean, default=False)      # 是否黑名单
    blacklist_reason = Column(Text)                      # 黑名单原因
    notes = Column(Text)                                 # 备注信息
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 链接
    reservations = relationship("Reservation", back_populates="guest")
    stay_records = relationship("StayRecord", back_populates="guest")


class Reservation(Base):
    """
    预订对象 - 预订阶段的聚合根
    属性安全等级：reservation_no(PUBLIC), total_amount(CONFIDENTIAL)
    """
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    reservation_no = Column(String(20), unique=True, nullable=False)  # 预订号
    guest_id = Column(Integer, ForeignKey("guests.id"), nullable=False)
    room_type_id = Column(Integer, ForeignKey("room_types.id"), nullable=False)
    check_in_date = Column(Date, nullable=False)         # 入住日期
    check_out_date = Column(Date, nullable=False)        # 离店日期
    room_count = Column(Integer, default=1)              # 房间数
    adult_count = Column(Integer, default=1)             # 成人数
    child_count = Column(Integer, default=0)             # 儿童数
    status = Column(SQLEnum(ReservationStatus), default=ReservationStatus.CONFIRMED)
    total_amount = Column(Numeric(10, 2))                # 预估总价
    prepaid_amount = Column(Numeric(10, 2), default=0)   # 预付金额
    special_requests = Column(Text)                      # 特殊要求
    estimated_arrival = Column(String(10))               # 预计到店时间
    cancel_reason = Column(Text)                         # 取消原因
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("employees.id"))  # 创建人

    # 链接
    guest = relationship("Guest", back_populates="reservations")
    room_type = relationship("RoomType")
    stay_records = relationship("StayRecord", back_populates="reservation")
    creator = relationship("Employee", foreign_keys=[created_by])


class StayRecord(Base):
    """
    住宿记录对象 - 住宿期间的聚合根
    管理 Bill 和入住周期
    属性安全等级：全部 INTERNAL 或 CONFIDENTIAL
    """
    __tablename__ = "stay_records"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=True)  # 可能是 walk-in
    guest_id = Column(Integer, ForeignKey("guests.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    check_in_time = Column(DateTime, nullable=False)     # 实际入住时间
    check_out_time = Column(DateTime)                    # 实际退房时间
    expected_check_out = Column(Date, nullable=False)    # 预计离店日期
    deposit_amount = Column(Numeric(10, 2), default=0)   # 押金
    status = Column(SQLEnum(StayRecordStatus), default=StayRecordStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("employees.id"))

    # 链接
    reservation = relationship("Reservation", back_populates="stay_records")
    guest = relationship("Guest", back_populates="stay_records")
    room = relationship("Room", back_populates="stay_records")
    bill = relationship("Bill", back_populates="stay_record", uselist=False)
    creator = relationship("Employee", foreign_keys=[created_by])


class Bill(Base):
    """
    账单对象
    属于 StayRecord 聚合根
    属性安全等级：total_amount(CONFIDENTIAL)
    """
    __tablename__ = "bills"

    id = Column(Integer, primary_key=True, index=True)
    stay_record_id = Column(Integer, ForeignKey("stay_records.id"), nullable=False)
    total_amount = Column(Numeric(10, 2), default=0)     # 总金额
    paid_amount = Column(Numeric(10, 2), default=0)      # 已付金额
    adjustment_amount = Column(Numeric(10, 2), default=0)  # 调整金额
    adjustment_reason = Column(Text)                     # 调整原因
    is_settled = Column(Boolean, default=False)          # 是否结清
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 链接
    stay_record = relationship("StayRecord", back_populates="bill")
    payments = relationship("Payment", back_populates="bill")

    @property
    def balance(self) -> Decimal:
        """计算余额"""
        return self.total_amount + self.adjustment_amount - self.paid_amount


class Payment(Base):
    """
    支付记录对象
    属于 Bill
    """
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    bill_id = Column(Integer, ForeignKey("bills.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)      # 支付金额
    method = Column(SQLEnum(PaymentMethod), nullable=False)  # 支付方式
    payment_time = Column(DateTime, default=datetime.utcnow)
    remark = Column(Text)                                # 备注
    created_by = Column(Integer, ForeignKey("employees.id"))

    # 链接
    bill = relationship("Bill", back_populates="payments")
    operator = relationship("Employee")


class Task(Base):
    """
    任务对象
    用于清洁和维修任务管理
    """
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    task_type = Column(SQLEnum(TaskType), nullable=False)
    status = Column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    assignee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    priority = Column(Integer, default=1)                # 优先级 1-5
    notes = Column(Text)                                 # 备注
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)                        # 开始时间
    completed_at = Column(DateTime)                      # 完成时间
    created_by = Column(Integer, ForeignKey("employees.id"))

    # 链接
    room = relationship("Room", back_populates="tasks")
    assignee = relationship("Employee", foreign_keys=[assignee_id], back_populates="assigned_tasks")
    creator = relationship("Employee", foreign_keys=[created_by])


class Employee(Base):
    """
    员工对象
    属性安全等级：name(PUBLIC), password_hash(RESTRICTED), role(INTERNAL)
    """
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)  # 登录账号
    password_hash = Column(String(255), nullable=False)  # 密码哈希
    name = Column(String(100), nullable=False)           # 姓名
    phone = Column(String(20))                           # 手机号
    role = Column(SQLEnum(EmployeeRole), nullable=False)
    is_active = Column(Boolean, default=True)            # 是否启用
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 链接
    assigned_tasks = relationship("Task", foreign_keys="Task.assignee_id", back_populates="assignee")

    @property
    def clearance(self) -> SecurityLevel:
        """根据角色返回安全等级"""
        if self.role == EmployeeRole.MANAGER:
            return SecurityLevel.RESTRICTED
        elif self.role == EmployeeRole.RECEPTIONIST:
            return SecurityLevel.CONFIDENTIAL
        else:
            return SecurityLevel.INTERNAL


class RatePlan(Base):
    """
    价格策略对象
    用于动态定价管理
    """
    __tablename__ = "rate_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)           # 策略名称
    room_type_id = Column(Integer, ForeignKey("room_types.id"), nullable=False)
    start_date = Column(Date, nullable=False)            # 开始日期
    end_date = Column(Date, nullable=False)              # 结束日期
    price = Column(Numeric(10, 2), nullable=False)       # 策略价格
    priority = Column(Integer, default=1)                # 优先级(数字越大优先级越高)
    is_weekend = Column(Boolean, default=False)          # 是否仅周末有效
    is_active = Column(Boolean, default=True)            # 是否启用
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("employees.id"))

    # 链接
    room_type = relationship("RoomType", back_populates="rate_plans")


class SystemLog(Base):
    """
    系统日志对象
    记录关键操作用于审计
    """
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, index=True)
    operator_id = Column(Integer, ForeignKey("employees.id"))
    action = Column(String(100), nullable=False)         # 操作类型
    entity_type = Column(String(50))                     # 实体类型
    entity_id = Column(Integer)                          # 实体ID
    old_value = Column(Text)                             # 旧值(JSON)
    new_value = Column(Text)                             # 新值(JSON)
    ip_address = Column(String(50))                      # IP地址
    created_at = Column(DateTime, default=datetime.utcnow)

    # 链接
    operator = relationship("Employee")
