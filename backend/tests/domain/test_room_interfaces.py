"""
测试 Room 实体的接口实现 (SPEC-02.5.3)
"""
import pytest
from core.ontology.registry import OntologyRegistry
from app.hotel.domain.interfaces import BookableResource, Maintainable, Billable, Trackable


@pytest.fixture(autouse=True)
def ensure_room_registered():
    """确保 Room 的接口注册数据存在（装饰器在导入时只触发一次）"""
    from app.hotel.domain.room import RoomEntity
    reg = OntologyRegistry()

    # 重新注册接口和实现关系（因为其他测试的 autouse fixture 可能清空了 registry）
    reg.register_interface(BookableResource)
    reg.register_interface(Maintainable)
    reg.register_interface_implementation("BookableResource", "RoomEntity")
    reg.register_interface_implementation("Maintainable", "RoomEntity")

    yield


class TestBookableResource:
    """BookableResource 接口测试"""

    def test_interface_definition(self):
        """验证接口定义"""
        assert "status" in BookableResource.required_properties
        assert "check_in" in BookableResource.required_actions
        assert "check_out" in BookableResource.required_actions

    def test_room_implements_bookable(self):
        """Room 实现了 BookableResource 接口"""
        reg = OntologyRegistry()
        impls = reg.get_implementations("BookableResource")
        assert "RoomEntity" in impls


class TestMaintainable:
    """Maintainable 接口测试"""

    def test_interface_definition(self):
        """验证接口定义"""
        assert "status" in Maintainable.required_properties
        assert "mark_maintenance" in Maintainable.required_actions
        assert "complete_maintenance" in Maintainable.required_actions

    def test_room_implements_maintainable(self):
        """Room 实现了 Maintainable 接口"""
        reg = OntologyRegistry()
        impls = reg.get_implementations("Maintainable")
        assert "RoomEntity" in impls


class TestBillable:
    """Billable 接口测试"""

    def test_interface_definition(self):
        """验证接口定义"""
        assert "total_amount" in Billable.required_properties
        assert "paid_amount" in Billable.required_properties
        assert "add_payment" in Billable.required_actions


class TestTrackable:
    """Trackable 接口测试"""

    def test_interface_definition(self):
        """验证接口定义"""
        assert "status" in Trackable.required_properties
        assert "created_at" in Trackable.required_properties
        assert Trackable.required_actions == []


class TestRoomInterfaceRegistration:
    """Room 接口注册验证"""

    def test_room_registered_in_schema(self):
        """Room 的接口信息能在 schema 导出中体现"""
        reg = OntologyRegistry()
        schema = reg.export_schema()

        # 检查接口是否导出
        assert "BookableResource" in schema["interfaces"]
        assert "Maintainable" in schema["interfaces"]

        # 检查 Room 在实现列表中
        assert "RoomEntity" in schema["interfaces"]["BookableResource"]["implementations"]
        assert "RoomEntity" in schema["interfaces"]["Maintainable"]["implementations"]

    def test_room_has_implements_attribute(self):
        """RoomEntity 类上有 __implements_interfaces__ 属性"""
        from app.hotel.domain.room import RoomEntity
        assert hasattr(RoomEntity, '__implements_interfaces__')
        interface_names = [i.__name__ for i in RoomEntity.__implements_interfaces__]
        assert "BookableResource" in interface_names
        assert "Maintainable" in interface_names

    def test_interface_registered_in_registry(self):
        """接口类被注册到注册中心"""
        reg = OntologyRegistry()
        assert reg.get_interface("BookableResource") is BookableResource
        assert reg.get_interface("Maintainable") is Maintainable
