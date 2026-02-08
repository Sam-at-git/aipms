#!/usr/bin/env python3
"""
生成半年运营数据脚本
"""
import random
from datetime import datetime, timedelta, date
from decimal import Decimal
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models.ontology import (
    Room, RoomType, Guest, Reservation, StayRecord, Bill,
    Payment, Task, Employee, TaskStatus, TaskType,
    ReservationStatus, StayRecordStatus, PaymentMethod,
    GuestTier, RoomStatus
)

# 常用中文姓名
SURNAMES = ["王", "李", "张", "刘", "陈", "杨", "黄", "赵", "周", "吴", "徐", "孙", "马", "朱", "胡", "郭", "何", "高", "林", "罗"]
NAMES = ["伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋", "勇", "艳", "杰", "涛", "明", "超", "秀英", "娟", "英", "华", "红", "平", "刚", "桂英", "玉兰"]

CITIES = ["北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "武汉", "西安", "重庆", "天津", "苏州"]

SPECIAL_REQUESTS = ["需要高楼层", "要安静房间", "不要靠马路", "需要无烟房", "希望有窗", "延迟退房", "提前入住", "需要接站", "生日布置", "蜜月房间", "", "", ""]
CANCEL_REASONS = ["行程变更", "临时有事", "找到其他住宿", "天气原因", "身体不适", "工作调整", ""]
MAINTENANCE_NOTES = ["空调不制冷", "水龙头漏水", "灯泡损坏", "门锁故障", "电视遥控器失灵", "WiFi信号弱", "马桶冲水有问题", "窗户卡住", "墙纸脱落", "地毯污渍"]

RESERVATION_COUNTER = 0


def random_phone():
    return f"13{random.randint(0, 9)}{random.randint(1000, 9999)}{random.randint(1000, 9999)}"


def random_name():
    return f"{random.choice(SURNAMES)}{random.choice(NAMES)}"


def get_price_for_date(room_type_id: int, target_date: date, base_prices: dict) -> Decimal:
    base = base_prices[room_type_id]
    if target_date.weekday() >= 5:
        return base * Decimal('1.2')
    return base


def generate_guests(db: Session, count: int = 200):
    guests = []
    for i in range(count):
        is_repeat = random.random() < 0.3
        tier = GuestTier.NORMAL
        if is_repeat:
            tier_roll = random.random()
            if tier_roll < 0.6: tier = GuestTier.SILVER
            elif tier_roll < 0.85: tier = GuestTier.GOLD
            else: tier = GuestTier.PLATINUM

        guest = Guest(
            name=random_name(),
            id_type="身份证",
            id_number=f"{random.randint(110000, 650000)}{random.randint(1970, 2002)}{random.randint(1, 12):02d}{random.randint(1, 28):02d}{random.randint(1000, 9999)}",
            phone=random_phone(),
            email=f"guest{i}@example.com" if random.random() < 0.5 else None,
            tier=tier.value,
            total_stays=random.randint(1, 20) if is_repeat else 1,
            total_amount=Decimal(str(random.randint(500, 50000))) if is_repeat else Decimal('0'),
            is_blacklisted=random.random() < 0.01,
            notes=f"从 {random.choice(CITIES)} 来" if random.random() < 0.3 else None
        )
        db.add(guest)
        guests.append(guest)
    db.commit()
    return guests


def generate_reservations(db, guests, rooms, room_types, base_prices, employees, start_date, end_date):
    global RESERVATION_COUNTER
    reservations = []
    current_date = start_date

    while current_date <= end_date:
        weekday = current_date.weekday()
        month = current_date.month
        if month in [8, 10]: base_bookings = 8
        elif month in [1, 2]: base_bookings = 3
        else: base_bookings = 5

        if weekday >= 5: daily_bookings = base_bookings + random.randint(2, 5)
        else: daily_bookings = base_bookings + random.randint(-2, 3)

        for _ in range(max(1, daily_bookings)):
            days_ahead = random.randint(1, 14)
            check_in = current_date + timedelta(days=days_ahead)
            if check_in > end_date: continue

            nights = random.choices([1, 2, 3, 4, 5, 6, 7], weights=[30, 35, 20, 8, 4, 2, 1])[0]
            check_out = check_in + timedelta(days=nights)

            guest = random.choice(guests)
            room_type_id = random.choice(list(room_types.keys()))

            total_amount = Decimal('0')
            for i in range(nights):
                night_date = check_in + timedelta(days=i)
                total_amount += get_price_for_date(room_type_id, night_date, base_prices)

            if check_in < date.today():
                status_roll = random.random()
                if status_roll < 0.7: status = ReservationStatus.COMPLETED
                elif status_roll < 0.85: status = ReservationStatus.CANCELLED
                else: status = ReservationStatus.NO_SHOW
            elif check_in == date.today():
                status = random.choice([ReservationStatus.CONFIRMED, ReservationStatus.CHECKED_IN])
            else:
                if random.random() < 0.1: status = ReservationStatus.CANCELLED
                else: status = ReservationStatus.CONFIRMED

            RESERVATION_COUNTER += 1
            reservation_no = f"RES{check_in.strftime('%Y%m%d')}{RESERVATION_COUNTER:05d}"

            reservation = Reservation(
                reservation_no=reservation_no,
                guest_id=guest.id,
                room_type_id=room_type_id,
                check_in_date=check_in,
                check_out_date=check_out,
                room_count=1,
                adult_count=random.choices([1, 2, 3, 4], weights=[10, 70, 15, 5])[0],
                child_count=random.choices([0, 1, 2], weights=[80, 15, 5])[0],
                status=status,
                total_amount=total_amount,
                prepaid_amount=total_amount * Decimal('0.3') if status == ReservationStatus.CONFIRMED else Decimal('0'),
                special_requests=random.choice(SPECIAL_REQUESTS) or None,
                estimated_arrival=f"{random.randint(12, 22)}:00" if random.random() < 0.5 else None,
                cancel_reason=random.choice(CANCEL_REASONS) if status == ReservationStatus.CANCELLED else None,
                created_at=datetime.combine(current_date, datetime.min.time()) + timedelta(hours=random.randint(8, 20)),
                created_by=random.choice([e for e in employees if e.role in ['manager', 'receptionist']]).id
            )
            db.add(reservation)
            reservations.append(reservation)

        current_date += timedelta(days=1)

    db.commit()
    return reservations


def generate_stay_records(db, reservations, rooms, employees, room_types, base_prices):
    stay_records = []
    bills = []
    payments = []
    room_occupancy = {}

    checked_in = [r for r in reservations if r.status in [ReservationStatus.CHECKED_IN, ReservationStatus.COMPLETED]]

    for res in sorted(checked_in, key=lambda r: r.check_in_date):
        check_in_date = res.check_in_date

        available_rooms = []
        for room in rooms:
            if room.room_type_id != res.room_type_id: continue
            if room.id in room_occupancy and room_occupancy[room.id] > check_in_date: continue
            available_rooms.append(room)

        if not available_rooms: continue

        room = random.choice(available_rooms)
        room_occupancy[room.id] = res.check_out_date

        check_in_time = datetime.combine(check_in_date, datetime.min.time()) + timedelta(
            hours=random.randint(14, 18), minutes=random.randint(0, 59))

        check_out_time = None
        if res.status == ReservationStatus.COMPLETED:
            check_out_time = datetime.combine(res.check_out_date, datetime.min.time()) + timedelta(
                hours=random.randint(8, 12), minutes=random.randint(0, 59))

        room_charge = Decimal('0')
        nights = (res.check_out_date - check_in_date).days
        for i in range(nights):
            night_date = check_in_date + timedelta(days=i)
            room_charge += get_price_for_date(room.room_type_id, night_date, base_prices)

        stay = StayRecord(
            reservation_id=res.id,
            guest_id=res.guest_id,
            room_id=room.id,
            check_in_time=check_in_time,
            check_out_time=check_out_time,
            expected_check_out=res.check_out_date,
            deposit_amount=Decimal(str(random.randint(200, 500))),
            status=StayRecordStatus.CHECKED_OUT if check_out_time else StayRecordStatus.ACTIVE,
            created_at=check_in_time,
            created_by=random.choice([e for e in employees if e.role in ['manager', 'receptionist']]).id
        )
        db.add(stay)
        db.flush()
        stay_records.append(stay)

        bill = Bill(stay_record_id=stay.id, total_amount=room_charge, paid_amount=Decimal('0'), is_settled=False)

        if check_out_time:
            payment_roll = random.random()
            if payment_roll < 0.85:
                paid = room_charge
                bill.is_settled = True
            elif payment_roll < 0.95:
                paid = room_charge * Decimal('0.5')
                bill.is_settled = False
            else:
                paid = Decimal('0')
                bill.is_settled = False

            bill.total_amount = room_charge
            bill.paid_amount = paid

            if paid > 0:
                payment = Payment(
                    bill_id=0,
                    amount=paid,
                    method=random.choice([PaymentMethod.CASH, PaymentMethod.CARD]),
                    payment_time=check_out_time + timedelta(minutes=random.randint(5, 30)),
                    remark="房费结清" if bill.is_settled else "部分支付",
                    created_by=random.choice([e for e in employees if e.role in ['manager', 'receptionist']]).id
                )
                db.add(payment)
                db.flush()
                payments.append(payment)

        db.add(bill)
        db.flush()
        bills.append(bill)

    db.commit()
    return stay_records, bills, payments


def generate_tasks(db, stay_records, rooms, employees, start_date, end_date):
    tasks = []
    cleaners = [e for e in employees if e.role == 'cleaner'] or employees

    for stay in stay_records:
        if stay.status == StayRecordStatus.CHECKED_OUT and stay.check_out_time:
            task_created = stay.check_out_time + timedelta(minutes=random.randint(5, 30))
            if task_created.date() > end_date: continue

            completion_delay = random.choices([0, 1], weights=[70, 30])[0]
            task_completed = task_created + timedelta(hours=random.randint(1, 6), days=completion_delay)

            status = TaskStatus.COMPLETED
            started_at = task_created + timedelta(minutes=random.randint(10, 60))
            completed_at = task_completed

            if random.random() < 0.05:
                status = TaskStatus.ASSIGNED
                completed_at = None

            task = Task(
                room_id=stay.room_id,
                task_type=TaskType.CLEANING,
                status=status,
                assignee_id=random.choice(cleaners).id,
                priority=random.choices([1, 2, 3], weights=[50, 40, 10])[0],
                notes="退房后清洁",
                created_at=task_created,
                started_at=started_at,
                completed_at=completed_at,
                created_by=random.choice([e for e in employees if e.role in ['manager', 'receptionist']]).id
            )
            db.add(task)
            tasks.append(task)

    for room in rooms:
        maintenance_count = random.choices([0, 0, 1, 1, 2, 3], weights=[30, 30, 20, 12, 6, 2])[0]
        for _ in range(maintenance_count):
            task_date = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))
            task_created = datetime.combine(task_date, datetime.min.time()) + timedelta(hours=random.randint(8, 18))
            task_completed = task_created + timedelta(days=random.randint(1, 3), hours=random.randint(2, 8))

            task = Task(
                room_id=room.id,
                task_type=TaskType.MAINTENANCE,
                status=TaskStatus.COMPLETED,
                assignee_id=random.choice(cleaners).id if random.random() < 0.6 else None,
                priority=random.choices([2, 3, 4], weights=[40, 40, 20])[0],
                notes=random.choice(MAINTENANCE_NOTES),
                created_at=task_created,
                started_at=task_created + timedelta(hours=random.randint(1, 4)),
                completed_at=task_completed,
                created_by=random.choice([e for e in employees if e.role == 'manager']).id
            )
            db.add(task)
            tasks.append(task)

    db.commit()
    return tasks


def update_room_status(db, stay_records, tasks):
    db.query(Room).update({"status": RoomStatus.VACANT_CLEAN})
    db.flush()

    for stay in stay_records:
        if stay.status == StayRecordStatus.ACTIVE:
            room = db.query(Room).get(stay.room_id)
            if room: room.status = RoomStatus.OCCUPIED

    for task in tasks:
        if task.status in [TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS]:
            room = db.query(Room).get(task.room_id)
            if room: room.status = RoomStatus.VACANT_DIRTY

    db.commit()


def generate_walk_ins(db, guests, rooms, employees, room_types, base_prices, start_date, end_date):
    stay_records = []
    bills = []
    payments = []
    receptionists = [e for e in employees if e.role in ['manager', 'receptionist']]

    current_date = start_date
    while current_date <= end_date:
        walk_in_count = random.choices([0, 1, 2, 3], weights=[20, 50, 25, 5])[0]
        if current_date.weekday() >= 5:
            walk_in_count = random.choices([0, 1, 2, 3, 4], weights=[10, 40, 30, 15, 5])[0]

        for _ in range(walk_in_count):
            # Find available rooms
            occupied = set()
            for s in db.query(StayRecord).all():
                if s.check_in_time.date() <= current_date <= (s.check_out_time.date() if s.check_out_time else date.today()):
                    if s.status == StayRecordStatus.ACTIVE: occupied.add(s.room_id)
            for s in stay_records:
                if s.check_in_time.date() <= current_date <= (s.check_out_time.date() if s.check_out_time else date.today()):
                    if s.status == StayRecordStatus.ACTIVE: occupied.add(s.room_id)

            available = [r for r in rooms if r.id not in occupied]
            if not available: continue

            room = random.choice(available)
            guest = random.choice(guests)
            nights = random.choices([1, 2, 3, 4, 5], weights=[40, 35, 15, 7, 3])[0]
            check_in_date = current_date
            check_out_date = current_date + timedelta(days=nights)

            room_charge = Decimal('0')
            for i in range(nights):
                room_charge += get_price_for_date(room.room_type_id, check_in_date + timedelta(days=i), base_prices)

            check_in_time = datetime.combine(check_in_date, datetime.min.time()) + timedelta(
                hours=random.randint(14, 20), minutes=random.randint(0, 59))

            is_active = (current_date + timedelta(days=nights)) > date.today()
            status = StayRecordStatus.ACTIVE if is_active else StayRecordStatus.CHECKED_OUT
            check_out_time = None
            if not is_active:
                check_out_time = datetime.combine(check_out_date, datetime.min.time()) + timedelta(hours=random.randint(8, 12))

            stay = StayRecord(
                reservation_id=None,
                guest_id=guest.id,
                room_id=room.id,
                check_in_time=check_in_time,
                check_out_time=check_out_time,
                expected_check_out=check_out_date,
                deposit_amount=Decimal(str(random.randint(200, 500))),
                status=status,
                created_at=check_in_time,
                created_by=random.choice(receptionists).id
            )
            db.add(stay)
            db.flush()
            stay_records.append(stay)

            bill = Bill(stay_record_id=stay.id, total_amount=room_charge, paid_amount=Decimal('0'), is_settled=False)

            if check_out_time and random.random() < 0.8:
                paid = room_charge * Decimal(random.uniform(0.5, 1))
                payment = Payment(
                    bill_id=0,
                    amount=paid,
                    method=random.choice([PaymentMethod.CASH, PaymentMethod.CARD]),
                    payment_time=check_out_time + timedelta(minutes=random.randint(5, 60)),
                    created_by=random.choice(receptionists).id
                )
                db.add(payment)
                db.flush()
                payments.append(payment)
                bill.paid_amount = paid
                bill.is_settled = paid >= room_charge

            db.add(bill)
            db.flush()
            bills.append(bill)

        current_date += timedelta(days=1)

    db.commit()
    return stay_records, bills, payments


def main():
    print("=" * 60)
    print("生成半年运营数据")
    print("=" * 60)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        print("\n清空现有数据...")
        for model in [Payment, Bill, StayRecord, Task, Reservation, Guest, Room, RoomType, Employee]:
            db.query(model).delete()
        db.commit()
        print("✓ 数据清空完成")

        print("\n创建房型...")
        room_types_data = [
            {"name": "标间", "base_price": Decimal("288.00"), "max_occupancy": 2},
            {"name": "大床房", "base_price": Decimal("368.00"), "max_occupancy": 2},
            {"name": "豪华间", "base_price": Decimal("588.00"), "max_occupancy": 3},
        ]
        room_types = {}
        base_prices = {}
        for rt_data in room_types_data:
            rt = RoomType(**rt_data)
            db.add(rt)
            db.flush()
            room_types[rt.id] = rt
            base_prices[rt.id] = rt_data["base_price"]
        print(f"✓ 创建了 {len(room_types)} 种房型")

        print("\n创建房间...")
        rooms = []
        floor_room_nums = {1: range(101, 115), 2: range(201, 215), 3: range(301, 312)}
        room_type_ids = list(room_types.keys())
        for floor, room_nums in floor_room_nums.items():
            for room_num in room_nums:
                rt_id = room_type_ids[0] if floor == 1 else (
                    random.choices(room_type_ids, weights=[60, 35, 5])[0] if floor == 2 else
                    random.choices(room_type_ids, weights=[20, 50, 30])[0]
                )
                room = Room(room_number=str(room_num), floor=floor, room_type_id=rt_id, status=RoomStatus.VACANT_CLEAN)
                rooms.append(room)
                db.add(room)
        db.commit()
        print(f"✓ 创建了 {len(rooms)} 间房间")

        print("\n创建员工...")
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        employees_data = [
            {"username": "sysadmin", "name": "系统管理员", "phone": "13800000000", "role": "sysadmin"},
            {"username": "manager", "name": "张经理", "phone": "13800001111", "role": "manager"},
            {"username": "front1", "name": "李前台", "phone": "13800001112", "role": "receptionist"},
            {"username": "front2", "name": "王前台", "phone": "13800001113", "role": "receptionist"},
            {"username": "front3", "name": "赵前台", "phone": "13800001114", "role": "receptionist"},
            {"username": "cleaner1", "name": "刘阿姨", "phone": "13800002111", "role": "cleaner"},
            {"username": "cleaner2", "name": "陈阿姨", "phone": "13800002112", "role": "cleaner"},
        ]
        employees = []
        for emp_data in employees_data:
            emp = Employee(username=emp_data["username"], password_hash=pwd_context.hash(emp_data["username"]),
                          name=emp_data["name"], phone=emp_data["phone"], role=emp_data["role"], is_active=True)
            employees.append(emp)
            db.add(emp)
        db.commit()
        print(f"✓ 创建了 {len(employees)} 名员工")

        start_date = date.today() - timedelta(days=180)
        end_date = date.today()
        print(f"\n生成数据范围: {start_date} 至 {end_date}")

        print("\n生成客人数据...")
        guests = generate_guests(db, 300)
        print(f"✓ 生成了 {len(guests)} 位客人")

        print("\n生成预订数据...")
        reservations = generate_reservations(db, guests, rooms, room_types, base_prices, employees, start_date, end_date)
        print(f"✓ 生成了 {len(reservations)} 条预订记录")

        print("\n生成入住记录数据...")
        stay_records, bills, payments = generate_stay_records(db, reservations, rooms, employees, room_types, base_prices)
        print(f"✓ 生成了 {len(stay_records)} 条入住记录")
        print(f"✓ 生成了 {len(bills)} 条账单")
        print(f"✓ 生成了 {len(payments)} 条支付记录")

        print("\n生成直接入住数据...")
        walkin_stays, walkin_bills, walkin_payments = generate_walk_ins(db, guests, rooms, employees, room_types, base_prices, start_date, end_date)
        print(f"✓ 生成了 {len(walkin_stays)} 条直接入住记录")

        all_stays = stay_records + walkin_stays

        print("\n生成任务数据...")
        tasks = generate_tasks(db, all_stays, rooms, employees, start_date, end_date)
        print(f"✓ 生成了 {len(tasks)} 条任务记录")

        print("\n更新房间状态...")
        update_room_status(db, all_stays, tasks)

        print("\n" + "=" * 60)
        print("数据生成完成！统计信息：")
        print("=" * 60)
        for k, v in [("房型", len(room_types)), ("房间", len(rooms)), ("员工", len(employees)),
                     ("客人", db.query(Guest).count()), ("预订", db.query(Reservation).count()),
                     ("入住记录", db.query(StayRecord).count()), ("账单", db.query(Bill).count()),
                     ("支付", db.query(Payment).count()), ("任务", db.query(Task).count())]:
            print(f"  {k}: {v}")

        print("\n预订状态分布:")
        for status in ["confirmed", "checked_in", "completed", "cancelled", "no_show"]:
            print(f"  {status}: {db.query(Reservation).filter_by(status=status).count()}")

        print("\n当前房间状态:")
        for status in ["vacant_clean", "occupied", "vacant_dirty", "out_of_order"]:
            print(f"  {status}: {db.query(Room).filter_by(status=status).count()}")

        print("\n" + "=" * 60)
        print("默认登录账号（密码与用户名相同）：")
        print("  sysadmin, manager, front1, cleaner1")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
