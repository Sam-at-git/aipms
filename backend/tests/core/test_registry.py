"""
测试 core.ontology.registry 本体注册中心
"""
import pytest
from core.ontology.registry import OntologyRegistry, registry
from core.ontology.metadata import (
    EntityMetadata,
    ActionMetadata,
    StateMachine,
    StateTransition,
    BusinessRule,
    ActionParam,
    ParamType,
)


def test_singleton_pattern():
    """测试单例模式"""
    reg1 = OntologyRegistry()
    reg2 = OntologyRegistry()
    assert reg1 is reg2


def test_global_registry_is_singleton():
    """测试全局注册中心是单例"""
    reg = OntologyRegistry()
    assert registry is reg


def test_register_and_get_entity():
    """测试实体注册和获取"""
    reg = OntologyRegistry()
    reg.clear()

    metadata = EntityMetadata(
        name="Room",
        description="酒店房间",
        table_name="rooms",
    )
    reg.register_entity(metadata)

    retrieved = reg.get_entity("Room")
    assert retrieved is metadata
    assert retrieved.name == "Room"


def test_get_entity_not_found():
    """测试获取不存在的实体返回 None"""
    reg = OntologyRegistry()
    reg.clear()

    assert reg.get_entity("NonExistent") is None


def test_get_entities():
    """测试获取所有实体"""
    reg = OntologyRegistry()
    reg.clear()

    reg.register_entity(EntityMetadata(name="Room", description="", table_name="rooms"))
    reg.register_entity(EntityMetadata(name="Guest", description="", table_name="guests"))

    entities = reg.get_entities()
    assert len(entities) == 2
    entity_names = {e.name for e in entities}
    assert entity_names == {"Room", "Guest"}


def test_register_and_get_action():
    """测试动作注册和获取"""
    reg = OntologyRegistry()
    reg.clear()

    action = ActionMetadata(
        action_type="update_status",
        entity="Room",
        method_name="update_status",
        description="更新房间状态",
    )
    reg.register_action("Room", action)

    actions = reg.get_actions("Room")
    assert len(actions) == 1
    assert actions[0].action_type == "update_status"


def test_get_actions_by_entity():
    """测试按实体获取动作"""
    reg = OntologyRegistry()
    reg.clear()

    action1 = ActionMetadata(
        action_type="update_status", entity="Room", method_name="m1", description=""
    )
    action2 = ActionMetadata(
        action_type="delete", entity="Room", method_name="m2", description=""
    )
    action3 = ActionMetadata(
        action_type="create", entity="Guest", method_name="m3", description=""
    )

    reg.register_action("Room", action1)
    reg.register_action("Room", action2)
    reg.register_action("Guest", action3)

    room_actions = reg.get_actions("Room")
    assert len(room_actions) == 2

    guest_actions = reg.get_actions("Guest")
    assert len(guest_actions) == 1


def test_get_all_actions():
    """测试获取所有动作"""
    reg = OntologyRegistry()
    reg.clear()

    reg.register_action("Room", ActionMetadata(action_type="a1", entity="Room", method_name="m1", description=""))
    reg.register_action("Guest", ActionMetadata(action_type="a2", entity="Guest", method_name="m2", description=""))

    all_actions = reg.get_actions()
    assert len(all_actions) == 2


def test_get_actions_empty_entity():
    """测试获取不存在实体的动作返回空列表"""
    reg = OntologyRegistry()
    reg.clear()

    assert reg.get_actions("NonExistent") == []


def test_register_and_get_state_machine():
    """测试状态机注册"""
    reg = OntologyRegistry()
    reg.clear()

    machine = StateMachine(
        entity="Room",
        states=["vacant_clean", "occupied", "vacant_dirty"],
        transitions=[
            StateTransition(from_state="vacant_clean", to_state="occupied", trigger="check_in"),
        ],
        initial_state="vacant_clean",
    )
    reg.register_state_machine(machine)

    retrieved = reg.get_state_machine("Room")
    assert retrieved is machine
    assert retrieved.entity == "Room"


def test_get_state_machine_not_found():
    """测试获取不存在实体的状态机返回 None"""
    reg = OntologyRegistry()
    reg.clear()

    assert reg.get_state_machine("NonExistent") is None


def test_register_and_get_business_rule():
    """测试业务规则注册"""
    reg = OntologyRegistry()
    reg.clear()

    rule = BusinessRule(
        rule_id="test_rule",
        entity="Room",
        rule_name="测试规则",
        description="测试",
        condition="True",
        action="pass",
    )
    reg.register_business_rule("Room", rule)

    rules = reg.get_business_rules("Room")
    assert len(rules) == 1
    assert rules[0].rule_id == "test_rule"


def test_get_business_rules_by_entity():
    """测试按实体获取业务规则"""
    reg = OntologyRegistry()
    reg.clear()

    rule1 = BusinessRule(rule_id="r1", entity="Room", rule_name="R1", description="", condition="", action="")
    rule2 = BusinessRule(rule_id="r2", entity="Room", rule_name="R2", description="", condition="", action="")
    rule3 = BusinessRule(rule_id="r3", entity="Guest", rule_name="R3", description="", condition="", action="")

    reg.register_business_rule("Room", rule1)
    reg.register_business_rule("Room", rule2)
    reg.register_business_rule("Guest", rule3)

    room_rules = reg.get_business_rules("Room")
    assert len(room_rules) == 2

    guest_rules = reg.get_business_rules("Guest")
    assert len(guest_rules) == 1


def test_get_all_business_rules():
    """测试获取所有业务规则"""
    reg = OntologyRegistry()
    reg.clear()

    reg.register_business_rule("Room", BusinessRule(rule_id="r1", entity="Room", rule_name="R1", description="", condition="", action=""))
    reg.register_business_rule("Guest", BusinessRule(rule_id="r2", entity="Guest", rule_name="R2", description="", condition="", action=""))

    all_rules = reg.get_business_rules()
    assert len(all_rules) == 2


def test_get_business_rules_empty_entity():
    """测试获取不存在实体的业务规则返回空列表"""
    reg = OntologyRegistry()
    reg.clear()

    assert reg.get_business_rules("NonExistent") == []


def test_register_permission():
    """测试权限注册"""
    reg = OntologyRegistry()
    reg.clear()

    reg.register_permission("update_status", {"manager", "receptionist"})

    perms = reg.get_permissions()
    assert "update_status" in perms
    assert "manager" in perms["update_status"]
    assert "receptionist" in perms["update_status"]


def test_register_permission_multiple_calls():
    """测试多次注册权限会合并角色"""
    reg = OntologyRegistry()
    reg.clear()

    reg.register_permission("update_status", {"manager"})
    reg.register_permission("update_status", {"receptionist"})

    perms = reg.get_permissions()
    assert len(perms["update_status"]) == 2
    assert "manager" in perms["update_status"]
    assert "receptionist" in perms["update_status"]


def test_get_permissions():
    """测试获取权限矩阵返回副本"""
    reg = OntologyRegistry()
    reg.clear()

    reg.register_permission("action1", {"role1"})

    perms1 = reg.get_permissions()
    perms2 = reg.get_permissions()

    # 修改返回的字典不应该影响原始数据
    perms1["action2"] = {"role2"}

    assert "action2" not in perms2
    assert "action2" not in reg.get_permissions()


def test_clear():
    """测试清空注册表"""
    reg = OntologyRegistry()

    # 添加一些数据
    reg.register_entity(EntityMetadata(name="Test", description="", table_name="test"))
    reg.register_action("Test", ActionMetadata(action_type="test", entity="Test", method_name="test", description=""))
    reg.register_state_machine(
        StateMachine(entity="Test", states=["s1"], transitions=[], initial_state="s1")
    )
    reg.register_business_rule("Test", BusinessRule(rule_id="r1", entity="Test", rule_name="R1", description="", condition="", action=""))
    reg.register_permission("test", {"role1"})

    # 清空
    reg.clear()

    # 验证所有数据都被清空
    assert reg.get_entity("Test") is None
    assert len(reg.get_entities()) == 0
    assert reg.get_actions("Test") == []
    assert reg.get_state_machine("Test") is None
    assert reg.get_business_rules("Test") == []
    assert reg.get_permissions() == {}


def test_clear_affects_all_instances():
    """测试清空会影响所有单例实例"""
    reg1 = OntologyRegistry()
    reg2 = OntologyRegistry()

    reg1.register_entity(EntityMetadata(name="Test", description="", table_name="test"))

    assert reg2.get_entity("Test") is not None

    reg2.clear()

    assert reg1.get_entity("Test") is None


def test_register_entity_overwrite():
    """测试注册同名实体会覆盖"""
    reg = OntologyRegistry()
    reg.clear()

    entity1 = EntityMetadata(name="Room", description="旧描述", table_name="rooms")
    entity2 = EntityMetadata(name="Room", description="新描述", table_name="rooms")

    reg.register_entity(entity1)
    reg.register_entity(entity2)

    retrieved = reg.get_entity("Room")
    assert retrieved.description == "新描述"
    assert retrieved is entity2


def test_multiple_actions_per_entity():
    """测试一个实体可以有多个动作"""
    reg = OntologyRegistry()
    reg.clear()

    action1 = ActionMetadata(action_type="create", entity="Room", method_name="create", description="")
    action2 = ActionMetadata(action_type="update", entity="Room", method_name="update", description="")
    action3 = ActionMetadata(action_type="delete", entity="Room", method_name="delete", description="")

    reg.register_action("Room", action1)
    reg.register_action("Room", action2)
    reg.register_action("Room", action3)

    actions = reg.get_actions("Room")
    assert len(actions) == 3
