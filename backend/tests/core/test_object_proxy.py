"""
测试 ObjectProxy 对象代理功能
"""
import pytest
from core.ontology.base import BaseEntity, ObjectProxy


class TestEntity(BaseEntity):
    """测试用的模拟实体"""

    def __init__(self, id: int, name: str):
        self.id = id
        self.name = name
        self._secret = "hidden"


def test_proxy_get_attribute():
    """测试代理读取属性"""
    entity = TestEntity(id=1, name="Test")
    proxy = ObjectProxy(entity, context=None)
    assert proxy.id == 1
    assert proxy.name == "Test"


def test_proxy_set_attribute():
    """测试代理写入属性"""
    entity = TestEntity(id=1, name="Test")
    proxy = ObjectProxy(entity, context=None)
    proxy.name = "Modified"
    assert entity.name == "Modified"
    assert proxy.name == "Modified"


def test_proxy_set_creates_new_attribute():
    """测试代理创建新属性"""
    entity = TestEntity(id=1, name="Test")
    proxy = ObjectProxy(entity, context=None)
    proxy.new_attr = "new_value"
    assert entity.new_attr == "new_value"
    assert proxy.new_attr == "new_value"


def test_proxy_attribute_error():
    """测试不存在的属性抛出 AttributeError"""
    entity = TestEntity(id=1, name="Test")
    proxy = ObjectProxy(entity, context=None)
    with pytest.raises(AttributeError, match="has no attribute 'nonexistent'"):
        _ = proxy.nonexistent


def test_proxy_repr():
    """测试字符串表示"""
    entity = TestEntity(id=1, name="Test")
    proxy = ObjectProxy(entity, context=None)
    assert repr(proxy) == "Proxy(TestEntity(id=1))"


def test_proxy_repr_without_id():
    """测试没有 id 属性的字符串表示"""
    class EntityWithoutId(BaseEntity):
        def __init__(self, name: str):
            self.name = name

    entity = EntityWithoutId(name="Test")
    proxy = ObjectProxy(entity, context=None)
    assert repr(proxy) == "Proxy(EntityWithoutId(id=?))"


def test_proxy_unwrap():
    """测试解包获取原始对象"""
    entity = TestEntity(id=1, name="Test")
    proxy = ObjectProxy(entity, context=None)
    assert proxy.unwrap() is entity
    assert proxy.unwrap().id == 1


def test_proxy_get_context_none():
    """测试获取 None 安全上下文"""
    entity = TestEntity(id=1, name="Test")
    proxy = ObjectProxy(entity, context=None)
    assert proxy.get_context() is None


def test_proxy_get_context():
    """测试获取安全上下文"""
    entity = TestEntity(id=1, name="Test")
    mock_context = object()  # 使用任意对象作为模拟上下文
    proxy = ObjectProxy(entity, context=mock_context)
    assert proxy.get_context() is mock_context


def test_proxy_dir():
    """测试 dir() 支持"""
    entity = TestEntity(id=1, name="Test")
    proxy = ObjectProxy(entity, context=None)
    attrs = dir(proxy)
    # dir() 返回实体的属性列表
    assert "id" in attrs
    assert "name" in attrs
    # proxy 方法不在 dir() 中，因为 __dir__ 返回 dir(entity)
    # 但可以直接调用
    assert hasattr(proxy, "unwrap")
    assert hasattr(proxy, "get_context")


def test_proxy_internal_attribute_access():
    """测试内部属性直接访问（不触发拦截）"""
    entity = TestEntity(id=1, name="Test")
    proxy = ObjectProxy(entity, context=None)

    # 访问 _secret 内部属性
    assert proxy._secret == "hidden"

    # 设置新的内部属性
    proxy._new_internal = "value"
    assert proxy._new_internal == "value"


def test_proxy_preserves_entity_state():
    """测试代理保持实体状态一致性"""
    entity = TestEntity(id=1, name="Original")
    proxy = ObjectProxy(entity, context=None)

    # 通过代理修改
    proxy.name = "Modified"
    proxy.id = 99

    # 实体也被修改
    assert entity.name == "Modified"
    assert entity.id == 99

    # 直接修改实体
    entity.name = "Direct"
    assert proxy.name == "Direct"


def test_proxy_with_none_context():
    """测试不传 context 参数时的行为"""
    entity = TestEntity(id=1, name="Test")
    proxy = ObjectProxy(entity)
    assert proxy.get_context() is None
    assert proxy.id == 1
    proxy.name = "Modified"
    assert entity.name == "Modified"


def test_proxy_multiple_proxies_same_entity():
    """测试多个代理指向同一实体"""
    entity = TestEntity(id=1, name="Test")
    proxy1 = ObjectProxy(entity)
    proxy2 = ObjectProxy(entity)

    proxy1.name = "ViaProxy1"
    assert proxy2.name == "ViaProxy1"  # 两个代理指向同一实体，值应该一致
    assert entity.name == "ViaProxy1"
