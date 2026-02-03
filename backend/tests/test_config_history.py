"""
配置版本管理服务单元测试
"""
import pytest
import json

from app.services.config_history_service import ConfigHistoryService
from app.models.snapshots import ConfigHistory


class TestConfigHistoryService:
    """配置版本管理服务测试"""

    @pytest.fixture
    def config_service(self, db_session):
        """创建配置历史服务实例"""
        return ConfigHistoryService(db_session)

    def test_record_change(self, config_service, db_session, sample_employee):
        """测试记录配置变更"""
        history = config_service.record_change(
            config_key="llm_settings",
            old_value={"model": "gpt-3.5"},
            new_value={"model": "gpt-4"},
            changed_by=sample_employee.id,
            change_reason="升级模型"
        )
        db_session.commit()

        assert history is not None
        assert history.config_key == "llm_settings"
        assert history.version == 1
        assert history.is_current == True
        assert history.change_reason == "升级模型"

    def test_record_change_increments_version(self, config_service, db_session, sample_employee):
        """测试版本号递增"""
        config_service.record_change(
            config_key="llm_settings",
            old_value={"model": "gpt-3.5"},
            new_value={"model": "gpt-4"},
            changed_by=sample_employee.id
        )
        db_session.commit()

        history2 = config_service.record_change(
            config_key="llm_settings",
            old_value={"model": "gpt-4"},
            new_value={"model": "gpt-4-turbo"},
            changed_by=sample_employee.id
        )
        db_session.commit()

        assert history2.version == 2

    def test_previous_version_not_current(self, config_service, db_session, sample_employee):
        """测试之前版本标记为非当前"""
        history1 = config_service.record_change(
            config_key="llm_settings",
            old_value={},
            new_value={"model": "gpt-4"},
            changed_by=sample_employee.id
        )
        db_session.commit()

        config_service.record_change(
            config_key="llm_settings",
            old_value={"model": "gpt-4"},
            new_value={"model": "gpt-4-turbo"},
            changed_by=sample_employee.id
        )
        db_session.commit()

        # 刷新第一个历史记录
        db_session.refresh(history1)
        assert history1.is_current == False

    def test_get_history(self, config_service, db_session, sample_employee):
        """测试获取历史记录"""
        for i in range(5):
            config_service.record_change(
                config_key="llm_settings",
                old_value={"version": i},
                new_value={"version": i + 1},
                changed_by=sample_employee.id
            )
        db_session.commit()

        history = config_service.get_history("llm_settings")
        assert len(history) == 5
        # 最新版本在前
        assert history[0].version == 5

    def test_get_history_limit(self, config_service, db_session, sample_employee):
        """测试获取历史记录限制"""
        for i in range(10):
            config_service.record_change(
                config_key="llm_settings",
                old_value={},
                new_value={"version": i},
                changed_by=sample_employee.id
            )
        db_session.commit()

        history = config_service.get_history("llm_settings", limit=5)
        assert len(history) == 5

    def test_get_version(self, config_service, db_session, sample_employee):
        """测试获取特定版本"""
        config_service.record_change(
            config_key="llm_settings",
            old_value={},
            new_value={"model": "gpt-4"},
            changed_by=sample_employee.id
        )
        config_service.record_change(
            config_key="llm_settings",
            old_value={"model": "gpt-4"},
            new_value={"model": "gpt-4-turbo"},
            changed_by=sample_employee.id
        )
        db_session.commit()

        version1 = config_service.get_version("llm_settings", 1)
        version2 = config_service.get_version("llm_settings", 2)

        assert version1 is not None
        assert version2 is not None
        assert json.loads(version1.new_value)["model"] == "gpt-4"
        assert json.loads(version2.new_value)["model"] == "gpt-4-turbo"

    def test_get_version_not_found(self, config_service, db_session):
        """测试获取不存在的版本"""
        version = config_service.get_version("llm_settings", 999)
        assert version is None

    def test_get_current(self, config_service, db_session, sample_employee):
        """测试获取当前版本"""
        config_service.record_change(
            config_key="llm_settings",
            old_value={},
            new_value={"model": "gpt-4"},
            changed_by=sample_employee.id
        )
        config_service.record_change(
            config_key="llm_settings",
            old_value={"model": "gpt-4"},
            new_value={"model": "gpt-4-turbo"},
            changed_by=sample_employee.id
        )
        db_session.commit()

        current = config_service.get_current("llm_settings")
        assert current is not None
        assert current.version == 2
        assert current.is_current == True

    def test_rollback_to_version(self, config_service, db_session, sample_employee):
        """测试回滚到指定版本"""
        config_service.record_change(
            config_key="llm_settings",
            old_value={},
            new_value={"model": "gpt-4", "temperature": 0.7},
            changed_by=sample_employee.id
        )
        config_service.record_change(
            config_key="llm_settings",
            old_value={"model": "gpt-4", "temperature": 0.7},
            new_value={"model": "gpt-4-turbo", "temperature": 0.5},
            changed_by=sample_employee.id
        )
        db_session.commit()

        # 回滚到版本1
        rollback_history = config_service.rollback_to_version(
            config_key="llm_settings",
            version=1,
            changed_by=sample_employee.id
        )
        db_session.commit()

        assert rollback_history.version == 3
        assert "回滚到版本 1" in rollback_history.change_reason

        # 验证新值是版本1的值
        new_value = json.loads(rollback_history.new_value)
        assert new_value["model"] == "gpt-4"
        assert new_value["temperature"] == 0.7

    def test_rollback_to_nonexistent_version(self, config_service, db_session, sample_employee):
        """测试回滚到不存在的版本"""
        config_service.record_change(
            config_key="llm_settings",
            old_value={},
            new_value={"model": "gpt-4"},
            changed_by=sample_employee.id
        )
        db_session.commit()

        with pytest.raises(ValueError, match="不存在"):
            config_service.rollback_to_version(
                config_key="llm_settings",
                version=999,
                changed_by=sample_employee.id
            )

    def test_compare_versions(self, config_service, db_session, sample_employee):
        """测试比较版本差异"""
        config_service.record_change(
            config_key="llm_settings",
            old_value={},
            new_value={"model": "gpt-4", "temperature": 0.7},
            changed_by=sample_employee.id
        )
        config_service.record_change(
            config_key="llm_settings",
            old_value={"model": "gpt-4", "temperature": 0.7},
            new_value={"model": "gpt-4-turbo", "max_tokens": 1000},
            changed_by=sample_employee.id
        )
        db_session.commit()

        diff = config_service.compare_versions("llm_settings", 1, 2)

        assert "added" in diff
        assert "removed" in diff
        assert "changed" in diff

        # max_tokens 是新增的
        assert "max_tokens" in diff["added"]

        # temperature 被移除了
        assert "temperature" in diff["removed"]

        # model 改变了
        assert "model" in diff["changed"]
        assert diff["changed"]["model"]["old"] == "gpt-4"
        assert diff["changed"]["model"]["new"] == "gpt-4-turbo"

    def test_different_config_keys_independent(self, config_service, db_session, sample_employee):
        """测试不同配置项独立"""
        config_service.record_change(
            config_key="llm_settings",
            old_value={},
            new_value={"model": "gpt-4"},
            changed_by=sample_employee.id
        )
        config_service.record_change(
            config_key="other_settings",
            old_value={},
            new_value={"key": "value"},
            changed_by=sample_employee.id
        )
        db_session.commit()

        llm_history = config_service.get_history("llm_settings")
        other_history = config_service.get_history("other_settings")

        assert len(llm_history) == 1
        assert len(other_history) == 1
        assert llm_history[0].version == 1
        assert other_history[0].version == 1
