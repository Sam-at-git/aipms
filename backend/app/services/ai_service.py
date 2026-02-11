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

SPEC-54: 集成新的 core/ai/ 模块，保持向后兼容
"""
import json
import re
import logging
from typing import Optional, List, Dict, Any, Union, TYPE_CHECKING
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.ontology import (
    Room, RoomStatus, RoomType, Guest, Reservation, ReservationStatus,
    StayRecord, StayRecordStatus, Task, TaskType, TaskStatus, Employee
)

logger = logging.getLogger(__name__)
from app.services.room_service import RoomService
from app.services.reservation_service import ReservationService
from app.services.checkin_service import CheckInService
from app.services.checkout_service import CheckOutService
from app.services.task_service import TaskService
from app.services.billing_service import BillingService
from app.services.report_service import ReportService
from app.services.llm_service import LLMService, TopicRelevance
from app.services.param_parser_service import ParamParserService
from app.models.schemas import MissingField

# 导入新的 core/ai/ 模块 (SPEC-28, 29, 30)
try:
    from core.ai import (
        OpenAICompatibleClient,
        PromptBuilder,
        PromptContext,
        ConfirmByRiskStrategy,
        ConfirmationLevel,
    )
    CORE_AI_AVAILABLE = True
except ImportError:
    CORE_AI_AVAILABLE = False

# 导入业务规则模块 (SPEC-47, 48, 49)
try:
    from core.domain.rules import (
        register_all_rules,
        calculate_room_price,
        calculate_guest_tier,
    )
    CORE_RULES_AVAILABLE = True
except ImportError:
    CORE_RULES_AVAILABLE = False

# 导入元数据配置 (SPEC-21, 53)
try:
    from core.domain.metadata import (
        get_security_level,
        get_action_requirements,
        should_skip_confirmation,
    )
    CORE_METADATA_AVAILABLE = True
except ImportError:
    CORE_METADATA_AVAILABLE = False

# 导入 DebugLogger (调试追踪)
try:
    from core.ai.debug_logger import DebugLogger
    DEBUG_LOGGER_AVAILABLE = True
except ImportError:
    DEBUG_LOGGER_AVAILABLE = False


class SystemCommandHandler:
    """处理以 # 开头的系统指令（仅 sysadmin）"""

    # 已知实体名映射（支持大小写和中文）
    ENTITY_ALIASES = {
        'room': 'Room', 'rooms': 'Room', '房间': 'Room',
        'guest': 'Guest', 'guests': 'Guest', '客人': 'Guest',
        'reservation': 'Reservation', 'reservations': 'Reservation', '预订': 'Reservation',
        'stayrecord': 'StayRecord', 'stay': 'StayRecord', '住宿': 'StayRecord',
        'task': 'Task', 'tasks': 'Task', '任务': 'Task',
        'bill': 'Bill', 'bills': 'Bill', '账单': 'Bill',
        'employee': 'Employee', 'employees': 'Employee', '员工': 'Employee',
        'roomtype': 'RoomType', '房型': 'RoomType',
    }

    def is_system_command(self, message: str) -> bool:
        """判断是否为系统指令（# 后跟字母或中文，不跟数字）"""
        msg = message.strip()
        if not msg.startswith('#'):
            return False
        if len(msg) < 2:
            return False
        # # 后面紧跟数字的不算系统指令（如 #123）
        second_char = msg[1]
        return not second_char.isdigit()

    def execute(self, command: str, user: Employee, db: Session) -> dict:
        """执行系统指令"""
        from app.models.ontology import EmployeeRole

        if user.role != EmployeeRole.SYSADMIN:
            return {
                'message': '系统指令仅限系统管理员使用。',
                'suggested_actions': [],
                'context': {'type': 'system_command', 'command': command}
            }

        cmd = command.strip().lstrip('#').strip()

        # 处理 "查询XXX对象定义" 模式
        if cmd.startswith('查询') and '对象' in cmd:
            entity_name = cmd.replace('查询', '').replace('对象定义', '').replace('对象', '').strip()
            return self._query_entity(entity_name, db)

        # 处理 "日志" / "logs" 命令
        if cmd.lower() in ('日志', 'logs', 'log', '审计日志'):
            return self._query_logs(db)

        # 默认尝试作为实体名查询
        return self._query_entity(cmd, db)

    def _query_entity(self, name: str, db: Session) -> dict:
        """查询实体元数据"""
        # 查找实体名
        lookup = name.lower().strip()
        entity_name = self.ENTITY_ALIASES.get(lookup, name)

        try:
            from app.services.ontology_metadata_service import OntologyMetadataService
            service = OntologyMetadataService(db)
            semantic = service.get_semantic_metadata()

            # 查找匹配的实体
            for entity in semantic.get('entities', []):
                if entity.get('name', '').lower() == entity_name.lower():
                    attrs = entity.get('attributes', [])
                    lines = [f"**{entity_name}** 对象定义：\n"]
                    lines.append(f"描述: {entity.get('description', 'N/A')}")
                    lines.append(f"数据表: {entity.get('table_name', 'N/A')}")
                    lines.append(f"\n属性列表 ({len(attrs)} 个):")
                    for attr in attrs:
                        attr_line = f"  - {attr['name']}: {attr.get('type', 'unknown')}"
                        if attr.get('primary'):
                            attr_line += ' [主键]'
                        if attr.get('nullable') is False:
                            attr_line += ' [必填]'
                        lines.append(attr_line)

                    return {
                        'message': '\n'.join(lines),
                        'suggested_actions': [],
                        'context': {'type': 'system_command', 'entity': entity_name}
                    }

            # 未找到，列出可用实体
            available = [e.get('name', '') for e in semantic.get('entities', [])]
            return {
                'message': f"未找到实体 '{name}'。可用实体: {', '.join(available)}",
                'suggested_actions': [],
                'context': {'type': 'system_command'}
            }
        except Exception as e:
            return {
                'message': f"查询实体信息失败: {str(e)}",
                'suggested_actions': [],
                'context': {'type': 'system_command'}
            }

    def _query_logs(self, db: Session) -> dict:
        """查询最近审计日志"""
        try:
            from app.services.audit_service import AuditService
            service = AuditService(db)
            logs = service.get_logs(limit=10)
            if not logs:
                return {
                    'message': '暂无审计日志。',
                    'suggested_actions': [],
                    'context': {'type': 'system_command', 'command': 'logs'}
                }
            lines = ["最近 10 条审计日志：\n"]
            for log in logs:
                lines.append(
                    f"- [{log.created_at}] {log.action} {log.entity_type}"
                    f"#{log.entity_id} by user#{log.operator_id}"
                )
            return {
                'message': '\n'.join(lines),
                'suggested_actions': [],
                'context': {'type': 'system_command', 'command': 'logs'}
            }
        except Exception as e:
            return {
                'message': f"查询日志失败: {str(e)}",
                'suggested_actions': [],
                'context': {'type': 'system_command', 'command': 'logs'}
            }


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
        self.system_command_handler = SystemCommandHandler()

        # SPEC-08: ActionRegistry (lazy initialized)
        self._action_registry = None

        # SPEC-19/20/21: OAG components (lazy initialized)
        self._intent_router = None
        self._query_compiler = None
        self._response_generator = None

        # DebugLogger (调试追踪)
        self.debug_logger = DebugLogger() if DEBUG_LOGGER_AVAILABLE else None

        # 初始化新的 core/ai/ 组件 (如果可用)
        self._init_core_components()

    def _init_core_components(self):
        """初始化 core/ai/ 组件"""
        self.use_core_ai = CORE_AI_AVAILABLE
        self.use_core_rules = CORE_RULES_AVAILABLE
        self.use_core_metadata = CORE_METADATA_AVAILABLE

        # 创建 LLM 客户端
        if self.use_core_ai:
            self.llm_client = OpenAICompatibleClient()
            self.prompt_builder = PromptBuilder()
            self.hitl_strategy = ConfirmByRiskStrategy()
        else:
            self.llm_client = None
            self.prompt_builder = None
            self.hitl_strategy = None

        # 注册业务规则
        if self.use_core_rules:
            from core.engine.rule_engine import rule_engine
            try:
                register_all_rules(rule_engine)
            except Exception:
                pass  # 规则可能已经注册

    # ========== SPEC-08: ActionRegistry 集成 ==========

    def get_action_registry(self):
        """
        获取全局动作注册表实例（懒加载）。

        SPEC-08: 集成 ActionRegistry 到 AIService

        Returns:
            ActionRegistry 实例
        """
        if self._action_registry is None:
            try:
                from app.services.actions import get_action_registry
                self._action_registry = get_action_registry()
                logger.info(f"ActionRegistry initialized with {len(self._action_registry.list_actions())} actions")
            except Exception as e:
                logger.warning(f"Failed to initialize ActionRegistry: {e}")
                self._action_registry = False  # 标记为不可用
        return self._action_registry if self._action_registry is not False else None

    def use_action_registry(self) -> bool:
        """
        检查是否可以使用 ActionRegistry。

        Returns:
            True 如果 ActionRegistry 可用
        """
        registry = self.get_action_registry()
        return registry is not None

    # ========== SPEC-19/20/21: OAG Component Accessors ==========

    def _get_intent_router(self):
        """Get IntentRouter instance (SPEC-19)"""
        if self._intent_router is None:
            try:
                from core.ai.intent_router import IntentRouter
                from core.ontology.registry import OntologyRegistry
                registry = self.get_action_registry()
                ontology_reg = OntologyRegistry()
                self._intent_router = IntentRouter(
                    action_registry=registry,
                    ontology_registry=ontology_reg
                )
            except Exception as e:
                logger.debug(f"IntentRouter not available: {e}")
                self._intent_router = False
        return self._intent_router if self._intent_router is not False else None

    def _get_query_compiler(self):
        """Get OntologyQueryCompiler instance (SPEC-20)"""
        if self._query_compiler is None:
            try:
                from core.ai.query_compiler import OntologyQueryCompiler
                from core.ontology.registry import OntologyRegistry
                ontology_reg = OntologyRegistry()
                rule_applicator = None
                try:
                    from core.ontology.rule_applicator import RuleApplicator
                    rule_applicator = RuleApplicator(ontology_reg)
                except Exception:
                    pass
                self._query_compiler = OntologyQueryCompiler(
                    registry=ontology_reg,
                    rule_applicator=rule_applicator
                )
            except Exception as e:
                logger.debug(f"QueryCompiler not available: {e}")
                self._query_compiler = False
        return self._query_compiler if self._query_compiler is not False else None

    def _get_response_generator(self):
        """Get ResponseGenerator instance (SPEC-21)"""
        if self._response_generator is None:
            try:
                from core.ai.response_generator import ResponseGenerator
                self._response_generator = ResponseGenerator(language="zh")
            except Exception as e:
                logger.debug(f"ResponseGenerator not available: {e}")
                self._response_generator = False
        return self._response_generator if self._response_generator is not False else None

    def _try_oag_path(self, message: str, user: Employee) -> dict:
        """
        Try the OAG (Ontology Action Graph) fast path (SPEC-19/20/21)

        Steps:
        1. extract_intent (LLM or rule-based)
        2. IntentRouter.route() for action/query identification
        3. If query + high confidence → QueryCompiler → execute
        4. If mutation + high confidence → extract_params → return for confirmation
        5. If low confidence → return None (fall through to LLM path)

        Returns:
            Response dict if OAG handled it, or None to fall through
        """
        router = self._get_intent_router()
        if not router:
            return None

        # Step 1: Extract intent
        intent_data = self.llm_service.extract_intent(message)

        # Step 2: Route intent
        try:
            from core.ai.intent_router import ExtractedIntent
            intent = ExtractedIntent(
                entity_mentions=intent_data.get("entity_mentions", []),
                action_hints=intent_data.get("action_hints", []),
                extracted_params=intent_data.get("extracted_values", {}),
                time_references=intent_data.get("time_references", []),
            )
            routing = router.route(intent, user_role=user.role if hasattr(user, 'role') else "admin")
        except Exception as e:
            logger.debug(f"OAG routing failed: {e}")
            return None

        # Step 3: Check confidence threshold (lowered to 0.7 to catch more cases)
        if routing.confidence < 0.7:
            return None  # Low confidence, fall through to LLM

        # Step 4: Handle query actions via QueryCompiler (SPEC-20)
        if routing.action and routing.action.startswith("query") or routing.action == "ontology_query":
            return self._oag_handle_query(intent, routing, user)

        # Step 5: Handle mutation actions (SPEC-19)
        if routing.action:
            return self._oag_handle_mutation(intent, routing, message, user)

        return None

    def _oag_handle_query(self, intent, routing, user) -> dict:
        """Handle query intent via OAG path (SPEC-20)"""
        compiler = self._get_query_compiler()
        if not compiler:
            return None

        try:
            from core.ai.query_compiler import ExtractedQuery
            extracted = ExtractedQuery(
                target_entity_hint=intent.entity_mentions[0] if intent.entity_mentions else None,
                target_fields_hint=[],
                conditions=[
                    {"field": k, "operator": "eq", "value": v}
                    for k, v in intent.extracted_params.items()
                ],
            )
            compilation = compiler.compile(extracted)

            if compilation.confidence < 0.7 or compilation.fallback_needed:
                return None  # Fall through to LLM

            # Execute compiled query
            if compilation.query:
                from core.ontology.query_engine import QueryEngine
                engine = QueryEngine()
                results = engine.execute(self.db, compilation.query)

                # Format via ResponseGenerator (SPEC-21)
                resp_gen = self._get_response_generator()
                if resp_gen:
                    from core.ai.response_generator import OntologyResult
                    onto_result = OntologyResult(
                        result_type="query_result",
                        data={
                            "results": results if isinstance(results, list) else [],
                            "entity": compilation.query.root_object,
                            "total": len(results) if isinstance(results, list) else 0,
                        },
                        entity_type=compilation.query.root_object,
                    )
                    formatted = resp_gen.generate(onto_result)
                    return {
                        "message": formatted,
                        "suggested_actions": [],
                        "context": {"oag_path": True, "confidence": compilation.confidence},
                        "query_result": results if isinstance(results, list) else [],
                    }
        except Exception as e:
            logger.debug(f"OAG query compilation failed: {e}")

        return None

    def _oag_handle_mutation(self, intent, routing, message, user) -> dict:
        """Handle mutation intent via OAG path (SPEC-19)"""
        registry = self.get_action_registry()
        if not registry:
            return None

        action_def = registry.get_action(routing.action)
        if not action_def:
            return None

        # Extract params via LLM slot-filling (SPEC-16)
        schema = {}
        if action_def.parameters_schema:
            try:
                schema = action_def.parameters_schema.model_json_schema()
            except Exception:
                pass

        param_result = self.llm_service.extract_params(
            message, schema, intent.extracted_params
        )

        # Format response via ResponseGenerator (SPEC-21)
        resp_gen = self._get_response_generator()

        if param_result.get("missing"):
            # Missing fields - ask for more info
            if resp_gen:
                from core.ai.response_generator import OntologyResult
                onto_result = OntologyResult(
                    result_type="missing_fields",
                    data={
                        "missing": param_result["missing"],
                        "action_name": routing.action,
                    },
                    action_name=routing.action,
                )
                formatted = resp_gen.generate(onto_result)
            else:
                formatted = f"执行 {routing.action} 还需要以下信息：" + ", ".join(param_result["missing"])

            return {
                "message": formatted,
                "suggested_actions": [{
                    "action_type": routing.action,
                    "entity_type": action_def.entity,
                    "description": action_def.description,
                    "params": param_result["params"],
                    "requires_confirmation": False,
                    "missing_fields": param_result["missing"],
                }],
                "context": {"oag_path": True, "confidence": routing.confidence},
            }

        # All params collected - return for confirmation
        if resp_gen:
            from core.ai.response_generator import OntologyResult
            onto_result = OntologyResult(
                result_type="action_needs_confirm",
                data={
                    "action_name": routing.action,
                    "params": param_result["params"],
                    "description": action_def.description,
                },
                action_name=routing.action,
            )
            formatted = resp_gen.generate(onto_result)
        else:
            formatted = f"请确认执行：{action_def.description}"

        return {
            "message": formatted,
            "suggested_actions": [{
                "action_type": routing.action,
                "entity_type": action_def.entity,
                "description": action_def.description,
                "params": param_result["params"],
                "requires_confirmation": True,
            }],
            "context": {"oag_path": True, "confidence": routing.confidence},
        }

    def dispatch_via_registry(
        self,
        action_name: str,
        params: dict,
        user: Employee
    ) -> dict:
        """
        通过 ActionRegistry 分发动作。

        SPEC-08: 新推荐的动作执行方式

        Args:
            action_name: 动作名称（如 "walkin_checkin"）
            params: 参数字典
            user: 当前用户

        Returns:
            {
                "success": True/False,
                "message": "...",
                "data": {...}  # 可选，动作返回的数据
            }

        Raises:
            ValueError: 动作不存在
            ValidationError: 参数验证失败
            PermissionError: 权限不足
        """
        registry = self.get_action_registry()
        if registry is None:
            raise ValueError("ActionRegistry is not available")

        context = {
            "db": self.db,
            "user": user,
            "param_parser": self.param_parser
        }

        result = registry.dispatch(action_name, params, context)

        # 统一返回格式
        return {
            "success": result.get("success", True),
            "message": result.get("message", ""),
            "data": {k: v for k, v in result.items() if k not in ("success", "message")}
        }

    def get_relevant_tools(self, query: str, top_k: int = 5) -> list:
        """
        获取相关工具（OpenAI Tools 格式）。

        SPEC-08: 用于动态工具注入到 LLM 提示词

        Args:
            query: 用户查询（用于语义搜索）
            top_k: 返回工具数量上限

        Returns:
            [
                {
                    "type": "function",
                    "function": {
                        "name": "walkin_checkin",
                        "description": "...",
                        "parameters": {...JSON Schema...}
                    }
                },
                ...
        """
        registry = self.get_action_registry()
        if registry is None:
            return []

        # 如果 ActionRegistry 支持 get_relevant_tools，使用它
        if hasattr(registry, 'get_relevant_tools'):
            return registry.get_relevant_tools(query, top_k)

        # 否则返回所有工具
        return registry.export_all_tools()

    def list_registered_actions(self) -> list:
        """
        列出所有已注册的动作。

        SPEC-08: 用于 API 端点

        Returns:
            动作定义列表
        """
        registry = self.get_action_registry()
        if registry is None:
            return []

        return [
            {
                "name": action.name,
                "entity": action.entity,
                "description": action.description,
                "category": action.category,
                "requires_confirmation": action.requires_confirmation,
                "allowed_roles": list(action.allowed_roles),
                "undoable": action.undoable,
                "parameters": action.parameters_schema.model_json_schema()
            }
            for action in registry.list_actions()
        ]

    # ========== SPEC-08 End ==========

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

        # 明天/明日（注意：单独的"明"会匹配包含它的词，如"明天"、"明日"等）
        if date_str in ["明天", "明日", "明晚", "明早"]:
            return date.today() + timedelta(days=1)
        if date_str == "明":
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

    # 各操作类型必需的参数定义
    ACTION_REQUIRED_PARAMS = {
        'walkin_checkin': ['room_number', 'guest_name', 'guest_phone', 'expected_check_out'],
        'create_reservation': ['guest_name', 'guest_phone', 'room_type_id', 'check_in_date', 'check_out_date'],
        'checkin': ['reservation_id', 'room_number'],
        'checkout': ['stay_record_id'],
        'extend_stay': ['stay_record_id', 'new_check_out_date'],
        'change_room': ['stay_record_id', 'new_room_number'],
        'create_task': ['room_number', 'task_type'],
    }

    def _validate_action_params(
        self,
        action_type: str,
        params: dict,
        user: Employee
    ) -> tuple[bool, list[MissingField], str]:
        """
        校验操作参数是否完整

        Returns:
            (is_valid, missing_fields, error_message)
        """
        if action_type not in self.ACTION_REQUIRED_PARAMS:
            # 不需要校验的操作类型
            return True, [], ""

        required = self.ACTION_REQUIRED_PARAMS.get(action_type, [])
        missing = []
        collected = {}

        for param in required:
            value = params.get(param)
            if not value or (isinstance(value, str) and not value.strip()):
                # 参数缺失，生成 MissingField
                field_def = self._get_field_definition(action_type, param, params)
                if field_def:
                    missing.append(field_def)
            else:
                collected[param] = value

        # 特殊校验：日期合理性
        if 'check_in_date' in params and 'check_out_date' in params:
            if params['check_in_date'] and params['check_out_date']:
                # 这里可以添加日期比较逻辑，但需要先解析日期字符串
                pass

        is_valid = len(missing) == 0
        error_message = f"需要补充信息：{', '.join([f.display_name for f in missing])}" if missing else ""

        return is_valid, missing, error_message

    def _get_field_definition(
        self,
        action_type: str,
        param_name: str,
        current_params: dict
    ) -> Optional[MissingField]:
        """获取字段定义（用于生成追问表单）"""
        field_definitions = {
            'room_number': MissingField(
                field_name='room_number',
                display_name='房间号',
                field_type='text',
                placeholder='如：201',
                required=True
            ),
            'guest_name': MissingField(
                field_name='guest_name',
                display_name='客人姓名',
                field_type='text',
                placeholder='请输入客人姓名',
                required=True
            ),
            'guest_phone': MissingField(
                field_name='guest_phone',
                display_name='联系电话',
                field_type='text',
                placeholder='请输入手机号',
                required=True
            ),
            'room_type_id': MissingField(
                field_name='room_type_id',
                display_name='房型',
                field_type='select',
                options=self._get_room_type_options(),
                placeholder='请选择房型',
                required=True
            ),
            'check_in_date': MissingField(
                field_name='check_in_date',
                display_name='入住日期',
                field_type='date',
                placeholder='如：今天、明天、2025-02-05',
                required=True
            ),
            'check_out_date': MissingField(
                field_name='check_out_date',
                display_name='离店日期',
                field_type='date',
                placeholder='如：明天、后天、2025-02-06',
                required=True
            ),
            'expected_check_out': MissingField(
                field_name='expected_check_out',
                display_name='预计离店日期',
                field_type='date',
                placeholder='如：明天、后天',
                required=True
            ),
            'new_room_number': MissingField(
                field_name='new_room_number',
                display_name='新房间号',
                field_type='text',
                placeholder='请输入目标房间号',
                required=True
            ),
            'stay_record_id': MissingField(
                field_name='stay_record_id',
                display_name='住宿记录',
                field_type='select',
                options=self._get_active_stay_options(),
                placeholder='请选择客人',
                required=True
            ),
            'reservation_id': MissingField(
                field_name='reservation_id',
                display_name='预订记录',
                field_type='select',
                options=self._get_reservation_options(),
                placeholder='请选择预订',
                required=True
            ),
            'task_type': MissingField(
                field_name='task_type',
                display_name='任务类型',
                field_type='select',
                options=[
                    {'value': 'cleaning', 'label': '清洁'},
                    {'value': 'maintenance', 'label': '维修'}
                ],
                placeholder='请选择任务类型',
                required=True
            ),
        }
        return field_definitions.get(param_name)

    def _get_room_type_options(self) -> list[dict]:
        """获取房型选项列表"""
        room_types = self.room_service.get_room_types()
        return [
            {'value': str(rt.id), 'label': f'{rt.name} ¥{rt.base_price}/晚'}
            for rt in room_types
        ]

    def _get_active_stay_options(self) -> list[dict]:
        """获取在住客人选项列表"""
        stays = self.checkin_service.get_active_stays()
        return [
            {'value': str(s.id), 'label': f'{s.room.room_number}号房 - {s.guest.name}'}
            for s in stays
        ]

    def _get_reservation_options(self) -> list[dict]:
        """获取今日预订选项列表"""
        reservations = self.reservation_service.get_today_arrivals()
        return [
            {'value': str(r.id), 'label': f'{r.reservation_no} - {r.guest.name} ({r.room_type.name})'}
            for r in reservations
        ]

    def _generate_followup_response(
        self,
        action_type: str,
        action_description: str,
        params: dict,
        missing_fields: list[MissingField],
        entity_type: str = "unknown"
    ) -> dict:
        """
        生成追问响应

        Args:
            action_type: 操作类型
            action_description: 操作描述
            params: 已收集的参数
            missing_fields: 缺失的字段列表
            entity_type: 实体类型

        Returns:
            包含追问信息的响应字典
        """
        # 生成自然语言追问消息
        collected_info = []
        for key, value in params.items():
            if value:
                # 转换参数名为显示名称
                display_names = {
                    'guest_name': '客人',
                    'guest_phone': '电话',
                    'room_type': '房型',
                    'room_number': '房间号',
                    'check_in_date': '入住日期',
                    'check_out_date': '离店日期',
                    'expected_check_out': '预计离店',
                }
                name = display_names.get(key, key)
                collected_info.append(f"- {name}：{value}")

        message = action_description or "请补充以下信息："
        if collected_info:
            message += f"\n\n已收集信息：\n" + "\n".join(collected_info)
        message += f"\n\n还需要补充：{', '.join([f.display_name for f in missing_fields])}"

        return {
            'message': message,
            'suggested_actions': [{
                'action_type': action_type,
                'entity_type': entity_type,
                'description': action_description,
                'requires_confirmation': False,
                'params': params,
                'missing_fields': [f.model_dump() for f in missing_fields]
            }],
            'follow_up': {
                'action_type': action_type,
                'message': message,
                'missing_fields': [f.model_dump() for f in missing_fields],
                'collected_fields': params,
                'context': {}
            },
            'context': {
                'collected_fields': params,
                'action_type': action_type
            }
        }

    def _process_followup_input(
        self,
        message: str,
        follow_up_context: dict,
        user: Employee
    ) -> dict:
        """
        处理追问模式的用户输入

        Args:
            message: 用户新输入
            follow_up_context: 追问上下文，包含 action_type 和 collected_fields
            user: 当前用户

        Returns:
            处理后的响应
        """
        action_type = follow_up_context.get('action_type', '')
        collected_params = follow_up_context.get('collected_fields', {})

        # 构建上下文
        context = self._build_llm_context(user)

        # 使用 LLM 解析用户输入
        prev_missing_fields = follow_up_context.get('missing_fields')
        llm_result = self.llm_service.parse_followup_input(
            user_input=message,
            action_type=action_type,
            collected_params=collected_params,
            context=context,
            missing_fields=prev_missing_fields
        )

        # LLM 返回的合并后参数
        merged_params = llm_result.get('params', {})
        is_complete = llm_result.get('is_complete', False)
        missing_fields_data = llm_result.get('missing_fields', [])

        # 获取实体类型（定义在外面，两种路径都需要）
        entity_types = {
            'walkin_checkin': 'stay_record',
            'create_reservation': 'reservation',
            'checkin': 'stay_record',
            'checkout': 'stay_record',
            'extend_stay': 'stay_record',
            'change_room': 'stay_record',
            'create_task': 'task',
        }

        # 如果信息完整，生成可执行的操作
        if is_complete:
            # 增强参数（添加数据库验证后的值）
            enhanced_result = self._enhance_single_action_params(
                action_type, merged_params, user
            )

            entity_type = entity_types.get(action_type, 'unknown')

            # 生成操作描述
            descriptions = {
                'walkin_checkin': f"为 {merged_params.get('guest_name')} 办理散客入住",
                'create_reservation': f"创建 {merged_params.get('guest_name')} 的预订",
                'checkin': "办理预订入住",
                'checkout': "办理退房",
                'extend_stay': f"为客人续住",
                'change_room': "为客人换房",
                'create_task': f"创建任务",
            }

            result = {
                'message': llm_result.get('message', ''),
                'suggested_actions': [{
                    'action_type': action_type,
                    'entity_type': entity_type,
                    'description': descriptions.get(action_type, action_type),
                    'requires_confirmation': True,
                    'params': enhanced_result,
                    # 确保不包含 missing_fields，避免前端判断错误
                    # 注意：不设置 missing_fields 字段，让它不出现在响应中
                }],
                'context': {},
                'follow_up': None
            }
            print(f"DEBUG: Returning complete action - {action_type}, requires_confirmation: True")
            return result

        # 信息仍不完整，继续追问
        else:
            # 将 LLM 返回的 missing_fields 转换为 MissingField 对象
            missing_fields = [
                MissingField(**f) for f in missing_fields_data
            ] if missing_fields_data else []

            # 如果没有 missing_fields 但 is_complete=false，用后端校验
            if not missing_fields:
                is_valid, missing_fields, _ = self._validate_action_params(
                    action_type, merged_params, user
                )

            if missing_fields:
                # 继续追问
                descriptions = {
                    'walkin_checkin': f"办理散客入住",
                    'create_reservation': f"创建预订",
                    'checkin': "办理入住",
                    'checkout': "办理退房",
                    'extend_stay': "续住",
                    'change_room': "换房",
                    'create_task': "创建任务",
                }

                return self._generate_followup_response(
                    action_type=action_type,
                    action_description=descriptions.get(action_type, action_type),
                    params=merged_params,
                    missing_fields=missing_fields,
                    entity_type=entity_types.get(action_type, 'unknown')
                )

            # 没有缺失字段，信息完整！返回确认操作
            # （LLM 可能误判为 is_complete=false，但后端校验发现信息完整）
            entity_type = entity_types.get(action_type, 'unknown')
            descriptions = {
                'walkin_checkin': f"为 {merged_params.get('guest_name')} 办理散客入住",
                'create_reservation': f"创建 {merged_params.get('guest_name')} 的预订",
                'checkin': "办理预订入住",
                'checkout': "办理退房",
                'extend_stay': f"为客人续住",
                'change_room': "为客人换房",
                'create_task': f"创建任务",
            }

            return {
                'message': llm_result.get('message', f"{descriptions.get(action_type, action_type)}，确认办理吗？"),
                'suggested_actions': [{
                    'action_type': action_type,
                    'entity_type': entity_type,
                    'description': descriptions.get(action_type, action_type),
                    'requires_confirmation': True,
                    'params': merged_params
                }],
                'context': {},
                'follow_up': None
            }

    def _enhance_single_action_params(
        self,
        action_type: str,
        params: dict,
        user: Employee
    ) -> dict:
        """
        增强单个操作的参数（添加数据库验证后的值）

        这是 _enhance_actions_with_db_data 的简化版本，用于追问模式
        """
        enhanced_params = params.copy()

        # 解析房型参数
        if "room_type" in params and params["room_type"]:
            room_type_input = params["room_type"]
            parse_result = self.param_parser.parse_room_type(str(room_type_input))
            if parse_result.confidence >= 0.7:
                enhanced_params["room_type_id"] = parse_result.value
                room_type = self.room_service.get_room_type(parse_result.value)
                if room_type:
                    enhanced_params["room_type_name"] = room_type.name

        # 解析房间参数
        if "room_number" in params and params["room_number"]:
            room_input = params["room_number"]
            parse_result = self.param_parser.parse_room(str(room_input))
            if parse_result.confidence >= 0.7:
                enhanced_params["room_id"] = parse_result.value

        # 解析新房间（换房场景）
        if "new_room_number" in params and params["new_room_number"]:
            room_input = params["new_room_number"]
            parse_result = self.param_parser.parse_room(str(room_input))
            if parse_result.confidence >= 0.7:
                enhanced_params["new_room_id"] = parse_result.value

        return enhanced_params

    def process_message(
        self,
        message: str,
        user: Employee,
        conversation_history: list = None,
        topic_id: str = None,
        follow_up_context: dict = None,
        language: str = None
    ) -> dict:
        """
        处理用户消息 - OODA 循环入口

        优先使用 LLM，失败时回退到规则匹配

        Args:
            message: 用户消息
            user: 当前用户
            conversation_history: 历史对话消息列表（可选）
            topic_id: 当前话题 ID（可选）
            follow_up_context: 追问上下文（包含 action_type 和 collected_fields）

        Returns:
            包含 message, suggested_actions, context, topic_id 的字典
        """
        message = message.strip()
        new_topic_id = topic_id
        include_context = False
        start_time = datetime.now()

        # ========== DebugLogger: 创建会话 ==========
        debug_session_id = None
        if self.debug_logger:
            debug_session_id = self.debug_logger.create_session(
                input_message=message,
                user=user
            )

        # ========== 系统指令处理 ==========
        if self.system_command_handler.is_system_command(message):
            result = self.system_command_handler.execute(message, user, self.db)
            result['topic_id'] = new_topic_id
            if debug_session_id:
                execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                self.debug_logger.complete_session(
                    debug_session_id,
                    result=result,
                    status="success",
                    execution_time_ms=execution_time_ms
                )
            return result

        # ========== 追问模式处理 ==========
        # 如果有追问上下文，使用专门的追问处理逻辑
        if follow_up_context and follow_up_context.get('action_type'):
            result = self._process_followup_input(message, follow_up_context, user)
            result['topic_id'] = new_topic_id
            return self._complete_debug_session(debug_session_id, result, start_time, "success")

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

        # ========== SPEC-19: OAG Fast Path ==========
        # Try OAG routing before LLM chat (lower latency, zero/fewer LLM calls)
        try:
            oag_result = self._try_oag_path(message, user)
            if oag_result:
                oag_result['topic_id'] = new_topic_id
                return self._complete_debug_session(debug_session_id, oag_result, start_time, "success")
        except Exception as e:
            logger.debug(f"OAG fast path failed, falling through to LLM: {e}")

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

                # 注入查询 Schema（用于 ontology_query）
                context['include_query_schema'] = True

                # ========== DebugLogger: 记录检索上下文 ==========
                if debug_session_id and self.debug_logger:
                    retrieved_schema = {
                        "room_summary": context.get("room_summary"),
                        "room_types_count": len(context.get("room_types", [])),
                        "active_stays_count": len(context.get("active_stays", [])),
                        "pending_tasks_count": len(context.get("pending_tasks", [])),
                    }
                    retrieved_tools = [{"name": "chat", "service": "LLMService"}]
                    self.debug_logger.update_session_retrieval(
                        debug_session_id,
                        retrieved_schema=retrieved_schema,
                        retrieved_tools=retrieved_tools
                    )

                result = self.llm_service.chat(message, context, language=language)

                # ========== DebugLogger: 记录 LLM 调用 ==========
                if debug_session_id and self.debug_logger:
                    # 尝试从 llm_service 获取 prompt 和 token 信息
                    llm_info = self._extract_llm_debug_info()
                    if llm_info:
                        self.debug_logger.update_session_llm(
                            debug_session_id,
                            prompt=llm_info.get("prompt", ""),
                            response=str(result),
                            tokens_used=llm_info.get("tokens_used"),
                            model=llm_info.get("model", "unknown")
                        )

                # 如果 LLM 返回了有效的操作，则处理并返回
                if result.get("suggested_actions") and not result.get("context", {}).get("error"):
                    # 先检查是否是查询类操作，需要获取实际数据
                    action_type = result["suggested_actions"][0].get("action_type", "")
                    # 查询类操作：包括 query_*, view, ontology_query, query_smart
                    is_query_action = (
                        action_type.startswith("query_") or
                        action_type == "view" or
                        action_type in ["ontology_query", "query_smart"]
                    )
                    if is_query_action:
                        response = self._handle_query_action(result, user)
                        response['topic_id'] = new_topic_id
                        return response

                    # 增强参数（添加数据库验证后的值）
                    result = self._enhance_actions_with_db_data(result)

                    # 后端参数校验：检查操作类请求是否信息完整
                    if result.get("suggested_actions"):
                        action = result["suggested_actions"][0]
                        action_params = action.get("params", {})
                        action_type = action.get("action_type", "")

                        # 如果 LLM 已经返回了 missing_fields，直接使用
                        if action.get("missing_fields"):
                            result['topic_id'] = new_topic_id
                            return result

                        # 否则进行后端校验
                        is_valid, missing_fields, error_msg = self._validate_action_params(
                            action_type, action_params, user
                        )

                        if not is_valid and missing_fields:
                            # 信息不完整，生成追问
                            followup = self._generate_followup_response(
                                action_type=action_type,
                                action_description=action.get("description", ""),
                                params=action_params,
                                missing_fields=missing_fields,
                                entity_type=action.get("entity_type", "unknown")
                            )
                            followup['topic_id'] = new_topic_id
                            return followup

                        # 信息完整：确保 action 不包含 missing_fields，设置 requires_confirmation
                        if result.get("suggested_actions"):
                            for act in result["suggested_actions"]:
                                # 移除可能存在的 missing_fields
                                if "missing_fields" in act:
                                    del act["missing_fields"]
                                # 设置 requires_confirmation
                                act["requires_confirmation"] = True
                                # 确保 params 存在
                                if "params" not in act:
                                    act["params"] = action_params
                            print(f"DEBUG: Complete action set, actions count: {len(result['suggested_actions'])}")

                    result['topic_id'] = new_topic_id
                    return self._complete_debug_session(debug_session_id, result, start_time, "success")

                # 其他情况回退到规则模式
            except Exception as e:
                # LLM 出错，回退到规则模式
                print(f"LLM error, falling back to rule-based: {e}")

        # 规则模式（后备）
        result = self._process_with_rules(message, user)
        result['topic_id'] = new_topic_id
        return self._complete_debug_session(debug_session_id, result, start_time, "success")

    def _complete_debug_session(self, session_id: str, result: dict, start_time: datetime, status: str) -> dict:
        """完成 DebugLogger 会话并返回结果"""
        if session_id and self.debug_logger:
            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            # 提取 actions_executed
            actions_executed = result.get("suggested_actions", []) if result else []
            self.debug_logger.complete_session(
                session_id,
                result=result,
                status=status,
                execution_time_ms=execution_time_ms,
                actions_executed=actions_executed
            )
        return result

    def _extract_llm_debug_info(self) -> Optional[Dict[str, Any]]:
        """从 LLMService 提取调试信息"""
        try:
            if hasattr(self.llm_service, 'last_request') and self.llm_service.last_request:
                return {
                    "prompt": self.llm_service.last_request.get("messages", []),
                    "model": self.llm_service.last_request.get("model", "unknown"),
                    "tokens_used": None,  # 需要从响应中获取
                }
        except Exception as e:
            logger.debug(f"Failed to extract LLM debug info: {e}")
        return None

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

            # 解析任务类型（支持中文：维修、清洁）
            if "task_type" in params:
                task_type_result = self.param_parser.parse_task_type(params["task_type"])
                if task_type_result.confidence >= 0.7:
                    params["task_type"] = task_type_result.value.value
                else:
                    # 返回可用任务类型列表让用户选择
                    from app.models.ontology import TaskType
                    action["requires_confirmation"] = True
                    action["candidates"] = [
                        {'value': t.value, 'label': t.value}
                        for t in TaskType
                    ]
                    action["params"] = params
                    continue

            # 解析价格类型（支持中文：周末、平日）
            if "price_type" in params:
                price_type_input = str(params["price_type"]).lower().strip()
                price_type_aliases = {
                    'weekend': ['周末', '周末价', 'weekend', '周六日', '星期六日'],
                    'standard': ['平日', '标准', 'standard', '工作日', '平时']
                }
                matched = None
                for ptype, aliases in price_type_aliases.items():
                    if price_type_input in [a.lower() for a in aliases]:
                        matched = ptype
                        break
                if matched:
                    params["price_type"] = matched

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

            # 解析相对日期（结果转为 ISO 字符串以保证 JSON 可序列化）
            for date_field in ["expected_check_out", "new_check_out_date", "check_in_date", "check_out_date"]:
                if date_field in params:
                    # 先尝试智能参数解析
                    parse_result = self.param_parser.parse_date(params[date_field])
                    if parse_result.confidence > 0:
                        val = parse_result.value
                        params[date_field] = val.isoformat() if isinstance(val, date) else str(val)
                    else:
                        # 回退到原有的相对日期解析
                        parsed_date = self._parse_relative_date(params[date_field])
                        if parsed_date:
                            params[date_field] = parsed_date.isoformat() if isinstance(parsed_date, date) else str(parsed_date)

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

        # query_smart: 结构化查询，返回表格/图表数据
        if action_type == "query_smart":
            params = action.get("params", {})
            query_result = self._execute_smart_query(
                entity=params.get("entity", entity_type),
                query_type=params.get("query_type", "list"),
                filters=params.get("filters", {}),
                user=user
            )
            # 让 LLM 格式化查询结果
            return self._format_query_result_with_llm(result, query_result, user)

        # ontology_query: NL2OntologyQuery - 动态字段选择查询
        if action_type == "ontology_query":
            params = action.get("params", {})
            query_result = self._execute_ontology_query(
                structured_query_dict=params,
                user=user
            )
            # 让 LLM 格式化查询结果
            return self._format_query_result_with_llm(result, query_result, user)

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

    def _format_query_result_with_llm(self, original_result: Dict, query_result: Dict, user: Employee) -> Dict:
        """
        使用 LLM 格式化查询结果，生成更友好的回复

        Args:
            original_result: LLM 原始返回的 result
            query_result: 执行查询后的结果（包含 rows, columns 等）
            user: 当前用户

        Returns:
            格式化后的响应，包含更友好的 message 和 query_result
        """
        query_data = query_result.get("query_result", {})
        rows = query_data.get("rows", [])
        columns = query_data.get("columns", [])
        summary = query_data.get("summary", "")

        # 如果没有结果，直接返回
        if not rows:
            return query_result

        # 构建数据摘要，让 LLM 理解查询结果
        data_summary = self._build_data_summary(rows, columns)

        # 构建格式化提示
        format_prompt = f"""用户的问题：{original_result.get('message', '')}

查询结果摘要：{summary}

详细数据：
{data_summary}

请根据查询结果，用自然语言回答用户的问题。
要求：
1. 直接回答问题，列出关键信息
2. 必须使用上面提供的详细数据，不要说"未提供"或"无法列出"
3. 如果是人名，只列出名字即可
4. 保持简洁，不要啰嗦
5. 不要添加 JSON 格式，直接用自然语言回答

请直接给出回答："""

        try:
            llm_response = self.llm_service.chat(
                format_prompt,
                {"user_role": user.role.value, "user_name": user.name},
                language='zh'
            )
            formatted_message = llm_response.get("message", summary)

            # 检查 LLM 是否返回了有效数据（而不是占位符文本）
            if any(phrase in formatted_message for phrase in ["未提供", "无法列出", "无法获取", "没有提供", "建议您进一步筛选"]):
                # LLM 返回了占位符文本，使用数据摘要
                logger.warning(f"LLM returned placeholder text, using data summary")
                formatted_message = f"{summary}\n\n{data_summary}"

            # 替换 message
            query_result["message"] = formatted_message
            return query_result

        except Exception as e:
            logger.warning(f"LLM formatting failed: {e}, using data summary")
            # 失败时也使用数据摘要
            query_result["message"] = f"{summary}\n\n{data_summary}"
            return query_result

    def _build_data_summary(self, rows: List[Dict], columns: List[str]) -> str:
        """构建数据摘要文本"""
        if not rows:
            return "无数据"

        lines = []
        # 显示所有数据（不限制条数），或者至少显示前20条
        for i, row in enumerate(rows[:20]):
            # row 的键可能是中文（column_keys）或英文
            # 我们需要用 row 的实际键来获取值
            row_items = []
            for idx, col in enumerate(columns):
                # 尝试多种方式获取值
                value = None
                # 1. 直接用列名作为键
                if col in row:
                    value = row[col]
                # 2. 用索引获取
                elif len(row) > idx:
                    value = list(row.values())[idx]
                # 3. 使用空字符串
                else:
                    value = ""

                if value == "" or value is None:
                    value = "(空)"
                row_items.append(f"{col}: {value}")
            row_text = ", ".join(row_items)
            lines.append(f"- {row_text}")

        if len(rows) > 20:
            lines.append(f"... 还有 {len(rows) - 20} 条记录")

        return "\n".join(lines)

    def _process_with_rules(self, message: str, user: Employee) -> dict:
        """
        使用规则模式处理消息（后备方案）
        """
        # Orient: 意图识别和实体提取
        intent = self._identify_intent(message)
        entities = self._extract_entities(message)

        # Decide: 根据意图生成建议动作
        response = self._generate_response(intent, entities, user, message)

        return response

    def _identify_intent(self, message: str) -> str:
        """
        识别用户意图 - 使用动态关键字查询（框架无关）

        从 core/ai/query_keywords 获取通用查询动词
        从 OntologyRegistry 获取领域相关的实体/属性关键字
        """
        from core.ai import QUERY_KEYWORDS, ACTION_KEYWORDS, HELP_KEYWORDS
        from core.ontology.registry import registry

        message_lower = message.lower()

        # 帮助意图 - 优先检查
        if any(kw in message_lower for kw in HELP_KEYWORDS):
            return 'help'

        # 查询类意图 - 使用框架层通用查询动词 + 领域层实体关键字
        if any(kw in message_lower for kw in QUERY_KEYWORDS):
            # 动态查询匹配的实体
            matched_entities = registry.find_entities_by_keywords(message)
            if matched_entities:
                # 有实体匹配，返回对应的查询意图
                # 根据实体类型映射到具体的 intent
                entity_intent_map = {
                    'Room': 'query_rooms',
                    'Guest': 'query_guests',
                    'Reservation': 'query_reservations',
                    'Task': 'query_tasks',
                    'StayRecord': 'query_guests',  # 住宿记录归为客人查询
                    'Bill': 'query_reports',
                    'Employee': 'query_reports',
                }
                # 返回第一个匹配实体的意图（多个匹配时由 LLM 消歧）
                for entity in matched_entities:
                    if entity in entity_intent_map:
                        return entity_intent_map[entity]

            # 特殊的报表查询关键字
            if any(kw in message_lower for kw in ['入住率', '营收', '报表', '统计']):
                return 'query_reports'

        # 操作类意图 - 使用框架层通用操作动词
        if any(kw in message_lower for kw in ACTION_KEYWORDS):
            # 根据具体操作类型判断
            if any(kw in message_lower for kw in ['入住', '办理入住', 'checkin', 'check in']):
                return 'action_checkin'
            if any(kw in message_lower for kw in ['退房', '结账', 'checkout', 'check out']):
                return 'action_checkout'
            if any(kw in message_lower for kw in ['预订', '预约', '订房', 'reserve', 'booking']):
                return 'action_reserve'
            if any(kw in message_lower for kw in ['换房', '转房', 'change']):
                return 'action_change_room'
            if any(kw in message_lower for kw in ['续住', '延期', 'extend']):
                return 'action_extend'
            if any(kw in message_lower for kw in ['清洁', '打扫', 'cleaning', 'clean']):
                return 'action_cleaning'

        return 'unknown'

    def _extract_entities(self, message: str) -> dict:
        """
        提取实体 - 使用动态关键字查询（框架无关）

        结合规则匹配（房间号、日期等）和动态关键字查询（房型、状态等）
        """
        from core.ontology.registry import registry

        entities = {}

        # ===== 规则匹配：结构化信息 =====
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

        # ===== 动态关键字查询：领域相关实体 =====
        # 查询匹配的实体
        matched = registry.resolve_keyword_matches(message)

        # 如果匹配到 Room 实体，提取房型信息
        if 'Room' in matched['entities']:
            # 从 RoomType 表获取房型（如果用户提到了具体房型）
            from app.models.ontology import RoomType
            room_types = self.db.query(RoomType).all()
            for rt in room_types:
                if rt.name in message:
                    entities['room_type'] = rt.name
                    break

        return entities

    def _generate_response(self, intent: str, entities: dict, user: Employee, original_message: str = "") -> dict:
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
            return self._checkin_response(entities, user, original_message)

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
        # 如果指定了房型，返回该房型的统计
        if 'room_type' in entities:
            room_type_name = entities['room_type']
            room_type = self.db.query(RoomType).filter(RoomType.name == room_type_name).first()

            if room_type:
                rooms = self.db.query(Room).filter(Room.room_type_id == room_type.id).all()
                total = len(rooms)
                vacant_clean = sum(1 for r in rooms if r.status == RoomStatus.VACANT_CLEAN)
                occupied = sum(1 for r in rooms if r.status == RoomStatus.OCCUPIED)
                vacant_dirty = sum(1 for r in rooms if r.status == RoomStatus.VACANT_DIRTY)
                out_of_order = sum(1 for r in rooms if r.status == RoomStatus.OUT_OF_ORDER)

                message = f"**{room_type_name}统计：**\n\n"
                message += f"- 总数：{total} 间\n"
                message += f"- 空闲可住：{vacant_clean} 间 ✅\n"
                message += f"- 已入住：{occupied} 间 🔴\n"
                message += f"- 待清洁：{vacant_dirty} 间 🟡\n"
                message += f"- 维修中：{out_of_order} 间 ⚫\n"

                return {
                    'message': message,
                    'suggested_actions': [],
                    'context': {
                        'room_type': room_type_name,
                        'room_type_id': room_type.id,
                        'count': total
                    }
                }

        # 默认返回全部房态统计
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

    def _execute_smart_query(self, entity: str, query_type: str, filters: dict, user: Employee) -> dict:
        """
        执行智能查询，返回结构化结果

        Args:
            entity: 查询实体 (room, reservation, guest, task, report)
            query_type: 查询类型 (status, list, count, summary)
            filters: 过滤条件
            user: 当前用户

        Returns:
            包含 message, query_result 的字典
            query_result: {display_type, columns, rows, summary}
        """
        entity_lower = entity.lower()

        if entity_lower in ('room', 'rooms', '房间'):
            return self._smart_query_rooms(filters)
        elif entity_lower in ('reservation', 'reservations', '预订'):
            return self._smart_query_reservations(filters)
        elif entity_lower in ('guest', 'guests', '客人', '在住客人'):
            return self._smart_query_guests(filters)
        elif entity_lower in ('task', 'tasks', '任务'):
            return self._smart_query_tasks(filters)
        elif entity_lower in ('report', 'reports', '报表', '统计'):
            return self._smart_query_reports()
        else:
            return {
                'message': f'不支持的查询实体: {entity}',
                'suggested_actions': [],
                'query_result': {'display_type': 'text', 'data': None}
            }

    def _smart_query_rooms(self, filters: dict) -> dict:
        """房间智能查询 - 返回结构化表格"""
        summary = self.room_service.get_room_status_summary()
        rooms = self.db.query(Room).all()

        # 文本摘要
        message = f"共 {summary['total']} 间房间"

        # 结构化数据
        rows = []
        for r in rooms:
            rows.append({
                'room_number': r.room_number,
                'floor': r.floor,
                'type': r.room_type.name if r.room_type else '',
                'status': r.status.value,
            })

        return {
            'message': message,
            'suggested_actions': [],
            'query_result': {
                'display_type': 'table',
                'columns': ['房号', '楼层', '房型', '状态'],
                'column_keys': ['room_number', 'floor', 'type', 'status'],
                'rows': rows,
                'summary': summary
            }
        }

    def _smart_query_reservations(self, filters: dict) -> dict:
        """预订智能查询"""
        arrivals = self.reservation_service.get_today_arrivals()
        rows = []
        for r in arrivals:
            rows.append({
                'reservation_no': r.reservation_no,
                'guest_name': r.guest.name if r.guest else '',
                'room_type': r.room_type.name if r.room_type else '',
                'check_in_date': str(r.check_in_date),
                'check_out_date': str(r.check_out_date),
                'status': r.status.value,
            })

        return {
            'message': f"今日预抵 {len(arrivals)} 位客人",
            'suggested_actions': [],
            'query_result': {
                'display_type': 'table',
                'columns': ['预订号', '客人', '房型', '入住', '离店', '状态'],
                'column_keys': ['reservation_no', 'guest_name', 'room_type', 'check_in_date', 'check_out_date', 'status'],
                'rows': rows,
            }
        }

    def _smart_query_guests(self, filters: dict) -> dict:
        """在住客人智能查询"""
        active_stays = self.db.query(StayRecord).filter(
            StayRecord.status == StayRecordStatus.ACTIVE
        ).all()

        rows = []
        for s in active_stays:
            rows.append({
                'guest_name': s.guest.name if s.guest else '',
                'room_number': s.room.room_number if s.room else '',
                'check_in': str(s.check_in_time.date()) if s.check_in_time else '',
                'expected_out': str(s.expected_check_out),
            })

        return {
            'message': f"当前在住 {len(active_stays)} 位客人",
            'suggested_actions': [],
            'query_result': {
                'display_type': 'table',
                'columns': ['客人', '房间', '入住日期', '预计退房'],
                'column_keys': ['guest_name', 'room_number', 'check_in', 'expected_out'],
                'rows': rows,
            }
        }

    def _smart_query_tasks(self, filters: dict) -> dict:
        """任务智能查询"""
        tasks = self.db.query(Task).filter(
            Task.status.in_([TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS])
        ).all()

        rows = []
        for t in tasks:
            rows.append({
                'room_number': t.room.room_number if t.room else '',
                'task_type': t.task_type.value if t.task_type else '',
                'status': t.status.value,
                'assignee': t.assignee.name if t.assignee else '未分配',
            })

        return {
            'message': f"当前有 {len(tasks)} 个待处理任务",
            'suggested_actions': [],
            'query_result': {
                'display_type': 'table',
                'columns': ['房间', '类型', '状态', '负责人'],
                'column_keys': ['room_number', 'task_type', 'status', 'assignee'],
                'rows': rows,
            }
        }

    def _smart_query_reports(self) -> dict:
        """报表智能查询"""
        stats = self.report_service.get_dashboard_stats()

        return {
            'message': f"入住率 {stats['occupancy_rate']}%，今日营收 ¥{stats['today_revenue']}",
            'suggested_actions': [],
            'query_result': {
                'display_type': 'chart',
                'data': stats,
                'summary': stats
            }
        }

    def _execute_ontology_query(
        self,
        structured_query_dict: dict,
        user: Employee
    ) -> dict:
        """
        执行 Ontology 查询 (NL2OntologyQuery)

        使用 QueryEngine 动态构建并执行查询，
        无硬编码实体逻辑。

        Args:
            structured_query_dict: StructuredQuery 字典
            user: 当前用户

        Returns:
            {
                "message": "共 X 条记录",
                "suggested_actions": [],
                "query_result": {
                    "display_type": "table",
                    "columns": ["姓名", "电话"],
                    "column_keys": ["name", "phone"],
                    "rows": [{"name": "张三", "phone": "123"}],
                    "summary": "共 2 条记录"
                }
            }
        """
        from core.ontology.query import StructuredQuery
        from core.ontology.query_engine import QueryEngine
        from core.ontology.registry import registry

        try:
            # 调试日志：打印 LLM 返回的查询结构
            logger.info(f"LLM returned query: {structured_query_dict}")

            # 验证必需的 entity 字段
            if "entity" not in structured_query_dict:
                logger.warning(f"Missing 'entity' field in query: {structured_query_dict}")
                # 尝试从上下文推断 entity
                return {
                    "message": "查询参数不完整：缺少实体类型。请指定要查询的实体（如：房间、客人、预订等）",
                    "suggested_actions": [],
                    "query_result": {
                        "display_type": "text",
                        "rows": [],
                        "summary": "查询参数错误"
                    }
                }

            # 验证和纠正字段名（重要保障机制）
            corrected_query = self._validate_and_correct_fields(structured_query_dict)

            if corrected_query != structured_query_dict:
                logger.info(f"Corrected query fields: {structured_query_dict} -> {corrected_query}")

            # 解析 StructuredQuery
            query = StructuredQuery.from_dict(corrected_query)

            # 调试日志：打印解析后的查询
            logger.info(f"Parsed query - entity: {query.entity}, fields: {query.fields}, "
                       f"aggregate: {query.aggregate}, group_by: {query.group_by}, "
                       f"filters: {len(query.filters)}, limit: {query.limit}")

            # 判断是否为简单查询（可用 Service 优化）
            # 聚合查询不视为简单查询
            if query.is_simple() and not query.aggregate:
                simple_result = self._execute_simple_query(query, user)
                # 记录简单查询结果
                logger.info(f"Simple query result: {len(simple_result.get('query_result', {}).get('rows', []))} rows")
                return simple_result

            # 复杂查询使用 QueryEngine
            engine = QueryEngine(self.db, registry)
            result = engine.execute(query, user)

            # 记录查询结果
            logger.info(f"QueryEngine result: display_type={result.get('display_type')}, "
                       f"rows={len(result.get('rows', []))}, columns={result.get('columns', [])}")

            # 当查询结果为空时，给出更友好的提示
            if result.get("display_type") == "table" and len(result.get("rows", [])) == 0:
                # 检查是否有日期过滤条件
                has_date_filter = any(
                    f.field in ["check_in_time", "check_out_time", "check_in_date", "check_out_date", "created_at"]
                    for f in query.filters
                )
                if has_date_filter:
                    result["message"] = f"指定时间范围内没有找到记录。当前数据范围：2025年2月 - 2026年2月"

            return {
                "message": result.get("summary", result.get("message", "查询完成")),
                "suggested_actions": [],
                "query_result": result
            }

        except Exception as e:
            logger.error(f"Ontology query failed: {e}", exc_info=True)
            return {
                "message": f"查询失败: {str(e)}",
                "suggested_actions": [],
                "query_result": {
                    "display_type": "text",
                    "rows": [],
                    "summary": "查询失败"
                }
            }

    def _validate_and_correct_fields(self, query_dict: dict) -> dict:
        """
        验证和纠正 LLM 返回的字段名

        这是一个重要的保障机制，确保 LLM 使用正确的 Ontology 字段名。
        常见的 LLM 错误：
        - check_in_date -> check_in_time
        - check_out_date -> check_out_time
        - guest_name -> guest.name
        - room_number -> room.room_number

        Args:
            query_dict: LLM 返回的查询字典

        Returns:
            纠正后的查询字典
        """
        from core.ontology.registry import registry
        import copy

        corrected = copy.deepcopy(query_dict)
        entity_name = corrected.get("entity", "")

        # 获取实体的有效字段
        schema = registry.export_query_schema()
        entity_schema = schema.get("entities", {}).get(entity_name, {})
        valid_fields = set(entity_schema.get("fields", {}).keys())

        # 字段名映射表（常见的 LLM 错误）
        field_mappings = {
            # StayRecord 常见错误
            "check_in_date": "check_in_time",
            "check_out_date": "check_out_time",
            "guest_name": "guest.name",
            "guest_phone": "guest.phone",
            "room_number": "room.room_number",
            "room_type": "room.room_type.name",
            "stay_date": "check_in_time",
            "booking_date": "created_at",

            # Reservation 常见错误
            "checkin_date": "check_in_date",
            "checkout_date": "check_out_date",
            "booking_date": "created_at",

            # Guest 常见错误
            "guest_name": "name",
            "customer_name": "name",

            # Room 常见错误
            "room_status": "status",
            "room_type_id": "room_type_id",
        }

        # 纠正 filters 中的字段名
        filters = corrected.get("filters", [])
        for f in filters:
            field = f.get("field", "")
            if field not in valid_fields:
                # 尝试映射
                corrected_field = field_mappings.get(field)
                if corrected_field and corrected_field in valid_fields:
                    f["field"] = corrected_field
                    logger.info(f"Corrected filter field: {field} -> {corrected_field}")
                # 尝试模糊匹配（相似度）
                elif self._find_similar_field(field, valid_fields):
                    f["field"] = self._find_similar_field(field, valid_fields)

        # 纠正 fields 列表中的字段名
        fields = corrected.get("fields", [])
        corrected_fields = []
        for field in fields:
            if field in valid_fields:
                corrected_fields.append(field)
            else:
                # 尝试映射
                corrected_field = field_mappings.get(field)
                if corrected_field and corrected_field in valid_fields:
                    corrected_fields.append(corrected_field)
                    logger.info(f"Corrected field: {field} -> {corrected_field}")
                # 如果是聚合别名，保留
                elif corrected.get("aggregate", {}).get("alias") == field:
                    corrected_fields.append(field)
                # 尝试模糊匹配
                elif self._find_similar_field(field, valid_fields):
                    corrected_fields.append(self._find_similar_field(field, valid_fields))

        if corrected_fields:
            corrected["fields"] = corrected_fields

        # 纠正 aggregate 中的字段名
        aggregate = corrected.get("aggregate")
        if aggregate:
            agg_field = aggregate.get("field", "")
            if agg_field not in valid_fields:
                corrected_agg = field_mappings.get(agg_field)
                if corrected_agg and corrected_agg in valid_fields:
                    aggregate["field"] = corrected_agg
                    logger.info(f"Corrected aggregate field: {agg_field} -> {corrected_agg}")

        # 纠正 order_by 中的字段名
        order_by = corrected.get("order_by", [])
        corrected_order_by = []
        for order_expr in order_by:
            parts = order_expr.split()
            if parts:
                field = parts[0]
                if field not in valid_fields:
                    corrected_field = field_mappings.get(field)
                    if corrected_field and corrected_field in valid_fields:
                        direction = parts[1] if len(parts) > 1 else ""
                        corrected_order_by.append(f"{corrected_field} {direction}".strip() if direction else corrected_field)
                        logger.info(f"Corrected order_by field: {field} -> {corrected_field}")
                        continue
                corrected_order_by.append(order_expr)

        if corrected_order_by:
            corrected["order_by"] = corrected_order_by

        return corrected

    def _find_similar_field(self, field: str, valid_fields: set) -> str:
        """
        查找相似的字段名（用于模糊匹配）

        Args:
            field: LLM 使用的字段名
            valid_fields: 有效的字段名集合

        Returns:
            匹配的字段名，如果没有匹配返回空字符串
        """
        field_lower = field.lower().replace("_", "").replace(".", "")

        # 直接匹配
        for valid in valid_fields:
            valid_clean = valid.lower().replace("_", "").replace(".", "")
            if field_lower == valid_clean:
                return valid

        # 包含匹配
        for valid in valid_fields:
            if field_lower in valid.lower() or valid.lower() in field_lower:
                return valid

        return ""

    def _execute_simple_query(self, query: 'StructuredQuery', user: Employee) -> dict:
        """
        执行简单查询（使用 Service 优化性能）

        简单查询定义：无 JOIN，过滤器 <= 1，字段数 <= 3
        """
        from core.ontology.query import FilterOperator

        entity = query.entity
        fields = query.fields

        # 根据 entity 和 fields 使用对应的 Service
        if entity == "Guest":
            if "name" in fields:
                # 获取客人姓名列表
                active_stays = self.db.query(StayRecord).filter(
                    StayRecord.status == StayRecordStatus.ACTIVE
                ).all()

                rows = []
                for stay in active_stays:
                    row = {}
                    if "name" in fields:
                        row["name"] = stay.guest.name if stay.guest else ""
                    if "phone" in fields:
                        row["phone"] = stay.guest.phone if stay.guest else ""
                    rows.append(row)

                return {
                    "message": f"共 {len(rows)} 条记录",
                    "suggested_actions": [],
                    "query_result": {
                        "display_type": "table",
                        "columns": [self._get_display_name(f) for f in fields],
                        "column_keys": fields,
                        "rows": rows,
                        "summary": f"共 {len(rows)} 条记录"
                    }
                }

        elif entity == "Room":
            # Room 查询需要考虑过滤器
            # 如果有 status 过滤器，应用它
            from app.models.ontology import RoomStatus

            filtered_rooms = []

            # 字段映射：支持中英文字段名
            field_mapping = {
                "room_number": "room_number",
                "房号": "room_number",
                "floor": "floor",
                "楼层": "floor",
                "room_type": "room_type",
                "房型": "room_type",
                "status": "status",
                "状态": "status",
                "room_type_id": "room_type_id",
                "id": "id",
                "price": "price",
                "价格": "price",
                # 常见的错误字段映射
                "name": "room_number",  # Room 的 "name" 通常指房号
                "features": "features",  # 房间设施
                "guest_name": None,  # Room 没有客人姓名
                "姓名": None,
            }

            # 检查是否有状态过滤器
            status_filter = None
            if query.filters:
                for f in query.filters:
                    if f.field == "status" or f.field == "状态":
                        status_filter = f.value
                        break

            # 获取房间
            rooms = self.room_service.get_rooms()

            # 应用状态过滤
            if status_filter:
                if isinstance(status_filter, list):
                    # IN 操作符
                    for room in rooms:
                        if room.status.value in status_filter:
                            filtered_rooms.append(room)
                else:
                    # EQ 操作符
                    target_status = status_filter if isinstance(status_filter, str) else status_filter.value if hasattr(status_filter, 'value') else str(status_filter)
                    for room in rooms:
                        if room.status.value == target_status:
                            filtered_rooms.append(room)
            else:
                filtered_rooms = rooms

            rows = []
            for room in filtered_rooms:
                row = {}
                has_valid_field = False
                for field in fields:
                    # 使用字段映射
                    mapped_field = field_mapping.get(field, field)

                    # 如果映射为 None，表示这个字段不存在，使用空字符串
                    if mapped_field is None and field in field_mapping:
                        row[field] = ""
                        continue

                    # 获取字段值
                    value = ""

                    if mapped_field == "room_number" or field == "room_number" or field == "name":
                        value = str(room.room_number)
                        has_valid_field = True
                    elif mapped_field == "status" or field == "status":
                        value = room.status.value if hasattr(room.status, 'value') else str(room.status)
                        has_valid_field = True
                    elif mapped_field == "floor" or field == "floor":
                        value = str(room.floor)
                        has_valid_field = True
                    elif mapped_field == "room_type" or field == "room_type":
                        value = room.room_type.name if room.room_type else ""
                        has_valid_field = True
                    elif (mapped_field == "room_type_id" or field == "room_type_id") and room.room_type_id:
                        value = str(room.room_type_id)
                        has_valid_field = True
                    elif (mapped_field == "id" or field == "id") and room.id:
                        value = str(room.id)
                        has_valid_field = True
                    elif (mapped_field == "price" or field == "price") and room.room_type:
                        value = str(room.room_type.base_price)
                        has_valid_field = True
                    elif mapped_field == "features" or field == "features":
                        value = room.features if room.features else ""
                        has_valid_field = True
                    else:
                        # 未知字段，使用空字符串
                        value = ""

                    row[field] = value

                # 只要有一个有效字段就添加行
                if has_valid_field or row:
                    rows.append(row)

            return {
                "message": f"共 {len(rows)} 条记录",
                "suggested_actions": [],
                "query_result": {
                    "display_type": "table",
                    "columns": [self._get_display_name(f) for f in fields],
                    "column_keys": fields,
                    "rows": rows,
                    "summary": f"共 {len(rows)} 条记录"
                }
            }

        # 默认使用 QueryEngine
        from core.ontology.query_engine import QueryEngine
        from core.ontology.registry import registry
        engine = QueryEngine(self.db, registry)
        result = engine.execute(query, user)

        return {
            "message": result["summary"],
            "suggested_actions": [],
            "query_result": result
        }

    def _get_display_name(self, field: str) -> str:
        """获取字段的显示名称"""
        DISPLAY_NAMES = {
            # 英文字段名
            "name": "姓名",
            "phone": "电话",
            "room_number": "房号",
            "room_type": "房型",
            "status": "状态",
            "floor": "楼层",
            "check_in_date": "入住日期",
            "check_out_date": "退房日期",
            "task_type": "任务类型",
            "reservation_no": "预订号",
            "total_amount": "总金额",
            "is_settled": "已结清",
            "price": "价格",
            "id": "ID",
            # 中文字段名直接返回
            "房号": "房号",
            "楼层": "楼层",
            "房型": "房型",
            "状态": "状态",
            "姓名": "姓名",
            "电话": "电话",
            "价格": "价格",
        }
        return DISPLAY_NAMES.get(field, field)

    def _checkin_response(self, entities: dict, user: Employee, original_message: str = "") -> dict:
        """
        Handle check-in response with walk-in keyword detection.

        Args:
            entities: Extracted entities from message
            user: Current employee user
            original_message: Original user message for keyword detection

        Returns:
            Response dict with message and suggested_actions
        """
        # Detect walk-in keywords from ActionRegistry (single source of truth)
        walkin_keywords = []
        ar = self.get_action_registry()
        if ar:
            walkin_action = ar.get_action("walkin_checkin")
            if walkin_action:
                walkin_keywords = walkin_action.search_keywords
        is_walkin = any(kw in original_message for kw in walkin_keywords)

        # 根据实体查找目标
        if 'room_number' in entities:
            room = self.room_service.get_room_by_number(entities['room_number'])
            if room and room.status in [RoomStatus.VACANT_CLEAN, RoomStatus.VACANT_DIRTY]:
                # If user explicitly said walk-in, skip the question and go directly to walkin_checkin
                if is_walkin:
                    return {
                        'message': f"{room.room_number}号房（{room.room_type.name}）当前空闲，"
                                   f"确认办理散客入住吗？",
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
                # Otherwise ask the standard question
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

        SPEC-08: 优先使用 ActionRegistry，未注册的动作回退到旧逻辑
        """
        action_type = action.get('action_type')
        params = action.get('params', {})

        # ========== SPEC-08: 新路径 - ActionRegistry ==========
        if self.use_action_registry():
            try:
                registry = self.get_action_registry()
                if registry.get_action(action_type):
                    logger.info(f"Executing {action_type} via ActionRegistry")
                    return self.dispatch_via_registry(action_type, params, user)
            except Exception as e:
                logger.warning(f"Registry dispatch failed for {action_type}: {e}, falling back to legacy")
                # 继续尝试旧路径
                pass
        # ========== SPEC-08 End ==========

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
                # 根据实际任务类型返回正确的消息
                task_type_name = "清洁" if task.task_type == TaskType.CLEANING else "维修"
                return {
                    'success': True,
                    'message': f'{task_type_name}任务已创建，任务ID：{task.id}'
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

            # ========== ActionRegistry 回退支持 ==========
            # 以下动作已在 ActionRegistry 中注册，此处提供回退实现

            # create_guest: 创建客人
            if action_type == 'create_guest':
                from app.models.schemas import GuestCreate
                from app.services.guest_service import GuestService
                from app.models.ontology import Guest

                if params.get('phone'):
                    existing = self.db.query(Guest).filter(
                        Guest.phone == params['phone']
                    ).first()
                    if existing:
                        return {
                            'success': False,
                            'message': f"手机号 {params['phone']} 已被客人「{existing.name}」使用",
                            'error': 'duplicate'
                        }

                create_data = GuestCreate(
                    name=params.get('name', ''),
                    phone=params.get('phone'),
                    id_type=params.get('id_type'),
                    id_number=params.get('id_number'),
                    email=params.get('email')
                )
                service = GuestService(self.db)
                guest = service.create_guest(create_data)
                return {
                    'success': True,
                    'message': f"客人「{guest.name}」已创建",
                    'guest_id': guest.id,
                    'guest_name': guest.name,
                    'phone': guest.phone
                }

            # mark_room_clean: 标记房间已清洁
            if action_type == 'mark_room_clean':
                from app.services.room_service import RoomService
                from app.models.ontology import RoomStatus
                room_id = params.get('room_id') or params.get('room_number')
                if isinstance(room_id, str) and room_id.isdigit():
                    room_id = int(room_id)
                service = RoomService(self.db)
                room = service.get_room(room_id) if room_id else None
                if room:
                    room = service.update_room_status(room.id, RoomStatus.VACANT_CLEAN)
                    return {
                        'success': True,
                        'message': f'{room.room_number}号房已标记为已清洁'
                    }
                return {
                    'success': False,
                    'message': '房间不存在'
                }

            # mark_room_dirty: 标记房间待清洁
            if action_type == 'mark_room_dirty':
                from app.services.room_service import RoomService
                from app.models.ontology import RoomStatus
                room_id = params.get('room_id') or params.get('room_number')
                if isinstance(room_id, str) and room_id.isdigit():
                    room_id = int(room_id)
                service = RoomService(self.db)
                room = service.get_room(room_id) if room_id else None
                if room:
                    room = service.update_room_status(room.id, RoomStatus.VACANT_DIRTY)
                    return {
                        'success': True,
                        'message': f'{room.room_number}号房已标记为待清洁'
                    }
                return {
                    'success': False,
                    'message': '房间不存在'
                }

            # delete_task: 删除任务
            if action_type == 'delete_task':
                from app.models.schemas import TaskDelete
                from app.services.task_service import TaskService
                task_id = params.get('task_id')
                service = TaskService(self.db)
                service.delete_task(task_id, user.id)
                return {
                    'success': True,
                    'message': '任务已删除'
                }

            # update_guest: 更新客人
            if action_type == 'update_guest':
                from app.models.schemas import GuestUpdate
                from app.services.guest_service import GuestService
                from app.models.ontology import Guest

                guest_id = params.get('guest_id')
                guest_name = params.get('guest_name')

                guest = None
                if guest_id:
                    service = GuestService(self.db)
                    guest = service.get_guest(guest_id)
                elif guest_name:
                    guest = self.db.query(Guest).filter(
                        Guest.name == guest_name
                    ).first()

                if not guest:
                    return {
                        'success': False,
                        'message': '未找到客人',
                        'error': 'not_found'
                    }

                update_fields = {}
                for field in ['name', 'phone', 'email', 'id_type', 'id_number', 'tier']:
                    if field in params and params[field] is not None:
                        update_fields[field] = params[field]

                if not update_fields:
                    return {
                        'success': False,
                        'message': '没有需要更新的字段',
                        'error': 'no_updates'
                    }

                update_data = GuestUpdate(**update_fields)
                service = GuestService(self.db)
                updated_guest = service.update_guest(guest.id, update_data)
                return {
                    'success': True,
                    'message': f"已更新客人「{updated_guest.name}」的信息",
                    'guest_id': updated_guest.id
                }

            # ========== End of ActionRegistry 回退支持 ==========

            # ontology_query: NL2OntologyQuery - 动态字段选择查询
            if action_type == 'ontology_query':
                result = self._execute_ontology_query(params, user)
                # 整合返回格式
                query_result = result.get('query_result', {})
                return {
                    'success': True,
                    'message': result.get('message', '查询完成'),
                    'query_result': query_result
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
