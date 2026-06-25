#!/usr/bin/env python3
"""Live smoke test for the Claude provider — run ON YOUR HOST with ANTHROPIC_API_KEY set.
Spends one tiny call (haiku by default). Confirms claude.py does a real round-trip.

    ANTHROPIC_API_KEY=... python3 scripts/claude_smoke.py [model]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from erebos.providers.claude import ClaudeClient, KNOWN_MODELS

def main():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        print("set ANTHROPIC_API_KEY first"); return 1
    # catch the classic "pasted the placeholder" slip before the SDK throws a 30-line
    # header-encoding traceback
    if not key.isascii():
        print("ANTHROPIC_API_KEY contains non-ASCII chars — did you paste the literal "
              "placeholder (e.g. the '…')? Use your real sk-ant-... key."); return 1
    if not key.startswith("sk-ant-"):
        print(f"warning: key doesn't start with 'sk-ant-' (got {key[:6]}...) — continuing anyway")
    model = sys.argv[1] if len(sys.argv) > 1 else "claude-haiku-4-5-20251001"
    print("known models:", KNOWN_MODELS)
    print("using:", model)
    c = ClaudeClient()
    class M:
        total=0
        def update(self,t): self.total=t
    c.token_monitor = M()
    out = c._chat(model, [{"role":"user","content":"Reply with exactly one word: pong"}])
    print("response:", repr(out))
    print("tokens reported:", c.token_monitor.total)
    print("OK" if out else "EMPTY RESPONSE")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
