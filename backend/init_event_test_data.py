"""
事件测试数据初始化脚本
创建完整的测试数据以覆盖所有 15+ 种领域事件
"""
import sys
sys.path.insert(0, '.')

from datetime import date, datetime, timedelta
from decimal import Decimal

from app.database import SessionLocal, init_db
from app.models.ontology import (
    RoomType, Room, RoomStatus,
    Guest, Reservation, ReservationStatus,
    StayRecord, StayRecordStatus,
    Task, TaskType, TaskStatus,
    Bill, Payment, PaymentMethod,
    Employee, EmployeeRole, RatePlan
)
from app.models.events import EventType
from app.services.event_bus import event_bus, Event
from app.services.event_handlers import event_handlers, register_event_handlers
from app.security.auth import get_password_hash


def generate_reservation_no(db, suffix: str = "") -> str:
    """生成唯一的预订号"""
    import random
    count = db.query(Reservation).count()
    random_suffix = random.randint(1000, 9999)
    return f"RES{datetime.now().strftime('%Y%m%d')}{suffix}{count + 1:02d}{random_suffix}"


def init_additional_guests(db):
    """初始化测试客人数据"""
    guests_data = [
        {
            'name': '张三',
            'phone': '13900001111',
            'id_number': '110101199001011234',
            'email': 'zhangsan@example.com',
            'tier': 'normal',
            'preferences': '{"smoking": false, "floor": "high"}'
        },
        {
            'name': '李四',
            'phone': '13900002222',
            'id_number': '110101198502022345',
            'email': 'lisi@example.com',
            'tier': 'silver',
            'preferences': '{"smoking": true, "newspaper": "morning"}'
        },
        {
            'name': '王五',
            'phone': '13900003333',
            'id_number': '110101199003033456',
            'email': 'wangwu@example.com',
            'tier': 'gold',
            'preferences': '{"floor": "low", "extra_towels": true}'
        },
        {
            'name': '赵六',
            'phone': '13900004444',
            'id_number': '110101198804044567',
            'tier': 'platinum',
            'preferences': '{"no_disturb": true, "late_checkout": true}'
        },
        {
            'name': '孙七',
            'phone': '13900005555',
            'id_number': '110101199505055678',
            'tier': 'normal'
        },
        {
            'name': '周八',
            'phone': '13900006666',
            'id_number': '110101198206066789',
            'tier': 'silver'
        },
        {
            'name': '吴九',
            'phone': '13900007777',
            'id_number': '110101199307077890',
            'tier': 'gold'
        },
        {
            'name': '郑十',
            'phone': '13900008888',
            'id_number': '110101198808088901',
            'tier': 'normal'
        },
        {
            'name': '钱一',
            'phone': '13900009999',
            'id_number': '110101199109099012',
            'tier': 'black',  # 黑名单客人
            'is_blacklisted': True,
            'blacklist_reason': '多次未付款逃单'
        }
    ]

    created = []
    for guest_data in guests_data:
        existing = db.query(Guest).filter(Guest.phone == guest_data['phone']).first()
        if not existing:
            guest = Guest(**guest_data)
            db.add(guest)
            created.append(guest_data['name'])

    db.commit()
    print(f"测试客人初始化完成: {created if created else '已存在'}")
    return db.query(Guest).all()


def create_test_reservations(db, guests, room_types):
    """创建各种状态的预订"""
    today = date.today()
    rt_map = {rt.name: rt.id for rt in room_types}
    guest_list = list(guests)

    reservations_config = [
        # CONFIRMED - 确认的预订（今天到达）
        {
            'guest_idx': 0,
            'room_type': '标间',
            'check_in': today,
            'check_out': today + timedelta(days=3),
            'status': ReservationStatus.CONFIRMED,
            'adult_count': 2,
            'total_amount': Decimal('864.00'),
            'suffix': 'A'
        },
        # CONFIRMED - 未来预订
        {
            'guest_idx': 1,
            'room_type': '大床房',
            'check_in': today + timedelta(days=5),
            'check_out': today + timedelta(days=7),
            'status': ReservationStatus.CONFIRMED,
            'adult_count': 1,
            'total_amount': Decimal('656.00'),
            'suffix': 'B'
        },
        # CHECKED_IN - 已入住
        {
            'guest_idx': 2,
            'room_type': '豪华间',
            'check_in': today - timedelta(days=2),
            'check_out': today + timedelta(days=1),
            'status': ReservationStatus.CHECKED_IN,
            'adult_count': 2,
            'total_amount': Decimal('1374.00'),
            'suffix': 'C'
        },
        # COMPLETED - 已完成
        {
            'guest_idx': 3,
            'room_type': '标间',
            'check_in': today - timedelta(days=10),
            'check_out': today - timedelta(days=7),
            'status': ReservationStatus.COMPLETED,
            'adult_count': 1,
            'total_amount': Decimal('864.00'),
            'suffix': 'D'
        },
        # CANCELLED - 已取消
        {
            'guest_idx': 4,
            'room_type': '大床房',
            'check_in': today - timedelta(days=5),
            'check_out': today - timedelta(days=3),
            'status': ReservationStatus.CANCELLED,
            'adult_count': 2,
            'cancel_reason': '临时有事无法到店',
            'suffix': 'E'
        },
        # NO_SHOW - 未到店
        {
            'guest_idx': 5,
            'room_type': '标间',
            'check_in': today - timedelta(days=3),
            'check_out': today - timedelta(days=1),
            'status': ReservationStatus.NO_SHOW,
            'adult_count': 1,
            'suffix': 'F'
        },
        # 更多确认预订
        {
            'guest_idx': 6,
            'room_type': '豪华间',
            'check_in': today + timedelta(days=10),
            'check_out': today + timedelta(days=14),
            'status': ReservationStatus.CONFIRMED,
            'adult_count': 3,
            'total_amount': Decimal('1832.00'),
            'suffix': 'G'
        }
    ]

    created = []
    for config in reservations_config:
        guest = guest_list[config['guest_idx']]
        existing = db.query(Reservation).filter(
            Reservation.guest_id == guest.id,
            Reservation.check_in_date == config['check_in']
        ).first()
        if not existing:
            reservation = Reservation(
                reservation_no=generate_reservation_no(db, config.get('suffix', '')),
                guest_id=guest.id,
                room_type_id=rt_map[config['room_type']],
                check_in_date=config['check_in'],
                check_out_date=config['check_out'],
                status=config['status'],
                adult_count=config['adult_count'],
                total_amount=config.get('total_amount'),
                cancel_reason=config.get('cancel_reason')
            )
            db.add(reservation)
            created.append(reservation.reservation_no)

    db.commit()
    print(f"测试预订初始化完成: {len(created)} 条")
    return db.query(Reservation).all()


def create_test_stay_records(db, guests, rooms):
    """创建各种状态的住宿记录"""
    today = date.today()
    now = datetime.now()
    manager = db.query(Employee).filter(Employee.username == 'manager').first()

    # 获取第一个已确认的预订
    confirmed_res = db.query(Reservation).filter(
        Reservation.status == ReservationStatus.CONFIRMED
    ).first()

    stay_records_config = [
        # ACTIVE - 当前在住
        {
            'guest_idx': 0,
            'room_number': '201',
            'check_in': now - timedelta(days=1),
            'check_out': None,
            'expected_checkout': today + timedelta(days=2),
            'status': StayRecordStatus.ACTIVE,
            'reservation_id': None,
            'deposit': Decimal('500.00')
        },
        # ACTIVE - 在住（有预订）
        {
            'guest_idx': 2,
            'room_number': '301',
            'check_in': now - timedelta(days=2),
            'check_out': None,
            'expected_checkout': today + timedelta(days=1),
            'status': StayRecordStatus.ACTIVE,
            'reservation_id': confirmed_res.id if confirmed_res else None,
            'deposit': Decimal('800.00')
        },
        # CHECKED_OUT - 已退房
        {
            'guest_idx': 1,
            'room_number': '202',
            'check_in': now - timedelta(days=5),
            'check_out': now - timedelta(days=3),
            'expected_checkout': today - timedelta(days=3),
            'status': StayRecordStatus.CHECKED_OUT,
            'reservation_id': None,
            'deposit': Decimal('500.00')
        },
        # CHECKED_OUT - 另一个已退房
        {
            'guest_idx': 3,
            'room_number': '401',
            'check_in': now - timedelta(days=10),
            'check_out': now - timedelta(days=7),
            'expected_checkout': today - timedelta(days=7),
            'status': StayRecordStatus.CHECKED_OUT,
            'reservation_id': None,
            'deposit': Decimal('300.00')
        }
    ]

    created = []
    guest_list = list(guests)
    room_map = {r.room_number: r.id for r in rooms}

    for config in stay_records_config:
        guest = guest_list[config['guest_idx']]
        existing = db.query(StayRecord).filter(
            StayRecord.guest_id == guest.id,
            StayRecord.room_id == room_map[config['room_number']],
            StayRecord.check_in_time == config['check_in']
        ).first()
        if not existing:
            stay = StayRecord(
                guest_id=guest.id,
                room_id=room_map[config['room_number']],
                check_in_time=config['check_in'],
                check_out_time=config['check_out'],
                expected_check_out=config['expected_checkout'],
                status=config['status'],
                reservation_id=config['reservation_id'],
                deposit_amount=config['deposit'],
                created_by=manager.id
            )
            db.add(stay)
            created.append(f"{guest.name}-{config['room_number']}")

    db.commit()
    print(f"测试住宿记录初始化完成: {len(created)} 条")
    return db.query(StayRecord).all()


def create_test_bills_and_payments(db, stay_records):
    """创建账单和支付记录"""
    manager = db.query(Employee).filter(Employee.username == 'manager').first()
    front1 = db.query(Employee).filter(Employee.username == 'front1').first()

    bills_config = [
        # Active stay - 未结清账单
        {
            'stay_idx': 0,  # 第一个活跃住宿
            'total_amount': Decimal('864.00'),
            'paid_amount': Decimal('500.00'),
            'adjustment': Decimal('0.00'),
            'is_settled': False,
            'payments': [
                {'amount': Decimal('300.00'), 'method': PaymentMethod.CASH, 'operator': manager.id},
                {'amount': Decimal('200.00'), 'method': PaymentMethod.CARD, 'operator': front1.id}
            ]
        },
        # Second active stay
        {
            'stay_idx': 1,
            'total_amount': Decimal('1374.00'),
            'paid_amount': Decimal('800.00'),
            'adjustment': Decimal('0.00'),
            'is_settled': False,
            'payments': [
                {'amount': Decimal('500.00'), 'method': PaymentMethod.CARD, 'operator': manager.id},
                {'amount': Decimal('300.00'), 'method': PaymentMethod.CASH, 'operator': front1.id}
            ]
        },
        # Checked out - 已结清
        {
            'stay_idx': 2,
            'total_amount': Decimal('1440.00'),
            'paid_amount': Decimal('1440.00'),
            'adjustment': Decimal('0.00'),
            'is_settled': True,
            'payments': [
                {'amount': Decimal('1440.00'), 'method': PaymentMethod.CARD, 'operator': manager.id}
            ]
        },
        # Another checked out - 有调整
        {
            'stay_idx': 3,
            'total_amount': Decimal('864.00'),
            'paid_amount': Decimal('800.00'),
            'adjustment': Decimal('-64.00'),  # 优惠
            'is_settled': True,
            'payments': [
                {'amount': Decimal('500.00'), 'method': PaymentMethod.CASH, 'operator': front1.id},
                {'amount': Decimal('300.00'), 'method': PaymentMethod.CASH, 'operator': front1.id}
            ]
        }
    ]

    created_bills = 0
    created_payments = 0
    stay_list = list(stay_records)

    for config in bills_config:
        if config['stay_idx'] >= len(stay_list):
            continue
        stay = stay_list[config['stay_idx']]

        existing = db.query(Bill).filter(Bill.stay_record_id == stay.id).first()
        if not existing:
            bill = Bill(
                stay_record_id=stay.id,
                total_amount=config['total_amount'],
                paid_amount=config['paid_amount'],
                adjustment_amount=config['adjustment'],
                is_settled=config['is_settled']
            )
            db.add(bill)
            db.flush()  # 获取 bill.id
            created_bills += 1

            # 创建支付记录
            for pay_config in config['payments']:
                payment = Payment(
                    bill_id=bill.id,
                    amount=pay_config['amount'],
                    method=pay_config['method'],
                    created_by=pay_config['operator']
                )
                db.add(payment)
                created_payments += 1

    db.commit()
    print(f"测试账单初始化完成: {created_bills} 条账单, {created_payments} 条支付")


def create_test_tasks(db, rooms, employees):
    """创建各种状态的任务"""
    cleaner1 = db.query(Employee).filter(Employee.username == 'cleaner1').first()
    cleaner2 = db.query(Employee).filter(Employee.username == 'cleaner2').first()
    manager = db.query(Employee).filter(Employee.username == 'manager').first()
    now = datetime.now()

    tasks_config = [
        # PENDING - 待分配清洁任务
        {
            'room_number': '202',
            'task_type': TaskType.CLEANING,
            'status': TaskStatus.PENDING,
            'priority': 2,
            'notes': '退房清洁',
            'assignee': None
        },
        # ASSIGNED - 已分配清洁任务
        {
            'room_number': '203',
            'task_type': TaskType.CLEANING,
            'status': TaskStatus.ASSIGNED,
            'priority': 1,
            'notes': '日常清洁',
            'assignee': cleaner1.id
        },
        # IN_PROGRESS - 进行中清洁任务
        {
            'room_number': '204',
            'task_type': TaskType.CLEANING,
            'status': TaskStatus.IN_PROGRESS,
            'priority': 2,
            'notes': '深度清洁',
            'assignee': cleaner1.id,
            'started_at': now - timedelta(minutes=30)
        },
        # COMPLETED - 已完成清洁任务
        {
            'room_number': '205',
            'task_type': TaskType.CLEANING,
            'status': TaskStatus.COMPLETED,
            'priority': 1,
            'notes': '日常清洁',
            'assignee': cleaner2.id,
            'started_at': now - timedelta(hours=2),
            'completed_at': now - timedelta(hours=1)
        },
        # PENDING - 维修任务
        {
            'room_number': '206',
            'task_type': TaskType.MAINTENANCE,
            'status': TaskStatus.PENDING,
            'priority': 3,
            'notes': '空调漏水',
            'assignee': None
        },
        # IN_PROGRESS - 维修任务
        {
            'room_number': '207',
            'task_type': TaskType.MAINTENANCE,
            'status': TaskStatus.IN_PROGRESS,
            'priority': 4,
            'notes': '更换灯泡',
            'assignee': cleaner2.id,
            'started_at': now - timedelta(minutes=15)
        }
    ]

    created = 0
    room_map = {r.room_number: r.id for r in rooms}

    for config in tasks_config:
        existing = db.query(Task).filter(
            Task.room_id == room_map[config['room_number']],
            Task.status == config['status']
        ).first()
        if not existing:
            task = Task(
                room_id=room_map[config['room_number']],
                task_type=config['task_type'],
                status=config['status'],
                priority=config['priority'],
                notes=config['notes'],
                assignee_id=config['assignee'],
                started_at=config.get('started_at'),
                completed_at=config.get('completed_at'),
                created_by=manager.id
            )
            db.add(task)
            created += 1

    db.commit()
    print(f"测试任务初始化完成: {created} 条")


def update_room_statuses(db, rooms):
    """更新房间状态以覆盖不同状态"""
    room_map = {r.room_number: r for r in rooms}

    status_updates = [
        ('201', RoomStatus.OCCUPIED),           # 入住中
        ('202', RoomStatus.VACANT_DIRTY),       # 待清洁
        ('203', RoomStatus.VACANT_DIRTY),       # 待清洁
        ('204', RoomStatus.OUT_OF_ORDER),       # 维修中
        ('205', RoomStatus.VACANT_CLEAN),       # 已清洁
        ('301', RoomStatus.OCCUPIED),           # 入住中
        ('302', RoomStatus.VACANT_CLEAN),       # 空闲
        ('303', RoomStatus.VACANT_DIRTY),       # 待清洁
    ]

    updated = 0
    for room_number, status in status_updates:
        if room_number in room_map:
            room = room_map[room_number]
            if room.status != status:
                room.status = status
                updated += 1

    db.commit()
    print(f"房间状态更新完成: {updated} 间")


def create_operation_snapshots(db, stay_records):
    """创建操作快照用于测试撤销功能"""
    from app.models.snapshots import OperationSnapshot, OperationType
    import uuid

    manager = db.query(Employee).filter(Employee.username == 'manager').first()
    stay_list = list(stay_records)

    # 获取一些用于测试的实体ID
    room = db.query(Room).first()
    task = db.query(Task).first()

    snapshots_config = [
        {
            'operation_type': OperationType.CHECK_IN,
            'entity_type': 'StayRecord',
            'entity_id': stay_list[0].id if stay_list else 1,
            'before': '{}',
            'after': '{"room_id": 1, "guest_id": 1}',
        },
        {
            'operation_type': OperationType.CHECK_OUT,
            'entity_type': 'StayRecord',
            'entity_id': stay_list[2].id if len(stay_list) > 2 else 2,
            'before': '{"status": "active"}',
            'after': '{"status": "checked_out"}',
        },
        {
            'operation_type': OperationType.EXTEND_STAY,
            'entity_type': 'StayRecord',
            'entity_id': stay_list[1].id if len(stay_list) > 1 else 1,
            'before': '{"expected_checkout": "2026-02-04"}',
            'after': '{"expected_checkout": "2026-02-05"}',
        },
        {
            'operation_type': OperationType.CHANGE_ROOM,
            'entity_type': 'StayRecord',
            'entity_id': stay_list[0].id if stay_list else 1,
            'before': '{"room_id": 1}',
            'after': f'{{"room_id": {room.id + 1 if room else 2}}}',
        },
        {
            'operation_type': OperationType.COMPLETE_TASK,
            'entity_type': 'Task',
            'entity_id': task.id if task else 1,
            'before': '{"status": "in_progress"}',
            'after': '{"status": "completed"}',
        },
        {
            'operation_type': OperationType.ADD_PAYMENT,
            'entity_type': 'Bill',
            'entity_id': 1,
            'before': '{"paid_amount": 500}',
            'after': '{"paid_amount": 800}',
        }
    ]

    created = 0
    now = datetime.now()
    for config in snapshots_config:
        snapshot = OperationSnapshot(
            snapshot_uuid=str(uuid.uuid4()),
            operation_type=config['operation_type'],
            entity_type=config['entity_type'],
            entity_id=config['entity_id'],
            before_state=config['before'],
            after_state=config['after'],
            operator_id=manager.id,
            expires_at=now + timedelta(hours=24),
            is_undone=False
        )
        db.add(snapshot)
        created += 1

    db.commit()
    print(f"操作快照初始化完成: {created} 条")


def create_security_events(db):
    """创建安全事件"""
    from app.models.security_events import (
        SecurityEventModel, SecurityEventType, SecurityEventSeverity
    )

    manager = db.query(Employee).filter(Employee.username == 'manager').first()
    cleaner1 = db.query(Employee).filter(Employee.username == 'cleaner1').first()

    security_events_config = [
        {
            'event_type': SecurityEventType.LOGIN_FAILED,
            'severity': SecurityEventSeverity.LOW,
            'description': '登录失败 - 错误密码',
            'source_ip': '192.168.1.100',
            'user_name': 'test',
            'details': '{"attempts": 3}'
        },
        {
            'event_type': SecurityEventType.LOGIN_SUCCESS,
            'severity': SecurityEventSeverity.LOW,
            'description': '用户登录成功',
            'source_ip': '192.168.1.101',
            'user_id': manager.id,
            'user_name': manager.name,
            'details': '{}'
        },
        {
            'event_type': SecurityEventType.UNUSUAL_TIME_ACCESS,
            'severity': SecurityEventSeverity.MEDIUM,
            'description': '异常操作 - 非工作时间访问',
            'source_ip': '192.168.1.102',
            'user_id': manager.id,
            'user_name': manager.name,
            'details': '{"action": "export_guests", "time": "02:30"}'
        },
        {
            'event_type': SecurityEventType.UNAUTHORIZED_ACCESS,
            'severity': SecurityEventSeverity.MEDIUM,
            'description': '权限拒绝 - 尝试访问管理功能',
            'source_ip': '192.168.1.103',
            'user_id': cleaner1.id if cleaner1 else None,
            'user_name': cleaner1.name if cleaner1 else 'cleaner1',
            'details': '{"action": "delete_bill"}'
        },
        {
            'event_type': SecurityEventType.MULTIPLE_LOGIN_FAILURES,
            'severity': SecurityEventSeverity.HIGH,
            'description': '多次登录失败 - 超过阈值',
            'source_ip': '192.168.1.105',
            'details': '{"attempts": 5, "window_minutes": 3}'
        },
        {
            'event_type': SecurityEventType.SENSITIVE_DATA_ACCESS,
            'severity': SecurityEventSeverity.MEDIUM,
            'description': '访问敏感数据 - 查看黑名单',
            'source_ip': '192.168.1.106',
            'user_id': manager.id,
            'user_name': manager.name,
            'details': '{"resource": "blacklist"}'
        },
        {
            'event_type': SecurityEventType.BULK_DATA_EXPORT,
            'severity': SecurityEventSeverity.HIGH,
            'description': '批量数据导出 - 导出所有客人信息',
            'source_ip': '192.168.1.107',
            'user_id': manager.id,
            'user_name': manager.name,
            'details': '{"records": 50, "format": "csv"}'
        }
    ]

    created = 0
    for config in security_events_config:
        existing = db.query(SecurityEventModel).filter(
            SecurityEventModel.event_type == config['event_type']
        ).first()
        if not existing:
            event = SecurityEventModel(
                event_type=config['event_type'],
                severity=config['severity'],
                description=config['description'],
                source_ip=config['source_ip'],
                user_id=config.get('user_id'),
                user_name=config.get('user_name'),
                details=config['details']
            )
            db.add(event)
            created += 1

    db.commit()
    print(f"安全事件初始化完成: {created} 条")


def print_event_coverage():
    """打印事件覆盖情况"""
    print("\n" + "=" * 60)
    print("领域事件覆盖情况")
    print("=" * 60)

    events = {
        "房间相关": [
            EventType.ROOM_STATUS_CHANGED,
            EventType.ROOM_CREATED,
            EventType.ROOM_UPDATED,
        ],
        "入住相关": [
            EventType.GUEST_CHECKED_IN,
            EventType.GUEST_CHECKED_OUT,
            EventType.STAY_EXTENDED,
            EventType.ROOM_CHANGED,
        ],
        "预订相关": [
            EventType.RESERVATION_CREATED,
            EventType.RESERVATION_CANCELLED,
            EventType.RESERVATION_CONFIRMED,
        ],
        "任务相关": [
            EventType.TASK_CREATED,
            EventType.TASK_ASSIGNED,
            EventType.TASK_STARTED,
            EventType.TASK_COMPLETED,
        ],
        "账单相关": [
            EventType.BILL_CREATED,
            EventType.PAYMENT_RECEIVED,
            EventType.BILL_ADJUSTED,
        ],
        "操作相关": [
            EventType.OPERATION_EXECUTED,
            EventType.OPERATION_UNDONE,
        ],
        "安全相关": [
            EventType.SECURITY_EVENT,
        ]
    }

    total = 0
    for category, event_list in events.items():
        print(f"\n{category}:")
        for event in event_list:
            print(f"  ✓ {event.value}")
            total += 1

    print(f"\n总计: {total} 种事件类型")
    print("=" * 60)


def print_test_scenarios():
    """打印测试场景说明"""
    print("\n" + "=" * 60)
    print("测试场景说明")
    print("=" * 60)

    scenarios = [
        ("房间状态", "VACANT_CLEAN / OCCUPIED / VACANT_DIRTY / OUT_OF_ORDER"),
        ("预订状态", "CONFIRMED / CHECKED_IN / COMPLETED / CANCELLED / NO_SHOW"),
        ("住宿记录", "ACTIVE 在住 / CHECKED_OUT 已退房"),
        ("任务状态", "PENDING / ASSIGNED / IN_PROGRESS / COMPLETED"),
        ("任务类型", "CLEANING / MAINTENANCE"),
        ("支付方式", "CASH / CARD"),
        ("客户等级", "normal / silver / gold / platinum / 黑名单"),
        ("账单状态", "已结清 / 未结清 / 有调整"),
    ]

    for title, desc in scenarios:
        print(f"  {title}: {desc}")

    print("=" * 60)


def main():
    """主函数"""
    print("=" * 60)
    print("AIPMS 事件测试数据初始化")
    print("=" * 60)

    # 初始化数据库
    init_db()
    print("数据库表创建完成")

    # 注册事件处理器
    register_event_handlers()
    print("事件处理器注册完成")

    # 创建会话
    db = SessionLocal()

    try:
        # 获取基础数据
        room_types = db.query(RoomType).all()
        if not room_types:
            print("错误: 请先运行 init_data.py 初始化基础数据")
            return

        rooms = db.query(Room).all()
        employees = db.query(Employee).all()

        # 初始化测试数据
        print("\n开始初始化测试数据...")

        guests = init_additional_guests(db)
        reservations = create_test_reservations(db, guests, room_types)
        stay_records = create_test_stay_records(db, guests, rooms)
        create_test_bills_and_payments(db, stay_records)
        create_test_tasks(db, rooms, employees)
        update_room_statuses(db, rooms)
        create_operation_snapshots(db, stay_records)
        create_security_events(db)

        # 打印信息
        print("\n" + "=" * 60)
        print("数据统计")
        print("=" * 60)
        print(f"  客人: {db.query(Guest).count()} 人")
        print(f"  预订: {db.query(Reservation).count()} 条")
        print(f"  住宿记录: {db.query(StayRecord).count()} 条")
        print(f"  账单: {db.query(Bill).count()} 条")
        print(f"  支付: {db.query(Payment).count()} 条")
        print(f"  任务: {db.query(Task).count()} 条")
        print(f"  房间: {db.query(Room).count()} 间")
        print(f"  员工: {db.query(Employee).count()} 人")

        print_event_coverage()
        print_test_scenarios()

        print("\n" + "=" * 60)
        print("测试数据初始化完成！")
        print("=" * 60)
        print("\n可以通过以下方式测试事件:")
        print("  1. 完成清洁任务 → 触发 TASK_COMPLETED → 房间状态更新")
        print("  2. 客人退房 → 触发 GUEST_CHECKED_OUT → 创建清洁任务")
        print("  3. 客人换房 → 触发 ROOM_CHANGED → 原房间创建清洁任务")
        print("  4. 查看事件历史: GET /debug/events")
        print("  5. 查看操作快照: GET /undo/operations")
        print("=" * 60)

    finally:
        db.close()


if __name__ == '__main__':
    main()
