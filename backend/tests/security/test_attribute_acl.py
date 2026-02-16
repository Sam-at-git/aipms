"""
测试 core.security.attribute_acl 模块 - 属性级访问控制单元测试
"""
import pytest

from core.security.context import SecurityContext, SecurityContextManager
from core.ontology.security import SecurityLevel
from core.security.attribute_acl import (
    AttributePermission,
    AttributeAccessDenied,
    AttributeACL,
    attribute_acl,
)


class TestAttributePermission:
    def test_creation(self):
        """测试创建属性权限"""
        perm = AttributePermission(
            entity_type="Guest",
            attribute="phone",
            security_level=SecurityLevel.CONFIDENTIAL,
        )
        assert perm.entity_type == "Guest"
        assert perm.attribute == "phone"
        assert perm.security_level == SecurityLevel.CONFIDENTIAL
        assert perm.allow_read is True
        assert perm.allow_write is False

    def test_repr(self):
        """测试字符串表示"""
        perm = AttributePermission(
            entity_type="Guest",
            attribute="phone",
            security_level=SecurityLevel.CONFIDENTIAL,
        )
        repr_str = repr(perm)
        assert "Guest" in repr_str
        assert "phone" in repr_str
        assert "CONFIDENTIAL" in repr_str


class TestAttributeAccessDenied:
    def test_exception(self):
        """测试异常"""
        exc = AttributeAccessDenied(
            "Cannot read phone",
            entity_type="Guest",
            attribute="phone",
            operation="read",
        )
        assert exc.entity_type == "Guest"
        assert exc.attribute == "phone"
        assert exc.operation == "read"
        assert "Cannot read phone" in str(exc)


class TestAttributeACL:
    def setup_method(self):
        """每个测试前重置 ACL 和上下文"""
        acl = AttributeACL()
        # 清空自定义规则并重新注册酒店域权限
        acl._rules.clear()
        acl.register_domain_permissions([
            AttributePermission("Guest", "phone", SecurityLevel.CONFIDENTIAL),
            AttributePermission("Guest", "id_card", SecurityLevel.RESTRICTED),
            AttributePermission("Guest", "blacklist_reason", SecurityLevel.RESTRICTED),
            AttributePermission("Guest", "tier", SecurityLevel.INTERNAL),
            AttributePermission("Room", "price", SecurityLevel.INTERNAL),
            AttributePermission("Employee", "salary", SecurityLevel.RESTRICTED, allow_write=False),
            AttributePermission("Employee", "password_hash", SecurityLevel.RESTRICTED, allow_read=False),
            AttributePermission("Bill", "total_amount", SecurityLevel.INTERNAL),
        ])

        manager = SecurityContextManager()
        while manager.get_context():
            manager.clear_context()

    def test_singleton(self):
        """测试单例模式"""
        acl1 = AttributeACL()
        acl2 = AttributeACL()
        assert acl1 is acl2

    def test_register_attribute(self):
        """测试注册属性权限"""
        acl = AttributeACL()
        perm = AttributePermission(
            entity_type="TestEntity",
            attribute="secret",
            security_level=SecurityLevel.RESTRICTED,
        )
        acl.register_attribute(perm)

        retrieved = acl.get_permission("TestEntity", "secret")
        assert retrieved is perm

    def test_has_rule(self):
        """测试检查是否有规则"""
        acl = AttributeACL()
        acl.register_attribute(
            AttributePermission("Test", "attr1", SecurityLevel.PUBLIC)
        )

        assert acl.has_rule("Test", "attr1")
        assert not acl.has_rule("Test", "attr2")
        assert not acl.has_rule("Other", "attr1")

    def test_can_read_no_rule(self):
        """测试无规则时默认允许"""
        acl = AttributeACL()
        assert acl.can_read("AnyEntity", "any_attribute")

    def test_can_read_allow_read_false(self):
        """测试 allow_read=False"""
        acl = AttributeACL()
        acl.register_attribute(
            AttributePermission(
                "Entity", "attr", SecurityLevel.PUBLIC, allow_read=False
            )
        )
        assert not acl.can_read("Entity", "attr")

    def test_can_read_security_level(self):
        """测试安全级别检查"""
        acl = AttributeACL()
        acl.register_attribute(
            AttributePermission(
                "Entity", "attr", SecurityLevel.CONFIDENTIAL, allow_read=True
            )
        )

        # 高级别上下文
        high_ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        SecurityContextManager().set_context(high_ctx)
        assert acl.can_read("Entity", "attr")

        # 低级别上下文
        low_ctx = SecurityContext(
            user_id=2,
            username="user",
            role="user",
            security_level=SecurityLevel.PUBLIC,
        )
        SecurityContextManager().set_context(low_ctx)
        assert not acl.can_read("Entity", "attr")

    def test_can_read_no_context(self):
        """测试无上下文"""
        acl = AttributeACL()
        acl.register_attribute(
            AttributePermission("Entity", "attr", SecurityLevel.PUBLIC)
        )
        # PUBLIC 级别在没有上下文时允许
        assert acl.can_read("Entity", "attr")

    def test_can_write_no_rule(self):
        """测试无规则时默认允许"""
        acl = AttributeACL()
        assert acl.can_write("AnyEntity", "any_attribute")

    def test_can_write_allow_write_false(self):
        """测试 allow_write=False"""
        acl = AttributeACL()
        acl.register_attribute(
            AttributePermission(
                "Entity", "attr", SecurityLevel.PUBLIC, allow_write=False
            )
        )
        assert not acl.can_write("Entity", "attr")

    def test_can_write_security_level(self):
        """测试写入安全级别检查"""
        acl = AttributeACL()
        acl.register_attribute(
            AttributePermission(
                "Entity", "attr", SecurityLevel.INTERNAL, allow_write=True
            )
        )

        # 足够级别
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.CONFIDENTIAL,
        )
        SecurityContextManager().set_context(ctx)
        assert acl.can_write("Entity", "attr")

        # 级别不足
        ctx_low = SecurityContext(
            user_id=2,
            username="user",
            role="user",
            security_level=SecurityLevel.PUBLIC,
        )
        SecurityContextManager().set_context(ctx_low)
        assert not acl.can_write("Entity", "attr")

    def test_filter_attributes(self):
        """测试过滤属性"""
        acl = AttributeACL()
        acl.register_attribute(
            AttributePermission("Entity", "secret", SecurityLevel.RESTRICTED)
        )
        acl.register_attribute(
            AttributePermission("Entity", "public", SecurityLevel.PUBLIC)
        )

        ctx = SecurityContext(
            user_id=1,
            username="user",
            role="user",
            security_level=SecurityLevel.PUBLIC,
        )
        SecurityContextManager().set_context(ctx)

        attrs = {"public": "value1", "secret": "value2", "other": "value3"}
        filtered = acl.filter_attributes("Entity", attrs, ctx)

        # secret 应该被过滤（级别不足）
        assert "public" in filtered
        assert "secret" not in filtered
        assert "other" in filtered  # 没有规则，默认包含

    def test_predefined_guest_attributes(self):
        """测试预定义的 Guest 属性"""
        acl = AttributeACL()

        # 检查规则存在
        assert acl.has_rule("Guest", "phone")
        assert acl.has_rule("Guest", "id_card")
        assert acl.has_rule("Guest", "blacklist_reason")

        # phone 需要 CONFIDENTIAL
        phone_perm = acl.get_permission("Guest", "phone")
        assert phone_perm.security_level == SecurityLevel.CONFIDENTIAL

        # id_card 需要 RESTRICTED
        id_card_perm = acl.get_permission("Guest", "id_card")
        assert id_card_perm.security_level == SecurityLevel.RESTRICTED

    def test_predefined_employee_attributes(self):
        """测试预定义的 Employee 属性"""
        acl = AttributeACL()

        # password_hash 不允许读取
        pwd_perm = acl.get_permission("Employee", "password_hash")
        assert pwd_perm.allow_read is False

        # salary 需要 RESTRICTED
        salary_perm = acl.get_permission("Employee", "salary")
        assert salary_perm.security_level == SecurityLevel.RESTRICTED

    def test_get_entity_attributes(self):
        """测试获取实体所有受控属性"""
        acl = AttributeACL()
        acl.register_attribute(
            AttributePermission("Test", "attr1", SecurityLevel.PUBLIC)
        )
        acl.register_attribute(
            AttributePermission("Test", "attr2", SecurityLevel.PUBLIC)
        )

        attrs = acl.get_entity_attributes("Test")
        assert set(attrs) == {"attr1", "attr2"}


class TestGlobalInstance:
    def test_global_acl_instance(self):
        """测试全局 ACL 实例"""
        from core.security.attribute_acl import attribute_acl

        assert isinstance(attribute_acl, AttributeACL)

    def test_global_acl_singleton(self):
        """测试全局 ACL 是单例"""
        from core.security.attribute_acl import attribute_acl

        acl = AttributeACL()
        assert attribute_acl is acl
