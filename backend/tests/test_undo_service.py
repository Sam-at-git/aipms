"""
撤销服务单元测试
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
import json

from app.services.undo_service import UndoService, create_checkin_snapshot
from app.models.snapshots import OperationSnapshot, OperationType
from app.models.ontology import (
    StayRecord, StayRecordStatus, Room, RoomStatus,
    Reservation, ReservationStatus, Task, TaskStatus, Bill
)


class TestUndoService:
    """撤销服务测试"""

    @pytest.fixture
    def undo_service(self, db_session):
        """创建撤销服务实例"""
        mock_publisher = MagicMock()
        return UndoService(db_session, event_publisher=mock_publisher)

    def test_create_snapshot(self, undo_service, sample_employee):
        """测试创建快照"""
        snapshot = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={"room": {"status": "vacant_clean"}},
            after_state={"room": {"status": "occupied"}},
            operator_id=sample_employee.id
        )

        assert snapshot is not None
        assert snapshot.snapshot_uuid is not None
        assert snapshot.operation_type == "check_in"
        assert snapshot.entity_type == "stay_record"
        assert snapshot.entity_id == 1
        assert not snapshot.is_undone

    def test_get_snapshot(self, undo_service, sample_employee):
        """测试获取快照"""
        created = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=sample_employee.id
        )

        found = undo_service.get_snapshot(created.snapshot_uuid)
        assert found is not None
        assert found.id == created.id

    def test_get_undoable_operations(self, undo_service, sample_employee):
        """测试获取可撤销操作列表"""
        # 创建多个快照
        for i in range(3):
            undo_service.create_snapshot(
                operation_type=OperationType.CHECK_IN,
                entity_type="stay_record",
                entity_id=i,
                before_state={},
                after_state={},
                operator_id=sample_employee.id
            )

        operations = undo_service.get_undoable_operations()
        assert len(operations) == 3

    def test_get_undoable_operations_filter_by_entity(self, undo_service, sample_employee):
        """测试按实体筛选可撤销操作"""
        undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=sample_employee.id
        )
        undo_service.create_snapshot(
            operation_type=OperationType.COMPLETE_TASK,
            entity_type="task",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=sample_employee.id
        )

        operations = undo_service.get_undoable_operations(entity_type="stay_record")
        assert len(operations) == 1
        assert operations[0].entity_type == "stay_record"

    def test_can_undo_valid_snapshot(self, undo_service, sample_employee):
        """测试有效快照可以撤销"""
        snapshot = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=sample_employee.id
        )

        can_undo, reason = undo_service.can_undo(snapshot)
        assert can_undo
        assert reason == ""

    def test_can_undo_already_undone(self, undo_service, db_session, sample_employee):
        """测试已撤销的快照不能再撤销"""
        snapshot = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=sample_employee.id
        )
        snapshot.is_undone = True
        db_session.commit()

        can_undo, reason = undo_service.can_undo(snapshot)
        assert not can_undo
        assert "已撤销" in reason

    def test_can_undo_expired(self, undo_service, db_session, sample_employee):
        """测试过期快照不能撤销"""
        snapshot = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=1,
            before_state={},
            after_state={},
            operator_id=sample_employee.id
        )
        snapshot.expires_at = datetime.now() - timedelta(hours=1)
        db_session.commit()

        can_undo, reason = undo_service.can_undo(snapshot)
        assert not can_undo
        assert "过期" in reason

    def test_can_undo_none_snapshot(self, undo_service):
        """测试空快照"""
        can_undo, reason = undo_service.can_undo(None)
        assert not can_undo
        assert "不存在" in reason


class TestUndoServiceRollback:
    """撤销服务回滚测试"""

    @pytest.fixture
    def undo_service(self, db_session):
        """创建撤销服务实例"""
        mock_publisher = MagicMock()
        return UndoService(db_session, event_publisher=mock_publisher)

    def test_undo_checkin(self, undo_service, db_session, sample_room, sample_guest, sample_employee):
        """测试撤销入住"""
        from decimal import Decimal

        # 创建入住记录
        stay_record = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=sample_employee.id
        )
        db_session.add(stay_record)
        db_session.flush()

        bill = Bill(
            stay_record_id=stay_record.id,
            total_amount=Decimal("288.00")
        )
        db_session.add(bill)

        sample_room.status = RoomStatus.OCCUPIED
        db_session.commit()

        # 创建快照
        snapshot = undo_service.create_snapshot(
            operation_type=OperationType.CHECK_IN,
            entity_type="stay_record",
            entity_id=stay_record.id,
            before_state={
                "room": {
                    "id": sample_room.id,
                    "room_number": sample_room.room_number,
                    "status": "vacant_clean"
                }
            },
            after_state={"stay_record_id": stay_record.id},
            operator_id=sample_employee.id
        )
        db_session.commit()

        # 执行撤销
        result = undo_service.undo_operation(snapshot.snapshot_uuid, sample_employee.id)
        db_session.commit()

        # 验证结果
        assert "入住已撤销" in result["message"]

        # 验证住宿记录被删除
        deleted_stay = db_session.query(StayRecord).filter(
            StayRecord.id == stay_record.id
        ).first()
        assert deleted_stay is None

        # 验证房间状态恢复
        db_session.refresh(sample_room)
        assert sample_room.status == RoomStatus.VACANT_CLEAN

    def test_undo_extend_stay(self, undo_service, db_session, sample_room, sample_guest, sample_employee):
        """测试撤销续住"""
        from decimal import Decimal

        # 创建入住记录
        original_checkout = datetime.now().date() + timedelta(days=1)
        stay_record = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=original_checkout + timedelta(days=2),  # 已续住
            created_by=sample_employee.id
        )
        db_session.add(stay_record)
        db_session.flush()

        bill = Bill(
            stay_record_id=stay_record.id,
            total_amount=Decimal("864.00")  # 3天
        )
        db_session.add(bill)
        db_session.commit()

        # 创建续住快照
        snapshot = undo_service.create_snapshot(
            operation_type=OperationType.EXTEND_STAY,
            entity_type="stay_record",
            entity_id=stay_record.id,
            before_state={
                "expected_check_out": original_checkout.isoformat(),
                "bill": {"total_amount": 288.00}
            },
            after_state={
                "expected_check_out": (original_checkout + timedelta(days=2)).isoformat(),
                "bill": {"total_amount": 864.00}
            },
            operator_id=sample_employee.id
        )
        db_session.commit()

        # 执行撤销
        result = undo_service.undo_operation(snapshot.snapshot_uuid, sample_employee.id)
        db_session.commit()

        # 验证结果
        assert "续住已撤销" in result["message"]

        # 验证退房日期恢复
        db_session.refresh(stay_record)
        assert stay_record.expected_check_out == original_checkout


class TestCreateSnapshot:
    """快照创建辅助函数测试"""

    def test_create_checkin_snapshot(self, db_session, sample_room, sample_guest, sample_employee):
        """测试创建入住快照"""
        stay_record = StayRecord(
            guest_id=sample_guest.id,
            room_id=sample_room.id,
            check_in_time=datetime.now(),
            expected_check_out=datetime.now().date() + timedelta(days=1),
            created_by=sample_employee.id
        )
        db_session.add(stay_record)
        db_session.flush()

        snapshot = create_checkin_snapshot(
            db=db_session,
            stay_record=stay_record,
            room=sample_room,
            operator_id=sample_employee.id
        )

        assert snapshot is not None
        assert snapshot.operation_type == "check_in"
        assert snapshot.entity_type == "stay_record"

        before_state = json.loads(snapshot.before_state)
        assert "room" in before_state
        assert before_state["room"]["room_number"] == sample_room.room_number
