"""
core/domain/stay_record.py

StayRecord 领域实体 - 住宿期间的聚合根
"""
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, date
from decimal import Decimal
import logging

from core.ontology.base import BaseEntity

if TYPE_CHECKING:
    from app.models.ontology import StayRecord

logger = logging.getLogger(__name__)


class StayRecordState(str):
    ACTIVE = "active"
    CHECKED_OUT = "checked_out"


class StayRecordEntity(BaseEntity):
    def __init__(self, orm_model: "StayRecord"):
        self._orm_model = orm_model

    @property
    def id(self) -> int:
        return self._orm_model.id

    @property
    def guest_id(self) -> int:
        return self._orm_model.guest_id

    @property
    def room_id(self) -> int:
        return self._orm_model.room_id

    @property
    def reservation_id(self) -> Optional[int]:
        return self._orm_model.reservation_id

    @property
    def check_in_time(self) -> datetime:
        return self._orm_model.check_in_time

    @property
    def check_out_time(self) -> Optional[datetime]:
        return self._orm_model.check_out_time

    @property
    def expected_check_out(self) -> date:
        return self._orm_model.expected_check_out

    @property
    def status(self) -> str:
        return self._orm_model.status.value if self._orm_model.status else StayRecordState.ACTIVE

    @property
    def created_at(self) -> datetime:
        return self._orm_model.created_at

    @property
    def deposit_amount(self) -> Decimal:
        return self._orm_model.deposit_amount or Decimal("0")

    def check_out(self, check_out_time: Optional[datetime] = None) -> None:
        from app.models.ontology import StayRecordStatus
        if self._orm_model.status == StayRecordStatus.CHECKED_OUT:
            raise ValueError("住宿记录已经退房")
        if check_out_time:
            self._orm_model.check_out_time = check_out_time
        else:
            self._orm_model.check_out_time = datetime.utcnow()
        self._orm_model.status = StayRecordStatus.CHECKED_OUT
        logger.info(f"StayRecord {self.id} checked out")

    def extend_stay(self, new_check_out_date: date) -> None:
        self._orm_model.expected_check_out = new_check_out_date
        logger.info(f"StayRecord {self.id} extended to {new_check_out_date}")

    def is_active(self) -> bool:
        return self.status == StayRecordState.ACTIVE

    def get_nights(self) -> int:
        if self.check_in_time and self.check_out_time:
            return (self.check_out_time.date() - self.check_in_time.date()).days
        elif self.check_in_time and self.expected_check_out:
            return (self.expected_check_out - self.check_in_time.date()).days
        return 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "guest_id": self.guest_id,
            "room_id": self.room_id,
            "reservation_id": self.reservation_id,
            "check_in_time": self.check_in_time.isoformat() if self.check_in_time else None,
            "check_out_time": self.check_out_time.isoformat() if self.check_out_time else None,
            "expected_check_out": self.expected_check_out.isoformat() if self.expected_check_out else None,
            "status": self.status,
            "nights": self.get_nights(),
            "deposit_amount": float(self.deposit_amount),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class StayRecordRepository:
    def __init__(self, db_session):
        self._db = db_session

    def get_by_id(self, stay_record_id: int) -> Optional[StayRecordEntity]:
        from app.models.ontology import StayRecord
        orm_model = self._db.query(StayRecord).filter(StayRecord.id == stay_record_id).first()
        if orm_model is None:
            return None
        return StayRecordEntity(orm_model)

    def find_active(self) -> List[StayRecordEntity]:
        from app.models.ontology import StayRecord, StayRecordStatus
        orm_models = self._db.query(StayRecord).filter(StayRecord.status == StayRecordStatus.ACTIVE).all()
        return [StayRecordEntity(m) for m in orm_models]

    def find_by_guest(self, guest_id: int) -> List[StayRecordEntity]:
        from app.models.ontology import StayRecord
        orm_models = self._db.query(StayRecord).filter(StayRecord.guest_id == guest_id).all()
        return [StayRecordEntity(m) for m in orm_models]

    def find_by_room(self, room_id: int) -> List[StayRecordEntity]:
        from app.models.ontology import StayRecord
        orm_models = self._db.query(StayRecord).filter(StayRecord.room_id == room_id).all()
        return [StayRecordEntity(m) for m in orm_models]

    def save(self, stay_record: StayRecordEntity) -> None:
        self._db.add(stay_record._orm_model)
        self._db.commit()

    def list_all(self) -> List[StayRecordEntity]:
        from app.models.ontology import StayRecord
        orm_models = self._db.query(StayRecord).order_by(StayRecord.created_at.desc()).all()
        return [StayRecordEntity(m) for m in orm_models]


__all__ = ["StayRecordState", "StayRecordEntity", "StayRecordRepository"]
