"""
测试 core.ontology.security 安全等级定义
"""
import pytest
from core.ontology.security import SecurityLevel


def test_security_level_values():
    """测试安全等级枚举值"""
    assert SecurityLevel.PUBLIC == 1
    assert SecurityLevel.INTERNAL == 2
    assert SecurityLevel.CONFIDENTIAL == 3
    assert SecurityLevel.RESTRICTED == 4


def test_security_level_comparison():
    """测试安全等级比较"""
    assert SecurityLevel.PUBLIC < SecurityLevel.INTERNAL
    assert SecurityLevel.INTERNAL < SecurityLevel.CONFIDENTIAL
    assert SecurityLevel.CONFIDENTIAL < SecurityLevel.RESTRICTED


def test_security_level_str():
    """测试安全等级字符串表示"""
    assert str(SecurityLevel.PUBLIC) == "PUBLIC"
    assert str(SecurityLevel.INTERNAL) == "INTERNAL"
    assert str(SecurityLevel.CONFIDENTIAL) == "CONFIDENTIAL"
    assert str(SecurityLevel.RESTRICTED) == "RESTRICTED"


def test_from_string_valid():
    """测试从字符串创建有效的安全等级"""
    assert SecurityLevel.from_string("PUBLIC") == SecurityLevel.PUBLIC
    assert SecurityLevel.from_string("INTERNAL") == SecurityLevel.INTERNAL
    assert SecurityLevel.from_string("CONFIDENTIAL") == SecurityLevel.CONFIDENTIAL
    assert SecurityLevel.from_string("RESTRICTED") == SecurityLevel.RESTRICTED


def test_from_string_case_insensitive():
    """测试 from_string 大小写不敏感"""
    assert SecurityLevel.from_string("public") == SecurityLevel.PUBLIC
    assert SecurityLevel.from_string("Public") == SecurityLevel.PUBLIC
    assert SecurityLevel.from_string("PUBLIC") == SecurityLevel.PUBLIC


def test_from_string_invalid():
    """测试从无效字符串创建安全等级抛出异常"""
    with pytest.raises(ValueError, match="Invalid security level"):
        SecurityLevel.from_string("INVALID")


def test_security_level_name():
    """测试安全等级名称"""
    assert SecurityLevel.PUBLIC.name == "PUBLIC"
    assert SecurityLevel.INTERNAL.name == "INTERNAL"
