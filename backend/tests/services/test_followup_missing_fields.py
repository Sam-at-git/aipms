"""
tests/services/test_followup_missing_fields.py

SPEC-1: Test that missing_fields are injected into the follow-up prompt
for more targeted LLM parameter extraction.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from app.services.llm_service import LLMService


@pytest.fixture
def llm_service():
    """Create LLMService with mocked client."""
    with patch('app.services.llm_service.OpenAI') as MockOpenAI:
        service = LLMService()
        service.enabled = True
        service.client = MockOpenAI.return_value
        return service


class TestMissingFieldsPromptInjection:
    """Test that missing_fields details are injected into parse_followup_input prompt."""

    def test_prompt_includes_missing_fields_text(self, llm_service):
        """When missing_fields are provided, the prompt should contain field details."""
        missing_fields = [
            {
                "field_name": "room_number",
                "display_name": "房间号",
                "field_type": "text",
                "placeholder": "如：201",
                "required": True
            },
            {
                "field_name": "expected_check_out",
                "display_name": "预计离店日期",
                "field_type": "date",
                "placeholder": "如：明天、后天",
                "required": True
            }
        ]

        # Mock the LLM response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"params": {"guest_name": "张三"}, "is_complete": false, "missing_fields": [], "message": "请提供房间号"}'
        llm_service.client.chat.completions.create = Mock(return_value=mock_response)

        llm_service.parse_followup_input(
            user_input="张三入住",
            action_type="walkin_checkin",
            collected_params={"guest_name": "张三"},
            missing_fields=missing_fields
        )

        # Verify the prompt sent to LLM contains missing field details
        call_args = llm_service.client.chat.completions.create.call_args
        prompt = call_args[1]['messages'][1]['content']

        assert "当前缺失的字段" in prompt
        assert "room_number" in prompt
        assert "房间号" in prompt
        assert "expected_check_out" in prompt
        assert "预计离店日期" in prompt
        assert "如：201" in prompt

    def test_prompt_includes_select_options(self, llm_service):
        """When missing_fields have select type with options, options appear in prompt."""
        missing_fields = [
            {
                "field_name": "task_type",
                "display_name": "任务类型",
                "field_type": "select",
                "options": [
                    {"value": "cleaning", "label": "清洁"},
                    {"value": "maintenance", "label": "维修"}
                ],
                "required": True
            }
        ]

        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"params": {}, "is_complete": false, "missing_fields": [], "message": "请选择"}'
        llm_service.client.chat.completions.create = Mock(return_value=mock_response)

        llm_service.parse_followup_input(
            user_input="创建任务",
            action_type="create_task",
            collected_params={"room_number": "201"},
            missing_fields=missing_fields
        )

        call_args = llm_service.client.chat.completions.create.call_args
        prompt = call_args[1]['messages'][1]['content']

        assert "选择类型字段的有效选项" in prompt
        assert "task_type" in prompt
        assert "清洁" in prompt
        assert "维修" in prompt

    def test_prompt_without_missing_fields_unchanged(self, llm_service):
        """When no missing_fields provided, prompt should not contain the section."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"params": {}, "is_complete": false, "missing_fields": [], "message": "请提供信息"}'
        llm_service.client.chat.completions.create = Mock(return_value=mock_response)

        llm_service.parse_followup_input(
            user_input="入住",
            action_type="walkin_checkin",
            collected_params={}
        )

        call_args = llm_service.client.chat.completions.create.call_args
        prompt = call_args[1]['messages'][1]['content']

        assert "当前缺失的字段" not in prompt

    def test_backward_compatible_without_missing_fields_param(self, llm_service):
        """Calling without missing_fields param should work (backward compatible)."""
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"params": {"guest_name": "李四"}, "is_complete": true, "missing_fields": [], "message": "ok"}'
        llm_service.client.chat.completions.create = Mock(return_value=mock_response)

        result = llm_service.parse_followup_input(
            user_input="李四",
            action_type="walkin_checkin",
            collected_params={}
        )

        assert result['params']['guest_name'] == '李四'
        assert result['is_complete'] is True

    def test_task_instruction_emphasizes_missing_fields(self, llm_service):
        """When missing_fields present, task instruction should mention extracting them."""
        missing_fields = [
            {
                "field_name": "guest_phone",
                "display_name": "联系电话",
                "field_type": "text",
                "placeholder": "请输入手机号",
                "required": True
            }
        ]

        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"params": {}, "is_complete": false, "missing_fields": [], "message": "ok"}'
        llm_service.client.chat.completions.create = Mock(return_value=mock_response)

        llm_service.parse_followup_input(
            user_input="电话13800138000",
            action_type="walkin_checkin",
            collected_params={"guest_name": "张三"},
            missing_fields=missing_fields
        )

        call_args = llm_service.client.chat.completions.create.call_args
        prompt = call_args[1]['messages'][1]['content']

        assert "重点提取上述缺失字段" in prompt


class TestAIServicePassesMissingFields:
    """Test that AIService passes missing_fields from follow_up_context to LLM."""

    def test_missing_fields_passed_from_context(self):
        """_process_followup_input passes missing_fields from follow_up_context."""
        with patch('app.services.llm_service.OpenAI'):
            from app.services.ai_service import AIService
            service = AIService.__new__(AIService)
            service.llm_service = Mock()
            service.llm_service.parse_followup_input = Mock(return_value={
                'params': {'guest_name': '张三'},
                'is_complete': False,
                'missing_fields': [],
                'message': '请提供房间号'
            })

            mock_user = Mock()
            mock_user.role = Mock()
            mock_user.role.value = 'receptionist'

            service._build_llm_context = Mock(return_value={})
            service._validate_action_params = Mock(return_value=(False, [], ""))
            service._generate_followup_response = Mock(return_value={'message': 'test'})

            prev_missing = [{"field_name": "room_number", "display_name": "房间号", "field_type": "text"}]

            follow_up_context = {
                'action_type': 'walkin_checkin',
                'collected_fields': {'guest_name': '张三'},
                'missing_fields': prev_missing
            }

            service._process_followup_input("201号房", follow_up_context, mock_user)

            # Verify missing_fields was passed to parse_followup_input
            call_args = service.llm_service.parse_followup_input.call_args
            assert call_args[1].get('missing_fields') == prev_missing or call_args.kwargs.get('missing_fields') == prev_missing
