"""Tests for ConversationService and /conversations API endpoints"""
import os
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient
from app.services.conversation_service import ConversationService, ConversationMessage
from app.routers.conversations import get_conversation_service
from app.models.ontology import Employee, EmployeeRole
from app.security.auth import get_password_hash, create_access_token
from app.main import app


@pytest.fixture
def sysadmin_token(db_session):
    """Create sysadmin user and return token"""
    admin = Employee(
        username="sysadmin",
        password_hash=get_password_hash("123456"),
        name="系统管理员",
        role=EmployeeRole.SYSADMIN,
        is_active=True
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return create_access_token(admin.id, admin.role)


@pytest.fixture
def sysadmin_auth_headers(sysadmin_token):
    """Auth headers for sysadmin"""
    return {"Authorization": f"Bearer {sysadmin_token}"}


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test data"""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.fixture
def service(temp_dir):
    """Create a ConversationService with temporary storage"""
    return ConversationService(base_dir=temp_dir)


class TestGetLastActiveConversation:
    """Tests for get_last_active_conversation()"""

    def test_no_history_returns_empty(self, service):
        """No conversation history → returns empty list and None"""
        messages, date_str = service.get_last_active_conversation(user_id=999)
        assert messages == []
        assert date_str is None

    def test_single_date_returns_messages(self, service):
        """Single date file → returns all messages from that date"""
        service.save_message_pair(
            user_id=1,
            user_content="你好",
            assistant_content="你好！有什么可以帮助您的？",
            topic_id="test-topic"
        )
        messages, date_str = service.get_last_active_conversation(user_id=1)
        assert len(messages) == 2
        assert date_str is not None
        assert messages[0].role == "user"
        assert messages[0].content == "你好"
        assert messages[1].role == "assistant"

    def test_multiple_dates_returns_latest(self, service):
        """Multiple date files → returns messages from the latest date only"""
        from datetime import datetime, timedelta

        # Save messages for "yesterday" by creating file directly
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')

        # Create yesterday's file
        user_dir = service._get_user_dir(1)
        yesterday_file = user_dir / f"{yesterday}.jsonl"
        import json
        old_msg = ConversationMessage(
            id="old-1",
            timestamp=f"{yesterday}T10:00:00",
            role="user",
            content="旧消息"
        )
        with open(yesterday_file, 'w', encoding='utf-8') as f:
            f.write(json.dumps(old_msg.to_dict(), ensure_ascii=False) + '\n')

        # Save today's messages normally
        service.save_message_pair(
            user_id=1,
            user_content="今天的消息",
            assistant_content="今天的回复"
        )

        messages, date_str = service.get_last_active_conversation(user_id=1)
        assert date_str == today
        assert len(messages) == 2
        assert messages[0].content == "今天的消息"


class TestLastActiveEndpoint:
    """Tests for GET /conversations/last-active endpoint"""

    def test_last_active_no_auth(self, client: TestClient):
        """Unauthenticated request returns 401"""
        response = client.get("/conversations/last-active")
        assert response.status_code == 401

    def test_last_active_no_history(self, client: TestClient, manager_auth_headers, temp_dir):
        """No history → empty messages, active_date is null"""
        temp_service = ConversationService(base_dir=temp_dir)
        app.dependency_overrides[get_conversation_service] = lambda: temp_service
        try:
            response = client.get("/conversations/last-active", headers=manager_auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert data["messages"] == []
            assert data["has_more"] is False
            assert data["active_date"] is None
        finally:
            app.dependency_overrides.pop(get_conversation_service, None)

    def test_last_active_with_history(self, client: TestClient, manager_auth_headers, temp_dir, db_session):
        """With history → returns messages from latest date"""
        temp_service = ConversationService(base_dir=temp_dir)
        # Get the manager user ID from db
        from app.models.ontology import Employee
        manager = db_session.query(Employee).filter_by(username="manager").first()
        temp_service.save_message_pair(
            user_id=manager.id,
            user_content="测试消息",
            assistant_content="测试回复"
        )
        app.dependency_overrides[get_conversation_service] = lambda: temp_service
        try:
            response = client.get("/conversations/last-active", headers=manager_auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data["messages"]) == 2
            assert data["has_more"] is False
            assert data["active_date"] is not None
            assert data["messages"][0]["role"] == "user"
            assert data["messages"][0]["content"] == "测试消息"
        finally:
            app.dependency_overrides.pop(get_conversation_service, None)


class TestGetUsersWithConversations:
    """Tests for get_users_with_conversations()"""

    def test_no_users(self, service):
        """No users → empty list"""
        users = service.get_users_with_conversations()
        assert users == []

    def test_with_users(self, service):
        """Users with conversations → returns sorted list"""
        service.save_message_pair(user_id=3, user_content="hi", assistant_content="hello")
        service.save_message_pair(user_id=1, user_content="hi", assistant_content="hello")
        users = service.get_users_with_conversations()
        assert users == [1, 3]


class TestAdminEndpoints:
    """Tests for admin conversation endpoints"""

    def test_admin_users_requires_sysadmin(self, client: TestClient, manager_auth_headers):
        """Manager cannot access admin endpoints"""
        response = client.get("/conversations/admin/users", headers=manager_auth_headers)
        assert response.status_code == 403

    def test_admin_users_list(self, client: TestClient, sysadmin_auth_headers, temp_dir, db_session):
        """Sysadmin can list users with conversations"""
        temp_service = ConversationService(base_dir=temp_dir)
        temp_service.save_message_pair(user_id=1, user_content="hi", assistant_content="hello")
        temp_service.save_message_pair(user_id=2, user_content="hi", assistant_content="hello")
        app.dependency_overrides[get_conversation_service] = lambda: temp_service
        try:
            response = client.get("/conversations/admin/users", headers=sysadmin_auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data["users"]) == 2
            assert data["users"][0]["user_id"] == 1
        finally:
            app.dependency_overrides.pop(get_conversation_service, None)

    def test_admin_user_messages(self, client: TestClient, sysadmin_auth_headers, temp_dir, db_session):
        """Sysadmin can view user messages"""
        temp_service = ConversationService(base_dir=temp_dir)
        temp_service.save_message_pair(user_id=1, user_content="测试", assistant_content="回复")
        app.dependency_overrides[get_conversation_service] = lambda: temp_service
        try:
            response = client.get("/conversations/admin/user/1/messages", headers=sysadmin_auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data["messages"]) == 2
            assert data["messages"][0]["content"] == "测试"
        finally:
            app.dependency_overrides.pop(get_conversation_service, None)

    def test_admin_user_dates(self, client: TestClient, sysadmin_auth_headers, temp_dir, db_session):
        """Sysadmin can get user's available dates"""
        temp_service = ConversationService(base_dir=temp_dir)
        temp_service.save_message_pair(user_id=1, user_content="hi", assistant_content="hello")
        app.dependency_overrides[get_conversation_service] = lambda: temp_service
        try:
            response = client.get("/conversations/admin/user/1/dates", headers=sysadmin_auth_headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data["dates"]) == 1
        finally:
            app.dependency_overrides.pop(get_conversation_service, None)
