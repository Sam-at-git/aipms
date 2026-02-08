"""
core/reasoning/constraint_engine.py

Constraint reasoning engine - Validates actions against ontology constraints
Part of the universal ontology-driven LLM reasoning framework
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from core.ontology.registry import OntologyRegistry
    from core.ontology.metadata import ConstraintMetadata, ConstraintSeverity


from core.ontology.metadata import (
    ConstraintEvaluationContext,
    IConstraintValidator,
    ConstraintSeverity,
)


@dataclass
class ConstraintValidationResult:
    """约束验证结果"""
    is_valid: bool = True
    violated_constraints: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def add_violation(
        self,
        constraint: "ConstraintMetadata",
        message: str
    ) -> None:
        """添加违规"""
        self.is_valid = False
        self.violated_constraints.append({
            "constraint_id": constraint.id,
            "constraint_name": constraint.name,
            "severity": constraint.severity.value,
            "message": message
        })

        if hasattr(constraint, 'suggestion_message') and constraint.suggestion_message:
            self.suggestions.append(constraint.suggestion_message)

    def add_warning(
        self,
        constraint: "ConstraintMetadata",
        message: str
    ) -> None:
        """添加警告"""
        self.warnings.append({
            "constraint_id": constraint.id,
            "constraint_name": constraint.name,
            "message": message
        })

        if hasattr(constraint, 'suggestion_message') and constraint.suggestion_message:
            self.suggestions.append(constraint.suggestion_message)

    def to_llm_feedback(self) -> Optional[str]:
        """生成 LLM 反馈"""
        if self.is_valid and not self.warnings:
            return None

        sections = []

        if self.violated_constraints:
            sections.append("**约束违规:**")
            for v in self.violated_constraints:
                sections.append(f"- {v['constraint_name']}: {v['message']}")

        if self.warnings:
            sections.append("\n**警告:**")
            for w in self.warnings:
                sections.append(f"- {w['constraint_name']}: {w['message']}")

        if self.suggestions:
            sections.append("\n**建议:**")
            for s in self.suggestions:
                sections.append(f"- {s}")

        return "\n".join(sections)


class ConstraintEngine:
    """约束推理引擎 - 领域无关"""

    def __init__(self, registry: "OntologyRegistry"):
        """
        初始化约束引擎

        Args:
            registry: 本体注册表实例
        """
        self.registry = registry
        self._custom_validators: Dict[str, IConstraintValidator] = {}

    def register_validator(
        self,
        constraint_id: str,
        validator: IConstraintValidator
    ) -> None:
        """
        注册自定义验证器

        Args:
            constraint_id: 约束ID
            validator: 验证器实例
        """
        self._custom_validators[constraint_id] = validator

    def validate_action(
        self,
        entity_type: str,
        action_type: str,
        params: Dict[str, Any],
        current_state: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> ConstraintValidationResult:
        """
        验证操作是否满足约束

        Args:
            entity_type: 实体类型
            action_type: 操作类型
            params: 操作参数
            current_state: 当前系统状态
            user_context: 用户上下文

        Returns:
            ConstraintValidationResult 验证结果
        """
        result = ConstraintValidationResult()

        # 获取相关约束
        constraints = self.registry.get_constraints_for_entity_action(
            entity_type, action_type
        )

        # 构建评估上下文
        context = ConstraintEvaluationContext(
            entity_type=entity_type,
            action_type=action_type,
            parameters=params,
            current_state=current_state,
            user_context=user_context
        )

        # 评估每个约束
        for constraint in constraints:
            self._evaluate_constraint(constraint, context, result)

        return result

    def _evaluate_constraint(
        self,
        constraint: "ConstraintMetadata",
        context: ConstraintEvaluationContext,
        result: ConstraintValidationResult
    ) -> None:
        """
        评估单个约束

        Args:
            constraint: 约束元数据
            context: 评估上下文
            result: 验证结果对象
        """
        # 检查触发条件
        if hasattr(constraint, 'trigger_conditions') and constraint.trigger_conditions:
            if not self._check_trigger_conditions(
                constraint.trigger_conditions, context
            ):
                return

        # 使用自定义验证器
        if hasattr(constraint, 'validator') and constraint.validator:
            is_valid, message = constraint.validator.validate(context)
            if not is_valid:
                result.add_violation(constraint, message or constraint.error_message or "约束验证失败")
            return

        if constraint.id in self._custom_validators:
            validator = self._custom_validators[constraint.id]
            is_valid, message = validator.validate(context)
            if not is_valid:
                result.add_violation(constraint, message or constraint.error_message or "约束验证失败")
            return

        # 检查严重程度
        if hasattr(constraint, 'severity') and constraint.severity == ConstraintSeverity.ERROR:
            # TODO: 实现 expression evaluation
            # For now, add to warnings as we can't evaluate without expression engine
            result.add_warning(constraint, constraint.description)
        elif hasattr(constraint, 'severity') and constraint.severity == ConstraintSeverity.WARNING:
            result.add_warning(constraint, constraint.description)

    def _check_trigger_conditions(
        self,
        conditions: List[str],
        context: ConstraintEvaluationContext
    ) -> bool:
        """
        检查触发条件

        Args:
            conditions: 条件列表
            context: 评估上下文

        Returns:
            是否满足触发条件
        """
        # TODO: 实现条件表达式评估
        return True

    def get_constraints_for_llm(
        self,
        entity_type: Optional[str] = None,
        action_type: Optional[str] = None
    ) -> str:
        """
        获取约束的 LLM 描述

        Args:
            entity_type: 实体类型过滤
            action_type: 操作类型过滤

        Returns:
            约束的 LLM 友好描述文本
        """
        sections = []

        if entity_type and action_type:
            constraints = self.registry.get_constraints_for_entity_action(
                entity_type, action_type
            )
        elif entity_type:
            constraints = self.registry.get_constraints(entity_type)
        else:
            constraints = self.registry.get_constraints()

        for constraint in constraints:
            if hasattr(constraint, 'to_llm_summary'):
                sections.append(constraint.to_llm_summary())
            else:
                sections.append(f"- {constraint.name}: {constraint.description}")

        return "\n\n".join(sections)


# Export
__all__ = [
    "ConstraintValidationResult",
    "ConstraintEngine",
]
