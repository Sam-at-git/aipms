"""
系统配置 Service — 配置 CRUD + 内存缓存 + 敏感值脱敏
"""
import json
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.system.models.config import SysConfig

# In-memory config cache (loaded at startup, updated on write)
_config_cache: Dict[str, SysConfig] = {}
_cache_loaded = False


def _is_sensitive_key(key: str) -> bool:
    """Check if a config key contains sensitive data"""
    sensitive_patterns = ["api_key", "secret", "password", "token", "credential"]
    key_lower = key.lower()
    return any(p in key_lower for p in sensitive_patterns)


def _mask_value(value: str) -> str:
    """Mask sensitive config values for API display"""
    if not value or len(value) <= 4:
        return "****"
    return value[:2] + "****" + value[-2:]


class ConfigService:
    def __init__(self, db: Session):
        self.db = db

    def _load_cache(self):
        """Load all configs into memory cache"""
        global _config_cache, _cache_loaded
        configs = self.db.query(SysConfig).all()
        _config_cache = {c.key: c for c in configs}
        _cache_loaded = True

    def _ensure_cache(self):
        if not _cache_loaded:
            self._load_cache()

    # ---- Read operations ----

    def get_all(self, group: Optional[str] = None) -> List[SysConfig]:
        query = self.db.query(SysConfig)
        if group:
            query = query.filter(SysConfig.group == group)
        return query.order_by(SysConfig.group, SysConfig.key).all()

    def get_by_key(self, key: str) -> Optional[SysConfig]:
        self._ensure_cache()
        if key in _config_cache:
            return _config_cache[key]
        # Fallback to DB
        config = self.db.query(SysConfig).filter(SysConfig.key == key).first()
        if config:
            _config_cache[key] = config
        return config

    def get_value(self, key: str, default: Any = None) -> Any:
        """Get typed config value"""
        config = self.get_by_key(key)
        if not config:
            return default
        return self._cast_value(config.value, config.value_type)

    def get_groups(self) -> List[str]:
        """Get distinct config groups"""
        rows = self.db.query(SysConfig.group).distinct().order_by(SysConfig.group).all()
        return [r[0] for r in rows]

    def get_public_configs(self) -> List[SysConfig]:
        """Get configs accessible without login"""
        return self.db.query(SysConfig).filter(SysConfig.is_public == True).all()

    # ---- Write operations ----

    def create(
        self,
        key: str,
        value: str,
        name: str,
        group: str = "system",
        value_type: str = "string",
        description: str = "",
        is_public: bool = False,
        is_system: bool = False,
        updated_by: Optional[int] = None,
    ) -> SysConfig:
        existing = self.db.query(SysConfig).filter(SysConfig.key == key).first()
        if existing:
            raise ValueError(f"配置键 '{key}' 已存在")

        config = SysConfig(
            group=group, key=key, value=value, value_type=value_type,
            name=name, description=description,
            is_public=is_public, is_system=is_system,
            updated_by=updated_by,
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        _config_cache[key] = config
        return config

    def update(self, key: str, value: str, updated_by: Optional[int] = None) -> SysConfig:
        config = self.db.query(SysConfig).filter(SysConfig.key == key).first()
        if not config:
            raise ValueError(f"配置键 '{key}' 不存在")

        config.value = value
        if updated_by:
            config.updated_by = updated_by
        self.db.commit()
        self.db.refresh(config)
        _config_cache[key] = config
        return config

    def update_by_id(self, config_id: int, **kwargs) -> SysConfig:
        config = self.db.query(SysConfig).filter(SysConfig.id == config_id).first()
        if not config:
            raise ValueError("配置项不存在")

        for k, v in kwargs.items():
            if hasattr(config, k):
                setattr(config, k, v)

        self.db.commit()
        self.db.refresh(config)
        _config_cache[config.key] = config
        return config

    def delete(self, config_id: int) -> bool:
        config = self.db.query(SysConfig).filter(SysConfig.id == config_id).first()
        if not config:
            raise ValueError("配置项不存在")
        if config.is_system:
            raise ValueError(f"系统内置配置 '{config.key}' 不可删除")

        _config_cache.pop(config.key, None)
        self.db.delete(config)
        self.db.commit()
        return True

    # ---- Helpers ----

    def to_api_dict(self, config: SysConfig, mask_sensitive: bool = True) -> Dict[str, Any]:
        """Convert config to API response dict with optional value masking"""
        value = config.value
        if mask_sensitive and _is_sensitive_key(config.key):
            value = _mask_value(value)

        return {
            "id": config.id,
            "group": config.group,
            "key": config.key,
            "value": value,
            "value_type": config.value_type,
            "name": config.name,
            "description": config.description,
            "is_public": config.is_public,
            "is_system": config.is_system,
            "created_at": config.created_at.isoformat() if config.created_at else None,
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
            "updated_by": config.updated_by,
        }

    @staticmethod
    def _cast_value(value: str, value_type: str) -> Any:
        """Cast string value to its declared type"""
        if value_type == "number":
            try:
                return int(value) if '.' not in value else float(value)
            except (ValueError, TypeError):
                return value
        elif value_type == "boolean":
            return value.lower() in ("true", "1", "yes")
        elif value_type == "json":
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value

    @staticmethod
    def reset_cache():
        """Reset the config cache (for testing)"""
        global _config_cache, _cache_loaded
        _config_cache = {}
        _cache_loaded = False
