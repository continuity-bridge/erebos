"""erebos - Network-agnostic LLM harness."""

from .providers import (
    ProviderClient,
    ProviderStatus,
    ProviderError,
    ProviderConnectionError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderModelNotFoundError,
    ProviderResponseError,
    ProviderCapabilityError,
    OllamaClient,
)
from .discovery import (
    OllamaDiscovery,
    NoduleConfig,
    discover_and_save,
)

__version__ = "0.1.0-dev"

__all__ = [
    # Provider interface
    "ProviderClient",
    "ProviderStatus",
    "ProviderError",
    "ProviderConnectionError",
    "ProviderAuthError",
    "ProviderRateLimitError",
    "ProviderModelNotFoundError",
    "ProviderResponseError",
    "ProviderCapabilityError",
    # Provider implementations
    "OllamaClient",
    # Discovery
    "OllamaDiscovery",
    "NoduleConfig",
    "discover_and_save",
]