"""
消息通知 API 路由
前缀: /api/system/messages, /api/system/templates, /api/system/announcements
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.hotel.models.ontology import Employee
from app.security.auth import get_current_user, require_manager
from app.system.schemas import (
    MessageSend, MessageResponse, InboxResponse,
    TemplateCreate, TemplateUpdate, TemplateResponse,
    AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse,
    AnnouncementActiveResponse,
)
from app.system.services.message_service import MessageService

msg_router = APIRouter(prefix="/system/messages", tags=["消息通知"])
tpl_router = APIRouter(prefix="/system/templates", tags=["消息模板"])
ann_router = APIRouter(prefix="/system/announcements", tags=["系统公告"])


# =============== Messages ===============

@msg_router.get("/inbox", response_model=InboxResponse)
def get_inbox(
    is_read: Optional[bool] = None,
    msg_type: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取收件箱"""
    service = MessageService(db)
    messages, total = service.get_inbox(
        user_id=current_user.id, is_read=is_read, msg_type=msg_type,
        limit=limit, offset=offset,
    )
    unread = service.get_unread_count(current_user.id)
    return InboxResponse(
        messages=[MessageResponse.model_validate(m) for m in messages],
        total=total, unread_count=unread,
    )


@msg_router.get("/unread-count")
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取未读消息数"""
    service = MessageService(db)
    return {"count": service.get_unread_count(current_user.id)}


@msg_router.post("/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def send_message(
    data: MessageSend,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """发送站内消息（需要经理权限）"""
    service = MessageService(db)
    msg = service.send_message(
        recipient_id=data.recipient_id, title=data.title, content=data.content,
        msg_type=data.msg_type, sender_id=current_user.id,
        related_entity_type=data.related_entity_type,
        related_entity_id=data.related_entity_id,
    )
    return MessageResponse.model_validate(msg)


@msg_router.put("/{message_id}/read")
def mark_message_read(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """标记消息已读"""
    service = MessageService(db)
    ok = service.mark_read(message_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="消息不存在")
    return {"success": True}


@msg_router.put("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """标记所有消息已读"""
    service = MessageService(db)
    count = service.mark_all_read(current_user.id)
    return {"updated": count}


# =============== Templates ===============

@tpl_router.get("", response_model=List[TemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """获取消息模板列表"""
    service = MessageService(db)
    return service.get_templates()


@tpl_router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """创建消息模板"""
    service = MessageService(db)
    try:
        return service.create_template(
            code=data.code, name=data.name, channel=data.channel,
            subject_template=data.subject_template,
            content_template=data.content_template,
            variables=data.variables,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@tpl_router.put("/{tpl_id}", response_model=TemplateResponse)
def update_template(
    tpl_id: int,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """更新消息模板"""
    service = MessageService(db)
    try:
        return service.update_template(tpl_id, **data.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@tpl_router.delete("/{tpl_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    tpl_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """删除消息模板"""
    service = MessageService(db)
    try:
        service.delete_template(tpl_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============== Announcements ===============

@ann_router.get("", response_model=List[AnnouncementResponse])
def list_announcements(
    ann_status: Optional[str] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """获取公告列表（管理视角）"""
    service = MessageService(db)
    return service.get_announcements(status=ann_status)


@ann_router.get("/active", response_model=List[AnnouncementActiveResponse])
def get_active_announcements(
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """获取当前有效公告（用户视角）"""
    service = MessageService(db)
    return service.get_active_announcements(current_user.id)


@ann_router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
def create_announcement(
    data: AnnouncementCreate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """创建公告"""
    service = MessageService(db)
    return service.create_announcement(
        title=data.title, content=data.content, publisher_id=current_user.id,
        status=data.status, is_pinned=data.is_pinned,
    )


@ann_router.put("/{ann_id}", response_model=AnnouncementResponse)
def update_announcement(
    ann_id: int,
    data: AnnouncementUpdate,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """更新公告"""
    service = MessageService(db)
    ann = service.get_announcement_by_id(ann_id)
    if not ann:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="公告不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(ann, key, value)
    db.commit()
    db.refresh(ann)
    return ann


@ann_router.put("/{ann_id}/publish", response_model=AnnouncementResponse)
def publish_announcement(
    ann_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """发布公告"""
    service = MessageService(db)
    try:
        return service.publish_announcement(ann_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@ann_router.put("/{ann_id}/archive", response_model=AnnouncementResponse)
def archive_announcement(
    ann_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(require_manager),
):
    """归档公告"""
    service = MessageService(db)
    try:
        return service.archive_announcement(ann_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@ann_router.put("/{ann_id}/read")
def mark_announcement_read(
    ann_id: int,
    db: Session = Depends(get_db),
    current_user: Employee = Depends(get_current_user),
):
    """标记公告已读"""
    service = MessageService(db)
    service.mark_announcement_read(ann_id, current_user.id)
    return {"success": True}
