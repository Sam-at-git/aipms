"""
core/domain/interfaces.py

业务接口定义 - 酒店领域的通用抽象

这些接口定义了跨实体的通用行为契约，
支持面向接口编程，增强系统可扩展性。

设计原则：
- 接口基于实际业务场景定义
- 属性要求尽量宽松（只要求核心属性）
- 动作要求基于已有的 @ontology_action 装饰器
"""
from core.ontology.interface import OntologyInterface
from core.ontology.metadata import ParamType


class BookableResource(OntologyInterface):
    """
    可预订资源接口

    适用实体: Room, MeetingRoom, BanquetHall
    核心能力: 具有状态管理和入住/退房流程
    """
    required_properties = {
        "status": ParamType.STRING,
    }
    required_actions = [
        "check_in",
        "check_out",
    ]


class Maintainable(OntologyInterface):
    """
    可维护实体接口

    适用实体: Room, Equipment
    核心能力: 支持维护流程（标记维修、完成维修）
    """
    required_properties = {
        "status": ParamType.STRING,
    }
    required_actions = [
        "mark_maintenance",
        "complete_maintenance",
    ]


class Billable(OntologyInterface):
    """
    可计费实体接口

    适用实体: StayRecord, Reservation, ServiceOrder
    核心能力: 具有金额和支付能力
    """
    required_properties = {
        "total_amount": ParamType.NUMBER,
        "paid_amount": ParamType.NUMBER,
    }
    required_actions = [
        "add_payment",
    ]


class Trackable(OntologyInterface):
    """
    可追踪实体接口

    适用实体: Task, Delivery, Order
    核心能力: 具有状态和时间追踪
    """
    required_properties = {
        "status": ParamType.STRING,
        "created_at": ParamType.DATETIME,
    }
    required_actions = []


# 导出
__all__ = [
    "BookableResource",
    "Maintainable",
    "Billable",
    "Trackable",
]
