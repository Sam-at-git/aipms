"""
Tests for settings router (app/routers/settings.py)
Covers LLM settings CRUD, connection testing, provider list,
embedding test, config history, and rollback.
"""
import json
import os
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from app.models.snapshots import ConfigHistory


# ────────────────────────── helpers ──────────────────────────


@pytest.fixture
def config_history_record(db_session, sysadmin_token):
    """Insert a config history record so history/version endpoints have data."""
    # We need to get the sysadmin user id
    from app.hotel.models.ontology import Employee
    user = db_session.query(Employee).filter(Employee.username == "sysadmin").first()

    old_value = {
        "openai_base_url": "https://api.deepseek.com",
        "llm_model": "deepseek-chat",
        "llm_temperature": 0.7,
        "llm_max_tokens": 2000,
        "enable_llm": True,
        "system_prompt": "old prompt",
        "embedding_enabled": True,
        "embedding_base_url": "http://localhost:11434/v1",
        "embedding_model": "nomic-embed-text",
    }
    new_value = {
        "openai_base_url": "https://api.openai.com/v1",
        "llm_model": "gpt-4o",
        "llm_temperature": 0.5,
        "llm_max_tokens": 1000,
        "enable_llm": True,
        "system_prompt": "new prompt",
        "embedding_enabled": True,
        "embedding_base_url": "http://localhost:11434/v1",
        "embedding_model": "nomic-embed-text",
    }

    record = ConfigHistory(
        config_key="llm_settings",
        version=1,
        old_value=json.dumps(old_value, ensure_ascii=False),
        new_value=json.dumps(new_value, ensure_ascii=False),
        changed_by=user.id,
        changed_at=datetime.now(),
        change_reason="initial config",
        is_current=True,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


# ────────────────────────── GET /settings/llm ──────────────────────────


class TestGetLLMSettings:
    """GET /settings/llm - any authenticated user can read LLM settings."""

    def test_get_llm_settings_as_sysadmin(self, client, sysadmin_auth_headers):
        resp = client.get("/settings/llm", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "openai_base_url" in data
        assert "llm_model" in data
        assert "llm_temperature" in data
        assert "llm_max_tokens" in data
        assert "enable_llm" in data
        assert "embedding_enabled" in data
        assert "embedding_base_url" in data
        assert "embedding_model" in data
        # api_key should not be exposed
        assert data["openai_api_key"] is None

    def test_get_llm_settings_as_manager(self, client, manager_auth_headers):
        resp = client.get("/settings/llm", headers=manager_auth_headers)
        assert resp.status_code == 200

    def test_get_llm_settings_as_receptionist(self, client, receptionist_auth_headers):
        resp = client.get("/settings/llm", headers=receptionist_auth_headers)
        assert resp.status_code == 200

    def test_get_llm_settings_unauthenticated(self, client):
        resp = client.get("/settings/llm")
        assert resp.status_code in (401, 403)

    def test_has_env_key_flag(self, client, sysadmin_auth_headers):
        """has_env_key should reflect presence of OPENAI_API_KEY env var."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=False):
            resp = client.get("/settings/llm", headers=sysadmin_auth_headers)
            assert resp.status_code == 200
            assert resp.json()["has_env_key"] is True


# ────────────────────────── POST /settings/llm ──────────────────────────


class TestUpdateLLMSettings:
    """POST /settings/llm - sysadmin only."""

    def _settings_payload(self, **overrides):
        base = {
            "openai_api_key": "***",
            "openai_base_url": "https://api.deepseek.com",
            "llm_model": "deepseek-chat",
            "llm_temperature": 0.7,
            "llm_max_tokens": 2000,
            "enable_llm": True,
            "system_prompt": "test prompt",
            "embedding_enabled": True,
            "embedding_base_url": "http://localhost:11434/v1",
            "embedding_model": "nomic-embed-text",
        }
        base.update(overrides)
        return base

    @patch("core.ai.reset_embedding_service")
    def test_update_llm_settings_sysadmin(self, mock_reset, client, sysadmin_auth_headers):
        payload = self._settings_payload(llm_model="gpt-4o-mini", llm_temperature=0.5)
        resp = client.post("/settings/llm", json=payload, headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "LLM 设置已更新"
        assert data["settings"]["llm_model"] == "gpt-4o-mini"
        assert data["settings"]["llm_temperature"] == 0.5
        mock_reset.assert_called_once()

    @patch("core.ai.reset_embedding_service")
    def test_update_llm_settings_with_reason(self, mock_reset, client, sysadmin_auth_headers):
        payload = self._settings_payload(llm_model="gpt-4o")
        resp = client.post(
            "/settings/llm?reason=testing+new+model",
            json=payload,
            headers=sysadmin_auth_headers,
        )
        assert resp.status_code == 200

    @patch("core.ai.reset_embedding_service")
    def test_update_llm_settings_with_real_api_key(self, mock_reset, client, sysadmin_auth_headers):
        """When api_key is not '***', it should be saved."""
        payload = self._settings_payload(openai_api_key="sk-new-key")
        resp = client.post("/settings/llm", json=payload, headers=sysadmin_auth_headers)
        assert resp.status_code == 200

    def test_update_llm_settings_manager_forbidden(self, client, manager_auth_headers):
        payload = self._settings_payload()
        resp = client.post("/settings/llm", json=payload, headers=manager_auth_headers)
        assert resp.status_code == 403

    def test_update_llm_settings_receptionist_forbidden(self, client, receptionist_auth_headers):
        payload = self._settings_payload()
        resp = client.post("/settings/llm", json=payload, headers=receptionist_auth_headers)
        assert resp.status_code == 403

    def test_update_llm_settings_cleaner_forbidden(self, client, cleaner_auth_headers):
        payload = self._settings_payload()
        resp = client.post("/settings/llm", json=payload, headers=cleaner_auth_headers)
        assert resp.status_code == 403

    @patch("core.ai.reset_embedding_service")
    def test_update_embedding_settings(self, mock_reset, client, sysadmin_auth_headers):
        payload = self._settings_payload(
            embedding_enabled=False,
            embedding_base_url="http://new-host:11434/v1",
            embedding_model="all-minilm",
        )
        resp = client.post("/settings/llm", json=payload, headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["settings"]["embedding_enabled"] is False
        assert data["settings"]["embedding_base_url"] == "http://new-host:11434/v1"
        assert data["settings"]["embedding_model"] == "all-minilm"

    @patch("core.ai.reset_embedding_service")
    def test_update_system_prompt(self, mock_reset, client, sysadmin_auth_headers):
        payload = self._settings_payload(system_prompt="You are a hotel assistant.")
        resp = client.post("/settings/llm", json=payload, headers=sysadmin_auth_headers)
        assert resp.status_code == 200


# ────────────────────────── POST /settings/llm/test ──────────────────────────


class TestLLMConnectionTest:
    """POST /settings/llm/test - sysadmin only."""

    @patch("openai.OpenAI")
    def test_llm_connection_success(self, mock_openai_cls, client, sysadmin_auth_headers):
        """Successful LLM connection test."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Connection confirmed!"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        payload = {
            "api_key": "sk-test-key",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-chat",
        }
        resp = client.post("/settings/llm/test", json=payload, headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "连接成功"
        assert data["response"] == "Connection confirmed!"

    @patch("openai.OpenAI")
    def test_llm_connection_failure(self, mock_openai_cls, client, sysadmin_auth_headers):
        """LLM connection failure is reported gracefully."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Connection refused")
        mock_openai_cls.return_value = mock_client

        payload = {
            "api_key": "sk-bad-key",
            "base_url": "https://bad.example.com",
            "model": "bad-model",
        }
        resp = client.post("/settings/llm/test", json=payload, headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "连接失败" in data["message"]

    def test_llm_connection_test_no_key(self, client, sysadmin_auth_headers):
        """When no api_key provided and no env var, should return error."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure OPENAI_API_KEY is not set
            env_copy = os.environ.copy()
            env_copy.pop("OPENAI_API_KEY", None)
            with patch.dict(os.environ, env_copy, clear=True):
                payload = {
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-chat",
                }
                resp = client.post("/settings/llm/test", json=payload, headers=sysadmin_auth_headers)
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is False
                assert "API Key" in data["message"]

    @patch("openai.OpenAI")
    def test_llm_connection_test_uses_env_key(self, mock_openai_cls, client, sysadmin_auth_headers):
        """When no api_key in request but env var exists, use env var."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OK"
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"}, clear=False):
            payload = {
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
            }
            resp = client.post("/settings/llm/test", json=payload, headers=sysadmin_auth_headers)
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    def test_llm_connection_test_forbidden_for_manager(self, client, manager_auth_headers):
        payload = {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"}
        resp = client.post("/settings/llm/test", json=payload, headers=manager_auth_headers)
        assert resp.status_code == 403


# ────────────────────────── GET /settings/llm/providers ──────────────────────────


class TestGetProviders:
    """GET /settings/llm/providers - any authenticated user."""

    def test_get_providers(self, client, sysadmin_auth_headers):
        resp = client.get("/settings/llm/providers", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        providers = data["providers"]
        assert len(providers) >= 4
        names = [p["name"] for p in providers]
        assert "DeepSeek" in names
        assert "OpenAI" in names

    def test_get_providers_as_manager(self, client, manager_auth_headers):
        resp = client.get("/settings/llm/providers", headers=manager_auth_headers)
        assert resp.status_code == 200

    def test_get_providers_unauthenticated(self, client):
        resp = client.get("/settings/llm/providers")
        assert resp.status_code in (401, 403)

    def test_provider_structure(self, client, sysadmin_auth_headers):
        resp = client.get("/settings/llm/providers", headers=sysadmin_auth_headers)
        for provider in resp.json()["providers"]:
            assert "name" in provider
            assert "base_url" in provider
            assert "models" in provider
            assert "default_model" in provider
            assert isinstance(provider["models"], list)


# ────────────────────────── POST /settings/embedding/test ──────────────────────────


class TestEmbeddingConnectionTest:
    """POST /settings/embedding/test - sysadmin only."""

    @patch("openai.OpenAI")
    def test_embedding_connection_success(self, mock_openai_cls, client, sysadmin_auth_headers):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 768
        mock_response.data = [mock_embedding]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        payload = {
            "base_url": "http://localhost:11434/v1",
            "model": "nomic-embed-text",
        }
        resp = client.post("/settings/embedding/test", json=payload, headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "768" in data["message"]

    @patch("openai.OpenAI")
    def test_embedding_connection_failure(self, mock_openai_cls, client, sysadmin_auth_headers):
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("Embed fail")
        mock_openai_cls.return_value = mock_client

        payload = {"base_url": "http://bad:11434/v1", "model": "bad-model"}
        resp = client.post("/settings/embedding/test", json=payload, headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "连接失败" in data["message"]

    @patch("openai.OpenAI")
    def test_embedding_ollama_uses_ollama_key(self, mock_openai_cls, client, sysadmin_auth_headers):
        """For Ollama URLs, the api_key should be 'ollama'."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1] * 384
        mock_response.data = [mock_embedding]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        payload = {"base_url": "http://localhost:11434/v1", "model": "nomic-embed-text"}
        resp = client.post("/settings/embedding/test", json=payload, headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        # Check that OpenAI was initialized with "ollama" as api_key
        call_kwargs = mock_openai_cls.call_args
        assert call_kwargs[1]["api_key"] == "ollama"

    def test_embedding_test_forbidden_for_manager(self, client, manager_auth_headers):
        payload = {"base_url": "http://localhost:11434/v1", "model": "nomic-embed-text"}
        resp = client.post("/settings/embedding/test", json=payload, headers=manager_auth_headers)
        assert resp.status_code == 403


# ────────────────────────── GET /settings/llm/history ──────────────────────────


class TestLLMSettingsHistory:
    """GET /settings/llm/history - sysadmin only."""

    def test_get_empty_history(self, client, sysadmin_auth_headers):
        resp = client.get("/settings/llm/history", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_history_with_data(self, client, sysadmin_auth_headers, config_history_record):
        resp = client.get("/settings/llm/history", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["config_key"] == "llm_settings"
        assert data[0]["version"] == 1
        assert data[0]["is_current"] is True

    def test_get_history_with_limit(self, client, sysadmin_auth_headers, config_history_record):
        resp = client.get("/settings/llm/history?limit=5", headers=sysadmin_auth_headers)
        assert resp.status_code == 200

    def test_get_history_forbidden_for_manager(self, client, manager_auth_headers):
        resp = client.get("/settings/llm/history", headers=manager_auth_headers)
        assert resp.status_code == 403


# ────────────────────────── GET /settings/llm/history/{version} ──────────────────────────


class TestLLMSettingsVersion:
    """GET /settings/llm/history/{version} - sysadmin only."""

    def test_get_version_success(self, client, sysadmin_auth_headers, config_history_record):
        resp = client.get("/settings/llm/history/1", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == 1
        assert data["config_key"] == "llm_settings"
        assert "old_value" in data
        assert "new_value" in data
        assert data["is_current"] is True

    def test_get_version_not_found(self, client, sysadmin_auth_headers):
        resp = client.get("/settings/llm/history/999", headers=sysadmin_auth_headers)
        assert resp.status_code == 404

    def test_get_version_forbidden_for_manager(self, client, manager_auth_headers):
        resp = client.get("/settings/llm/history/1", headers=manager_auth_headers)
        assert resp.status_code == 403


# ────────────────────────── POST /settings/llm/rollback/{version} ──────────────────────────


class TestLLMSettingsRollback:
    """POST /settings/llm/rollback/{version} - sysadmin only."""

    def test_rollback_success(self, client, sysadmin_auth_headers, config_history_record):
        resp = client.post("/settings/llm/rollback/1", headers=sysadmin_auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "回滚" in data["message"]
        assert "settings" in data

    def test_rollback_nonexistent_version(self, client, sysadmin_auth_headers):
        resp = client.post("/settings/llm/rollback/999", headers=sysadmin_auth_headers)
        assert resp.status_code == 404

    def test_rollback_forbidden_for_manager(self, client, manager_auth_headers):
        resp = client.post("/settings/llm/rollback/1", headers=manager_auth_headers)
        assert resp.status_code == 403

    def test_rollback_forbidden_for_cleaner(self, client, cleaner_auth_headers):
        resp = client.post("/settings/llm/rollback/1", headers=cleaner_auth_headers)
        assert resp.status_code == 403
