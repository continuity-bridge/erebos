---
title: "Erebos Desktop Authentication & Profile Architecture Documentation"
subtitle: "Reverse Engineering the Chromium Cookie Storage & Profile Isolation Layers"
project: "erebos"
subsystem: "auth-harness"
type: "research-specification"
status: "validated"
version: "1.0.0"
date: "2026-06-23"
author: "The Architect"
tags:
  - sqlite
  - cookies
  - electron
  - profile-isolation
  - security
---

# Erebos Desktop Authentication & Profile Architecture Documentation

This document compiles the reverse-engineering discoveries regarding the authentication lifecycles, database validation invariants, and multi-profile session injection mechanisms required to stabilize headless automation workflows within **Erebos**.

## 1. Authentication Topology & Storage Roots

Chromium/Electron applications maintain active user sessions via stateful database files stored locally within user configuration data spaces.

### 1.1 Core File Dispositions

When a user authenticates against the primary client layout, session profiles partition their storage parameters across distinct locations:

- **Primary Profile Cookie Vault:** `~/.config/Claude/Cookies`

  *An encryption-isolated SQLite database housing authorization tokens, network tracing tokens, and lifecycle state markers.*

- **Core Account Configuration Map:** `~/.config/Claude/claude_desktop_config.json`

  *An explicit JSON object maintaining baseline account identifiers, flags, and account mapping hashes.*

- **Erebos Target Sandboxes:** `~/.config/claude-harness/{profile_name}/session-data/`

  *Isolated workstation environments managed by the Erebos runner grid to isolate concurrent multi-account execution loops.*

## 2. Chromium Database Validation Invariants

Replicating an authenticated session requires bypassing strict column invariants added to modern Chromium/Electron SQLite engines. Simply executing a naive `INSERT` payload with a stolen token string fails due to database constraint triggers (`NOT NULL constraint failed`).

### 2.1 The Structural Constraints Matrix

To successfully map a token directly into an isolated target profile database without throwing structural exceptions, the data payload must explicitly satisfy these structural gates:

| **Column Field**              | **Target Data Type** | **Subsystem Invariant Purpose**                              | **Injection Requirement**                                    |
| ----------------------------- | -------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **`encrypted_value`**         | `BLOB`               | Modern builds require either a raw string in `value` or a binary blob payload. If omitted entirely, it triggers a schema-level database rejection. | Pass an empty zero-length binary BLOB literal (`X''`) to satisfy the column structure without polluting data parsing layouts. |
| **`last_update_utc`**         | `INTEGER`            | Tracks high-precision temporal modification cycles across the cookie lifespan. | Compute a current epoch timestamp in microseconds matching the creation parameters (`strftime('%s','now')*1000000`). |
| **`source_type`**             | `INTEGER`            | Tracks the engine insertion channel origin (e.g., HTTP response headers vs. direct programmatic API injections). | Pass an explicit integer value of `1` (representing a standard network/script stream source type origin flag). |
| **`has_cross_site_ancestor`** | `INTEGER`            | Monitors secure authentication boundary flags and tracking configurations across cross-site parent layouts. | Must evaluate to an integer boolean flag (`0` or `1`) matching the current structural specification of the engine. |

## 3. Native Cross-Database Mirroring Strategy

Because Chromium updating cycles continuously alter internal cookie table structural flags, explicitly hardcoding manual shell queries or string-parsing algorithms introduces breaking points when engine schemas evolve.

### 3.1 The Direct Connection Vector

The robust approach involves utilizing SQLite's native `ATTACH DATABASE` directive. This instructs the execution engine to bridge two independent database paths within a single transaction pipeline, cloning rows using the matching native schema layout resident on the disk.

```bash
+------------------------------------+
|  Target Sandbox Database           |  <--- Executing Connection Node
|  (~/.config/claude-harness/.../C)  |
+------------------------------------+
                 |
                 |  (ATTACH DATABASE)
                 v
+------------------------------------+
|  Primary Client Profile DB         |  <--- Source Row Container
|  (~/.config/Claude/Cookies)        |
+------------------------------------+
                 |
                 |  (INSERT INTO main.cookies SELECT * FROM ...)
                 v
[ Native Pixel-for-Pixel Row Mapping Across All Constraints ]
```

### 3.2 SQL Operational Logic

The transaction drops any stale session rows inside the isolated target sandbox profile, mounts the primary application space into the active execution context, clones the active `sessionKey` parameter natively, and gracefully disconnects:

SQL

```sqlite
-- Terminate any conflicting session row targets first
DELETE FROM cookies WHERE host_key LIKE '%claude.ai%' AND name = 'sessionKey';

-- Bridge the default live database into the harness profile workspace
ATTACH DATABASE '/home/tallest/.config/Claude/Cookies' AS default_db;

-- Clone the exact row structurally, capturing all modern constraint fields
INSERT INTO main.cookies 
SELECT * FROM default_db.cookies 
WHERE host_key LIKE '%claude.ai%' AND name = 'sessionKey' 
LIMIT 1;

-- Cleanly detach resource channels
DETACH DATABASE default_db;
```

## 4. Multi-Account Profile Stabilization

Once the session rows are successfully cloned into place, Electron requires a corresponding configuration alignment to finalize initialization without dropping out to default authentication gates.

1. **Configuration Profile Parity:** The `claude_desktop_config.json` containing account mapping keys must be copied over exactly to the target user-data directory (`--user-data-dir`).
2. **Singleton Resource Cleaning:** Stale file system locks (`SingletonLock`, `SingletonCookie`, `SingletonSocket`) must be aggressively unlinked prior to booting isolated instances. This avoids window interception conflicts and prevents the process from bouncing authentication paths back onto the default user space.