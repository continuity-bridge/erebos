"""
Unit tests for ClaudeClient provider.
Uses mocks — no real API calls.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from erebos.providers.claude import ClaudeClient, KNOWN_MODELS
from erebos.providers.base import (
    ProviderAuthError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderModelNotFoundError,
)
from anthropic import APIStatusError, APIConnectionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_client(api_key="test-key"):
    return ClaudeClient(api_key=api_key, label="Test Claude")


def make_message_response(text="Hello!", input_tokens=10, output_tokens=5):
    """Build a mock Anthropic messages.create() response."""
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response


def make_api_status_error(status_code, message="error"):
    """Build a real APIStatusError with the given status code."""
    import httpx
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request, json={"error": {"message": message}})
    return APIStatusError(message, response=response, body={"error": message})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_list_models():
    client = make_client()
    models = client.list_models()
    assert len(models) > 0
    assert "claude-sonnet-4-6" in models
    assert models == KNOWN_MODELS


def test_split_system_no_system():
    system, msgs = ClaudeClient._split_system([
        {"role": "user", "content": "hello"}
    ])
    assert system is None
    assert msgs == [{"role": "user", "content": "hello"}]


def test_split_system_with_system():
    system, msgs = ClaudeClient._split_system([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "hello"},
    ])
    assert system == "You are helpful."
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"


def test_split_system_multiple_system():
    system, msgs = ClaudeClient._split_system([
        {"role": "system", "content": "Part 1."},
        {"role": "system", "content": "Part 2."},
        {"role": "user", "content": "hello"},
    ])
    assert "Part 1." in system
    assert "Part 2." in system


def test_chat_returns_text():
    client = make_client()
    mock_response = make_message_response(text="42")

    with patch.object(client, '_get_client') as mock_get:
        mock_get.return_value.messages.create.return_value = mock_response
        result = client._chat("claude-sonnet-4-6", [{"role": "user", "content": "hi"}])

    assert result == "42"


def test_chat_reports_tokens_to_monitor():
    client = make_client()
    monitor = MagicMock()
    client.token_monitor = monitor

    mock_response = make_message_response(input_tokens=100, output_tokens=50)

    with patch.object(client, '_get_client') as mock_get:
        mock_get.return_value.messages.create.return_value = mock_response
        client._chat("claude-sonnet-4-6", [{"role": "user", "content": "hi"}])

    monitor.update.assert_called_once_with(150)


def test_chat_no_monitor_no_error():
    """Token monitor is optional — no crash if absent."""
    client = make_client()
    assert client.token_monitor is None

    mock_response = make_message_response()
    with patch.object(client, '_get_client') as mock_get:
        mock_get.return_value.messages.create.return_value = mock_response
        result = client._chat("claude-sonnet-4-6", [{"role": "user", "content": "hi"}])

    assert result == "Hello!"


def test_chat_auth_error():
    client = make_client()
    with patch.object(client, '_get_client') as mock_get:
        mock_get.return_value.messages.create.side_effect = make_api_status_error(401)
        with pytest.raises(ProviderAuthError):
            client._chat("claude-sonnet-4-6", [{"role": "user", "content": "hi"}])


def test_chat_rate_limit_error():
    client = make_client()
    with patch.object(client, '_get_client') as mock_get:
        mock_get.return_value.messages.create.side_effect = make_api_status_error(429)
        with pytest.raises(ProviderRateLimitError):
            client._chat("claude-sonnet-4-6", [{"role": "user", "content": "hi"}])


def test_chat_model_not_found():
    client = make_client()
    with patch.object(client, '_get_client') as mock_get:
        mock_get.return_value.messages.create.side_effect = make_api_status_error(404)
        with pytest.raises(ProviderModelNotFoundError):
            client._chat("bad-model", [{"role": "user", "content": "hi"}])


def test_no_api_key_raises_auth_error():
    client = ClaudeClient(api_key="")
    with pytest.raises(ProviderAuthError):
        client._get_client()


def test_token_monitor_wired_via_attribute():
    """Verify token_monitor attribute exists on base class."""
    client = make_client()
    assert hasattr(client, "token_monitor")
    assert client.token_monitor is None
    monitor = MagicMock()
    client.token_monitor = monitor
    assert client.token_monitor is monitor
