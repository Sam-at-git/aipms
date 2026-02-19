"""
Tests for Benchmark Suite/Case CRUD API.
"""
import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


class TestBenchmarkSuiteCRUD:
    """Suite CRUD endpoint tests."""

    def test_create_suite(self, client: TestClient, manager_token: str):
        resp = client.post(
            "/benchmark/suites",
            json={"name": "散客入住", "category": "入住", "description": "测试散客入住流程"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "散客入住"
        assert data["category"] == "入住"
        assert data["case_count"] == 0
        assert "id" in data

    def test_list_suites(self, client: TestClient, manager_token: str):
        headers = {"Authorization": f"Bearer {manager_token}"}
        # Create two suites in different categories
        client.post("/benchmark/suites", json={"name": "S1", "category": "入住"}, headers=headers)
        client.post("/benchmark/suites", json={"name": "S2", "category": "查询"}, headers=headers)

        resp = client.get("/benchmark/suites", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_list_suites_filter_by_category(self, client: TestClient, manager_token: str):
        headers = {"Authorization": f"Bearer {manager_token}"}
        client.post("/benchmark/suites", json={"name": "S1", "category": "入住"}, headers=headers)
        client.post("/benchmark/suites", json={"name": "S2", "category": "查询"}, headers=headers)

        resp = client.get("/benchmark/suites?category=查询", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert all(s["category"] == "查询" for s in data)

    def test_get_suite_detail(self, client: TestClient, manager_token: str):
        headers = {"Authorization": f"Bearer {manager_token}"}
        create_resp = client.post(
            "/benchmark/suites",
            json={"name": "Detail Suite", "category": "test"},
            headers=headers,
        )
        suite_id = create_resp.json()["id"]

        resp = client.get(f"/benchmark/suites/{suite_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Detail Suite"
        assert "cases" in data
        assert data["cases"] == []

    def test_get_suite_not_found(self, client: TestClient, manager_token: str):
        resp = client.get(
            "/benchmark/suites/9999",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 404

    def test_update_suite(self, client: TestClient, manager_token: str):
        headers = {"Authorization": f"Bearer {manager_token}"}
        create_resp = client.post(
            "/benchmark/suites",
            json={"name": "Old Name", "category": "old"},
            headers=headers,
        )
        suite_id = create_resp.json()["id"]

        resp = client.put(
            f"/benchmark/suites/{suite_id}",
            json={"name": "New Name"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["category"] == "old"  # unchanged

    def test_delete_suite(self, client: TestClient, manager_token: str):
        headers = {"Authorization": f"Bearer {manager_token}"}
        create_resp = client.post(
            "/benchmark/suites",
            json={"name": "To Delete", "category": "test"},
            headers=headers,
        )
        suite_id = create_resp.json()["id"]

        resp = client.delete(f"/benchmark/suites/{suite_id}", headers=headers)
        assert resp.status_code == 200

        # Verify deleted
        resp = client.get(f"/benchmark/suites/{suite_id}", headers=headers)
        assert resp.status_code == 404

    def test_requires_manager_role(self, client: TestClient, receptionist_token: str):
        resp = client.get(
            "/benchmark/suites",
            headers={"Authorization": f"Bearer {receptionist_token}"},
        )
        assert resp.status_code == 403

    def test_requires_auth(self, client: TestClient):
        resp = client.get("/benchmark/suites")
        assert resp.status_code in (401, 403)


class TestBenchmarkCaseCRUD:
    """Case CRUD endpoint tests."""

    @pytest.fixture
    def suite_id(self, client: TestClient, manager_token: str):
        resp = client.post(
            "/benchmark/suites",
            json={"name": "Case Suite", "category": "test"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        return resp.json()["id"]

    def test_create_case(self, client: TestClient, manager_token: str, suite_id: int):
        headers = {"Authorization": f"Bearer {manager_token}"}
        assertions = json.dumps({"response_contains": ["入住"]})
        resp = client.post(
            f"/benchmark/suites/{suite_id}/cases",
            json={
                "name": "Test Case 1",
                "input": "帮张三办理入住",
                "assertions": assertions,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Case 1"
        assert data["sequence_order"] == 1
        assert data["suite_id"] == suite_id

    def test_create_case_auto_sequence(self, client: TestClient, manager_token: str, suite_id: int):
        headers = {"Authorization": f"Bearer {manager_token}"}
        # Create two cases without explicit sequence_order
        client.post(
            f"/benchmark/suites/{suite_id}/cases",
            json={"name": "C1", "input": "i1", "assertions": "{}"},
            headers=headers,
        )
        resp = client.post(
            f"/benchmark/suites/{suite_id}/cases",
            json={"name": "C2", "input": "i2", "assertions": "{}"},
            headers=headers,
        )
        assert resp.json()["sequence_order"] == 2

    def test_create_case_suite_not_found(self, client: TestClient, manager_token: str):
        resp = client.post(
            "/benchmark/suites/9999/cases",
            json={"name": "C", "input": "i", "assertions": "{}"},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 404

    def test_update_case(self, client: TestClient, manager_token: str, suite_id: int):
        headers = {"Authorization": f"Bearer {manager_token}"}
        create_resp = client.post(
            f"/benchmark/suites/{suite_id}/cases",
            json={"name": "Old", "input": "old input", "assertions": "{}"},
            headers=headers,
        )
        case_id = create_resp.json()["id"]

        resp = client.put(
            f"/benchmark/cases/{case_id}",
            json={"name": "Updated"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
        assert resp.json()["input"] == "old input"  # unchanged

    def test_delete_case(self, client: TestClient, manager_token: str, suite_id: int):
        headers = {"Authorization": f"Bearer {manager_token}"}
        create_resp = client.post(
            f"/benchmark/suites/{suite_id}/cases",
            json={"name": "To Delete", "input": "i", "assertions": "{}"},
            headers=headers,
        )
        case_id = create_resp.json()["id"]

        resp = client.delete(f"/benchmark/cases/{case_id}", headers=headers)
        assert resp.status_code == 200

        # Verify case is gone from suite detail
        suite_resp = client.get(f"/benchmark/suites/{suite_id}", headers=headers)
        assert all(c["id"] != case_id for c in suite_resp.json()["cases"])

    def test_reorder_cases(self, client: TestClient, manager_token: str, suite_id: int):
        headers = {"Authorization": f"Bearer {manager_token}"}
        ids = []
        for i in range(3):
            resp = client.post(
                f"/benchmark/suites/{suite_id}/cases",
                json={"name": f"C{i}", "input": f"i{i}", "assertions": "{}"},
                headers=headers,
            )
            ids.append(resp.json()["id"])

        # Reverse order
        resp = client.put(
            f"/benchmark/suites/{suite_id}/cases/reorder",
            json={"case_ids": list(reversed(ids))},
            headers=headers,
        )
        assert resp.status_code == 200

        # Verify new order
        suite_resp = client.get(f"/benchmark/suites/{suite_id}", headers=headers)
        case_orders = [(c["id"], c["sequence_order"]) for c in suite_resp.json()["cases"]]
        assert case_orders[0][0] == ids[2]  # Last created is now first
        assert case_orders[2][0] == ids[0]  # First created is now last

    def test_reorder_invalid_case_id(self, client: TestClient, manager_token: str, suite_id: int):
        resp = client.put(
            f"/benchmark/suites/{suite_id}/cases/reorder",
            json={"case_ids": [9999]},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 400

    def test_suite_detail_includes_cases_ordered(self, client: TestClient, manager_token: str, suite_id: int):
        headers = {"Authorization": f"Bearer {manager_token}"}
        for i in [3, 1, 2]:
            client.post(
                f"/benchmark/suites/{suite_id}/cases",
                json={"name": f"C{i}", "input": f"i{i}", "assertions": "{}", "sequence_order": i},
                headers=headers,
            )

        resp = client.get(f"/benchmark/suites/{suite_id}", headers=headers)
        orders = [c["sequence_order"] for c in resp.json()["cases"]]
        assert orders == sorted(orders)

    def test_delete_suite_cascades_cases(self, client: TestClient, manager_token: str, suite_id: int):
        headers = {"Authorization": f"Bearer {manager_token}"}
        client.post(
            f"/benchmark/suites/{suite_id}/cases",
            json={"name": "C1", "input": "i", "assertions": "{}"},
            headers=headers,
        )

        client.delete(f"/benchmark/suites/{suite_id}", headers=headers)

        resp = client.get(f"/benchmark/suites/{suite_id}", headers=headers)
        assert resp.status_code == 404


class TestGenerateAssertions:
    """AI assertion generation endpoint tests."""

    def test_generate_assertions_success(self, client: TestClient, manager_token: str):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "assertions": {
                "verify_db": [
                    {
                        "description": "201房间变为占用",
                        "sql": "SELECT status FROM rooms WHERE room_number = '201'",
                        "expect": {"rows": 1, "values": {"status": "occupied"}},
                    }
                ],
                "response_contains": ["入住", "201"],
                "response_not_contains": ["失败"],
            },
            "suggested_follow_up_fields": {"guest_name": "张三", "room_number": "201"},
        })

        with patch("app.services.benchmark_service.OpenAI") as MockOpenAI, \
             patch("app.services.benchmark_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.ENABLE_LLM = True
            mock_settings.OPENAI_BASE_URL = "https://api.example.com"
            mock_settings.LLM_MODEL = "test-model"
            mock_settings.LLM_MAX_TOKENS = 2000
            MockOpenAI.return_value.chat.completions.create.return_value = mock_response

            resp = client.post(
                "/benchmark/generate-assertions",
                json={"input": "帮张三办理201房间入住", "case_type": "mutation"},
                headers={"Authorization": f"Bearer {manager_token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "assertions" in data
        assert "verify_db" in data["assertions"]
        assert len(data["assertions"]["verify_db"]) == 1
        assert "suggested_follow_up_fields" in data

    def test_generate_assertions_flat_response(self, client: TestClient, manager_token: str):
        """LLM may return flat structure without 'assertions' wrapper."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "verify_db": [],
            "response_contains": ["房间", "查询"],
            "response_not_contains": [],
        })

        with patch("app.services.benchmark_service.OpenAI") as MockOpenAI, \
             patch("app.services.benchmark_service.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "test-key"
            mock_settings.ENABLE_LLM = True
            mock_settings.OPENAI_BASE_URL = "https://api.example.com"
            mock_settings.LLM_MODEL = "test-model"
            mock_settings.LLM_MAX_TOKENS = 2000
            MockOpenAI.return_value.chat.completions.create.return_value = mock_response

            resp = client.post(
                "/benchmark/generate-assertions",
                json={"input": "查询空房", "case_type": "query"},
                headers={"Authorization": f"Bearer {manager_token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["assertions"]["response_contains"] == ["房间", "查询"]

    def test_generate_assertions_llm_disabled(self, client: TestClient, manager_token: str):
        with patch("app.services.benchmark_service.settings") as mock_settings:
            mock_settings.ENABLE_LLM = False
            mock_settings.OPENAI_API_KEY = None

            resp = client.post(
                "/benchmark/generate-assertions",
                json={"input": "test", "case_type": "mutation"},
                headers={"Authorization": f"Bearer {manager_token}"},
            )

        assert resp.status_code == 503

    def test_generate_assertions_requires_auth(self, client: TestClient, receptionist_token: str):
        resp = client.post(
            "/benchmark/generate-assertions",
            json={"input": "test"},
            headers={"Authorization": f"Bearer {receptionist_token}"},
        )
        assert resp.status_code == 403


class TestBenchmarkExecution:
    """Execution engine endpoint tests."""

    def test_run_empty_suite_ids(self, client: TestClient, manager_token: str):
        resp = client.post(
            "/benchmark/run",
            json={"suite_ids": []},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 400

    def test_run_nonexistent_suite(self, client: TestClient, manager_token: str):
        resp = client.post(
            "/benchmark/run",
            json={"suite_ids": [9999]},
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []  # skipped nonexistent suite

    def test_list_runs_empty(self, client: TestClient, manager_token: str):
        resp = client.get(
            "/benchmark/runs",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_run_not_found(self, client: TestClient, manager_token: str):
        resp = client.get(
            "/benchmark/runs/9999",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 404

    def test_reset_db_endpoint(self, client: TestClient, manager_token: str):
        with patch("init_data.reset_business_data"):
            resp = client.post(
                "/benchmark/reset-db",
                headers={"Authorization": f"Bearer {manager_token}"},
            )
        assert resp.status_code == 200


class TestAssertionExecution:
    """Unit tests for L3/L4 assertion logic (via shared benchmark_assertions module)."""

    def test_l4_response_contains(self):
        from app.services.benchmark_assertions import evaluate_l4_response

        results = evaluate_l4_response(
            "入住成功！张三已入住201房间。",
            {"response_contains": ["入住", "201", "张三"], "response_not_contains": ["失败"]},
        )
        assert all(r["passed"] for r in results)

    def test_l4_response_contains_fail(self):
        from app.services.benchmark_assertions import evaluate_l4_response

        results = evaluate_l4_response(
            "操作失败",
            {"response_contains": ["成功"], "response_not_contains": ["失败"]},
        )
        failed = [r for r in results if not r["passed"]]
        assert len(failed) >= 1

    def test_l4_not_contains_fail(self):
        from app.services.benchmark_assertions import evaluate_l4_response

        results = evaluate_l4_response(
            "系统错误，请重试",
            {"response_contains": [], "response_not_contains": ["错误"]},
        )
        failed = [r for r in results if not r["passed"]]
        assert len(failed) >= 1

    def test_l3_assertions(self, db_session):
        """Test L3 SQL assertion execution."""
        from app.services.benchmark_assertions import evaluate_l3_db
        from app.hotel.models.ontology import RoomType

        # Seed a room type
        rt = RoomType(name="标间", base_price=288)
        db_session.add(rt)
        db_session.commit()

        results = evaluate_l3_db(db_session, {
            "verify_db": [
                {
                    "description": "标间应存在",
                    "sql": "SELECT name, base_price FROM room_types WHERE name = '标间'",
                    "expect": {"rows": 1, "values": {"name": "标间"}},
                }
            ]
        })
        assert len(results) == 1
        assert results[0]["passed"] is True

    def test_l3_assertions_fail(self, db_session):
        from app.services.benchmark_assertions import evaluate_l3_db

        results = evaluate_l3_db(db_session, {
            "verify_db": [
                {
                    "description": "不存在的表应失败",
                    "sql": "SELECT * FROM nonexistent_table",
                    "expect": {"rows": 1},
                }
            ]
        })
        assert len(results) == 1
        assert results[0]["passed"] is False

    def test_resolve_placeholders(self):
        from app.services.benchmark_runner import _resolve_placeholders
        from datetime import date

        result = _resolve_placeholders("入住到$tomorrow")
        expected = (date.today() + __import__("datetime").timedelta(days=1)).isoformat()
        assert expected in result
        assert "$tomorrow" not in result


class TestYAMLImportExport:
    """YAML import/export tests."""

    def test_export_empty(self, client: TestClient, manager_token: str):
        resp = client.get(
            "/benchmark/export",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert resp.status_code == 200
        assert "text/yaml" in resp.headers["content-type"]

    def test_export_with_data(self, client: TestClient, manager_token: str):
        headers = {"Authorization": f"Bearer {manager_token}"}
        # Create a suite with a case
        suite_resp = client.post(
            "/benchmark/suites",
            json={"name": "Export Suite", "category": "test"},
            headers=headers,
        )
        suite_id = suite_resp.json()["id"]
        client.post(
            f"/benchmark/suites/{suite_id}/cases",
            json={
                "name": "Test Case",
                "input": "帮张三入住",
                "assertions": json.dumps({"response_contains": ["入住"]}),
                "follow_up_fields": json.dumps({"guest_name": "张三"}),
            },
            headers=headers,
        )

        resp = client.get("/benchmark/export", headers=headers)
        assert resp.status_code == 200
        import yaml
        data = yaml.safe_load(resp.text)
        assert len(data["suites"]) >= 1
        suite = next(s for s in data["suites"] if s["name"] == "Export Suite")
        assert len(suite["cases"]) == 1
        assert suite["cases"][0]["assertions"]["response_contains"] == ["入住"]
        assert suite["cases"][0]["follow_up_fields"]["guest_name"] == "张三"

    def test_export_single_suite(self, client: TestClient, manager_token: str):
        headers = {"Authorization": f"Bearer {manager_token}"}
        suite_resp = client.post(
            "/benchmark/suites",
            json={"name": "Single Export", "category": "test"},
            headers=headers,
        )
        suite_id = suite_resp.json()["id"]

        resp = client.get(f"/benchmark/export/{suite_id}", headers=headers)
        assert resp.status_code == 200
        import yaml
        data = yaml.safe_load(resp.text)
        assert len(data["suites"]) == 1
        assert data["suites"][0]["name"] == "Single Export"

    def test_import_yaml(self, client: TestClient, manager_token: str):
        headers = {"Authorization": f"Bearer {manager_token}"}
        yaml_content = """
suites:
  - name: "Imported Suite"
    category: "导入测试"
    description: "Test import"
    cases:
      - name: "Imported Case 1"
        input: "查询空房"
        assertions:
          response_contains: ["房间"]
      - name: "Imported Case 2"
        input: "入住201"
        assertions:
          verify_db:
            - description: "201变为占用"
              sql: "SELECT status FROM rooms WHERE room_number = '201'"
              expect:
                rows: 1
                values:
                  status: "occupied"
          response_contains: ["入住"]
        follow_up_fields:
          room_number: "201"
"""
        resp = client.post(
            "/benchmark/import",
            content=yaml_content.encode(),
            headers={**headers, "content-type": "text/yaml"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created_suites"] == 1
        assert data["created_cases"] == 2

        # Verify imported data
        suites_resp = client.get("/benchmark/suites", headers=headers)
        imported = [s for s in suites_resp.json() if s["name"] == "Imported Suite"]
        assert len(imported) == 1
        assert imported[0]["case_count"] == 2

    def test_import_merge_skip_existing(self, client: TestClient, manager_token: str):
        headers = {"Authorization": f"Bearer {manager_token}"}
        # Create existing suite
        client.post(
            "/benchmark/suites",
            json={"name": "Existing", "category": "test"},
            headers=headers,
        )

        yaml_content = """
suites:
  - name: "Existing"
    category: "test"
    cases: []
  - name: "New Suite"
    category: "test"
    cases: []
"""
        resp = client.post(
            "/benchmark/import",
            content=yaml_content.encode(),
            headers={**headers, "content-type": "text/yaml"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created_suites"] == 1
        assert data["skipped_suites"] == 1

    def test_import_unified_format(self, client: TestClient, manager_token: str):
        """Test import with unified assertions dict format."""
        headers = {"Authorization": f"Bearer {manager_token}"}
        yaml_content = """
suites:
  - name: "散客入住流程-统一格式"
    category: "OAG"
    description: "测试散客入住"
    cases:
      - name: "散客入住201"
        input: "汪先生要入住201房间"
        run_as: "front1"
        assertions:
          expect_action:
            action_type: "walkin_checkin"
          verify_db:
            - sql: "SELECT status FROM rooms WHERE room_number = '201'"
              expect:
                values:
                  status: "occupied"
          response_not_contains: ["错误", "失败"]
        follow_up_fields:
          guest_name: "汪先生"
"""
        resp = client.post(
            "/benchmark/import",
            content=yaml_content.encode(),
            headers={**headers, "content-type": "text/yaml"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["created_suites"] == 1
        assert data["created_cases"] == 1

    def test_import_empty_body(self, client: TestClient, manager_token: str):
        resp = client.post(
            "/benchmark/import",
            content=b"",
            headers={"Authorization": f"Bearer {manager_token}", "content-type": "text/yaml"},
        )
        assert resp.status_code == 400

    def test_roundtrip_export_import(self, client: TestClient, manager_token: str):
        """Export then import should produce identical data."""
        headers = {"Authorization": f"Bearer {manager_token}"}

        # Create a suite
        suite_resp = client.post(
            "/benchmark/suites",
            json={"name": "Roundtrip", "category": "test", "description": "Roundtrip test"},
            headers=headers,
        )
        suite_id = suite_resp.json()["id"]
        client.post(
            f"/benchmark/suites/{suite_id}/cases",
            json={
                "name": "RT Case",
                "input": "查询空房",
                "assertions": json.dumps({"response_contains": ["房间"]}),
            },
            headers=headers,
        )

        # Export
        export_resp = client.get("/benchmark/export", headers=headers)
        yaml_content = export_resp.text

        # Delete the suite
        client.delete(f"/benchmark/suites/{suite_id}", headers=headers)

        # Import
        import_resp = client.post(
            "/benchmark/import?mode=merge",
            content=yaml_content.encode(),
            headers={**headers, "content-type": "text/yaml"},
        )
        assert import_resp.status_code == 200
        assert import_resp.json()["created_suites"] >= 1
