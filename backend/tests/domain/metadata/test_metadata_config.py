"""
tests/domain/metadata/test_metadata_config.py

元数据配置测试
"""
import pytest
from pathlib import Path

from app.hotel.domain.metadata import (
    load_security_levels,
    load_hitl_policies,
    get_security_level,
    get_action_confirmation_level,
    get_action_requirements,
    get_role_exemptions,
    should_skip_confirmation,
)


class TestSecurityLevelsConfig:
    """安全等级配置测试"""

    def test_load_security_levels(self):
        """测试加载安全等级配置"""
        config = load_security_levels()

        assert isinstance(config, dict)
        assert "Room" in config
        assert "Guest" in config
        assert "Bill" in config

    def test_room_security_levels(self):
        """测试房间安全等级"""
        assert get_security_level("Room", "room_number") == "PUBLIC"
        assert get_security_level("Room", "status") == "PUBLIC"
        assert get_security_level("Room", "base_price") == "RESTRICTED"
        assert get_security_level("Room", "internal_notes") == "CONFIDENTIAL"

    def test_guest_security_levels(self):
        """测试客人安全等级"""
        assert get_security_level("Guest", "name") == "PUBLIC"
        assert get_security_level("Guest", "phone") == "INTERNAL"
        assert get_security_level("Guest", "id_number") == "RESTRICTED"
        assert get_security_level("Guest", "blacklist_reason") == "CONFIDENTIAL"

    def test_bill_security_levels(self):
        """测试账单安全等级"""
        assert get_security_level("Bill", "id") == "RESTRICTED"
        assert get_security_level("Bill", "total_amount") == "RESTRICTED"
        assert get_security_level("Bill", "adjustment_amount") == "RESTRICTED"

    def test_unknown_property_returns_internal(self):
        """测试未知属性返回 INTERNAL"""
        assert get_security_level("Room", "unknown_property") == "INTERNAL"
        assert get_security_level("UnknownEntity", "any_property") == "INTERNAL"

    def test_default_values(self):
        """测试默认值"""
        assert get_security_level("AnyEntity", "id") == "INTERNAL"
        assert get_security_level("AnyEntity", "created_at") == "INTERNAL"
        assert get_security_level("AnyEntity", "notes") == "RESTRICTED"


class TestHITLPoliciesConfig:
    """HITL 策略配置测试"""

    def test_load_hitl_policies(self):
        """测试加载 HITL 策略配置"""
        config = load_hitl_policies()

        assert isinstance(config, dict)
        assert "high_risk_actions" in config
        assert "medium_risk_actions" in config
        assert "low_risk_actions" in config

    def test_high_risk_actions(self):
        """测试高风险操作配置"""
        config = load_hitl_policies()
        high_risk = config["high_risk_actions"]

        assert len(high_risk) > 0
        assert any(a["action_type"] == "adjust_bill" for a in high_risk)
        assert any(a["action_type"] == "delete_guest" for a in high_risk)

        # adjust_bill 应该是 CRITICAL 级别
        adjust_bill = next(a for a in high_risk if a["action_type"] == "adjust_bill")
        assert adjust_bill["level"] == "CRITICAL"
        assert adjust_bill["require_reason"] is True

    def test_medium_risk_actions(self):
        """测试中风险操作配置"""
        config = load_hitl_policies()
        medium_risk = config["medium_risk_actions"]

        assert len(medium_risk) > 0
        assert any(a["action_type"] == "extend_stay" for a in medium_risk)
        assert any(a["action_type"] == "change_room" for a in medium_risk)

        # extend_stay 应该是 MEDIUM 级别
        extend_stay = next(a for a in medium_risk if a["action_type"] == "extend_stay")
        assert extend_stay["level"] == "MEDIUM"

    def test_low_risk_actions(self):
        """测试低风险操作配置"""
        config = load_hitl_policies()
        low_risk = config["low_risk_actions"]

        assert len(low_risk) > 0
        assert any(a["action_type"] == "create_task" for a in low_risk)
        assert any(a["action_type"] == "complete_task" for a in low_risk)

        # start_task 应该是 NONE 级别
        start_task = next(a for a in low_risk if a["action_type"] == "start_task")
        assert start_task["level"] == "NONE"

    def test_query_actions(self):
        """测试查询操作配置"""
        config = load_hitl_policies()
        query_actions = config["query_actions"]

        assert len(query_actions) > 0
        assert any(a["action_type"] == "ontology_query" for a in query_actions)
        assert any(a["action_type"] == "view" for a in query_actions)
        assert any(a["action_type"] == "query_rooms" for a in query_actions)

        # 查询操作应该是 NONE 级别
        for action in query_actions:
            assert action["level"] in ("NONE", "LOW")


class TestConfirmationLevel:
    """确认级别测试"""

    def test_high_risk_confirmation_level(self):
        """测试高风险操作确认级别"""
        assert get_action_confirmation_level("adjust_bill") == "CRITICAL"
        assert get_action_confirmation_level("delete_guest") == "CRITICAL"
        assert get_action_confirmation_level("cancel_reservation") == "HIGH"

    def test_medium_risk_confirmation_level(self):
        """测试中风险操作确认级别"""
        assert get_action_confirmation_level("extend_stay") == "MEDIUM"
        assert get_action_confirmation_level("change_room") == "MEDIUM"
        assert get_action_confirmation_level("checkout") == "MEDIUM"

    def test_low_risk_confirmation_level(self):
        """测试低风险操作确认级别"""
        assert get_action_confirmation_level("create_task") == "LOW"
        assert get_action_confirmation_level("complete_task") == "LOW"
        assert get_action_confirmation_level("start_task") == "NONE"

    def test_query_confirmation_level(self):
        """测试查询操作确认级别"""
        assert get_action_confirmation_level("ontology_query") == "NONE"
        assert get_action_confirmation_level("view") == "NONE"
        assert get_action_confirmation_level("query_rooms") == "NONE"
        assert get_action_confirmation_level("query_reservations") == "NONE"

    def test_unknown_action_returns_medium(self):
        """测试未知操作返回 MEDIUM"""
        assert get_action_confirmation_level("unknown_action") == "MEDIUM"


class TestActionRequirements:
    """操作要求测试"""

    def test_get_adjust_bill_requirements(self):
        """测试获取账单调整要求"""
        req = get_action_requirements("adjust_bill")

        assert req["action_type"] == "adjust_bill"
        assert req["level"] == "CRITICAL"
        assert req["require_reason"] is True
        assert "manager" in req["allowed_roles"]

    def test_get_checkout_requirements(self):
        """测试获取退房要求"""
        req = get_action_requirements("checkout")

        assert req["action_type"] == "checkout"
        assert req["level"] == "MEDIUM"
        assert req["require_confirmation"] is True

    def test_get_create_task_requirements(self):
        """测试获取创建任务要求"""
        req = get_action_requirements("create_task")

        assert req["action_type"] == "create_task"
        assert req["level"] == "LOW"
        assert req["require_confirmation"] is False

    def test_unknown_action_returns_medium_requirements(self):
        """测试未知操作返回中等风险要求"""
        req = get_action_requirements("unknown_action")

        assert req["action_type"] == "unknown_action"
        assert req["level"] == "MEDIUM"
        assert req["require_confirmation"] is True


class TestRoleExemptions:
    """角色豁免测试"""

    def test_load_role_exemptions(self):
        """测试加载角色豁免配置"""
        config = load_hitl_policies()
        assert "role_exemptions" in config
        assert "manager" in config["role_exemptions"]
        assert "sysadmin" in config["role_exemptions"]

    def test_manager_exemptions(self):
        """测试经理豁免"""
        exemptions = get_role_exemptions("manager")

        assert "add_payment" in exemptions
        assert "create_reservation" in exemptions
        assert "update_room_status" in exemptions

    def test_sysadmin_exemptions(self):
        """测试系统管理员豁免"""
        exemptions = get_role_exemptions("sysadmin")

        assert "update_room_status" in exemptions
        assert "create_task" in exemptions
        assert "assign_task" in exemptions

    def test_regular_role_no_exemptions(self):
        """测试普通角色无豁免"""
        exemptions = get_role_exemptions("receptionist")

        assert len(exemptions) == 0


class TestShouldSkipConfirmation:
    """跳过确认判断测试"""

    def test_manager_can_skip_payment(self):
        """测试经理可以跳过支付确认"""
        assert should_skip_confirmation("add_payment", "manager") is True

    def test_manager_can_skip_reservation(self):
        """测试经理可以跳过预订确认"""
        assert should_skip_confirmation("create_reservation", "manager") is True

    def test_receptionist_cannot_skip_payment(self):
        """测试前台不能跳过支付确认"""
        assert should_skip_confirmation("add_payment", "receptionist") is False

    def test_sysadmin_can_skip_task_creation(self):
        """测试系统管理员可以跳过任务创建确认"""
        assert should_skip_confirmation("create_task", "sysadmin") is True

    def test_unknown_role_no_exemptions(self):
        """测试未知角色无豁免"""
        assert should_skip_confirmation("add_payment", "unknown_role") is False


class TestConfigFilesExist:
    """配置文件存在性测试"""

    def test_security_levels_file_exists(self):
        """测试安全等级配置文件存在"""
        from app.hotel.domain.metadata import _security_levels_file
        assert _security_levels_file.exists()
        assert _security_levels_file.is_file()

    def test_hitl_policies_file_exists(self):
        """测试 HITL 策略配置文件存在"""
        from app.hotel.domain.metadata import _hitl_policies_file
        assert _hitl_policies_file.exists()
        assert _hitl_policies_file.is_file()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
