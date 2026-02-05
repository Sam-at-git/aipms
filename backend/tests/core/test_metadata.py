"""
测试 core.ontology.metadata 元数据定义
"""
import pytest
from core.ontology.metadata import (
    ParamType,
    ActionParam,
    BusinessRule,
    StateTransition,
    StateMachine,
    ActionMetadata,
    PropertyMetadata,
    EntityMetadata,
)


def test_entity_metadata_creation():
    """测试实体元数据创建"""
    metadata = EntityMetadata(
        name="Room",
        description="酒店房间",
        table_name="rooms",
        is_aggregate_root=False,
    )
    assert metadata.name == "Room"
    assert metadata.description == "酒店房间"
    assert metadata.is_aggregate_root is False
    assert metadata.related_entities == []
    assert metadata.business_rules == []
    assert metadata.state_machine is None


def test_entity_metadata_with_related_entities():
    """测试包含关联实体的元数据"""
    metadata = EntityMetadata(
        name="Room",
        description="酒店房间",
        table_name="rooms",
        related_entities=["RoomType", "StayRecord", "Task"],
    )
    assert len(metadata.related_entities) == 3
    assert "RoomType" in metadata.related_entities


def test_action_metadata_creation():
    """测试动作元数据创建"""
    action = ActionMetadata(
        action_type="update_status",
        entity="Room",
        method_name="update_status",
        description="更新房间状态",
        params=[
            ActionParam(name="room_id", type=ParamType.INTEGER, required=True),
            ActionParam(
                name="status",
                type=ParamType.ENUM,
                required=True,
                enum_values=["vacant_clean", "occupied", "vacant_dirty"],
            ),
        ],
        requires_confirmation=True,
        allowed_roles={"manager", "receptionist"},
        writeback=True,
        undoable=True,
    )
    assert action.action_type == "update_status"
    assert action.entity == "Room"
    assert len(action.params) == 2
    assert action.requires_confirmation is True
    assert "manager" in action.allowed_roles
    assert action.writeback is True
    assert action.undoable is True


def test_action_metadata_defaults():
    """测试动作元数据默认值"""
    action = ActionMetadata(
        action_type="test",
        entity="Test",
        method_name="test",
        description="测试",
    )
    assert action.params == []
    assert action.requires_confirmation is False
    assert action.allowed_roles == set()
    assert action.writeback is True
    assert action.undoable is False


def test_action_param_creation():
    """测试动作参数创建"""
    param = ActionParam(
        name="guest_name",
        type=ParamType.STRING,
        required=True,
        description="客人姓名",
    )
    assert param.name == "guest_name"
    assert param.type == ParamType.STRING
    assert param.required is True


def test_action_param_with_enum():
    """测试枚举类型参数"""
    param = ActionParam(
        name="room_status",
        type=ParamType.ENUM,
        enum_values=["vacant_clean", "occupied", "vacant_dirty", "out_of_order"],
        required=True,
    )
    assert param.type == ParamType.ENUM
    assert len(param.enum_values) == 4


def test_property_metadata_security_levels():
    """测试属性安全等级"""
    prop = PropertyMetadata(
        name="id_number",
        type="String",
        python_type="str",
        security_level="RESTRICTED",
    )
    assert prop.security_level == "RESTRICTED"


def test_property_metadata_all_fields():
    """测试属性元数据所有字段"""
    prop = PropertyMetadata(
        name="id",
        type="Integer",
        python_type="int",
        is_primary_key=True,
        is_required=True,
        is_unique=True,
        is_nullable=False,
        security_level="PUBLIC",
    )
    assert prop.name == "id"
    assert prop.is_primary_key is True
    assert prop.is_required is True
    assert prop.is_unique is True
    assert prop.is_nullable is False
    assert prop.security_level == "PUBLIC"


def test_property_metadata_foreign_key():
    """测试外键属性元数据"""
    prop = PropertyMetadata(
        name="room_type_id",
        type="Integer",
        python_type="int",
        is_foreign_key=True,
        foreign_key_target="room_types",
        is_required=True,
    )
    assert prop.is_foreign_key is True
    assert prop.foreign_key_target == "room_types"


def test_property_metadata_defaults():
    """测试属性元数据默认值"""
    prop = PropertyMetadata(
        name="test",
        type="String",
        python_type="str",
    )
    assert prop.is_primary_key is False
    assert prop.is_foreign_key is False
    assert prop.is_required is False
    assert prop.is_unique is False
    assert prop.is_nullable is True
    assert prop.security_level == "INTERNAL"


def test_state_machine_creation():
    """测试状态机创建"""
    machine = StateMachine(
        entity="Room",
        states=["vacant_clean", "occupied", "vacant_dirty", "out_of_order"],
        transitions=[
            StateTransition(from_state="vacant_clean", to_state="occupied", trigger="check_in"),
            StateTransition(
                from_state="occupied",
                to_state="vacant_dirty",
                trigger="check_out",
                side_effects=["create_cleaning_task"],
            ),
            StateTransition(from_state="vacant_dirty", to_state="vacant_clean", trigger="task_complete"),
        ],
        initial_state="vacant_clean",
    )
    assert machine.entity == "Room"
    assert len(machine.states) == 4
    assert len(machine.transitions) == 3
    assert machine.initial_state == "vacant_clean"
    assert machine.transitions[1].side_effects == ["create_cleaning_task"]


def test_state_transition_with_condition():
    """测试带条件的状态转换"""
    transition = StateTransition(
        from_state="vacant_dirty",
        to_state="vacant_clean",
        trigger="task_complete",
        condition="task.type == 'cleaning' and task.status == 'completed'",
    )
    assert transition.condition is not None
    assert "task.type" in transition.condition


def test_business_rule_creation():
    """测试业务规则创建"""
    rule = BusinessRule(
        rule_id="checkout_auto_dirty",
        entity="Room",
        rule_name="退房自动转脏房",
        description="客人退房后房间自动变为待清洁状态",
        condition="status == 'occupied' and event == 'checkout'",
        action="status = 'vacant_dirty'",
        severity="info",
    )
    assert rule.rule_id == "checkout_auto_dirty"
    assert rule.entity == "Room"
    assert rule.severity == "info"


def test_business_rule_defaults():
    """测试业务规则默认值"""
    rule = BusinessRule(
        rule_id="test",
        entity="Test",
        rule_name="测试",
        description="测试规则",
        condition="True",
        action="pass",
    )
    assert rule.severity == "error"


def test_param_type_enum():
    """测试参数类型枚举"""
    assert ParamType.STRING == "string"
    assert ParamType.INTEGER == "integer"
    assert ParamType.NUMBER == "number"
    assert ParamType.BOOLEAN == "boolean"
    assert ParamType.DATE == "date"
    assert ParamType.DATETIME == "datetime"
    assert ParamType.ENUM == "enum"
    assert ParamType.ARRAY == "array"
    assert ParamType.OBJECT == "object"


def test_dataclass_immutability_of_defaults():
    """测试数据类默认值的正确性（避免共享可变对象）"""
    # 创建两个元数据实例
    entity1 = EntityMetadata(name="E1", description="", table_name="t1")
    entity2 = EntityMetadata(name="E2", description="", table_name="t2")

    # 修改一个实例的列表
    entity1.related_entities.append("Related")

    # 另一个实例不应该受影响
    assert len(entity2.related_entities) == 0
    assert len(entity1.related_entities) == 1


def test_action_metadata_with_empty_params():
    """测试空参数列表的动作元数据"""
    action = ActionMetadata(
        action_type="get_all",
        entity="Room",
        method_name="get_all_rooms",
        description="获取所有房间",
        params=[],
    )
    assert action.params == []


def test_state_machine_empty_transitions():
    """测试无转换的状态机"""
    machine = StateMachine(
        entity="Simple",
        states=["state1"],
        transitions=[],
        initial_state="state1",
    )
    assert len(machine.transitions) == 0
