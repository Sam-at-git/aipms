"""
测试 core.ontology.link 对象链接抽象
"""
import pytest
from core.ontology.link import Link, LinkCollection
from core.ontology.base import BaseEntity


class MockEntity(BaseEntity):
    """测试用的模拟实体"""

    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name


def test_link_creation_empty():
    """测试创建空链接"""
    link = Link()
    assert link.get() is None
    assert not link.is_loaded()


def test_link_creation_with_target():
    """测试创建带目标的链接"""
    entity = MockEntity(id=1, name="Test")
    link = Link(entity)
    assert link.get() is entity
    assert link.is_loaded()


def test_link_set_and_get():
    """测试设置和获取链接目标"""
    link = Link()
    assert not link.is_loaded()

    entity = MockEntity(id=1, name="Test")
    link.set(entity)
    assert link.get() is entity
    assert link.is_loaded()


def test_link_clear():
    """测试清除链接"""
    entity = MockEntity(id=1, name="Test")
    link = Link(entity)
    assert link.is_loaded()

    link.clear()
    assert not link.is_loaded()
    assert link.get() is None


def test_link_repr_loaded():
    """测试已加载链接的字符串表示"""
    entity = MockEntity(id=5, name="Test")
    link = Link(entity)
    assert repr(link) == "Link(MockEntity(id=5))"


def test_link_repr_empty():
    """测试空链接的字符串表示"""
    link = Link()
    assert repr(link) == "Link(None)"


def test_link_collection_creation_empty():
    """测试创建空链接集合"""
    collection = LinkCollection()
    assert len(collection) == 0
    assert collection.all() == []


def test_link_collection_creation_with_items():
    """测试创建带项目的链接集合"""
    entity1 = MockEntity(id=1, name="A")
    entity2 = MockEntity(id=2, name="B")
    collection = LinkCollection([entity1, entity2])
    assert len(collection) == 2


def test_link_collection_add():
    """测试添加项目到集合"""
    collection = LinkCollection()
    entity = MockEntity(id=1, name="Test")

    collection.add(entity)
    assert len(collection) == 1
    assert entity in collection


def test_link_collection_add_duplicate():
    """测试添加重复项目不会重复添加"""
    collection = LinkCollection()
    entity = MockEntity(id=1, name="Test")

    collection.add(entity)
    collection.add(entity)
    assert len(collection) == 1


def test_link_collection_remove():
    """测试从集合中移除项目"""
    entity1 = MockEntity(id=1, name="A")
    entity2 = MockEntity(id=2, name="B")
    collection = LinkCollection([entity1, entity2])

    collection.remove(entity1)
    assert len(collection) == 1
    assert entity1 not in collection
    assert entity2 in collection


def test_link_collection_remove_not_exists():
    """测试移除不存在的项目抛出异常"""
    entity = MockEntity(id=1, name="Test")
    collection = LinkCollection()

    with pytest.raises(ValueError):
        collection.remove(entity)


def test_link_collection_clear():
    """测试清空集合"""
    entity1 = MockEntity(id=1, name="A")
    entity2 = MockEntity(id=2, name="B")
    collection = LinkCollection([entity1, entity2])

    collection.clear()
    assert len(collection) == 0


def test_link_collection_all():
    """测试获取所有项目"""
    entity1 = MockEntity(id=1, name="A")
    entity2 = MockEntity(id=2, name="B")
    collection = LinkCollection([entity1, entity2])

    items = collection.all()
    assert len(items) == 2
    assert entity1 in items
    assert entity2 in items


def test_link_collection_iteration():
    """测试迭代集合"""
    entity1 = MockEntity(id=1, name="A")
    entity2 = MockEntity(id=2, name="B")
    collection = LinkCollection([entity1, entity2])

    ids = [e.id for e in collection]
    assert ids == [1, 2]


def test_link_collection_contains():
    """测试 in 操作符"""
    entity1 = MockEntity(id=1, name="A")
    entity2 = MockEntity(id=2, name="B")
    collection = LinkCollection([entity1])

    assert entity1 in collection
    assert entity2 not in collection


def test_link_collection_repr():
    """测试链接集合的字符串表示"""
    entity1 = MockEntity(id=1, name="A")
    entity2 = MockEntity(id=2, name="B")
    collection = LinkCollection([entity1, entity2])

    assert repr(collection) == "LinkCollection(2 items)"
