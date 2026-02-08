"""
测试 core.ontology.interface 接口多态系统 (SPEC-02.5.2)
"""
import pytest
from core.ontology.interface import OntologyInterface, implements
from core.ontology.metadata import ParamType
from core.ontology.registry import OntologyRegistry


@pytest.fixture(autouse=True)
def clean_registry():
    """每个测试前清空注册表"""
    reg = OntologyRegistry()
    reg.clear()
    yield reg
    reg.clear()


class TestOntologyInterface:
    """OntologyInterface 基类测试"""

    def test_interface_has_marker(self):
        """接口类有 __is_ontology_interface__ 标记"""
        assert OntologyInterface.__is_ontology_interface__ is True

    def test_default_empty_contracts(self):
        """默认接口没有契约要求"""
        class EmptyInterface(OntologyInterface):
            pass

        assert EmptyInterface.required_properties == {}
        assert EmptyInterface.required_links == {}
        assert EmptyInterface.required_actions == []

    def test_define_interface_with_properties(self):
        """定义带属性要求的接口"""
        class Searchable(OntologyInterface):
            required_properties = {
                "name": ParamType.STRING,
                "status": ParamType.STRING,
            }

        assert len(Searchable.required_properties) == 2
        assert Searchable.required_properties["name"] == ParamType.STRING

    def test_define_interface_with_actions(self):
        """定义带动作要求的接口"""
        class Bookable(OntologyInterface):
            required_actions = ["check_availability", "book"]

        assert len(Bookable.required_actions) == 2
        assert "book" in Bookable.required_actions


class TestValidateImplementation:
    """validate_implementation() 测试"""

    def test_validate_passes_with_properties(self):
        """具有所有必需属性的类通过验证"""
        class HasStatus(OntologyInterface):
            required_properties = {"status": ParamType.STRING}

        class MyEntity:
            @property
            def status(self):
                return "active"

        errors = HasStatus.validate_implementation(MyEntity)
        assert errors == []

    def test_validate_fails_missing_property(self):
        """缺少必需属性的类验证失败"""
        class NeedsName(OntologyInterface):
            required_properties = {"name": ParamType.STRING}

        class MyEntity:
            pass

        errors = NeedsName.validate_implementation(MyEntity)
        assert len(errors) == 1
        assert "name" in errors[0]

    def test_validate_passes_with_annotations(self):
        """通过类型注解声明的属性也能通过验证"""
        class NeedsCapacity(OntologyInterface):
            required_properties = {"capacity": ParamType.INTEGER}

        class MyEntity:
            capacity: int = 0

        errors = NeedsCapacity.validate_implementation(MyEntity)
        assert errors == []

    def test_validate_passes_with_ontology_properties(self):
        """通过 __ontology_properties__ 声明的属性能通过验证"""
        class NeedsStatus(OntologyInterface):
            required_properties = {"status": ParamType.STRING}

        class MyEntity:
            __ontology_properties__ = {"status": "string"}

        errors = NeedsStatus.validate_implementation(MyEntity)
        assert errors == []

    def test_validate_actions_pass(self):
        """具有所有必需动作的类通过验证"""
        class NeedsActions(OntologyInterface):
            required_actions = ["do_something"]

        class MyEntity:
            __ontology_actions__ = ["do_something"]

        errors = NeedsActions.validate_implementation(MyEntity)
        assert errors == []

    def test_validate_actions_fail(self):
        """缺少必需动作的类验证失败"""
        class NeedsActions(OntologyInterface):
            required_actions = ["do_something"]

        class MyEntity:
            __ontology_actions__ = []

        errors = NeedsActions.validate_implementation(MyEntity)
        assert len(errors) == 1
        assert "do_something" in errors[0]

    def test_validate_multiple_errors(self):
        """多个缺失项会返回所有错误"""
        class Complex(OntologyInterface):
            required_properties = {
                "name": ParamType.STRING,
                "status": ParamType.STRING,
            }
            required_actions = ["action1", "action2"]

        class EmptyEntity:
            pass

        errors = Complex.validate_implementation(EmptyEntity)
        assert len(errors) == 4  # 2 properties + 2 actions


class TestImplementsDecorator:
    """@implements 装饰器测试"""

    def test_implements_basic(self, clean_registry):
        """基本的 implements 装饰器功能"""
        class Trackable(OntologyInterface):
            required_properties = {"status": ParamType.STRING}

        @implements(Trackable)
        class TaskEntity:
            __ontology_properties__ = {"status": "string"}

        # 验证注册
        impls = clean_registry.get_implementations("Trackable")
        assert "TaskEntity" in impls

    def test_implements_multiple_interfaces(self, clean_registry):
        """实现多个接口"""
        class Interface1(OntologyInterface):
            required_properties = {"name": ParamType.STRING}

        class Interface2(OntologyInterface):
            required_properties = {"status": ParamType.STRING}

        @implements(Interface1, Interface2)
        class MultiEntity:
            __ontology_properties__ = {"name": "string", "status": "string"}

        impls1 = clean_registry.get_implementations("Interface1")
        impls2 = clean_registry.get_implementations("Interface2")
        assert "MultiEntity" in impls1
        assert "MultiEntity" in impls2

    def test_implements_registers_interface(self, clean_registry):
        """装饰器会注册接口本身"""
        class Bookable(OntologyInterface):
            """可预订资源"""
            required_properties = {"status": ParamType.STRING}

        @implements(Bookable)
        class RoomEntity:
            __ontology_properties__ = {"status": "string"}

        iface = clean_registry.get_interface("Bookable")
        assert iface is Bookable

    def test_implements_sets_class_attribute(self, clean_registry):
        """装饰器在类上设置 __implements_interfaces__"""
        class Iface(OntologyInterface):
            pass

        @implements(Iface)
        class MyEntity:
            pass

        assert hasattr(MyEntity, '__implements_interfaces__')
        assert Iface in MyEntity.__implements_interfaces__

    def test_implements_fails_on_contract_violation(self, clean_registry):
        """不满足契约时抛出 TypeError"""
        class StrictInterface(OntologyInterface):
            required_properties = {
                "name": ParamType.STRING,
                "capacity": ParamType.INTEGER,
            }

        with pytest.raises(TypeError, match="does not satisfy interface contracts"):
            @implements(StrictInterface)
            class BadEntity:
                pass

    def test_implements_with_property_descriptors(self, clean_registry):
        """使用 Python property 的实体能通过验证"""
        class HasName(OntologyInterface):
            required_properties = {"name": ParamType.STRING}

        @implements(HasName)
        class PropEntity:
            @property
            def name(self):
                return "test"

        impls = clean_registry.get_implementations("HasName")
        assert "PropEntity" in impls

    def test_implements_preserves_class(self, clean_registry):
        """装饰器不改变原始类"""
        class Iface(OntologyInterface):
            pass

        @implements(Iface)
        class Original:
            value = 42

        assert Original.value == 42
        obj = Original()
        assert obj.value == 42
