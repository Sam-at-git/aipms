"""
系统配置种子数据 — 初始化各分组默认配置项
"""
from sqlalchemy.orm import Session
from app.system.models.config import SysConfig


SEED_CONFIGS = [
    # ========== Security Group ==========
    {
        "group": "security", "key": "security.password_min_length",
        "value": "6", "value_type": "number",
        "name": "密码最小长度", "description": "用户密码最少字符数",
        "is_system": True,
    },
    {
        "group": "security", "key": "security.password_require_mixed",
        "value": "false", "value_type": "boolean",
        "name": "要求混合字符", "description": "是否要求密码包含字母和数字",
        "is_system": True,
    },
    {
        "group": "security", "key": "security.login_max_failures",
        "value": "5", "value_type": "number",
        "name": "登录失败锁定阈值", "description": "连续登录失败次数达到此值后锁定账户",
        "is_system": True,
    },
    {
        "group": "security", "key": "security.login_lockout_minutes",
        "value": "30", "value_type": "number",
        "name": "锁定时长(分钟)", "description": "账户被锁定后的持续时间",
        "is_system": True,
    },
    {
        "group": "security", "key": "security.token_expire_minutes",
        "value": "480", "value_type": "number",
        "name": "Token过期时间(分钟)", "description": "JWT Token的有效期，默认8小时",
        "is_system": True,
    },
    {
        "group": "security", "key": "security.session_timeout_minutes",
        "value": "60", "value_type": "number",
        "name": "会话超时(分钟)", "description": "前端无操作超过此时间自动退出",
        "is_system": True,
    },
    {
        "group": "security", "key": "security.max_concurrent_sessions",
        "value": "3", "value_type": "number",
        "name": "最大并发会话数", "description": "同一账户允许同时在线的会话数量",
        "is_system": True,
    },
    {
        "group": "security", "key": "security.audit_retention_days",
        "value": "90", "value_type": "number",
        "name": "审计日志保留天数", "description": "审计日志自动清理的保留天数",
        "is_system": True,
    },
]


def seed_config_data(db: Session) -> dict:
    """Seed system config defaults. Idempotent — skips existing keys.

    Returns dict with count of created items.
    """
    stats = {"configs": 0}

    for cfg in SEED_CONFIGS:
        existing = db.query(SysConfig).filter(SysConfig.key == cfg["key"]).first()
        if not existing:
            db.add(SysConfig(**cfg))
            stats["configs"] += 1

    if stats["configs"] > 0:
        db.commit()
    return stats
