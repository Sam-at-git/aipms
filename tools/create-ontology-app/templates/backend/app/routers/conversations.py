"""
会话历史路由
管理聊天消息的查询和搜索
"""
import csv
import io
from datetime import date
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.hotel.models.ontology import Employee
from app.services.conversation_service import ConversationService, ConversationMessage
from app.security.auth import get_current_user, require_sysadmin


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
    result_data: Optional[dict] = None  # query_result, context from AI response

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
            context=context,
            result_data=msg.result_data,
        )


class MessagesListResponse(BaseModel):
    messages: List[ConversationMessageResponse]
    has_more: bool
    oldest_timestamp: Optional[str] = None
    active_date: Optional[str] = None


class SearchResultsResponse(BaseModel):
    messages: List[ConversationMessageResponse]
    total: int


class AvailableDatesResponse(BaseModel):
    dates: List[str]


# ============== 路由 ==============

@router.get("/last-active", response_model=MessagesListResponse)
def get_last_active_conversation(
    current_user: Employee = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service)
):
    """
    获取用户最后一次活跃对话的所有消息

    登录后首次调用，加载上次聊天记录。无记录时返回空列表。
    """
    messages, date_str = service.get_last_active_conversation(
        user_id=current_user.id
    )

    oldest_timestamp = None
    if messages:
        oldest_timestamp = messages[0].timestamp

    return MessagesListResponse(
        messages=[ConversationMessageResponse.from_model(m) for m in messages],
        has_more=False,
        oldest_timestamp=oldest_timestamp,
        active_date=date_str
    )


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


# ============== 管理员端点 ==============

class AdminUserInfo(BaseModel):
    user_id: int


class AdminUsersResponse(BaseModel):
    users: List[AdminUserInfo]


@router.get("/admin/users", response_model=AdminUsersResponse)
def admin_get_users_with_conversations(
    current_user: Employee = Depends(require_sysadmin),
    service: ConversationService = Depends(get_conversation_service)
):
    """
    【管理员】获取有聊天记录的用户列表

    仅 sysadmin 可访问
    """
    user_ids = service.get_users_with_conversations()
    return AdminUsersResponse(
        users=[AdminUserInfo(user_id=uid) for uid in user_ids]
    )


@router.get("/admin/user/{user_id}/dates", response_model=AvailableDatesResponse)
def admin_get_user_dates(
    user_id: int,
    current_user: Employee = Depends(require_sysadmin),
    service: ConversationService = Depends(get_conversation_service)
):
    """
    【管理员】获取指定用户的聊天日期列表

    仅 sysadmin 可访问
    """
    dates = service.get_available_dates(user_id=user_id)
    return AvailableDatesResponse(dates=dates)


@router.get("/admin/user/{user_id}/messages", response_model=MessagesListResponse)
def admin_get_user_messages(
    user_id: int,
    date_str: Optional[str] = Query(default=None, description="日期 YYYY-MM-DD"),
    keyword: Optional[str] = Query(default=None, description="搜索关键词"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: Employee = Depends(require_sysadmin),
    service: ConversationService = Depends(get_conversation_service)
):
    """
    【管理员】获取指定用户的聊天记录

    仅 sysadmin 可访问。支持按日期和关键词过滤。
    """
    if keyword:
        messages = service.search_messages(
            user_id=user_id,
            keyword=keyword,
            start_date=date_str,
            end_date=date_str,
            limit=limit
        )
    elif date_str:
        messages = service.get_messages_by_date(user_id=user_id, date_str=date_str)
    else:
        messages, _ = service.get_messages(user_id=user_id, limit=limit)

    oldest_timestamp = None
    if messages:
        oldest_timestamp = messages[0].timestamp

    return MessagesListResponse(
        messages=[ConversationMessageResponse.from_model(m) for m in messages],
        has_more=False,
        oldest_timestamp=oldest_timestamp
    )


@router.get("/admin/statistics")
def admin_get_statistics(
    current_user: Employee = Depends(require_sysadmin),
    service: ConversationService = Depends(get_conversation_service),
) -> Dict[str, Any]:
    """
    【管理员】获取聊天统计概览

    返回总消息数、今日消息数、用户数、热门操作分布
    """
    return service.get_statistics()


@router.get("/admin/export")
def admin_export_messages(
    user_id: int = Query(..., description="用户 ID"),
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD"),
    format: str = Query(default="json", description="导出格式: json 或 csv"),
    current_user: Employee = Depends(require_sysadmin),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    【管理员】导出指定用户的聊天记录

    支持 JSON 和 CSV 格式
    """
    messages = service.export_messages(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "timestamp", "role", "content"])
        for msg in messages:
            writer.writerow([
                msg.get("id", ""),
                msg.get("timestamp", ""),
                msg.get("role", ""),
                msg.get("content", ""),
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=chat_user_{user_id}.csv"},
        )

    return {"user_id": user_id, "count": len(messages), "messages": messages}
