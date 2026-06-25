<!-- Migrated from Notion (Cognate Quarters → Coding DB) 2026-06-25 by Vector (Dom1).
     Source: https://app.notion.com/p/351c4ef87ccc81119d1cf6009f6f7351 · Notion status: In progress -->

# G700 Lenovo Laptop — Erebos Testing Configuration

**Purpose:** Thin client for testing "local ≠ localhost" architecture
**Machine:** Lenovo G700 (no discrete GPU) · **OS:** Debian Trixie XFCE · **Role:** Erebos client → network Ollama
**Status:** Planning phase (2026-05-01). ⚠️ Network is `192.168.12.0/24` (not .1.x as first planned).

---
## Architecture Context
G700 is the ideal test platform for network-aware orchestration: no GPU (can't run Ollama locally — intentional), must reach P71/Desktop for inference, validates privacy-tier routing and discovery.

```
G700 Thin Client (No GPU, No Ollama)
├─ At Home:  Desktop @ 192.168.1.50 (24GB VRAM, RTX 4090) → llama3.2:70b, qwen2.5:72b
└─ Away (VPN / P71 on-site): P71 @ 192.168.1.100 (6GB VRAM, P3000) → llama3.2, mistral, codellama
```

## Install (Debian Trixie)
```bash
sudo apt update && sudo apt upgrade -y
python3 --version            # target 3.11+
sudo apt install -y git python3-pip python3-venv build-essential curl nmap avahi-utils
```
```bash
mkdir -p ~/Projects && cd ~/Projects
git clone https://github.com/continuity-bridge/native-claude-client erebos && cd erebos
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt
```

## Example config (`~/.erebos/config.yaml`)
```yaml
nodules:
  ollama-desktop: { type: ollama, base_url: "http://192.168.1.50:11434",  location: network, priority: 1, enabled: true }
  ollama-p71:     { type: ollama, base_url: "http://192.168.1.100:11434", location: network, priority: 2, enabled: true }
discovery: { enabled: true, method: broadcast, subnets: ["192.168.1.0/24"], timeout: 5 }
privacy:   { default_tier: network, allow_cloud: false }
```

## Testing protocol (objectives)
1. Basic connection — G700 can reach Ollama instances.
2. Erebos orchestration — route through the event system (`list nodules`, `run ... --nodule`).
3. Auto-routing by model size — small→P71, 70b→Desktop.
4. Network discovery — broadcast/mDNS finds instances.
5. Privacy-tier enforcement — network-only, NO cloud fallback when nodes offline.
6. Multi-nodule concurrent (future — needs async CLI/GUI).

## Known limitations
- **⚠️ KEYBOARD FAILURE (2026-04-30):** built-in keyboard died on boot. Workarounds: external USB keyboard, SSH from another machine, or VNC/RDP. CLI still testable via SSH. Decision pending: fix vs different test hardware.
- No local Ollama (intentional); network dependency on P71/Desktop; VPN required when away.

## Success criteria (open items)
- [ ] reach Ollama on Desktop / P71
- [ ] list nodules · route to specific nodule · auto-route by size
- [ ] discovery finds instances · privacy-tier prevents cloud fallback · CLI functional · ready for GUI phase

---
**Created:** 2026-04-29 · **Updated:** 2026-04-30 · **By:** Vector with Uncle Tallest
**Repo (historical):** https://github.com/continuity-bridge/native-claude-client
