"""
配置版本管理服务
记录配置变更历史，支持查看和回滚
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
import json
import logging

from app.models.snapshots import ConfigHistory

logger = logging.getLogger(__name__)


class ConfigHistoryService:
    """配置版本管理服务"""

    def __init__(self, db: Session):
        self.db = db

    def record_change(
        self,
        config_key: str,
        old_value: Dict[str, Any],
        new_value: Dict[str, Any],
        changed_by: int,
        change_reason: str = None
    ) -> ConfigHistory:
        """
        记录配置变更

        Args:
            config_key: 配置项标识（如 llm_settings）
            old_value: 变更前的值
            new_value: 变更后的值
            changed_by: 变更人ID
            change_reason: 变更原因

        Returns:
            创建的配置历史记录
        """
        # 获取当前最新版本号
        latest = self.db.query(func.max(ConfigHistory.version)).filter(
            ConfigHistory.config_key == config_key
        ).scalar()
        new_version = (latest or 0) + 1

        # 将之前的版本标记为非当前
        self.db.query(ConfigHistory).filter(
            ConfigHistory.config_key == config_key,
            ConfigHistory.is_current == True
        ).update({"is_current": False})

        # 创建新的历史记录
        history = ConfigHistory(
            config_key=config_key,
            version=new_version,
            old_value=json.dumps(old_value, default=str, ensure_ascii=False),
            new_value=json.dumps(new_value, default=str, ensure_ascii=False),
            changed_by=changed_by,
            changed_at=datetime.now(),
            change_reason=change_reason,
            is_current=True
        )
        self.db.add(history)
        self.db.flush()

        logger.info(f"Recorded config change: {config_key} v{new_version}")
        return history

    def get_history(
        self,
        config_key: str,
        limit: int = 20
    ) -> List[ConfigHistory]:
        """
        获取配置变更历史

        Args:
            config_key: 配置项标识
            limit: 返回数量限制

        Returns:
            配置历史记录列表
        """
        return self.db.query(ConfigHistory).filter(
            ConfigHistory.config_key == config_key
        ).order_by(ConfigHistory.version.desc()).limit(limit).all()

    def get_version(self, config_key: str, version: int) -> Optional[ConfigHistory]:
        """
        获取特定版本的配置

        Args:
            config_key: 配置项标识
            version: 版本号

        Returns:
            配置历史记录
        """
        return self.db.query(ConfigHistory).filter(
            ConfigHistory.config_key == config_key,
            ConfigHistory.version == version
        ).first()

    def get_current(self, config_key: str) -> Optional[ConfigHistory]:
        """
        获取当前版本的配置

        Args:
            config_key: 配置项标识

        Returns:
            当前配置历史记录
        """
        return self.db.query(ConfigHistory).filter(
            ConfigHistory.config_key == config_key,
            ConfigHistory.is_current == True
        ).first()

    def rollback_to_version(
        self,
        config_key: str,
        version: int,
        changed_by: int
    ) -> ConfigHistory:
        """
        回滚到指定版本

        Args:
            config_key: 配置项标识
            version: 要回滚到的版本号
            changed_by: 操作人ID

        Returns:
            新创建的配置历史记录
        """
        target = self.get_version(config_key, version)
        if not target:
            raise ValueError(f"版本 {version} 不存在")

        current = self.get_current(config_key)
        if not current:
            raise ValueError(f"配置 {config_key} 不存在")

        # 目标版本的 new_value 作为回滚后的值
        target_value = json.loads(target.new_value)
        current_value = json.loads(current.new_value)

        return self.record_change(
            config_key=config_key,
            old_value=current_value,
            new_value=target_value,
            changed_by=changed_by,
            change_reason=f"回滚到版本 {version}"
        )

    def compare_versions(
        self,
        config_key: str,
        version1: int,
        version2: int
    ) -> Dict[str, Any]:
        """
        比较两个版本的差异

        Args:
            config_key: 配置项标识
            version1: 版本1
            version2: 版本2

        Returns:
            差异信息
        """
        v1 = self.get_version(config_key, version1)
        v2 = self.get_version(config_key, version2)

        if not v1 or not v2:
            raise ValueError("指定的版本不存在")

        v1_value = json.loads(v1.new_value)
        v2_value = json.loads(v2.new_value)

        # 计算差异
        added = {k: v2_value[k] for k in v2_value if k not in v1_value}
        removed = {k: v1_value[k] for k in v1_value if k not in v2_value}
        changed = {
            k: {"old": v1_value[k], "new": v2_value[k]}
            for k in v1_value
            if k in v2_value and v1_value[k] != v2_value[k]
        }

        return {
            "version1": version1,
            "version2": version2,
            "added": added,
            "removed": removed,
            "changed": changed
        }
