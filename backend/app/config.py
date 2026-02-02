"""
应用配置
从环境变量读取配置，支持 OpenAI 兼容 API
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用设置"""

    # 应用基础配置
    APP_NAME: str = "AIPMS"
    DEBUG: bool = False

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./aipms.db"

    # JWT 配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # LLM 配置 (OpenAI 兼容 API)
    OPENAI_API_KEY: Optional[str] = os.environ.get("OPENAI_API_KEY")
    OPENAI_BASE_URL: str = os.environ.get(
        "OPENAI_BASE_URL",
        "https://api.deepseek.com"
    )
    LLM_MODEL: str = os.environ.get("LLM_MODEL", "deepseek-chat")
    LLM_TEMPERATURE: float = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
    LLM_MAX_TOKENS: int = int(os.environ.get("LLM_MAX_TOKENS", "1000"))

    # LLM 功能开关
    ENABLE_LLM: bool = os.environ.get("ENABLE_LLM", "true").lower() == "true"

    class Config:
        env_file = ".env"
        case_sensitive = True


# 全局设置实例
settings = Settings()
