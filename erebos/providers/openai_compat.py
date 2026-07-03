"""
erebos/providers/openai_compat.py

OpenAI-compatible provider client for any endpoint that speaks the
/v1/chat/completions API — llama-swap, llama.cpp server, LM Studio,
vLLM, Tailscale Aperture routing to any of the above, etc.

Provider type is determined by base_url at instantiation:
    - "local"   : base_url points to localhost / 127.0.0.1
    - "network" : base_url points to any other host (Tailscale IP,
                  LAN IP, or public hostname)

This is intentionally NOT an openai-sdk dependency. Raw requests only,
same as the Ollama provider — keeps transport under our control and
avoids SDK churn. The OpenAI SDK is overkill for what erebos needs here.
"""

import json as _json
import socket
import time
import logging
from datetime import datetime, timezone
from typing import Generator, Optional

import requests

from .base import (
    ProviderClient,
    ProviderStatus,
    ProviderConnectionError,
    ProviderAuthError,
    ProviderModelNotFoundError,
    ProviderResponseError,
    ProviderRateLimitError,
    ProviderCapabilityError,
)

logger = logging.getLogger(__name__)


def _infer_provider_type(base_url: str) -> str:
    """Determine if this is a local or network endpoint from the URL."""
    local_hosts = ("localhost", "127.0.0.1", "::1")
    try:
        host = base_url.split("//")[-1].split(":")[0]
        return "local" if host in local_hosts else "network"
    except Exception:
        return "network"


class OpenAICompatClient(ProviderClient):
    """
    Provider client for any OpenAI-compatible /v1/chat/completions endpoint.

    Designed for llama-swap on Hephaestus (the primary use case) but
    generic enough to front any compatible server — including Tailscale
    Aperture when it's routing to a local backend.

    The operator or cognate chooses which model to use explicitly.
    llama-swap handles model aliasing on its end (e.g. a request for
    "creative-gemma4-opus" routes to the right GGUF). This client just
    passes the model string through — no opinions about what runs where.

    Capabilities:
        - Non-streaming chat        ✓
        - Streaming chat            ✓
        - Conversation history      ✓
        - Model listing             ✓  (via /v1/models)
        - Health check              ✓
        - Auth (API key)            ✓  (optional — llama-swap supports it,
                                        pass None if endpoint has no auth)
        - Rate limiting             ✓  (handles 429 from Aperture/cloud)
        - Token usage reporting     ✗  (available in response but not
                                        surfaced yet — add if needed)

    Configuration:
        base_url  : Endpoint root, e.g. "http://100.126.134.91:8081"
                    Do NOT include /v1 — this client appends it.
        api_key   : Bearer token if the endpoint requires auth.
                    Pass None for unauthenticated local endpoints.
        timeout   : Request timeout in seconds (default: 60 — longer than
                    Ollama default because llama.cpp model load can be slow)
        label     : Human-readable name for display/logging
    """

    provider_name: str = "openai_compat"
    provider_type: str = "network"  # Overridden at __init__ based on base_url

    supports_streaming: bool = True
    supports_conversation: bool = True

    DEFAULT_PORT = 8081  # llama-swap default in this setup
    DEFAULT_TIMEOUT = 60  # longer than Ollama — model load latency
    HEALTH_TIMEOUT = 5   # slightly longer than Ollama for network hops

    def __init__(
        self,
        base_url: str = "http://localhost:8081",
        api_key: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
        label: Optional[str] = None,
        event_bus=None,
        **config,
    ):
        """
        Args:
            base_url : Endpoint root URL (no trailing slash, no /v1)
            api_key  : Bearer token for auth — None if endpoint has no auth
            timeout  : Request timeout for chat calls in seconds
            label    : Human-readable label for logging/display
        """
        super().__init__(event_bus=event_bus, **config)
        self.base_url = base_url.rstrip("/").rstrip("/v1").rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.label = label or base_url

        # Instance-level type based on actual URL
        self.provider_type = _infer_provider_type(base_url)

        self._last_healthy: Optional[datetime] = None

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def _headers(self) -> dict:
        """Build request headers. Includes Bearer auth only if api_key is set."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _v1(self, path: str) -> str:
        """Build a full /v1/... URL."""
        return f"{self.base_url}/v1/{path.lstrip('/')}"

    # ---------------------------------------------------------------------------
    # Public Interface
    # ---------------------------------------------------------------------------

    def list_models(self) -> list[str]:
        """
        Return list of model identifiers available on this endpoint.

        Uses GET /v1/models (standard OpenAI endpoint).

        Raises:
            ProviderConnectionError: Cannot reach endpoint.
            ProviderAuthError:       401/403 from endpoint.
            ProviderResponseError:   Unexpected response format.
        """
        try:
            response = requests.get(
                self._v1("models"),
                headers=self._headers(),
                timeout=self.HEALTH_TIMEOUT,
            )

            if response.status_code in (401, 403):
                raise ProviderAuthError(
                    f"Auth failed for {self.base_url} — check api_key",
                    provider=self.provider_name,
                )

            response.raise_for_status()
            data = response.json()

            # OpenAI format: {"object": "list", "data": [{"id": "model-name"}, ...]}
            return [m["id"] for m in data.get("data", [])]

        except ProviderAuthError:
            raise
        except requests.exceptions.ConnectionError as e:
            raise ProviderConnectionError(
                f"Cannot reach {self.base_url}",
                provider=self.provider_name,
            ) from e
        except requests.exceptions.Timeout as e:
            raise ProviderConnectionError(
                f"Timed out listing models from {self.base_url}",
                provider=self.provider_name,
            ) from e
        except (KeyError, ValueError) as e:
            raise ProviderResponseError(
                f"Malformed model list response from {self.base_url}: {e}",
                provider=self.provider_name,
            ) from e
        except requests.exceptions.HTTPError as e:
            raise ProviderResponseError(
                f"HTTP error listing models: {e}",
                provider=self.provider_name,
            ) from e

    def health_check(self) -> ProviderStatus:
        """
        Check if this endpoint is reachable and responsive.

        Socket check first (fast), then /v1/models API check.
        Never raises — all exceptions captured into ProviderStatus.
        """
        start = time.monotonic()
        raw_host = self.base_url.split("//")[-1].split(":")[0]
        try:
            port_str = self.base_url.split("//")[-1].split(":")[1].split("/")[0]
            port = int(port_str)
        except (IndexError, ValueError):
            port = self.DEFAULT_PORT

        # Phase 1: socket check
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.HEALTH_TIMEOUT)
            result = sock.connect_ex((raw_host, port))
            sock.close()

            if result != 0:
                latency_ms = (time.monotonic() - start) * 1000
                return ProviderStatus(
                    available=False,
                    provider_name=self.provider_name,
                    latency_ms=latency_ms,
                    endpoint=self.base_url,
                    last_healthy=self._last_healthy,
                    error=ProviderConnectionError(
                        f"Port {port} closed on {raw_host}",
                        provider=self.provider_name,
                    ),
                    error_message=f"Port {port} closed on {raw_host}",
                )
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            return ProviderStatus(
                available=False,
                provider_name=self.provider_name,
                latency_ms=latency_ms,
                endpoint=self.base_url,
                last_healthy=self._last_healthy,
                error=ProviderConnectionError(str(e), provider=self.provider_name),
                error_message=str(e),
            )

        # Phase 2: API check
        try:
            response = requests.get(
                self._v1("models"),
                headers=self._headers(),
                timeout=self.HEALTH_TIMEOUT,
            )

            if response.status_code in (401, 403):
                latency_ms = (time.monotonic() - start) * 1000
                err = ProviderAuthError(
                    f"Auth failed — check api_key for {self.base_url}",
                    provider=self.provider_name,
                )
                return ProviderStatus(
                    available=False,
                    provider_name=self.provider_name,
                    latency_ms=latency_ms,
                    endpoint=self.base_url,
                    last_healthy=self._last_healthy,
                    error=err,
                    error_message=str(err),
                )

            response.raise_for_status()
            latency_ms = (time.monotonic() - start) * 1000
            self._last_healthy = datetime.now(timezone.utc)

            return ProviderStatus(
                available=True,
                provider_name=self.provider_name,
                latency_ms=latency_ms,
                endpoint=self.base_url,
                last_healthy=self._last_healthy,
            )

        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            error = ProviderConnectionError(
                f"API unresponsive at {self.base_url}: {e}",
                provider=self.provider_name,
            )
            return ProviderStatus(
                available=False,
                provider_name=self.provider_name,
                latency_ms=latency_ms,
                endpoint=self.base_url,
                last_healthy=self._last_healthy,
                error=error,
                error_message=str(e),
            )

    # ---------------------------------------------------------------------------
    # Transport Implementation
    # ---------------------------------------------------------------------------

    def _chat(self, model: str, messages: list[dict]) -> str:
        """
        Send a non-streaming chat request.

        Args:
            model:    Model identifier passed through to the endpoint.
                      llama-swap handles aliasing on its end.
            messages: Conversation history as list of role/content dicts.

        Returns:
            Complete response string (content field from first choice).

        Raises:
            ProviderAuthError:          401/403 from endpoint.
            ProviderRateLimitError:     429 from endpoint.
            ProviderModelNotFoundError: Model not found (404).
            ProviderConnectionError:    Cannot reach endpoint.
            ProviderResponseError:      Unexpected response.
        """
        try:
            response = requests.post(
                self._v1("chat/completions"),
                headers=self._headers(),
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                },
                timeout=self.timeout,
            )

            if response.status_code in (401, 403):
                raise ProviderAuthError(
                    f"Auth failed for {self.base_url}",
                    provider=self.provider_name,
                    model=model,
                )
            if response.status_code == 404:
                raise ProviderModelNotFoundError(
                    f"Model '{model}' not found on {self.base_url}. "
                    f"Check llama-swap config for this alias.",
                    provider=self.provider_name,
                    model=model,
                )
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 0)) or None
                raise ProviderRateLimitError(
                    f"Rate limited by {self.base_url}",
                    provider=self.provider_name,
                    model=model,
                    retry_after=retry_after,
                )

            response.raise_for_status()
            data = response.json()

            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                raise ProviderResponseError(
                    f"Unexpected response structure: missing {e}",
                    provider=self.provider_name,
                    model=model,
                ) from e

        except (ProviderAuthError, ProviderModelNotFoundError,
                ProviderRateLimitError, ProviderResponseError):
            raise
        except requests.exceptions.ConnectionError as e:
            raise ProviderConnectionError(
                f"Cannot reach {self.base_url}",
                provider=self.provider_name,
                model=model,
            ) from e
        except requests.exceptions.Timeout as e:
            raise ProviderConnectionError(
                f"Request timed out after {self.timeout}s — "
                f"model may still be loading on llama-swap",
                provider=self.provider_name,
                model=model,
            ) from e
        except requests.exceptions.HTTPError as e:
            raise ProviderResponseError(
                f"HTTP error: {e}",
                provider=self.provider_name,
                model=model,
            ) from e

    def _stream_chat(self, model: str, messages: list[dict]) -> Generator:
        """
        Send a streaming chat request.

        Yields response text chunks as they arrive (SSE delta content).

        Args:
            model:    Model identifier.
            messages: Conversation history.

        Yields:
            str chunks of the response.

        Raises:
            ProviderAuthError:          401/403.
            ProviderRateLimitError:     429.
            ProviderModelNotFoundError: 404.
            ProviderConnectionError:    Cannot reach endpoint or timeout.
            ProviderResponseError:      Unexpected response or parse error.
        """
        try:
            with requests.post(
                self._v1("chat/completions"),
                headers=self._headers(),
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                },
                timeout=self.timeout,
                stream=True,
            ) as response:

                if response.status_code in (401, 403):
                    raise ProviderAuthError(
                        f"Auth failed for {self.base_url}",
                        provider=self.provider_name,
                        model=model,
                    )
                if response.status_code == 404:
                    raise ProviderModelNotFoundError(
                        f"Model '{model}' not found on {self.base_url}.",
                        provider=self.provider_name,
                        model=model,
                    )
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 0)) or None
                    raise ProviderRateLimitError(
                        f"Rate limited by {self.base_url}",
                        provider=self.provider_name,
                        model=model,
                        retry_after=retry_after,
                    )

                response.raise_for_status()

                for line in response.iter_lines():
                    if not line:
                        continue
                    # SSE format: "data: {...}" or "data: [DONE]"
                    decoded = line.decode("utf-8") if isinstance(line, bytes) else line
                    if not decoded.startswith("data:"):
                        continue
                    payload = decoded[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = _json.loads(payload)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (_json.JSONDecodeError, IndexError) as e:
                        raise ProviderResponseError(
                            f"Failed to parse streaming chunk: {e}",
                            provider=self.provider_name,
                            model=model,
                        ) from e

        except (ProviderAuthError, ProviderModelNotFoundError,
                ProviderRateLimitError, ProviderResponseError):
            raise
        except requests.exceptions.ConnectionError as e:
            raise ProviderConnectionError(
                f"Cannot reach {self.base_url}",
                provider=self.provider_name,
                model=model,
            ) from e
        except requests.exceptions.Timeout as e:
            raise ProviderConnectionError(
                f"Stream timed out after {self.timeout}s",
                provider=self.provider_name,
                model=model,
            ) from e
        except requests.exceptions.HTTPError as e:
            raise ProviderResponseError(
                f"HTTP error during stream: {e}",
                provider=self.provider_name,
                model=model,
            ) from e

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def __repr__(self) -> str:
        auth = "key=***" if self.api_key else "no auth"
        return (
            f"OpenAICompatClient(base_url={self.base_url!r}, "
            f"type={self.provider_type!r}, "
            f"{auth}, "
            f"label={self.label!r})"
        )
