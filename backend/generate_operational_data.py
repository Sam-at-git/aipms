"""
模拟一年运营数据脚本
生成周期：2025年2月7日 - 2026年2月6日
规则：周末入住率90-100%，工作日60-85%
"""
import sys
sys.path.insert(0, '.')

import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from app.database import SessionLocal, init_db
from app.models.ontology import (
    Room, RoomType, RoomStatus, Guest, Reservation, ReservationStatus,
    StayRecord, StayRecordStatus, Bill, Payment, PaymentMethod, Employee, EmployeeRole
)


# ============ 随机数据生成器 ============

CHINESE_SURNAMES = [
    '王', '李', '张', '刘', '陈', '杨', '黄', '赵', '周', '吴',
    '徐', '孙', '马', '胡', '朱', '郭', '何', '罗', '高', '林'
]

CHINESE_NAMES = [
    '伟', '芳', '娜', '敏', '静', '丽', '强', '磊', '军', '洋',
    '勇', '艳', '杰', '娟', '涛', '明', '超', '秀英', '霞', '平',
    '刚', '桂英', '玉兰', '萍', '毅', '浩', '宇', '轩', '然', '凯'
]

def generate_random_name():
    """生成随机中文姓名"""
    surname = random.choice(CHINESE_SURNAMES)
    if random.random() < 0.3:
        # 单名
        return surname + random.choice(CHINESE_NAMES)
    else:
        # 双名
        return surname + random.choice(CHINESE_NAMES) + random.choice(CHINESE_NAMES)


def generate_random_phone():
    """生成随机手机号"""
    return f"1{random.choice([3, 5, 7, 8, 9])}{random.randint(100000000, 999999999)}"


def generate_id_number():
    """生成随机身份证号"""
    return f"{random.randint(110000, 650000)}{random.randint(19900101, 20051231)}{random.randint(1000, 9999)}"


# ============ 入住率配置 ============

START_DATE = date(2025, 2, 7)
END_DATE = date(2026, 2, 6)

WEEKEND_OCCUPANCY_MIN = 0.90  # 周末最低 90%
WEEKEND_OCCUPANCY_MAX = 1.00  # 周末最高 100%
WEEKDAY_OCCUPANCY_MIN = 0.60  # 工作日最低 60%
WEEKDAY_OCCUPANCY_MAX = 0.85  # 工作日最高 85%


def is_weekend(d: date) -> bool:
    """判断是否为周末"""
    return d.weekday() in [5, 6]  # 5=周六, 6=周日


def get_target_occupancy(d: date) -> float:
    """获取指定日期的目标入住率"""
    if is_weekend(d):
        return random.uniform(WEEKEND_OCCUPANCY_MIN, WEEKEND_OCCUPANCY_MAX)
    else:
        return random.uniform(WEEKDAY_OCCUPANCY_MIN, WEEKDAY_OCCUPANCY_MAX)


def get_room_type_distribution():
    """返回房型分布比例（与实际房间数量匹配）"""
    # 根据init_data.py的房间分布：
    # 标间：2楼5间 + 3楼5间 + 4楼5间 = 15间
    # 大床房：2楼5间 + 3楼5间 + 4楼3间 + 5楼2间 = 15间
    # 豪华间：4楼2间 + 5楼8间 = 10间
    return {'标间': 15, '大床房': 15, '豪华间': 10}


# ============ 核心生成逻辑 ============

class OperationalDataGenerator:
    """运营数据生成器"""

    def __init__(self, db):
        self.db = db
        self.rooms = []
        self.room_types = []
        self.employees = []
        self.guests = {}  # phone -> Guest
        self.used_reservation_numbers = set()

        # 房间占用记录：date -> set(room_id)
        self.room_occupancy = {}

        # 生成的数据
        self.generated_guests = []
        self.generated_reservations = []
        self.generated_stay_records = []
        self.generated_bills = []
        self.generated_payments = []

    def load_existing_data(self):
        """加载现有基础数据"""
        self.rooms = self.db.query(Room).filter(Room.is_active == True).all()
        self.room_types = self.db.query(RoomType).all()
        self.employees = self.db.query(Employee).filter(Employee.is_active == True).all()

        print(f"加载 {len(self.rooms)} 间房间")
        print(f"加载 {len(self.room_types)} 种房型")
        print(f"加载 {len(self.employees)} 名员工")

        # 初始化占用记录
        for d in range((END_DATE - START_DATE).days + 1):
            current_date = START_DATE + timedelta(days=d)
            self.room_occupancy[current_date] = set()

    def get_or_create_guest(self, phone: str) -> Guest:
        """获取或创建客人"""
        if phone in self.guests:
            return self.guests[phone]

        existing = self.db.query(Guest).filter(Guest.phone == phone).first()
        if existing:
            self.guests[phone] = existing
            return existing

        guest = Guest(
            name=generate_random_name(),
            phone=phone,
            id_number=generate_id_number(),
            tier=random.choices(
                ['normal', 'silver', 'gold', 'platinum'],
                weights=[70, 20, 8, 2]
            )[0],
            total_stays=0,
            total_amount=Decimal('0'),
            is_blacklisted=False
        )
        self.db.add(guest)
        self.db.flush()

        self.guests[phone] = guest
        self.generated_guests.append(guest)
        return guest

    def generate_reservation_number(self) -> str:
        """生成唯一预订号"""
        while True:
            res_no = f"RES{datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
            if res_no not in self.used_reservation_numbers:
                self.used_reservation_numbers.add(res_no)
                return res_no

    def get_available_rooms(self, target_date: date, room_type_id: int = None) -> list[Room]:
        """获取指定日期可用的房间"""
        occupied = self.room_occupancy.get(target_date, set())

        available = []
        for room in self.rooms:
            if room.id in occupied:
                continue
            if room_type_id and room.room_type_id != room_type_id:
                continue
            available.append(room)

        return available

    def is_room_available(self, room: Room, start_date: date, end_date: date) -> bool:
        """检查房间在日期范围内是否可用"""
        for d in range((end_date - start_date).days):
            check_date = start_date + timedelta(days=d)
            if room.id in self.room_occupancy.get(check_date, set()):
                return False
        return True

    def occupy_room(self, room: Room, start_date: date, end_date: date):
        """占用房间（记录入住）"""
        for d in range((end_date - start_date).days):
            check_date = start_date + timedelta(days=d)
            if check_date not in self.room_occupancy:
                self.room_occupancy[check_date] = set()
            self.room_occupancy[check_date].add(room.id)

    def get_room_type_by_name(self, name: str) -> RoomType:
        """根据名称获取房型"""
        for rt in self.room_types:
            if rt.name == name:
                return rt
        return self.room_types[0]

    def get_front_desk_staff(self) -> Employee:
        """获取前台员工"""
        front_desk = [e for e in self.employees if e.role == EmployeeRole.RECEPTIONIST]
        return random.choice(front_desk) if front_desk else self.employees[0]

    def get_room_price(self, room: Room, check_in_date: date) -> Decimal:
        """获取房间价格（考虑周末）"""
        room_type = next(rt for rt in self.room_types if rt.id == room.room_type_id)

        # 周末价
        if is_weekend(check_in_date):
            weekend_prices = {'标间': Decimal('358.00'), '大床房': Decimal('398.00'), '豪华间': Decimal('558.00')}
            return weekend_prices.get(room_type.name, room_type.base_price)

        return room_type.base_price

    def is_holiday(self, d: date) -> bool:
        """判断是否为节假日（简化版）"""
        # 春节 (2025年: 1月28日-2月3日, 2026年: 2月17日-2月23日)
        spring_festival_2025_start = date(2025, 1, 28)
        spring_festival_2025_end = date(2025, 2, 5)
        spring_festival_2026_start = date(2026, 2, 14)
        spring_festival_2026_end = date(2026, 2, 23)

        # 国庆节 (10月1-7日)
        national_day_start = date(d.year, 10, 1)
        national_day_end = date(d.year, 10, 7)

        # 劳动节 (5月1-5日)
        labor_day_start = date(d.year, 5, 1)
        labor_day_end = date(d.year, 5, 5)

        # 端午节 (2025年: 5月31日-6月2日, 2026年: 6月19日-6月21日)
        dragon_boat_2025_start = date(2025, 5, 31)
        dragon_boat_2025_end = date(2025, 6, 2)
        dragon_boat_2026_start = date(2026, 6, 19)
        dragon_boat_2026_end = date(2026, 6, 21)

        # 中秋节 (2025年: 10月6日-10月8日, 2026年: 9月25日-9月27日)
        mid_autumn_2025_start = date(2025, 10, 6)
        mid_autumn_2025_end = date(2025, 10, 8)
        mid_autumn_2026_start = date(2026, 9, 25)
        mid_autumn_2026_end = date(2026, 9, 27)

        # 清明节 (4月4-6日)
        qingming_start = date(d.year, 4, 4)
        qingming_end = date(d.year, 4, 6)

        # 元旦 (1月1-3日)
        new_year_start = date(d.year, 1, 1)
        new_year_end = date(d.year, 1, 3)

        return (
            (spring_festival_2025_start <= d <= spring_festival_2025_end) or
            (spring_festival_2026_start <= d <= spring_festival_2026_end) or
            (national_day_start <= d <= national_day_end) or
            (labor_day_start <= d <= labor_day_end) or
            (dragon_boat_2025_start <= d <= dragon_boat_2025_end) or
            (dragon_boat_2026_start <= d <= dragon_boat_2026_end) or
            (mid_autumn_2025_start <= d <= mid_autumn_2025_end) or
            (mid_autumn_2026_start <= d <= mid_autumn_2026_end) or
            (qingming_start <= d <= qingming_end) or
            (new_year_start <= d <= new_year_end)
        )

    def get_seasonal_factor(self, d: date) -> float:
        """获取季节性因子（影响入住率）"""
        # 春季(3-5月): 1.0, 夏季(6-8月): 1.05, 秋季(9-11月): 1.0, 冬季(12-2月): 0.95
        month = d.month
        if month in [6, 7, 8]:
            return 1.05  # 夏季旅游旺季
        elif month in [12, 1, 2]:
            return 0.95  # 冬季略淡
        else:
            return 1.0

    def generate_day_reservations(self, target_date: date):
        """为指定日期生成预订和入住"""
        # 获取基础入住率
        base_occupancy = get_target_occupancy(target_date)

        # 应用季节性因子
        seasonal_factor = self.get_seasonal_factor(target_date)

        # 节假日额外提升入住率
        if self.is_holiday(target_date):
            seasonal_factor *= 1.05  # 节假日更高

        target_occupancy = min(1.0, base_occupancy * seasonal_factor)
        total_rooms = len(self.rooms)
        target_occupied = int(total_rooms * target_occupancy)

        # 计算当前已被占用的房间数
        already_occupied = len(self.room_occupancy.get(target_date, set()))
        needed = max(0, target_occupied - already_occupied)

        if needed <= 0:
            return

        # 获取可用房间
        available_rooms = self.get_available_rooms(target_date)

        # 随机选择需要的房间数量
        selected_rooms = random.sample(available_rooms, min(needed, len(available_rooms)))

        for room in selected_rooms:
            self.generate_single_reservation(room, target_date)

    def generate_single_reservation(self, room: Room, check_in_date: date):
        """生成单个预订"""
        # 随机决定入住天数：1-5天，周末倾向于更长
        if is_weekend(check_in_date):
            stay_days = random.choices([1, 2, 3, 4], weights=[20, 40, 30, 10])[0]
        else:
            stay_days = random.choices([1, 2, 3, 4], weights=[40, 35, 20, 5])[0]

        check_out_date = check_in_date + timedelta(days=stay_days)

        # 确保不超过结束日期
        if check_out_date > END_DATE + timedelta(days=7):  # 允许超出一周退房
            check_out_date = END_DATE + timedelta(days=1)
            stay_days = (check_out_date - check_in_date).days

        if stay_days <= 0:
            return

        # 创建/获取客人
        phone = generate_random_phone()
        guest = self.get_or_create_guest(phone)

        # 决定是否有预订（80%有预订，20% walk-in）
        has_reservation = random.random() < 0.8

        room_type = next(rt for rt in self.room_types if rt.id == room.room_type_id)
        price_per_night = self.get_room_price(room, check_in_date)
        total_amount = price_per_night * stay_days

        front_desk = self.get_front_desk_staff()

        if has_reservation:
            # 创建预订
            reservation = Reservation(
                reservation_no=self.generate_reservation_number(),
                guest_id=guest.id,
                room_type_id=room_type.id,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                adult_count=random.choices([1, 2], weights=[30, 70])[0],
                child_count=random.choices([0, 1], weights=[80, 20])[0],
                status=ReservationStatus.CONFIRMED,
                total_amount=total_amount,
                prepaid_amount=Decimal('0'),
                special_requests=random.choices(['', '高层房间', '无烟房', '安静房间'], weights=[70, 10, 10, 10])[0],
                estimated_arrival=f"{random.randint(12, 22)}:00",
                created_by=front_desk.id
            )
            self.db.add(reservation)
            self.db.flush()
            self.generated_reservations.append(reservation)
            reservation_id = reservation.id
        else:
            reservation_id = None

        # 创建入住记录
        check_in_time = datetime.combine(check_in_date, datetime.min.time()) + timedelta(
            hours=random.randint(13, 22),
            minutes=random.randint(0, 59)
        )

        stay_record = StayRecord(
            reservation_id=reservation_id,
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=check_in_time,
            expected_check_out=check_out_date,
            deposit_amount=Decimal(str(random.randint(200, 500))),
            status=StayRecordStatus.ACTIVE,
            created_by=front_desk.id
        )
        self.db.add(stay_record)
        self.db.flush()
        self.generated_stay_records.append(stay_record)

        # 创建账单
        bill = Bill(
            stay_record_id=stay_record.id,
            total_amount=total_amount,
            paid_amount=Decimal('0'),
            is_settled=False
        )
        self.db.add(bill)
        self.db.flush()
        self.generated_bills.append(bill)

        # 随机决定是否预付（30%预付）
        if random.random() < 0.3:
            prepaid_ratio = random.uniform(0.3, 1.0)
            prepaid_amount = total_amount * Decimal(str(prepaid_ratio))
            prepaid_amount = prepaid_amount.quantize(Decimal('0.01'))

            payment = Payment(
                bill_id=bill.id,
                amount=prepaid_amount,
                method=random.choices([PaymentMethod.CASH, PaymentMethod.CARD], weights=[40, 60])[0],
                created_by=front_desk.id
            )
            self.db.add(payment)
            self.generated_payments.append(payment)

            # 更新账单
            bill.paid_amount = prepaid_amount
            if has_reservation:
                reservation = self.db.query(Reservation).filter(Reservation.id == reservation_id).first()
                if reservation:
                    reservation.prepaid_amount = prepaid_amount

        # 标记房间被占用
        self.occupy_room(room, check_in_date, check_out_date)

        # 更新客人统计
        guest.total_stays += 1
        guest.total_amount += total_amount

        # 有预订的更新状态
        if has_reservation:
            reservation.status = ReservationStatus.CHECKED_IN

    def generate_checkouts(self, target_date: date):
        """处理指定日期的退房"""
        # 查找应该在这一天退房的活跃入住记录
        checking_out = []
        for stay in self.generated_stay_records:
            if stay.status == StayRecordStatus.ACTIVE:
                expected_checkout = stay.expected_check_out if isinstance(stay.expected_check_out, date) else stay.expected_check_out
                if expected_checkout == target_date:
                    checking_out.append(stay)

        for stay in checking_out:
            # 随机决定是否延迟退房（10%概率）
            if random.random() < 0.1:
                continue  # 延迟退房，稍后处理

            self.process_checkout(stay, target_date)

    def process_checkout(self, stay: StayRecord, checkout_date: date):
        """处理退房"""
        checkout_time = datetime.combine(checkout_date, datetime.min.time()) + timedelta(
            hours=random.randint(8, 13),
            minutes=random.randint(0, 59)
        )

        stay.check_out_time = checkout_time
        stay.status = StayRecordStatus.CHECKED_OUT

        # 获取账单并计算最终金额
        bill = stay.bill
        if bill:
            # 如果有未付金额，生成支付
            if bill.balance > 0:
                payment = Payment(
                    bill_id=bill.id,
                    amount=bill.balance,
                    method=random.choices([PaymentMethod.CASH, PaymentMethod.CARD], weights=[50, 50])[0],
                    created_by=self.get_front_desk_staff().id
                )
                self.db.add(payment)
                self.generated_payments.append(payment)
                bill.paid_amount += bill.balance

            bill.is_settled = True

        # 释放房间（但checkout_date当天仍算占用）
        room = stay.room
        # 退房后房间变成vacant_dirty状态（这里只记录数据释放，不修改房间状态因为那是实时状态）

    def generate_cancellations(self):
        """生成少量取消预订"""
        # 随机取消一些已确认的预订（约5%）
        confirmed_reservations = [r for r in self.generated_reservations if r.status == ReservationStatus.CONFIRMED]

        num_to_cancel = int(len(confirmed_reservations) * 0.05)

        for reservation in random.sample(confirmed_reservations, min(num_to_cancel, len(confirmed_reservations))):
            # 只取消还没入住的
            has_stay = any(s.reservation_id == reservation.id for s in self.generated_stay_records)
            if not has_stay:
                reservation.status = ReservationStatus.CANCELLED
                reservation.cancel_reason = random.choice([
                    '临时有事', '行程变更', '找到了更合适的酒店', '身体不适'
                ])

                # 释放占用的房间
                self.release_room_occupancy(reservation.check_in_date, reservation.check_out_date, reservation.room_type_id)

    def release_room_occupancy(self, start_date: date, end_date: date, room_type_id: int):
        """释放取消预订的房间占用"""
        # 找到这个预订对应的房间并释放
        for d in range((end_date - start_date).days):
            check_date = start_date + timedelta(days=d)
            if check_date in self.room_occupancy:
                # 这个处理比较复杂，简化处理：不做精确释放
                pass

    def update_room_statuses(self):
        """更新所有房间的最终状态"""
        # 检查今天（模拟结束日）的入住情况
        today = END_DATE
        active_stays = [s for s in self.generated_stay_records if s.status == StayRecordStatus.ACTIVE]

        for stay in active_stays:
            room = stay.room
            room.status = RoomStatus.OCCUPIED

        # 其余房间设为空闲清洁状态
        occupied_room_ids = {s.room_id for s in active_stays}
        for room in self.rooms:
            if room.id not in occupied_room_ids:
                room.status = RoomStatus.VACANT_CLEAN

    def generate(self):
        """生成所有数据"""
        print("\n" + "=" * 50)
        print("开始生成运营数据")
        print("=" * 50)

        # 按日期生成
        total_days = (END_DATE - START_DATE).days + 1
        print(f"总天数: {total_days} 天")

        for i in range(total_days):
            current_date = START_DATE + timedelta(days=i)
            is_wed = is_weekend(current_date)
            is_hol = self.is_holiday(current_date)
            target_occ = get_target_occupancy(current_date)

            # 每30天或最后一天打印一次进度
            if (i + 1) % 30 == 0 or i == total_days - 1:
                print(f"[{i+1}/{total_days}] {current_date.strftime('%Y-%m-%d')} "
                      f"{'周末' if is_wed else '工作日'}{' 节假日' if is_hol else ''} - 目标入住率: {target_occ*100:.0f}%")

            # 生成当天的预订和入住
            self.generate_day_reservations(current_date)

            # 处理当天的退房
            self.generate_checkouts(current_date)

        # 生成取消预订
        print("\n生成取消预订...")
        self.generate_cancellations()

        # 更新房间状态
        print("更新房间状态...")
        self.update_room_statuses()

        # 提交所有数据
        print("\n提交数据到数据库...")
        self.db.commit()

        # 统计信息
        self.print_statistics()

    def print_statistics(self):
        """打印统计信息"""
        print("\n" + "=" * 50)
        print("数据生成完成！")
        print("=" * 50)

        print(f"\n新增客人: {len(self.generated_guests)} 位")
        print(f"生成预订: {len(self.generated_reservations)} 条")

        # 预订状态统计
        res_status = {}
        for r in self.generated_reservations:
            status = r.status.value if hasattr(r.status, 'value') else r.status
            res_status[status] = res_status.get(status, 0) + 1
        print("  预订状态分布:")
        for status, count in res_status.items():
            print(f"    - {status}: {count}")

        print(f"\n生成入住记录: {len(self.generated_stay_records)} 条")

        # 入住状态统计
        stay_status = {}
        for s in self.generated_stay_records:
            status = s.status.value if hasattr(s.status, 'value') else s.status
            stay_status[status] = stay_status.get(status, 0) + 1
        print("  入住状态分布:")
        for status, count in stay_status.items():
            print(f"    - {status}: {count}")

        print(f"\n生成账单: {len(self.generated_bills)} 条")
        print(f"生成支付记录: {len(self.generated_payments)} 条")

        # 房间分布
        print(f"\n房间总数: {len(self.rooms)} 间")
        room_status_count = {}
        for room in self.rooms:
            status = room.status.value if hasattr(room.status, 'value') else room.status
            room_status_count[status] = room_status_count.get(status, 0) + 1
        print("  房间状态分布:")
        for status, count in room_status_count.items():
            print(f"    - {status}: {count}")

        # 计算实际入住率
        total_room_nights = sum(len(occ) for occ in self.room_occupancy.values())
        total_possible_nights = len(self.rooms) * len(self.room_occupancy)
        actual_occupancy = total_room_nights / total_possible_nights if total_possible_nights > 0 else 0

        print(f"\n总体入住率: {actual_occupancy * 100:.1f}%")
        print(f"总间夜数: {total_room_nights}")
        print(f"可售间夜数: {total_possible_nights}")

        # 月度统计
        print("\n" + "-" * 50)
        print("月度入住率统计:")
        print("-" * 50)

        monthly_stats = {}
        for d, occupied_rooms in self.room_occupancy.items():
            month_key = d.strftime('%Y-%m')
            if month_key not in monthly_stats:
                monthly_stats[month_key] = {'occupied': 0, 'days': 0}
            monthly_stats[month_key]['occupied'] += len(occupied_rooms)
            monthly_stats[month_key]['days'] += 1

        for month in sorted(monthly_stats.keys()):
            stats = monthly_stats[month]
            avg_occupancy = stats['occupied'] / (stats['days'] * len(self.rooms)) * 100
            print(f"  {month}: {avg_occupancy:.1f}%")


def main():
    """主函数"""
    print("=" * 50)
    print("AIPMS 运营数据生成器")
    print("=" * 50)
    print(f"模拟周期: {START_DATE} 至 {END_DATE} ({(END_DATE - START_DATE).days + 1}天)")
    print(f"周末入住率: {WEEKEND_OCCUPANCY_MIN * 100}% - {WEEKEND_OCCUPANCY_MAX * 100}%")
    print(f"工作日入住率: {WEEKDAY_OCCUPANCY_MIN * 100}% - {WEEKDAY_OCCUPANCY_MAX * 100}%")
    print(f"包含节假日: 春节、国庆、劳动节、端午、中秋、清明、元旦")

    # 创建会话
    db = SessionLocal()

    try:
        generator = OperationalDataGenerator(db)
        generator.load_existing_data()
        generator.generate()

        print("\n" + "=" * 50)
        print("所有数据已写入数据库！")
        print("=" * 50)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == '__main__':
    main()
