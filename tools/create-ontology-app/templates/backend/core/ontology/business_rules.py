"""
core/ontology/business_rules.py

领域业务规则 - 声明式定义，供 AI 查询使用

设计原则：
1. 规则与本体元数据（EntityMetadata）联动
2. 支持运行时查询
3. 可导出为 LLM prompt、文档、测试用例
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set
from enum import Enum
import json
import threading


class RuleType(Enum):
    """规则类型"""
    QUERY_EXPANSION = "query_expansion"  # 查询扩展（如"空闲房间" → 包含多种状态）
    VALUE_MAPPING = "value_mapping"      # 值映射（如"今天" → 具体日期）
    ALIAS_DEFINITION = "alias_definition"  # 别名定义
    VALIDATION = "validation"              # 验证规则


@dataclass
class BusinessRule:
    """
    业务规则定义

    Example:
        BusinessRule(
            id="vacant_room_expansion",
            name="空闲房间查询扩展",
            rule_type=RuleType.QUERY_EXPANSION,
            entity="Room",
            trigger_keywords=["空闲", "可住", "可用", "空房"],
            condition={"field": "status", "operator": "in", "value": ["vacant_clean", "vacant_dirty"]},
            description="查询空闲房间时，应包含净房和脏房两种状态"
        )
    """
    id: str                                          # 唯一标识
    name: str                                        # 规则名称
    rule_type: RuleType                              # 规则类型
    entity: Optional[str] = None                     # 关联实体
    trigger_keywords: List[str] = field(default_factory=list)  # 触发关键词
    condition: Dict[str, Any] = field(default_factory=dict)  # 规则条件
    alias_mapping: Dict[str, Any] = field(default_factory=dict)  # 别名映射
    description: str = ""                             # 描述

    def to_llm_prompt(self) -> str:
        """导出为 LLM prompt 格式"""
        if self.rule_type == RuleType.QUERY_EXPANSION:
            values_str = ", ".join(self.condition.get("value", []))
            return f"""- {self.name}:
  - 触发词: {", ".join(self.trigger_keywords)}
  - 查询 {self.entity} 时，{self.condition.get("field")} 应使用 in 操作符
  - 值设为 [{values_str}]
  - 示例: "列举{'/'.join(self.trigger_keywords[:2])}房间" → filters: [{{"field": "{self.condition.get("field")}", "operator": "in", "value": {self.condition.get("value")}}}]"""

        elif self.rule_type == RuleType.ALIAS_DEFINITION:
            return f"""- {self.name}:
  - 别名: {", ".join(self.alias_mapping.keys())} → 标准值: {", ".join(self.alias_mapping.values())}"""

        return ""


@dataclass
class BusinessRuleRegistry:
    """
    业务规则注册表

    提供规则的注册、查询、导出功能。
    与 OntologyRegistry 分离，专注于业务规则。
    """
    _instance: Optional['BusinessRuleRegistry'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._rules: Dict[str, BusinessRule] = {}
        self._rules_by_entity: Dict[str, List[str]] = {}
        self._rules_by_type: Dict[RuleType, List[str]] = {}
        self._initialized = True

    def register(self, rule: BusinessRule) -> None:
        """注册规则"""
        self._rules[rule.id] = rule

        if rule.entity:
            if rule.entity not in self._rules_by_entity:
                self._rules_by_entity[rule.entity] = []
            self._rules_by_entity[rule.entity].append(rule.id)

        if rule.rule_type not in self._rules_by_type:
            self._rules_by_type[rule.rule_type] = []
        self._rules_by_type[rule.rule_type].append(rule.id)

    def get(self, rule_id: str) -> Optional[BusinessRule]:
        """获取规则"""
        return self._rules.get(rule_id)

    def get_by_entity(self, entity: str) -> List[BusinessRule]:
        """获取实体的所有规则"""
        rule_ids = self._rules_by_entity.get(entity, [])
        return [self._rules[rid] for rid in rule_ids]

    def get_by_type(self, rule_type: RuleType) -> List[BusinessRule]:
        """获取特定类型的所有规则"""
        rule_ids = self._rules_by_type.get(rule_type, [])
        return [self._rules[rid] for rid in rule_ids]

    def find_matching_rules(self, entity: str, keywords: List[str]) -> List[BusinessRule]:
        """根据实体和关键词查找匹配的规则"""
        matching = []

        # 1. 实体匹配
        entity_rules = self.get_by_entity(entity)

        # 2. 关键词匹配
        keyword_set = set(k.lower() for k in keywords)

        for rule in entity_rules:
            if any(kw.lower() in keyword_set for kw in rule.trigger_keywords):
                matching.append(rule)

        return matching

    def export_for_llm(self, entity: Optional[str] = None) -> str:
        """导出为 LLM prompt 格式"""
        if entity:
            rules = self.get_by_entity(entity)
        else:
            rules = list(self._rules.values())

        prompts = []
        for rule in rules:
            if rule and rule.to_llm_prompt:
                prompt = rule.to_llm_prompt()
                if prompt:
                    prompts.append(prompt)

        return "\n".join(prompts)

    def export_json(self) -> str:
        """导出为 JSON（用于文档、测试等）"""
        rules_data = []
        for rule in self._rules.values():
            rules_data.append({
                "id": rule.id,
                "name": rule.name,
                "rule_type": rule.rule_type.value,
                "entity": rule.entity,
                "trigger_keywords": rule.trigger_keywords,
                "condition": rule.condition,
                "alias_mapping": rule.alias_mapping,
                "description": rule.description
            })

        return json.dumps(rules_data, ensure_ascii=False, indent=2)


# 全局单例
business_rules = BusinessRuleRegistry()


def init_default_business_rules() -> None:
    """
    初始化默认业务规则

    This is a no-op in the core layer. Domain-specific business rules
    should be initialized by the domain layer directly (e.g., in app lifespan
    or domain adapter).
    """
    pass


# 便捷函数
def get_business_rules() -> BusinessRuleRegistry:
    """获取业务规则注册表"""
    return BusinessRuleRegistry()


__all__ = [
    "BusinessRule",
    "BusinessRuleRegistry",
    "RuleType",
    "business_rules",
    "init_default_business_rules",
    "get_business_rules"
]
