"""
tests/domain/rules/test_room_rules.py

房间规则单元测试
"""
import pytest
from datetime import date

from app.hotel.domain.rules.room_rules import (
    register_room_rules,
    should_create_cleaning_task_after_checkout,
    should_mark_room_occupied_after_checkin,
)
from core.engine.rule_engine import RuleContext, RuleEngine


class TestRoomRulesRegistration:
    """房间规则注册测试"""

    def test_register_room_rules(self):
        """测试注册房间规则"""
        engine = RuleEngine()
        register_room_rules(engine)

        # 验证规则已注册
        assert engine.get_rule("room_checkout_to_dirty") is not None
        assert engine.get_rule("room_checkin_to_occupied") is not None
        assert engine.get_rule("room_clean_to_vacant") is not None


class TestConvenienceFunctions:
    """便捷函数测试"""

    def test_should_create_cleaning_task_after_checkout(self):
        """测试退房后是否应该创建清洁任务"""
        from app.models.ontology import RoomStatus

        assert should_create_cleaning_task_after_checkout(RoomStatus.VACANT_DIRTY.value) is True
        assert should_create_cleaning_task_after_checkout(RoomStatus.OCCUPIED.value) is False
        assert should_create_cleaning_task_after_checkout(RoomStatus.VACANT_CLEAN.value) is False

    def test_should_mark_room_occupied_after_checkin(self):
        """测试入住后是否应该标记房间为占用"""
        from app.models.ontology import RoomStatus

        assert should_mark_room_occupied_after_checkin(RoomStatus.VACANT_CLEAN.value) is True
        assert should_mark_room_occupied_after_checkin(RoomStatus.VACANT_DIRTY.value) is True
        assert should_mark_room_occupied_after_checkin(RoomStatus.OCCUPIED.value) is False


class TestCheckoutRule:
    """退房转脏房规则测试"""

    def test_checkout_action_triggers_dirty_rule(self):
        """测试退房动作触发脏房规则"""
        engine = RuleEngine()
        register_room_rules(engine)

        # 模拟退房上下文
        class MockRoom:
            def __str__(self):
                return "Room 201"

        context = RuleContext(
            entity=MockRoom(),
            entity_type="room",
            action="checkout",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "room_checkout_to_dirty" in rule_ids

    def test_checkin_action_does_not_trigger_dirty_rule(self):
        """测试入住动作不触发脏房规则"""
        engine = RuleEngine()
        register_room_rules(engine)

        class MockRoom:
            def __str__(self):
                return "Room 201"

        context = RuleContext(
            entity=MockRoom(),
            entity_type="room",
            action="checkin",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "room_checkout_to_dirty" not in rule_ids


class TestCheckinRule:
    """入住转占用规则测试"""

    def test_checkin_action_triggers_occupied_rule(self):
        """测试入住动作触发占用规则"""
        engine = RuleEngine()
        register_room_rules(engine)

        class MockRoom:
            def __str__(self):
                return "Room 201"

        context = RuleContext(
            entity=MockRoom(),
            entity_type="room",
            action="checkin",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "room_checkin_to_occupied" in rule_ids

    def test_walkin_checkin_triggers_occupied_rule(self):
        """测试散客入住触发占用规则"""
        engine = RuleEngine()
        register_room_rules(engine)

        class MockRoom:
            def __str__(self):
                return "Room 201"

        context = RuleContext(
            entity=MockRoom(),
            entity_type="room",
            action="walkin_checkin",
            parameters={}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "room_checkin_to_occupied" in rule_ids


class TestCleaningRule:
    """清洁转空闲规则测试"""

    def test_cleaning_complete_triggers_vacant_rule(self):
        """测试清洁完成触发空闲规则"""
        engine = RuleEngine()
        register_room_rules(engine)

        class MockRoom:
            def __str__(self):
                return "Room 201"

        context = RuleContext(
            entity=MockRoom(),
            entity_type="room",
            action="complete_task",
            parameters={"task_type": "cleaning"}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "room_clean_to_vacant" in rule_ids

    def test_other_task_does_not_trigger_vacant_rule(self):
        """测试其他任务不触发空闲规则"""
        engine = RuleEngine()
        register_room_rules(engine)

        class MockRoom:
            def __str__(self):
                return "Room 201"

        context = RuleContext(
            entity=MockRoom(),
            entity_type="room",
            action="complete_task",
            parameters={"task_type": "maintenance"}
        )

        triggered = engine.evaluate(context)
        rule_ids = [r.rule_id for r in triggered]

        assert "room_clean_to_vacant" not in rule_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
