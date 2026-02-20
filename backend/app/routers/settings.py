"""
系统设置路由
LLM 配置和系统参数管理
支持配置版本管理
"""
import os
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from app.database import get_db
from app.models.ontology import Employee
from app.models.schemas import LLMSettings, LLMTestRequest
from app.services.llm_service import LLMService
from app.services.config_history_service import ConfigHistoryService
from app.security.auth import get_current_user, require_sysadmin, require_permission
from app.security.permissions import SETTINGS_READ, SETTINGS_WRITE
from app.config import settings

router = APIRouter(prefix="/settings", tags=["系统设置"])


class ConfigHistoryResponse(BaseModel):
    """配置历史响应模型"""
    id: int
    config_key: str
    version: int
    changed_by: int
    changed_at: str
    change_reason: Optional[str]
    is_current: bool
    model_config = ConfigDict(from_attributes=True)


@router.get("/llm", response_model=LLMSettings)
def get_llm_settings(
    current_user: Employee = Depends(get_current_user)
):
    """获取当前 LLM 设置（隐藏敏感信息）"""
    return LLMSettings(
        openai_api_key=None,  # 不返回实际 key，使用环境变量
        openai_base_url=settings.OPENAI_BASE_URL,
        llm_model=settings.LLM_MODEL,
        llm_temperature=settings.LLM_TEMPERATURE,
        llm_max_tokens=settings.LLM_MAX_TOKENS,
        enable_llm=settings.ENABLE_LLM,
        system_prompt=LLMService.SYSTEM_PROMPT,
        has_env_key=bool(os.environ.get("OPENAI_API_KEY")),  # 标识是否有环境变量 key
        embedding_enabled=settings.EMBEDDING_ENABLED,
        embedding_base_url=settings.EMBEDDING_BASE_URL,
        embedding_model=settings.EMBEDDING_MODEL
    )


@router.post("/llm")
def update_llm_settings(
    data: LLMSettings,
    reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(SETTINGS_WRITE))
):
    """更新 LLM 设置（仅经理），自动记录版本历史"""
    # 记录变更前的配置
    old_settings = {
        "openai_base_url": settings.OPENAI_BASE_URL,
        "llm_model": settings.LLM_MODEL,
        "llm_temperature": settings.LLM_TEMPERATURE,
        "llm_max_tokens": settings.LLM_MAX_TOKENS,
        "enable_llm": settings.ENABLE_LLM,
        "system_prompt": LLMService.SYSTEM_PROMPT,
        "embedding_enabled": settings.EMBEDDING_ENABLED,
        "embedding_base_url": settings.EMBEDDING_BASE_URL,
        "embedding_model": settings.EMBEDDING_MODEL
    }

    # 更新环境变量
    if data.openai_api_key and data.openai_api_key != "***":
        os.environ["OPENAI_API_KEY"] = data.openai_api_key

    if data.openai_base_url:
        os.environ["OPENAI_BASE_URL"] = data.openai_base_url

    if data.llm_model:
        os.environ["LLM_MODEL"] = data.llm_model

    if data.llm_temperature is not None:
        os.environ["LLM_TEMPERATURE"] = str(data.llm_temperature)

    if data.llm_max_tokens is not None:
        os.environ["LLM_MAX_TOKENS"] = str(data.llm_max_tokens)

    os.environ["ENABLE_LLM"] = "true" if data.enable_llm else "false"

    # 更新 embedding 设置
    os.environ["EMBEDDING_ENABLED"] = "true" if data.embedding_enabled else "false"
    os.environ["EMBEDDING_BASE_URL"] = data.embedding_base_url
    os.environ["EMBEDDING_MODEL"] = data.embedding_model

    # 更新 settings 实例
    settings.OPENAI_API_KEY = data.openai_api_key if data.openai_api_key != "***" else settings.OPENAI_API_KEY
    settings.OPENAI_BASE_URL = data.openai_base_url
    settings.LLM_MODEL = data.llm_model
    settings.LLM_TEMPERATURE = data.llm_temperature
    settings.LLM_MAX_TOKENS = data.llm_max_tokens
    settings.ENABLE_LLM = data.enable_llm
    settings.EMBEDDING_ENABLED = data.embedding_enabled
    settings.EMBEDDING_BASE_URL = data.embedding_base_url
    settings.EMBEDDING_MODEL = data.embedding_model

    # 更新系统提示词
    if data.system_prompt:
        LLMService.SYSTEM_PROMPT = data.system_prompt

    # 重置 embedding 服务以应用新配置
    from core.ai import reset_embedding_service
    reset_embedding_service()

    # 记录变更后的配置
    new_settings = {
        "openai_base_url": settings.OPENAI_BASE_URL,
        "llm_model": settings.LLM_MODEL,
        "llm_temperature": settings.LLM_TEMPERATURE,
        "llm_max_tokens": settings.LLM_MAX_TOKENS,
        "enable_llm": settings.ENABLE_LLM,
        "system_prompt": LLMService.SYSTEM_PROMPT,
        "embedding_enabled": settings.EMBEDDING_ENABLED,
        "embedding_base_url": settings.EMBEDDING_BASE_URL,
        "embedding_model": settings.EMBEDDING_MODEL
    }

    # 记录配置历史
    config_history_service = ConfigHistoryService(db)
    config_history_service.record_change(
        config_key="llm_settings",
        old_value=old_settings,
        new_value=new_settings,
        changed_by=current_user.id,
        change_reason=reason
    )
    db.commit()

    return {"message": "LLM 设置已更新", "settings": get_llm_settings(current_user)}


@router.post("/llm/test")
def test_llm_connection(
    data: LLMTestRequest,
    current_user: Employee = Depends(require_permission(SETTINGS_WRITE))
):
    """测试 LLM 连接"""
    try:
        # 创建临时 LLM 服务进行测试
        from openai import OpenAI

        # 如果没有提供 api_key，使用环境变量
        api_key = data.api_key
        if not api_key:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                return {
                    "success": False,
                    "message": "未配置 API Key，请在界面输入或设置环境变量 OPENAI_API_KEY"
                }

        client = OpenAI(
            api_key=api_key,
            base_url=data.base_url,
            timeout=10.0
        )

        response = client.chat.completions.create(
            model=data.model,
            messages=[
                {"role": "system", "content": "你是一个酒店管理助手。"},
                {"role": "user", "content": "你好，请用一句话回复确认连接成功。"}
            ],
            max_tokens=50
        )

        return {
            "success": True,
            "message": "连接成功",
            "response": response.choices[0].message.content
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)}"
        }


@router.get("/llm/providers")
def get_llm_providers(
    current_user: Employee = Depends(get_current_user)
):
    """获取常用的 LLM 服务商配置"""
    return {
        "providers": [
            {
                "name": "DeepSeek",
                "base_url": "https://api.deepseek.com",
                "models": ["deepseek-chat", "deepseek-coder"],
                "default_model": "deepseek-chat"
            },
            {
                "name": "OpenAI",
                "base_url": "https://api.openai.com/v1",
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
                "default_model": "gpt-4o-mini"
            },
            {
                "name": "Azure OpenAI",
                "base_url": "https://your-resource.openai.azure.com/openai/deployments/your-deployment",
                "models": ["gpt-4", "gpt-35-turbo"],
                "default_model": "gpt-4"
            },
            {
                "name": "Ollama (本地)",
                "base_url": "http://localhost:11434/v1",
                "models": ["llama2", "mistral", "codellama"],
                "default_model": "llama2"
            }
        ]
    }


class EmbeddingTestRequest(BaseModel):
    """Embedding 连接测试请求"""
    base_url: str
    model: str


@router.post("/embedding/test")
def test_embedding_connection(
    data: EmbeddingTestRequest,
    current_user: Employee = Depends(require_permission(SETTINGS_WRITE))
):
    """测试 Embedding 连接"""
    try:
        from openai import OpenAI

        # Ollama 不需要真实的 API key，但需要一个非空字符串
        api_key = "ollama" if "localhost:11434" in data.base_url or "ollama" in data.base_url.lower() else None

        client = OpenAI(
            api_key=api_key or "dummy",
            base_url=data.base_url,
            timeout=10.0
        )

        # 测试 embedding
        response = client.embeddings.create(
            model=data.model,
            input="测试文本"
        )

        dimension = len(response.data[0].embedding)

        return {
            "success": True,
            "message": f"连接成功！Embedding 维度: {dimension}"
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)}"
        }


@router.get("/llm/history", response_model=List[ConfigHistoryResponse])
def get_llm_settings_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(SETTINGS_WRITE))
):
    """获取 LLM 设置变更历史（仅经理）"""
    config_history_service = ConfigHistoryService(db)
    history = config_history_service.get_history("llm_settings", limit)

    return [
        ConfigHistoryResponse(
            id=h.id,
            config_key=h.config_key,
            version=h.version,
            changed_by=h.changed_by,
            changed_at=h.changed_at.isoformat(),
            change_reason=h.change_reason,
            is_current=h.is_current
        )
        for h in history
    ]


@router.get("/llm/history/{version}")
def get_llm_settings_version(
    version: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(SETTINGS_WRITE))
):
    """获取特定版本的 LLM 设置（仅经理）"""
    import json

    config_history_service = ConfigHistoryService(db)
    history = config_history_service.get_version("llm_settings", version)

    if not history:
        raise HTTPException(status_code=404, detail=f"版本 {version} 不存在")

    return {
        "id": history.id,
        "config_key": history.config_key,
        "version": history.version,
        "old_value": json.loads(history.old_value),
        "new_value": json.loads(history.new_value),
        "changed_by": history.changed_by,
        "changer_name": history.changer.name if history.changer else None,
        "changed_at": history.changed_at.isoformat(),
        "change_reason": history.change_reason,
        "is_current": history.is_current
    }


@router.post("/llm/rollback/{version}")
def rollback_llm_settings(
    version: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_permission(SETTINGS_WRITE))
):
    """回滚到指定版本的 LLM 设置（仅经理）"""
    import json

    config_history_service = ConfigHistoryService(db)

    try:
        # 获取目标版本的配置
        target = config_history_service.get_version("llm_settings", version)
        if not target:
            raise HTTPException(status_code=404, detail=f"版本 {version} 不存在")

        target_value = json.loads(target.new_value)

        # 应用配置
        if target_value.get("openai_base_url"):
            settings.OPENAI_BASE_URL = target_value["openai_base_url"]
            os.environ["OPENAI_BASE_URL"] = target_value["openai_base_url"]

        if target_value.get("llm_model"):
            settings.LLM_MODEL = target_value["llm_model"]
            os.environ["LLM_MODEL"] = target_value["llm_model"]

        if target_value.get("llm_temperature") is not None:
            settings.LLM_TEMPERATURE = target_value["llm_temperature"]
            os.environ["LLM_TEMPERATURE"] = str(target_value["llm_temperature"])

        if target_value.get("llm_max_tokens") is not None:
            settings.LLM_MAX_TOKENS = target_value["llm_max_tokens"]
            os.environ["LLM_MAX_TOKENS"] = str(target_value["llm_max_tokens"])

        if target_value.get("enable_llm") is not None:
            settings.ENABLE_LLM = target_value["enable_llm"]
            os.environ["ENABLE_LLM"] = "true" if target_value["enable_llm"] else "false"

        if target_value.get("system_prompt"):
            LLMService.SYSTEM_PROMPT = target_value["system_prompt"]

        # 记录回滚操作
        config_history_service.rollback_to_version(
            config_key="llm_settings",
            version=version,
            changed_by=current_user.id
        )
        db.commit()

        return {
            "message": f"已回滚到版本 {version}",
            "settings": get_llm_settings(current_user)
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
