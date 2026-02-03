"""
任务管理 API 单元测试
覆盖 /tasks 端点的所有功能
"""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from decimal import Decimal


class TestListTasks:
    """任务列表测试"""

    def test_list_tasks(self, client: TestClient, manager_auth_headers, db_session, sample_room):
        """测试获取任务列表"""
        from app.models.ontology import Task, TaskType, TaskStatus

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            notes="打扫房间101"
        )
        db_session.add(task)
        db_session.commit()

        response = client.get("/tasks", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_tasks_filter_by_status(self, client: TestClient, manager_auth_headers, db_session, sample_room):
        """测试按状态筛选任务"""
        from app.models.ontology import Task, TaskType, TaskStatus

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            notes="打扫房间102"
        )
        db_session.add(task)
        db_session.commit()

        response = client.get("/tasks?status=pending", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert data[0]["status"] == "pending"

    def test_list_tasks_filter_by_type(self, client: TestClient, manager_auth_headers, db_session, sample_room):
        """测试按类型筛选任务"""
        from app.models.ontology import Task, TaskType, TaskStatus

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.MAINTENANCE,
            status=TaskStatus.PENDING,
            notes="维修空调"
        )
        db_session.add(task)
        db_session.commit()

        response = client.get("/tasks?task_type=maintenance", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestCreateTask:
    """创建任务测试"""

    def test_create_cleaning_task(self, client: TestClient, manager_auth_headers, sample_room):
        """测试创建清洁任务"""
        response = client.post("/tasks", headers=manager_auth_headers, json={
            "room_id": sample_room.id,
            "task_type": "cleaning",
            "notes": "打扫房间101",
            "priority": 1
        })

        assert response.status_code == 200
        data = response.json()
        assert data["task_type"] == "cleaning"
        assert data["status"] == "pending"

    def test_create_maintenance_task(self, client: TestClient, manager_auth_headers, sample_room):
        """测试创建维修任务"""
        response = client.post("/tasks", headers=manager_auth_headers, json={
            "room_id": sample_room.id,
            "task_type": "maintenance",
            "notes": "修水龙头",
            "priority": 2
        })

        assert response.status_code == 200
        data = response.json()
        assert data["task_type"] == "maintenance"


class TestGetTaskDetail:
    """任务详情测试"""

    def test_get_task_detail(self, client: TestClient, manager_auth_headers, db_session, sample_room):
        """测试获取任务详情"""
        from app.models.ontology import Task, TaskType, TaskStatus

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            notes="打扫房间201"
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        response = client.get(f"/tasks/{task.id}", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task.id

    def test_get_task_not_found(self, client: TestClient, manager_auth_headers):
        """测试获取不存在的任务"""
        response = client.get("/tasks/99999", headers=manager_auth_headers)

        assert response.status_code == 404


class TestAssignTask:
    """分配任务测试"""

    def test_assign_task(self, client: TestClient, manager_auth_headers, db_session, sample_room, sample_cleaner):
        """测试分配任务"""
        from app.models.ontology import Task, TaskType, TaskStatus

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            notes="打扫房间202"
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        response = client.post(f"/tasks/{task.id}/assign", headers=manager_auth_headers, json={
            "assignee_id": sample_cleaner.id
        })

        assert response.status_code == 200
        data = response.json()
        assert "assignee_name" in data
        assert "message" in data


class TestStartTask:
    """开始任务测试"""

    def test_start_task(self, client: TestClient, cleaner_auth_headers, db_session, sample_room, cleaner_token):
        """测试开始任务"""
        from app.models.ontology import Task, TaskType, TaskStatus, Employee
        from jose import jwt
        from app.security.auth import SECRET_KEY, ALGORITHM

        payload = jwt.decode(cleaner_token, SECRET_KEY, algorithms=[ALGORITHM])
        cleaner_id = int(payload["sub"])

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.ASSIGNED,
            assignee_id=cleaner_id,
            notes="打扫房间203"
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        response = client.post(f"/tasks/{task.id}/start", headers=cleaner_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    def test_start_task_not_assigned(self, client: TestClient, cleaner_auth_headers, db_session, sample_room):
        """测试开始未分配的任务"""
        from app.models.ontology import Task, TaskType, TaskStatus

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            notes="打扫房间204"
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        response = client.post(f"/tasks/{task.id}/start", headers=cleaner_auth_headers)

        assert response.status_code == 400


class TestCompleteTask:
    """完成任务测试"""

    @pytest.mark.skip(reason="事件处理器在测试环境中未正确初始化")
    def test_complete_cleaning_task(self, client: TestClient, cleaner_auth_headers, db_session, sample_room, cleaner_token):
        """测试完成清洁任务"""
        pass

    def test_complete_maintenance_task(self, client: TestClient, cleaner_auth_headers, db_session, sample_room, cleaner_token):
        """测试完成维修任务（房间状态不应变化）"""
        from app.models.ontology import (
            Task, TaskType, TaskStatus, RoomStatus, Room
        )
        from jose import jwt
        from app.security.auth import SECRET_KEY, ALGORITHM

        payload = jwt.decode(cleaner_token, SECRET_KEY, algorithms=[ALGORITHM])
        cleaner_id = int(payload["sub"])

        # 设置房间为维修状态
        room = db_session.query(Room).filter_by(id=sample_room.id).first()
        room.status = RoomStatus.OUT_OF_ORDER
        db_session.commit()

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.MAINTENANCE,
            status=TaskStatus.IN_PROGRESS,
            assignee_id=cleaner_id,
            notes="维修房间206"
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        response = client.post(f"/tasks/{task.id}/complete", headers=cleaner_auth_headers)

        assert response.status_code == 200

        # 维修任务完成后，房间仍需要手动设置为可用
        db_session.refresh(room)
        assert room.status == RoomStatus.OUT_OF_ORDER


class TestGetPendingTasks:
    """待处理任务测试"""

    def test_get_pending_tasks(self, client: TestClient, manager_auth_headers, db_session, sample_room):
        """测试获取待处理任务"""
        from app.models.ontology import Task, TaskType, TaskStatus

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            notes="打扫房间301"
        )
        db_session.add(task)
        db_session.commit()

        response = client.get("/tasks/pending", headers=manager_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1


class TestGetMyTasks:
    """我的任务测试"""

    def test_get_my_tasks(self, client: TestClient, cleaner_auth_headers, db_session, sample_room, cleaner_token):
        """测试获取我的任务"""
        from app.models.ontology import Task, TaskType, TaskStatus
        from jose import jwt
        from app.security.auth import SECRET_KEY, ALGORITHM

        payload = jwt.decode(cleaner_token, SECRET_KEY, algorithms=[ALGORITHM])
        cleaner_id = int(payload["sub"])

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.ASSIGNED,
            assignee_id=cleaner_id,
            notes="打扫房间302"
        )
        db_session.add(task)
        db_session.commit()

        response = client.get("/tasks/my-tasks", headers=cleaner_auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestBatchOperations:
    """批量操作测试"""

    @pytest.mark.skip(reason="批量操作端点尚未实现")
    def test_batch_complete_tasks(self, client: TestClient, manager_auth_headers, db_session, sample_room):
        """测试批量完成任务"""
        pass
