"""
价格服务 - 本体操作层
管理 RatePlan 对象和动态定价逻辑
"""
from typing import List, Optional
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.ontology import RatePlan, RoomType
from app.models.schemas import RatePlanCreate, RatePlanUpdate


class PriceService:
    """价格服务"""

    def __init__(self, db: Session):
        self.db = db

    def get_rate_plans(self, room_type_id: Optional[int] = None,
                       is_active: Optional[bool] = None) -> List[RatePlan]:
        """获取价格策略列表"""
        query = self.db.query(RatePlan)

        if room_type_id:
            query = query.filter(RatePlan.room_type_id == room_type_id)
        if is_active is not None:
            query = query.filter(RatePlan.is_active == is_active)

        return query.order_by(RatePlan.priority.desc()).all()

    def get_rate_plan(self, rate_plan_id: int) -> Optional[RatePlan]:
        """获取单个价格策略"""
        return self.db.query(RatePlan).filter(RatePlan.id == rate_plan_id).first()

    def create_rate_plan(self, data: RatePlanCreate, created_by: int) -> RatePlan:
        """创建价格策略"""
        room_type = self.db.query(RoomType).filter(RoomType.id == data.room_type_id).first()
        if not room_type:
            raise ValueError("房型不存在")

        if data.end_date < data.start_date:
            raise ValueError("结束日期不能早于开始日期")

        rate_plan = RatePlan(**data.model_dump(), created_by=created_by)
        self.db.add(rate_plan)
        self.db.commit()
        self.db.refresh(rate_plan)
        return rate_plan

    def update_rate_plan(self, rate_plan_id: int, data: RatePlanUpdate) -> RatePlan:
        """更新价格策略"""
        rate_plan = self.get_rate_plan(rate_plan_id)
        if not rate_plan:
            raise ValueError("价格策略不存在")

        update_data = data.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(rate_plan, key, value)

        # 验证日期
        if rate_plan.end_date < rate_plan.start_date:
            raise ValueError("结束日期不能早于开始日期")

        self.db.commit()
        self.db.refresh(rate_plan)
        return rate_plan

    def delete_rate_plan(self, rate_plan_id: int) -> bool:
        """删除价格策略"""
        rate_plan = self.get_rate_plan(rate_plan_id)
        if not rate_plan:
            raise ValueError("价格策略不存在")

        self.db.delete(rate_plan)
        self.db.commit()
        return True

    def get_price_for_date(self, room_type_id: int, target_date: date) -> Decimal:
        """获取指定日期的房型价格"""
        room_type = self.db.query(RoomType).filter(RoomType.id == room_type_id).first()
        if not room_type:
            raise ValueError("房型不存在")

        # 检查是否是周末
        is_weekend = target_date.weekday() >= 4  # 周五(4)、周六(5)

        # 查找适用的价格策略（按优先级排序）
        query = self.db.query(RatePlan).filter(
            RatePlan.room_type_id == room_type_id,
            RatePlan.is_active == True,
            RatePlan.start_date <= target_date,
            RatePlan.end_date >= target_date
        )

        # 优先使用周末策略
        if is_weekend:
            weekend_plan = query.filter(RatePlan.is_weekend == True).order_by(
                RatePlan.priority.desc()
            ).first()
            if weekend_plan:
                return weekend_plan.price

        # 使用非周末策略或通用策略
        plan = query.filter(RatePlan.is_weekend == False).order_by(
            RatePlan.priority.desc()
        ).first()

        if plan:
            return plan.price

        # 无匹配策略，使用基础价格
        return room_type.base_price

    def calculate_total_price(self, room_type_id: int, check_in_date: date,
                              check_out_date: date, room_count: int = 1) -> Decimal:
        """计算总房费"""
        total = Decimal('0')
        current_date = check_in_date

        while current_date < check_out_date:
            daily_price = self.get_price_for_date(room_type_id, current_date)
            total += daily_price * room_count
            current_date = date(
                current_date.year,
                current_date.month,
                current_date.day + 1
            ) if current_date.day < 28 else self._next_day(current_date)

        return total

    def _next_day(self, d: date) -> date:
        """获取下一天"""
        from datetime import timedelta
        return d + timedelta(days=1)

    def get_price_calendar(self, room_type_id: int, start_date: date, end_date: date) -> List[dict]:
        """获取价格日历"""
        result = []
        current_date = start_date

        while current_date <= end_date:
            price = self.get_price_for_date(room_type_id, current_date)
            result.append({
                'date': current_date,
                'price': price,
                'is_weekend': current_date.weekday() >= 4
            })
            current_date = self._next_day(current_date)

        return result
