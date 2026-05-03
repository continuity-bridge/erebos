"""
erebos/providers/ollama.py

Ollama provider client for local and network-hosted Ollama instances.
Supports both localhost and LAN-hosted Ollama (e.g. a dedicated machine
with dedicated VRAM).

Provider type is determined by the base_url at instantiation:
    - "local"   : base_url points to localhost / 127.0.0.1
    - "network" : base_url points to any other host
"""

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
    ProviderModelNotFoundError,
    ProviderResponseError,
    ProviderCapabilityError,
)

logger = logging.getLogger(__name__)

# Ollama has no auth layer, so ProviderAuthError is intentionally not imported.
# ProviderRateLimitError is also not applicable — Ollama doesn't rate-limit.


def _infer_provider_type(base_url: str) -> str:
    """Determine if this is a local or network Ollama instance from the URL."""
    local_hosts = ("localhost", "127.0.0.1", "::1")
    try:
        host = base_url.split("//")[-1].split(":")[0]
        return "local" if host in local_hosts else "network"
    except Exception:
        return "network"


class OllamaClient(ProviderClient):
    """
    Provider client for Ollama instances (local or network).

    Ollama exposes a REST API — no SDK dependency, raw requests only.
    This keeps the transport layer under our control and avoids
    provider-specific package churn.

    Capabilities:
        - Non-streaming chat        ✓
        - Streaming chat            ✓
        - Conversation history      ✓
        - Model listing             ✓
        - Health check              ✓
        - Auth                      ✗ (Ollama has no auth layer)
        - Rate limiting             ✗ (Ollama doesn't rate-limit)
        - Token usage reporting     ✗ (not exposed by Ollama API)

    Configuration:
        base_url    : Ollama endpoint (default: http://localhost:11434)
        timeout     : Request timeout in seconds (default: 30)
        label       : Human-readable name for display/logging
    """

    provider_name: str = "ollama"
    provider_type: str = "local"  # Overridden at __init__ based on base_url

    supports_streaming: bool = True
    supports_conversation: bool = True

    DEFAULT_PORT = 11434
    DEFAULT_TIMEOUT = 30
    HEALTH_TIMEOUT = 2  # Faster timeout for health/discovery checks

    def __init__(self, base_url: str = "http://localhost:11434",
                 timeout: int = DEFAULT_TIMEOUT,
                 label: Optional[str] = None,
                 event_bus=None,  # Add this parameter
                 **config):
        """
        Args:
            base_url : Ollama endpoint URL
            timeout  : Request timeout for chat calls in seconds
            label    : Human-readable label (used in logging and status display)
        """
        # Pass event_bus and any other config to the base class
        super().__init__(event_bus=event_bus, **config)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.label = label or base_url

        # Override provider_type based on actual URL — instance-level,
        # doesn't affect the class variable
        self.provider_type = _infer_provider_type(base_url)

        self._last_healthy: Optional[datetime] = None

    # ---------------------------------------------------------------------------
    # Public Interface
    # ---------------------------------------------------------------------------

    def list_models(self) -> list[str]:
        """
        Return list of model identifiers available on this Ollama instance.

        Raises:
            ProviderConnectionError: Cannot reach Ollama endpoint.
            ProviderResponseError:   Unexpected response format.
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=self.HEALTH_TIMEOUT
            )
            response.raise_for_status()
            return [m["name"] for m in response.json().get("models", [])]

        except requests.exceptions.ConnectionError as e:
            raise ProviderConnectionError(
                f"Cannot reach Ollama at {self.base_url}",
                provider=self.provider_name
            ) from e
        except requests.exceptions.Timeout as e:
            raise ProviderConnectionError(
                f"Timed out listing models from {self.base_url}",
                provider=self.provider_name
            ) from e
        except (KeyError, ValueError) as e:
            raise ProviderResponseError(
                f"Malformed model list response from {self.base_url}: {e}",
                provider=self.provider_name
            ) from e
        except requests.exceptions.HTTPError as e:
            raise ProviderResponseError(
                f"HTTP error listing models: {e}",
                provider=self.provider_name
            ) from e

    def health_check(self) -> ProviderStatus:
        """
        Check if this Ollama instance is reachable and responsive.

        Attempts a socket connection first (fast), then verifies the
        API responds correctly (confirms it's actually Ollama).

        Never raises — all exceptions are captured into ProviderStatus.
        """
        start = time.monotonic()
        host = self.base_url.split("//")[-1].split(":")[0]
        port = int(self.base_url.split(":")[-1]) if ":" in self.base_url.split("//")[-1] else self.DEFAULT_PORT

        # Phase 1: socket check (fast)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.HEALTH_TIMEOUT)
            result = sock.connect_ex((host, port))
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
                        f"Port {port} closed on {host}",
                        provider=self.provider_name
                    ),
                    error_message=f"Port {port} closed on {host}"
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
                error_message=str(e)
            )

        # Phase 2: API check (confirms it's Ollama, not just an open port)
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=self.HEALTH_TIMEOUT
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
                f"Ollama API unresponsive at {self.base_url}: {e}",
                provider=self.provider_name
            )
            return ProviderStatus(
                available=False,
                provider_name=self.provider_name,
                latency_ms=latency_ms,
                endpoint=self.base_url,
                last_healthy=self._last_healthy,
                error=error,
                error_message=str(e)
            )

    # ---------------------------------------------------------------------------
    # Transport Implementation
    # ---------------------------------------------------------------------------

    def _chat(self, model: str, messages: list[dict]) -> str:
        """
        Send a non-streaming chat request to Ollama.

        Args:
            model:    Ollama model identifier (e.g. "llama3.1:8b")
            messages: Conversation history as list of role/content dicts

        Returns:
            Complete response string.

        Raises:
            ProviderModelNotFoundError: Model not found on this instance.
            ProviderConnectionError:    Cannot reach endpoint.
            ProviderResponseError:      Unexpected response.
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                },
                timeout=self.timeout
            )

            if response.status_code == 404:
                raise ProviderModelNotFoundError(
                    f"Model '{model}' not found on {self.base_url}. "
                    f"Run 'ollama pull {model}' on the host.",
                    provider=self.provider_name,
                    model=model
                )

            response.raise_for_status()

            data = response.json()
            try:
                return data["message"]["content"]
            except KeyError as e:
                raise ProviderResponseError(
                    f"Unexpected response structure: missing {e}",
                    provider=self.provider_name,
                    model=model
                ) from e

        except ProviderModelNotFoundError:
            raise
        except requests.exceptions.ConnectionError as e:
            raise ProviderConnectionError(
                f"Cannot reach Ollama at {self.base_url}",
                provider=self.provider_name,
                model=model
            ) from e
        except requests.exceptions.Timeout as e:
            raise ProviderConnectionError(
                f"Request timed out after {self.timeout}s",
                provider=self.provider_name,
                model=model
            ) from e
        except requests.exceptions.HTTPError as e:
            raise ProviderResponseError(
                f"HTTP error: {e}",
                provider=self.provider_name,
                model=model
            ) from e

    def _stream_chat(self, model: str, messages: list[dict]) -> Generator:
        """
        Send a streaming chat request to Ollama.

        Yields response text chunks as they arrive.

        Args:
            model:    Ollama model identifier
            messages: Conversation history

        Yields:
            str chunks of the response.

        Raises:
            ProviderModelNotFoundError: Model not found.
            ProviderConnectionError:    Cannot reach endpoint.
            ProviderResponseError:      Unexpected response or parse error.
        """
        import json as _json

        try:
            with requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                },
                timeout=self.timeout,
                stream=True
            ) as response:

                if response.status_code == 404:
                    raise ProviderModelNotFoundError(
                        f"Model '{model}' not found on {self.base_url}. "
                        f"Run 'ollama pull {model}' on the host.",
                        provider=self.provider_name,
                        model=model
                    )

                response.raise_for_status()

                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = _json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if chunk.get("done"):
                            break
                    except _json.JSONDecodeError as e:
                        raise ProviderResponseError(
                            f"Failed to parse streaming chunk: {e}",
                            provider=self.provider_name,
                            model=model
                        ) from e

        except ProviderModelNotFoundError:
            raise
        except requests.exceptions.ConnectionError as e:
            raise ProviderConnectionError(
                f"Cannot reach Ollama at {self.base_url}",
                provider=self.provider_name,
                model=model
            ) from e
        except requests.exceptions.Timeout as e:
            raise ProviderConnectionError(
                f"Stream timed out after {self.timeout}s",
                provider=self.provider_name,
                model=model
            ) from e
        except requests.exceptions.HTTPError as e:
            raise ProviderResponseError(
                f"HTTP error during stream: {e}",
                provider=self.provider_name,
                model=model
            ) from e

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    @staticmethod
    def resolve_hostname(host: str) -> Optional[str]:
        """
        Attempt reverse DNS lookup to get a human-readable hostname.

        Returns the short hostname (first segment only) on success,
        None on failure. Used by discovery to generate nodule labels.
        """
        try:
            full_hostname = socket.gethostbyaddr(host)[0]
            return full_hostname.split(".")[0]
        except socket.herror:
            return None

    def __repr__(self) -> str:
        return (
            f"OllamaClient(base_url={self.base_url!r}, "
            f"type={self.provider_type!r}, "
            f"label={self.label!r})"
        )