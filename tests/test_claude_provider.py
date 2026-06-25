"""Provider-logic tests for claude.py with a MOCKED Anthropic SDK — proves the
provider's request shaping, response parsing, token reporting, and error mapping
WITHOUT a real API key or network call."""
import types
import pytest
from unittest.mock import patch, MagicMock
from anthropic import APIStatusError

from erebos.providers.claude import ClaudeClient
from erebos.providers.base import (
    ProviderAuthError, ProviderModelNotFoundError,
    ProviderRateLimitError, ProviderResponseError,
)

def _resp(text="pong", tin=12, tout=3):
    return types.SimpleNamespace(
        usage=types.SimpleNamespace(input_tokens=tin, output_tokens=tout),
        content=[types.SimpleNamespace(text=text)],
    )

class _Monitor:
    def __init__(self): self.total = None
    def update(self, t): self.total = t

def _status_err(code, msg="boom", headers=None):
    e = APIStatusError.__new__(APIStatusError)   # bypass __init__
    e.status_code = code; e.message = msg
    e.response = types.SimpleNamespace(headers=headers or {})
    return e

@patch("erebos.providers.claude.Anthropic")
def test_chat_happy_path_and_request_shape(MockAnthropic):
    fake = MagicMock()
    fake.messages.create.return_value = _resp("pong", 12, 3)
    MockAnthropic.return_value = fake

    c = ClaudeClient(api_key="test-key")
    c.token_monitor = _Monitor()
    out = c._chat("claude-haiku-4-5", [
        {"role": "system", "content": "be terse"},
        {"role": "user", "content": "ping"},
    ])
    assert out == "pong"
    # token reporting fired with the sum
    assert c.token_monitor.total == 15
    # system was split out; create got the right kwargs
    kwargs = fake.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-haiku-4-5"
    assert kwargs["system"] == "be terse"
    assert kwargs["messages"] == [{"role": "user", "content": "ping"}]
    assert "max_tokens" in kwargs

@patch("erebos.providers.claude.Anthropic")
def test_stream_chat_yields_and_reports(MockAnthropic):
    fake = MagicMock()
    class _Stream:
        text_stream = iter(["po", "ng"])
        def get_final_message(self):
            return _resp("pong", 9, 6)
        def __enter__(self): return self
        def __exit__(self, *a): return False
    fake.messages.stream.return_value = _Stream()
    MockAnthropic.return_value = fake

    c = ClaudeClient(api_key="test-key"); c.token_monitor = _Monitor()
    chunks = list(c._stream_chat("claude-haiku-4-5", [{"role": "user", "content": "ping"}]))
    assert "".join(chunks) == "pong"
    assert c.token_monitor.total == 15

def test_split_system():
    sys, rest = ClaudeClient._split_system([
        {"role": "system", "content": "A"}, {"role": "system", "content": "B"},
        {"role": "user", "content": "hi"},
    ])
    assert sys == "A\n\nB"
    assert rest == [{"role": "user", "content": "hi"}]

def test_no_key_raises():
    import os
    c = ClaudeClient(api_key="")
    old = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        with pytest.raises(ProviderAuthError):
            c._get_client()
    finally:
        if old: os.environ["ANTHROPIC_API_KEY"] = old

@pytest.mark.parametrize("code,exc", [
    (401, ProviderAuthError),
    (404, ProviderModelNotFoundError),
    (429, ProviderRateLimitError),
    (500, ProviderResponseError),
])
def test_error_mapping(code, exc):
    c = ClaudeClient(api_key="test-key")
    with pytest.raises(exc):
        c._raise_from_status(_status_err(code), model="claude-haiku-4-5")

def test_rate_limit_retry_after_parsed():
    c = ClaudeClient(api_key="test-key")
    try:
        c._raise_from_status(_status_err(429, headers={"retry-after": "7"}), model="m")
    except ProviderRateLimitError as e:
        assert getattr(e, "retry_after", None) == 7
    else:
        pytest.fail("expected ProviderRateLimitError")
