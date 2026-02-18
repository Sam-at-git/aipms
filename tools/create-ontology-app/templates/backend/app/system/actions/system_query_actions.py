"""
系统实体查询 Action — 复用 ontology_query 引擎，增加系统实体访问控制
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from core.ai.actions import ActionRegistry
from core.ontology.registry import registry as ontology_registry
from app.hotel.models.ontology import Employee, EmployeeRole
from app.services.actions.query_actions import handle_ontology_query
from app.services.actions.base import OntologyQueryParams


# System entity names registered by SystemDomainAdapter
SYSTEM_ENTITIES = {"SysRole", "SysPermission", "SysMenu", "SysDictType", "SysDictItem", "SysConfig", "SysDepartment", "SysPosition", "SysMessage", "SysAnnouncement", "SysJob"}


def _check_system_query_permission(entity_name: str, user: Employee) -> Optional[str]:
    """Check if user can query this system entity.

    Returns error message if denied, None if allowed.
    """
    entity_meta = ontology_registry.get_entity(entity_name)
    if not entity_meta:
        return None  # Let ontology_query handle unknown entities

    chat_access = getattr(entity_meta, 'extensions', {}).get("chat_access", {}) if hasattr(entity_meta, 'extensions') else {}
    if not chat_access:
        return None

    # Check if entity is queryable via chat
    if not chat_access.get("queryable", True):
        return f"{entity_name} 不支持通过对话查询"

    # Check allowed roles
    allowed_roles = chat_access.get("allowed_query_roles")
    if allowed_roles:
        user_role = user.role.value if hasattr(user.role, 'value') else str(user.role)
        if user_role not in allowed_roles:
            return f"权限不足，无法查询 {entity_name}"

    return None


def handle_query_system(
    params: OntologyQueryParams,
    db: Session,
    user: Employee,
    **context
) -> Dict[str, Any]:
    """Execute system entity query with access control."""
    entity_name = params.entity

    # If querying a system entity, check permissions
    if entity_name in SYSTEM_ENTITIES:
        error = _check_system_query_permission(entity_name, user)
        if error:
            return {"success": False, "message": error}

    # Delegate to standard ontology_query engine
    return handle_ontology_query(params, db, user, **context)


def register_system_query_actions(registry: ActionRegistry) -> None:
    """Register system entity query action."""
    registry.register(
        name="query_system",
        entity="System",
        description="查询系统管理数据（角色、权限、菜单、数据字典、系统配置、定时任务等）。支持字段选择、过滤条件、排序。",
        category="query",
        requires_confirmation=False,
        allowed_roles=set(),
        undoable=False,
        side_effects=[],
        search_keywords=[
            "系统", "角色", "权限", "字典", "配置", "菜单", "定时任务",
            "system", "role", "permission", "dict", "config", "menu", "scheduler", "job",
            "数据字典", "系统配置", "权限管理", "角色管理", "任务调度",
        ],
    )(handle_query_system)
