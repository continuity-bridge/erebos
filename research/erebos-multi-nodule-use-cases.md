<!-- Migrated from Notion (Cognate Quarters → Coding DB) 2026-06-25 by Vector (Dom1).
     Source: https://app.notion.com/p/350c4ef87ccc818fa0eed884f408944f · Notion status: In progress -->

# Multi-Nodule Use Cases

**Purpose:** Concrete scenarios demonstrating orchestration patterns

## Use Case 9: Network Resource Leverage (GPU Distribution)

**Scenario:** WSL laptop (no GPU) uses P71 workstation's GPU over network
**Nodules involved:** Ollama@P71 (network), Ollama@Desktop (network)

### Topology
```
WSL Laptop (ThinkPad, no discrete GPU)
 └─ erebos-client
    ├─ Local: Nothing (no GPU, no Ollama installed)
    └─ Network:
       ├─ P71 @ 192.168.1.100 (6GB VRAM, P3000)
       └─ Desktop @ 192.168.1.50 (24GB VRAM, RTX 4090)
```

### Flow
```
1. User on laptop: "Run llama3.2:70b on this code"
2. Orchestrator checks requirements:
   - Model: llama3.2:70b (~40GB)
   - Requires: Desktop (24GB VRAM)
3. Route to Ollama@Desktop (192.168.1.50)
4. Desktop runs inference, streams response
5. Laptop displays result (no local GPU needed)
```

### Auto-Selection Logic
```python
def select_nodule_for_model(self, model: str):
    requirements = self.get_model_requirements(model)

    # llama3.2:70b needs ~40GB VRAM
    if requirements['vram_gb'] > 20:
        return self.nodules['ollama-desktop']  # 24GB VRAM

    # llama3.2 (7B) needs ~6GB VRAM
    elif requirements['vram_gb'] > 4:
        return self.nodules['ollama-p71']  # 6GB VRAM

    # Fallback to cloud if no network GPU available
    else:
        return self.nodules['claude-desktop']
```

## Privacy Model

**Tier 1: Localhost** (highest privacy)
- Data never leaves single machine
- Example: Ollama on same device as client

**Tier 2: Network-Local** (high privacy)
- Data stays on your network (LAN/VPN)
- Example: Ollama on P71 @ 192.168.1.100
- No internet required
- Subject to your infrastructure security

**Tier 3: Cloud APIs** (standard privacy)
- Data sent to cloud providers
- Example: Claude API, OpenAI API
- Subject to provider ToS
- Requires internet

### Privacy-Aware Routing
```python
@dataclass
class PrivacyPolicy:
    pii_detected: bool = False
    confidential: bool = False
    healthcare: bool = False

    def max_allowed_tier(self) -> str:
        if self.confidential or self.healthcare:
            return "localhost"  # Never leave machine
        elif self.pii_detected:
            return "network"  # Stay on your network
        else:
            return "cloud"  # OK to use APIs
```

## Real-World Scenario: Jerry's Setup
- Working from laptop at coffee shop (WSL, no GPU)
- P71 at home running Ollama (always on)
- VPN connection to home network
- Runs 70B models via P71, no cloud API costs
- Sensitive data never leaves home network

---
**Created:** 2026-04-22
**By:** Vector with Uncle Tallest
**Complete use cases in project repository**
