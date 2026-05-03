"""
erebos/providers/base.py

Base provider interface for all LLM backends.
Supports both local/network providers (Ollama) and cloud API providers
(Anthropic, Gemini, OpenAI, etc).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generator, Optional


# ---------------------------------------------------------------------------
# Exception Hierarchy
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Base exception for all provider errors."""
    def __init__(self, message: str, provider: str, model: Optional[str] = None):
        self.provider = provider
        self.model = model
        super().__init__(f"[{provider}] {message}")


class ProviderConnectionError(ProviderError):
    """Cannot reach the provider endpoint.

    Local/network: host unreachable, port closed, timeout.
    Cloud: DNS failure, network down.
    """
    pass


class ProviderAuthError(ProviderError):
    """Authentication or authorization failure.

    Cloud: invalid API key, expired token, insufficient permissions.
    Local: not applicable (raises ProviderConnectionError instead).
    """
    pass


class ProviderRateLimitError(ProviderError):
    """Request refused due to rate limiting or quota exhaustion.

    Includes a retry_after hint in seconds when the provider supplies it.
    """
    def __init__(self, message: str, provider: str, model: Optional[str] = None,
                 retry_after: Optional[int] = None):
        self.retry_after = retry_after
        super().__init__(message, provider, model)


class ProviderModelNotFoundError(ProviderError):
    """Requested model does not exist or is not available on this provider."""
    pass


class ProviderResponseError(ProviderError):
    """Provider was reachable but returned an unexpected or malformed response."""
    pass


class ProviderCapabilityError(ProviderError):
    """Operation requested is not supported by this provider.

    Example: requesting streaming from a provider with supports_streaming = False.
    """
    pass


# ---------------------------------------------------------------------------
# Health Status
# ---------------------------------------------------------------------------

@dataclass
class ProviderStatus:
    """
    Full health and availability status for a provider.

    Returned by health_check() instead of a bare bool so the router
    has enough context to make smart decisions: retry timing, error
    classification, staleness detection, last-known-good tracking.

    available: False means do not route to this provider right now.
    """
    available: bool
    provider_name: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Populated on failure
    error: Optional[ProviderError] = None
    error_message: Optional[str] = None

    # Latency of the health check itself in milliseconds
    latency_ms: Optional[float] = None

    # Last time this provider was confirmed healthy
    last_healthy: Optional[datetime] = None

    # For local/network providers
    endpoint: Optional[str] = None

    # For cloud providers
    quota_remaining: Optional[int] = None
    rate_limit_reset: Optional[datetime] = None

    @property
    def is_rate_limited(self) -> bool:
        return isinstance(self.error, ProviderRateLimitError)

    @property
    def is_auth_failure(self) -> bool:
        return isinstance(self.error, ProviderAuthError)

    @property
    def is_unreachable(self) -> bool:
        return isinstance(self.error, ProviderConnectionError)

    @property
    def seconds_since_check(self) -> float:
        return (datetime.now(timezone.utc) - self.checked_at).total_seconds()

    def __str__(self) -> str:
        status = "✓ available" if self.available else "✗ unavailable"
        latency = f" ({self.latency_ms:.0f}ms)" if self.latency_ms is not None else ""
        error = f" — {self.error_message}" if self.error_message else ""
        return f"[{self.provider_name}] {status}{latency}{error}"


# ---------------------------------------------------------------------------
# Abstract Metadata Descriptor
# Enforces provider_name and provider_type at class definition time.
# ---------------------------------------------------------------------------

class _RequiredClassVar:
    """Descriptor that raises TypeError if a subclass doesn't override."""
    def __init__(self, name: str, expected_type: type):
        self.name = name
        self.expected_type = expected_type

    def __set_name__(self, owner, name):
        self.attr = name

    def __get__(self, obj, objtype=None):
        raise TypeError(
            f"{objtype.__name__} must define class variable "
            f"'{self.name}' as a non-empty {self.expected_type.__name__}"
        )


# ---------------------------------------------------------------------------
# Base Provider
# ---------------------------------------------------------------------------

class ProviderClient(ABC):
    """
    Abstract base class for all LLM provider clients.

    Subclasses MUST declare:
        provider_name: str   — e.g. "ollama", "anthropic", "gemini"
        provider_type: str   — one of "local", "network", "cloud"

    Subclasses declare capabilities via class variables:
        supports_streaming:    bool (default False)
        supports_conversation: bool (default True)

    Subclasses implement:
        _chat()         — non-streaming request
        _stream_chat()  — streaming request (if supports_streaming = True)
        list_models()   — available model identifiers
        health_check()  — returns ProviderStatus, must not raise

    The public chat() method handles capability checking, event emission,
    and error normalization so subclasses don't have to.

    Conversation continuity:
        Messages are passed as a list of {"role": ..., "content": ...} dicts.
        The caller is responsible for building and persisting message history
        between runs. A single-turn prompt is just a one-entry list.
    """

    # Enforced: subclasses must override these or instantiation fails loudly
    provider_name: str = _RequiredClassVar("provider_name", str)
    provider_type: str = _RequiredClassVar("provider_type", str)

    # Declared capabilities — override in subclasses
    supports_streaming: bool = False
    supports_conversation: bool = True

    def __init_subclass__(cls, **kwargs):
        """Validate required class variables at subclass definition time."""
        super().__init_subclass__(**kwargs)

        # Skip validation on abstract subclasses
        if ABC in cls.__bases__:
            return

        for var in ("provider_name", "provider_type"):
            val = cls.__dict__.get(var)
            if val is None:
                raise TypeError(
                    f"{cls.__name__} must define class variable '{var}'"
                )
            if not isinstance(val, str) or not val.strip():
                raise TypeError(
                    f"{cls.__name__}.{var} must be a non-empty string, got {val!r}"
                )

        valid_types = ("local", "network", "cloud")
        if cls.__dict__.get("provider_type") not in valid_types:
            raise TypeError(
                f"{cls.__name__}.provider_type must be one of {valid_types}, "
                f"got {cls.__dict__.get('provider_type')!r}"
            )

    def __init__(self, event_bus=None, **config):
        # NEW: Initialize the emitter with the provided bus
        self.event_bus = event_bus
        self.event_emitter = EventEmitter(event_bus) if event_bus else None

    # ---------------------------------------------------------------------------
    # Public Interface
    # ---------------------------------------------------------------------------

    def chat(self, model: str, messages: list[dict],
             stream: bool = False) -> "str | Generator":
        """
        Send a chat request to the provider.

        Args:
            model:    Model identifier (e.g. "llama3.1:8b", "claude-sonnet-4-5")
            messages: Conversation history as list of {"role": ..., "content": ...}
                      Single-turn: [{"role": "user", "content": "your prompt"}]
            stream:   If True, returns a Generator yielding response chunks.
                      Raises ProviderCapabilityError if provider doesn't support it.

        Returns:
            str if stream=False, Generator[str, None, None] if stream=True.

        Raises:
            ProviderCapabilityError:    stream=True but provider doesn't support it.
            ProviderConnectionError:    Cannot reach provider endpoint.
            ProviderAuthError:          Authentication failed.
            ProviderRateLimitError:     Rate limit or quota exceeded.
            ProviderModelNotFoundError: Model not available on this provider.
            ProviderResponseError:      Unexpected response from provider.
        """
        if stream and not self.supports_streaming:
            raise ProviderCapabilityError(
                f"Streaming not supported by {self.provider_name}",
                provider=self.provider_name,
                model=model
            )

        tool_name = f"{self.provider_name}:{model}"
        tool_family = self.provider_name

        try:
            if stream:
                return self._stream_with_events(model, messages, tool_name, tool_family)
            else:
                result = self._chat(model, messages)
                self._emit_success(tool_name, tool_family)
                return result

        except ProviderError:
            self._emit_failure(tool_name, tool_family)
            raise
        except Exception as e:
            self._emit_failure(tool_name, tool_family)
            raise ProviderResponseError(
                f"Unexpected error: {e}",
                provider=self.provider_name,
                model=model
            ) from e

    @abstractmethod
    def list_models(self) -> list[str]:
        """
        Return list of model identifiers available from this provider.

        Raises:
            ProviderConnectionError: Cannot reach provider.
            ProviderAuthError:       Auth failed (cloud providers).
        """
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> ProviderStatus:
        """
        Return a ProviderStatus reflecting current availability.

        Must never raise — catch all exceptions internally and reflect
        them in the returned ProviderStatus. The router relies on this
        contract to poll providers without defensive try/catch everywhere.

        Implementations should:
            - Measure and populate latency_ms
            - Populate endpoint (local/network) or quota_remaining (cloud)
            - Set last_healthy when available=True
            - Wrap caught exceptions in the appropriate ProviderError subclass
              and attach to status.error
        """
        raise NotImplementedError

    # ---------------------------------------------------------------------------
    # Abstract Transport Methods (implement in subclasses)
    # ---------------------------------------------------------------------------

    @abstractmethod
    def _chat(self, model: str, messages: list[dict]) -> str:
        """Send non-streaming request. Return complete response string."""
        raise NotImplementedError

    def _stream_chat(self, model: str, messages: list[dict]) -> Generator:
        """
        Send streaming request. Yield response chunks as strings.

        Only required if supports_streaming = True. Default raises
        ProviderCapabilityError so subclasses can't forget to implement
        it when they set the flag.
        """
        raise ProviderCapabilityError(
            f"{self.provider_name} declared supports_streaming=True "
            f"but did not implement _stream_chat()",
            provider=self.provider_name
        )

    # ---------------------------------------------------------------------------
    # Internal Helpers
    # ---------------------------------------------------------------------------

    def _stream_with_events(self, model: str, messages: list[dict],
                            tool_name: str, tool_family: str) -> Generator:
        """Wrap _stream_chat with event emission."""
        try:
            for chunk in self._stream_chat(model, messages):
                yield chunk
            self._emit_success(tool_name, tool_family)
        except ProviderError:
            self._emit_failure(tool_name, tool_family)
            raise
        except Exception as e:
            self._emit_failure(tool_name, tool_family)
            raise ProviderResponseError(
                f"Unexpected streaming error: {e}",
                provider=self.provider_name,
                model=model
            ) from e

    def _emit_success(self, tool_name: str, tool_family: str):
        if self.event_emitter:
            self.event_emitter.tool_succeeded(tool_name, tool_family)

    def _emit_failure(self, tool_name: str, tool_family: str):
        if self.event_emitter:
            self.event_emitter.tool_failed(tool_name, tool_family)