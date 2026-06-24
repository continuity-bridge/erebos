# Erebos: Orchestration Architecture

**Status:** Design Document

**Version:** 0.2.0

**Purpose:** Define the multi-LLM orchestration vision for Erebos

## Core Vision

Erebos is **not** a Claude-specific application with optional other backends. It is a **multi-LLM orchestration platform** where different models work together as peers or agents, with Claude as one nodule among many.

### Key Principles

1. **Model-agnostic by design** - No model is privileged in the architecture
2. **Simultaneous multi-nodule** - Multiple LLM backends active concurrently
3. **Flexible collaboration** - Models can work as peers, agents, or in fallback chains
4. **Pluggable everything** - Nodules, auth providers, tokenizers all modular
5. **Event-driven coordination** - Orchestrator manages through event system
6. **Network-aware** - "Local" means network-accessible, not just [localhost](http://localhost)

## Network Topology: Local ≠ [Localhost](http://Localhost)

**Critical insight:** "Local" LLMs are not necessarily on the same machine as the client.

### Data Privacy Tiers

1. **Cloud APIs** - Data leaves your network
   - Claude API ([api.anthropic.com](http://api.anthropic.com))
   - OpenAI API ([api.openai.com](http://api.openai.com))
   - Requires internet, subject to provider ToS
2. **Network-Local** - Data stays on your network
   - Ollama on workstation P71 (192.168.1.100:11434)
   - Company LLM server ([internal.company.com:8080](http://internal.company.com:8080))
   - Team inference server (gpu-server.local:11434)
   - No internet required, your infrastructure
3. [**Localhost**](http://Localhost) - Single-machine only
   - Special case of network-local
   - Ollama on same machine as client (127.0.0.1:11434)

### Example Topology

```
WSL Laptop (No GPU)
├─ erebos-client
└─ connects to:
   ├─ P71 Workstation (192.168.1.100)
   │  └─ Ollama (6GB VRAM, P3000 GPU)
   │     └─ Models: llama3.2, mistral, codellama
   │
   ├─ Desktop (192.168.1.50)
   │  └─ Ollama (24GB VRAM, RTX 4090)
   │     └─ Models: llama3.2:70b, qwen2.5:72b
   │
   └─ Cloud APIs (internet)
      ├─ Claude via api.anthropic.com
      └─ OpenAI via api.openai.com
```

## Network Discovery

Orchestrator can auto-discover Ollama instances on local network:

```python
class NetworkDiscovery:
    """Discover LLM services on local network."""
    
    def discover_ollama_servers(self, timeout=5):
        """
        Scan local network for Ollama instances.
        
        Methods:
        1. mDNS/Bonjour service discovery
        2. Broadcast ping on port 11434
        3. Manual network scan (config-defined subnets)
        """
        discovered = []
        
        # Method 1: mDNS (if available)
        services = self._mdns_discover("_ollama._tcp.local.")
        
        # Method 2: Scan known subnets
        subnets = config.get("discovery.subnets", ["192.168.12.0/24"])
        for subnet in subnets:
            services.extend(self._scan_subnet(subnet, port=11434))
        
        return [
            {
                "name": f"ollama-{hostname}",
                "url": f"http://{ip}:{port}",
                "hostname": hostname,
                "models": self._query_models(ip, port)
            }
            for ip, hostname, port in services
        ]
```

------

**Created:** 2026-04-22

**Updated:** 2026-04-22 (v0.2.0 - network-local concepts)

**By:** Vector with Uncle Tallest

**Status:** Living document

**Full specification available in project repository**