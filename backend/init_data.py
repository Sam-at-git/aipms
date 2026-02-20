"""
初始化数据脚本 — 多分店版
创建：组织架构、角色权限、房型、房间、员工、价格策略、菜单、系统配置

组织架构：
  AI酒店集团 (GROUP)
  ├── 杭州西湖店 (BRANCH)
  │   ├── 前台部 (DEPARTMENT)
  │   └── 客房部 (DEPARTMENT)
  └── 上海外滩店 (BRANCH)
      ├── 前台部 (DEPARTMENT)
      └── 客房部 (DEPARTMENT)

默认账号（密码均为 123456）：
  sysadmin       系统管理员   集团
  manager        张经理       杭州西湖店
  front1         李前台       杭州西湖店
  cleaner1       刘阿姨       杭州西湖店
  sh_manager     王经理       上海外滩店
  sh_front1      赵前台       上海外滩店
  sh_cleaner1    陈阿姨       上海外滩店
"""
import sys
sys.path.insert(0, '.')

from datetime import date, timedelta
from decimal import Decimal
from app.database import SessionLocal, init_db
from app.models.ontology import (
    RoomType, Room, RoomStatus, Employee, EmployeeRole, RatePlan
)
from app.system.models.org import SysDepartment, DeptType
from app.security.auth import get_password_hash


def init_org_structure(db):
    """初始化组织架构：集团 → 分店 → 部门"""
    # 集团
    group = db.query(SysDepartment).filter(SysDepartment.code == "GROUP_HQ").first()
    if not group:
        group = SysDepartment(
            name="AI酒店集团", code="GROUP_HQ", dept_type=DeptType.GROUP,
            sort_order=0, is_active=True
        )
        db.add(group)
        db.flush()

    # 杭州西湖店
    branch_hz = db.query(SysDepartment).filter(SysDepartment.code == "BRANCH_HZ").first()
    if not branch_hz:
        branch_hz = SysDepartment(
            name="杭州西湖店", code="BRANCH_HZ", dept_type=DeptType.BRANCH,
            parent_id=group.id, sort_order=1, is_active=True
        )
        db.add(branch_hz)
        db.flush()

    dept_hz_front = db.query(SysDepartment).filter(SysDepartment.code == "HZ_FRONT").first()
    if not dept_hz_front:
        dept_hz_front = SysDepartment(
            name="前台部", code="HZ_FRONT", dept_type=DeptType.DEPARTMENT,
            parent_id=branch_hz.id, sort_order=1, is_active=True
        )
        db.add(dept_hz_front)
        db.flush()

    dept_hz_house = db.query(SysDepartment).filter(SysDepartment.code == "HZ_HOUSEKEEP").first()
    if not dept_hz_house:
        dept_hz_house = SysDepartment(
            name="客房部", code="HZ_HOUSEKEEP", dept_type=DeptType.DEPARTMENT,
            parent_id=branch_hz.id, sort_order=2, is_active=True
        )
        db.add(dept_hz_house)
        db.flush()

    # 上海外滩店
    branch_sh = db.query(SysDepartment).filter(SysDepartment.code == "BRANCH_SH").first()
    if not branch_sh:
        branch_sh = SysDepartment(
            name="上海外滩店", code="BRANCH_SH", dept_type=DeptType.BRANCH,
            parent_id=group.id, sort_order=2, is_active=True
        )
        db.add(branch_sh)
        db.flush()

    dept_sh_front = db.query(SysDepartment).filter(SysDepartment.code == "SH_FRONT").first()
    if not dept_sh_front:
        dept_sh_front = SysDepartment(
            name="前台部", code="SH_FRONT", dept_type=DeptType.DEPARTMENT,
            parent_id=branch_sh.id, sort_order=1, is_active=True
        )
        db.add(dept_sh_front)
        db.flush()

    dept_sh_house = db.query(SysDepartment).filter(SysDepartment.code == "SH_HOUSEKEEP").first()
    if not dept_sh_house:
        dept_sh_house = SysDepartment(
            name="客房部", code="SH_HOUSEKEEP", dept_type=DeptType.DEPARTMENT,
            parent_id=branch_sh.id, sort_order=2, is_active=True
        )
        db.add(dept_sh_house)
        db.flush()

    db.commit()
    print(f"组织架构初始化完成: 集团={group.name}, 分店=[{branch_hz.name}, {branch_sh.name}]")
    return {
        "group": group,
        "branch_hz": branch_hz, "dept_hz_front": dept_hz_front, "dept_hz_house": dept_hz_house,
        "branch_sh": branch_sh, "dept_sh_front": dept_sh_front, "dept_sh_house": dept_sh_house,
    }


def init_room_types(db, org):
    """初始化房型（每个分店各一套）"""
    room_type_defs = [
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
    for branch_key, branch in [("branch_hz", org["branch_hz"]), ("branch_sh", org["branch_sh"])]:
        for rt_data in room_type_defs:
            existing = db.query(RoomType).filter(
                RoomType.name == rt_data['name'],
                RoomType.branch_id == branch.id
            ).first()
            if not existing:
                rt = RoomType(**rt_data, branch_id=branch.id)
                db.add(rt)
                created.append(f"{branch.name}-{rt_data['name']}")

    db.commit()
    print(f"房型初始化完成: {len(created)} 个新建")
    return {
        "hz": {rt.name: rt for rt in db.query(RoomType).filter(RoomType.branch_id == org["branch_hz"].id).all()},
        "sh": {rt.name: rt for rt in db.query(RoomType).filter(RoomType.branch_id == org["branch_sh"].id).all()},
    }


def init_rooms(db, room_types_map, org):
    """初始化房间 — 杭州20间(2-3F)、上海20间(2-3F)"""
    def make_rooms(floors_config, branch_id, rt_map):
        rooms = []
        for floor, configs in floors_config.items():
            for num, type_name in configs:
                rooms.append({
                    'room_number': str(num),
                    'floor': floor,
                    'room_type_id': rt_map[type_name].id,
                    'branch_id': branch_id,
                })
        return rooms

    # 杭州: 2F(201-210), 3F(301-310) = 20间
    hz_floors = {
        2: [(f'20{i}', '标间') for i in range(1, 6)] +
           [(f'2{i:02d}' if i < 10 else f'2{i}', '大床房') for i in range(6, 11)],
        3: [(f'30{i}', '标间') for i in range(1, 6)] +
           [(f'3{i:02d}' if i < 10 else f'3{i}', '大床房') for i in range(6, 11)],
    }

    # 上海: 4F(401-410), 5F(501-510) = 20间
    sh_floors = {
        4: [(f'40{i}', '标间') for i in range(1, 6)] +
           [(f'4{i:02d}', '大床房') for i in range(6, 9)] +
           [(f'4{i:02d}' if i < 10 else f'4{i}', '豪华间') for i in range(9, 11)],
        5: [(f'50{i}', '大床房') for i in range(1, 3)] +
           [(f'5{i:02d}' if i < 10 else f'5{i}', '豪华间') for i in range(3, 11)],
    }

    hz_rooms = make_rooms(hz_floors, org["branch_hz"].id, room_types_map["hz"])
    sh_rooms = make_rooms(sh_floors, org["branch_sh"].id, room_types_map["sh"])

    created = 0
    for room_data in hz_rooms + sh_rooms:
        existing = db.query(Room).filter(
            Room.room_number == room_data['room_number'],
            Room.branch_id == room_data['branch_id']
        ).first()
        if not existing:
            room = Room(
                room_number=room_data['room_number'],
                floor=room_data['floor'],
                room_type_id=room_data['room_type_id'],
                branch_id=room_data['branch_id'],
                status=RoomStatus.VACANT_CLEAN
            )
            db.add(room)
            created += 1

    db.commit()
    total = db.query(Room).count()
    print(f"房间初始化完成: 新增 {created} 间，共 {total} 间")


def init_employees(db, org):
    """初始化员工 — 集团1人 + 杭州3人 + 上海3人"""
    employees = [
        # 集团层
        {
            'username': 'sysadmin', 'password': '123456',
            'name': '系统管理员', 'phone': '13800000000',
            'role': EmployeeRole.SYSADMIN,
            'department_id': org["group"].id,
            'branch_id': None,  # 集团管理员不属于特定分店
        },
        # 杭州西湖店
        {
            'username': 'manager', 'password': '123456',
            'name': '张经理', 'phone': '13800001111',
            'role': EmployeeRole.MANAGER,
            'department_id': org["branch_hz"].id,
            'branch_id': org["branch_hz"].id,
        },
        {
            'username': 'front1', 'password': '123456',
            'name': '李前台', 'phone': '13800002222',
            'role': EmployeeRole.RECEPTIONIST,
            'department_id': org["dept_hz_front"].id,
            'branch_id': org["branch_hz"].id,
        },
        {
            'username': 'cleaner1', 'password': '123456',
            'name': '刘阿姨', 'phone': '13800005555',
            'role': EmployeeRole.CLEANER,
            'department_id': org["dept_hz_house"].id,
            'branch_id': org["branch_hz"].id,
        },
        # 上海外滩店
        {
            'username': 'sh_manager', 'password': '123456',
            'name': '王经理', 'phone': '13800011111',
            'role': EmployeeRole.MANAGER,
            'department_id': org["branch_sh"].id,
            'branch_id': org["branch_sh"].id,
        },
        {
            'username': 'sh_front1', 'password': '123456',
            'name': '赵前台', 'phone': '13800012222',
            'role': EmployeeRole.RECEPTIONIST,
            'department_id': org["dept_sh_front"].id,
            'branch_id': org["branch_sh"].id,
        },
        {
            'username': 'sh_cleaner1', 'password': '123456',
            'name': '陈阿姨', 'phone': '13800016666',
            'role': EmployeeRole.CLEANER,
            'department_id': org["dept_sh_house"].id,
            'branch_id': org["branch_sh"].id,
        },
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
                role=emp_data['role'],
                department_id=emp_data.get('department_id'),
                branch_id=emp_data.get('branch_id'),
            )
            db.add(emp)
            created.append(emp_data['name'])

    db.commit()
    print(f"员工初始化完成: {created if created else '已存在'}")


def init_rate_plans(db, room_types_map, org):
    """初始化价格策略（每分店各一套周末价）"""
    today = date.today()
    weekend_end = today + timedelta(days=90)

    weekend_defs = [
        {'name': '标间周末价', 'room_type': '标间', 'price': Decimal('358.00')},
        {'name': '大床房周末价', 'room_type': '大床房', 'price': Decimal('398.00')},
        {'name': '豪华间周末价', 'room_type': '豪华间', 'price': Decimal('558.00')},
    ]

    created = []
    for branch_key, branch, rt_map in [
        ("hz", org["branch_hz"], room_types_map["hz"]),
        ("sh", org["branch_sh"], room_types_map["sh"]),
    ]:
        for plan_data in weekend_defs:
            plan_name = f"{branch.name}-{plan_data['name']}"
            existing = db.query(RatePlan).filter(RatePlan.name == plan_name).first()
            if not existing:
                plan = RatePlan(
                    name=plan_name,
                    room_type_id=rt_map[plan_data['room_type']].id,
                    start_date=today,
                    end_date=weekend_end,
                    price=plan_data['price'],
                    priority=2,
                    is_weekend=True,
                    is_active=True,
                    branch_id=branch.id,
                )
                db.add(plan)
                created.append(plan_name)

    db.commit()
    print(f"价格策略初始化完成: {len(created)} 个新建")


def main():
    """主函数"""
    print("=" * 50)
    print("AIPMS 初始化数据（多分店版）")
    print("=" * 50)

    # 初始化数据库
    init_db()
    print("数据库表创建完成")

    # 创建会话
    db = SessionLocal()

    try:
        # 1. 组织架构
        org = init_org_structure(db)

        # 2. 房型（分店独立）
        room_types_map = init_room_types(db, org)

        # 3. 房间（分店独立）
        init_rooms(db, room_types_map, org)

        # 4. 员工（含分店归属）
        init_employees(db, org)

        # 5. 价格策略（分店独立）
        init_rate_plans(db, room_types_map, org)

        # 6. 系统模块种子数据
        from app.system.services.rbac_seed import seed_rbac_data
        from app.system.services.menu_seed import seed_menu_data
        from app.system.services.config_seed import seed_config_data

        rbac_stats = seed_rbac_data(db)
        print(f"RBAC初始化完成: {rbac_stats}")
        menu_stats = seed_menu_data(db)
        print(f"菜单初始化完成: {menu_stats}")
        config_stats = seed_config_data(db)
        print(f"系统配置初始化完成: {config_stats}")

        print("=" * 50)
        print("初始化完成！")
        print()
        print("默认账号（密码均为 123456）：")
        print("  系统管理员:   sysadmin    （集团全局）")
        print("  杭州店经理:   manager     （杭州西湖店）")
        print("  杭州店前台:   front1      （杭州西湖店）")
        print("  杭州店清洁:   cleaner1    （杭州西湖店）")
        print("  上海店经理:   sh_manager  （上海外滩店）")
        print("  上海店前台:   sh_front1   （上海外滩店）")
        print("  上海店清洁:   sh_cleaner1 （上海外滩店）")
        print("=" * 50)

    finally:
        db.close()


def init_business_data(db):
    """初始化业务数据（向后兼容 — 不依赖组织架构，供 benchmark 使用）

    创建 3 种房型 + 40 间房间 + 6 个价格策略（无 branch_id）
    """
    room_type_defs = [
        {'name': '标间', 'description': '舒适标准双床房', 'base_price': Decimal('288.00'), 'max_occupancy': 2,
         'amenities': '空调,电视,WiFi,独立卫浴,电热水壶,吹风机'},
        {'name': '大床房', 'description': '温馨大床房', 'base_price': Decimal('328.00'), 'max_occupancy': 2,
         'amenities': '空调,电视,WiFi,独立卫浴,电热水壶,吹风机,迷你冰箱'},
        {'name': '豪华间', 'description': '宽敞豪华房', 'base_price': Decimal('458.00'), 'max_occupancy': 3,
         'amenities': '空调,电视,WiFi,独立卫浴,电热水壶,吹风机,迷你冰箱,沙发,保险箱,浴袍'},
    ]

    rt_map = {}
    for rt_data in room_type_defs:
        existing = db.query(RoomType).filter(RoomType.name == rt_data['name']).first()
        if not existing:
            rt = RoomType(**rt_data)
            db.add(rt)
            db.flush()
            rt_map[rt_data['name']] = rt
        else:
            rt_map[rt_data['name']] = existing
    db.flush()

    # 40 rooms: 2F(201-210), 3F(301-310), 4F(401-410), 5F(501-510)
    room_configs = {
        2: [(f'20{i}', '标间') for i in range(1, 6)] + [(f'2{i:02d}' if i < 10 else f'2{i}', '大床房') for i in range(6, 11)],
        3: [(f'30{i}', '标间') for i in range(1, 6)] + [(f'3{i:02d}' if i < 10 else f'3{i}', '大床房') for i in range(6, 11)],
        4: [(f'40{i}', '标间') for i in range(1, 6)] + [(f'4{i:02d}', '大床房') for i in range(6, 9)] +
           [(f'4{i:02d}' if i < 10 else f'4{i}', '豪华间') for i in range(9, 11)],
        5: [(f'50{i}', '大床房') for i in range(1, 3)] + [(f'5{i:02d}' if i < 10 else f'5{i}', '豪华间') for i in range(3, 11)],
    }

    for floor, configs in room_configs.items():
        for num, type_name in configs:
            existing = db.query(Room).filter(Room.room_number == str(num)).first()
            if not existing:
                db.add(Room(
                    room_number=str(num), floor=floor,
                    room_type_id=rt_map[type_name].id,
                    status=RoomStatus.VACANT_CLEAN,
                ))

    db.commit()


def reset_business_data(db):
    """重置业务数据（保留 benchmark 和系统管理数据）

    Benchmark 测试使用此函数在每次运行前重置到已知状态。
    """
    from app.hotel.models.ontology import (
        Room, RoomType, Guest, Reservation, StayRecord, Bill, Payment, Task, RatePlan
    )

    # 按外键依赖顺序删除
    db.query(Payment).delete()
    db.query(Bill).delete()
    db.query(Task).delete()
    db.query(StayRecord).delete()
    db.query(Reservation).delete()
    db.query(Guest).delete()
    db.query(Room).delete()
    db.query(RatePlan).delete()
    db.query(RoomType).delete()
    db.commit()

    # 重新 seed
    init_business_data(db)


if __name__ == '__main__':
    main()
