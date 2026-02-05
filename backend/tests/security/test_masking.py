"""
测试 core.security.masking 模块 - 敏感数据脱敏单元测试
"""
import pytest

from core.security.context import SecurityContext, SecurityContextManager
from core.ontology.security import SecurityLevel
from core.security.masking import (
    MaskingStrategy,
    MaskingRule,
    DataMasker,
    data_masker,
)


class TestMaskingStrategy:
    def test_enum_values(self):
        """测试枚举值"""
        assert MaskingStrategy.FULL.value == "full"
        assert MaskingStrategy.PARTIAL.value == "partial"
        assert MaskingStrategy.EMAIL.value == "email"
        assert MaskingStrategy.NAME.value == "name"
        assert MaskingStrategy.CUSTOM.value == "custom"


class TestMaskingRule:
    def test_creation(self):
        """测试创建脱敏规则"""
        rule = MaskingRule(
            field_name="phone",
            data_type="phone",
            strategy=MaskingStrategy.PARTIAL,
            security_level=SecurityLevel.CONFIDENTIAL,
        )
        assert rule.field_name == "phone"
        assert rule.data_type == "phone"
        assert rule.strategy == MaskingStrategy.PARTIAL
        assert rule.security_level == SecurityLevel.CONFIDENTIAL
        assert rule.preserve_chars == 0


class TestDataMasker:
    def setup_method(self):
        """每个测试前重置上下文"""
        manager = SecurityContextManager()
        while manager.get_context():
            manager.clear_context()

    def test_singleton(self):
        """测试单例模式"""
        masker1 = DataMasker()
        masker2 = DataMasker()
        assert masker1 is masker2

    def test_register_rule(self):
        """测试注册规则"""
        masker = DataMasker()
        rule = MaskingRule(
            field_name="custom_field",
            data_type="custom",
            strategy=MaskingStrategy.FULL,
            security_level=SecurityLevel.RESTRICTED,
        )
        masker.register_rule(rule)

        retrieved = masker.get_rule("custom_field")
        assert retrieved is rule

    def test_mask_no_rule(self):
        """测试无规则时不脱敏"""
        masker = DataMasker()
        result = masker.mask("unknown_field", "some_value")
        assert result == "some_value"

    def test_mask_none_value(self):
        """测试 None 值不脱敏"""
        masker = DataMasker()
        result = masker.mask("phone", None)
        assert result is None

    def test_mask_non_string(self):
        """测试非字符串不脱敏"""
        masker = DataMasker()
        result = masker.mask("phone", 12345)
        assert result == 12345

    def test_mask_full_strategy(self):
        """测试完全脱敏"""
        masker = DataMasker()
        masker.register_rule(
            MaskingRule(
                field_name="secret",
                data_type="text",
                strategy=MaskingStrategy.FULL,
                security_level=SecurityLevel.RESTRICTED,  # 需要 RESTRICTED 级别
            )
        )
        # 无上下文时，PUBLIC 以上的级别会被脱敏
        result = masker.mask("secret", "sensitive_data")
        assert result == "*" * len("sensitive_data")

    def test_mask_partial_strategy(self):
        """测试部分脱敏"""
        masker = DataMasker()
        masker.register_rule(
            MaskingRule(
                field_name="phone",
                data_type="phone",
                strategy=MaskingStrategy.PARTIAL,
                security_level=SecurityLevel.CONFIDENTIAL,  # 需要 CONFIDENTIAL 级别
                preserve_chars=3,
            )
        )
        # 无上下文时，PUBLIC 以上的级别会被脱敏
        result = masker.mask("phone", "13800138000")
        assert result == "138********"  # 保留前3位，其余用星号代替

    def test_mask_email_strategy(self):
        """测试邮箱脱敏"""
        masker = DataMasker()
        masker.register_rule(
            MaskingRule(
                field_name="email",
                data_type="email",
                strategy=MaskingStrategy.EMAIL,
                security_level=SecurityLevel.INTERNAL,  # 需要 INTERNAL 级别
            )
        )
        # 无上下文时，PUBLIC 以上的级别会被脱敏
        result = masker.mask("email", "alice@example.com")
        assert result == "a****@example.com"  # alice -> a****

    def test_mask_name_strategy(self):
        """测试姓名脱敏"""
        masker = DataMasker()
        masker.register_rule(
            MaskingRule(
                field_name="name",
                data_type="name",
                strategy=MaskingStrategy.NAME,
                security_level=SecurityLevel.INTERNAL,  # 需要 INTERNAL 级别
            )
        )
        # 无上下文时，PUBLIC 以上的级别会被脱敏
        result = masker.mask("name", "张三")
        assert result == "张*"

    def test_mask_with_sufficient_clearance(self):
        """测试有足够权限时不脱敏"""
        masker = DataMasker()
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        SecurityContextManager().set_context(ctx)

        result = masker.mask("phone", "13800138000", ctx)
        assert result == "13800138000"  # 不脱敏

    def test_mask_with_insufficient_clearance(self):
        """测试权限不足时脱敏"""
        masker = DataMasker()
        ctx = SecurityContext(
            user_id=1,
            username="user",
            role="user",
            security_level=SecurityLevel.PUBLIC,
        )
        SecurityContextManager().set_context(ctx)

        result = masker.mask("phone", "13800138000", ctx)
        # 应该被脱敏（phone 需要 CONFIDENTIAL）
        assert "*" in result
        assert result != "13800138000"

    def test_mask_dict(self):
        """测试字典脱敏"""
        masker = DataMasker()
        ctx = SecurityContext(
            user_id=1,
            username="user",
            role="user",
            security_level=SecurityLevel.PUBLIC,
        )
        SecurityContextManager().set_context(ctx)

        data = {
            "name": "张三",
            "phone": "13800138000",
            "email": "test@example.com",
            "normal_field": "public_value",
        }
        result = masker.mask_dict(data, ctx)

        # phone 和 email 应该被脱敏
        assert "*" in result["phone"]
        assert "*" in result["email"]
        # normal_field 不应该被脱敏
        assert result["normal_field"] == "public_value"

    def test_predefined_phone_rule(self):
        """测试预定义的电话号码规则"""
        masker = data_masker
        rule = masker.get_rule("phone")
        assert rule is not None
        assert rule.data_type == "phone"
        assert rule.strategy == MaskingStrategy.PARTIAL
        assert rule.preserve_chars == 3

    def test_predefined_id_card_rule(self):
        """测试预定义的身份证规则"""
        masker = data_masker
        rule = masker.get_rule("id_card")
        assert rule is not None
        assert rule.data_type == "id_card"
        assert rule.strategy == MaskingStrategy.PARTIAL

    def test_predefined_email_rule(self):
        """测试预定义的邮箱规则"""
        masker = data_masker
        rule = masker.get_rule("email")
        assert rule is not None
        assert rule.data_type == "email"
        assert rule.strategy == MaskingStrategy.EMAIL


class TestGlobalInstance:
    def test_global_masker_instance(self):
        """测试全局脱敏器实例"""
        from core.security.masking import data_masker

        assert isinstance(data_masker, DataMasker)

    def test_global_masker_singleton(self):
        """测试全局脱敏器是单例"""
        from core.security.masking import data_masker

        masker = DataMasker()
        assert data_masker is masker
