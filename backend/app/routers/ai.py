"""
AI 对话路由
实现自然语言交互和 OODA 循环
"""
import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ontology import Employee
from app.models.schemas import AIAction, ActionConfirmation
from app.services.ai_service import AIService
from app.services.conversation_service import ConversationService
from app.security.auth import get_current_user


router = APIRouter(prefix="/ai", tags=["AI对话"])

# 全局会话服务实例
_conversation_service: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    """获取会话服务实例"""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service


# ============== 请求/响应模型 ==============

class AIMessageWithContext(BaseModel):
    """带上下文的 AI 消息请求"""
    content: str
    topic_id: Optional[str] = None
    follow_up_context: Optional[dict] = None  # 追问上下文
    language: Optional[str] = None  # 语言偏好: "zh" | "en" | None(自动检测)


class AIResponseWithHistory(BaseModel):
    """带历史信息的 AI 响应"""
    message: str
    suggested_actions: List[AIAction] = []
    context: dict = {}
    message_id: str
    topic_id: Optional[str] = None
    requires_confirmation: Optional[bool] = None
    candidates: Optional[List[dict]] = None
    follow_up: Optional[dict] = None
    query_result: Optional[dict] = None


# ============== 路由 ==============

@router.post("/chat", response_model=AIResponseWithHistory)
def chat(
    message: AIMessageWithContext,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
    conv_service: ConversationService = Depends(get_conversation_service)
):
    """
    AI 对话接口
    接收自然语言输入，返回结构化响应和建议动作

    - **content**: 用户消息内容
    - **topic_id**: 可选，当前话题 ID（用于上下文追踪）
    """
    # 获取历史上下文消息
    conversation_history = []
    follow_up_context = None

    if message.topic_id:
        # 获取该话题的历史消息
        context_messages = conv_service.get_context_messages(
            user_id=current_user.id,
            topic_id=message.topic_id,
            max_rounds=3
        )
        conversation_history = [
            {'role': m.role, 'content': m.content}
            for m in context_messages
        ]

        # 从最近的助手消息中提取追问上下文
        for msg in reversed(context_messages):
            if msg.role == 'assistant' and msg.context:
                context_data = msg.context
                if isinstance(context_data, dict):
                    # 检查是否有 follow_up 信息
                    if 'follow_up' in context_data or 'action_type' in context_data:
                        follow_up_context = {
                            'action_type': context_data.get('action_type'),
                            'collected_fields': context_data.get('collected_fields', {})
                        }
                        break
    else:
        # 获取最近的历史消息
        context_messages = conv_service.get_context_messages(
            user_id=current_user.id,
            max_rounds=3
        )
        conversation_history = [
            {'role': m.role, 'content': m.content}
            for m in context_messages
        ]

    # 如果前端传了 follow_up_context，优先使用
    if message.follow_up_context:
        follow_up_context = message.follow_up_context

    # 处理消息
    service = AIService(db)
    result = service.process_message(
        message=message.content,
        user=current_user,
        conversation_history=conversation_history,
        topic_id=message.topic_id,
        follow_up_context=follow_up_context,
        language=message.language
    )

    # 确定 topic_id
    topic_id = result.get('topic_id') or message.topic_id
    if not topic_id:
        # 生成新的 topic_id
        topic_id = conv_service.generate_topic_id()

    # 保存消息对
    user_msg, assistant_msg = conv_service.save_message_pair(
        user_id=current_user.id,
        user_content=message.content,
        assistant_content=result.get('message', ''),
        actions=[a.dict() if hasattr(a, 'dict') else a for a in result.get('suggested_actions', [])],
        topic_id=topic_id,
        is_followup=bool(message.topic_id)
    )

    # 构建响应
    return AIResponseWithHistory(
        message=result.get('message', ''),
        suggested_actions=result.get('suggested_actions', []),
        context=result.get('context', {}),
        message_id=assistant_msg.id,
        topic_id=topic_id,
        requires_confirmation=result.get('requires_confirmation'),
        candidates=result.get('candidates'),
        follow_up=result.get('follow_up'),
        query_result=result.get('query_result')
    )


@router.post("/execute")
def execute_action(
    confirmation: ActionConfirmation,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
    conv_service: ConversationService = Depends(get_conversation_service)
):
    """
    执行 AI 建议的动作
    需要人类确认（Human-in-the-loop）
    """
    if not confirmation.confirmed:
        # 保存取消操作的消息
        conv_service.save_message_pair(
            user_id=current_user.id,
            user_content="[取消操作]",
            assistant_content="操作已取消。"
        )
        return {"message": "操作已取消"}

    service = AIService(db)

    try:
        result = service.execute_action(confirmation.action.model_dump(), current_user)

        # 保存执行结果
        action_desc = confirmation.action.description or confirmation.action.action_type
        conv_service.save_message_pair(
            user_id=current_user.id,
            user_content=f"[确认执行: {action_desc}]",
            assistant_content=result.get('message', '操作已完成')
        )

        return result
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Error executing action: {e}\n{traceback.format_exc()}")

        # 返回错误信息给前端
        return {
            "success": False,
            "message": f"操作执行失败: {str(e)}",
            "error": str(e)
        }
