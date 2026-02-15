"""
消息通知 Service — 站内消息发送/收件箱/标记已读/公告管理
"""
from datetime import datetime
from string import Template
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.system.models.message import (
    SysMessage, SysMessageTemplate, SysAnnouncement, SysAnnouncementRead,
)


class MessageService:
    def __init__(self, db: Session):
        self.db = db

    # =============== Messages ===============

    def send_message(
        self,
        recipient_id: int,
        title: str,
        content: str,
        msg_type: str = "system",
        sender_id: Optional[int] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[int] = None,
    ) -> SysMessage:
        """发送站内消息"""
        msg = SysMessage(
            sender_id=sender_id,
            recipient_id=recipient_id,
            title=title,
            content=content,
            msg_type=msg_type,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def send_from_template(
        self,
        template_code: str,
        recipient_id: int,
        variables: Optional[Dict[str, str]] = None,
        sender_id: Optional[int] = None,
        related_entity_type: Optional[str] = None,
        related_entity_id: Optional[int] = None,
    ) -> Optional[SysMessage]:
        """使用模板发送消息"""
        tpl = self.db.query(SysMessageTemplate).filter(
            SysMessageTemplate.code == template_code,
            SysMessageTemplate.is_active == True,
        ).first()
        if not tpl:
            return None

        vars_dict = variables or {}
        title = Template(tpl.subject_template).safe_substitute(vars_dict)
        content = Template(tpl.content_template).safe_substitute(vars_dict)

        return self.send_message(
            recipient_id=recipient_id,
            title=title,
            content=content,
            msg_type="business",
            sender_id=sender_id,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )

    def get_inbox(
        self,
        user_id: int,
        is_read: Optional[bool] = None,
        msg_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[SysMessage], int]:
        """获取收件箱消息（分页）"""
        query = self.db.query(SysMessage).filter(SysMessage.recipient_id == user_id)
        if is_read is not None:
            query = query.filter(SysMessage.is_read == is_read)
        if msg_type:
            query = query.filter(SysMessage.msg_type == msg_type)

        total = query.count()
        messages = query.order_by(SysMessage.created_at.desc()).offset(offset).limit(limit).all()
        return messages, total

    def get_unread_count(self, user_id: int) -> int:
        """获取未读消息数"""
        return self.db.query(SysMessage).filter(
            SysMessage.recipient_id == user_id,
            SysMessage.is_read == False,
        ).count()

    def mark_read(self, message_id: int, user_id: int) -> bool:
        """标记消息为已读"""
        msg = self.db.query(SysMessage).filter(
            SysMessage.id == message_id,
            SysMessage.recipient_id == user_id,
        ).first()
        if not msg:
            return False
        msg.is_read = True
        msg.read_at = datetime.utcnow()
        self.db.commit()
        return True

    def mark_all_read(self, user_id: int) -> int:
        """标记所有消息为已读，返回更新数量"""
        count = self.db.query(SysMessage).filter(
            SysMessage.recipient_id == user_id,
            SysMessage.is_read == False,
        ).update({"is_read": True, "read_at": datetime.utcnow()})
        self.db.commit()
        return count

    # =============== Templates ===============

    def get_templates(self) -> List[SysMessageTemplate]:
        return self.db.query(SysMessageTemplate).order_by(SysMessageTemplate.id).all()

    def get_template_by_id(self, tpl_id: int) -> Optional[SysMessageTemplate]:
        return self.db.query(SysMessageTemplate).filter(SysMessageTemplate.id == tpl_id).first()

    def create_template(
        self, code: str, name: str, channel: str = "internal",
        subject_template: str = "", content_template: str = "",
        variables: str = "",
    ) -> SysMessageTemplate:
        existing = self.db.query(SysMessageTemplate).filter(
            SysMessageTemplate.code == code
        ).first()
        if existing:
            raise ValueError(f"模板编码 '{code}' 已存在")

        tpl = SysMessageTemplate(
            code=code, name=name, channel=channel,
            subject_template=subject_template,
            content_template=content_template,
            variables=variables,
        )
        self.db.add(tpl)
        self.db.commit()
        self.db.refresh(tpl)
        return tpl

    def update_template(self, tpl_id: int, **kwargs) -> SysMessageTemplate:
        tpl = self.get_template_by_id(tpl_id)
        if not tpl:
            raise ValueError("模板不存在")
        for key, value in kwargs.items():
            if hasattr(tpl, key):
                setattr(tpl, key, value)
        self.db.commit()
        self.db.refresh(tpl)
        return tpl

    def delete_template(self, tpl_id: int) -> bool:
        tpl = self.get_template_by_id(tpl_id)
        if not tpl:
            raise ValueError("模板不存在")
        self.db.delete(tpl)
        self.db.commit()
        return True

    # =============== Announcements ===============

    def get_announcements(self, status: Optional[str] = None) -> List[SysAnnouncement]:
        query = self.db.query(SysAnnouncement)
        if status:
            query = query.filter(SysAnnouncement.status == status)
        return query.order_by(SysAnnouncement.created_at.desc()).all()

    def get_announcement_by_id(self, ann_id: int) -> Optional[SysAnnouncement]:
        return self.db.query(SysAnnouncement).filter(SysAnnouncement.id == ann_id).first()

    def create_announcement(
        self, title: str, content: str, publisher_id: int,
        status: str = "draft", is_pinned: bool = False,
    ) -> SysAnnouncement:
        ann = SysAnnouncement(
            title=title, content=content, publisher_id=publisher_id,
            status=status, is_pinned=is_pinned,
        )
        if status == "published":
            ann.publish_at = datetime.utcnow()
        self.db.add(ann)
        self.db.commit()
        self.db.refresh(ann)
        return ann

    def publish_announcement(self, ann_id: int) -> SysAnnouncement:
        ann = self.get_announcement_by_id(ann_id)
        if not ann:
            raise ValueError("公告不存在")
        ann.status = "published"
        ann.publish_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(ann)
        return ann

    def archive_announcement(self, ann_id: int) -> SysAnnouncement:
        ann = self.get_announcement_by_id(ann_id)
        if not ann:
            raise ValueError("公告不存在")
        ann.status = "archived"
        self.db.commit()
        self.db.refresh(ann)
        return ann

    def get_active_announcements(self, user_id: int) -> List[dict]:
        """获取当前有效公告（已发布 + 未过期），标注已读状态"""
        now = datetime.utcnow()
        anns = self.db.query(SysAnnouncement).filter(
            SysAnnouncement.status == "published",
        ).order_by(SysAnnouncement.is_pinned.desc(), SysAnnouncement.publish_at.desc()).all()

        # Filter expired
        active = [a for a in anns if not a.expire_at or a.expire_at > now]

        # Get read status
        read_ids = set()
        if active:
            reads = self.db.query(SysAnnouncementRead.announcement_id).filter(
                SysAnnouncementRead.user_id == user_id,
                SysAnnouncementRead.announcement_id.in_([a.id for a in active]),
            ).all()
            read_ids = {r[0] for r in reads}

        return [
            {
                "id": a.id, "title": a.title, "content": a.content,
                "is_pinned": a.is_pinned, "publish_at": a.publish_at.isoformat() if a.publish_at else None,
                "is_read": a.id in read_ids,
            }
            for a in active
        ]

    def mark_announcement_read(self, ann_id: int, user_id: int) -> bool:
        """标记公告已读"""
        existing = self.db.query(SysAnnouncementRead).filter(
            SysAnnouncementRead.announcement_id == ann_id,
            SysAnnouncementRead.user_id == user_id,
        ).first()
        if existing:
            return True  # Already read
        read_record = SysAnnouncementRead(announcement_id=ann_id, user_id=user_id)
        self.db.add(read_record)
        self.db.commit()
        return True
