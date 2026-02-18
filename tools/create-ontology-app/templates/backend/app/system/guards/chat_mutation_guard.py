"""
ChatMutationGuard — 安全拦截层

拦截通过 Chat 对安全关键系统实体的写操作。
即使 LLM 意外生成了不存在的 action_type（如 assign_role），
此 guard 作为最后防线确保不会执行。
"""
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass


@dataclass
class GuardResult:
    """Guard check result"""
    blocked: bool
    message: str = ""


class ChatMutationGuard:
    """
    拦截通过 Chat 对安全关键系统实体的写操作。
    """

    # 永远不可通过 Chat 修改的实体
    IMMUTABLE_VIA_CHAT: Set[str] = {
        "SysRole", "SysPermission", "SysMenu",
        "Role", "Permission", "RolePermission",
        "UserRole", "Menu",
    }

    # 永远不可通过 Chat 修改的配置分组
    IMMUTABLE_CONFIG_GROUPS: Set[str] = {"security", "llm"}

    # 实体名称到管理界面路径的映射
    _ENTITY_ADMIN_PATHS: Dict[str, str] = {
        "SysRole": "系统管理 > 权限管理",
        "Role": "系统管理 > 权限管理",
        "SysPermission": "系统管理 > 权限管理",
        "Permission": "系统管理 > 权限管理",
        "SysMenu": "系统管理 > 菜单管理",
        "Menu": "系统管理 > 菜单管理",
        "RolePermission": "系统管理 > 权限管理",
        "UserRole": "系统管理 > 权限管理",
    }

    def check(
        self,
        action_name: str,
        entity: str,
        category: str,
        params: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Optional[GuardResult]:
        """Check if a chat-initiated action should be blocked.

        Args:
            action_name: The action being attempted
            entity: Target entity name
            category: Action category (query, mutation, etc.)
            params: Action parameters
            context: Execution context

        Returns:
            GuardResult if blocked, None if allowed
        """
        # Only intercept chat-initiated actions
        if not context.get("via_chat", False):
            return None

        # Query operations are always allowed (access control is in the query handler)
        if category == "query":
            return None

        # Block mutations on immutable entities
        if entity in self.IMMUTABLE_VIA_CHAT:
            admin_path = self._ENTITY_ADMIN_PATHS.get(entity, "系统管理界面")
            return GuardResult(
                blocked=True,
                message=(
                    f"{entity} 的修改操作需要在管理界面完成，"
                    f"请前往「{admin_path}」进行操作。"
                ),
            )

        # Block mutations on sensitive config groups
        if entity in ("SysConfig", "SystemConfig", "Config"):
            group = params.get("group_code", "") or params.get("group", "")
            if group in self.IMMUTABLE_CONFIG_GROUPS:
                return GuardResult(
                    blocked=True,
                    message=f"「{group}」分组的配置不允许通过对话修改，请前往「系统管理 > 系统配置」操作。",
                )

        return None


# Singleton instance
chat_mutation_guard = ChatMutationGuard()
