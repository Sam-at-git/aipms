"""
app/hotel/field_definitions.py

Hotel-specific UI field definitions for missing-parameter forms.

Provides field definitions (type, display name, placeholder, dynamic options)
for the AI service's parameter validation flow. When a required parameter is
missing, the field definition tells the frontend how to render the input form.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.schemas import MissingField


class HotelFieldDefinitionProvider:
    """
    Provides hotel-domain UI field definitions for missing action parameters.

    Usage:
        provider = HotelFieldDefinitionProvider(db, room_service, checkin_service, reservation_service)
        field = provider.get_field_definition('room_number', action_type, current_params)
    """

    def __init__(self, db: Session, room_service, checkin_service, reservation_service):
        self.db = db
        self.room_service = room_service
        self.checkin_service = checkin_service
        self.reservation_service = reservation_service

    def get_field_definition(
        self,
        field_name: str,
        action_type: str = "",
        current_params: dict = None,
    ) -> Optional[MissingField]:
        """
        Get UI field definition for a missing parameter.

        Args:
            field_name: The parameter name (e.g., 'room_number', 'guest_name')
            action_type: The action being validated (for context-dependent fields)
            current_params: Already-collected params (for context-dependent options)

        Returns:
            MissingField definition, or None if unknown field.
        """
        builder = _FIELD_BUILDERS.get(field_name)
        if builder:
            return builder(self)
        return None


# ---- Static field builders ----

def _build_room_number(provider: 'HotelFieldDefinitionProvider') -> MissingField:
    return MissingField(
        field_name='room_number',
        display_name='房间号',
        field_type='text',
        placeholder='如：201',
        required=True,
    )


def _build_guest_name(provider: 'HotelFieldDefinitionProvider') -> MissingField:
    return MissingField(
        field_name='guest_name',
        display_name='客人姓名',
        field_type='text',
        placeholder='请输入客人姓名',
        required=True,
    )


def _build_guest_phone(provider: 'HotelFieldDefinitionProvider') -> MissingField:
    return MissingField(
        field_name='guest_phone',
        display_name='联系电话',
        field_type='text',
        placeholder='请输入手机号',
        required=True,
    )


def _build_check_in_date(provider: 'HotelFieldDefinitionProvider') -> MissingField:
    return MissingField(
        field_name='check_in_date',
        display_name='入住日期',
        field_type='date',
        placeholder='如：今天、明天、2025-02-05',
        required=True,
    )


def _build_check_out_date(provider: 'HotelFieldDefinitionProvider') -> MissingField:
    return MissingField(
        field_name='check_out_date',
        display_name='离店日期',
        field_type='date',
        placeholder='如：明天、后天、2025-02-06',
        required=True,
    )


def _build_expected_check_out(provider: 'HotelFieldDefinitionProvider') -> MissingField:
    return MissingField(
        field_name='expected_check_out',
        display_name='预计离店日期',
        field_type='date',
        placeholder='如：明天、后天',
        required=True,
    )


def _build_new_room_number(provider: 'HotelFieldDefinitionProvider') -> MissingField:
    return MissingField(
        field_name='new_room_number',
        display_name='新房间号',
        field_type='text',
        placeholder='请输入目标房间号',
        required=True,
    )


# ---- Dynamic field builders (query DB for options) ----

def _build_room_type_id(provider: 'HotelFieldDefinitionProvider') -> MissingField:
    room_types = provider.room_service.get_room_types()
    options = [
        {'value': str(rt.id), 'label': f'{rt.name} ¥{rt.base_price}/晚'}
        for rt in room_types
    ]
    return MissingField(
        field_name='room_type_id',
        display_name='房型',
        field_type='select',
        options=options,
        placeholder='请选择房型',
        required=True,
    )


def _build_stay_record_id(provider: 'HotelFieldDefinitionProvider') -> MissingField:
    stays = provider.checkin_service.get_active_stays()
    options = [
        {'value': str(s.id), 'label': f'{s.room.room_number}号房 - {s.guest.name}'}
        for s in stays
    ]
    return MissingField(
        field_name='stay_record_id',
        display_name='住宿记录',
        field_type='select',
        options=options,
        placeholder='请选择客人',
        required=True,
    )


def _build_reservation_id(provider: 'HotelFieldDefinitionProvider') -> MissingField:
    reservations = provider.reservation_service.get_today_arrivals()
    options = [
        {'value': str(r.id), 'label': f'{r.reservation_no} - {r.guest.name} ({r.room_type.name})'}
        for r in reservations
    ]
    return MissingField(
        field_name='reservation_id',
        display_name='预订记录',
        field_type='select',
        options=options,
        placeholder='请选择预订',
        required=True,
    )


def _build_task_type(provider: 'HotelFieldDefinitionProvider') -> MissingField:
    return MissingField(
        field_name='task_type',
        display_name='任务类型',
        field_type='select',
        options=[
            {'value': 'cleaning', 'label': '清洁'},
            {'value': 'maintenance', 'label': '维修'},
        ],
        placeholder='请选择任务类型',
        required=True,
    )


# Registry mapping field names to builder functions
_FIELD_BUILDERS = {
    'room_number': _build_room_number,
    'guest_name': _build_guest_name,
    'guest_phone': _build_guest_phone,
    'room_type_id': _build_room_type_id,
    'check_in_date': _build_check_in_date,
    'check_out_date': _build_check_out_date,
    'expected_check_out': _build_expected_check_out,
    'new_room_number': _build_new_room_number,
    'stay_record_id': _build_stay_record_id,
    'reservation_id': _build_reservation_id,
    'task_type': _build_task_type,
}
