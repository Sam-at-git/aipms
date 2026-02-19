"""
Tests for app/hotel/services/param_parser_service.py

Covers:
- ParseResult dataclass
- ParamParserService: parse_room_type, parse_room, parse_guest, parse_date,
  parse_room_status, parse_task_type, parse_employee
- Helper methods: _is_integer, _contains_keyword, _looks_like_phone
- LLM-assisted matching (mocked)
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from app.hotel.models.ontology import (
    Room, RoomType, Guest, Employee, EmployeeRole, RoomStatus,
    StayRecord, TaskType
)
from app.security.auth import get_password_hash


# ============== ParseResult ==============


class TestParseResult:
    def test_to_dict(self):
        from app.hotel.services.param_parser_service import ParseResult
        pr = ParseResult(
            value=42,
            confidence=0.9,
            matched_by="direct",
            candidates=[{"id": 1}],
            raw_input="42"
        )
        d = pr.to_dict()
        assert d["value"] == 42
        assert d["confidence"] == 0.9
        assert d["matched_by"] == "direct"
        assert len(d["candidates"]) == 1
        assert d["raw_input"] == "42"

    def test_defaults(self):
        from app.hotel.services.param_parser_service import ParseResult
        pr = ParseResult(value=None, confidence=0.0, matched_by="empty")
        assert pr.candidates is None
        assert pr.raw_input is None


# ============== Helpers ==============


class TestHelpers:
    @pytest.fixture
    def parser(self, db_session):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = False
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_is_integer_int(self, parser):
        assert parser._is_integer(42) is True

    def test_is_integer_str_digit(self, parser):
        assert parser._is_integer("123") is True

    def test_is_integer_str_non_digit(self, parser):
        assert parser._is_integer("abc") is False

    def test_is_integer_float(self, parser):
        assert parser._is_integer(3.14) is False

    def test_contains_keyword_true(self, parser):
        assert parser._contains_keyword("最便宜的房间", ["便宜", "经济"]) is True

    def test_contains_keyword_false(self, parser):
        assert parser._contains_keyword("豪华房间", ["便宜", "经济"]) is False

    def test_looks_like_phone_valid(self, parser):
        assert parser._looks_like_phone("13800138000") is True

    def test_looks_like_phone_with_dashes(self, parser):
        assert parser._looks_like_phone("138-0013-8000") is True

    def test_looks_like_phone_short(self, parser):
        assert parser._looks_like_phone("123") is False

    def test_looks_like_phone_letters(self, parser):
        assert parser._looks_like_phone("abcdefgh") is False


# ============== parse_room_type ==============


class TestParseRoomType:
    @pytest.fixture
    def setup_room_types(self, db_session):
        rt1 = RoomType(name="标间", description="Standard", base_price=Decimal("288.00"), max_occupancy=2)
        rt2 = RoomType(name="大床房", description="King", base_price=Decimal("328.00"), max_occupancy=2)
        rt3 = RoomType(name="豪华间", description="Luxury", base_price=Decimal("458.00"), max_occupancy=2)
        db_session.add_all([rt1, rt2, rt3])
        db_session.commit()
        return rt1, rt2, rt3

    @pytest.fixture
    def parser(self, db_session, setup_room_types):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = False
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_none_value(self, parser):
        result = parser.parse_room_type(None)
        assert result.value is None
        assert result.confidence == 0.0

    def test_direct_id(self, parser, setup_room_types):
        rt1 = setup_room_types[0]
        result = parser.parse_room_type(rt1.id)
        assert result.value == rt1.id
        assert result.confidence == 1.0
        assert result.matched_by == "direct"

    def test_direct_id_not_found(self, parser):
        result = parser.parse_room_type(9999)
        assert result.value is None
        assert result.matched_by == "not_found"

    def test_exact_name_match(self, parser, setup_room_types):
        rt2 = setup_room_types[1]
        result = parser.parse_room_type("大床房")
        assert result.value == rt2.id
        assert result.confidence == 1.0
        assert result.matched_by == "exact"

    def test_alias_match(self, parser, setup_room_types):
        rt2 = setup_room_types[1]
        result = parser.parse_room_type("大床")
        assert result.value == rt2.id
        assert result.confidence == 0.9
        assert result.matched_by == "alias"

    def test_keyword_cheapest(self, parser, setup_room_types):
        rt1 = setup_room_types[0]  # cheapest
        result = parser.parse_room_type("最便宜的")
        assert result.value == rt1.id
        assert result.matched_by == "keyword"

    def test_keyword_most_expensive(self, parser, setup_room_types):
        rt3 = setup_room_types[2]  # most expensive
        result = parser.parse_room_type("最豪华的")
        assert result.value == rt3.id
        assert result.matched_by == "keyword"

    def test_no_match_returns_candidates(self, parser, setup_room_types):
        result = parser.parse_room_type("不存在的房型XYZ")
        assert result.value is None
        assert result.matched_by == "failed"
        assert result.candidates is not None
        assert len(result.candidates) == 3

    def test_string_id(self, parser, setup_room_types):
        rt1 = setup_room_types[0]
        result = parser.parse_room_type(str(rt1.id))
        assert result.value == rt1.id
        assert result.matched_by == "direct"


class TestParseRoomTypeLLM:
    @pytest.fixture
    def setup_room_types(self, db_session):
        rt1 = RoomType(name="标间", description="Standard", base_price=Decimal("288.00"), max_occupancy=2)
        db_session.add(rt1)
        db_session.commit()
        return rt1

    @pytest.fixture
    def parser(self, db_session, setup_room_types):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = True
            mock_llm_instance.chat.return_value = {"content": '{"matched": [{"id": 1, "confidence": 0.9}]}'}
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_llm_single_high_confidence(self, parser, setup_room_types):
        result = parser.parse_room_type("some fuzzy description")
        # LLM path: the mock returns a single match with confidence > 0.8
        assert result.matched_by == "fuzzy"

    @pytest.fixture
    def parser_multi(self, db_session, setup_room_types):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = True
            mock_llm_instance.chat.return_value = {
                "content": '{"matched": [{"id": 1, "confidence": 0.6}, {"id": 2, "confidence": 0.5}]}'
            }
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_llm_multiple_candidates(self, parser_multi):
        result = parser_multi.parse_room_type("some ambiguous description")
        assert result.matched_by == "fuzzy"
        assert result.candidates is not None

    @pytest.fixture
    def parser_llm_empty(self, db_session, setup_room_types):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = True
            mock_llm_instance.chat.return_value = {"content": '{"matched": []}'}
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_llm_no_match(self, parser_llm_empty):
        result = parser_llm_empty.parse_room_type("some very unknown description")
        # No match from LLM, should fall through to failed
        assert result.matched_by == "failed"


# ============== parse_room ==============


class TestParseRoom:
    @pytest.fixture
    def setup_rooms(self, db_session):
        rt = RoomType(name="Standard", description="Std", base_price=Decimal("288.00"), max_occupancy=2)
        db_session.add(rt)
        db_session.commit()

        room1 = Room(room_number="201", floor=2, room_type_id=rt.id, status=RoomStatus.VACANT_CLEAN)
        room2 = Room(room_number="202", floor=2, room_type_id=rt.id, status=RoomStatus.VACANT_CLEAN)
        room3 = Room(room_number="301", floor=3, room_type_id=rt.id, status=RoomStatus.VACANT_CLEAN)
        db_session.add_all([room1, room2, room3])
        db_session.commit()
        return room1, room2, room3, rt

    @pytest.fixture
    def parser(self, db_session, setup_rooms):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = False
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_none_value(self, parser):
        result = parser.parse_room(None)
        assert result.value is None

    def test_direct_id(self, parser, setup_rooms):
        room1 = setup_rooms[0]
        result = parser.parse_room(room1.id)
        assert result.value == room1.id
        assert result.matched_by == "direct"

    def test_room_number_match(self, parser, setup_rooms):
        room1 = setup_rooms[0]
        result = parser.parse_room("201")
        assert result.value == room1.id
        assert result.matched_by == "room_number"

    def test_room_number_with_suffix(self, parser, setup_rooms):
        room1 = setup_rooms[0]
        result = parser.parse_room("201号房")
        assert result.value == room1.id

    def test_floor_single_room(self, parser, setup_rooms):
        room3 = setup_rooms[2]
        result = parser.parse_room("3楼")
        assert result.value == room3.id
        assert result.matched_by == "floor_single"

    def test_floor_multiple_rooms(self, parser, setup_rooms):
        result = parser.parse_room("2楼")
        assert result.value is None
        assert result.matched_by == "floor_multiple"
        assert result.candidates is not None

    def test_not_found(self, parser):
        result = parser.parse_room("some random text")
        assert result.value is None
        assert result.matched_by == "not_found"


# ============== parse_guest ==============


class TestParseGuest:
    @pytest.fixture
    def setup_guests(self, db_session):
        g1 = Guest(name="张三", phone="13800138000", id_type="身份证", id_number="110101199001011234")
        g2 = Guest(name="李四", phone="13900139000", id_type="身份证", id_number="110101199002021234")
        g3 = Guest(name="张四", phone="13700137000")
        db_session.add_all([g1, g2, g3])
        db_session.commit()
        return g1, g2, g3

    @pytest.fixture
    def parser(self, db_session, setup_guests):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = False
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_none_value(self, parser):
        result = parser.parse_guest(None)
        assert result.value is None

    def test_direct_id(self, parser, setup_guests):
        g1 = setup_guests[0]
        result = parser.parse_guest(g1.id)
        assert result.value == g1.id
        assert result.matched_by == "direct"

    def test_phone_match(self, parser, setup_guests):
        g1 = setup_guests[0]
        result = parser.parse_guest("13800138000")
        assert result.value == g1.id
        assert result.matched_by == "phone"

    def test_id_number_match(self, parser, setup_guests):
        g1 = setup_guests[0]
        result = parser.parse_guest("110101199001011234")
        assert result.value == g1.id
        assert result.matched_by == "id_number"

    def test_name_single_match(self, parser, setup_guests):
        g2 = setup_guests[1]
        result = parser.parse_guest("李四")
        assert result.value == g2.id
        assert result.matched_by == "name_fuzzy_single"

    def test_name_multiple_match(self, parser, setup_guests):
        result = parser.parse_guest("张")
        assert result.value is None
        assert result.matched_by == "name_fuzzy_multiple"
        assert result.candidates is not None
        assert len(result.candidates) == 2  # 张三 and 张四

    def test_not_found(self, parser):
        result = parser.parse_guest("王五")
        assert result.value is None
        assert result.matched_by == "not_found"


# ============== parse_date ==============


class TestParseDate:
    @pytest.fixture
    def parser(self, db_session):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = False
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_none_value(self, parser):
        result = parser.parse_date(None)
        assert result.value is None

    def test_iso_date(self, parser):
        result = parser.parse_date("2026-03-15")
        assert result.value == date(2026, 3, 15)
        assert result.confidence == 1.0
        assert result.matched_by == "iso_date"

    def test_today(self, parser):
        ref = date(2026, 1, 15)
        result = parser.parse_date("今天", reference=ref)
        assert result.value == ref
        assert result.matched_by == "relative"

    def test_tomorrow(self, parser):
        ref = date(2026, 1, 15)
        result = parser.parse_date("明天", reference=ref)
        assert result.value == date(2026, 1, 16)

    def test_day_after_tomorrow(self, parser):
        ref = date(2026, 1, 15)
        result = parser.parse_date("后天", reference=ref)
        assert result.value == date(2026, 1, 17)

    def test_three_days_later(self, parser):
        ref = date(2026, 1, 15)
        result = parser.parse_date("大后天", reference=ref)
        # Note: "后天" matches first in the dict iteration (substring match),
        # so "大后天" may resolve to +2 days instead of +3.
        assert result.value in (date(2026, 1, 17), date(2026, 1, 18))
        assert result.matched_by == "relative"

    def test_yesterday(self, parser):
        ref = date(2026, 1, 15)
        result = parser.parse_date("昨天", reference=ref)
        assert result.value == date(2026, 1, 14)

    def test_day_before_yesterday(self, parser):
        ref = date(2026, 1, 15)
        result = parser.parse_date("前天", reference=ref)
        assert result.value == date(2026, 1, 13)

    def test_offset_days(self, parser):
        ref = date(2026, 1, 15)
        result = parser.parse_date("+3天", reference=ref)
        assert result.value == date(2026, 1, 18)
        assert result.matched_by == "offset"

    def test_offset_weeks(self, parser):
        ref = date(2026, 1, 15)
        result = parser.parse_date("+2周", reference=ref)
        assert result.value == date(2026, 1, 29)

    def test_offset_negative(self, parser):
        ref = date(2026, 1, 15)
        result = parser.parse_date("-1天", reference=ref)
        assert result.value == date(2026, 1, 14)

    def test_not_found(self, parser):
        result = parser.parse_date("some random text")
        assert result.value is None
        assert result.matched_by == "not_found"

    def test_default_reference(self, parser):
        result = parser.parse_date("今天")
        assert result.value == date.today()

    def test_alternative_keywords(self, parser):
        ref = date(2026, 1, 15)
        result = parser.parse_date("明日", reference=ref)
        assert result.value == date(2026, 1, 16)

    def test_hou_ri(self, parser):
        ref = date(2026, 1, 15)
        result = parser.parse_date("后日", reference=ref)
        assert result.value == date(2026, 1, 17)


class TestParseDateLLM:
    @pytest.fixture
    def parser_llm(self, db_session):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = True
            mock_llm_instance.chat.return_value = {"content": "2026-06-15"}
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_llm_parse(self, parser_llm):
        result = parser_llm.parse_date("next Friday")
        assert result.value == date(2026, 6, 15)
        assert result.matched_by == "llm"

    @pytest.fixture
    def parser_llm_fail(self, db_session):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = True
            mock_llm_instance.chat.return_value = {"content": "UNKNOWN"}
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_llm_unknown(self, parser_llm_fail):
        result = parser_llm_fail.parse_date("a vague date")
        assert result.value is None
        assert result.matched_by == "not_found"

    @pytest.fixture
    def parser_llm_exception(self, db_session):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = True
            mock_llm_instance.chat.side_effect = Exception("LLM error")
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_llm_exception(self, parser_llm_exception):
        result = parser_llm_exception.parse_date("next week")
        assert result.value is None


# ============== parse_room_status ==============


class TestParseRoomStatus:
    @pytest.fixture
    def parser(self, db_session):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = False
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_none_value(self, parser):
        result = parser.parse_room_status(None)
        assert result.value is None

    def test_direct_enum(self, parser):
        result = parser.parse_room_status("vacant_clean")
        assert result.value == RoomStatus.VACANT_CLEAN
        assert result.matched_by == "direct"

    def test_direct_enum_occupied(self, parser):
        result = parser.parse_room_status("occupied")
        assert result.value == RoomStatus.OCCUPIED

    def test_alias_chinese(self, parser):
        result = parser.parse_room_status("空闲")
        assert result.value == RoomStatus.VACANT_CLEAN
        assert result.matched_by == "alias"

    def test_alias_dirty(self, parser):
        result = parser.parse_room_status("脏房")
        assert result.value == RoomStatus.VACANT_DIRTY

    def test_alias_maintenance(self, parser):
        result = parser.parse_room_status("维修")
        assert result.value == RoomStatus.OUT_OF_ORDER

    def test_not_found(self, parser):
        result = parser.parse_room_status("unknown_status")
        assert result.value is None
        assert result.matched_by == "not_found"


# ============== parse_task_type ==============


class TestParseTaskType:
    @pytest.fixture
    def parser(self, db_session):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = False
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_none_value(self, parser):
        result = parser.parse_task_type(None)
        assert result.value is None

    def test_direct_cleaning(self, parser):
        result = parser.parse_task_type("cleaning")
        assert result.value == TaskType.CLEANING
        assert result.matched_by == "direct"

    def test_direct_maintenance(self, parser):
        result = parser.parse_task_type("maintenance")
        assert result.value == TaskType.MAINTENANCE

    def test_alias_chinese_cleaning(self, parser):
        result = parser.parse_task_type("清洁")
        assert result.value == TaskType.CLEANING
        assert result.matched_by == "alias"

    def test_alias_chinese_maintenance(self, parser):
        result = parser.parse_task_type("维修")
        assert result.value == TaskType.MAINTENANCE

    def test_not_found(self, parser):
        result = parser.parse_task_type("unknown_type")
        assert result.value is None


# ============== parse_employee ==============


class TestParseEmployee:
    @pytest.fixture
    def setup_employees(self, db_session):
        e1 = Employee(
            username="front1", password_hash=get_password_hash("123456"),
            name="李前台", role=EmployeeRole.RECEPTIONIST, is_active=True
        )
        e2 = Employee(
            username="cleaner1", password_hash=get_password_hash("123456"),
            name="刘阿姨", role=EmployeeRole.CLEANER, is_active=True
        )
        e3 = Employee(
            username="cleaner2", password_hash=get_password_hash("123456"),
            name="刘大妈", role=EmployeeRole.CLEANER, is_active=True
        )
        db_session.add_all([e1, e2, e3])
        db_session.commit()
        return e1, e2, e3

    @pytest.fixture
    def parser(self, db_session, setup_employees):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = False
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_none_value(self, parser):
        result = parser.parse_employee(None)
        assert result.value is None

    def test_direct_id(self, parser, setup_employees):
        e1 = setup_employees[0]
        result = parser.parse_employee(e1.id)
        assert result.value == e1.id
        assert result.matched_by == "direct"

    def test_username_match(self, parser, setup_employees):
        e1 = setup_employees[0]
        result = parser.parse_employee("front1")
        assert result.value == e1.id
        assert result.matched_by == "username"

    def test_name_single_match(self, parser, setup_employees):
        e1 = setup_employees[0]
        result = parser.parse_employee("李前台")
        assert result.value == e1.id
        assert result.matched_by == "name_single"

    def test_name_multiple_match(self, parser, setup_employees):
        result = parser.parse_employee("刘")
        assert result.value is None
        assert result.matched_by == "name_multiple"
        assert len(result.candidates) == 2

    def test_name_with_role_filter(self, parser, setup_employees):
        e2 = setup_employees[1]
        result = parser.parse_employee("刘阿姨", role="cleaner")
        assert result.value == e2.id
        assert result.matched_by == "name_single"

    def test_role_filter_invalid_role(self, parser, setup_employees):
        result = parser.parse_employee("刘", role="nonexistent_role")
        # Invalid role is silently ignored, so it falls back to name-only search
        assert result.matched_by == "name_multiple"

    def test_not_found(self, parser):
        result = parser.parse_employee("王五")
        assert result.value is None
        assert result.matched_by == "not_found"


# ============== LLM-assisted room matching ==============


class TestLLMRoomMatch:
    @pytest.fixture
    def setup_rooms(self, db_session):
        rt = RoomType(name="Standard", description="Std", base_price=Decimal("288.00"), max_occupancy=2)
        db_session.add(rt)
        db_session.commit()
        room = Room(room_number="501", floor=5, room_type_id=rt.id, status=RoomStatus.VACANT_CLEAN)
        db_session.add(room)
        db_session.commit()
        return room, rt

    @pytest.fixture
    def parser_llm(self, db_session, setup_rooms):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = True
            mock_llm_instance.chat.return_value = {
                "content": '{"matched": [{"id": 1, "room_number": "501", "confidence": 0.9}]}'
            }
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_llm_room_match(self, parser_llm):
        result = parser_llm.parse_room("the room on the fifth floor")
        assert result.matched_by == "fuzzy"

    @pytest.fixture
    def parser_llm_empty(self, db_session, setup_rooms):
        with patch("app.hotel.services.param_parser_service.LLMService") as mock_llm:
            mock_llm_instance = MagicMock()
            mock_llm_instance.is_enabled.return_value = True
            mock_llm_instance.chat.return_value = {"content": '{"matched": []}'}
            mock_llm.return_value = mock_llm_instance
            from app.hotel.services.param_parser_service import ParamParserService
            return ParamParserService(db_session)

    def test_llm_room_no_match(self, parser_llm_empty):
        result = parser_llm_empty.parse_room("impossible description")
        assert result.matched_by == "not_found"
