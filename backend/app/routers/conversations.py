"""
会话历史路由
管理聊天消息的查询和搜索
"""
from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from app.models.ontology import Employee
from app.services.conversation_service import ConversationService, ConversationMessage
from app.security.auth import get_current_user


router = APIRouter(prefix="/conversations", tags=["会话历史"])

# 全局服务实例
_conversation_service: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    """获取会话服务实例"""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service


# ============== 响应模型 ==============

class MessageContextResponse(BaseModel):
    topic_id: Optional[str] = None
    is_followup: bool = False
    parent_message_id: Optional[str] = None


class ConversationMessageResponse(BaseModel):
    id: str
    timestamp: str
    role: str
    content: str
    actions: Optional[List[dict]] = None
    context: Optional[MessageContextResponse] = None

    @classmethod
    def from_model(cls, msg: ConversationMessage) -> 'ConversationMessageResponse':
        context = None
        if msg.context:
            context = MessageContextResponse(
                topic_id=msg.context.topic_id,
                is_followup=msg.context.is_followup,
                parent_message_id=msg.context.parent_message_id
            )
        return cls(
            id=msg.id,
            timestamp=msg.timestamp,
            role=msg.role,
            content=msg.content,
            actions=msg.actions,
            context=context
        )


class MessagesListResponse(BaseModel):
    messages: List[ConversationMessageResponse]
    has_more: bool
    oldest_timestamp: Optional[str] = None


class SearchResultsResponse(BaseModel):
    messages: List[ConversationMessageResponse]
    total: int


class AvailableDatesResponse(BaseModel):
    dates: List[str]


# ============== 路由 ==============

@router.get("/messages", response_model=MessagesListResponse)
def get_messages(
    limit: int = Query(default=50, ge=1, le=200),
    before: Optional[str] = Query(default=None, description="获取此时间戳之前的消息"),
    current_user: Employee = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service)
):
    """
    获取最近的聊天消息（支持分页）

    - **limit**: 返回数量限制（默认 50，最大 200）
    - **before**: 可选，获取此时间戳之前的消息（用于向上滚动加载更多）
    """
    messages, has_more = service.get_messages(
        user_id=current_user.id,
        limit=limit,
        before=before
    )

    oldest_timestamp = None
    if messages:
        oldest_timestamp = messages[0].timestamp

    return MessagesListResponse(
        messages=[ConversationMessageResponse.from_model(m) for m in messages],
        has_more=has_more,
        oldest_timestamp=oldest_timestamp
    )


@router.get("/messages/date/{date_str}", response_model=List[ConversationMessageResponse])
def get_messages_by_date(
    date_str: str,
    current_user: Employee = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service)
):
    """
    获取指定日期的所有消息

    - **date_str**: 日期字符串，格式为 YYYY-MM-DD
    """
    # 验证日期格式
    try:
        date.fromisoformat(date_str)
    except ValueError:
        return []

    messages = service.get_messages_by_date(
        user_id=current_user.id,
        date_str=date_str
    )

    return [ConversationMessageResponse.from_model(m) for m in messages]


@router.get("/search", response_model=SearchResultsResponse)
def search_messages(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: Employee = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service)
):
    """
    搜索聊天历史

    - **keyword**: 搜索关键词
    - **start_date**: 可选，开始日期（格式 YYYY-MM-DD）
    - **end_date**: 可选，结束日期（格式 YYYY-MM-DD）
    - **limit**: 返回数量限制
    """
    messages = service.search_messages(
        user_id=current_user.id,
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )

    return SearchResultsResponse(
        messages=[ConversationMessageResponse.from_model(m) for m in messages],
        total=len(messages)
    )


@router.get("/dates", response_model=AvailableDatesResponse)
def get_available_dates(
    current_user: Employee = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service)
):
    """
    获取有历史记录的日期列表

    返回按日期倒序排列的日期字符串列表
    """
    dates = service.get_available_dates(user_id=current_user.id)
    return AvailableDatesResponse(dates=dates)
