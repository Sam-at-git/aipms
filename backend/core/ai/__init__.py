"""
core/ai/ - AI 抽象层

提供统一的 LLM 调用接口、提示词构建和人类在环确认策略。
"""
from core.ai.llm_client import LLMClient, OpenAICompatibleClient
from core.ai.prompt_builder import PromptBuilder
from core.ai.hitl import HITLStrategy, ConfirmAlwaysStrategy, ConfirmByRiskStrategy, ConfirmByPolicyStrategy

__all__ = [
    "LLMClient",
    "OpenAICompatibleClient",
    "PromptBuilder",
    "HITLStrategy",
    "ConfirmAlwaysStrategy",
    "ConfirmByRiskStrategy",
    "ConfirmByPolicyStrategy",
]
