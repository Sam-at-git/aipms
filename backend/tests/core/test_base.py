"""
测试 BaseEntity 基类功能
"""
import pytest
from core.ontology.base import BaseEntity


class MockEntity(BaseEntity):
    """测试用的模拟实体"""

    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name


def test_get_entity_name():
    """测试获取实体名称"""
    assert MockEntity.get_entity_name() == "MockEntity"


def test_to_dict():
    """测试字典转换"""
    entity = MockEntity(id=1, name="Test")
    result = entity.to_dict()
    assert result == {"id": 1, "name": "Test"}


def test_to_dict_filters_internal():
    """测试字典转换过滤内部属性"""
    entity = MockEntity(id=1, name="Test")
    entity._internal = "secret"  # pylint: disable=attribute-defined-outside-init
    result = entity.to_dict()
    assert "_internal" not in result
    assert result == {"id": 1, "name": "Test"}


def test_repr():
    """测试字符串表示"""
    entity = MockEntity(id=5, name="Test")
    assert repr(entity) == "MockEntity(id=5)"


def test_repr_without_id():
    """测试没有 id 属性的字符串表示"""
    class EntityWithoutId(BaseEntity):
        def __init__(self, name: str):
            self.name = name

    entity = EntityWithoutId(name="Test")
    assert repr(entity) == "EntityWithoutId(id=?)"


def test_get_metadata_none():
    """测试未注册元数据时返回 None"""
    assert MockEntity.get_metadata() is None


def test_get_state_machine_none():
    """测试未定义状态机时返回 None"""
    assert MockEntity.get_state_machine() is None
