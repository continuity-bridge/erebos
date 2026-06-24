# Erebos: LLM Nodule Protocol

**Version:** 0.2.0

**Purpose:** Define the standard interface for LLM backend nodules

## Concept: Nodules

In Erebos architecture, **nodules** are self-contained

A nodule can implement an authorization mechanism.

A nodule can connect other nodules.

A nodule could be a set of instructions, knowledge, or context meant to be shared across the nodes; or for a single nodule.

A nodule could be configured as an LLM backend provider that attaches to the event system.

**Why "Nodules"?**

- **Self-contained:** Each nodule is independent
- **Attachable:** Connect without modifying core
- **Organic growth:** New nodules extend naturally
- **Multiple simultaneous:** Coexist as peers
- **Composable:** Nodules can call each other (agentic patterns)

## Network-Aware Configuration

```python
class OllamaClient(LLMBackend):
    SUPPORTED_AUTH = [NullAuth]
    
    def __init__(self, auth_provider: AuthProvider, base_url: str):
        super().__init__(auth_provider)
        self.base_url = base_url  # Network address, not just localhost
        self.location = self._infer_location()
    
    def _infer_location(self) -> str:
        """Cloud, network, or localhost?"""
        if "localhost" in self.base_url or "127.0.0.1" in self.base_url:
            return "localhost"
        if self._is_private_ip(self.base_url):
            return "network"  # 192.168.x.x, 10.x.x.x, etc.
        return "cloud"
```

## Privacy-Aware Routing

```python
def route_message(self, prompt: str, privacy_level: str = "normal"):
    if privacy_level == "sensitive":
        # Network-local only, never cloud
        return self.get_nodule_by_location("network")
    elif privacy_level == "confidential":
        # Localhost only
        return self.get_nodule_by_location("localhost")
    else:
        # Use normal routing (cloud OK)
        return self.route_by_capability(prompt)
```

## Configuration Examples

```yaml
# Multiple Ollama nodules at different network locations
nodules:
  ollama-p71:
    base_url: "<http://192.168.1.100:11434>"
    location: network
    label: "P71 Workstation - 6GB VRAM"
    
  ollama-desktop:
    base_url: "<http://192.168.1.50:11434>"
    location: network
    label: "Desktop - 24GB VRAM, RTX 4090"
    
  ollama-local:
    base_url: "<http://localhost:11434>"
    location: localhost
    enabled: false  # WSL laptop has no GPU
```

------

**Created:** 2026-04-22

**By:** Vector with Uncle Tallest

**Full protocol specification in project repository**