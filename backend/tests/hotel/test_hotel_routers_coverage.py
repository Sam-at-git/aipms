"""
Tests for hotel routers with low coverage:
- app/hotel/routers/prices.py (39% coverage)
- app/hotel/routers/reports.py (68% coverage)
- app/hotel/routers/tasks.py (71% coverage)
- app/hotel/routers/checkout.py (80% coverage)
- app/hotel/routers/billing.py (82% coverage)
"""
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.hotel.models.ontology import (
    Room, RoomType, RoomStatus, Guest, Reservation, ReservationStatus,
    StayRecord, StayRecordStatus, Bill, Payment, PaymentMethod,
    Task, TaskType, TaskStatus, Employee, EmployeeRole, RatePlan,
)
from app.security.auth import get_password_hash


# ======================================================================
# Helper fixtures
# ======================================================================

@pytest.fixture
def setup_stay(db_session, sample_room_type, sample_room, sample_guest, manager_token):
    """Create an active stay record with a bill for testing."""
    sample_room.status = RoomStatus.OCCUPIED
    stay = StayRecord(
        guest_id=sample_guest.id,
        room_id=sample_room.id,
        check_in_time=datetime.now(),
        expected_check_out=date.today() + timedelta(days=1),
        status=StayRecordStatus.ACTIVE,
    )
    db_session.add(stay)
    db_session.flush()

    bill = Bill(
        stay_record_id=stay.id,
        total_amount=Decimal("288.00"),
        paid_amount=Decimal("0"),
    )
    db_session.add(bill)
    db_session.commit()
    db_session.refresh(stay)
    db_session.refresh(bill)
    return stay, bill


@pytest.fixture
def setup_settled_stay(db_session, sample_room_type, sample_room, sample_guest, manager_token):
    """Create a settled stay for checkout tests."""
    sample_room.status = RoomStatus.OCCUPIED
    stay = StayRecord(
        guest_id=sample_guest.id,
        room_id=sample_room.id,
        check_in_time=datetime.now(),
        expected_check_out=date.today() + timedelta(days=1),
        status=StayRecordStatus.ACTIVE,
    )
    db_session.add(stay)
    db_session.flush()

    bill = Bill(
        stay_record_id=stay.id,
        total_amount=Decimal("288.00"),
        paid_amount=Decimal("288.00"),
        is_settled=True,
    )
    db_session.add(bill)
    db_session.commit()
    db_session.refresh(stay)
    db_session.refresh(bill)
    return stay, bill


# ======================================================================
# Price router tests
# ======================================================================

class TestPriceRouter:
    """Test /prices/* endpoints."""

    def test_list_rate_plans_empty(self, client, manager_auth_headers):
        """GET /prices/rate-plans - empty list."""
        resp = client.get("/prices/rate-plans", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_rate_plan(self, client, db_session, manager_auth_headers, sample_room_type):
        """POST /prices/rate-plans - create a rate plan."""
        data = {
            "name": "春节特价",
            "room_type_id": sample_room_type.id,
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=30)),
            "price": 388.0,
            "priority": 2,
            "is_weekend": False,
        }
        resp = client.post("/prices/rate-plans", json=data, headers=manager_auth_headers)
        assert resp.status_code == 200
        result = resp.json()
        assert result["name"] == "春节特价"
        assert result["room_type_name"] == "标准间"

    def test_create_rate_plan_invalid_room_type(self, client, manager_auth_headers):
        """POST /prices/rate-plans - invalid room type."""
        data = {
            "name": "Invalid Plan",
            "room_type_id": 99999,
            "start_date": str(date.today()),
            "end_date": str(date.today() + timedelta(days=10)),
            "price": 100.0,
        }
        resp = client.post("/prices/rate-plans", json=data, headers=manager_auth_headers)
        assert resp.status_code == 400

    def test_create_rate_plan_invalid_dates(self, client, manager_auth_headers, sample_room_type):
        """POST /prices/rate-plans - end date before start date."""
        data = {
            "name": "Bad Dates",
            "room_type_id": sample_room_type.id,
            "start_date": str(date.today() + timedelta(days=10)),
            "end_date": str(date.today()),
            "price": 100.0,
        }
        resp = client.post("/prices/rate-plans", json=data, headers=manager_auth_headers)
        assert resp.status_code == 400

    def test_get_rate_plan(self, client, db_session, manager_auth_headers, sample_room_type):
        """GET /prices/rate-plans/{id} - get rate plan detail."""
        plan = RatePlan(
            name="测试策略",
            room_type_id=sample_room_type.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            price=Decimal("388.00"),
            priority=1,
        )
        db_session.add(plan)
        db_session.commit()

        resp = client.get(f"/prices/rate-plans/{plan.id}", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "测试策略"

    def test_get_rate_plan_not_found(self, client, manager_auth_headers):
        """GET /prices/rate-plans/{id} - not found."""
        resp = client.get("/prices/rate-plans/99999", headers=manager_auth_headers)
        assert resp.status_code == 404

    def test_update_rate_plan(self, client, db_session, manager_auth_headers, sample_room_type):
        """PUT /prices/rate-plans/{id} - update rate plan."""
        plan = RatePlan(
            name="原始策略",
            room_type_id=sample_room_type.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            price=Decimal("300.00"),
            priority=1,
        )
        db_session.add(plan)
        db_session.commit()

        resp = client.put(
            f"/prices/rate-plans/{plan.id}",
            json={"price": 350.0, "name": "更新策略"},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        assert float(resp.json()["price"]) == 350.0

    def test_update_rate_plan_not_found(self, client, manager_auth_headers):
        """PUT /prices/rate-plans/{id} - not found."""
        resp = client.put(
            "/prices/rate-plans/99999",
            json={"price": 100.0},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 400

    def test_delete_rate_plan(self, client, db_session, manager_auth_headers, sample_room_type):
        """DELETE /prices/rate-plans/{id} - delete rate plan."""
        plan = RatePlan(
            name="要删除的",
            room_type_id=sample_room_type.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=10),
            price=Decimal("200.00"),
        )
        db_session.add(plan)
        db_session.commit()

        resp = client.delete(f"/prices/rate-plans/{plan.id}", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert "删除成功" in resp.json()["message"]

    def test_delete_rate_plan_not_found(self, client, manager_auth_headers):
        """DELETE /prices/rate-plans/{id} - not found."""
        resp = client.delete("/prices/rate-plans/99999", headers=manager_auth_headers)
        assert resp.status_code == 400

    def test_list_rate_plans_with_filter(
        self, client, db_session, manager_auth_headers, sample_room_type
    ):
        """GET /prices/rate-plans with filters."""
        plan = RatePlan(
            name="过滤测试",
            room_type_id=sample_room_type.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=10),
            price=Decimal("200.00"),
            is_active=True,
        )
        db_session.add(plan)
        db_session.commit()

        resp = client.get(
            f"/prices/rate-plans?room_type_id={sample_room_type.id}&is_active=true",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_price_calendar(self, client, db_session, manager_auth_headers, sample_room_type):
        """GET /prices/calendar - price calendar."""
        resp = client.get(
            f"/prices/calendar?room_type_id={sample_room_type.id}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_calculate_price(self, client, db_session, manager_auth_headers, sample_room_type):
        """GET /prices/calculate - calculate price."""
        tomorrow = date.today() + timedelta(days=1)
        day_after = date.today() + timedelta(days=3)
        resp = client.get(
            f"/prices/calculate?room_type_id={sample_room_type.id}"
            f"&check_in_date={tomorrow}&check_out_date={day_after}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_amount" in data
        assert data["nights"] == 2


# ======================================================================
# Report router tests
# ======================================================================

class TestReportRouter:
    """Test /reports/* endpoints."""

    def test_get_dashboard(self, client, db_session, manager_auth_headers, sample_room):
        """GET /reports/dashboard - returns dashboard stats."""
        resp = client.get("/reports/dashboard", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_rooms" in data
        assert "occupancy_rate" in data
        assert "today_revenue" in data

    def test_get_occupancy_report(self, client, manager_auth_headers):
        """GET /reports/occupancy - returns occupancy report."""
        start = date.today() - timedelta(days=2)
        end = date.today()
        resp = client.get(
            f"/reports/occupancy?start_date={start}&end_date={end}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_revenue_report(self, client, manager_auth_headers):
        """GET /reports/revenue - returns revenue report."""
        start = date.today() - timedelta(days=2)
        end = date.today()
        resp = client.get(
            f"/reports/revenue?start_date={start}&end_date={end}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_room_type_report(self, client, db_session, manager_auth_headers, sample_room_type):
        """GET /reports/room-types - returns room type report."""
        start = date.today() - timedelta(days=7)
        end = date.today()
        resp = client.get(
            f"/reports/room-types?start_date={start}&end_date={end}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


# ======================================================================
# Task router tests
# ======================================================================

class TestTaskRouter:
    """Test /tasks/* endpoints."""

    def test_list_tasks_empty(self, client, manager_auth_headers):
        """GET /tasks - empty list."""
        resp = client.get("/tasks", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_task(self, client, db_session, manager_auth_headers, sample_room):
        """POST /tasks - create task."""
        data = {
            "room_id": sample_room.id,
            "task_type": "cleaning",
            "priority": 3,
            "notes": "深度清洁",
        }
        resp = client.post("/tasks", json=data, headers=manager_auth_headers)
        assert resp.status_code == 200
        result = resp.json()
        assert result["task_type"] == "cleaning"
        assert result["priority"] == 3

    def test_create_task_invalid_room(self, client, manager_auth_headers):
        """POST /tasks - invalid room id."""
        data = {
            "room_id": 99999,
            "task_type": "cleaning",
        }
        resp = client.post("/tasks", json=data, headers=manager_auth_headers)
        assert resp.status_code == 400

    def test_get_task(self, client, db_session, manager_auth_headers, sample_room):
        """GET /tasks/{id} - get task detail."""
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        db_session.commit()

        resp = client.get(f"/tasks/{task.id}", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == task.id

    def test_get_task_not_found(self, client, manager_auth_headers):
        """GET /tasks/{id} - not found."""
        resp = client.get("/tasks/99999", headers=manager_auth_headers)
        assert resp.status_code == 404

    def test_assign_task(
        self, client, db_session, manager_auth_headers, sample_room, sample_cleaner
    ):
        """POST /tasks/{id}/assign - assign task to cleaner."""
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        db_session.commit()

        resp = client.post(
            f"/tasks/{task.id}/assign",
            json={"assignee_id": sample_cleaner.id},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        assert "分配成功" in resp.json()["message"]

    def test_assign_task_invalid_cleaner(
        self, client, db_session, manager_auth_headers, sample_room
    ):
        """POST /tasks/{id}/assign - invalid cleaner id."""
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        db_session.commit()

        resp = client.post(
            f"/tasks/{task.id}/assign",
            json={"assignee_id": 99999},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 400

    def test_start_task(self, client, db_session, sample_room, sample_cleaner):
        """POST /tasks/{id}/start - start task."""
        from app.security.auth import create_access_token

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.ASSIGNED,
            assignee_id=sample_cleaner.id,
        )
        db_session.add(task)
        db_session.commit()

        cleaner_token = create_access_token(sample_cleaner.id, sample_cleaner.role)
        headers = {"Authorization": f"Bearer {cleaner_token}"}

        resp = client.post(f"/tasks/{task.id}/start", headers=headers)
        assert resp.status_code == 200
        assert "任务已开始" in resp.json()["message"]

    def test_start_task_wrong_assignee(self, client, db_session, manager_auth_headers, sample_room, sample_cleaner):
        """POST /tasks/{id}/start - wrong assignee."""
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.ASSIGNED,
            assignee_id=sample_cleaner.id,
        )
        db_session.add(task)
        db_session.commit()

        # Manager tries to start (not the assignee)
        resp = client.post(f"/tasks/{task.id}/start", headers=manager_auth_headers)
        assert resp.status_code == 400

    def test_complete_task(self, client, db_session, sample_room, sample_cleaner):
        """POST /tasks/{id}/complete - complete task."""
        from app.security.auth import create_access_token

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.IN_PROGRESS,
            assignee_id=sample_cleaner.id,
            started_at=datetime.now(),
        )
        db_session.add(task)
        db_session.commit()

        cleaner_token = create_access_token(sample_cleaner.id, sample_cleaner.role)
        headers = {"Authorization": f"Bearer {cleaner_token}"}

        resp = client.post(f"/tasks/{task.id}/complete", headers=headers)
        assert resp.status_code == 200
        assert "任务已完成" in resp.json()["message"]

    def test_complete_task_wrong_assignee(
        self, client, db_session, manager_auth_headers, sample_room, sample_cleaner
    ):
        """POST /tasks/{id}/complete - wrong assignee."""
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.IN_PROGRESS,
            assignee_id=sample_cleaner.id,
        )
        db_session.add(task)
        db_session.commit()

        resp = client.post(f"/tasks/{task.id}/complete", headers=manager_auth_headers)
        assert resp.status_code == 400

    def test_update_task(self, client, db_session, manager_auth_headers, sample_room):
        """PUT /tasks/{id} - update task."""
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
            priority=1,
        )
        db_session.add(task)
        db_session.commit()

        resp = client.put(
            f"/tasks/{task.id}",
            json={"priority": 5, "notes": "紧急"},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["priority"] == 5

    def test_update_task_not_found(self, client, manager_auth_headers):
        """PUT /tasks/{id} - not found."""
        resp = client.put(
            "/tasks/99999",
            json={"priority": 3},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 400

    def test_delete_task(self, client, db_session, manager_auth_headers, sample_room):
        """DELETE /tasks/{id} - delete task."""
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        db_session.commit()

        resp = client.delete(f"/tasks/{task.id}", headers=manager_auth_headers)
        assert resp.status_code == 200

    def test_delete_task_not_found(self, client, manager_auth_headers):
        """DELETE /tasks/{id} - not found."""
        resp = client.delete("/tasks/99999", headers=manager_auth_headers)
        assert resp.status_code == 400

    def test_get_pending_tasks(self, client, db_session, manager_auth_headers, sample_room):
        """GET /tasks/pending - pending tasks list."""
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        db_session.commit()

        resp = client.get("/tasks/pending", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_my_tasks(self, client, db_session, sample_room, sample_cleaner):
        """GET /tasks/my-tasks - my tasks for cleaner."""
        from app.security.auth import create_access_token

        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.ASSIGNED,
            assignee_id=sample_cleaner.id,
        )
        db_session.add(task)
        db_session.commit()

        cleaner_token = create_access_token(sample_cleaner.id, sample_cleaner.role)
        headers = {"Authorization": f"Bearer {cleaner_token}"}

        resp = client.get("/tasks/my-tasks", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_task_summary(self, client, db_session, manager_auth_headers, sample_room):
        """GET /tasks/summary - task summary."""
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        db_session.commit()

        resp = client.get("/tasks/summary", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "pending" in data

    def test_get_cleaners(self, client, db_session, manager_auth_headers, sample_cleaner):
        """GET /tasks/cleaners - list cleaners."""
        resp = client.get("/tasks/cleaners", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_batch_delete_tasks(self, client, db_session, manager_auth_headers, sample_room):
        """DELETE /tasks/batch - batch delete pending tasks."""
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        db_session.commit()

        resp = client.delete(
            f"/tasks/batch?room_id={sample_room.id}",
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["deleted_count"] >= 1

    def test_batch_delete_tasks_forbidden_for_receptionist(
        self, client, db_session, receptionist_auth_headers, sample_room
    ):
        """DELETE /tasks/batch - forbidden for receptionist."""
        task = Task(
            room_id=sample_room.id,
            task_type=TaskType.CLEANING,
            status=TaskStatus.PENDING,
        )
        db_session.add(task)
        db_session.commit()

        resp = client.delete("/tasks/batch", headers=receptionist_auth_headers)
        assert resp.status_code == 403


# ======================================================================
# Checkout router tests
# ======================================================================

class TestCheckoutRouter:
    """Test /checkout/* endpoints."""

    def test_checkout_success(self, client, db_session, manager_auth_headers, setup_settled_stay):
        """POST /checkout - successful checkout."""
        stay, bill = setup_settled_stay
        resp = client.post(
            "/checkout",
            json={"stay_record_id": stay.id},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        assert "退房成功" in resp.json()["message"]

    def test_checkout_unsettled_bill(self, client, db_session, manager_auth_headers, setup_stay):
        """POST /checkout - unsettled bill error."""
        stay, bill = setup_stay
        resp = client.post(
            "/checkout",
            json={"stay_record_id": stay.id},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 400
        assert "账单未结清" in resp.json()["detail"]

    def test_checkout_not_found(self, client, manager_auth_headers):
        """POST /checkout - stay not found."""
        resp = client.post(
            "/checkout",
            json={"stay_record_id": 99999},
            headers=manager_auth_headers,
        )
        assert resp.status_code == 400

    def test_batch_checkout(self, client, db_session, manager_auth_headers, setup_settled_stay):
        """POST /checkout/batch - batch checkout."""
        stay, bill = setup_settled_stay
        resp = client.post(
            "/checkout/batch",
            json=[stay.id],
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1

    def test_get_today_expected_checkouts(self, client, manager_auth_headers):
        """GET /checkout/today-expected."""
        resp = client.get("/checkout/today-expected", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_overdue_stays(self, client, manager_auth_headers):
        """GET /checkout/overdue."""
        resp = client.get("/checkout/overdue", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ======================================================================
# Billing router tests
# ======================================================================

class TestBillingRouter:
    """Test /billing/* endpoints."""

    def test_get_bill(self, client, db_session, manager_auth_headers, setup_stay):
        """GET /billing/bill/{id} - get bill detail."""
        stay, bill = setup_stay
        resp = client.get(f"/billing/bill/{bill.id}", headers=manager_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == bill.id
        assert float(data["total_amount"]) == 288.0

    def test_get_bill_not_found(self, client, manager_auth_headers):
        """GET /billing/bill/{id} - not found."""
        resp = client.get("/billing/bill/99999", headers=manager_auth_headers)
        assert resp.status_code == 404

    def test_get_bill_by_stay(self, client, db_session, manager_auth_headers, setup_stay):
        """GET /billing/stay/{id} - get bill by stay record."""
        stay, bill = setup_stay
        resp = client.get(f"/billing/stay/{stay.id}", headers=manager_auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == bill.id

    def test_get_bill_by_stay_not_found(self, client, manager_auth_headers):
        """GET /billing/stay/{id} - not found."""
        resp = client.get("/billing/stay/99999", headers=manager_auth_headers)
        assert resp.status_code == 404

    def test_add_payment(self, client, db_session, manager_auth_headers, setup_stay):
        """POST /billing/payment - add payment."""
        stay, bill = setup_stay
        resp = client.post(
            "/billing/payment",
            json={
                "bill_id": bill.id,
                "amount": 100.0,
                "method": "cash",
            },
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "payment_id" in data
        assert data["amount"] == 100.0

    def test_add_payment_invalid_bill(self, client, manager_auth_headers):
        """POST /billing/payment - invalid bill id."""
        resp = client.post(
            "/billing/payment",
            json={
                "bill_id": 99999,
                "amount": 100.0,
                "method": "cash",
            },
            headers=manager_auth_headers,
        )
        assert resp.status_code == 400

    def test_adjust_bill(self, client, db_session, manager_auth_headers, setup_stay):
        """POST /billing/adjust - adjust bill."""
        stay, bill = setup_stay
        resp = client.post(
            "/billing/adjust",
            json={
                "bill_id": bill.id,
                "adjustment_amount": -50.0,
                "reason": "VIP折扣",
            },
            headers=manager_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["adjustment_amount"] == -50.0

    def test_adjust_bill_invalid_bill(self, client, manager_auth_headers):
        """POST /billing/adjust - invalid bill id."""
        resp = client.post(
            "/billing/adjust",
            json={
                "bill_id": 99999,
                "adjustment_amount": -50.0,
                "reason": "test",
            },
            headers=manager_auth_headers,
        )
        assert resp.status_code == 400
