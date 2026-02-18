"""
core/ai/ooda_orchestrator.py — Domain-agnostic OODA loop orchestrator

Provides the AI orchestration engine independent of any business domain.
Domain-specific logic is injected via IDomainAdapter and constructor params.

IMPORTANT: This module must NOT import application-layer modules — all
domain-specific logic is accessed through self.adapter and injected dependencies.
"""
import json
import re
import logging
from typing import Optional, List, Dict, Any, Union, TYPE_CHECKING
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Core framework imports (domain-agnostic)
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

try:
    from core.ai.debug_logger import DebugLogger
    DEBUG_LOGGER_AVAILABLE = True
except ImportError:
    DEBUG_LOGGER_AVAILABLE = False


class _SystemCommandHandlerStub:
    """Stub — real SystemCommandHandler is injected from app layer."""
    def is_system_command(self, message: str) -> bool:
        return False
    def execute(self, command, user, db) -> Dict[str, Any]:
        return {'message': 'System commands not available', 'suggested_actions': [], 'context': {}}


class OodaOrchestrator:
    """Domain-agnostic OODA loop orchestrator.

    All domain-specific logic is injected via:
    - adapter: IDomainAdapter for domain operations
    - llm_service: LLM integration service
    - system_command_handler: handles system commands
    - action_registry_factory: callable returning ActionRegistry
    - missing_field_class: class for MissingField construction
    - descriptive_summary_fn: builds descriptive summaries from query results
    - topic_continuation / topic_followup_answer: topic relevance sentinel values
    - model_resolver: callable(name) → ORM model class (for fallback resolution)
    """

    # Subclasses can define _TOPIC_CONTINUATION / _TOPIC_FOLLOWUP_ANSWER
    _TOPIC_CONTINUATION = "continuation"
    _TOPIC_FOLLOWUP_ANSWER = "followup_answer"

    def __init__(
        self,
        db: Session,
        adapter,
        *,
        llm_service=None,
        system_command_handler=None,
        action_registry_factory=None,
        missing_field_class=None,
        descriptive_summary_fn=None,
        topic_continuation=None,
        topic_followup_answer=None,
        model_resolver=None,
        domain_rules_init=None,
        domain_action_keywords=None,
    ):
        self.db = db
        self.adapter = adapter
        self.llm_service = llm_service
        self.system_command_handler = system_command_handler or _SystemCommandHandlerStub()
        self._action_registry_factory = action_registry_factory
        self._missing_field_class = missing_field_class
        self._descriptive_summary_fn = descriptive_summary_fn
        self._model_resolver = model_resolver
        self._domain_rules_init = domain_rules_init
        self._domain_action_keywords = domain_action_keywords or []
        if topic_continuation is not None:
            self._TOPIC_CONTINUATION = topic_continuation
        if topic_followup_answer is not None:
            self._TOPIC_FOLLOWUP_ANSWER = topic_followup_answer

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
        """Initialize core/ai/ components (domain-agnostic)."""
        self.use_core_ai = CORE_AI_AVAILABLE
        self.use_core_rules = False  # Subclass sets to True after registering rules
        self.use_core_metadata = False  # Subclass sets to True after loading metadata

        # Core AI client
        if self.use_core_ai:
            from core.ontology.registry import OntologyRegistry
            self.llm_client = OpenAICompatibleClient()
            self.prompt_builder = PromptBuilder()
            self.hitl_strategy = ConfirmByRiskStrategy(registry=OntologyRegistry())
        else:
            self.llm_client = None
            self.prompt_builder = None
            self.hitl_strategy = None

        # Domain rules registration (injected callable)
        if self._domain_rules_init:
            try:
                self._domain_rules_init()
                self.use_core_rules = True
            except Exception:
                pass

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
                if self._action_registry_factory:
                    self._action_registry = self._action_registry_factory()
                    logger.info(f"ActionRegistry initialized with {len(self._action_registry.list_actions())} actions")
                else:
                    self._action_registry = False
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

    def _try_oag_path(self, message: str, user: Any) -> Dict[str, Any]:
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

        # Step 1.5: Check for denied system intents (SPEC-24)
        denied = intent_data.get("denied_intents", [])
        if denied:
            redirects = getattr(self.llm_service, '_DENIED_INTENT_REDIRECTS', {})
            admin_path = redirects.get(denied[0], "系统管理界面")
            return {
                "message": f"该操作不支持通过对话完成，请前往「{admin_path}」进行操作。",
                "suggested_actions": [],
                "context": {"denied_intent": denied[0]},
            }

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

    def _oag_handle_query(self, intent, routing, user) -> Dict[str, Any]:
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

    def _oag_handle_mutation(self, intent, routing, message, user) -> Dict[str, Any]:
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
        params: Dict[str, Any],
        user: Any
    ) -> Dict[str, Any]:
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
            "param_parser": self.adapter.param_parser
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

    def _get_required_params(self, action_name: str) -> list[str]:
        """
        获取操作必需参数列表。

        优先使用 ActionDefinition.ui_required_fields,
        否则从 Pydantic schema 中内省必填字段。
        """
        try:
            action_registry = self.get_action_registry()
            action_def = action_registry.get_action(action_name)
            if action_def:
                # 1. Check ui_required_fields first (from @registry.register())
                if action_def.ui_required_fields:
                    return action_def.ui_required_fields
                # 2. Introspect Pydantic schema
                if action_def.parameters_schema:
                    schema = action_def.parameters_schema
                    required = []
                    for field_name, field_info in schema.model_fields.items():
                        if field_info.is_required():
                            required.append(field_name)
                    return required
        except Exception:
            pass

        return []

    def _validate_action_params(
        self,
        action_type: str,
        params: Dict[str, Any],
        user: Any
    ) -> tuple[bool, list, str]:
        """
        校验操作参数是否完整

        Returns:
            (is_valid, missing_fields, error_message)
        """
        required = self._get_required_params(action_type)
        if not required:
            return True, [], ""

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
        current_params: Dict[str, Any]
    ) -> Optional[Any]:
        """获取字段定义 — delegates to adapter"""
        return self.adapter.get_field_definition(param_name, action_type, current_params, self.db)

    def _generate_followup_response(
        self,
        action_type: str,
        action_description: str,
        params: Dict[str, Any],
        missing_fields: list,
        entity_type: str = "unknown"
    ) -> Dict[str, Any]:
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
                display_names = self.adapter.get_display_names()
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
        follow_up_context: Dict[str, Any],
        user: Any
    ) -> Dict[str, Any]:
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

        # Derive entity_type and description from ActionRegistry (no hardcoded dicts)
        try:
            ar = self.get_action_registry()
            action_def = ar.get_action(action_type) if ar else None
        except (AttributeError, Exception):
            action_def = None
        entity_type = action_def.entity.lower() if action_def else action_type
        action_desc = action_def.description if action_def else action_type

        # 如果信息完整，生成可执行的操作
        if is_complete:
            enhanced_result = self._enhance_single_action_params(
                action_type, merged_params, user
            )

            result = {
                'message': llm_result.get('message', ''),
                'suggested_actions': [{
                    'action_type': action_type,
                    'entity_type': entity_type,
                    'description': action_desc,
                    'requires_confirmation': True,
                    'params': enhanced_result,
                }],
                'context': {},
                'follow_up': None
            }
            return result

        # 信息仍不完整，继续追问
        else:
            missing_fields = [
                self._missing_field_class(**f) for f in missing_fields_data
            ] if missing_fields_data and self._missing_field_class else []

            if not missing_fields:
                is_valid, missing_fields, _ = self._validate_action_params(
                    action_type, merged_params, user
                )

            if missing_fields:
                return self._generate_followup_response(
                    action_type=action_type,
                    action_description=action_desc,
                    params=merged_params,
                    missing_fields=missing_fields,
                    entity_type=entity_type,
                )

            # 没有缺失字段，信息完整！
            return {
                'message': llm_result.get('message', f"{action_desc}，确认办理吗？"),
                'suggested_actions': [{
                    'action_type': action_type,
                    'entity_type': entity_type,
                    'description': action_desc,
                    'requires_confirmation': True,
                    'params': merged_params,
                }],
                'context': {},
                'follow_up': None
            }

    def _enhance_single_action_params(
        self,
        action_type: str,
        params: Dict[str, Any],
        user: Any
    ) -> Dict[str, Any]:
        """增强单个操作的参数 — delegates to adapter"""
        return self.adapter.enhance_single_action_params(action_type, params, self.db)

    def process_message(
        self,
        message: str,
        user: Any,
        conversation_history: list = None,
        topic_id: str = None,
        follow_up_context: Dict[str, Any] = None,
        language: str = None
    ) -> Dict[str, Any]:
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
        start_time = datetime.now()

        # ========== DebugLogger: 创建会话 ==========
        debug_session_id = None
        if self.debug_logger:
            debug_session_id = self.debug_logger.create_session(
                input_message=message,
                user=user
            )

        # ========== LLMCallContext: 开始会话 ==========
        if debug_session_id and self.debug_logger:
            try:
                from core.ai.llm_call_context import LLMCallContext
                LLMCallContext.begin_session(debug_session_id, self.debug_logger)
            except ImportError:
                pass

        try:
            return self._process_message_inner(
                message=message,
                user=user,
                conversation_history=conversation_history,
                topic_id=topic_id,
                follow_up_context=follow_up_context,
                language=language,
                debug_session_id=debug_session_id,
                start_time=start_time,
            )
        finally:
            # ========== LLMCallContext: 结束会话 ==========
            try:
                from core.ai.llm_call_context import LLMCallContext
                LLMCallContext.end_session()
            except ImportError:
                pass

    def _process_message_inner(
        self,
        message: str,
        user: Any,
        conversation_history: list,
        topic_id: str,
        follow_up_context: Dict[str, Any],
        language: str,
        debug_session_id: str,
        start_time: datetime,
    ) -> Dict[str, Any]:
        """Inner implementation of process_message (separated for try/finally in caller)."""
        new_topic_id = topic_id
        include_context = False

        # ========== OODA Phase Timing (SPEC-25) ==========
        ooda_phases = {}
        t_observe_start = start_time

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

        # ========== OODA Observe Phase ==========
        t_observe_end = datetime.now()
        ooda_phases["observe"] = {
            "duration_ms": int((t_observe_end - t_observe_start).total_seconds() * 1000),
            "output": {"message": message[:200]},
        }

        # ========== OODA Orient Phase ==========
        t_orient_start = t_observe_end
        orient_output = {}

        # 检查话题相关性并决定是否携带上下文
        if conversation_history and self.llm_service.is_enabled():
            try:
                # 将历史转换为简单格式
                history_for_check = [
                    {'role': h.get('role'), 'content': h.get('content')}
                    for h in conversation_history[-6:]  # 最近 3 轮
                ]

                relevance = self.llm_service.check_topic_relevance(message, history_for_check)

                if relevance == self._TOPIC_CONTINUATION:
                    include_context = True
                    orient_output["topic_relevance"] = "continuation"
                elif relevance == self._TOPIC_FOLLOWUP_ANSWER:
                    include_context = True
                    orient_output["topic_relevance"] = "followup_answer"
                else:
                    include_context = False
                    new_topic_id = None
                    orient_output["topic_relevance"] = "new_topic"
            except Exception as e:
                logger.warning(f"Topic relevance check failed: {e}")
                include_context = bool(conversation_history)

        t_orient_end = datetime.now()
        ooda_phases["orient"] = {
            "duration_ms": int((t_orient_end - t_orient_start).total_seconds() * 1000),
            "output": orient_output,
        }

        # ========== OODA Decide Phase (OAG or LLM) ==========
        t_decide_start = t_orient_end

        # ========== SPEC-19: OAG Fast Path ==========
        # Try OAG routing before LLM chat (lower latency, zero/fewer LLM calls)
        try:
            oag_result = self._try_oag_path(message, user)
            if oag_result:
                t_decide_end = datetime.now()
                ooda_phases["decide"] = {
                    "duration_ms": int((t_decide_end - t_decide_start).total_seconds() * 1000),
                    "output": {"path": "oag", "action": oag_result.get("suggested_actions", [{}])[0].get("action_type", "")},
                }
                ooda_phases["act"] = {
                    "duration_ms": 0,
                    "output": {"result": "oag_direct"},
                }
                oag_result['topic_id'] = new_topic_id
                return self._complete_debug_session(
                    debug_session_id, oag_result, start_time, "success",
                    metadata={"ooda_phases": ooda_phases}
                )
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

                # ========== OODA Decide Phase End (SPEC-25) ==========
                t_decide_end = datetime.now()
                ooda_phases["decide"] = {
                    "duration_ms": int((t_decide_end - t_decide_start).total_seconds() * 1000),
                    "output": {"path": "llm", "action": result.get("suggested_actions", [{}])[0].get("action_type", "") if result.get("suggested_actions") else ""},
                }
                t_act_start = t_decide_end

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
                    # 查询类操作：ontology_query, query_*, view (deprecated, will be retried)
                    is_query_action = (
                        action_type.startswith("query_") or
                        action_type == "view" or
                        action_type == "ontology_query"
                    )
                    if is_query_action:
                        response = self._handle_query_action(result, user)
                        response['topic_id'] = new_topic_id
                        t_act_end = datetime.now()
                        ooda_phases["act"] = {
                            "duration_ms": int((t_act_end - t_act_start).total_seconds() * 1000),
                            "output": {"result": "query_executed"},
                        }
                        return self._complete_debug_session(
                            debug_session_id, response, start_time, "success",
                            metadata={"ooda_phases": ooda_phases}
                        )

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
                            logger.debug(f"Complete action set, actions count: {len(result['suggested_actions'])}")

                    # ========== OODA Act Phase End (SPEC-25) ==========
                    t_act_end = datetime.now()
                    ooda_phases["act"] = {
                        "duration_ms": int((t_act_end - t_act_start).total_seconds() * 1000),
                        "output": {"result": "action_proposed"},
                    }

                    result['topic_id'] = new_topic_id
                    return self._complete_debug_session(
                        debug_session_id, result, start_time, "success",
                        metadata={"ooda_phases": ooda_phases}
                    )

                # 其他情况回退到规则模式
            except Exception as e:
                # LLM 出错，回退到规则模式
                logger.warning(f"LLM error, falling back to rule-based: {e}")

        # 规则模式（后备）
        result = self._process_with_rules(message, user)
        result['topic_id'] = new_topic_id
        ooda_phases["decide"] = {
            "duration_ms": int((datetime.now() - t_decide_start).total_seconds() * 1000),
            "output": {"path": "rule_based"},
        }
        ooda_phases["act"] = {"duration_ms": 0, "output": {"result": "rule_based"}}
        return self._complete_debug_session(
            debug_session_id, result, start_time, "success",
            metadata={"ooda_phases": ooda_phases}
        )

    def _complete_debug_session(
        self, session_id: str, result: Dict[str, Any], start_time: datetime,
        status: str, metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
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
                actions_executed=actions_executed,
                metadata=metadata,
            )
        if result is not None and session_id:
            result["debug_session_id"] = session_id
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

    def _build_llm_context(self, user: Any) -> Dict[str, Any]:
        """构建 LLM 上下文 — delegates domain-specific data to adapter"""
        context = {
            "user_role": user.role.value,
            "user_name": user.name,
        }
        # Merge domain-specific context from adapter
        domain_context = self.adapter.build_llm_context(self.db)
        context.update(domain_context)
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
        """使用数据库数据增强 LLM 返回的操作.

        Pipeline: action_def.param_enhancer (action-specific) → adapter.enhance_action_params (generic)
        """
        registry = self.get_action_registry()
        for action in result.get("suggested_actions", []):
            params = action.get("params", {})
            action_type = action.get("action_type", "")

            # Step 1: Action-level enhancer (action-specific DB lookups)
            if registry:
                action_def = registry.get_action(action_type)
                if action_def and action_def.param_enhancer:
                    try:
                        params = action_def.param_enhancer(params, self.db)
                    except Exception as e:
                        logger.warning(f"param_enhancer failed for {action_type}: {e}")

            # Step 2: Adapter-level enhancement (generic field parsing)
            params = self.adapter.enhance_action_params(
                action_type, params, "", self.db
            )

            action["params"] = params
        return result

    def _handle_query_action(self, result: Dict, user: Any) -> Dict:
        """
        Unified query pipeline: route all queries through ontology_query or query_reports.

        Paths:
        1. ontology_query → _execute_ontology_query → _format_query_result_with_llm
        2. query_reports  → _query_reports_response (cross-entity dashboard)
        3. view           → _retry_as_ontology_query (Reflexion-lite rejection)
        4. query_smart / query_* → convert to ontology_query
        """
        actions = result.get("suggested_actions", [])
        if not actions:
            return result

        action = actions[0]
        action_type = action.get("action_type", "")
        entity_type = action.get("entity_type", "")
        params = action.get("params", {})

        # Path 1: ontology_query (primary path)
        if action_type == "ontology_query":
            return self._execute_and_format_query(params, result, user, pipeline="ontology_query")

        # Path 2: query_reports (cross-entity dashboard)
        if action_type == "query_reports":
            return self._query_reports_response()

        # Path 3: view → Reflexion-lite retry
        if action_type == "view":
            return self._retry_as_ontology_query(result, user)

        # Path 4: query_smart or query_* → convert to ontology_query
        if action_type == "query_smart" or action_type.startswith("query_"):
            entity = params.get("entity") or entity_type or ""
            if entity:
                params["entity"] = entity
            return self._execute_and_format_query(params, result, user, pipeline="converted_from_" + action_type)

        return result

    def _execute_and_format_query(self, params: Dict, original_result: Dict, user: Any, pipeline: str = "ontology_query") -> Dict:
        """Execute ontology_query and format result with LLM."""
        query_result = self._execute_ontology_query(
            structured_query_dict=params,
            user=user
        )
        formatted = self._format_query_result_with_llm(original_result, query_result, user)

        # Log pipeline observability
        if DEBUG_LOGGER_AVAILABLE and hasattr(self, 'debug_logger') and self.debug_logger:
            action = original_result.get("suggested_actions", [{}])[0]
            try:
                self.debug_logger.update_metadata(
                    getattr(self, '_current_debug_session_id', ''),
                    {
                        "query_pipeline": pipeline,
                        "original_action_type": action.get("action_type", ""),
                        "final_action_type": "ontology_query",
                        "entity": params.get("entity", ""),
                    }
                )
            except Exception:
                pass  # observability is best-effort

        return formatted

    def _retry_as_ontology_query(self, view_result: Dict, user: Any) -> Dict:
        """
        Reflexion-lite: reject deprecated 'view' action, construct ontology_query from context.

        Instead of calling LLM again (which costs latency), we convert the view result
        into an ontology_query based on entity_type and message keywords.
        """
        action = view_result.get("suggested_actions", [{}])[0]
        entity_type = action.get("entity_type", "")
        params = action.get("params", {})

        logger.warning(f"LLM returned deprecated 'view' action (entity_type={entity_type}), converting to ontology_query")

        # Infer entity from entity_type or message keywords
        entity = self._infer_entity_from_view(entity_type, view_result.get("message", ""))

        if entity:
            params["entity"] = entity
            return self._execute_and_format_query(params, view_result, user, pipeline="view_converted")

        # Last resort: if we can't infer entity, return the original result
        logger.warning(f"Could not infer entity from view action, returning original result")
        return view_result

    def _infer_entity_from_view(self, entity_type: str, message: str) -> str:
        """Infer ontology entity name from view entity_type or message keywords.

        Resolution strategy:
        1. Match entity_type against registered models in OntologyRegistry
        2. Normalize entity_type to PascalCase via model module introspection
        3. Use registry.find_entities_by_keywords() for message-based inference
        """
        from core.ontology.registry import registry

        # Step 1: Try registry model map (populated at bootstrap or lazily)
        if entity_type:
            model_map = registry.get_model_map()
            # Direct match (e.g., "Room" → "Room")
            if entity_type in model_map:
                return entity_type

            # Case-insensitive + base-word match against registered models
            entity_lower = entity_type.lower().split("_")[0]  # "room_status" → "room"
            for name in model_map:
                if entity_lower == name.lower():
                    return name

            # Fallback: try resolving via injected model_resolver
            if self._model_resolver:
                try:
                    for candidate in [entity_type, entity_type.title(), entity_type.split("_")[0].title()]:
                        cls = self._model_resolver(candidate)
                        if cls is not None and hasattr(cls, '__tablename__'):
                            return candidate
                except Exception:
                    pass

        # Step 2: Use registry keyword matching from message
        if message:
            matched = registry.find_entities_by_keywords(message)
            if matched:
                return matched[0]

        return ""

    def _format_query_result_with_llm(self, original_result: Dict, query_result: Dict, user: Any) -> Dict:
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
            try:
                from core.ai.llm_call_context import LLMCallContext
                LLMCallContext.before_call("act", "format_result")
            except ImportError:
                pass

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

    def _process_with_rules(self, message: str, user: Any) -> Dict[str, Any]:
        """
        使用规则模式处理消息（后备方案）
        """
        # Orient: 意图识别 (entity extraction now handled by LLM path)
        intent = self._identify_intent(message)
        entities = {}

        # Decide: 根据意图生成建议动作
        response = self._generate_response(intent, entities, user, message)

        return response

    def _identify_intent(self, message: str) -> str:
        """
        识别用户意图 - 使用 registry 元数据驱动的通用分类

        从 core/ai 获取通用查询/操作/帮助关键字
        从 OntologyRegistry 获取实体关键字
        从 ActionRegistry 获取操作 search_keywords
        """
        from core.ai import QUERY_KEYWORDS, ACTION_KEYWORDS, HELP_KEYWORDS
        from core.ontology.registry import registry

        message_lower = message.lower()

        # 帮助意图 - 优先检查
        if any(kw in message_lower for kw in HELP_KEYWORDS):
            return 'help'

        # 查询类意图 - 使用通用查询动词 + 实体关键字匹配
        if any(kw in message_lower for kw in QUERY_KEYWORDS):
            matched_entities = registry.find_entities_by_keywords(message)
            if matched_entities:
                entity = matched_entities[0]
                return f'query_{entity.lower()}s'

            return 'query_reports'

        # 操作类意图 - 从 ActionDefinition.search_keywords 动态匹配
        ar = None
        try:
            ar = self.get_action_registry()
        except Exception:
            pass

        if ar:
            best_match = None
            best_score = 0
            for action in ar.list_actions():
                if not action.search_keywords:
                    continue
                for kw in action.search_keywords:
                    if kw in message_lower and len(kw) > best_score:
                        best_score = len(kw)
                        best_match = action.name
            if best_match:
                return f'action_{best_match}'

        # Fallback: check generic ACTION_KEYWORDS + domain-injected keywords
        all_action_keywords = list(ACTION_KEYWORDS) + list(self._domain_action_keywords)
        if any(kw in message_lower for kw in all_action_keywords):
            return 'action_unknown'

        return 'unknown'

    def _generate_response(self, intent: str, entities: Dict[str, Any], user: Any, original_message: str = "") -> Dict[str, Any]:
        """
        生成响应和建议动作 — 通用分发，由 registry 元数据驱动
        """
        if intent == 'help':
            return self._help_response()

        # Query intents: extract entity name from intent and route to ontology_query
        if intent.startswith('query_') and intent != 'query_reports':
            # intent is "query_{entity}s" — extract entity name
            entity_suffix = intent[6:]  # strip "query_"
            if entity_suffix.endswith('s'):
                entity_suffix = entity_suffix[:-1]  # strip trailing 's'
            # Find matching entity in registry (case-insensitive)
            from core.ontology.registry import registry as ont_registry
            entity_name = None
            for entity in ont_registry.get_entities():
                if entity.name.lower() == entity_suffix:
                    entity_name = entity.name
                    break
            if entity_name:
                try:
                    return self._execute_ontology_query(
                        structured_query_dict={"entity": entity_name},
                        user=user
                    )
                except Exception as e:
                    logger.warning(f"Rule-based ontology_query failed for {entity_name}: {e}")
                    return {
                        'message': f'查询{entity_name}失败: {str(e)}',
                        'suggested_actions': [],
                        'context': {'intent': intent}
                    }

        if intent == 'query_reports':
            return self._query_reports_response()

        # Action intents: look up action in registry and suggest it
        if intent.startswith('action_'):
            action_name = intent[7:]  # strip "action_"
            ar = None
            try:
                ar = self.get_action_registry()
            except Exception:
                pass
            if ar:
                action_def = ar.get_action(action_name)
                if action_def:
                    return {
                        'message': action_def.description,
                        'suggested_actions': [{
                            'action_type': action_name,
                            'params': {},
                            'requires_confirmation': action_def.requires_confirmation,
                        }],
                        'context': {}
                    }

        return {
            'message': self.adapter.get_help_text(),
            'suggested_actions': [],
            'context': {'intent': intent, 'entities': entities}
        }

    def _help_response(self) -> Dict[str, Any]:
        return {
            'message': self.adapter.get_help_text(),
            'suggested_actions': [],
            'context': {}
        }

    def _query_reports_response(self) -> Dict[str, Any]:
        report_data = self.adapter.get_report_data(self.db)
        return {
            'message': report_data.get('message', ''),
            'suggested_actions': [],
            'context': report_data.get('stats', {}),
        }

    def _execute_ontology_query(
        self,
        structured_query_dict: Dict[str, Any],
        user: Any
    ) -> Dict[str, Any]:
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

            # Ensure entity model is registered (lazy fallback for non-bootstrapped contexts)
            if registry.get_model(query.entity) is None and self._model_resolver:
                model_cls = self._model_resolver(query.entity)
                if model_cls is not None:
                    registry.register_model(query.entity, model_cls)

            # 所有查询统一使用 QueryEngine（不再区分简单/复杂）
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

            # Use descriptive summary for small result sets
            rows = result.get("rows", [])
            columns = result.get("columns", [])
            column_keys = result.get("column_keys", [])
            descriptive = self._descriptive_summary_fn(rows, columns, column_keys) if self._descriptive_summary_fn else ""
            message = descriptive or result.get("summary", result.get("message", "查询完成"))

            return {
                "message": message,
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

    def _validate_and_correct_fields(self, query_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证和纠正 LLM 返回的字段名

        使用 registry 关系元数据动态构建字段映射，而非硬编码映射表。
        支持：
        - 关系路径映射（guest_name → guest.name）
        - 模糊匹配（check_in_date → check_in_time）

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

        # 从 registry 关系动态构建字段映射
        field_mappings = self._build_dynamic_field_mappings(entity_name, valid_fields, entity_schema)

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

    def _build_dynamic_field_mappings(
        self, entity_name: str, valid_fields: set, entity_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        从 registry 关系元数据动态构建字段名映射。

        Builds mappings like:
        - "guest_name" → "guest.name"  (from relationship "guest" + field "name")
        - "room_number" → "room.room_number"  (from relationship "room" + field "room_number")
        - "room_status" → "status"  (prefix stripping for entity's own fields)
        """
        mappings = {}
        relationships = entity_schema.get("relationships", {})

        for rel_name, rel_info in relationships.items():
            # For each valid field that starts with "rel_name.", build an underscore variant
            for field in valid_fields:
                if field.startswith(f"{rel_name}."):
                    # "guest.name" → key "guest_name"
                    suffix = field[len(rel_name) + 1:]
                    underscore_key = f"{rel_name}_{suffix}".replace(".", "_")
                    if underscore_key not in valid_fields:
                        mappings[underscore_key] = field

        # Also handle entity_name prefix stripping (e.g., "room_status" → "status")
        entity_lower = entity_name.lower()
        for field in valid_fields:
            prefixed = f"{entity_lower}_{field}"
            if prefixed not in valid_fields:
                mappings[prefixed] = field

        return mappings

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

    def execute_action(self, action: Dict[str, Any], user: Any) -> Dict[str, Any]:
        """
        执行动作 - OODA 循环的 Act 阶段
        所有操作通过 ActionRegistry 分发执行
        """
        action_type = action.get('action_type')
        params = action.get('params', {})

        # All actions dispatch via ActionRegistry
        if self.use_action_registry():
            registry = self.get_action_registry()
            if registry and registry.get_action(action_type):
                try:
                    logger.info(f"Executing {action_type} via ActionRegistry")
                    return self.dispatch_via_registry(action_type, params, user)
                except Exception as e:
                    logger.error(f"Registry dispatch failed for {action_type}: {e}")
                    return {"success": False, "message": f"操作执行失败: {str(e)}"}

        return {
            'success': False,
            'message': f'不支持的操作类型：{action_type}'
        }


__all__ = ["OodaOrchestrator"]
