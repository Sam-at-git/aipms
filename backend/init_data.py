"""
初始化数据脚本
创建：3种房型、40间房间、6名员工、初始价格策略
"""
import sys
sys.path.insert(0, '.')

from datetime import date, timedelta
from decimal import Decimal
from app.database import SessionLocal, init_db
from app.models.ontology import (
    RoomType, Room, RoomStatus, Employee, EmployeeRole, RatePlan
)
from app.security.auth import get_password_hash


def init_room_types(db):
    """初始化房型"""
    room_types = [
        {
            'name': '标间',
            'description': '舒适标准双床房，配备独立卫浴、空调、电视、免费WiFi',
            'base_price': Decimal('288.00'),
            'max_occupancy': 2,
            'amenities': '空调,电视,WiFi,独立卫浴,电热水壶,吹风机'
        },
        {
            'name': '大床房',
            'description': '温馨大床房，1.8米大床，适合情侣或单人入住',
            'base_price': Decimal('328.00'),
            'max_occupancy': 2,
            'amenities': '空调,电视,WiFi,独立卫浴,电热水壶,吹风机,迷你冰箱'
        },
        {
            'name': '豪华间',
            'description': '宽敞豪华房，配备沙发休息区，高层景观',
            'base_price': Decimal('458.00'),
            'max_occupancy': 3,
            'amenities': '空调,电视,WiFi,独立卫浴,电热水壶,吹风机,迷你冰箱,沙发,保险箱,浴袍'
        }
    ]

    created = []
    for rt_data in room_types:
        existing = db.query(RoomType).filter(RoomType.name == rt_data['name']).first()
        if not existing:
            rt = RoomType(**rt_data)
            db.add(rt)
            created.append(rt_data['name'])

    db.commit()
    print(f"房型初始化完成: {created if created else '已存在'}")
    return db.query(RoomType).all()


def init_rooms(db, room_types):
    """初始化40间房间"""
    # 房间分布：
    # 2楼: 201-210 (标间5间, 大床房5间)
    # 3楼: 301-310 (标间5间, 大床房5间)
    # 4楼: 401-410 (标间5间, 大床房3间, 豪华间2间)
    # 5楼: 501-510 (大床房2间, 豪华间8间)

    rt_map = {rt.name: rt.id for rt in room_types}

    rooms_config = []

    # 2楼
    for i in range(1, 6):
        rooms_config.append({'number': f'20{i}', 'floor': 2, 'type': '标间'})
    for i in range(6, 11):
        rooms_config.append({'number': f'2{i:02d}' if i < 10 else f'2{i}', 'floor': 2, 'type': '大床房'})

    # 3楼
    for i in range(1, 6):
        rooms_config.append({'number': f'30{i}', 'floor': 3, 'type': '标间'})
    for i in range(6, 11):
        rooms_config.append({'number': f'3{i:02d}' if i < 10 else f'3{i}', 'floor': 3, 'type': '大床房'})

    # 4楼
    for i in range(1, 6):
        rooms_config.append({'number': f'40{i}', 'floor': 4, 'type': '标间'})
    for i in range(6, 9):
        rooms_config.append({'number': f'4{i:02d}', 'floor': 4, 'type': '大床房'})
    for i in range(9, 11):
        rooms_config.append({'number': f'4{i:02d}' if i < 10 else f'4{i}', 'floor': 4, 'type': '豪华间'})

    # 5楼
    for i in range(1, 3):
        rooms_config.append({'number': f'50{i}', 'floor': 5, 'type': '大床房'})
    for i in range(3, 11):
        rooms_config.append({'number': f'5{i:02d}' if i < 10 else f'5{i}', 'floor': 5, 'type': '豪华间'})

    created = 0
    for room_data in rooms_config:
        existing = db.query(Room).filter(Room.room_number == room_data['number']).first()
        if not existing:
            room = Room(
                room_number=room_data['number'],
                floor=room_data['floor'],
                room_type_id=rt_map[room_data['type']],
                status=RoomStatus.VACANT_CLEAN
            )
            db.add(room)
            created += 1

    db.commit()
    total = db.query(Room).count()
    print(f"房间初始化完成: 新增 {created} 间，共 {total} 间")


def init_employees(db):
    """初始化6名员工"""
    employees = [
        {
            'username': 'manager',
            'password': '123456',
            'name': '张经理',
            'phone': '13800001111',
            'role': EmployeeRole.MANAGER
        },
        {
            'username': 'front1',
            'password': '123456',
            'name': '李前台',
            'phone': '13800002222',
            'role': EmployeeRole.RECEPTIONIST
        },
        {
            'username': 'front2',
            'password': '123456',
            'name': '王前台',
            'phone': '13800003333',
            'role': EmployeeRole.RECEPTIONIST
        },
        {
            'username': 'front3',
            'password': '123456',
            'name': '赵前台',
            'phone': '13800004444',
            'role': EmployeeRole.RECEPTIONIST
        },
        {
            'username': 'cleaner1',
            'password': '123456',
            'name': '刘阿姨',
            'phone': '13800005555',
            'role': EmployeeRole.CLEANER
        },
        {
            'username': 'cleaner2',
            'password': '123456',
            'name': '陈阿姨',
            'phone': '13800006666',
            'role': EmployeeRole.CLEANER
        }
    ]

    created = []
    for emp_data in employees:
        existing = db.query(Employee).filter(Employee.username == emp_data['username']).first()
        if not existing:
            emp = Employee(
                username=emp_data['username'],
                password_hash=get_password_hash(emp_data['password']),
                name=emp_data['name'],
                phone=emp_data['phone'],
                role=emp_data['role']
            )
            db.add(emp)
            created.append(emp_data['name'])

    db.commit()
    print(f"员工初始化完成: {created if created else '已存在'}")


def init_rate_plans(db, room_types):
    """初始化价格策略"""
    rt_map = {rt.name: rt.id for rt in room_types}

    today = date.today()
    weekend_start = today
    weekend_end = today + timedelta(days=90)

    # 周末价策略
    weekend_plans = [
        {'name': '标间周末价', 'room_type': '标间', 'price': Decimal('358.00')},
        {'name': '大床房周末价', 'room_type': '大床房', 'price': Decimal('398.00')},
        {'name': '豪华间周末价', 'room_type': '豪华间', 'price': Decimal('558.00')},
    ]

    created = []
    for plan_data in weekend_plans:
        existing = db.query(RatePlan).filter(RatePlan.name == plan_data['name']).first()
        if not existing:
            plan = RatePlan(
                name=plan_data['name'],
                room_type_id=rt_map[plan_data['room_type']],
                start_date=weekend_start,
                end_date=weekend_end,
                price=plan_data['price'],
                priority=2,
                is_weekend=True,
                is_active=True
            )
            db.add(plan)
            created.append(plan_data['name'])

    db.commit()
    print(f"价格策略初始化完成: {created if created else '已存在'}")


def main():
    """主函数"""
    print("=" * 50)
    print("AIPMS 初始化数据")
    print("=" * 50)

    # 初始化数据库
    init_db()
    print("数据库表创建完成")

    # 创建会话
    db = SessionLocal()

    try:
        # 初始化数据
        room_types = init_room_types(db)
        init_rooms(db, room_types)
        init_employees(db)
        init_rate_plans(db, room_types)

        print("=" * 50)
        print("初始化完成！")
        print()
        print("默认账号：")
        print("  经理: manager / 123456")
        print("  前台: front1 / 123456")
        print("  清洁员: cleaner1 / 123456")
        print("=" * 50)

    finally:
        db.close()


if __name__ == '__main__':
    main()
