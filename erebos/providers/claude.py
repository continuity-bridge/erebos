"""
erebos/providers/claude.py

Anthropic Claude provider client.

Supports both streaming and non-streaming chat via the Anthropic SDK.
Token usage is reported after every response so TokenMonitor stays current.

Configuration (cloud nodule):
    {
        "label":       "Claude API",
        "provider":    "anthropic",
        "location":    "cloud",
        "priority":    10,
        "enabled":     true,
        "api_key_env": "ANTHROPIC_API_KEY",   # env var holding the key
        "default_model": "claude-sonnet-4-6"
    }

System messages:
    Messages with role "system" are extracted from the messages list and
    passed as Anthropic's top-level `system=` parameter. All remaining
    messages are forwarded as-is.
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Generator, Optional

from anthropic import Anthropic, APIConnectionError, APIStatusError, APITimeoutError

from .base import (
    ProviderClient,
    ProviderStatus,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderRateLimitError,
    ProviderModelNotFoundError,
    ProviderResponseError,
)

logger = logging.getLogger(__name__)

# Models available via the Anthropic API.
# Update as new models ship — this list is for `erebos list` display only.
KNOWN_MODELS = [
    "claude-opus-4-8",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
]

DEFAULT_MODEL     = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 8192
HEALTH_MAX_TOKENS  = 1      # minimal spend for health check


class ClaudeClient(ProviderClient):
    """
    Provider client for Anthropic Claude (cloud API).

    Capabilities:
        - Non-streaming chat        ✓
        - Streaming chat            ✓
        - Conversation history      ✓
        - Model listing             ✓ (static list — Anthropic has no list endpoint)
        - Health check              ✓ (tiny API call to verify key)
        - Token usage reporting     ✓ (feeds TokenMonitor directly)
        - Auth                      ✓ (API key via env var or constructor)
        - Rate limiting             ✓ (surfaces ProviderRateLimitError with retry_after)
    """

    provider_name: str = "anthropic"
    provider_type: str = "cloud"

    supports_streaming: bool    = True
    supports_conversation: bool = True

    def __init__(
        self,
        api_key: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        label: Optional[str] = None,
        **config,
    ):
        """
        Args:
            api_key:    Anthropic API key. Falls back to ANTHROPIC_API_KEY env var.
            max_tokens: Max tokens per response (default 8192).
            label:      Human-readable name for display/logging.
        """
        super().__init__(**config)
        self.api_key    = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.max_tokens = max_tokens
        self.label      = label or "Claude API"

        self._client: Optional[Anthropic] = None
        self._last_healthy: Optional[datetime] = None

    # ---------------------------------------------------------------------------
    # Internal: lazy SDK client
    # ---------------------------------------------------------------------------

    def _get_client(self) -> Anthropic:
        """Return (or create) the Anthropic SDK client."""
        if self._client is None:
            if not self.api_key:
                raise ProviderAuthError(
                    "No API key — set ANTHROPIC_API_KEY or pass api_key=",
                    provider=self.provider_name,
                )
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    # ---------------------------------------------------------------------------
    # Message format helpers
    # ---------------------------------------------------------------------------

    @staticmethod
    def _split_system(messages: list[dict]) -> tuple[Optional[str], list[dict]]:
        """
        Extract system messages from the messages list.

        Returns (system_prompt, remaining_messages).
        Multiple system messages are joined with newlines.
        """
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        user_messages = [m for m in messages if m.get("role") != "system"]
        system = "\n\n".join(system_parts) if system_parts else None
        return system, user_messages

    # ---------------------------------------------------------------------------
    # Token reporting
    # ---------------------------------------------------------------------------

    def _report_tokens(self, input_tokens: int, output_tokens: int):
        """Update TokenMonitor with cumulative token count if one is attached."""
        if self.token_monitor is not None:
            total = input_tokens + output_tokens
            self.token_monitor.update(total)
            logger.debug(
                f"Token usage: {input_tokens} in + {output_tokens} out = {total} total"
            )

    # ---------------------------------------------------------------------------
    # Public Interface
    # ---------------------------------------------------------------------------

    def list_models(self) -> list[str]:
        """Return known Claude model identifiers (static list)."""
        return list(KNOWN_MODELS)

    def health_check(self) -> ProviderStatus:
        """
        Verify the API key is valid and the API is reachable.

        Makes a minimal 1-token request. Not free, but there's no cheaper
        Anthropic endpoint that confirms key validity.

        Never raises — all exceptions captured into ProviderStatus.
        """
        start = time.monotonic()

        try:
            client = self._get_client()
            client.messages.create(
                model=DEFAULT_MODEL,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=HEALTH_MAX_TOKENS,
            )
            latency_ms = (time.monotonic() - start) * 1000
            self._last_healthy = datetime.now(timezone.utc)

            return ProviderStatus(
                available=True,
                provider_name=self.provider_name,
                latency_ms=latency_ms,
                last_healthy=self._last_healthy,
            )

        except APIStatusError as e:
            latency_ms = (time.monotonic() - start) * 1000
            if e.status_code == 401:
                error = ProviderAuthError(
                    f"Invalid API key (HTTP 401)",
                    provider=self.provider_name,
                )
            elif e.status_code == 429:
                error = ProviderRateLimitError(
                    "Rate limited during health check",
                    provider=self.provider_name,
                )
            else:
                error = ProviderResponseError(
                    f"HTTP {e.status_code}: {e.message}",
                    provider=self.provider_name,
                )
            return ProviderStatus(
                available=False,
                provider_name=self.provider_name,
                latency_ms=latency_ms,
                last_healthy=self._last_healthy,
                error=error,
                error_message=str(error),
            )

        except (APIConnectionError, APITimeoutError) as e:
            latency_ms = (time.monotonic() - start) * 1000
            error = ProviderConnectionError(str(e), provider=self.provider_name)
            return ProviderStatus(
                available=False,
                provider_name=self.provider_name,
                latency_ms=latency_ms,
                last_healthy=self._last_healthy,
                error=error,
                error_message=str(e),
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return ProviderStatus(
                available=False,
                provider_name=self.provider_name,
                latency_ms=latency_ms,
                last_healthy=self._last_healthy,
                error_message=str(e),
            )

    # ---------------------------------------------------------------------------
    # Transport Implementation
    # ---------------------------------------------------------------------------

    def _chat(self, model: str, messages: list[dict]) -> str:
        """
        Non-streaming Claude request.

        Returns the complete response text.
        Reports token usage to TokenMonitor if attached.
        """
        system, filtered = self._split_system(messages)

        kwargs = dict(
            model=model,
            messages=filtered,
            max_tokens=self.max_tokens,
        )
        if system:
            kwargs["system"] = system

        try:
            response = self._get_client().messages.create(**kwargs)

            self._report_tokens(
                response.usage.input_tokens,
                response.usage.output_tokens,
            )

            return response.content[0].text

        except APIStatusError as e:
            self._raise_from_status(e, model)

        except (APIConnectionError, APITimeoutError) as e:
            raise ProviderConnectionError(
                f"Connection failed: {e}", provider=self.provider_name, model=model
            ) from e

    def _stream_chat(self, model: str, messages: list[dict]) -> Generator:
        """
        Streaming Claude request.

        Yields text chunks as they arrive.
        Reports token usage after stream completes.
        """
        system, filtered = self._split_system(messages)

        kwargs = dict(
            model=model,
            messages=filtered,
            max_tokens=self.max_tokens,
        )
        if system:
            kwargs["system"] = system

        try:
            with self._get_client().messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield text

                # Token usage available after stream closes
                final = stream.get_final_message()
                self._report_tokens(
                    final.usage.input_tokens,
                    final.usage.output_tokens,
                )

        except APIStatusError as e:
            self._raise_from_status(e, model)

        except (APIConnectionError, APITimeoutError) as e:
            raise ProviderConnectionError(
                f"Stream connection failed: {e}", provider=self.provider_name, model=model
            ) from e

    # ---------------------------------------------------------------------------
    # Error mapping
    # ---------------------------------------------------------------------------

    def _raise_from_status(self, e: APIStatusError, model: Optional[str] = None):
        """Map Anthropic HTTP status codes to ProviderError subclasses."""
        if e.status_code == 401:
            raise ProviderAuthError(
                f"Invalid API key", provider=self.provider_name, model=model
            ) from e
        if e.status_code == 404:
            raise ProviderModelNotFoundError(
                f"Model '{model}' not found", provider=self.provider_name, model=model
            ) from e
        if e.status_code == 429:
            retry_after = None
            if hasattr(e, "response") and e.response:
                retry_after_str = e.response.headers.get("retry-after")
                if retry_after_str:
                    try:
                        retry_after = int(retry_after_str)
                    except ValueError:
                        pass
            raise ProviderRateLimitError(
                f"Rate limited: {e.message}",
                provider=self.provider_name,
                model=model,
                retry_after=retry_after,
            ) from e
        raise ProviderResponseError(
            f"HTTP {e.status_code}: {e.message}",
            provider=self.provider_name,
            model=model,
        ) from e

    def __repr__(self) -> str:
        return (
            f"ClaudeClient(label={self.label!r}, "
            f"max_tokens={self.max_tokens})"
        )
