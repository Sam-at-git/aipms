"""
测试 core.security.context 模块 - 安全上下文单元测试
"""
import pytest
import threading
import time

from core.ontology.security import SecurityLevel
from core.security.context import (
    SecurityContext,
    SecurityContextManager,
    security_context_manager,
)


class TestSecurityContext:
    def test_creation(self):
        """测试创建安全上下文"""
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        assert ctx.user_id == 1
        assert ctx.username == "admin"
        assert ctx.role == "manager"
        assert ctx.security_level == SecurityLevel.RESTRICTED
        assert ctx.is_active is True

    def test_is_admin(self):
        """测试管理员检查"""
        admin_ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        assert admin_ctx.is_admin()

        user_ctx = SecurityContext(
            user_id=2,
            username="user",
            role="receptionist",
            security_level=SecurityLevel.INTERNAL,
        )
        assert not user_ctx.is_admin()

    def test_set_admin_roles(self):
        """测试可配置的管理员角色"""
        original = SecurityContext._admin_roles.copy()
        try:
            SecurityContext.set_admin_roles({"sysadmin", "manager"})

            sysadmin_ctx = SecurityContext(
                user_id=1, username="sysadmin", role="sysadmin",
                security_level=SecurityLevel.RESTRICTED,
            )
            assert sysadmin_ctx.is_admin()

            manager_ctx = SecurityContext(
                user_id=2, username="mgr", role="manager",
                security_level=SecurityLevel.RESTRICTED,
            )
            assert manager_ctx.is_admin()

            receptionist_ctx = SecurityContext(
                user_id=3, username="front", role="receptionist",
                security_level=SecurityLevel.INTERNAL,
            )
            assert not receptionist_ctx.is_admin()
        finally:
            SecurityContext._admin_roles = original

    def test_has_role(self):
        """测试角色检查"""
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        assert ctx.has_role("manager")
        assert not ctx.has_role("receptionist")

    def test_has_clearance(self):
        """测试安全级别检查"""
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        assert ctx.has_clearance(SecurityLevel.PUBLIC)
        assert ctx.has_clearance(SecurityLevel.INTERNAL)
        assert ctx.has_clearance(SecurityLevel.CONFIDENTIAL)
        assert ctx.has_clearance(SecurityLevel.RESTRICTED)

        low_ctx = SecurityContext(
            user_id=2,
            username="user",
            role="cleaner",
            security_level=SecurityLevel.PUBLIC,
        )
        assert low_ctx.has_clearance(SecurityLevel.PUBLIC)
        assert not low_ctx.has_clearance(SecurityLevel.INTERNAL)

    def test_to_dict(self):
        """测试转换为字典"""
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
            ip_address="127.0.0.1",
        )
        d = ctx.to_dict()
        assert d["user_id"] == 1
        assert d["username"] == "admin"
        assert d["role"] == "manager"
        assert d["security_level"] == 4  # RESTRICTED
        assert d["ip_address"] == "127.0.0.1"

    def test_repr(self):
        """测试字符串表示"""
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        repr_str = repr(ctx)
        assert "user_id=1" in repr_str
        assert "username='admin'" in repr_str
        assert "role='manager'" in repr_str


class TestSecurityContextManager:
    def setup_method(self):
        """每个测试前清空上下文"""
        manager = SecurityContextManager()
        # 清空所有上下文
        while manager.get_context():
            manager.clear_context()

    def test_singleton(self):
        """测试单例模式"""
        manager1 = SecurityContextManager()
        manager2 = SecurityContextManager()
        assert manager1 is manager2

    def test_set_and_get_context(self):
        """测试设置和获取上下文"""
        manager = SecurityContextManager()
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        manager.set_context(ctx)

        retrieved = manager.get_context()
        assert retrieved is ctx
        assert retrieved.user_id == 1

    def test_clear_context(self):
        """测试清除上下文"""
        manager = SecurityContextManager()
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        manager.set_context(ctx)
        assert manager.get_context() is not None

        manager.clear_context()
        assert manager.get_context() is None

    def test_get_user_id(self):
        """测试获取用户ID"""
        manager = SecurityContextManager()
        assert manager.get_user_id() is None

        ctx = SecurityContext(
            user_id=123,
            username="user",
            role="receptionist",
            security_level=SecurityLevel.INTERNAL,
        )
        manager.set_context(ctx)
        assert manager.get_user_id() == 123

    def test_get_username(self):
        """测试获取用户名"""
        manager = SecurityContextManager()
        assert manager.get_username() is None

        ctx = SecurityContext(
            user_id=1,
            username="testuser",
            role="receptionist",
            security_level=SecurityLevel.INTERNAL,
        )
        manager.set_context(ctx)
        assert manager.get_username() == "testuser"

    def test_get_role(self):
        """测试获取角色"""
        manager = SecurityContextManager()
        assert manager.get_role() is None

        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        manager.set_context(ctx)
        assert manager.get_role() == "manager"

    def test_get_security_level(self):
        """测试获取安全级别"""
        manager = SecurityContextManager()
        assert manager.get_security_level() == SecurityLevel.PUBLIC

        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        manager.set_context(ctx)
        assert manager.get_security_level() == SecurityLevel.RESTRICTED

    def test_is_authenticated(self):
        """测试认证状态"""
        manager = SecurityContextManager()
        assert not manager.is_authenticated()

        ctx = SecurityContext(
            user_id=1,
            username="user",
            role="receptionist",
            security_level=SecurityLevel.INTERNAL,
        )
        manager.set_context(ctx)
        assert manager.is_authenticated()

    def test_has_permission_admin(self):
        """测试管理员拥有所有权限"""
        manager = SecurityContextManager()
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        manager.set_context(ctx)
        assert manager.has_permission("any.permission")

    def test_has_permission_no_context(self):
        """测试无上下文时无权限"""
        manager = SecurityContextManager()
        assert not manager.has_permission("any.permission")

    def test_context_nesting(self):
        """测试上下文嵌套"""
        manager = SecurityContextManager()
        user_ctx = SecurityContext(
            user_id=1,
            username="user",
            role="receptionist",
            security_level=SecurityLevel.INTERNAL,
        )
        admin_ctx = SecurityContext(
            user_id=2,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )

        manager.set_context(user_ctx)
        assert manager.get_context() is user_ctx
        assert manager.get_context().parent_context is None

        manager.set_context(admin_ctx)
        assert manager.get_context() is admin_ctx
        assert manager.get_context().parent_context is user_ctx

        manager.clear_context()
        assert manager.get_context() is user_ctx
        assert manager.get_context().parent_context is None

    def test_enter_context_with_statement(self):
        """测试 with 语句支持"""
        manager = SecurityContextManager()
        user_ctx = SecurityContext(
            user_id=1,
            username="user",
            role="receptionist",
            security_level=SecurityLevel.INTERNAL,
        )
        admin_ctx = SecurityContext(
            user_id=2,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )

        manager.set_context(user_ctx)
        assert manager.get_username() == "user"

        with manager.enter_context(admin_ctx):
            assert manager.get_username() == "admin"

        # 恢复原上下文
        assert manager.get_username() == "user"


class TestThreadSafety:
    def test_thread_local_context(self):
        """测试线程隔离的上下文"""
        manager = SecurityContextManager()
        results = {}

        def thread_func(user_id, username):
            ctx = SecurityContext(
                user_id=user_id,
                username=username,
                role="receptionist",
                security_level=SecurityLevel.INTERNAL,
            )
            manager.set_context(ctx)
            time.sleep(0.01)  # 让其他线程也有机会设置
            results[user_id] = manager.get_user_id()

        threads = [
            threading.Thread(target=thread_func, args=(1, "user1")),
            threading.Thread(target=thread_func, args=(2, "user2")),
            threading.Thread(target=thread_func, args=(3, "user3")),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 每个线程应该看到自己的 user_id
        assert results[1] == 1
        assert results[2] == 2
        assert results[3] == 3


class TestGlobalInstance:
    def test_global_manager_instance(self):
        """测试全局管理器实例"""
        from core.security.context import security_context_manager

        assert isinstance(security_context_manager, SecurityContextManager)

    def test_global_manager_singleton(self):
        """测试全局管理器是单例"""
        from core.security.context import security_context_manager

        manager = SecurityContextManager()
        assert security_context_manager is manager
