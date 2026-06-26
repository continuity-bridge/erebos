---
title: "Erebos — Auth Models & ToS Decision"
date: 2026-06-25
status: decided
author: The Architect (operator) + Vector (Dom1)
supersedes_assumptions_in: erebos-architectural-integration-vs-pipeline-findings.md
---

# Erebos — Auth Models & the ToS Precipice (decided 2026-06-25)

Worked out live with the operator. Records WHY the model layer is the documented API,
so it isn't re-litigated.

## Two credentials, two APIs (not one "locked/unlocked" API)
- `sk-ant-api03-…` — **Messages API** key. `api.anthropic.com/v1/messages`, Bearer auth.
  What `claude.py` uses. Comes ONLY from a **Console** account (platform.claude.com),
  separate product + billing from claude.ai (a Pro/Max sub does NOT include API credits).
- `sk-ant-sid02-…` — **claude.ai session token** (the `sessionKey` cookie). Auths
  **claude.ai's own backend** (the app's endpoint), sent as a Cookie. Cannot auth the
  Messages API. Extracted by `research/erebos-tokens.py` for the 4 harness profiles.

## Two execution models
- **Model A — API providers** (`claude.py` + `_run_agent`): Messages API, `api03` key.
  Tool exec via cowork socket (Pro) OR MCP-stdio (no-cowork). DURABLE, supported, paid.
- **Model B — Desktop sessions**: the 4 claude.ai sessions (`sid02`), real Claude Desktop.

## ToS findings (the precipice)
1. `sid02` → claude.ai endpoint directly: **ToS violation** (automated access to the
   consumer product / circumventing the API). Fragile (undocumented) + account-ban risk.
2. Decoupling Electron / repackaging `app.asar` as a standalone inference backend:
   **ToS violation, worse** — adds reverse-engineering + repackaging of proprietary
   software; and shipping it to USERS distributes a circumvention tool that burns their
   accounts. NOT building this.
3. Vanilla free sessions in the REAL app: fine for **human interactive use** (incl.
   window-managing your own instances). Over the edge when (a) software DRIVES the
   sessions to extract inference for an agent loop (automated access — the GUI doesn't
   launder it), or (b) multiple free accounts exist to MULTIPLY free quota (multi-
   accounting / limit circumvention — a problem even with zero automation).
4. **There is no licensed "free programmatic inference."** That capability IS the API —
   it's what Anthropic sells. Free claude.ai = interactive human use in official clients.

## DECISION
- **Programmatic / agentic = documented Messages API** (`api03`, Console account; new
  Console accounts get a one-time ~$5 trial for dev — verify in Console).
- Official clients for interactive use. Cowork knowledge confined to orchestrating the
  operator's OWN real Cowork session's sandbox (CoworkSocketClient), not repackaging.
- The MCP-stdio executor serves "an API account without cowork," NOT free claude.ai
  accounts.
- If the goal is CHEAP not free: Haiku for bulk, **prompt caching**, **Batch API (−50%)**,
  $5 trials for dev. Architect erebos to lean on these.

*Not legal advice — operator's read + Vector's engineering/ethics read. Authority =
Anthropic Commercial Terms + Usage Policy + operator's lawyer.*

---

## Addendum (2026-06-25) — supporting the normal allowed use, two modes

Clarified with the operator: multiple sessions are for **domain separation** (distinct
calibrated cognitive contexts — creative ≠ balance), NOT throughput multiplication. That
is a legitimate organizational use. erebos should support BOTH of the following, and the
boundary is simply **what erebos's role is**:

- **Interactive mode (the normal allowed case).** A human uses the real Claude Desktop
  app, one context per domain; erebos is the *workspace around it* — window management,
  focus-shepherding, context switching (the Stoa Hubs / embed harness as a UI convenience).
  erebos arranges the room; the human drives the conversation. No inference extraction,
  no prompt injection. Fully inside the lines.
- **API mode (programmatic).** Multiple API contexts under a Console org = the domain
  mirrors, done programmatically. This is exactly what the API is for; run as many
  distinct contexts as you like.

**The one rule (stated positively):** a domain is EITHER interactive (real app, human
drives, erebos orchestrates) OR programmatic (API nodule). The only thing to never do is
**programmatically drive a *consumer* session** (real-app GUI doesn't launder automated
inference extraction).

Note: domain mirrors are *context* separation, not accounts. They do NOT require separate
Anthropic accounts — N contexts/system-prompts on ONE account/runtime achieve it, which
also removes the one-account-per-person soft spot. See substrate
`FOUNDATION/proposals/PROP-domain-account-decoupling.md`.
