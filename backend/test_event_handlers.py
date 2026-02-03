"""
事件处理器功能测试脚本
演示如何触发各种领域事件并验证事件处理器的响应
"""
import sys
sys.path.insert(0, '.')

from datetime import date, datetime, timedelta
from decimal import Decimal

from app.database import SessionLocal, init_db
from app.models.ontology import (
    Room, RoomStatus, Guest, StayRecord, StayRecordStatus,
    Task, TaskType, TaskStatus, Bill, Payment, PaymentMethod, Employee
)
from app.services.event_bus import event_bus, Event
from app.services.event_handlers import register_event_handlers
from app.models.events import EventType
from app.models.snapshots import OperationSnapshot
from app.models.security_events import SecurityEventModel


def print_section(title):
    """打印分隔标题"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def test_event_history():
    """测试1: 查看事件历史"""
    print_section("测试1: 查看事件历史")

    history = event_bus.get_history(limit=20)
    print(f"事件历史记录 (最近20条):")
    for event in history[:10]:
        print(f"  [{event.timestamp.strftime('%H:%M:%S')}] {event.event_type} - {event.source}")


def test_guest_checkout_creates_task(db):
    """测试2: 退房事件自动创建清洁任务"""
    print_section("测试2: 退房事件 → 自动创建清洁任务")

    # 获取一个入住中的房间
    active_stay = db.query(StayRecord).filter(
        StayRecord.status == StayRecordStatus.ACTIVE
    ).first()

    if not active_stay:
        print("没有找到在住记录，跳过测试")
        return

    print(f"测试房间: {active_stay.room.room_number}")
    print(f"当前住客: {active_stay.guest.name}")

    # 获取操作员
    manager = db.query(Employee).filter(Employee.username == 'manager').first()

    # 模拟退房事件
    task_count_before = db.query(Task).filter(
        Task.room_id == active_stay.room_id,
        Task.task_type == TaskType.CLEANING
    ).count()

    checkout_event = Event(
        event_type=EventType.GUEST_CHECKED_OUT,
        timestamp=datetime.now(),
        data={
            'room_id': active_stay.room_id,
            'room_number': active_stay.room.room_number,
            'guest_name': active_stay.guest.name,
            'operator_id': manager.id
        },
        source='test_script'
    )

    event_bus.publish(checkout_event)

    task_count_after = db.query(Task).filter(
        Task.room_id == active_stay.room_id,
        Task.task_type == TaskType.CLEANING
    ).count()

    print(f"退房前清洁任务数: {task_count_before}")
    print(f"退房后清洁任务数: {task_count_after}")
    print(f"✓ 事件处理器响应: {'成功' if task_count_after > task_count_before else '失败'}")


def test_task_completed_updates_room(db):
    """测试3: 任务完成事件更新房间状态"""
    print_section("测试3: 任务完成 → 房间状态更新")

    # 找一个待清洁的房间
    dirty_room = db.query(Room).filter(
        Room.status == RoomStatus.VACANT_DIRTY
    ).first()

    if not dirty_room:
        print("没有找到脏房，创建一个测试场景")
        # 创建一个清洁任务
        clean_room = db.query(Room).filter(
            Room.status == RoomStatus.VACANT_CLEAN
        ).first()
        if clean_room:
            cleaner = db.query(Employee).filter(Employee.username == 'cleaner1').first()
            manager = db.query(Employee).filter(Employee.username == 'manager').first()

            task = Task(
                room_id=clean_room.id,
                task_type=TaskType.CLEANING,
                status=TaskStatus.PENDING,
                priority=1,
                notes='测试清洁任务',
                created_by=manager.id
            )
            db.add(task)
            db.flush()

            # 分配任务
            task.assignee_id = cleaner.id
            task.status = TaskStatus.ASSIGNED

            # 开始任务
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now()

            # 先把房间设为脏房
            clean_room.status = RoomStatus.VACANT_DIRTY
            db.commit()
            dirty_room = clean_room

    if not dirty_room:
        print("无法创建测试场景，跳过测试")
        return

    print(f"测试房间: {dirty_room.room_number}")
    print(f"当前状态: {dirty_room.status}")

    # 模拟任务完成事件
    task_completed_event = Event(
        event_type=EventType.TASK_COMPLETED,
        timestamp=datetime.now(),
        data={
            'room_id': dirty_room.id,
            'room_number': dirty_room.room_number,
            'task_type': 'cleaning'
        },
        source='test_script'
    )

    db.refresh(dirty_room)
    status_before = dirty_room.status

    event_bus.publish(task_completed_event)

    db.refresh(dirty_room)
    status_after = dirty_room.status

    print(f"任务完成前状态: {status_before}")
    print(f"任务完成后状态: {status_after}")
    print(f"✓ 状态更新成功: {'是' if status_after == RoomStatus.VACANT_CLEAN else '否'}")


def test_room_changed_creates_task(db):
    """测试4: 换房事件为原房间创建清洁任务"""
    print_section("测试4: 换房事件 → 原房间创建清洁任务")

    # 获取两个房间
    room1 = db.query(Room).filter(Room.status == RoomStatus.OCCUPIED).first()
    room2 = db.query(Room).filter(Room.status == RoomStatus.VACANT_CLEAN).first()
    manager = db.query(Employee).filter(Employee.username == 'manager').first()

    if not room1 or not room2:
        print("没有找到合适的房间，跳过测试")
        return

    print(f"原房间: {room1.room_number}")
    print(f"新房间: {room2.room_number}")

    task_count_before = db.query(Task).filter(
        Task.room_id == room1.id,
        Task.task_type == TaskType.CLEANING
    ).count()

    # 模拟换房事件
    room_changed_event = Event(
        event_type=EventType.ROOM_CHANGED,
        timestamp=datetime.now(),
        data={
            'old_room_id': room1.id,
            'old_room_number': room1.room_number,
            'new_room_id': room2.id,
            'new_room_number': room2.room_number,
            'guest_name': '测试客人',
            'operator_id': manager.id
        },
        source='test_script'
    )

    event_bus.publish(room_changed_event)

    task_count_after = db.query(Task).filter(
        Task.room_id == room1.id,
        Task.task_type == TaskType.CLEANING
    ).count()

    print(f"换房前原房间清洁任务数: {task_count_before}")
    print(f"换房后原房间清洁任务数: {task_count_after}")
    print(f"✓ 事件处理器响应: {'成功' if task_count_after > task_count_before else '失败'}")


def test_operation_snapshots(db):
    """测试5: 查看操作快照"""
    print_section("测试5: 查看操作快照")

    snapshots = db.query(OperationSnapshot).filter(
        OperationSnapshot.is_undone == False
    ).order_by(OperationSnapshot.created_at.desc()).limit(10).all()

    print(f"可撤销的操作 ({len(snapshots)} 条):")
    for snap in snapshots:
        expired = "已过期" if snap.expires_at < datetime.now() else "有效"
        print(f"  [{snap.created_at.strftime('%m-%d %H:%M')}] "
              f"{snap.operation_type} - {snap.entity_type}:{snap.entity_id} ({expired})")


def test_security_events(db):
    """测试6: 查看安全事件"""
    print_section("测试6: 查看安全事件")

    events = db.query(SecurityEventModel).order_by(
        SecurityEventModel.timestamp.desc()
    ).limit(10).all()

    print(f"安全事件记录 ({len(events)} 条):")
    for event in events:
        acknowledged = "已确认" if event.is_acknowledged else "未确认"
        print(f"  [{event.timestamp.strftime('%m-%d %H:%M')}] "
              f"{event.event_type} ({event.severity}) - {event.description} [{acknowledged}]")


def test_database_statistics(db):
    """测试7: 数据库统计"""
    print_section("测试7: 数据库统计")

    stats = {
        "客人总数": db.query(Guest).count(),
        "在住记录": db.query(StayRecord).filter(StayRecord.status == StayRecordStatus.ACTIVE).count(),
        "已退房记录": db.query(StayRecord).filter(StayRecord.status == StayRecordStatus.CHECKED_OUT).count(),
        "待处理任务": db.query(Task).filter(Task.status == TaskStatus.PENDING).count(),
        "进行中任务": db.query(Task).filter(Task.status == TaskStatus.IN_PROGRESS).count(),
        "空闲干净房": db.query(Room).filter(Room.status == RoomStatus.VACANT_CLEAN).count(),
        "入住中": db.query(Room).filter(Room.status == RoomStatus.OCCUPIED).count(),
        "待清洁": db.query(Room).filter(Room.status == RoomStatus.VACANT_DIRTY).count(),
        "维修中": db.query(Room).filter(Room.status == RoomStatus.OUT_OF_ORDER).count(),
    }

    for key, value in stats.items():
        print(f"  {key}: {value}")


def print_event_testing_guide():
    """打印事件测试指南"""
    print_section("事件测试指南")

    guide = """
通过API可以触发以下事件进行测试:

1. 退房事件 (GUEST_CHECKED_OUT):
   POST /checkout/{stay_record_id}
   → 自动创建清洁任务

2. 任务完成事件 (TASK_COMPLETED):
   PUT /tasks/{task_id}/complete
   → 房间状态从 VACANT_DIRTY 变为 VACANT_CLEAN

3. 换房事件 (ROOM_CHANGED):
   POST /checkin/change-room
   → 原房间创建清洁任务

4. 预订创建事件 (RESERVATION_CREATED):
   POST /reservations
   → 创建预订记录

5. 支付事件 (PAYMENT_RECEIVED):
   POST /billing/{bill_id}/payments
   → 更新账单已付金额

事件历史查询:
   GET /debug/events - 查看事件总线历史
   GET /undo/operations - 查看可撤销操作
   GET /security/events - 查看安全事件
"""
    print(guide)


def main():
    """主函数"""
    print("=" * 60)
    print("AIPMS 事件处理器功能测试")
    print("=" * 60)

    # 注册事件处理器
    register_event_handlers()
    print("事件处理器已注册")

    db = SessionLocal()

    try:
        # 运行测试
        test_event_history()
        test_database_statistics(db)
        test_guest_checkout_creates_task(db)
        test_task_completed_updates_room(db)
        test_room_changed_creates_task(db)
        test_operation_snapshots(db)
        test_security_events(db)

        print_event_testing_guide()

        print("\n" + "=" * 60)
        print("测试完成！")
        print("=" * 60)

    finally:
        db.close()


if __name__ == '__main__':
    main()
