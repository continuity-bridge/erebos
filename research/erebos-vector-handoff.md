---
title: "Erebos Research Handoff: Architecture Unlocked"
subtitle: "Context Brief for Vector — What Was Found and What It Means for the Board"
project: "erebos"
subsystem: "cross-domain-handoff"
type: "context-brief"
status: "active"
version: "1.1.0"
date: "2026-06-23"
updated: "2026-06-23"
author: "MOAS (Dom2 Creative Cognate)"
recipient: "Vector (Dom1 Professional/DevRel Cognate)"
source_research:
  - "research/erebos-desktop-authentication-and-profile-architecture-documentation.md"
  - "research/erebos-protocol-and-orchestration-documentation.md"
  - "research/updating-erebos-after-claude-desktop-updates.md.md"
  - "research/erebos-architectural-integration-vs-pipeline-findings.md"
  - "research/erebos-orchestration-architecture.md"
  - "research/erebos-provider-abstraction-architecture.md"
  - "research/erebos-llm-nodule-protocol.md"
  - "research/security-implications-bwrap-kvm-daemon-vs-mcp-stdio.md"
  - "research/security-implications-fallback-to-mcp-path.md"
  - "research/github-discussion-foundation-utilities.md"
closes_issues:
  - 3
  - 4
unblocks_issues:
  - 6
  - 7
  - 8
  - 9
  - 10
  - 11
  - 12
tags:
  - handoff
  - architecture
  - research-summary
  - issue-triage
  - pipeline-integration
  - nodule-architecture
changelog:
  - version: "1.1.0"
    date: "2026-06-23"
    notes: "Added Section 4: Pipeline Integration Findings. Added Notion architecture
      docs migrated to research/. Updated recommended first moves."
  - version: "1.0.0"
    date: "2026-06-23"
    notes: "Initial handoff — cowork daemon, auth layer, maintenance automation."
---

# Erebos Research Handoff: Architecture Unlocked

Vector — this brief is from MOAS. The Architect spent time today doing deep
reverse-engineering work on Claude Desktop's internals. The findings are
significant enough that they restructure the entire roadmap. Before you touch
a single open issue, read this.

**v1.1.0 update:** A second research thread has been added — analysis of the
Anthropic-OpenWebUI pipeline against the Erebos architecture, with concrete
integration findings. Section 4 is new. The Notion architecture docs have also
been migrated from `docs/` to `research/` and are now referenced throughout.

---

## What Was Discovered

The research directory at `/home/tallest/Scriptorium/erebos/research/` now
contains the full record. This brief is the map, not the replacement.

---

### 1. The Authentication Layer Is Solved

**Source:** [`erebos-desktop-authentication-and-profile-architecture-documentation.md`](./erebos-desktop-authentication-and-profile-architecture-documentation.md)
*(subsystem: auth-harness | status: validated)*

Claude Desktop is an Electron/Chromium application. It stores session
authentication as a `sessionKey` cookie in a SQLite database at
`~/.config/Claude/Cookies`. The research document fully characterizes the
schema — including the constraint columns (`encrypted_value`, `last_update_utc`,
`source_type`, `has_cross_site_ancestor`) that cause naive INSERT attempts to
silently fail.

The solution is SQLite's native `ATTACH DATABASE` directive, which mirrors
rows between profile databases using whatever schema is live on disk at that
moment. This makes the auth layer **schema-agnostic and future-proof** — when
Anthropic adds a new tracking column, the mirror picks it up automatically.

A working multi-account harness is already defined:

- **Primary profile:** `~/.config/Claude/Cookies` (the logged-in desktop session)
- **Erebos sandbox profiles:** `~/.config/claude-harness/{profile}/session-data/`
- **Supported profiles:** `pro`, `free1`, `free2`, `free3`

The token census tool at [`erebos-tokens.py`](./erebos-tokens.py) already
enumerates all four profiles, extracts their `sessionKey` values, and handles
locked databases gracefully.

**Issues this closes: #3, #4.**

---

### 2. The Execution Layer Is Solved

**Source:** [`erebos-protocol-and-orchestration-documentation.md`](./erebos-protocol-and-orchestration-documentation.md)
*(subsystem: orchestration-daemon | status: stable | version: 1.1.0)*

Claude Desktop ships a background daemon called `cowork-vm-service`. On Linux,
this is a plain Node.js script — no Electron, no display required — that
manages a bubblewrap (`bwrap`) or QEMU sandbox and listens on a Unix domain
socket:

```
$XDG_RUNTIME_DIR/cowork-vm-service.sock
```

The wire protocol is simple and fully documented: a 4-byte big-endian length
prefix followed by a UTF-8 JSON-RPC payload. The research document contains the
complete method surface:

| Method | Purpose |
|---|---|
| `spawn` | Execute a command inside the sandbox |
| `mountPath` | Bind a host directory into the sandbox |
| `subscribeEvents` | Stream stdout/stderr back to the caller |
| `kill` | Terminate a tracked process |
| `writeStdin` | Pipe data to a running process |
| `createVM` / `startVM` / `stopVM` | Manage the sandbox lifecycle |
| `isRunning` / `isGuestConnected` | Health checks |
| `readFile` | Pull files out of the container |
| `configure` | Set runtime quotas and environment bounds |

A complete Python client — `CoworkSocketClient` — is fully implemented in the
document. It handles connection, length-prefixed framing, message dispatch, and
real-time stdout/stderr streaming.

**Electron is the process that currently launches this daemon and talks to it.
Erebos can do both without Electron.**

The extracted daemon source is at
[`extracted-app/cowork-vm-service.js`](./extracted-app/cowork-vm-service.js).

---

### 3. The Maintenance Layer Is Solved

**Source:** [`updating-erebos-after-claude-desktop-updates.md.md`](./updating-erebos-after-claude-desktop-updates.md.md)
*(subsystem: lifecycle-automation | status: active)*

Upstream `claude-desktop` package updates replace `app.asar` and can break
static references into the extracted source. Two automation vectors prevent
this from ever requiring manual repair:

**Auth layer (zero-maintenance):** The `ATTACH DATABASE` approach already
handles schema drift. Hook `erebos-login-helper.sh` into an APT post-invoke
rule and authentication sync runs automatically after every package update.

**Execution layer:** The `verify_and_refresh_source_payload()` function
(documented and ready to integrate into `claude.py`) compares the system
`app.asar` modification timestamp against a cached marker on startup. If the
upstream package has changed, it re-extracts automatically via `npx asar
extract`.

---

### 4. The Pipeline Integration Path (NEW in v1.1.0)

**Sources:**
- [`erebos-architectural-integration-vs-pipeline-findings.md`](./erebos-architectural-integration-vs-pipeline-findings.md)
- [`security-implications-bwrap-kvm-daemon-vs-mcp-stdio.md`](./security-implications-bwrap-kvm-daemon-vs-mcp-stdio.md)
- [`security-implications-fallback-to-mcp-path.md`](./security-implications-fallback-to-mcp-path.md)
- [`erebos-orchestration-architecture.md`](./erebos-orchestration-architecture.md)
- [`erebos-provider-abstraction-architecture.md`](./erebos-provider-abstraction-architecture.md)
- [`erebos-llm-nodule-protocol.md`](./erebos-llm-nodule-protocol.md)

The Anthropic-OpenWebUI pipeline was analyzed against the Erebos architecture.
Three things are worth stealing directly.

**4a. The capability flag pattern.**

The pipeline uses per-account valve flags (`ACC1_COWORK_ENABLED`, etc.) to
determine which accounts can talk to the cowork daemon and which fall back to
standard MCP stdio. This is exactly what Erebos needs to bridge the gap between
"we have session cookies for four accounts" and "we know which of those accounts
actually has Cowork access." The pro account gets `COWORK_ENABLED=True`; the
free accounts don't. Clean, no guessing, no failed socket connections on startup.

**4b. The fallback chain logic.**

The security implications doc contains a near-complete pseudocode implementation
of `_execute_with_fallback()` — try the cowork socket, catch the exception, drop
to MCP stdio, emit an event. This maps directly onto `CoworkToolExecutor` and
should be lifted wholesale rather than re-derived. See
[`security-implications-fallback-to-mcp-path.md`](./security-implications-fallback-to-mcp-path.md).

**4c. The tool mapping.**

The findings document provides the concrete translation table:

| MCP Tool | Cowork Method |
|---|---|
| `bash_tool` | `spawn` |
| `write_file` | `writeStdin` or `mountPath` + `spawn` |
| `read_file` | `readFile` |

This is the lookup table `CoworkToolExecutor` needs to dispatch tool use
blocks correctly.

**On the nodule architecture:**

The Notion docs also surface the full nodule/orchestration vision — multi-LLM
routing, privacy tiers, network discovery, VRAM-based model routing. This is
architecture Vector and the Architect developed together and it belongs in the
implementation picture. The provider abstraction layer in `erebos/providers/`
is already aligned with it. The nodule docs are the specification that
`claude.py`, `ollama.py`, and the planned `gemini.py` implement against.

See [`erebos-orchestration-architecture.md`](./erebos-orchestration-architecture.md)
and [`erebos-provider-abstraction-architecture.md`](./erebos-provider-abstraction-architecture.md)
for the full vision.

---

## What This Means for the Board

### Closed

| Issue | Was | Now |
|---|---|---|
| #3 Research: Locate and document Claude Desktop authentication tokens | In Review | **Done** |
| #4 Research: Test Anthropic API authentication with Desktop tokens | In Review | **Done** |

### Replanned

**#6 — [FEATURE] Implement basic GTK4 application window**

The design assumption changes entirely. Erebos is not building a Claude Desktop
lookalike. It is building a GTK4 shell that *owns* the cowork socket directly —
launching the daemon itself, talking to it directly, and presenting a native UI
that has no Electron dependency whatsoever.

This is a *smaller and cleaner* problem than the original framing assumed.
The window doesn't need to host a webview or replicate browser behavior. It
needs a conversation panel, an input bar, and a socket client. That's it.

**#9 — [FEATURE] Implement Claude API integration for conversations**

The provider layer (`erebos/providers/claude.py`) is already production-ready:
streaming, non-streaming, token reporting, full error hierarchy. The missing
piece is tool use — the agentic loop that handles `tool_use` content blocks
from the API and routes them through `CoworkSocketClient`. The architecture:

```
ClaudeClient._run_agent()
    │
    ├─ POST /v1/messages  (tools=[bash, str_replace_editor, computer])
    │       └─ Response: [TextBlock, ToolUseBlock(bash, "ls -la")]
    │
    ├─ CoworkToolExecutor.execute(tool_use_block)
    │   ├─ COWORK_ENABLED=True  → CoworkSocketClient.spawn(...)
    │   └─ COWORK_ENABLED=False → mcp_session.call_tool(...)
    │       └─ stdout: "erebos.py  providers/  ..."
    │
    └─ POST /v1/messages  (tool_result appended to history)
            └─ Response: [TextBlock("Here's what I found...")]
```

This issue should move from Planned to In Progress immediately. The socket
client is ready. The provider base is ready. The fallback logic is documented.
The loop needs to be written.

**#7 — [FEATURE] Build conversation input/output UI components**

Unblocked. The output model is now known: text blocks interleaved with tool
execution events streaming from the cowork socket. UI components need to handle
both.

**#8 — [FEATURE] Implement markdown rendering for responses**

Unblocked. No architectural dependency remaining.

**#10 — [FEATURE] Implement read-only diff viewer for file changes**

The `readFile` method on the cowork socket means file contents are directly
retrievable from the sandbox. Diff generation can happen in-process. Unblocked.

**#11 — [FEATURE] Display Claude usage limits from unified-limit-monitor**

The token monitor infrastructure already exists in `providers/base.py`.
The `ClaudeClient._report_tokens()` method already calls it. Unblocked.

**#12 — [FEATURE] Save and restore conversation sessions**

Conversation history is already managed as a `list[dict]` in the provider
layer. Serialization is trivial. Unblocked.

---

## Recommended First Moves

In priority order:

1. **Close #3 and #4.** Link the auth research doc. They're done.

2. **Move #9 to In Progress.** Write `ClaudeClient._run_agent()` and
   `CoworkToolExecutor` with the fallback pattern from
   [`security-implications-fallback-to-mcp-path.md`](./security-implications-fallback-to-mcp-path.md).
   This is the heart of what Erebos actually *is*.

3. **Add capability flags** to the provider config schema — `cowork_enabled`
   per nodule. Pro account gets `true`, free accounts get `false`. The
   `CoworkToolExecutor` reads this before attempting the socket.

4. **Reframe #6.** Update the issue description to reflect the new GTK4 +
   cowork socket architecture. The original spec assumed Electron parity;
   the new one doesn't.

5. **Add `verify_and_refresh_source_payload()`** to `claude.py` startup.
   Takes twenty minutes and makes the whole extraction layer maintenance-free.

6. **Review the nodule docs** against the G700 code when it syncs. The
   architecture in `erebos-provider-abstraction-architecture.md` and
   `erebos-orchestration-architecture.md` should validate cleanly against
   what's already implemented — close those open questions in the doc.

---

## A Note on the Provider Layer

The existing `claude.py` is good work. Don't refactor it before the agent loop
is running — the abstractions are right and the error hierarchy is solid. The
`_chat` and `_stream_chat` methods are text-only and should stay that way.
The agent loop belongs in a new `_run_agent()` method that handles `tool_use`
content blocks explicitly. Keep the separation clean.

---

## Research Directory — Current State

```
research/
├── erebos-desktop-authentication-and-profile-architecture-documentation.md
├── erebos-protocol-and-orchestration-documentation.md
├── updating-erebos-after-claude-desktop-updates.md.md
├── erebos-architectural-integration-vs-pipeline-findings.md   ← NEW
├── erebos-orchestration-architecture.md                       ← NEW
├── erebos-provider-abstraction-architecture.md                ← NEW
├── erebos-llm-nodule-protocol.md                              ← NEW
├── security-implications-bwrap-kvm-daemon-vs-mcp-stdio.md    ← NEW
├── security-implications-fallback-to-mcp-path.md              ← NEW
├── github-discussion-foundation-utilities.md                  ← NEW
├── erebos-tokens.py
├── read-leveldb.py
├── erebos-vector-handoff.md                                   ← THIS FILE
└── extracted-app/
    └── cowork-vm-service.js
```

---

*Handoff v1.1.0. The Architect did the hard part. Go build.*
