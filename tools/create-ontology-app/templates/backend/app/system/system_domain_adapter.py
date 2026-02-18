"""
SystemDomainAdapter — 系统管理域适配器

将系统管理实体注入 OAG (Ontology-Augmented Generation) 管线，
使用户能通过自然语言 Chat 查询系统管理数据。
"""
from typing import Dict, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.ontology.registry import OntologyRegistry

from core.ontology.domain_adapter import IDomainAdapter
from core.ontology.metadata import (
    EntityMetadata,
    PropertyMetadata,
)


class SystemDomainAdapter(IDomainAdapter):
    """系统功能域适配器"""

    def get_domain_name(self) -> str:
        return "System Management"

    def register_ontology(self, registry: "OntologyRegistry") -> None:
        self._register_models(registry)
        self._register_entities(registry)

    def get_current_state(self) -> Dict[str, Any]:
        """Return current system state summary."""
        return {
            "domain": "system_management",
            "description": "System module entities registered for OAG queries",
        }

    def execute_action(self, action_type: str, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """System actions are dispatched via ActionRegistry, not here."""
        return {"error": f"Unknown system action: {action_type}"}

    def get_llm_system_prompt_additions(self) -> str:
        return (
            "## 系统管理能力\n"
            "你可以帮助用户查询系统管理信息，包括角色、权限、数据字典、系统配置、"
            "部门、岗位、站内消息、系统公告、定时任务等。\n"
            "- 查询类操作可直接执行\n"
            "- 定时任务支持查询、启动、停止、立即执行操作（需确认）\n"
            "- 涉及安全的修改操作（角色权限、菜单配置、组织架构等）请引导用户到管理界面操作\n"
        )

    def _register_models(self, registry: "OntologyRegistry") -> None:
        """Register ORM model classes for registry-driven queries."""
        from app.system.models.rbac import SysRole, SysPermission
        from app.system.models.menu import SysMenu
        from app.system.models.dict import SysDictType, SysDictItem
        from app.system.models.config import SysConfig
        from app.system.models.org import SysDepartment, SysPosition
        from app.system.models.message import SysMessage, SysAnnouncement
        from app.system.models.scheduler import SysJob

        models = {
            "SysRole": SysRole,
            "SysPermission": SysPermission,
            "SysMenu": SysMenu,
            "SysDictType": SysDictType,
            "SysDictItem": SysDictItem,
            "SysConfig": SysConfig,
            "SysDepartment": SysDepartment,
            "SysPosition": SysPosition,
            "SysMessage": SysMessage,
            "SysAnnouncement": SysAnnouncement,
            "SysJob": SysJob,
        }
        for name, cls in models.items():
            registry.register_model(name, cls)

    _DISPLAY_NAMES = {
        "id": "主键", "code": "编码", "name": "名称", "description": "描述",
        "data_scope": "数据范围", "sort_order": "排序", "is_system": "是否系统内置",
        "is_active": "是否启用", "created_at": "创建时间", "updated_at": "更新时间",
        "type": "类型", "resource": "资源", "action": "操作", "parent_id": "父级ID",
        "path": "路由路径", "icon": "图标", "component": "组件",
        "permission_code": "权限编码", "menu_type": "菜单类型", "is_visible": "是否可见",
        "label": "显示文本", "value": "存储值", "color": "颜色", "extra": "扩展属性",
        "is_default": "是否默认", "dict_type_id": "字典类型ID",
        "key": "配置键", "group_code": "配置分组", "value_type": "值类型",
        "is_sensitive": "是否敏感", "is_public": "是否公开",
        # org
        "leader_id": "部门负责人ID", "department_id": "部门ID", "position_id": "岗位ID",
        # message
        "sender_id": "发送人ID", "recipient_id": "接收人ID", "title": "标题",
        "content": "内容", "msg_type": "消息类型", "is_read": "是否已读", "read_at": "阅读时间",
        "related_entity_type": "关联实体类型", "related_entity_id": "关联实体ID",
        # announcement
        "publisher_id": "发布人ID", "status": "状态", "publish_at": "发布时间",
        "expire_at": "过期时间", "is_pinned": "是否置顶",
        # scheduler
        "invoke_target": "执行目标", "cron_expression": "Cron表达式",
        "misfire_policy": "错过策略", "is_concurrent": "允许并发", "group": "分组",
    }

    def _auto_register_properties(self, entity_meta: EntityMetadata, model_class) -> EntityMetadata:
        """Auto-discover ORM columns and register as PropertyMetadata."""
        from sqlalchemy import inspect as sa_inspect, String, Integer, Float, Numeric, Boolean, Text, Date, DateTime
        mapper = sa_inspect(model_class)
        for col in mapper.columns:
            col_name = col.key
            if col_name in entity_meta.properties:
                continue

            col_type = type(col.type)
            if col_type in (String, Text) or issubclass(col_type, String):
                prop_type, py_type = "string", "str"
            elif col_type in (Integer,) or issubclass(col_type, Integer):
                prop_type, py_type = "integer", "int"
            elif col_type in (Float, Numeric) or issubclass(col_type, (Float, Numeric)):
                prop_type, py_type = "number", "float"
            elif col_type in (Boolean,) or issubclass(col_type, Boolean):
                prop_type, py_type = "boolean", "bool"
            elif col_type in (DateTime,) or issubclass(col_type, DateTime):
                prop_type, py_type = "datetime", "datetime"
            else:
                prop_type, py_type = "string", "str"

            is_fk = bool(col.foreign_keys)
            fk_target = None
            if is_fk and col.foreign_keys:
                fk_target = list(col.foreign_keys)[0].target_fullname.split(".")[0]

            entity_meta.add_property(PropertyMetadata(
                name=col_name,
                type=prop_type,
                python_type=py_type,
                is_primary_key=col.primary_key,
                is_foreign_key=is_fk,
                foreign_key_target=fk_target,
                is_required=not col.nullable and not col.primary_key,
                is_unique=col.unique or False,
                is_nullable=col.nullable if col.nullable is not None else True,
                description=self._DISPLAY_NAMES.get(col_name, col_name),
                display_name=self._DISPLAY_NAMES.get(col_name, ""),
                security_level="INTERNAL",
            ))
        return entity_meta

    def _register_entities(self, registry: "OntologyRegistry") -> None:
        """Register system entities with chat access metadata."""
        from app.system.models.rbac import SysRole, SysPermission
        from app.system.models.menu import SysMenu
        from app.system.models.dict import SysDictType, SysDictItem
        from app.system.models.config import SysConfig
        from app.system.models.org import SysDepartment, SysPosition
        from app.system.models.message import SysMessage, SysAnnouncement
        from app.system.models.scheduler import SysJob

        # SysRole — queryable, not mutable via chat
        role_meta = EntityMetadata(
            name="SysRole",
            description="系统角色 — 定义用户权限组合",
            table_name="sys_role",
            category="system",
            extensions={
                "chat_access": {
                    "queryable": True,
                    "mutable_via_chat": False,
                    "security_reason": "角色权限绑定属安全关键操作",
                }
            },
        )
        role_meta = self._auto_register_properties(role_meta, SysRole)
        registry.register_entity(role_meta)

        # SysPermission — queryable (sysadmin only), not mutable
        perm_meta = EntityMetadata(
            name="SysPermission",
            description="系统权限 — 定义可授予角色的操作权限",
            table_name="sys_permission",
            category="system",
            extensions={
                "chat_access": {
                    "queryable": True,
                    "mutable_via_chat": False,
                    "allowed_query_roles": ["sysadmin"],
                    "security_reason": "权限定义属安全关键数据",
                }
            },
        )
        perm_meta = self._auto_register_properties(perm_meta, SysPermission)
        registry.register_entity(perm_meta)

        # SysMenu — queryable (sysadmin), not mutable
        menu_meta = EntityMetadata(
            name="SysMenu",
            description="系统菜单 — 定义前端菜单结构",
            table_name="sys_menu",
            category="system",
            extensions={
                "chat_access": {
                    "queryable": True,
                    "mutable_via_chat": False,
                    "allowed_query_roles": ["sysadmin"],
                }
            },
        )
        menu_meta = self._auto_register_properties(menu_meta, SysMenu)
        registry.register_entity(menu_meta)

        # SysDictType — queryable, mutable (low risk)
        dict_type_meta = EntityMetadata(
            name="SysDictType",
            description="数据字典类型 — 业务枚举分类定义",
            table_name="sys_dict_type",
            category="system",
            extensions={
                "chat_access": {
                    "queryable": True,
                    "mutable_via_chat": True,
                    "requires_confirmation": True,
                }
            },
        )
        dict_type_meta = self._auto_register_properties(dict_type_meta, SysDictType)
        registry.register_entity(dict_type_meta)

        # SysDictItem — queryable, mutable (low risk)
        dict_item_meta = EntityMetadata(
            name="SysDictItem",
            description="数据字典项 — 业务枚举值定义",
            table_name="sys_dict_item",
            category="system",
            extensions={
                "chat_access": {
                    "queryable": True,
                    "mutable_via_chat": True,
                    "requires_confirmation": True,
                }
            },
        )
        dict_item_meta = self._auto_register_properties(dict_item_meta, SysDictItem)
        registry.register_entity(dict_item_meta)

        # SysConfig — queryable (by group), partially mutable
        config_meta = EntityMetadata(
            name="SysConfig",
            description="系统配置 — 运行时可调参数",
            table_name="sys_config",
            category="system",
            extensions={
                "chat_access": {
                    "queryable": True,
                    "mutable_via_chat": False,
                    "security_reason": "配置修改走管理界面",
                }
            },
        )
        config_meta = self._auto_register_properties(config_meta, SysConfig)
        registry.register_entity(config_meta)

        # SysDepartment — queryable, not mutable via chat
        dept_meta = EntityMetadata(
            name="SysDepartment",
            description="部门 — 组织架构树形结构",
            table_name="sys_department",
            category="system",
            extensions={
                "chat_access": {
                    "queryable": True,
                    "mutable_via_chat": False,
                    "security_reason": "组织架构调整走管理界面",
                }
            },
        )
        dept_meta = self._auto_register_properties(dept_meta, SysDepartment)
        registry.register_entity(dept_meta)

        # SysPosition — queryable, not mutable via chat
        pos_meta = EntityMetadata(
            name="SysPosition",
            description="岗位 — 组织内岗位定义",
            table_name="sys_position",
            category="system",
            extensions={
                "chat_access": {
                    "queryable": True,
                    "mutable_via_chat": False,
                    "security_reason": "岗位调整走管理界面",
                }
            },
        )
        pos_meta = self._auto_register_properties(pos_meta, SysPosition)
        registry.register_entity(pos_meta)

        # SysMessage — queryable (own messages), not mutable
        msg_meta = EntityMetadata(
            name="SysMessage",
            description="站内消息 — 系统通知和业务提醒",
            table_name="sys_message",
            category="system",
            extensions={
                "chat_access": {
                    "queryable": True,
                    "mutable_via_chat": False,
                    "security_reason": "消息管理走消息中心",
                }
            },
        )
        msg_meta = self._auto_register_properties(msg_meta, SysMessage)
        registry.register_entity(msg_meta)

        # SysAnnouncement — queryable, not mutable
        ann_meta = EntityMetadata(
            name="SysAnnouncement",
            description="系统公告 — 面向全体用户的通知",
            table_name="sys_announcement",
            category="system",
            extensions={
                "chat_access": {
                    "queryable": True,
                    "mutable_via_chat": False,
                    "security_reason": "公告发布走管理界面",
                }
            },
        )
        ann_meta = self._auto_register_properties(ann_meta, SysAnnouncement)
        registry.register_entity(ann_meta)

        # SysJob — queryable, mutable via chat (start/stop)
        job_meta = EntityMetadata(
            name="SysJob",
            description="定时任务 — 后台定时执行的系统任务",
            table_name="sys_job",
            category="system",
            extensions={
                "chat_access": {
                    "queryable": True,
                    "mutable_via_chat": True,
                    "requires_confirmation": True,
                    "allowed_query_roles": ["sysadmin"],
                    "security_reason": "任务启停需确认",
                }
            },
        )
        job_meta = self._auto_register_properties(job_meta, SysJob)
        registry.register_entity(job_meta)
