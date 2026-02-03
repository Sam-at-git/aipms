"""
AI 对话服务 - OODA 循环运行时
遵循 Palantir 原则：
- Observe: 捕获自然语言指令
- Orient: 将输入映射为本体操作
- Decide: 检查业务规则，生成建议动作
- Act: 执行状态变更（需人类确认）

支持两种模式：
1. LLM 模式：使用 OpenAI 兼容 API 进行自然语言理解
2. 规则模式：使用规则匹配作为后备方案
"""
import json
import re
from typing import Optional, List, Dict, Any, Union
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.ontology import (
    Room, RoomStatus, RoomType, Guest, Reservation, ReservationStatus,
    StayRecord, StayRecordStatus, Task, TaskType, TaskStatus, Employee
)
from app.services.room_service import RoomService
from app.services.reservation_service import ReservationService
from app.services.checkin_service import CheckInService
from app.services.checkout_service import CheckOutService
from app.services.task_service import TaskService
from app.services.billing_service import BillingService
from app.services.report_service import ReportService
from app.services.llm_service import LLMService, TopicRelevance
from app.services.param_parser_service import ParamParserService


class AIService:
    """AI 对话服务 - 实现 OODA 循环"""

    def __init__(self, db: Session):
        self.db = db
        self.room_service = RoomService(db)
        self.reservation_service = ReservationService(db)
        self.checkin_service = CheckInService(db)
        self.checkout_service = CheckOutService(db)
        self.task_service = TaskService(db)
        self.billing_service = BillingService(db)
        self.report_service = ReportService(db)
        self.llm_service = LLMService()
        self.param_parser = ParamParserService(db)

    def _parse_relative_date(self, date_input: Union[str, date]) -> Optional[date]:
        """
        解析相对日期字符串为实际日期

        支持的格式:
        - "今天", "明日", "明天" -> 今天 + 0天 或 +1天
        - "后天" -> 今天 + 2天
        - "大后天" -> 今天 + 3天
        - "明晚" -> 今天 + 1天
        - "下周X" -> 下周星期X
        - "YYYY-MM-DD" 格式
        - 已经是 date 对象则直接返回
        """
        if isinstance(date_input, date):
            return date_input

        if not isinstance(date_input, str):
            return None

        date_str = date_str_clean = date_input.strip()

        # 今天
        if date_str in ["今天", "今日", "今日内"]:
            return date.today()

        # 明天/明日
        if date_str in ["明天", "明日", "明", "明晚", "明早"]:
            return date.today() + timedelta(days=1)

        # 后天
        if date_str in ["后天", "后日"]:
            return date.today() + timedelta(days=2)

        # 大后天
        if date_str in ["大后天"]:
            return date.today() + timedelta(days=3)

        # 下周X
        weekday_map = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
        week_match = re.match(r'下?(周|星期)([一二三四五六日天])', date_str)
        if week_match:
            target_weekday = weekday_map.get(week_match.group(2))
            if target_weekday is not None:
                today = date.today()
                days_ahead = target_weekday - today.weekday()
                if days_ahead <= 0:  # 目标日已过，加7天
                    days_ahead += 7
                if week_match.group(1) == "周":  # "下周"需要再加7天
                    days_ahead += 7
                return today + timedelta(days=days_ahead)

        # 尝试解析 ISO 格式日期 YYYY-MM-DD
        try:
            return date.fromisoformat(date_str)
        except (ValueError, AttributeError):
            pass

        # 尝试其他常见格式
        for fmt in ["%Y/%m/%d", "%Y.%m.%d", "%m/%d", "%m.%d"]:
            try:
                parsed = datetime.strptime(date_str, fmt)
                if "%Y" not in fmt:  # 没有年份，使用今年
                    if parsed.month < date.today().month:
                        parsed = parsed.replace(year=date.today().year + 1)
                    else:
                        parsed = parsed.replace(year=date.today().year)
                return parsed.date()
            except ValueError:
                continue

        return None

    def process_message(
        self,
        message: str,
        user: Employee,
        conversation_history: list = None,
        topic_id: str = None
    ) -> dict:
        """
        处理用户消息 - OODA 循环入口

        优先使用 LLM，失败时回退到规则匹配

        Args:
            message: 用户消息
            user: 当前用户
            conversation_history: 历史对话消息列表（可选）
            topic_id: 当前话题 ID（可选）

        Returns:
            包含 message, suggested_actions, context, topic_id 的字典
        """
        message = message.strip()
        new_topic_id = topic_id
        include_context = False

        # 检查话题相关性并决定是否携带上下文
        if conversation_history and self.llm_service.is_enabled():
            try:
                # 将历史转换为简单格式
                history_for_check = [
                    {'role': h.get('role'), 'content': h.get('content')}
                    for h in conversation_history[-6:]  # 最近 3 轮
                ]

                relevance = self.llm_service.check_topic_relevance(message, history_for_check)

                if relevance == TopicRelevance.CONTINUATION:
                    # 继续话题，携带上下文
                    include_context = True
                elif relevance == TopicRelevance.FOLLOWUP_ANSWER:
                    # 回答追问，必须携带完整上下文
                    include_context = True
                else:
                    # 新话题，不携带上下文，生成新 topic_id
                    include_context = False
                    new_topic_id = None  # 将在返回时生成新的
            except Exception as e:
                print(f"Topic relevance check failed: {e}")
                # 默认携带上下文
                include_context = bool(conversation_history)

        # 尝试使用 LLM
        if self.llm_service.is_enabled():
            try:
                # 构建上下文
                context = self._build_llm_context(user)

                # 如果需要携带对话历史
                if include_context and conversation_history:
                    context['conversation_history'] = [
                        {'role': h.get('role'), 'content': h.get('content')}
                        for h in conversation_history[-6:]  # 最多 3 轮
                    ]

                result = self.llm_service.chat(message, context)

                # 如果 LLM 返回了有效的操作，则处理并返回
                if result.get("suggested_actions") and not result.get("context", {}).get("error"):
                    # 先检查是否是查询类操作，需要获取实际数据
                    action_type = result["suggested_actions"][0].get("action_type", "")
                    if action_type.startswith("query_") or action_type == "view":
                        response = self._handle_query_action(result, user)
                        response['topic_id'] = new_topic_id
                        return response

                    # 其他操作：增强参数并返回
                    result = self._enhance_actions_with_db_data(result)
                    result['topic_id'] = new_topic_id
                    return result

                # 其他情况回退到规则模式
            except Exception as e:
                # LLM 出错，回退到规则模式
                print(f"LLM error, falling back to rule-based: {e}")

        # 规则模式（后备）
        result = self._process_with_rules(message, user)
        result['topic_id'] = new_topic_id
        return result

    def _build_llm_context(self, user: Employee) -> Dict[str, Any]:
        """构建 LLM 上下文"""
        context = {
            "user_role": user.role.value,
            "user_name": user.name
        }

        # 添加房态摘要
        summary = self.room_service.get_room_status_summary()
        context["room_summary"] = summary

        # 添加可用房型列表（关键：让 LLM 知道有哪些房型）
        room_types = self.room_service.get_room_types()
        context["room_types"] = [
            {
                "id": rt.id,
                "name": rt.name,
                "price": float(rt.base_price)
            }
            for rt in room_types
        ]

        # 添加在住客人（最近5位）
        active_stays = self.checkin_service.get_active_stays()
        context["active_stays"] = [
            {
                "id": s.id,
                "room_number": s.room.room_number,
                "guest_name": s.guest.name,
                "expected_check_out": str(s.expected_check_out)
            }
            for s in active_stays[:5]
        ]

        # 添加待处理任务
        pending_tasks = self.task_service.get_pending_tasks()
        context["pending_tasks"] = [
            {
                "id": t.id,
                "room_number": t.room.room_number,
                "task_type": t.task_type.value
            }
            for t in pending_tasks[:5]
        ]

        # conversation_history 将在 process_message 中添加
        return context

    def _format_conversation_history(self, history: List[Dict]) -> str:
        """格式化对话历史为字符串"""
        if not history:
            return ""

        lines = ["\n**最近对话历史：**"]
        for msg in history:
            role = "用户" if msg.get('role') == 'user' else "助手"
            content = msg.get('content', '')[:200]  # 截断过长内容
            lines.append(f"- {role}: {content}")
        return "\n".join(lines)

    def _enhance_actions_with_db_data(self, result: Dict) -> Dict:
        """使用数据库数据增强 LLM 返回的操作，并进行参数解析"""
        for action in result.get("suggested_actions", []):
            params = action.get("params", {})
            action_type = action.get("action_type", "")

            # ========== 智能参数解析 ==========

            # 解析房型参数 - 支持多种键名
            if "room_type_id" in params or "room_type_name" in params or "room_type" in params:
                room_type_input = params.get("room_type_id") or params.get("room_type_name") or params.get("room_type")
                if room_type_input:
                    parse_result = self.param_parser.parse_room_type(room_type_input)
                    if parse_result.confidence >= 0.7:
                        params["room_type_id"] = parse_result.value
                        # 同时保存房型名称用于显示
                        room_type = self.room_service.get_room_type(parse_result.value)
                        if room_type:
                            params["room_type_name"] = room_type.name
                    else:
                        # 低置信度，需要用户确认
                        action["requires_confirmation"] = True
                        action["candidates"] = parse_result.candidates
                        result["requires_confirmation"] = True
                        result["candidates"] = parse_result.candidates
                        action["params"] = params
                        continue

            # 解析房间参数
            if "room_id" in params or "room_number" in params:
                room_input = params.get("room_id") or params.get("room_number")
                if room_input:
                    parse_result = self.param_parser.parse_room(room_input)
                    if parse_result.confidence >= 0.7:
                        params["room_id"] = parse_result.value
                        if "room_number" not in params and isinstance(parse_result.raw_input, str):
                            params["room_number"] = parse_result.raw_input
                    else:
                        action["requires_confirmation"] = True
                        action["candidates"] = parse_result.candidates
                        result["requires_confirmation"] = True
                        result["candidates"] = parse_result.candidates
                        action["params"] = params
                        continue

            # 解析新房间（换房场景）
            if "new_room_id" in params or "new_room_number" in params:
                room_input = params.get("new_room_id") or params.get("new_room_number")
                if room_input:
                    parse_result = self.param_parser.parse_room(room_input)
                    if parse_result.confidence >= 0.7:
                        params["new_room_id"] = parse_result.value
                    else:
                        action["requires_confirmation"] = True
                        action["candidates"] = parse_result.candidates
                        result["requires_confirmation"] = True
                        result["candidates"] = parse_result.candidates
                        action["params"] = params
                        continue

            # 解析任务分配员工
            if "assignee_id" in params or "assignee_name" in params:
                assignee_input = params.get("assignee_id") or params.get("assignee_name")
                if assignee_input:
                    parse_result = self.param_parser.parse_employee(assignee_input)
                    if parse_result.confidence >= 0.7:
                        params["assignee_id"] = parse_result.value
                    else:
                        action["requires_confirmation"] = True
                        action["candidates"] = parse_result.candidates
                        result["requires_confirmation"] = True
                        result["candidates"] = parse_result.candidates
                        action["params"] = params
                        continue

            # 解析房间状态
            if "status" in params:
                status_result = self.param_parser.parse_room_status(params["status"])
                if status_result.confidence >= 0.7:
                    params["status"] = status_result.value
                else:
                    # 返回可用状态列表让用户选择
                    from app.models.ontology import RoomStatus
                    action["requires_confirmation"] = True
                    action["candidates"] = [
                        {'value': s.value, 'label': s.value}
                        for s in RoomStatus
                    ]
                    action["params"] = params
                    continue

            # ========== 原有的增强逻辑（作为后备） ==========

            # 如果 LLM 返回了房间号但缺少 room_id，补充 room_id
            if "room_number" in params and "room_id" not in params:
                room = self.room_service.get_room_by_number(params["room_number"])
                if room:
                    params["room_id"] = room.id
                    action["entity_id"] = room.id

            # 如果 LLM 返回了客人姓名但缺少 stay_record_id，尝试查找
            if "guest_name" in params and action_type in ["checkout", "extend_stay", "change_room"]:
                stays = self.checkin_service.search_active_stays(params["guest_name"])
                if stays and "stay_record_id" not in params:
                    params["stay_record_id"] = stays[0].id
                    action["entity_id"] = stays[0].id

            # 如果 LLM 返回了预订号但缺少 reservation_id
            if "reservation_no" in params and "reservation_id" not in params:
                reservation = self.reservation_service.get_reservation_by_no(params["reservation_no"])
                if reservation:
                    params["reservation_id"] = reservation.id
                    action["entity_id"] = reservation.id

            # 解析相对日期
            for date_field in ["expected_check_out", "new_check_out_date", "check_in_date", "check_out_date"]:
                if date_field in params:
                    # 先尝试智能参数解析
                    parse_result = self.param_parser.parse_date(params[date_field])
                    if parse_result.confidence > 0:
                        params[date_field] = parse_result.value
                    else:
                        # 回退到原有的相对日期解析
                        parsed_date = self._parse_relative_date(params[date_field])
                        if parsed_date:
                            params[date_field] = parsed_date

            action["params"] = params

        return result

    def _handle_query_action(self, result: Dict, user: Employee) -> Dict:
        """处理查询类操作，获取实际数据替换 LLM 的占位响应"""
        actions = result.get("suggested_actions", [])
        if not actions:
            return result

        action = actions[0]
        action_type = action.get("action_type", "")
        entity_type = action.get("entity_type", "")

        # 根据查询类型获取实际数据
        # query_rooms 或 (view + entity_type 包含 room)
        if action_type == "query_rooms" or (action_type == "view" and "room" in entity_type.lower()):
            return self._query_rooms_response({})

        if action_type == "query_reservations" or (action_type == "view" and "reservation" in entity_type.lower()):
            return self._query_reservations_response({})

        if action_type == "query_guests" or (action_type == "view" and "guest" in entity_type.lower()):
            return self._query_guests_response({})

        if action_type == "query_tasks" or (action_type == "view" and "task" in entity_type.lower()):
            return self._query_tasks_response({})

        if action_type == "query_reports" or (action_type == "view" and "report" in entity_type.lower()):
            return self._query_reports_response()

        # 如果是通用的 view 类型，检查 LLM 返回的 message 来推断查询类型
        if action_type == "view":
            llm_message = result.get("message", "").lower()
            if any(kw in llm_message for kw in ["房态", "房间", "空房"]):
                return self._query_rooms_response({})
            if any(kw in llm_message for kw in ["预订", "预约"]):
                return self._query_reservations_response({})
            if any(kw in llm_message for kw in ["在住", "住客", "客人"]):
                return self._query_guests_response({})
            if any(kw in llm_message for kw in ["任务", "清洁"]):
                return self._query_tasks_response({})
            if any(kw in llm_message for kw in ["入住率", "营收", "报表"]):
                return self._query_reports_response()

        return result

    def _process_with_rules(self, message: str, user: Employee) -> dict:
        """
        使用规则模式处理消息（后备方案）
        """
        # Orient: 意图识别和实体提取
        intent = self._identify_intent(message)
        entities = self._extract_entities(message)

        # Decide: 根据意图生成建议动作
        response = self._generate_response(intent, entities, user)

        return response

    def _identify_intent(self, message: str) -> str:
        """识别用户意图"""
        message_lower = message.lower()

        # 查询类意图
        if any(kw in message_lower for kw in ['查看', '查询', '显示', '有多少', '哪些', '列表', '统计']):
            if any(kw in message_lower for kw in ['房间', '房态', '空房']):
                return 'query_rooms'
            if any(kw in message_lower for kw in ['预订', '预约']):
                return 'query_reservations'
            if any(kw in message_lower for kw in ['在住', '住客', '客人']):
                return 'query_guests'
            if any(kw in message_lower for kw in ['任务', '清洁']):
                return 'query_tasks'
            if any(kw in message_lower for kw in ['入住率', '营收', '报表', '统计']):
                return 'query_reports'

        # 操作类意图
        if any(kw in message_lower for kw in ['入住', '办理入住', 'checkin']):
            return 'action_checkin'
        if any(kw in message_lower for kw in ['退房', '结账', 'checkout']):
            return 'action_checkout'
        if any(kw in message_lower for kw in ['预订', '预约', '订房']):
            return 'action_reserve'
        if any(kw in message_lower for kw in ['换房', '转房']):
            return 'action_change_room'
        if any(kw in message_lower for kw in ['续住', '延期']):
            return 'action_extend'
        if any(kw in message_lower for kw in ['清洁', '打扫']):
            return 'action_cleaning'

        # 帮助
        if any(kw in message_lower for kw in ['帮助', '帮忙', '怎么', '如何', '你好', 'hello', 'hi']):
            return 'help'

        return 'unknown'

    def _extract_entities(self, message: str) -> dict:
        """提取实体"""
        entities = {}

        # 提取房间号
        room_match = re.search(r'(\d{3,4})\s*号?\s*房', message)
        if room_match:
            entities['room_number'] = room_match.group(1)

        # 提取姓名
        name_patterns = [
            r'客人\s*[:：]?\s*(\S+)',
            r'姓名\s*[:：]?\s*(\S+)',
            r'(?:帮|给|为)\s*(\S{2,4})\s*(?:办理|退房|入住)',
            r'(\S{2,4})\s*(?:先生|女士|的房间)'
        ]
        for pattern in name_patterns:
            name_match = re.search(pattern, message)
            if name_match:
                entities['guest_name'] = name_match.group(1)
                break

        # 提取日期
        date_match = re.search(r'(\d{1,2})[月/](\d{1,2})[日号]?', message)
        if date_match:
            month = int(date_match.group(1))
            day = int(date_match.group(2))
            year = date.today().year
            if month < date.today().month:
                year += 1
            entities['date'] = date(year, month, day)

        # 提取房型
        room_type_keywords = {
            '标间': '标间',
            '标准间': '标间',
            '大床': '大床房',
            '大床房': '大床房',
            '豪华': '豪华间',
            '豪华间': '豪华间'
        }
        for kw, rt in room_type_keywords.items():
            if kw in message:
                entities['room_type'] = rt
                break

        return entities

    def _generate_response(self, intent: str, entities: dict, user: Employee) -> dict:
        """生成响应和建议动作"""

        if intent == 'help':
            return self._help_response()

        if intent == 'query_rooms':
            return self._query_rooms_response(entities)

        if intent == 'query_reservations':
            return self._query_reservations_response(entities)

        if intent == 'query_guests':
            return self._query_guests_response(entities)

        if intent == 'query_tasks':
            return self._query_tasks_response(entities)

        if intent == 'query_reports':
            return self._query_reports_response()

        if intent == 'action_checkin':
            return self._checkin_response(entities, user)

        if intent == 'action_checkout':
            return self._checkout_response(entities, user)

        if intent == 'action_reserve':
            return self._reserve_response(entities)

        if intent == 'action_cleaning':
            return self._cleaning_response(entities)

        return {
            'message': '抱歉，我没有理解您的意思。您可以尝试：\n'
                       '- 查看房态\n'
                       '- 查询今日预抵\n'
                       '- 帮王五退房\n'
                       '- 301房入住',
            'suggested_actions': [],
            'context': {'intent': intent, 'entities': entities}
        }

    def _help_response(self) -> dict:
        return {
            'message': '您好！我是酒店智能助手，可以帮您：\n\n'
                       '**查询类：**\n'
                       '- 查看房态 / 有多少空房\n'
                       '- 查询今日预抵\n'
                       '- 查看在住客人\n'
                       '- 查看清洁任务\n'
                       '- 今日入住率\n\n'
                       '**操作类：**\n'
                       '- 帮王五办理入住\n'
                       '- 301房退房\n'
                       '- 预订一间大床房\n\n'
                       '请问有什么可以帮您？',
            'suggested_actions': [],
            'context': {}
        }

    def _query_rooms_response(self, entities: dict) -> dict:
        summary = self.room_service.get_room_status_summary()

        message = f"**当前房态统计：**\n\n"
        message += f"- 总房间数：{summary['total']} 间\n"
        message += f"- 空闲可住：{summary['vacant_clean']} 间 ✅\n"
        message += f"- 已入住：{summary['occupied']} 间 🔴\n"
        message += f"- 待清洁：{summary['vacant_dirty']} 间 🟡\n"
        message += f"- 维修中：{summary['out_of_order']} 间 ⚫\n"

        # 入住率
        sellable = summary['total'] - summary['out_of_order']
        rate = (summary['occupied'] / sellable * 100) if sellable > 0 else 0
        message += f"\n当前入住率：**{rate:.1f}%**"

        actions = []
        if summary['vacant_dirty'] > 0:
            actions.append({
                'action_type': 'view',
                'entity_type': 'task',
                'description': f'查看 {summary["vacant_dirty"]} 间待清洁房间',
                'requires_confirmation': False,
                'params': {'status': 'vacant_dirty'}
            })

        return {
            'message': message,
            'suggested_actions': actions,
            'context': {'room_summary': summary}
        }

    def _query_reservations_response(self, entities: dict) -> dict:
        arrivals = self.reservation_service.get_today_arrivals()

        if not arrivals:
            return {
                'message': '今日暂无预抵客人。',
                'suggested_actions': [],
                'context': {}
            }

        message = f"**今日预抵 ({len(arrivals)} 位客人)：**\n\n"
        actions = []

        for r in arrivals[:5]:  # 最多显示5条
            message += f"- {r.guest.name}，{r.room_type.name}，"
            message += f"预订号 {r.reservation_no}\n"
            actions.append({
                'action_type': 'checkin',
                'entity_type': 'reservation',
                'entity_id': r.id,
                'description': f'为 {r.guest.name} 办理入住',
                'requires_confirmation': True,
                'params': {'reservation_id': r.id, 'guest_name': r.guest.name}
            })

        if len(arrivals) > 5:
            message += f"\n... 还有 {len(arrivals) - 5} 位客人"

        return {
            'message': message,
            'suggested_actions': actions,
            'context': {'arrivals_count': len(arrivals)}
        }

    def _query_guests_response(self, entities: dict) -> dict:
        stays = self.checkin_service.get_active_stays()

        if not stays:
            return {
                'message': '当前没有在住客人。',
                'suggested_actions': [],
                'context': {}
            }

        message = f"**当前在住客人 ({len(stays)} 位)：**\n\n"

        for s in stays[:10]:
            message += f"- {s.room.room_number}号房：{s.guest.name}，"
            message += f"预计 {s.expected_check_out} 离店\n"

        if len(stays) > 10:
            message += f"\n... 还有 {len(stays) - 10} 位客人"

        return {
            'message': message,
            'suggested_actions': [],
            'context': {'guest_count': len(stays)}
        }

    def _query_tasks_response(self, entities: dict) -> dict:
        summary = self.task_service.get_task_summary()
        pending = self.task_service.get_pending_tasks()

        message = f"**任务统计：**\n\n"
        message += f"- 待分配：{summary['pending']} 个\n"
        message += f"- 待执行：{summary['assigned']} 个\n"
        message += f"- 进行中：{summary['in_progress']} 个\n"

        if pending:
            message += f"\n**待分配任务：**\n"
            for t in pending[:5]:
                message += f"- {t.room.room_number}号房 - {t.task_type.value}\n"

        return {
            'message': message,
            'suggested_actions': [],
            'context': {'task_summary': summary}
        }

    def _query_reports_response(self) -> dict:
        stats = self.report_service.get_dashboard_stats()

        message = f"**今日运营概览：**\n\n"
        message += f"- 入住率：**{stats['occupancy_rate']}%**\n"
        message += f"- 今日入住：{stats['today_checkins']} 间\n"
        message += f"- 今日退房：{stats['today_checkouts']} 间\n"
        message += f"- 今日营收：**¥{stats['today_revenue']}**\n"

        return {
            'message': message,
            'suggested_actions': [],
            'context': {'stats': stats}
        }

    def _checkin_response(self, entities: dict, user: Employee) -> dict:
        # 根据实体查找目标
        if 'room_number' in entities:
            room = self.room_service.get_room_by_number(entities['room_number'])
            if room and room.status in [RoomStatus.VACANT_CLEAN, RoomStatus.VACANT_DIRTY]:
                return {
                    'message': f"{room.room_number}号房（{room.room_type.name}）当前空闲，"
                               f"请问是预订入住还是散客入住？",
                    'suggested_actions': [
                        {
                            'action_type': 'walkin_checkin',
                            'entity_type': 'room',
                            'entity_id': room.id,
                            'description': '散客入住',
                            'requires_confirmation': True,
                            'params': {'room_id': room.id}
                        }
                    ],
                    'context': {'room': {'id': room.id, 'number': room.room_number}}
                }

        if 'guest_name' in entities:
            # 搜索预订
            reservations = self.reservation_service.search_reservations(entities['guest_name'])
            confirmed = [r for r in reservations if r.status == ReservationStatus.CONFIRMED]

            if confirmed:
                r = confirmed[0]
                # 获取可用房间
                available = self.room_service.get_available_rooms(
                    r.check_in_date, r.check_out_date, r.room_type_id
                )

                return {
                    'message': f"找到 {r.guest.name} 的预订（{r.room_type.name}，"
                               f"预订号 {r.reservation_no}）。\n"
                               f"有 {len(available)} 间可用房间，请选择房间办理入住。",
                    'suggested_actions': [
                        {
                            'action_type': 'checkin',
                            'entity_type': 'reservation',
                            'entity_id': r.id,
                            'description': f'为 {r.guest.name} 办理入住',
                            'requires_confirmation': True,
                            'params': {
                                'reservation_id': r.id,
                                'available_rooms': [{'id': rm.id, 'number': rm.room_number} for rm in available[:5]]
                            }
                        }
                    ],
                    'context': {'reservation_id': r.id}
                }

        return {
            'message': '请提供客人姓名或房间号，例如：\n'
                       '- 帮王五办理入住\n'
                       '- 301房散客入住',
            'suggested_actions': [],
            'context': {}
        }

    def _checkout_response(self, entities: dict, user: Employee) -> dict:
        stay = None

        if 'room_number' in entities:
            room = self.room_service.get_room_by_number(entities['room_number'])
            if room:
                stay = self.checkin_service.get_stay_by_room(room.id)

        if 'guest_name' in entities:
            stays = self.checkin_service.search_active_stays(entities['guest_name'])
            if stays:
                stay = stays[0]

        if stay:
            bill_info = ""
            if stay.bill:
                balance = stay.bill.total_amount + stay.bill.adjustment_amount - stay.bill.paid_amount
                bill_info = f"\n账单余额：¥{balance}"

            return {
                'message': f"找到 {stay.guest.name} 的住宿记录（{stay.room.room_number}号房）。{bill_info}\n"
                           f"确认办理退房吗？",
                'suggested_actions': [
                    {
                        'action_type': 'checkout',
                        'entity_type': 'stay_record',
                        'entity_id': stay.id,
                        'description': f'为 {stay.guest.name} 办理退房',
                        'requires_confirmation': True,
                        'params': {'stay_record_id': stay.id}
                    }
                ],
                'context': {'stay_record_id': stay.id}
            }

        return {
            'message': '请提供客人姓名或房间号，例如：\n'
                       '- 帮王五退房\n'
                       '- 301房退房',
            'suggested_actions': [],
            'context': {}
        }

    def _reserve_response(self, entities: dict) -> dict:
        room_types = self.room_service.get_room_types()

        message = "请提供预订信息：\n\n"
        message += "**可选房型：**\n"
        for rt in room_types:
            message += f"- {rt.name}：¥{rt.base_price}/晚\n"

        return {
            'message': message,
            'suggested_actions': [
                {
                    'action_type': 'create_reservation',
                    'entity_type': 'reservation',
                    'description': '创建新预订',
                    'requires_confirmation': True,
                    'params': {
                        'room_types': [{'id': rt.id, 'name': rt.name, 'price': float(rt.base_price)} for rt in room_types]
                    }
                }
            ],
            'context': {}
        }

    def _cleaning_response(self, entities: dict) -> dict:
        if 'room_number' in entities:
            room = self.room_service.get_room_by_number(entities['room_number'])
            if room:
                return {
                    'message': f"是否为 {room.room_number}号房 创建清洁任务？",
                    'suggested_actions': [
                        {
                            'action_type': 'create_task',
                            'entity_type': 'task',
                            'description': f'创建 {room.room_number} 清洁任务',
                            'requires_confirmation': True,
                            'params': {'room_id': room.id, 'task_type': 'cleaning'}
                        }
                    ],
                    'context': {}
                }

        # 显示所有脏房
        dirty_rooms = self.room_service.get_rooms(status=RoomStatus.VACANT_DIRTY)
        if dirty_rooms:
            message = f"**待清洁房间 ({len(dirty_rooms)} 间)：**\n\n"
            for r in dirty_rooms:
                message += f"- {r.room_number}号房\n"

            return {
                'message': message,
                'suggested_actions': [],
                'context': {'dirty_rooms': [r.room_number for r in dirty_rooms]}
            }

        return {
            'message': '当前没有待清洁的房间。',
            'suggested_actions': [],
            'context': {}
        }

    def execute_action(self, action: dict, user: Employee) -> dict:
        """
        执行动作 - OODA 循环的 Act 阶段
        所有关键操作都需要人类确认后才能执行
        """
        action_type = action.get('action_type')
        params = action.get('params', {})

        try:
            if action_type == 'checkout':
                from app.models.schemas import CheckOutRequest
                data = CheckOutRequest(stay_record_id=params['stay_record_id'])
                stay = self.checkout_service.check_out(data, user.id)
                return {
                    'success': True,
                    'message': f'退房成功！房间 {stay.room.room_number} 已变为待清洁状态。'
                }

            if action_type == 'create_task':
                from app.models.schemas import TaskCreate

                # 使用智能参数解析房间
                room_result = self.param_parser.parse_room(
                    params.get('room_id') or params.get('room_number')
                )

                if room_result.confidence < 0.7:
                    return {
                        'success': False,
                        'requires_confirmation': True,
                        'action': 'select_room',
                        'message': f'请确认房间："{room_result.raw_input}"',
                        'candidates': room_result.candidates
                    }

                # 解析任务类型
                task_type_result = self.param_parser.parse_task_type(
                    params.get('task_type', params.get('task_name', '清洁'))
                )

                data = TaskCreate(
                    room_id=int(room_result.value),
                    task_type=task_type_result.value if task_type_result.value else TaskType.CLEANING
                )
                task = self.task_service.create_task(data, user.id)
                return {
                    'success': True,
                    'message': f'清洁任务已创建，任务ID：{task.id}'
                }

            if action_type == 'walkin_checkin':
                from app.models.schemas import WalkInCheckIn

                # 使用智能参数解析房间
                room_result = self.param_parser.parse_room(
                    params.get('room_id') or params.get('room_number')
                )

                if room_result.confidence < 0.7:
                    return {
                        'success': False,
                        'requires_confirmation': True,
                        'action': 'select_room',
                        'message': f'请确认房间："{room_result.raw_input}"',
                        'candidates': room_result.candidates
                    }

                # 解理退房日期
                checkout_result = self.param_parser.parse_date(params.get('expected_check_out'))
                if checkout_result.confidence == 0:
                    checkout_result = self.param_parser.parse_date('明天')

                data = WalkInCheckIn(
                    guest_name=params.get('guest_name', '散客'),
                    guest_phone=params.get('guest_phone', ''),
                    guest_id_type=params.get('guest_id_type', '身份证'),
                    guest_id_number=params.get('guest_id_number', ''),
                    room_id=int(room_result.value),
                    expected_check_out=checkout_result.value,
                    deposit_amount=Decimal(str(params.get('deposit_amount', 0)))
                )
                stay = self.checkin_service.walk_in_check_in(data, user.id)
                return {
                    'success': True,
                    'message': f'散客入住成功！{stay.guest.name} 已入住 {stay.room.room_number}号房。'
                }

            if action_type == 'checkin':
                from app.models.schemas import CheckInFromReservation

                # 使用智能参数解析房间
                room_result = self.param_parser.parse_room(
                    params.get('room_id') or params.get('room_number')
                )

                if room_result.confidence < 0.7:
                    return {
                        'success': False,
                        'requires_confirmation': True,
                        'action': 'select_room',
                        'message': f'请确认房间："{room_result.raw_input}"',
                        'candidates': room_result.candidates,
                        'reservation_id': params.get('reservation_id')
                    }

                data = CheckInFromReservation(
                    reservation_id=params['reservation_id'],
                    room_id=int(room_result.value),
                    deposit_amount=Decimal(str(params.get('deposit_amount', 0)))
                )
                stay = self.checkin_service.check_in_from_reservation(data, user.id)
                return {
                    'success': True,
                    'message': f'入住成功！{stay.guest.name} 已入住 {stay.room.room_number}号房。'
                }

            if action_type == 'create_reservation':
                from app.models.schemas import ReservationCreate

                # 使用智能参数解析 - 支持多种参数名
                room_type_input = (
                    params.get('room_type_id') or
                    params.get('room_type_name') or
                    params.get('room_type')  # LLM 可能使用这个键名
                )

                # 如果没有房型参数，提示用户选择
                if not room_type_input:
                    room_types = self.room_service.get_room_types()
                    candidates = [
                        {'id': rt.id, 'name': rt.name, 'price': float(rt.base_price)}
                        for rt in room_types
                    ]
                    return {
                        'success': False,
                        'requires_confirmation': True,
                        'action': 'select_room_type',
                        'message': '请选择房型',
                        'candidates': candidates
                    }

                room_type_result = self.param_parser.parse_room_type(room_type_input)

                # 低置信度处理
                if room_type_result.confidence < 0.7:
                    return {
                        'success': False,
                        'requires_confirmation': True,
                        'action': 'select_room_type',
                        'message': f'请确认房型："{room_type_result.raw_input}"',
                        'candidates': room_type_result.candidates
                    }

                # 解析日期
                check_in_result = self.param_parser.parse_date(params.get('check_in_date'))
                check_out_result = self.param_parser.parse_date(params.get('check_out_date'))

                if check_in_result.confidence == 0:
                    check_in_result = self.param_parser.parse_date('今天')
                if check_out_result.confidence == 0:
                    check_out_result = self.param_parser.parse_date('明天')

                data = ReservationCreate(
                    guest_name=params.get('guest_name', '新客人'),
                    guest_phone=params.get('guest_phone', ''),
                    guest_id_number=params.get('guest_id_number'),
                    room_type_id=int(room_type_result.value),
                    check_in_date=check_in_result.value,
                    check_out_date=check_out_result.value,
                    adult_count=params.get('adult_count', 1),
                    child_count=params.get('child_count', 0),
                    prepaid_amount=Decimal(str(params.get('prepaid_amount', 0)))
                )
                reservation = self.reservation_service.create_reservation(data, user.id)
                return {
                    'success': True,
                    'message': f'预订成功！预订号：{reservation.reservation_no}'
                }

            # 续住
            if action_type == 'extend_stay':
                from app.models.schemas import ExtendStay
                data = ExtendStay(
                    new_check_out_date=params['new_check_out_date']
                )
                stay = self.checkin_service.extend_stay(params['stay_record_id'], data)
                return {
                    'success': True,
                    'message': f'续住成功！新的离店日期：{stay.expected_check_out}'
                }

            # 换房
            if action_type == 'change_room':
                from app.models.schemas import ChangeRoom
                data = ChangeRoom(new_room_id=params['new_room_id'])
                stay = self.checkin_service.change_room(params['stay_record_id'], data, user.id)
                return {
                    'success': True,
                    'message': f'换房成功！已从原房间换至 {stay.room.room_number}号房'
                }

            # 取消预订
            if action_type == 'cancel_reservation':
                from app.models.schemas import ReservationCancel
                data = ReservationCancel(cancel_reason=params.get('cancel_reason', '客人要求取消'))
                reservation = self.reservation_service.cancel_reservation(params['reservation_id'], data)
                return {
                    'success': True,
                    'message': f'预订 {reservation.reservation_no} 已取消'
                }

            # 分配任务
            if action_type == 'assign_task':
                from app.models.schemas import TaskAssign

                # 使用智能参数解析员工
                assignee_result = self.param_parser.parse_employee(
                    params.get('assignee_id') or params.get('assignee_name')
                )

                if assignee_result.confidence < 0.7:
                    # 获取可分配的清洁员列表
                    from app.models.ontology import EmployeeRole
                    cleaners = self.db.query(Employee).filter(
                        Employee.role == EmployeeRole.CLEANER,
                        Employee.is_active == True
                    ).all()
                    candidates = [
                        {'id': e.id, 'name': e.name, 'username': e.username}
                        for e in cleaners
                    ]
                    return {
                        'success': False,
                        'requires_confirmation': True,
                        'action': 'select_assignee',
                        'message': f'请确认分配给："{assignee_result.raw_input}"',
                        'candidates': candidates
                    }

                data = TaskAssign(assignee_id=int(assignee_result.value))
                task = self.task_service.assign_task(params['task_id'], data)
                return {
                    'success': True,
                    'message': f'任务已分配给 {task.assignee.name}'
                }

            # 开始任务
            if action_type == 'start_task':
                task = self.task_service.start_task(params['task_id'], user.id)
                return {
                    'success': True,
                    'message': f'任务已开始'
                }

            # 完成任务
            if action_type == 'complete_task':
                task = self.task_service.complete_task(
                    params['task_id'],
                    user.id,
                    params.get('notes')
                )
                return {
                    'success': True,
                    'message': f'任务已完成！房间 {task.room.room_number} 已变为空闲可住状态'
                }

            # 添加支付
            if action_type == 'add_payment':
                from app.models.schemas import PaymentCreate
                from app.models.ontology import PaymentMethod
                data = PaymentCreate(
                    bill_id=params['bill_id'],
                    amount=Decimal(str(params['amount'])),
                    method=PaymentMethod(params.get('method', 'cash')),
                    remark=params.get('remark')
                )
                payment = self.billing_service.add_payment(data, user.id)
                return {
                    'success': True,
                    'message': f'收款成功！金额：¥{payment.amount}'
                }

            # 账单调整（仅经理）
            if action_type == 'adjust_bill':
                from app.models.schemas import BillAdjustment
                if user.role.value != 'manager':
                    return {
                        'success': False,
                        'message': '只有经理可以调整账单'
                    }
                data = BillAdjustment(
                    bill_id=params['bill_id'],
                    adjustment_amount=Decimal(str(params['adjustment_amount'])),
                    reason=params.get('reason', 'AI操作调整')
                )
                bill = self.billing_service.adjust_bill(data, user.id)
                return {
                    'success': True,
                    'message': f'账单已调整，调整金额：¥{bill.adjustment_amount}'
                }

            # 修改房态
            if action_type == 'update_room_status':
                # 使用智能参数解析房间
                room_result = self.param_parser.parse_room(
                    params.get('room_id') or params.get('room_number')
                )

                if room_result.confidence < 0.7:
                    return {
                        'success': False,
                        'requires_confirmation': True,
                        'action': 'select_room',
                        'message': f'请确认房间："{room_result.raw_input}"',
                        'candidates': room_result.candidates
                    }

                # 解析房间状态
                status_result = self.param_parser.parse_room_status(params.get('status'))

                if status_result.confidence == 0:
                    return {
                        'success': False,
                        'message': f'无法理解房间状态：{params.get("status")}'
                    }

                room = self.room_service.update_room_status(
                    int(room_result.value),
                    status_result.value
                )
                return {
                    'success': True,
                    'message': f'{room.room_number}号房状态已更新为 {room.status.value}'
                }

            return {
                'success': False,
                'message': f'不支持的操作类型：{action_type}'
            }

        except ValueError as e:
            return {
                'success': False,
                'message': f'操作失败：{str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'系统错误：{str(e)}'
            }
