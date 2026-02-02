"""
系统设置路由
LLM 配置和系统参数管理
"""
import os
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee
from app.models.schemas import LLMSettings, LLMTestRequest
from app.services.llm_service import LLMService
from app.security.auth import get_current_user, require_manager
from app.config import settings

router = APIRouter(prefix="/settings", tags=["系统设置"])


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
        has_env_key=bool(os.environ.get("OPENAI_API_KEY"))  # 标识是否有环境变量 key
    )


@router.post("/llm")
def update_llm_settings(
    data: LLMSettings,
    current_user: Employee = Depends(require_manager)
):
    """更新 LLM 设置（仅经理）"""
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

    # 更新 settings 实例
    settings.OPENAI_API_KEY = data.openai_api_key if data.openai_api_key != "***" else settings.OPENAI_API_KEY
    settings.OPENAI_BASE_URL = data.openai_base_url
    settings.LLM_MODEL = data.llm_model
    settings.LLM_TEMPERATURE = data.llm_temperature
    settings.LLM_MAX_TOKENS = data.llm_max_tokens
    settings.ENABLE_LLM = data.enable_llm

    # 更新系统提示词
    if data.system_prompt:
        LLMService.SYSTEM_PROMPT = data.system_prompt

    return {"message": "LLM 设置已更新", "settings": get_llm_settings(current_user)}


@router.post("/llm/test")
def test_llm_connection(
    data: LLMTestRequest,
    current_user: Employee = Depends(require_manager)
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
