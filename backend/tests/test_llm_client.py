"""
Comprehensive unit tests for LLMClient and validate_safe_id.

All tests use unittest.mock — no real API calls are made.
"""

import json
import re
import pytest
from unittest.mock import patch, MagicMock, PropertyMock


# ---------------------------------------------------------------------------
# 1. Anthropic key detection
# ---------------------------------------------------------------------------

class TestIsAnthropicKey:
    """Test the _is_anthropic_key helper function."""

    def test_anthropic_key_detected(self):
        from app.utils.llm_client import _is_anthropic_key
        assert _is_anthropic_key("sk-ant-api03-xxxYYYzzz") is True

    def test_anthropic_key_short_prefix(self):
        from app.utils.llm_client import _is_anthropic_key
        assert _is_anthropic_key("sk-ant-abcdef") is True

    def test_openai_key_not_detected(self):
        from app.utils.llm_client import _is_anthropic_key
        assert _is_anthropic_key("sk-proj-xxxYYYzzz") is False

    def test_empty_string_returns_false(self):
        from app.utils.llm_client import _is_anthropic_key
        assert _is_anthropic_key("") is False

    def test_random_string_returns_false(self):
        from app.utils.llm_client import _is_anthropic_key
        assert _is_anthropic_key("some-random-key") is False

    def test_partial_prefix_returns_false(self):
        from app.utils.llm_client import _is_anthropic_key
        assert _is_anthropic_key("sk-an") is False

    def test_case_sensitive(self):
        from app.utils.llm_client import _is_anthropic_key
        # The prefix check is case-sensitive
        assert _is_anthropic_key("SK-ANT-api03-xxx") is False


# ---------------------------------------------------------------------------
# 2. Think tag stripping
# ---------------------------------------------------------------------------

class TestThinkTagStripping:
    """Test the think-tag removal regex applied in LLMClient.chat().

    We test the exact two-step regex from the source to verify behavior
    without constructing full LLMClient instances.
    """

    @staticmethod
    def _strip_think_tags(content: str) -> str:
        """Replicate the stripping logic from LLMClient.chat()."""
        content = re.sub(r'<think>[\s\S]*?</think>', '', content, flags=re.DOTALL).strip()
        content = re.sub(r'<think>[\s\S]*$', '', content, flags=re.DOTALL).strip()
        return content

    def test_single_line_think_tag(self):
        result = self._strip_think_tags("<think>reasoning</think>actual")
        assert result == "actual"

    def test_multiline_think_tag(self):
        text = "<think>\nlong\nreasoning\n</think>\nactual content"
        result = self._strip_think_tags(text)
        assert result == "actual content"

    def test_unclosed_think_tag(self):
        result = self._strip_think_tags("<think>reasoning without closing tag")
        assert result == ""

    def test_no_think_tags(self):
        result = self._strip_think_tags("just normal content")
        assert result == "just normal content"

    def test_multiple_think_blocks(self):
        text = "<think>a</think>between<think>b</think>after"
        result = self._strip_think_tags(text)
        assert "between" in result
        assert "after" in result
        assert "<think>" not in result

    def test_think_tag_with_whitespace_around(self):
        text = "  <think>stuff</think>  result  "
        result = self._strip_think_tags(text)
        assert result == "result"

    def test_unclosed_think_tag_at_end_of_real_content(self):
        text = "real content here\n<think>partial reasoning"
        result = self._strip_think_tags(text)
        assert result == "real content here"

    def test_empty_think_tag(self):
        result = self._strip_think_tags("<think></think>hello")
        assert result == "hello"

    def test_nested_angle_brackets_inside_think(self):
        text = "<think>some <b>bold</b> reasoning</think>output"
        result = self._strip_think_tags(text)
        assert result == "output"


# ---------------------------------------------------------------------------
# 3. System message separation (_chat_anthropic logic)
# ---------------------------------------------------------------------------

class TestSystemMessageSeparation:
    """Test that _chat_anthropic correctly separates system messages."""

    @patch("app.utils.llm_client.Config")
    @patch("anthropic.Anthropic")
    def _make_client(self, mock_anthropic_cls, mock_config):
        """Helper: build an LLMClient wired to a mock Anthropic SDK."""
        mock_config.LLM_API_KEY = "sk-ant-api03-test"
        mock_config.LLM_BASE_URL = "https://api.anthropic.com/v1/"
        mock_config.LLM_MODEL_NAME = "claude-haiku-4-5-20251001"

        mock_instance = MagicMock()
        mock_anthropic_cls.return_value = mock_instance

        # Build response mock
        mock_content_block = MagicMock()
        mock_content_block.text = "response text"
        mock_response = MagicMock()
        mock_response.content = [mock_content_block]
        mock_instance.messages.create.return_value = mock_response

        from app.utils.llm_client import LLMClient
        client = LLMClient(
            api_key="sk-ant-api03-test",
            base_url="https://api.anthropic.com/v1/",
            model="claude-haiku-4-5-20251001",
        )
        return client, mock_instance

    def test_single_system_message_extracted(self):
        client, mock_instance = self._make_client()
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        client.chat(messages)

        call_kwargs = mock_instance.messages.create.call_args
        # System text should be passed as a keyword argument
        assert "system" in call_kwargs.kwargs
        assert "You are helpful." in call_kwargs.kwargs["system"]
        # Non-system messages should only contain the user message
        passed_messages = call_kwargs.kwargs["messages"]
        assert len(passed_messages) == 1
        assert passed_messages[0]["role"] == "user"

    def test_multiple_system_messages_concatenated(self):
        client, mock_instance = self._make_client()
        messages = [
            {"role": "system", "content": "Instruction one."},
            {"role": "system", "content": "Instruction two."},
            {"role": "user", "content": "Hello"},
        ]
        client.chat(messages)

        call_kwargs = mock_instance.messages.create.call_args
        system_text = call_kwargs.kwargs["system"]
        assert "Instruction one." in system_text
        assert "Instruction two." in system_text

    def test_no_system_messages(self):
        client, mock_instance = self._make_client()
        messages = [
            {"role": "user", "content": "Hello"},
        ]
        client.chat(messages)

        call_kwargs = mock_instance.messages.create.call_args
        # With no system text, 'system' kwarg should not be present
        assert "system" not in call_kwargs.kwargs or call_kwargs.kwargs.get("system", "").strip() == ""
        passed_messages = call_kwargs.kwargs["messages"]
        assert len(passed_messages) == 1

    def test_system_and_assistant_messages_separated(self):
        client, mock_instance = self._make_client()
        messages = [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "What is 2+2?"},
            {"role": "assistant", "content": "4"},
            {"role": "user", "content": "Thanks"},
        ]
        client.chat(messages)

        call_kwargs = mock_instance.messages.create.call_args
        assert "Be concise." in call_kwargs.kwargs["system"]
        passed_messages = call_kwargs.kwargs["messages"]
        roles = [m["role"] for m in passed_messages]
        assert roles == ["user", "assistant", "user"]


# ---------------------------------------------------------------------------
# 4. JSON mode system prompt injection
# ---------------------------------------------------------------------------

class TestJsonModeInjection:
    """Test that response_format={"type": "json_object"} injects a JSON
    instruction into the system prompt for Anthropic calls."""

    @patch("app.utils.llm_client.Config")
    @patch("anthropic.Anthropic")
    def _make_client(self, mock_anthropic_cls, mock_config):
        mock_config.LLM_API_KEY = "sk-ant-api03-test"
        mock_config.LLM_BASE_URL = "https://api.anthropic.com/v1/"
        mock_config.LLM_MODEL_NAME = "claude-haiku-4-5-20251001"

        mock_instance = MagicMock()
        mock_anthropic_cls.return_value = mock_instance

        mock_content_block = MagicMock()
        mock_content_block.text = '{"key": "value"}'
        mock_response = MagicMock()
        mock_response.content = [mock_content_block]
        mock_instance.messages.create.return_value = mock_response

        from app.utils.llm_client import LLMClient
        client = LLMClient(
            api_key="sk-ant-api03-test",
            base_url="https://api.anthropic.com/v1/",
            model="claude-haiku-4-5-20251001",
        )
        return client, mock_instance

    def test_json_instruction_appended_with_existing_system(self):
        client, mock_instance = self._make_client()
        messages = [
            {"role": "system", "content": "You are an analyst."},
            {"role": "user", "content": "Give me JSON"},
        ]
        client.chat(messages, response_format={"type": "json_object"})

        call_kwargs = mock_instance.messages.create.call_args
        system_text = call_kwargs.kwargs["system"]
        assert "You are an analyst." in system_text
        assert "valid JSON only" in system_text

    def test_json_instruction_when_no_system_message(self):
        client, mock_instance = self._make_client()
        messages = [
            {"role": "user", "content": "Give me JSON"},
        ]
        client.chat(messages, response_format={"type": "json_object"})

        call_kwargs = mock_instance.messages.create.call_args
        system_text = call_kwargs.kwargs["system"]
        assert "valid JSON only" in system_text

    def test_no_json_instruction_without_response_format(self):
        client, mock_instance = self._make_client()
        messages = [
            {"role": "system", "content": "You are an analyst."},
            {"role": "user", "content": "Hello"},
        ]
        client.chat(messages)

        call_kwargs = mock_instance.messages.create.call_args
        system_text = call_kwargs.kwargs["system"]
        assert "valid JSON only" not in system_text

    def test_response_format_not_passed_to_anthropic_api(self):
        """Anthropic does not support response_format kwarg — it must NOT
        be forwarded to the SDK call."""
        client, mock_instance = self._make_client()
        messages = [
            {"role": "user", "content": "Give me JSON"},
        ]
        client.chat(messages, response_format={"type": "json_object"})

        call_kwargs = mock_instance.messages.create.call_args
        assert "response_format" not in call_kwargs.kwargs


# ---------------------------------------------------------------------------
# 5. OpenAI path basics
# ---------------------------------------------------------------------------

class TestOpenAIPath:
    """Test that the OpenAI code path works and forwards response_format."""

    @patch("app.utils.llm_client.Config")
    @patch("app.utils.llm_client.OpenAI")
    def test_openai_response_format_forwarded(self, mock_openai_cls, mock_config):
        mock_config.LLM_API_KEY = "sk-proj-abc123"
        mock_config.LLM_BASE_URL = "https://api.openai.com/v1"
        mock_config.LLM_MODEL_NAME = "gpt-4o-mini"

        mock_instance = MagicMock()
        mock_openai_cls.return_value = mock_instance

        mock_message = MagicMock()
        mock_message.content = '{"answer": 42}'
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_instance.chat.completions.create.return_value = mock_response

        from app.utils.llm_client import LLMClient
        client = LLMClient(
            api_key="sk-proj-abc123",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
        )

        result = client.chat(
            [{"role": "user", "content": "test"}],
            response_format={"type": "json_object"},
        )

        call_kwargs = mock_instance.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}
        assert result == '{"answer": 42}'

    @patch("app.utils.llm_client.Config")
    @patch("app.utils.llm_client.OpenAI")
    def test_openai_no_response_format_when_none(self, mock_openai_cls, mock_config):
        mock_config.LLM_API_KEY = "sk-proj-abc123"
        mock_config.LLM_BASE_URL = "https://api.openai.com/v1"
        mock_config.LLM_MODEL_NAME = "gpt-4o-mini"

        mock_instance = MagicMock()
        mock_openai_cls.return_value = mock_instance

        mock_message = MagicMock()
        mock_message.content = "hello"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_instance.chat.completions.create.return_value = mock_response

        from app.utils.llm_client import LLMClient
        client = LLMClient(
            api_key="sk-proj-abc123",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
        )

        client.chat([{"role": "user", "content": "test"}])

        call_kwargs = mock_instance.chat.completions.create.call_args.kwargs
        assert "response_format" not in call_kwargs


# ---------------------------------------------------------------------------
# 6. chat_json markdown cleanup and parsing
# ---------------------------------------------------------------------------

class TestChatJson:
    """Test chat_json cleans markdown fences and parses JSON."""

    @patch("app.utils.llm_client.Config")
    @patch("app.utils.llm_client.OpenAI")
    def _make_openai_client(self, raw_response, mock_openai_cls, mock_config):
        mock_config.LLM_API_KEY = "sk-proj-abc123"
        mock_config.LLM_BASE_URL = "https://api.openai.com/v1"
        mock_config.LLM_MODEL_NAME = "gpt-4o-mini"

        mock_instance = MagicMock()
        mock_openai_cls.return_value = mock_instance

        mock_message = MagicMock()
        mock_message.content = raw_response
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_instance.chat.completions.create.return_value = mock_response

        from app.utils.llm_client import LLMClient
        return LLMClient(
            api_key="sk-proj-abc123",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
        )

    def test_plain_json(self):
        client = self._make_openai_client('{"key": "value"}')
        result = client.chat_json([{"role": "user", "content": "test"}])
        assert result == {"key": "value"}

    def test_json_with_markdown_fences(self):
        client = self._make_openai_client('```json\n{"key": "value"}\n```')
        result = client.chat_json([{"role": "user", "content": "test"}])
        assert result == {"key": "value"}

    def test_json_with_bare_fences(self):
        client = self._make_openai_client('```\n{"key": "value"}\n```')
        result = client.chat_json([{"role": "user", "content": "test"}])
        assert result == {"key": "value"}

    def test_invalid_json_raises_valueerror(self):
        client = self._make_openai_client("not json at all")
        with pytest.raises(ValueError, match="Invalid JSON returned by LLM"):
            client.chat_json([{"role": "user", "content": "test"}])


# ---------------------------------------------------------------------------
# 7. Constructor validation
# ---------------------------------------------------------------------------

class TestLLMClientInit:
    """Test constructor behavior."""

    @patch("app.utils.llm_client.Config")
    def test_missing_api_key_raises(self, mock_config):
        mock_config.LLM_API_KEY = None
        mock_config.LLM_BASE_URL = "https://api.openai.com/v1"
        mock_config.LLM_MODEL_NAME = "gpt-4o-mini"

        from app.utils.llm_client import LLMClient
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            LLMClient(api_key="", base_url="https://api.openai.com/v1")

    @patch("app.utils.llm_client.Config")
    @patch("anthropic.Anthropic")
    def test_anthropic_base_url_not_set_when_contains_openai(self, mock_anthropic_cls, mock_config):
        """If base_url contains 'openai', it should NOT be passed to the
        Anthropic client (it's a leftover OpenAI URL)."""
        mock_config.LLM_API_KEY = "sk-ant-api03-test"
        mock_config.LLM_BASE_URL = "https://api.openai.com/v1"
        mock_config.LLM_MODEL_NAME = "claude-haiku-4-5-20251001"

        mock_instance = MagicMock()
        mock_anthropic_cls.return_value = mock_instance

        from app.utils.llm_client import LLMClient
        LLMClient(
            api_key="sk-ant-api03-test",
            base_url="https://api.openai.com/v1",
            model="claude-haiku-4-5-20251001",
        )

        # Anthropic constructor should NOT receive base_url
        call_kwargs = mock_anthropic_cls.call_args.kwargs
        assert "base_url" not in call_kwargs

    @patch("app.utils.llm_client.Config")
    @patch("anthropic.Anthropic")
    def test_anthropic_base_url_set_when_anthropic_domain(self, mock_anthropic_cls, mock_config):
        """If base_url is an Anthropic URL, it should be passed through."""
        mock_config.LLM_API_KEY = "sk-ant-api03-test"
        mock_config.LLM_BASE_URL = "https://api.anthropic.com/v1/"
        mock_config.LLM_MODEL_NAME = "claude-haiku-4-5-20251001"

        mock_instance = MagicMock()
        mock_anthropic_cls.return_value = mock_instance

        from app.utils.llm_client import LLMClient
        LLMClient(
            api_key="sk-ant-api03-test",
            base_url="https://api.anthropic.com/v1/",
            model="claude-haiku-4-5-20251001",
        )

        call_kwargs = mock_anthropic_cls.call_args.kwargs
        # /v1/ suffix is stripped since the Anthropic SDK adds it internally
        assert call_kwargs["base_url"] == "https://api.anthropic.com"


# ---------------------------------------------------------------------------
# 8. content_filter stop_reason handling
# ---------------------------------------------------------------------------

class TestContentFilterHandling:
    """Test that content_filter stop_reason raises an error."""

    @patch("app.utils.llm_client.Config")
    @patch("anthropic.Anthropic")
    def test_content_filter_raises_valueerror(self, mock_anthropic_cls, mock_config):
        mock_config.LLM_API_KEY = "sk-ant-api03-test"
        mock_config.LLM_BASE_URL = "https://api.anthropic.com/v1/"
        mock_config.LLM_MODEL_NAME = "claude-haiku-4-5-20251001"

        mock_instance = MagicMock()
        mock_anthropic_cls.return_value = mock_instance

        # Simulate content_filter response
        mock_response = MagicMock()
        mock_response.stop_reason = "content_filter"
        mock_response.content = [MagicMock(text="")]
        mock_instance.messages.create.return_value = mock_response

        from app.utils.llm_client import LLMClient
        client = LLMClient(
            api_key="sk-ant-api03-test",
            base_url="https://api.anthropic.com/v1/",
            model="claude-haiku-4-5-20251001",
        )

        with pytest.raises(ValueError, match="content filter"):
            client.chat([{"role": "user", "content": "test"}])

    @patch("app.utils.llm_client.Config")
    @patch("anthropic.Anthropic")
    def test_end_turn_succeeds(self, mock_anthropic_cls, mock_config):
        mock_config.LLM_API_KEY = "sk-ant-api03-test"
        mock_config.LLM_BASE_URL = "https://api.anthropic.com/v1/"
        mock_config.LLM_MODEL_NAME = "claude-haiku-4-5-20251001"

        mock_instance = MagicMock()
        mock_anthropic_cls.return_value = mock_instance

        mock_response = MagicMock()
        mock_response.stop_reason = "end_turn"
        mock_response.content = [MagicMock(text="Hello")]
        mock_instance.messages.create.return_value = mock_response

        from app.utils.llm_client import LLMClient
        client = LLMClient(
            api_key="sk-ant-api03-test",
            base_url="https://api.anthropic.com/v1/",
            model="claude-haiku-4-5-20251001",
        )

        result = client.chat([{"role": "user", "content": "test"}])
        assert result == "Hello"


# ---------------------------------------------------------------------------
# 9. validate_safe_id
# ---------------------------------------------------------------------------

class TestValidateSafeId:
    """Test the validate_safe_id input validation function."""

    def test_valid_simple_id(self):
        from app.utils.validation import validate_safe_id
        assert validate_safe_id("proj_abc123") == "proj_abc123"

    def test_valid_id_with_dash(self):
        from app.utils.validation import validate_safe_id
        assert validate_safe_id("my-project") == "my-project"

    def test_valid_id_with_underscore(self):
        from app.utils.validation import validate_safe_id
        assert validate_safe_id("sim_def456") == "sim_def456"

    def test_valid_alphanumeric(self):
        from app.utils.validation import validate_safe_id
        assert validate_safe_id("abc123XYZ") == "abc123XYZ"

    def test_path_traversal_rejected(self):
        from app.utils.validation import validate_safe_id
        with pytest.raises(ValueError, match="illegal characters"):
            validate_safe_id("../../etc")

    def test_forward_slash_rejected(self):
        from app.utils.validation import validate_safe_id
        with pytest.raises(ValueError, match="illegal characters"):
            validate_safe_id("foo/bar")

    def test_backslash_rejected(self):
        from app.utils.validation import validate_safe_id
        with pytest.raises(ValueError, match="illegal characters"):
            validate_safe_id("foo\\bar")

    def test_empty_string_rejected(self):
        from app.utils.validation import validate_safe_id
        with pytest.raises(ValueError, match="non-empty string"):
            validate_safe_id("")

    def test_too_long_rejected(self):
        from app.utils.validation import validate_safe_id
        with pytest.raises(ValueError, match="too long"):
            validate_safe_id("a" * 101)

    def test_exactly_100_chars_accepted(self):
        from app.utils.validation import validate_safe_id
        long_id = "a" * 100
        assert validate_safe_id(long_id) == long_id

    def test_semicolon_rejected(self):
        from app.utils.validation import validate_safe_id
        with pytest.raises(ValueError, match="must contain only"):
            validate_safe_id("proj;rm -rf")

    def test_dollar_sign_rejected(self):
        from app.utils.validation import validate_safe_id
        with pytest.raises(ValueError, match="illegal characters|must contain only"):
            validate_safe_id("proj$(cmd)")

    def test_spaces_rejected(self):
        from app.utils.validation import validate_safe_id
        with pytest.raises(ValueError, match="must contain only"):
            validate_safe_id("my project")

    def test_none_rejected(self):
        from app.utils.validation import validate_safe_id
        with pytest.raises(ValueError, match="non-empty string"):
            validate_safe_id(None)

    def test_custom_param_name_in_error(self):
        from app.utils.validation import validate_safe_id
        with pytest.raises(ValueError, match="Invalid project_id"):
            validate_safe_id("", param_name="project_id")

    def test_dot_rejected(self):
        from app.utils.validation import validate_safe_id
        with pytest.raises(ValueError, match="must contain only"):
            validate_safe_id("file.txt")

    def test_single_dot_dot_substring_rejected(self):
        from app.utils.validation import validate_safe_id
        with pytest.raises(ValueError, match="illegal characters"):
            validate_safe_id("a..b")
