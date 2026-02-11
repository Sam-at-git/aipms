"""
退房管理 API 单元测试
覆盖 /checkout 端点的所有功能
"""
import pytest
from datetime import date, timedelta, datetime
from fastapi.testclient import TestClient
from decimal import Decimal


class TestExecuteCheckout:
    """执行退房测试"""

    def test_checkout_success(self, client: TestClient, receptionist_auth_headers, db_session):
        """测试成功退房"""
        from app.models.ontology import (
            StayRecord, StayRecordStatus, Room, RoomType, Guest,
            RoomStatus, Bill
        )

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="101", floor=1, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
        db_session.add(room)
        guest = Guest(name="张三", phone="13800138000")
        db_session.add(guest)
        db_session.commit()

        stay = StayRecord(
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now() - timedelta(days=2),
            expected_check_out=date.today(),
            status=StayRecordStatus.ACTIVE
        )
        db_session.add(stay)
        db_session.commit()
        db_session.refresh(stay)

        # 创建账单 - 已全额支付
        bill = Bill(
            stay_record_id=stay.id,
            total_amount=Decimal("576.00"),
            paid_amount=Decimal("576.00"),
            is_settled=True
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(stay)

        response = client.post("/checkout", headers=receptionist_auth_headers, json={
            "stay_record_id": stay.id
        })

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        # 验证房间状态变为脏房
        db_session.refresh(room)
        assert room.status == RoomStatus.VACANT_DIRTY

    def test_checkout_not_found(self, client: TestClient, receptionist_auth_headers):
        """测试退房不存在的记录"""
        response = client.post("/checkout", headers=receptionist_auth_headers, json={
            "stay_record_id": 99999
        })

        assert response.status_code == 400

    def test_checkout_already_checked_out(self, client: TestClient, receptionist_auth_headers, db_session):
        """测试退已退房的记录"""
        from app.models.ontology import StayRecord, StayRecordStatus, Room, RoomType, Guest, RoomStatus

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="102", floor=1, room_type_id=room_type.id, status=RoomStatus.VACANT_DIRTY)
        db_session.add(room)
        guest = Guest(name="李四", phone="13900139000")
        db_session.add(guest)
        db_session.commit()

        stay = StayRecord(
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now() - timedelta(days=3),
            check_out_time=datetime.now() - timedelta(days=1),
            expected_check_out=date.today() - timedelta(days=1),
            status=StayRecordStatus.CHECKED_OUT
        )
        db_session.add(stay)
        db_session.commit()

        response = client.post("/checkout", headers=receptionist_auth_headers, json={
            "stay_record_id": stay.id
        })

        assert response.status_code == 400

    def test_checkout_creates_cleaning_task(self, client: TestClient, receptionist_auth_headers, db_session, test_event_bus):
        """测试退房后自动创建清洁任务"""
        from app.models.ontology import (
            StayRecord, StayRecordStatus, Room, RoomType, Guest,
            RoomStatus, Bill, Task, TaskType, TaskStatus
        )

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="301", floor=3, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
        db_session.add(room)
        guest = Guest(name="王五", phone="13700137000")
        db_session.add(guest)
        db_session.commit()

        stay = StayRecord(
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now() - timedelta(days=1),
            expected_check_out=date.today(),
            status=StayRecordStatus.ACTIVE
        )
        db_session.add(stay)
        db_session.commit()

        bill = Bill(
            stay_record_id=stay.id,
            total_amount=Decimal("288.00"),
            paid_amount=Decimal("288.00"),
            is_settled=True
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(stay)

        response = client.post("/checkout", headers=receptionist_auth_headers, json={
            "stay_record_id": stay.id
        })

        assert response.status_code == 200

        # Verify cleaning task was auto-created by event handler
        cleaning_task = db_session.query(Task).filter(
            Task.room_id == room.id,
            Task.task_type == TaskType.CLEANING
        ).first()
        assert cleaning_task is not None
        assert cleaning_task.status == TaskStatus.PENDING


class TestOverdueList:
    """逾期离店列表测试"""

    def test_get_overdue_stays(self, client: TestClient, manager_auth_headers, db_session):
        """测试获取逾期离店列表"""
        from app.models.ontology import StayRecord, StayRecordStatus, Room, RoomType, Guest, RoomStatus

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="301", floor=3, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
        db_session.add(room)
        guest = Guest(name="赵六", phone="13600136000")
        db_session.add(guest)
        db_session.commit()

        # 创建逾期记录（预期退房日期是昨天）
        stay = StayRecord(
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now() - timedelta(days=3),
            expected_check_out=date.today() - timedelta(days=1),
            status=StayRecordStatus.ACTIVE
        )
        db_session.add(stay)
        db_session.commit()

        response = client.get("/checkout/overdue", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1


class TestGetBillInfo:
    """获取账单信息测试"""

    def test_get_bill_by_stay_id(self, client: TestClient, manager_auth_headers, db_session):
        """测试通过住宿记录获取账单"""
        from app.models.ontology import (
            StayRecord, StayRecordStatus, Room, RoomType, Guest,
            RoomStatus, Bill
        )

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="401", floor=4, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
        db_session.add(room)
        guest = Guest(name="孙七", phone="13500135000")
        db_session.add(guest)
        db_session.commit()

        stay = StayRecord(
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now() - timedelta(days=2),
            expected_check_out=date.today(),
            status=StayRecordStatus.ACTIVE
        )
        db_session.add(stay)
        db_session.commit()

        bill = Bill(
            stay_record_id=stay.id,
            total_amount=Decimal("576.00"),
            paid_amount=Decimal("200.00"),
            is_settled=False
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(stay)

        # 使用 billing 端点而不是 checkout 端点
        response = client.get(f"/billing/stay/{stay.id}", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_amount"] == "576.00"

    def test_get_bill_stay_not_found(self, client: TestClient, manager_auth_headers):
        """测试获取不存在记录的账单"""
        # 使用 billing 端点而不是 checkout 端点
        response = client.get("/billing/stay/99999", headers=manager_auth_headers)

        assert response.status_code == 404


class TestCheckoutAutoRoomStatusChange:
    """退房自动状态变更测试"""

    def test_checkout_room_status_changes(self, client: TestClient, receptionist_auth_headers, db_session):
        """测试退房后房间状态自动变更流程"""
        from app.models.ontology import (
            StayRecord, StayRecordStatus, Room, RoomType, Guest,
            RoomStatus, Bill
        )

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()

        # 初始状态：OCCUPIED
        room = Room(room_number="501", floor=5, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
        db_session.add(room)
        guest = Guest(name="周八", phone="13400134000")
        db_session.add(guest)
        db_session.commit()

        stay = StayRecord(
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now() - timedelta(days=1),
            expected_check_out=date.today(),
            status=StayRecordStatus.ACTIVE
        )
        db_session.add(stay)
        db_session.commit()

        bill = Bill(
            stay_record_id=stay.id,
            total_amount=Decimal("288.00"),
            paid_amount=Decimal("288.00"),
            is_settled=True
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(stay)

        # 确认初始状态
        db_session.refresh(room)
        assert room.status == RoomStatus.OCCUPIED

        # 执行退房
        response = client.post("/checkout", headers=receptionist_auth_headers, json={
            "stay_record_id": stay.id
        })
        assert response.status_code == 200

        # 验证状态变为 VACANT_DIRTY
        db_session.refresh(room)
        assert room.status == RoomStatus.VACANT_DIRTY


class TestCheckoutWithPayment:
    """退房支付测试"""

    def test_checkout_with_partial_payment(self, client: TestClient, receptionist_auth_headers, db_session):
        """测试部分支付退房（需要挂账）"""
        from app.models.ontology import (
            StayRecord, StayRecordStatus, Room, RoomType, Guest,
            RoomStatus, Bill
        )

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="601", floor=6, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
        db_session.add(room)
        guest = Guest(name="吴九", phone="13300133000")
        db_session.add(guest)
        db_session.commit()

        stay = StayRecord(
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now() - timedelta(days=1),
            expected_check_out=date.today(),
            status=StayRecordStatus.ACTIVE
        )
        db_session.add(stay)
        db_session.commit()

        bill = Bill(
            stay_record_id=stay.id,
            total_amount=Decimal("288.00"),
            paid_amount=Decimal("100.00"),  # 只付了部分
            is_settled=False
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(stay)

        # 挂账退房（允许未结清）
        response = client.post("/checkout", headers=receptionist_auth_headers, json={
            "stay_record_id": stay.id,
            "allow_unsettled": True,
            "unsettled_reason": "客人承诺稍后支付"
        })

        assert response.status_code == 200

        # 验证账单状态
        db_session.refresh(bill)
        assert not bill.is_settled  # 未结清
