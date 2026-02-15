"""
测试 core.security.checker 模块 - 权限检查器单元测试
"""
import pytest

from core.security.context import SecurityContext, SecurityContextManager
from core.ontology.security import SecurityLevel
from core.security.checker import (
    Permission,
    PermissionRule,
    RolePermissionRule,
    OwnerPermissionRule,
    PermissionChecker,
    PermissionDenied,
    permission_checker,
)


def _register_hotel_permissions(rule: RolePermissionRule) -> None:
    """Register hotel permissions for testing (mirrors app/hotel/security)."""
    rule.register_role_permissions("manager", [Permission("*", "*")])
    rule.register_role_permissions("receptionist", [
        Permission("room", "read"),
        Permission("room", "update_status"),
        Permission("guest", "read"),
        Permission("guest", "write"),
        Permission("reservation", "read"),
        Permission("reservation", "write"),
        Permission("reservation", "create"),
        Permission("checkin", "*"),
        Permission("checkout", "read"),
        Permission("bill", "read"),
        Permission("task", "read"),
        Permission("task", "assign"),
    ])
    rule.register_role_permissions("cleaner", [
        Permission("room", "read"),
        Permission("task", "read"),
        Permission("task", "update"),
        Permission("task", "complete"),
    ])


class TestPermission:
    def test_creation(self):
        """测试创建权限"""
        perm = Permission(resource="room", action="read")
        assert perm.resource == "room"
        assert perm.action == "read"

    def test_str(self):
        """测试字符串表示"""
        perm = Permission(resource="room", action="read")
        assert str(perm) == "room:read"

    def test_from_string(self):
        """测试从字符串解析"""
        perm = Permission.from_string("room:read")
        assert perm.resource == "room"
        assert perm.action == "read"

    def test_from_string_invalid(self):
        """测试无效字符串"""
        with pytest.raises(ValueError):
            Permission.from_string("invalid")

    def test_from_string_with_spaces(self):
        """测试带空格的字符串"""
        perm = Permission.from_string(" room : read ")
        assert perm.resource == "room"
        assert perm.action == "read"

    def test_equality(self):
        """测试相等"""
        perm1 = Permission("room", "read")
        perm2 = Permission("room", "read")
        perm3 = Permission("room", "write")
        assert perm1 == perm2
        assert perm1 != perm3

    def test_hash(self):
        """测试哈希"""
        perm1 = Permission("room", "read")
        perm2 = Permission("room", "read")
        assert hash(perm1) == hash(perm2)

    def test_matches_exact(self):
        """测试完全匹配"""
        perm = Permission("room", "read")
        assert perm.matches(Permission("room", "read"))

    def test_matches_wildcard_resource(self):
        """测试资源通配符"""
        perm = Permission("*", "read")
        assert perm.matches(Permission("room", "read"))
        assert perm.matches(Permission("guest", "read"))

    def test_matches_wildcard_action(self):
        """测试操作通配符"""
        perm = Permission("room", "*")
        assert perm.matches(Permission("room", "read"))
        assert perm.matches(Permission("room", "write"))

    def test_matches_double_wildcard(self):
        """测试双重通配符"""
        perm = Permission("*", "*")
        assert perm.matches(Permission("room", "read"))
        assert perm.matches(Permission("guest", "write"))

    def test_matches_no_match(self):
        """测试不匹配"""
        perm = Permission("room", "read")
        assert not perm.matches(Permission("room", "write"))
        assert not perm.matches(Permission("guest", "read"))


class TestRolePermissionRule:
    def setup_method(self):
        """每个测试前清空上下文"""
        manager = SecurityContextManager()
        while manager.get_context():
            manager.clear_context()

    def test_check_manager_has_all(self):
        """测试管理员拥有所有权限"""
        rule = RolePermissionRule()
        _register_hotel_permissions(rule)
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        assert rule.check(ctx, Permission("any", "any"))

    def test_check_receptionist_permissions(self):
        """测试接待员权限"""
        rule = RolePermissionRule()
        _register_hotel_permissions(rule)
        ctx = SecurityContext(
            user_id=1,
            username="front",
            role="receptionist",
            security_level=SecurityLevel.INTERNAL,
        )
        assert rule.check(ctx, Permission("room", "read"))
        assert rule.check(ctx, Permission("guest", "write"))
        assert not rule.check(ctx, Permission("bill", "write"))

    def test_check_cleaner_permissions(self):
        """测试清洁工权限"""
        rule = RolePermissionRule()
        _register_hotel_permissions(rule)
        ctx = SecurityContext(
            user_id=1,
            username="cleaner",
            role="cleaner",
            security_level=SecurityLevel.PUBLIC,
        )
        assert rule.check(ctx, Permission("task", "read"))
        assert rule.check(ctx, Permission("task", "complete"))
        assert not rule.check(ctx, Permission("guest", "write"))

    def test_check_no_context(self):
        """测试无上下文"""
        rule = RolePermissionRule()
        assert not rule.check(None, Permission("room", "read"))

    def test_check_no_role(self):
        """测试无角色"""
        rule = RolePermissionRule()
        ctx = SecurityContext(
            user_id=1,
            username="user",
            role=None,
            security_level=SecurityLevel.PUBLIC,
        )
        assert not rule.check(ctx, Permission("room", "read"))

    def test_register_role_permissions(self):
        """测试注册角色权限"""
        rule = RolePermissionRule()
        new_perms = [Permission("test", "read"), Permission("test", "write")]
        rule.register_role_permissions("test_role", new_perms)

        ctx = SecurityContext(
            user_id=1,
            username="test",
            role="test_role",
            security_level=SecurityLevel.PUBLIC,
        )
        assert rule.check(ctx, Permission("test", "read"))
        assert rule.check(ctx, Permission("test", "write"))

    def test_get_role_permissions(self):
        """测试获取角色权限"""
        rule = RolePermissionRule()
        _register_hotel_permissions(rule)
        perms = rule.get_role_permissions("manager")
        assert Permission("*", "*") in perms


class TestOwnerPermissionRule:
    def test_check_no_context(self):
        """测试无上下文"""
        rule = OwnerPermissionRule()
        assert not rule.check(None, Permission("room", "read"), resource_id=1)

    def test_check_no_resource_id(self):
        """测试无资源ID"""
        rule = OwnerPermissionRule()
        ctx = SecurityContext(
            user_id=1,
            username="user",
            role="user",
            security_level=SecurityLevel.PUBLIC,
        )
        assert not rule.check(ctx, Permission("room", "read"), resource_id=None)

    def test_check_no_get_owner_func(self):
        """测试无获取函数"""
        rule = OwnerPermissionRule()
        ctx = SecurityContext(
            user_id=1,
            username="user",
            role="user",
            security_level=SecurityLevel.PUBLIC,
        )
        assert not rule.check(ctx, Permission("room", "read"), resource_id=1)

    def test_check_is_owner(self):
        """测试是所有者"""
        rule = OwnerPermissionRule(get_owner_func=lambda rid: 1 if rid == 100 else None)
        ctx = SecurityContext(
            user_id=1,
            username="user",
            role="user",
            security_level=SecurityLevel.PUBLIC,
        )
        assert rule.check(ctx, Permission("room", "read"), resource_id=100)
        assert not rule.check(ctx, Permission("room", "read"), resource_id=200)

    def test_set_get_owner_func(self):
        """测试设置获取函数"""
        rule = OwnerPermissionRule()
        rule.set_get_owner_func(lambda rid: 5)
        ctx = SecurityContext(
            user_id=5,
            username="user",
            role="user",
            security_level=SecurityLevel.PUBLIC,
        )
        assert rule.check(ctx, Permission("room", "read"), resource_id=1)


class TestPermissionChecker:
    def setup_method(self):
        """每个测试前重置检查器"""
        checker = PermissionChecker()
        checker.clear_cache()
        # Register hotel permissions on the singleton's role rule
        _register_hotel_permissions(checker._role_rule)
        # 清空上下文
        manager = SecurityContextManager()
        while manager.get_context():
            manager.clear_context()

    def test_singleton(self):
        """测试单例模式"""
        checker1 = PermissionChecker()
        checker2 = PermissionChecker()
        assert checker1 is checker2

    def test_check_permission_string(self):
        """测试字符串权限检查"""
        checker = PermissionChecker()
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        SecurityContextManager().set_context(ctx)
        assert checker.check_permission("room:read")

    def test_check_permission_invalid_string(self):
        """测试无效字符串"""
        checker = PermissionChecker()
        assert not checker.check_permission("invalid")

    def test_check_permission_no_context(self):
        """测试无上下文"""
        checker = PermissionChecker()
        assert not checker.check_permission("room:read")

    def test_check_permission_denied(self):
        """测试权限拒绝"""
        checker = PermissionChecker()
        ctx = SecurityContext(
            user_id=1,
            username="cleaner",
            role="cleaner",
            security_level=SecurityLevel.PUBLIC,
        )
        SecurityContextManager().set_context(ctx)
        assert not checker.check_permission("guest:write")

    def test_check_permission_with_resource_id(self):
        """测试带资源ID的检查"""
        checker = PermissionChecker()
        checker.set_get_owner_func(lambda rid: 1)

        ctx = SecurityContext(
            user_id=1,
            username="user",
            role="user",
            security_level=SecurityLevel.PUBLIC,
        )
        SecurityContextManager().set_context(ctx)

        # 所有者规则会生效
        assert checker.check_permission("room:write", resource_id=100)

    def test_require_permission_decorator(self):
        """测试权限装饰器"""
        checker = PermissionChecker()
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        SecurityContextManager().set_context(ctx)

        @checker.require_permission("room:read")
        def read_room():
            return "success"

        assert read_room() == "success"

    def test_require_permission_denied(self):
        """测试权限拒绝"""
        checker = PermissionChecker()
        ctx = SecurityContext(
            user_id=1,
            username="cleaner",
            role="cleaner",
            security_level=SecurityLevel.PUBLIC,
        )
        SecurityContextManager().set_context(ctx)

        @checker.require_permission("guest:write")
        def write_guest():
            return "success"

        with pytest.raises(PermissionDenied):
            write_guest()

    def test_require_permission_with_resource_id(self):
        """测试带资源ID的装饰器"""
        checker = PermissionChecker()
        checker.set_get_owner_func(lambda rid: 1)

        ctx = SecurityContext(
            user_id=1,
            username="user",
            role="user",
            security_level=SecurityLevel.PUBLIC,
        )
        SecurityContextManager().set_context(ctx)

        @checker.require_permission("room:write", resource_id_param="room_id")
        def write_room(room_id: int):
            return f"wrote {room_id}"

        assert write_room(room_id=100) == "wrote 100"

    def test_register_role_permissions(self):
        """测试注册角色权限"""
        checker = PermissionChecker()
        new_perms = [Permission("custom", "read")]
        checker.register_role_permissions("custom_role", new_perms)

        perms = checker.get_role_permissions("custom_role")
        assert Permission("custom", "read") in perms

    def test_clear_cache(self):
        """测试清空缓存"""
        checker = PermissionChecker()
        ctx = SecurityContext(
            user_id=1,
            username="admin",
            role="manager",
            security_level=SecurityLevel.RESTRICTED,
        )
        SecurityContextManager().set_context(ctx)

        # 首次检查
        checker.check_permission("room:read")

        # 清空缓存后再次检查
        checker.clear_cache()
        # 应该仍然可以工作
        assert checker.check_permission("room:read")


class TestPermissionDenied:
    def test_exception_message(self):
        """测试异常消息"""
        exc = PermissionDenied("test message")
        assert str(exc) == "test message"
        assert "test message" in exc.args[0]


class TestGlobalInstance:
    def test_global_checker_instance(self):
        """测试全局检查器实例"""
        from core.security.checker import permission_checker

        assert isinstance(permission_checker, PermissionChecker)

    def test_global_checker_singleton(self):
        """测试全局检查器是单例"""
        from core.security.checker import permission_checker

        checker = PermissionChecker()
        assert permission_checker is checker
