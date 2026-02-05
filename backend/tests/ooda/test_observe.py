"""
测试 core.ooda.observe 模块 - Observe 阶段单元测试
"""
import pytest
from datetime import datetime

from core.ooda.observe import (
    Observation,
    ValidationResult,
    InputValidator,
    CompositeValidator,
    InputNormalizer,
    PipelineNormalizer,
    NotEmptyValidator,
    MinLengthValidator,
    MaxLengthValidator,
    PatternValidator,
    TrimNormalizer,
    LowercaseNormalizer,
    UppercaseNormalizer,
    CollapseWhitespaceNormalizer,
    ObservePhase,
    observe_phase,
)


# ============== ValidationResult Tests ==============
class TestValidationResult:
    def test_valid_result(self):
        """测试有效结果"""
        result = ValidationResult(True)
        assert result.is_valid is True
        assert result.errors == []

    def test_invalid_result(self):
        """测试无效结果"""
        result = ValidationResult(False, ["Error 1", "Error 2"])
        assert result.is_valid is False
        assert len(result.errors) == 2

    def test_add_error(self):
        """测试添加错误"""
        result = ValidationResult(True)
        result.add_error("New error")
        assert result.is_valid is False
        assert "New error" in result.errors


# ============== InputValidator Tests ==============
class TestNotEmptyValidator:
    def test_valid_input(self):
        """测试有效输入"""
        validator = NotEmptyValidator()
        result = validator.validate("Hello")
        assert result.is_valid

    def test_empty_string(self):
        """测试空字符串"""
        validator = NotEmptyValidator()
        result = validator.validate("")
        assert not result.is_valid
        assert "cannot be empty" in result.errors[0].lower()

    def test_whitespace_only(self):
        """测试仅空白字符"""
        validator = NotEmptyValidator()
        result = validator.validate("   ")
        assert not result.is_valid


class TestMinLengthValidator:
    def test_valid_input(self):
        """测试有效输入"""
        validator = MinLengthValidator(5)
        assert validator.validate("Hello").is_valid
        assert not validator.validate("Hi").is_valid

    def test_exact_length(self):
        """测试精确长度"""
        validator = MinLengthValidator(3)
        assert validator.validate("ABC").is_valid


class TestMaxLengthValidator:
    def test_valid_input(self):
        """测试有效输入"""
        validator = MaxLengthValidator(5)
        assert validator.validate("Hello").is_valid
        assert not validator.validate("Hello World").is_valid


class TestPatternValidator:
    def test_valid_pattern(self):
        """测试匹配模式"""
        validator = PatternValidator(r"^\d+$", "Input must be digits only")
        assert validator.validate("12345").is_valid

    def test_invalid_pattern(self):
        """测试不匹配模式"""
        validator = PatternValidator(r"^\d+$", "Input must be digits only")
        result = validator.validate("abc")
        assert not result.is_valid
        assert "digits only" in result.errors[0]


# ============== InputNormalizer Tests ==============
class TestTrimNormalizer:
    def test_trim_whitespace(self):
        """测试去除空白"""
        normalizer = TrimNormalizer()
        assert normalizer.normalize("  Hello  ") == "Hello"


class TestLowercaseNormalizer:
    def test_convert_to_lowercase(self):
        """测试转小写"""
        normalizer = LowercaseNormalizer()
        assert normalizer.normalize("HELLO World") == "hello world"


class TestUppercaseNormalizer:
    def test_convert_to_uppercase(self):
        """测试转大写"""
        normalizer = UppercaseNormalizer()
        assert normalizer.normalize("hello World") == "HELLO WORLD"


class TestCollapseWhitespaceNormalizer:
    def test_collapse_spaces(self):
        """测试合并空白"""
        normalizer = CollapseWhitespaceNormalizer()
        assert normalizer.normalize("Hello    World") == "Hello World"


class TestRemoveSpecialCharsNormalizer:
    def test_keep_alphanumeric(self):
        """测试保留字母数字"""
        from core.ooda.observe import RemoveSpecialCharsNormalizer

        normalizer = RemoveSpecialCharsNormalizer()
        result = normalizer.normalize("Hello@World!123")
        assert result == "HelloWorld123"


class TestCompositeValidator:
    def test_multiple_validators(self):
        """测试组合验证器"""
        validator = NotEmptyValidator() & MinLengthValidator(3)
        assert validator.validate("Hello").is_valid
        assert not validator.validate("").is_valid
        assert not validator.validate("Hi").is_valid


class TestPipelineNormalizer:
    def test_multiple_normalizers(self):
        """测试管道规范化器"""
        normalizer = TrimNormalizer() & LowercaseNormalizer()
        result = normalizer.normalize("  HELLO WORLD  ")
        assert result == "hello world"


# ============== Observation Tests ==============
class TestObservation:
    def test_creation(self):
        """测试创建观察结果"""
        obs = Observation(
            raw_input="test",
            normalized_input="test",
        )
        assert obs.raw_input == "test"
        assert obs.normalized_input == "test"
        assert obs.is_valid is True
        assert obs.confidence == 1.0

    def test_to_dict(self):
        """测试转换为字典"""
        obs = Observation(
            raw_input="test",
            normalized_input="test",
            extracted_entities=["entity1"],
            confidence=0.85,
        )
        d = obs.to_dict()
        assert d["raw_input"] == "test"
        assert d["normalized_input"] == "test"
        assert d["extracted_entities"] == ["entity1"]
        assert d["confidence"] == 0.85


# ============== ObservePhase Tests ==============
class TestObservePhase:
    def test_observe_basic(self):
        """测试基本观察"""
        observe = ObservePhase()
        obs = observe.observe("Hello World")
        assert obs.normalized_input == "Hello World"
        assert obs.is_valid is True

    def test_observe_with_whitespace(self):
        """测试处理空白"""
        observe = ObservePhase()
        obs = observe.observe("  Hello    World  ")
        # 默认规范化会去除空白并合并
        assert obs.normalized_input == "Hello World"

    def test_observe_empty_input(self):
        """测试空输入"""
        observe = ObservePhase()
        obs = observe.observe("")
        assert not obs.is_valid
        assert "cannot be empty" in obs.validation_errors[0].lower()

    def test_add_custom_validator(self):
        """测试添加自定义验证器"""
        observe = ObservePhase()
        observe.clear_validators()
        observe.add_validator(MinLengthValidator(10))

        obs = observe.observe("short")
        assert not obs.is_valid

    def test_add_custom_normalizer(self):
        """测试添加自定义规范化器"""
        observe = ObservePhase()
        observe.clear_normalizers()
        observe.add_normalizer(UppercaseNormalizer())

        obs = observe.observe("hello")
        assert obs.normalized_input == "HELLO"

    def test_clear_validators(self):
        """测试清空验证器"""
        observe = ObservePhase()
        observe.clear_validators()

        # 没有验证器，空输入应该有效
        obs = observe.observe("")
        assert obs.is_valid

    def test_clear_normalizers(self):
        """测试清空规范化器"""
        observe = ObservePhase()
        observe.clear_normalizers()

        obs = observe.observe("  Hello  ")
        # 不会规范化
        assert obs.normalized_input == "  Hello  "

    def test_with_context(self):
        """测试带上下文的观察"""
        observe = ObservePhase()
        obs = observe.observe("test", context={"user_id": 123})

        assert obs.metadata["user_id"] == 123

    def test_timestamp(self):
        """测试时间戳"""
        before = datetime.utcnow()
        observe = ObservePhase()
        obs = observe.observe("test")
        after = datetime.utcnow()

        assert before <= obs.timestamp <= after


class TestGlobalInstance:
    def test_global_observe_phase_instance(self):
        """测试全局观察阶段实例"""
        from core.ooda.observe import observe_phase

        assert isinstance(observe_phase, ObservePhase)

    def test_global_observe_phase_singleton(self):
        """测试全局观察阶段是单例"""
        from core.ooda.observe import observe_phase

        observe = ObservePhase()
        assert observe_phase is observe
