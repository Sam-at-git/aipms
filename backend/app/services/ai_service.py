"""
AI 对话服务 — Hotel domain wrapper around OodaOrchestrator.

Provides backward-compatible AIService that injects hotel-specific
dependencies into the domain-agnostic OODA orchestrator.
"""
import logging
from sqlalchemy.orm import Session
from app.models.ontology import Employee
from app.services.llm_service import LLMService, TopicRelevance
from app.services.actions.query_actions import _build_descriptive_summary
from app.models.schemas import MissingField

from core.ai.ooda_orchestrator import OodaOrchestrator

logger = logging.getLogger(__name__)

# Domain rules (optional)
try:
    from app.hotel.domain.rules import register_all_rules
    CORE_RULES_AVAILABLE = True
except ImportError:
    CORE_RULES_AVAILABLE = False

# Domain metadata (optional)
try:
    from app.hotel.domain.metadata import (
        get_security_level,
        get_action_requirements,
        should_skip_confirmation,
    )
    CORE_METADATA_AVAILABLE = True
except ImportError:
    CORE_METADATA_AVAILABLE = False


def _init_domain_rules():
    """Register hotel business rules into the core rule engine."""
    from core.engine.rule_engine import rule_engine
    register_all_rules(rule_engine)


def _resolve_ontology_model(name: str):
    """Resolve an ORM model class by name from app.models.ontology."""
    from app.models import ontology as _models
    return getattr(_models, name, None)


class SystemCommandHandler:
    """处理以 # 开头的系统指令（仅 sysadmin）"""

    _entity_aliases_cache: dict = None

    @classmethod
    def _build_entity_aliases(cls) -> dict:
        """从 OntologyRegistry 动态构建实体别名映射"""
        from core.ontology.registry import OntologyRegistry
        import re as _re

        registry = OntologyRegistry()
        aliases = {}
        entity_names = set()

        for entity in registry.get_entities():
            name = entity.name
            entity_names.add(name)

            # 1. Exact lowercase name → entity (e.g., 'stayrecord' → 'StayRecord')
            aliases[name.lower()] = name

            # 2. Lowercase + 's' for English plural (e.g., 'rooms' → 'Room')
            aliases[name.lower() + 's'] = name

            # 3. Extract Chinese aliases from description (before " - " separator)
            desc = entity.description or ""
            if " - " in desc:
                cn_part = desc.split(" - ")[0].strip()
            elif "——" in desc:
                cn_part = desc.split("——")[0].strip()
            else:
                cn_part = ""

            if cn_part:
                aliases[cn_part] = name
                # For 4+ char Chinese terms, also add first 2 chars as shorter alias
                if len(cn_part) >= 4:
                    aliases[cn_part[:2]] = name
                    if cn_part.startswith("酒店"):
                        aliases[cn_part[2:]] = name

        # 4. CamelCase split: add first word as alias if no name conflict
        for entity in registry.get_entities():
            name = entity.name
            parts = _re.findall(r'[A-Z][a-z]*', name)
            if len(parts) > 1:
                first_part = parts[0].lower()
                if first_part not in aliases or aliases[first_part] == name:
                    aliases[first_part] = name

        return aliases

    @classmethod
    def get_entity_aliases(cls) -> dict:
        """获取实体别名映射（带缓存）"""
        if cls._entity_aliases_cache is None:
            cls._entity_aliases_cache = cls._build_entity_aliases()
        return cls._entity_aliases_cache

    @property
    def ENTITY_ALIASES(self) -> dict:
        return self.get_entity_aliases()

    def is_system_command(self, message: str) -> bool:
        """判断是否为系统指令（# 后跟字母或中文，不跟数字）"""
        msg = message.strip()
        if not msg.startswith('#'):
            return False
        if len(msg) < 2:
            return False
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

        if cmd.startswith('查询') and '对象' in cmd:
            entity_name = cmd.replace('查询', '').replace('对象定义', '').replace('对象', '').strip()
            return self._query_entity(entity_name, db)

        if cmd.lower() in ('日志', 'logs', 'log', '审计日志'):
            return self._query_logs(db)

        return self._query_entity(cmd, db)

    def _query_entity(self, name: str, db: Session) -> dict:
        """查询实体元数据"""
        lookup = name.lower().strip()
        entity_name = self.ENTITY_ALIASES.get(lookup, name)

        try:
            from app.services.ontology_metadata_service import OntologyMetadataService
            service = OntologyMetadataService(db)
            semantic = service.get_semantic_metadata()

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


class AIService(OodaOrchestrator):
    """Hotel-domain AI service — backward-compatible wrapper.

    Subclasses OodaOrchestrator and injects hotel-specific dependencies.
    """

    # Backward-compatible service access via __getattr__
    _SERVICE_ATTRS = {
        'room_service': '_room_service',
        'reservation_service': '_reservation_service',
        'checkin_service': '_checkin_service',
        'checkout_service': '_checkout_service',
        'task_service': '_task_service',
        'billing_service': '_billing_service',
        'report_service': '_report_service',
        'param_parser': '_param_parser',
    }

    def __getattr__(self, name):
        if name in self._SERVICE_ATTRS:
            adapter = object.__getattribute__(self, 'adapter')
            adapter._ensure_services()
            return getattr(adapter, self._SERVICE_ATTRS[name])
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __init__(self, db: Session, adapter=None):
        if adapter is None:
            from app.hotel.hotel_domain_adapter import HotelDomainAdapter
            adapter = HotelDomainAdapter(db)

        from app.services.actions import get_action_registry

        super().__init__(
            db=db,
            adapter=adapter,
            llm_service=LLMService(),
            system_command_handler=SystemCommandHandler(),
            action_registry_factory=get_action_registry,
            missing_field_class=MissingField,
            descriptive_summary_fn=_build_descriptive_summary,
            topic_continuation=TopicRelevance.CONTINUATION,
            topic_followup_answer=TopicRelevance.FOLLOWUP_ANSWER,
            model_resolver=_resolve_ontology_model,
            domain_rules_init=_init_domain_rules if CORE_RULES_AVAILABLE else None,
        )

        # Set domain metadata availability
        self.use_core_metadata = CORE_METADATA_AVAILABLE
