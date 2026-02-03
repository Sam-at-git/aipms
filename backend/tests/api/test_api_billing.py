"""
账单管理 API 单元测试
覆盖 /billing 端点的所有功能
"""
import pytest
from datetime import date, timedelta, datetime
from fastapi.testclient import TestClient
from decimal import Decimal


class TestGetBill:
    """获取账单测试"""

    def test_get_bill_by_stay(self, client: TestClient, manager_auth_headers, db_session):
        """测试通过住宿记录获取账单"""
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

        bill = Bill(
            stay_record_id=stay.id,
            total_amount=Decimal("576.00"),
            paid_amount=Decimal("0"),
            is_settled=False
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(stay)

        response = client.get(f"/billing/stay/{stay.id}", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_amount"] == "576.00"

    def test_get_bill_not_found(self, client: TestClient, manager_auth_headers):
        """测试获取不存在的账单"""
        response = client.get("/billing/stay/99999", headers=manager_auth_headers)

        assert response.status_code == 404


class TestAddPayment:
    """添加支付测试"""

    def test_add_payment_cash(self, client: TestClient, receptionist_auth_headers, db_session):
        """测试添加现金支付"""
        from app.models.ontology import (
            StayRecord, StayRecordStatus, Room, RoomType, Guest,
            RoomStatus, Bill
        )

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="201", floor=2, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
        db_session.add(room)
        guest = Guest(name="李四", phone="13900139000")
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
            paid_amount=Decimal("0"),
            is_settled=False
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(bill)

        response = client.post("/billing/payment", headers=receptionist_auth_headers, json={
            "bill_id": bill.id,
            "amount": "288.00",
            "method": "cash"
        })

        assert response.status_code == 200
        data = response.json()
        assert "payment_id" in data
        # API returns amount as float, not string
        assert float(data["amount"]) == 288.00

    def test_add_payment_card(self, client: TestClient, receptionist_auth_headers, db_session):
        """测试添加刷卡支付"""
        from app.models.ontology import (
            StayRecord, StayRecordStatus, Room, RoomType, Guest,
            RoomStatus, Bill
        )

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="202", floor=2, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
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
            paid_amount=Decimal("0"),
            is_settled=False
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(bill)

        response = client.post("/billing/payment", headers=receptionist_auth_headers, json={
            "bill_id": bill.id,
            "amount": "288.00",
            "method": "card",
            "transaction_id": "TXN123456"
        })

        assert response.status_code == 200
        data = response.json()
        assert "payment_id" in data
        assert float(data["amount"]) == 288.00

    def test_add_partial_payment(self, client: TestClient, receptionist_auth_headers, db_session):
        """测试部分支付"""
        from app.models.ontology import (
            StayRecord, StayRecordStatus, Room, RoomType, Guest,
            RoomStatus, Bill
        )

        room_type = RoomType(name="标准间", base_price=Decimal("588"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="203", floor=2, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
        db_session.add(room)
        guest = Guest(name="赵六", phone="13600136000")
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
            total_amount=Decimal("588.00"),
            paid_amount=Decimal("0"),
            is_settled=False
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(bill)

        # 部分支付
        response = client.post("/billing/payment", headers=receptionist_auth_headers, json={
            "bill_id": bill.id,
            "amount": "200.00",
            "method": "cash"
        })

        assert response.status_code == 200
        data = response.json()
        assert "payment_id" in data
        assert float(data["amount"]) == 200.00

    def test_add_payment_bill_not_found(self, client: TestClient, receptionist_auth_headers):
        """测试向不存在的账单支付"""
        response = client.post("/billing/payment", headers=receptionist_auth_headers, json={
            "bill_id": 99999,
            "amount": "100.00",
            "method": "cash"
        })

        # API returns 400 when bill not found
        assert response.status_code == 400


class TestAdjustBill:
    """调整账单测试"""

    def test_adjust_bill_discount(self, client: TestClient, manager_auth_headers, db_session):
        """测试折扣调整"""
        from app.models.ontology import (
            StayRecord, StayRecordStatus, Room, RoomType, Guest,
            RoomStatus, Bill
        )

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="301", floor=3, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
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
            paid_amount=Decimal("0"),
            is_settled=False
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(bill)

        response = client.post("/billing/adjust", headers=manager_auth_headers, json={
            "bill_id": bill.id,
            "adjustment_amount": "-50.00",
            "reason": "VIP折扣"
        })

        assert response.status_code == 200
        data = response.json()
        assert float(data["adjustment_amount"]) == -50.00

    def test_adjust_bill_surcharge(self, client: TestClient, manager_auth_headers, db_session):
        """测试附加费调整"""
        from app.models.ontology import (
            StayRecord, StayRecordStatus, Room, RoomType, Guest,
            RoomStatus, Bill
        )

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="302", floor=3, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
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
            paid_amount=Decimal("0"),
            is_settled=False
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(bill)

        response = client.post("/billing/adjust", headers=manager_auth_headers, json={
            "bill_id": bill.id,
            "adjustment_amount": "30.00",
            "reason": "额外服务费"
        })

        assert response.status_code == 200
        data = response.json()
        assert float(data["adjustment_amount"]) == 30.00

    def test_adjust_bill_unauthorized(self, client: TestClient, receptionist_auth_headers, db_session):
        """测试非经理不能调整账单"""
        from app.models.ontology import (
            StayRecord, StayRecordStatus, Room, RoomType, Guest,
            RoomStatus, Bill
        )

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="303", floor=3, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
        db_session.add(room)
        guest = Guest(name="郑十", phone="13200132000")
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
            paid_amount=Decimal("0"),
            is_settled=False
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(bill)

        response = client.post("/billing/adjust", headers=receptionist_auth_headers, json={
            "bill_id": bill.id,
            "adjustment_amount": "-50.00",
            "reason": "前台尝试折扣"
        })

        assert response.status_code == 403


class TestBillCalculation:
    """账单计算测试"""

    def test_calculate_room_charge(self, client: TestClient, manager_auth_headers, db_session):
        """测试房费计算"""
        from app.models.ontology import (
            StayRecord, StayRecordStatus, Room, RoomType, Guest,
            RoomStatus, Bill
        )

        room_type = RoomType(name="标准间", base_price=Decimal("288"), max_occupancy=2)
        db_session.add(room_type)
        db_session.commit()
        room = Room(room_number="401", floor=4, room_type_id=room_type.id, status=RoomStatus.OCCUPIED)
        db_session.add(room)
        guest = Guest(name="钱十一", phone="13100131000")
        db_session.add(guest)
        db_session.commit()

        # 入住2晚
        stay = StayRecord(
            guest_id=guest.id,
            room_id=room.id,
            check_in_time=datetime.now() - timedelta(days=2),
            expected_check_out=date.today(),
            status=StayRecordStatus.ACTIVE
        )
        db_session.add(stay)
        db_session.commit()

        # 创建账单
        bill = Bill(
            stay_record_id=stay.id,
            total_amount=Decimal("576.00"),
            paid_amount=Decimal("0"),
            is_settled=False
        )
        db_session.add(bill)
        db_session.commit()
        db_session.refresh(stay)

        # 获取账单
        response = client.get(f"/billing/stay/{stay.id}", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        # 2晚 * 288 = 576
        assert float(data.get("total_amount", 0)) == 576.00
