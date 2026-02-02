"""
智能参数解析服务
统一处理各种格式的输入，支持多级匹配策略
"""
from typing import Any, Optional, List, Dict, Union
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.ontology import Room, RoomType, Guest, StayRecord, Employee
from app.services.room_service import RoomService
from app.services.llm_service import LLMService
import re


class ParseResult:
    """解析结果"""
    def __init__(
        self,
        value: Any,
        confidence: float,
        matched_by: str,
        candidates: Optional[List[Dict]] = None,
        raw_input: Optional[str] = None
    ):
        self.value = value
        self.confidence = confidence  # 0.0 - 1.0
        self.matched_by = matched_by  # 'direct', 'exact', 'alias', 'fuzzy'
        self.candidates = candidates  # 低置信度时的候选项
        self.raw_input = raw_input

    def to_dict(self) -> dict:
        return {
            'value': self.value,
            'confidence': self.confidence,
            'matched_by': self.matched_by,
            'candidates': self.candidates,
            'raw_input': self.raw_input
        }


class ParamParserService:
    """智能参数解析服务"""

    # 房型别名映射
    ROOM_TYPE_ALIASES = {
        '标间': ['标间', '标准间', '双床房', '双人标间', '标准双床'],
        '大床房': ['大床房', '大床', '双人床', '双人大床', '大床间'],
        '豪华间': ['豪华间', '豪华房', '豪华标间', '高级房', '商务间']
    }

    # 房间状态别名
    ROOM_STATUS_ALIASES = {
        'vacant_clean': ['空闲', '干净', '空房', '可住', 'vacant_clean', '干净空房'],
        'occupied': ['入住', '有人', '占用', 'occupied', '在住'],
        'vacant_dirty': ['脏房', '待清洁', '需打扫', 'vacant_dirty', '待打扫'],
        'out_of_order': ['维修', '故障', '不可用', 'out_of_order', '坏房']
    }

    # 任务类型别名
    TASK_TYPE_ALIASES = {
        'cleaning': ['清洁', '打扫', 'cleaning', '清洁任务', '打扫卫生'],
        'maintenance': ['维修', '修理', 'maintenance', '设施维修']
    }

    def __init__(self, db: Session):
        self.db = db
        self.room_service = RoomService(db)
        self.llm_service = LLMService()

    def parse_room_type(self, value: Any) -> ParseResult:
        """
        解析房型参数
        支持输入：ID(1/2/3)、名称("大床房")、别名("大床")、模糊描述("最便宜的")
        """
        if value is None:
            return ParseResult(None, 0.0, 'empty', raw_input=str(value))

        raw_input = str(value)
        room_types = self.room_service.get_room_types()

        # Level 1: 直接数字ID
        if self._is_integer(value):
            room_type = self.room_service.get_room_type(int(value))
            if room_type:
                return ParseResult(int(value), 1.0, 'direct', raw_input=raw_input)
            return ParseResult(None, 0.0, 'not_found', raw_input=raw_input)

        # Level 2: 精确名称匹配
        for rt in room_types:
            if rt.name == raw_input:
                return ParseResult(rt.id, 1.0, 'exact', raw_input=raw_input)

        # Level 3: 别名匹配
        for rt in room_types:
            aliases = self.ROOM_TYPE_ALIASES.get(rt.name, [])
            if raw_input in aliases:
                return ParseResult(rt.id, 0.9, 'alias', raw_input=raw_input)

        # Level 3.5: 模糊关键词匹配
        if self._contains_keyword(raw_input, ['便宜', '低价', '经济']):
            cheapest = min(room_types, key=lambda x: float(x.base_price))
            return ParseResult(cheapest.id, 0.7, 'keyword', raw_input=raw_input)

        if self._contains_keyword(raw_input, ['贵', '高档', '豪华', '最好']):
            most_expensive = max(room_types, key=lambda x: float(x.base_price))
            return ParseResult(most_expensive.id, 0.7, 'keyword', raw_input=raw_input)

        # Level 4: LLM模糊匹配（如果启用）
        if self.llm_service.is_enabled():
            candidates = self._llm_match_room_type(raw_input, room_types)
            if candidates:
                if len(candidates) == 1 and candidates[0]['confidence'] > 0.8:
                    return ParseResult(
                        candidates[0]['id'],
                        candidates[0]['confidence'],
                        'fuzzy',
                        raw_input=raw_input
                    )
                # 多个候选或低置信度
                return ParseResult(
                    candidates[0]['id'] if candidates else None,
                    candidates[0]['confidence'] if candidates else 0.0,
                    'fuzzy',
                    candidates=candidates,
                    raw_input=raw_input
                )

        # 完全匹配失败，返回所有房型作为候选项
        all_candidates = [
            {'id': rt.id, 'name': rt.name, 'price': float(rt.base_price)}
            for rt in room_types
        ]
        return ParseResult(None, 0.0, 'failed', candidates=all_candidates, raw_input=raw_input)

    def parse_room(self, value: Any) -> ParseResult:
        """
        解析房间参数
        支持输入：ID、房间号("201")、描述("2楼的房间")
        """
        if value is None:
            return ParseResult(None, 0.0, 'empty', raw_input=str(value))

        raw_input = str(value)

        # Level 1: 直接数字ID
        if self._is_integer(value):
            room = self.room_service.get_room(int(value))
            if room:
                return ParseResult(int(value), 1.0, 'direct', raw_input=raw_input)

        # Level 2: 房间号匹配（支持"201"、"2-01"等格式）
        room_number = raw_input.upper().replace('-', '').replace('房', '').replace('号', '')
        room = self.room_service.get_room_by_number(room_number)
        if room:
            return ParseResult(room.id, 1.0, 'room_number', raw_input=raw_input)

        # Level 3: 楼层描述匹配
        floor_match = re.search(r'(\d+)楼?', raw_input)
        if floor_match:
            floor = int(floor_match.group(1))
            rooms = self.room_service.get_rooms(floor=floor, is_active=True)
            if len(rooms) == 1:
                return ParseResult(rooms[0].id, 0.8, 'floor_single', raw_input=raw_input)
            elif len(rooms) > 1:
                candidates = [
                    {'id': r.id, 'room_number': r.room_number, 'room_type': r.room_type.name}
                    for r in rooms[:5]
                ]
                return ParseResult(None, 0.5, 'floor_multiple', candidates=candidates, raw_input=raw_input)

        # Level 4: LLM模糊匹配
        if self.llm_service.is_enabled():
            candidates = self._llm_match_room(raw_input)
            if candidates:
                if len(candidates) == 1 and candidates[0]['confidence'] > 0.8:
                    return ParseResult(
                        candidates[0]['id'],
                        candidates[0]['confidence'],
                        'fuzzy',
                        raw_input=raw_input
                    )
                return ParseResult(
                    candidates[0]['id'] if candidates else None,
                    candidates[0]['confidence'] if candidates else 0.0,
                    'fuzzy',
                    candidates=candidates,
                    raw_input=raw_input
                )

        return ParseResult(None, 0.0, 'not_found', raw_input=raw_input)

    def parse_guest(self, value: Any) -> ParseResult:
        """
        解析客人参数
        支持输入：ID、姓名、手机号、ID号
        """
        if value is None:
            return ParseResult(None, 0.0, 'empty', raw_input=str(value))

        raw_input = str(value).strip()

        # Level 1: 数字ID
        if self._is_integer(value):
            guest = self.db.query(Guest).filter(Guest.id == int(value)).first()
            if guest:
                return ParseResult(int(value), 1.0, 'direct', raw_input=raw_input)

        # Level 2: 手机号匹配
        if self._looks_like_phone(raw_input):
            guest = self.db.query(Guest).filter(Guest.phone == raw_input).first()
            if guest:
                return ParseResult(guest.id, 1.0, 'phone', raw_input=raw_input)

        # Level 3: 证件号匹配
        if len(raw_input) >= 6:  # 证件号通常较长
            guest = self.db.query(Guest).filter(Guest.id_number == raw_input).first()
            if guest:
                return ParseResult(guest.id, 1.0, 'id_number', raw_input=raw_input)

        # Level 4: 姓名模糊匹配
        guests = self.db.query(Guest).filter(
            Guest.name.like(f'%{raw_input}%')
        ).limit(10).all()

        if len(guests) == 1:
            return ParseResult(guests[0].id, 0.9, 'name_fuzzy_single', raw_input=raw_input)
        elif len(guests) > 1:
            candidates = [
                {'id': g.id, 'name': g.name, 'phone': g.phone}
                for g in guests
            ]
            return ParseResult(None, 0.5, 'name_fuzzy_multiple', candidates=candidates, raw_input=raw_input)

        return ParseResult(None, 0.0, 'not_found', raw_input=raw_input)

    def parse_date(self, value: Any, reference: Optional[date] = None) -> ParseResult:
        """
        解析日期参数
        支持输入：ISO格式("2025-01-01")、相对日期("明天"、"后天")、偏移("+3天")
        """
        if value is None:
            return ParseResult(None, 0.0, 'empty', raw_input=str(value))

        if reference is None:
            reference = date.today()

        raw_input = str(value).strip().lower()

        # Level 1: ISO格式日期
        try:
            parsed_date = date.fromisoformat(raw_input)
            return ParseResult(parsed_date, 1.0, 'iso_date', raw_input=raw_input)
        except ValueError:
            pass

        # Level 2: 相对日期关键词
        relative_dates = {
            '今天': 0,
            '明日': 0, '明天': 0, '明': 0,
            '后天': 1, '后日': 1,
            '大后天': 2,
            '昨天': -1, '昨日': -1,
            '前天': -2,
        }

        for keyword, offset in relative_dates.items():
            if keyword in raw_input:
                result_date = reference + timedelta(days=offset)
                return ParseResult(result_date, 0.95, 'relative', raw_input=raw_input)

        # Level 3: 偏移量 (+3天, +1 week)
        offset_match = re.search(r'([+-]?\d+)\s*(天|日|周|week|day)', raw_input)
        if offset_match:
            offset = int(offset_match.group(1))
            unit = offset_match.group(2)
            if unit in ['周', 'week']:
                offset *= 7
            result_date = reference + timedelta(days=offset)
            return ParseResult(result_date, 0.9, 'offset', raw_input=raw_input)

        # Level 4: LLM解析（如果启用）
        if self.llm_service.is_enabled():
            parsed = self._llm_parse_date(raw_input, reference)
            if parsed:
                return ParseResult(parsed, 0.8, 'llm', raw_input=raw_input)

        return ParseResult(None, 0.0, 'not_found', raw_input=raw_input)

    def parse_room_status(self, value: Any) -> ParseResult:
        """
        解析房间状态
        支持输入：状态枚举值、中文描述
        """
        if value is None:
            return ParseResult(None, 0.0, 'empty', raw_input=str(value))

        raw_input = str(value).strip().lower()

        # Level 1: 直接枚举值
        from app.models.ontology import RoomStatus
        try:
            status = RoomStatus(raw_input)
            return ParseResult(status, 1.0, 'direct', raw_input=raw_input)
        except ValueError:
            pass

        # Level 2: 别名匹配
        for status_value, aliases in self.ROOM_STATUS_ALIASES.items():
            if raw_input in [a.lower() for a in aliases]:
                return ParseResult(RoomStatus(status_value), 0.95, 'alias', raw_input=raw_input)

        return ParseResult(None, 0.0, 'not_found', raw_input=raw_input)

    def parse_task_type(self, value: Any) -> ParseResult:
        """
        解析任务类型
        支持输入：任务类型枚举、中文描述
        """
        if value is None:
            return ParseResult(None, 0.0, 'empty', raw_input=str(value))

        raw_input = str(value).strip().lower()

        # Level 1: 直接枚举值
        from app.models.ontology import TaskType
        try:
            task_type = TaskType(raw_input)
            return ParseResult(task_type, 1.0, 'direct', raw_input=raw_input)
        except ValueError:
            pass

        # Level 2: 别名匹配
        for type_value, aliases in self.TASK_TYPE_ALIASES.items():
            if raw_input in [a.lower() for a in aliases]:
                return ParseResult(TaskType(type_value), 0.95, 'alias', raw_input=raw_input)

        return ParseResult(None, 0.0, 'not_found', raw_input=raw_input)

    def parse_employee(self, value: Any, role: Optional[str] = None) -> ParseResult:
        """
        解析员工参数
        支持输入：ID、姓名、用户名
        """
        if value is None:
            return ParseResult(None, 0.0, 'empty', raw_input=str(value))

        raw_input = str(value).strip()

        # Level 1: 数字ID
        if self._is_integer(value):
            employee = self.db.query(Employee).filter(Employee.id == int(value)).first()
            if employee:
                return ParseResult(int(value), 1.0, 'direct', raw_input=raw_input)

        # Level 2: 用户名精确匹配
        employee = self.db.query(Employee).filter(Employee.username == raw_input).first()
        if employee:
            return ParseResult(employee.id, 1.0, 'username', raw_input=raw_input)

        # Level 3: 姓名模糊匹配
        query = self.db.query(Employee).filter(Employee.name.like(f'%{raw_input}%'))
        if role:
            from app.models.ontology import EmployeeRole
            try:
                role_enum = EmployeeRole(role)
                query = query.filter(Employee.role == role_enum)
            except ValueError:
                pass

        employees = query.limit(10).all()

        if len(employees) == 1:
            return ParseResult(employees[0].id, 0.9, 'name_single', raw_input=raw_input)
        elif len(employees) > 1:
            candidates = [
                {'id': e.id, 'name': e.name, 'username': e.username, 'role': e.role}
                for e in employees
            ]
            return ParseResult(None, 0.5, 'name_multiple', candidates=candidates, raw_input=raw_input)

        return ParseResult(None, 0.0, 'not_found', raw_input=raw_input)

    # ========== 辅助方法 ==========

    def _is_integer(self, value: Any) -> bool:
        """检查值是否为整数（或可转换为整数的字符串）"""
        if isinstance(value, int):
            return True
        if isinstance(value, str) and value.isdigit():
            return True
        return False

    def _contains_keyword(self, text: str, keywords: List[str]) -> bool:
        """检查文本是否包含任一关键词"""
        return any(kw in text for kw in keywords)

    def _looks_like_phone(self, value: str) -> bool:
        """检查是否像手机号"""
        # 移除所有非数字字符
        digits = re.sub(r'\D', '', value)
        return len(digits) >= 7 and digits.isdigit()

    # ========== LLM辅助方法 ==========

    def _llm_match_room_type(self, description: str, room_types: List[RoomType]) -> List[Dict]:
        """使用LLM进行房型模糊匹配"""
        room_type_info = [
            f"{rt.id}:{rt.name}(¥{rt.base_price})"
            for rt in room_types
        ]
        room_types_str = ', '.join(room_type_info)

        prompt = f"""用户想选择的房型描述是："{description}"

可用房型列表：{room_types_str}

请分析用户描述，返回最匹配的房型。返回JSON格式：
{{
    "matched": [
        {{"id": 房型ID, "name": "房型名称", "confidence": 匹配置信度0-1, "reason": "匹配原因"}}
    ],
    "summary": "简短说明"
}}

如果无法确定或置信度低于0.6，matched返回空数组。"""

        try:
            response = self.llm_service.chat(prompt)
            import json
            content = response.get('content', '')
            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
                matched = result.get('matched', [])
                # 按置信度排序
                matched.sort(key=lambda x: x.get('confidence', 0), reverse=True)
                return matched[:3]  # 最多返回3个候选
        except Exception as e:
            pass

        return []

    def _llm_match_room(self, description: str) -> List[Dict]:
        """使用LLM进行房间模糊匹配"""
        rooms = self.room_service.get_rooms(is_active=True)
        room_info = [
            f"{r.id}:{r.room_number}({r.room_type.name})"
            for r in rooms[:20]  # 限制数量
        ]

        prompt = f"""用户想选择的房间描述是："{description}"

可用房间（前20间）：{', '.join(room_info)}

请分析用户描述，返回最匹配的房间。返回JSON格式：
{{
    "matched": [
        {{"id": 房间ID, "room_number": "房间号", "confidence": 匹配置信度0-1}}
    ],
    "summary": "简短说明"
}}

如果无法确定，matched返回空数组。"""

        try:
            response = self.llm_service.chat(prompt)
            import json
            content = response.get('content', '')
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                result = json.loads(json_match.group())
                matched = result.get('matched', [])
                matched.sort(key=lambda x: x.get('confidence', 0), reverse=True)
                return matched[:3]
        except Exception:
            pass

        return []

    def _llm_parse_date(self, description: str, reference: date) -> Optional[date]:
        """使用LLM解析日期"""
        today_str = reference.isoformat()

        prompt = f"""今天日期是：{today_str}

用户输入的日期描述是："{description}"

请解析为标准日期格式(YYYY-MM-DD)。只返回日期字符串，不要其他内容。

如果无法确定，返回"UNKNOWN"。"""

        try:
            response = self.llm_service.chat(prompt)
            content = response.get('content', '').strip()
            if content and content != 'UNKNOWN':
                parsed_date = date.fromisoformat(content.split()[0])  # 取第一个词
                return parsed_date
        except Exception:
            pass

        return None
