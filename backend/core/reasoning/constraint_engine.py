"""
core/reasoning/constraint_engine.py

Constraint reasoning engine - Validates actions against ontology constraints
Part of the universal ontology-driven LLM reasoning framework

OAG Enhancement: Adds property-level constraint validation with structured Decision results.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING, Callable
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import re

if TYPE_CHECKING:
    from core.ontology.registry import OntologyRegistry
    from core.ontology.metadata import ConstraintMetadata, ConstraintSeverity, PropertyMetadata
    from sqlalchemy.orm import Session


from core.ontology.metadata import (
    ConstraintEvaluationContext,
    IConstraintValidator,
    ConstraintSeverity,
)


class _DotDict:
    """允许点号访问的字典包装器，用于表达式求值"""
    def __init__(self, d: Dict[str, Any]):
        self._d = d or {}

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return super().__getattribute__(name)
        val = self._d.get(name)
        if isinstance(val, dict):
            return _DotDict(val)
        return val


@dataclass
class ConstraintViolation:
    """约束违规详情"""
    type: str  # 违规类型: FormatValidation, UniquenessValidation, BusinessRule, etc.
    field: str  # 字段名
    constraint: str  # 约束名称
    message: str  # 错误消息
    severity: str = "error"  # error, warning, info


@dataclass
class Decision:
    """
    OAG 决策结果 - 结构化的约束验证决策

    用于在动作执行前返回本体层的决策结果。
    """
    allowed: bool  # 是否允许执行
    reason: str  # 决策原因（自然语言）
    violations: List[ConstraintViolation] = field(default_factory=list)  # 违规详情列表
    suggested_action: Optional[str] = None  # 建议的操作: reject, confirm_with_warning, auto_correct
    correction_prompt: Optional[str] = None  # 给用户的纠正提示
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外元数据

    def to_response_dict(self) -> Dict[str, Any]:
        """转换为API响应格式"""
        return {
            "success": self.allowed,
            "message": self.reason,
            "allowed": self.allowed,
            "violations": [
                {
                    "type": v.type,
                    "field": v.field,
                    "constraint": v.constraint,
                    "message": v.message,
                    "severity": v.severity
                }
                for v in self.violations
            ],
            "suggested_action": self.suggested_action,
            "correction_prompt": self.correction_prompt,
            **self.metadata
        }


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


# ========== OAG 约束验证器实现 ==========


class PhoneFormatValidator:
    """
    手机号格式验证器

    验证中国手机号格式：11位数字，以1开头，第二位为3-9。
    可作为 PropertyMetadata 的 update_validation_rules 使用。
    """

    PHONE_REGEX = re.compile(r'^1[3-9]\d{9}$')

    @classmethod
    def validate(cls, old_value: Any, new_value: Any, entity_id: Optional[int] = None, db: Optional["Session"] = None) -> tuple[bool, str]:
        """
        验证手机号格式

        Args:
            old_value: 原手机号
            new_value: 新手机号
            entity_id: 实体ID（不使用）
            db: 数据库会话（不使用）

        Returns:
            (is_valid, error_message)
        """
        if new_value is None or new_value == "":
            return True, ""  # 空值允许（可选字段）

        if not isinstance(new_value, str):
            new_value = str(new_value)

        if cls.PHONE_REGEX.match(new_value):
            return True, ""

        return False, "手机号必须是11位数字，以1开头，第二位为3-9"

    def __call__(self, old_value: Any, new_value: Any, entity_id: Optional[int] = None, db: Optional["Session"] = None) -> tuple[bool, str]:
        return self.validate(old_value, new_value, entity_id, db)


class FieldUniquenessValidator:
    """
    通用字段唯一性验证器

    检查某实体的某字段值是否已被其他记录使用。
    需要数据库会话来查询现有记录。

    Args:
        entity_name: 实体名称（在 OntologyRegistry 中注册的名称）
        field_name: 需要检查唯一性的字段名
    """

    def __init__(self, entity_name: str, field_name: str):
        """初始化验证器"""
        self._entity_name = entity_name
        self._field_name = field_name
        self._model = None

    def _get_model(self, db: "Session"):
        """动态获取实体模型以避免循环依赖"""
        if self._model is None:
            from core.ontology.registry import OntologyRegistry
            model = OntologyRegistry().get_model(self._entity_name)
            if model is None:
                raise ValueError(f"{self._entity_name} model not registered in OntologyRegistry")
            self._model = model
        return self._model

    def validate(self, old_value: Any, new_value: Any, entity_id: Optional[int] = None, db: Optional["Session"] = None) -> tuple[bool, str]:
        """
        验证字段唯一性

        Args:
            old_value: 原值
            new_value: 新值
            entity_id: 当前实体ID（用于排除自身）
            db: 数据库会话

        Returns:
            (is_valid, error_message)
        """
        if new_value is None or new_value == "" or new_value == old_value:
            return True, ""  # 空值或未变更，无需检查唯一性

        if db is None:
            # 无数据库会话时跳过检查（记录警告）
            return True, ""

        model = self._get_model(db)
        field_attr = getattr(model, self._field_name, None)
        if field_attr is None:
            return True, ""

        # 查询是否有其他记录使用此值
        query = db.query(model).filter(field_attr == new_value)
        if entity_id is not None:
            query = query.filter(model.id != entity_id)

        existing = query.first()
        if existing:
            display_name = getattr(existing, 'name', str(entity_id))
            return False, f"「{new_value}」已被「{display_name}」使用"

        return True, ""

    def __call__(self, old_value: Any, new_value: Any, entity_id: Optional[int] = None, db: Optional["Session"] = None) -> tuple[bool, str]:
        return self.validate(old_value, new_value, entity_id, db)


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

        # 尝试表达式求值
        if hasattr(constraint, 'condition_code') and constraint.condition_code:
            try:
                is_valid = self._evaluate_expression(constraint.condition_code, context)
                if not is_valid:
                    if constraint.severity == ConstraintSeverity.ERROR:
                        result.add_violation(constraint, constraint.error_message or constraint.description)
                    else:
                        result.add_warning(constraint, constraint.error_message or constraint.description)
                return
            except Exception:
                pass  # Fall through to default behavior

        # 默认行为：无法求值时作为警告
        if hasattr(constraint, 'severity') and constraint.severity == ConstraintSeverity.ERROR:
            result.add_warning(constraint, constraint.description)
        elif hasattr(constraint, 'severity') and constraint.severity == ConstraintSeverity.WARNING:
            result.add_warning(constraint, constraint.description)

    def _evaluate_expression(
        self,
        expression: str,
        context: ConstraintEvaluationContext
    ) -> bool:
        """
        求值约束表达式

        支持的表达式格式:
        - "state.field == 'value'" - 状态字段等于
        - "state.field != 'value'" - 状态字段不等于
        - "state.field in ['a', 'b']" - 状态字段在列表中
        - "param.field > 0" - 参数比较
        """
        # 构建安全的求值命名空间
        namespace = {
            "state": _DotDict(context.current_state),
            "param": _DotDict(context.parameters),
            "user": _DotDict(context.user_context),
            "True": True,
            "False": False,
            "None": None,
        }

        try:
            return bool(eval(expression, {"__builtins__": {}}, namespace))
        except Exception:
            raise ValueError(f"Cannot evaluate expression: {expression}")

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

    # ========== OAG 增强方法：属性更新验证 ==========

    def validate_property_update(
        self,
        entity_type: str,
        property_name: str,
        old_value: Any,
        new_value: Any,
        user_context: Dict[str, Any],
        db: Optional["Session"] = None,
        entity_id: Optional[int] = None
    ) -> Decision:
        """
        OAG: 验证属性更新是否满足约束

        这是 OAG 决策流程的核心方法，在执行属性更新前调用。

        Args:
            entity_type: 实体类型
            property_name: 属性名
            old_value: 原值
            new_value: 新值
            user_context: 用户上下文（包含 role 等信息）
            db: 数据库会话（用于唯一性检查等）
            entity_id: 实体ID（用于排除自身）

        Returns:
            Decision 结构化决策结果
        """
        violations = []

        # 1. 获取属性元数据
        entity_metadata = self.registry.get_entity(entity_type)
        if not entity_metadata:
            return Decision(
                allowed=False,
                reason=f"实体 {entity_type} 不存在",
                violations=[],
                suggested_action="reject"
            )

        prop_metadata = entity_metadata.get_property(property_name)
        if not prop_metadata:
            return Decision(
                allowed=False,
                reason=f"属性 {entity_type}.{property_name} 不存在",
                violations=[],
                suggested_action="reject"
            )

        # 2. 检查可变性
        if not getattr(prop_metadata, 'mutable', True):
            return Decision(
                allowed=False,
                reason=f"属性「{property_name}」不可修改",
                violations=[ConstraintViolation(
                    type="Immutability",
                    field=property_name,
                    constraint="immutable",
                    message="此属性不可修改",
                    severity="error"
                )],
                suggested_action="reject"
            )

        # 3. 检查更新权限
        updatable_by = getattr(prop_metadata, 'updatable_by', [])
        user_role = user_context.get('role', '')
        if updatable_by and user_role not in updatable_by:
            return Decision(
                allowed=False,
                reason=f"当前角色「{user_role}」无权修改属性「{property_name}」",
                violations=[ConstraintViolation(
                    type="Permission",
                    field=property_name,
                    constraint="role_based_update",
                    message=f"仅 {', '.join(updatable_by)} 角色可修改此属性",
                    severity="error"
                )],
                suggested_action="reject"
            )

        # 4. 格式验证
        format_regex = getattr(prop_metadata, 'format_regex', None)
        if format_regex and new_value:
            if not re.match(format_regex, str(new_value)):
                violations.append(ConstraintViolation(
                    type="FormatValidation",
                    field=property_name,
                    constraint="format_regex",
                    message=f"值「{new_value}」不符合格式要求",
                    severity="error"
                ))

        # 5. 运行属性级别的验证规则
        validation_rules = getattr(prop_metadata, 'update_validation_rules', [])
        for rule_func in validation_rules:
            try:
                is_valid, error_msg = rule_func(old_value, new_value, entity_id, db)
                if not is_valid:
                    violations.append(ConstraintViolation(
                        type="CustomValidation",
                        field=property_name,
                        constraint="custom_rule",
                        message=error_msg,
                        severity="error"
                    ))
            except Exception as e:
                violations.append(ConstraintViolation(
                    type="ValidationError",
                    field=property_name,
                    constraint="custom_rule",
                    message=f"验证规则执行错误: {str(e)}",
                    severity="error"
                ))

        # 6. 返回决策结果
        if violations:
            return Decision(
                allowed=False,
                reason=f"属性「{property_name}」更新验证失败",
                violations=violations,
                suggested_action="reject_with_correction",
                correction_prompt=self._generate_correction_prompt(violations, new_value)
            )

        return Decision(
            allowed=True,
            reason=f"属性「{property_name}」可以更新"
        )

    def _generate_correction_prompt(self, violations: List[ConstraintViolation], new_value: Any) -> str:
        """生成纠正提示"""
        prompts = []
        for v in violations:
            if v.type == "FormatValidation":
                if v.field == "phone":
                    prompts.append(f"「{new_value}」不是有效的手机号格式。请提供11位手机号，以1开头，第二位为3-9。")
                else:
                    prompts.append(f"「{new_value}」格式不正确。")
            elif v.type == "UniquenessValidation":
                prompts.append(f"「{new_value}」已被使用，请使用其他值。")
            else:
                prompts.append(v.message)
        return "；".join(prompts) if prompts else "请检查输入值。"


# Export
__all__ = [
    "ConstraintValidationResult",
    "ConstraintEngine",
    "ConstraintViolation",
    "Decision",
    "PhoneFormatValidator",
    "FieldUniquenessValidator",
]
