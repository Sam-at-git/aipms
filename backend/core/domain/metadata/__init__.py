"""
core/domain/metadata/ - 元数据配置模块

提供运行时可调整的元数据配置，包括：
- 安全等级配置（属性级访问控制）
- HITL 策略配置（人类在环确认）
"""
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml


# 配置文件路径
_metadata_dir = Path(__file__).parent
_security_levels_file = _metadata_dir / "security_levels.yaml"
_hitl_policies_file = _metadata_dir / "hitl_policies.yaml"


def load_security_levels() -> Dict[str, Dict[str, str]]:
    """
    加载安全等级配置

    Returns:
        实体属性到安全等级的映射
        {
            "Room": {"id": "PUBLIC", "status": "PUBLIC", ...},
            "Guest": {"name": "PUBLIC", "id_number": "RESTRICTED", ...},
            ...
        }
    """
    with open(_security_levels_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_hitl_policies() -> Dict[str, Any]:
    """
    加载 HITL 策略配置

    Returns:
        HITL 策略配置字典
        {
            "high_risk_actions": [...],
            "medium_risk_actions": [...],
            "role_exemptions": {...},
            ...
        }
    """
    with open(_hitl_policies_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_security_level(entity_type: str, property_name: str) -> str:
    """
    获取指定实体属性的安全等级

    Args:
        entity_type: 实体类型（如 "Room", "Guest"）
        property_name: 属性名（如 "price", "id_number"）

    Returns:
        安全等级（PUBLIC, INTERNAL, RESTRICTED, CONFIDENTIAL）
        如果未定义则返回 "INTERNAL"
    """
    config = load_security_levels()

    if entity_type in config:
        entity_config = config[entity_type]
        if property_name in entity_config:
            return entity_config[property_name]

    # 检查全局默认值
    if "defaults" in config and property_name in config["defaults"]:
        return config["defaults"][property_name]

    return "INTERNAL"


def get_action_confirmation_level(action_type: str) -> str:
    """
    获取操作的确认级别

    Args:
        action_type: 操作类型（如 "checkout", "adjust_bill"）

    Returns:
        确认级别（NONE, LOW, MEDIUM, HIGH, CRITICAL）
        如果未定义则返回 "MEDIUM"
    """
    config = load_hitl_policies()

    # 按优先级检查各策略组
    for category in ["high_risk_actions", "medium_risk_actions", "low_risk_actions"]:
        if category in config:
            for action_config in config[category]:
                if action_config.get("action_type") == action_type:
                    return action_config.get("level", "MEDIUM")

    # 检查查询操作
    if "query_actions" in config:
        for action_config in config["query_actions"]:
            if action_config.get("action_type") == action_type:
                return action_config.get("level", "NONE")

    return "MEDIUM"


def get_action_requirements(action_type: str) -> Dict[str, Any]:
    """
    获取操作的所有要求配置

    Args:
        action_type: 操作类型

    Returns:
        操作配置字典，包含：
        - level: 确认级别
        - require_confirmation: 是否需要确认
        - require_reason: 是否需要原因
        - allowed_roles: 允许的角色列表
        - description: 操作描述
    """
    config = load_hitl_policies()

    # 搜索所有策略组
    for category in ["high_risk_actions", "medium_risk_actions", "low_risk_actions", "query_actions"]:
        if category in config:
            for action_config in config[category]:
                if action_config.get("action_type") == action_type:
                    return action_config

    # 默认返回中等风险配置
    return {
        "action_type": action_type,
        "level": "MEDIUM",
        "require_confirmation": True,
        "allowed_roles": ["manager", "receptionist"],
        "description": ""
    }


def get_role_exemptions(role: str) -> List[str]:
    """
    获取角色的豁免操作列表

    Args:
        role: 角色名称（如 "manager", "sysadmin"）

    Returns:
        可以跳过确认的操作类型列表
    """
    config = load_hitl_policies()

    if "role_exemptions" in config and role in config["role_exemptions"]:
        return config["role_exemptions"][role].get("skip_confirmation", [])

    return []


def should_skip_confirmation(action_type: str, user_role: str) -> bool:
    """
    判断是否跳过确认

    Args:
        action_type: 操作类型
        user_role: 用户角色

    Returns:
        是否跳过确认
    """
    exemptions = get_role_exemptions(user_role)
    return action_type in exemptions


__all__ = [
    "load_security_levels",
    "load_hitl_policies",
    "get_security_level",
    "get_action_confirmation_level",
    "get_action_requirements",
    "get_role_exemptions",
    "should_skip_confirmation",
]
