---
title: "cowork-vm-service — Wire Protocol Reference (LIVING)"
status: living
last_confirmed: 2026-06-25
confirmed_against_host: Sisyphus
claude_desktop_version: "1.11847.5-2.0.19"
maintained_by: Vector (Dom1)
note: >
  Source of truth for the ACTUAL daemon behavior, derived from live host probes
  (scripts/cowork_probe.py), NOT from the narrative in
  erebos-protocol-and-orchestration-documentation.md. Where the two disagree,
  THIS file wins. Mark every change with the Claude Desktop version it was seen on.
---

# cowork-vm-service — Wire Protocol Reference (living)

Socket: `$XDG_RUNTIME_DIR/cowork-vm-service.sock` (Unix domain, `AF_UNIX`/`SOCK_STREAM`).

**Framing:** `[ 4-byte big-endian uint32 length ][ UTF-8 JSON payload ]`.

**Request:** `{"method": <str>, "params": <object | positional-array>, "id": <int>}`
*Note:* `params` is usually an **object** (`spawn` reads `params.command`), but at least
one method (`readFile`) treats the **entire params payload as a positional array**. Per
method below.

**Response envelope:**
- success → `{"success": true,  "result": {...}, "id": <int>}`
- error   → `{"success": false, "error": "<message>", "id": <int>}`

Legend: ✅ confirmed live · ⚠️ partial · ❓ from research, not yet probed

---

## Methods

| Method | Status | Request `params` | Success `result` | Notes |
|---|---|---|---|---|
| `isRunning` | ✅ | `{}` | `{"running": bool}` | health check |
| `isGuestConnected` | ✅ | `{}` | `{"connected": bool}` | health check |
| `subscribeEvents` | ✅ | `{}` | `{}` (ack) | **must be sent before `spawn`** to receive its output events on this connection |
| `spawn` | ✅ | object `{"id":<str>, "command":<str>, "args":[...], "cwd":<str>, "env":{...}}` | ack `{}` then **events** (see below) | fire-and-ack: stdout/exit arrive as events, NOT on this reply |
| `readFile` | ❌ | **UNRESOLVED** — `{path}`, `{paths:[]}`, AND `[positional]` all rejected with `paths[0] undefined`. Param plumbing differs from spawn. Brute-force probe pending. | ❓ | handler validates `paths[0]` is a string |
| `mountPath` | ❓ | `{"hostPath":<str>, "mountName":<str>}` (research) | ❓ | bind a host dir into the sandbox |
| `kill` | ❓ | `{"id":<str>}` (research) | ❓ | terminate a tracked process |
| `writeStdin` | ❓ | `{"id":<str>, "data":<str>}` (research) | ❓ | pipe to a running process |
| `readFile` (multi) | ❓ | `["<p1>","<p2>"]` | ❓ | array implies batch reads |
| `createVM`/`startVM`/`stopVM` | ❓ | ? | ? | sandbox lifecycle |
| `configure` | ❓ | ? | ? | runtime quotas/env |

---

## Events (after `subscribeEvents`, during `spawn`)

| Event | Status | Shape |
|---|---|---|
| stdout | ✅ | `{"type":"stdout", "id":"<proc>", "data":"<str>"}` |
| stderr | ⚠️ | assumed `{"type":"stderr", "id":"<proc>", "data":"<str>"}` (not yet observed; stdout confirmed) |
| exit | ✅ | `{"type":"exit", "id":"<proc>", "exitCode":<int>, "signal":<null|str>}` |

`id` on events is the **process id** passed in `spawn` params (e.g. `"erebos-probe"`),
distinct from the request `id` (int) on the ack frame.

---

## Confirmation log (probe history)

| Date | CD version | What was confirmed/changed |
|---|---|---|
| 2026-06-25 | 1.11847.5-2.0.19 | First live probe (Sisyphus): framing real; `isRunning`/`isGuestConnected` ✅. `spawn` fire-and-ack; `subscribeEvents` required; stdout/exit event shapes captured ✅. |
| 2026-06-25 | 1.11847.5-2.0.19 | `readFile` param form UNRESOLVED — `{path}`, `{paths:[]}`, and `[positional]` all return `paths[0] undefined`. Brute-force probe queued. |

---

## Upstream change tracking

The daemon ships inside the `claude-desktop` package (`app.asar`). Updates can change
methods/shapes. To detect & record drift:

1. **Capture the version** on each probe and put it in the table above:
   `apt list --installed 2>/dev/null | grep -i claude-desktop` (or the asar's mtime/hash).
2. `erebos`'s `verify_and_refresh_source_payload()` already re-extracts the source on
   asar mtime change — pair a re-probe with each upstream bump.
3. When a shape changes, **add a row to the Confirmation log** with the new CD version
   and what moved; update the method/event tables, and bump `last_confirmed`.

*Keep this file honest: every ✅ should trace to a probe output, not a doc.*
