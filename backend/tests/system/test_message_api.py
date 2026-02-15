"""
消息通知 API 测试
覆盖 /system/messages, /system/templates, /system/announcements 端点
"""
import pytest
from fastapi.testclient import TestClient
from app.models.ontology import Employee, EmployeeRole
from app.security.auth import get_password_hash, create_access_token


@pytest.fixture
def recipient_user(db_session):
    """Create a recipient user"""
    user = Employee(
        username="recipient_msg",
        password_hash=get_password_hash("123456"),
        name="消息接收人",
        role=EmployeeRole.RECEPTIONIST,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def recipient_headers(recipient_user):
    token = create_access_token(recipient_user.id, recipient_user.role)
    return {"Authorization": f"Bearer {token}"}


class TestMessageAPI:
    """站内消息 API 测试"""

    def test_inbox_empty(self, client: TestClient, auth_headers):
        response = client.get("/system/messages/inbox", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []
        assert data["total"] == 0
        assert data["unread_count"] == 0

    def test_send_message(self, client: TestClient, auth_headers, recipient_user):
        response = client.post("/system/messages/send", headers=auth_headers, json={
            "recipient_id": recipient_user.id,
            "title": "测试消息",
            "content": "这是一条测试消息",
            "msg_type": "system",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "测试消息"
        assert data["recipient_id"] == recipient_user.id
        assert data["is_read"] is False

    def test_inbox_with_messages(self, client: TestClient, auth_headers, recipient_user, recipient_headers):
        # Send a message
        client.post("/system/messages/send", headers=auth_headers, json={
            "recipient_id": recipient_user.id,
            "title": "收件箱消息",
            "content": "内容",
        })

        # Check recipient inbox
        response = client.get("/system/messages/inbox", headers=recipient_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["unread_count"] == 1
        assert data["messages"][0]["title"] == "收件箱消息"

    def test_unread_count(self, client: TestClient, auth_headers, recipient_user, recipient_headers):
        # Send 2 messages
        for i in range(2):
            client.post("/system/messages/send", headers=auth_headers, json={
                "recipient_id": recipient_user.id,
                "title": f"消息{i}",
                "content": "内容",
            })

        response = client.get("/system/messages/unread-count", headers=recipient_headers)
        assert response.status_code == 200
        assert response.json()["count"] == 2

    def test_mark_read(self, client: TestClient, auth_headers, recipient_user, recipient_headers):
        send_resp = client.post("/system/messages/send", headers=auth_headers, json={
            "recipient_id": recipient_user.id,
            "title": "待读消息",
            "content": "内容",
        })
        msg_id = send_resp.json()["id"]

        # Mark read
        response = client.put(f"/system/messages/{msg_id}/read", headers=recipient_headers)
        assert response.status_code == 200

        # Verify unread count
        count_resp = client.get("/system/messages/unread-count", headers=recipient_headers)
        assert count_resp.json()["count"] == 0

    def test_mark_all_read(self, client: TestClient, auth_headers, recipient_user, recipient_headers):
        for i in range(3):
            client.post("/system/messages/send", headers=auth_headers, json={
                "recipient_id": recipient_user.id,
                "title": f"批量消息{i}",
                "content": "内容",
            })

        response = client.put("/system/messages/read-all", headers=recipient_headers)
        assert response.status_code == 200
        assert response.json()["updated"] == 3

    def test_filter_by_read_status(self, client: TestClient, auth_headers, recipient_user, recipient_headers):
        send_resp = client.post("/system/messages/send", headers=auth_headers, json={
            "recipient_id": recipient_user.id,
            "title": "已读消息",
            "content": "内容",
        })
        msg_id = send_resp.json()["id"]
        client.put(f"/system/messages/{msg_id}/read", headers=recipient_headers)

        client.post("/system/messages/send", headers=auth_headers, json={
            "recipient_id": recipient_user.id,
            "title": "未读消息",
            "content": "内容",
        })

        # Filter unread
        resp = client.get("/system/messages/inbox?is_read=false", headers=recipient_headers)
        assert resp.json()["total"] == 1
        assert resp.json()["messages"][0]["title"] == "未读消息"


class TestTemplateAPI:
    """消息模板 API 测试"""

    def test_list_templates_empty(self, client: TestClient, auth_headers):
        response = client.get("/system/templates", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_template(self, client: TestClient, auth_headers):
        response = client.post("/system/templates", headers=auth_headers, json={
            "code": "task_assign",
            "name": "任务分配通知",
            "subject_template": "您有新的$task_type任务",
            "content_template": "房间$room_number需要$task_type，请尽快处理。",
            "variables": '["task_type", "room_number"]',
        })
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "task_assign"
        assert data["name"] == "任务分配通知"

    def test_create_template_duplicate(self, client: TestClient, auth_headers):
        client.post("/system/templates", headers=auth_headers, json={
            "code": "dup_tpl", "name": "重复模板"
        })
        response = client.post("/system/templates", headers=auth_headers, json={
            "code": "dup_tpl", "name": "重复2"
        })
        assert response.status_code == 400
        assert "已存在" in response.json()["detail"]

    def test_update_template(self, client: TestClient, auth_headers):
        create = client.post("/system/templates", headers=auth_headers, json={
            "code": "upd_tpl", "name": "旧模板"
        })
        tpl_id = create.json()["id"]

        response = client.put(f"/system/templates/{tpl_id}", headers=auth_headers, json={
            "name": "新模板"
        })
        assert response.status_code == 200
        assert response.json()["name"] == "新模板"

    def test_delete_template(self, client: TestClient, auth_headers):
        create = client.post("/system/templates", headers=auth_headers, json={
            "code": "del_tpl", "name": "待删除"
        })
        tpl_id = create.json()["id"]

        response = client.delete(f"/system/templates/{tpl_id}", headers=auth_headers)
        assert response.status_code == 204


class TestAnnouncementAPI:
    """系统公告 API 测试"""

    def test_list_announcements_empty(self, client: TestClient, auth_headers):
        response = client.get("/system/announcements", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_create_announcement_draft(self, client: TestClient, auth_headers):
        response = client.post("/system/announcements", headers=auth_headers, json={
            "title": "系统维护通知",
            "content": "今晚 22:00 系统将进行维护",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "系统维护通知"
        assert data["status"] == "draft"
        assert data["publish_at"] is None

    def test_publish_announcement(self, client: TestClient, auth_headers):
        create = client.post("/system/announcements", headers=auth_headers, json={
            "title": "待发布公告", "content": "内容",
        })
        ann_id = create.json()["id"]

        response = client.put(f"/system/announcements/{ann_id}/publish", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "published"
        assert data["publish_at"] is not None

    def test_archive_announcement(self, client: TestClient, auth_headers):
        create = client.post("/system/announcements", headers=auth_headers, json={
            "title": "待归档公告", "content": "内容",
        })
        ann_id = create.json()["id"]
        client.put(f"/system/announcements/{ann_id}/publish", headers=auth_headers)

        response = client.put(f"/system/announcements/{ann_id}/archive", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "archived"

    def test_active_announcements(self, client: TestClient, auth_headers):
        # Create and publish
        create = client.post("/system/announcements", headers=auth_headers, json={
            "title": "活跃公告", "content": "内容", "status": "published",
        })
        assert create.status_code == 201

        response = client.get("/system/announcements/active", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["title"] == "活跃公告"
        assert data[0]["is_read"] is False

    def test_mark_announcement_read(self, client: TestClient, auth_headers):
        create = client.post("/system/announcements", headers=auth_headers, json={
            "title": "已读公告", "content": "内容", "status": "published",
        })
        ann_id = create.json()["id"]

        # Mark read
        response = client.put(f"/system/announcements/{ann_id}/read", headers=auth_headers)
        assert response.status_code == 200

        # Verify is_read
        active = client.get("/system/announcements/active", headers=auth_headers)
        matching = [a for a in active.json() if a["id"] == ann_id]
        assert matching[0]["is_read"] is True

    def test_update_announcement(self, client: TestClient, auth_headers):
        create = client.post("/system/announcements", headers=auth_headers, json={
            "title": "旧标题", "content": "旧内容",
        })
        ann_id = create.json()["id"]

        response = client.put(f"/system/announcements/{ann_id}", headers=auth_headers, json={
            "title": "新标题", "is_pinned": True,
        })
        assert response.status_code == 200
        assert response.json()["title"] == "新标题"
        assert response.json()["is_pinned"] is True
