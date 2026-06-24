---
title: "Erebos Protocol & Orchestration Documentation"
subtitle: "Unix Domain Sockets, Length-Prefixed Framing, and the Cowork RPC Interface"
project: "erebos"
subsystem: "orchestration-daemon"
type: "protocol-specification"
status: "stable"
version: "1.1.0"
date: "2026-06-23"
author: "The Architect"
target_socket: "$XDG_RUNTIME_DIR/cowork-vm-service.sock"
wire_format: "UInt32BE + JSON-RPC"
tags:
  - unix-sockets
  - network-protocols
  - json-rpc
  - bubblewrap
  - python-interop
---

# Erebos Protocol & Orchestration Documentation

This documentation covers the technical specifications, architectural findings, and programmatic integration strategies for decoupling the internal orchestration modules from the Claude Desktop client, allowing for native cross-account management and headless task execution inside **Erebos**.

## 1. Architectural Overview

The modern layout utilizes an isolated profile sandbox topology to bypass Electron framework window handlers and URL-scheme hijacking. Rather than interacting with heavy visual browser frames or tracking manual authentication loops, the layout is split into two independent domains:

1. **The Core Database Authentication Layer:** Handles stateful lifecycle session parameters.
2. **The Programmatic IPC Daemon Subsystem (`cowork`):** Dispatches sandboxed process execution arrays over local loopback vectors.

```bash
+------------------+      (Native Clone)      +-------------------------+
| Default Profile  | -----------------------> | Isolated Harness Vault  |
| (~/.config/Claude|                          | (~/.config/claude-harn) |
+------------------+                          +-------------------------+
                                                           |
                                                           v
+------------------+      (Length-Prefixed)   +-------------------------+
|   Erebos Core    | <======================> | cowork-vm-service.sock  |
|  (Python/Node)   |         JSON-RPC         |  (bwrap/qemu Sandbox)   |
+------------------+                          +-------------------------+
```

## 2. Authentication Sandbox & Lifecycle Injection

### 2.1 The Database Collision Problem

Modern Chromium-based engines require strict invariant validations on schema insert targets. Directly copying basic cookie string tokens initiates silent database rollbacks or execution crashes due to missing structural metadata.

### 2.2 The Solution: Native Cross-Database Mirroring

Rather than executing manual string injections, the structural fields, high-precision microsecond timestamps, and browser origin tracking markers are replicated pixel-for-pixel using SQLite's native `ATTACH DATABASE` engine commands. This guarantees absolute compliance with schema constraints (such as `encrypted_value`, `last_update_utc`, and `source_type`) without hardcoding volatile field configurations.

### 2.3 Automated Sync & Login Helper (`erebos-login-helper.sh`)

This shell utility terminates locking resource configurations, allocates missing sandbox directories, and executes direct cross-database replication pipelines:

Bash

```bash
#!/usr/bin/env bash
set -euo pipefail

TARGET_ACCOUNT="${1:-}"
if [[ -z "$TARGET_ACCOUNT" ]]; then
    echo "Error: Please specify a target profile (e.g., pro, free1)." >&2
    exit 1
fi

DEFAULT_COOKIE_DB="${HOME}/.config/Claude/Cookies"
DEFAULT_CONFIG="${HOME}/.config/Claude/claude_desktop_config.json"

TARGET_DATA_DIR="${HOME}/.config/claude-harness/${TARGET_ACCOUNT}/session-data"
TARGET_COOKIE_DB="${TARGET_DATA_DIR}/Cookies"
TARGET_CONFIG="${TARGET_DATA_DIR}/claude_desktop_config.json"

if [[ ! -f "$DEFAULT_COOKIE_DB" ]]; then
    echo "Error: Main default Claude profile database not found." >&2
    exit 1
fi

mkdir -p "$TARGET_DATA_DIR"

# Terminate active profile resource locks to prevent SQLite deadlocks
pgrep -af "claude-desktop" | grep -F "$TARGET_DATA_DIR" | awk '{print $1}' | xargs -r kill -9 2>/dev/null || true

if [[ ! -f "$TARGET_COOKIE_DB" ]]; then
    sqlite3 "$TARGET_COOKIE_DB" "CREATE TABLE IF NOT EXISTS cookies (dummy INTEGER);" 2>/dev/null || true
fi

echo "==> Syncing authentication session keys natively..."
sqlite3 "$TARGET_COOKIE_DB" << EOF
DELETE FROM cookies WHERE host_key LIKE '%claude.ai%' AND name = 'sessionKey';
ATTACH DATABASE '$DEFAULT_COOKIE_DB' AS default_db;
INSERT INTO main.cookies 
SELECT * FROM default_db.cookies 
WHERE host_key LIKE '%claude.ai%' AND name = 'sessionKey' 
LIMIT 1;
DETACH DATABASE default_db;
EOF

if [[ -f "$DEFAULT_CONFIG" ]]; then
    cp -f "$DEFAULT_CONFIG" "$TARGET_CONFIG"
fi

echo "==> [SUCCESS] '${TARGET_ACCOUNT}' profile is pre-authenticated."
```

## 3. Internal Wire Protocol Specification

The extraction targets are contained inside the production asset archives located at:

```bash
/usr/lib/claude-desktop/node_modules/electron/dist/resources/app.asar.unpacked/
```

The primary coordinator daemon (`cowork-vm-service.js`) establishes a localized inter-process communication pipeline over standard Unix Domain Sockets.

### 3.1 Network Transport Vector

- **Transport Protocol:** Streaming Unix Domain Socket (`SOCK_STREAM`)
- **Default Active Path:** `$XDG_RUNTIME_DIR/cowork-vm-service.sock`

### 3.2 Wire Message Framing Layout

All transactions traveling across the socket are framed using a precise length-prefixed protocol.

1. **Header:** 4-Byte Unsigned Big-Endian Integer (`readUInt32BE`) defining the exact octet footprint of the subsequent string payload.
2. **Payload:** A raw, variable-length UTF-8 encoded string containing a serialized JSON-RPC object format block.

```bash
+-----------------------------------+-----------------------------------------------+
|  Length Prefix (4 Bytes, Big-End) |  JSON Payload (UTF-8 Encoded String)          |
|  e.g., \x00\x00\x00\x2A           |  {"method":"spawn","params":{...},"id":1}     |
+-----------------------------------+-----------------------------------------------+
```

## 4. The JSON-RPC Execution API Reference

Communications dispatched to `cowork-vm-service.sock` target the internal `METHODS` routing map object. The server processes arguments through an asynchronous dispatch pattern: `await handler(params || {}, socket)`.

### 4.1 Supported Methods

| **Method Vector**      | **Expected Parameters**                     | **System Action Behavior**                                   |
| ---------------------- | ------------------------------------------- | ------------------------------------------------------------ |
| **`configure`**        | `(params)`                                  | Sets runtime resource quotas, environment bounds, or storage roots. |
| **`createVM`**         | `(params)`                                  | Instances the host-side sandboxing template configuration layers. |
| **`startVM`**          | `(params)`                                  | Spawns background system virtualization layers (`qemu`, `bwrap`, `virtiofsd`). |
| **`stopVM`**           | `()`                                        | Gracefully winds down the active container context frameworks. |
| **`isRunning`**        | `()`                                        | Verification flag returning structural host-to-guest execution statuses. |
| **`isGuestConnected`** | `()`                                        | Confirms socket tunnel presence via `socat` over local `vsock` lines. |
| **`spawn`**            | `(params: { id, command, args, cwd, env })` | **Core Runtime.** Spawns system tools inside unprivileged bubblewrap environments. |
| **`kill`**             | `(params: { id })`                          | Sends an immediate signal kill down to a tracked process thread. |
| **`writeStdin`**       | `(params: { id, data })`                    | Pipes character data to active tasks managed via `node-pty`. |
| **`isProcessRunning`** | `(params: { id })`                          | Audits whether a specifically tracked process instance is alive. |
| **`mountPath`**        | `(params: { hostPath, mountName })`         | Binds local project directories cleanly inside the virtualization layout. |
| **`readFile`**         | `(params)`                                  | Programmatically pulls arbitrary logs out from isolated container targets. |
| **`subscribeEvents`**  | `(params, socket)`                          | Attaches the active wire connection descriptor to listen to streaming IO frames. |

## 5. Erebos Headless Integration Engine

The following Python framework maps directly to the wire protocol invariants, allowing any automated orchestration pipeline inside Erebos to control sandboxed tasks without invoking Electron or running a desktop display environment.

Python

```python
import os
import json
import socket
import struct

class CoworkSocketClient:
    def __init__(self, socket_path=None):
        if socket_path is None:
            xdg_runtime = os.environ.get("XDG_RUNTIME_DIR", "/run/user/1000")
            socket_path = os.path.join(xdg_runtime, "cowork-vm-service.sock")
        
        self.socket_path = socket_path
        self.sock = None

    def connect(self):
        """Establish direct Unix domain socket connection to the cowork service."""
        if not os.path.exists(self.socket_path):
            raise FileNotFoundError(f"Cowork daemon socket not found at {self.socket_path}")
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)

    def send_message(self, message_dict):
        """Pack payload with a 4-byte Big-Endian length header and transmit."""
        payload = json.dumps(message_dict).encode('utf-8')
        header = struct.pack('>I', len(payload)) # >I matches Big-Endian UInt32
        self.sock.sendall(header + payload)

    def receive_message(self):
        """Read 4-byte header, determine size, and decode the incoming JSON payload."""
        header = self.sock.recv(4)
        if not header or len(header) < 4:
            return None
        
        length = struct.unpack('>I', header)[0]
        
        data = b""
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise ConnectionError("Socket closed prematurely while reading payload buffer.")
            data += chunk
            
        return json.loads(data.decode('utf-8'))

    def execute_task(self, project_path, target_command):
        """High-level orchestration routine to mount a path, subscribe to IO, and execute."""
        self.connect()

        # Mount target repository space
        self.send_message({
            "method": "mountPath",
            "params": {"hostPath": os.path.abspath(project_path), "mountName": "workspace"},
            "id": 1
        })
        print("[MOUNT]:", self.receive_message())

        # Bind event streaming listeners
        self.send_message({"method": "subscribeEvents", "params": {}, "id": 2})
        print("[SUBSCRIPTION]:", self.receive_message())

        # Spawn the task
        self.send_message({
            "method": "spawn",
            "params": {
                "id": "erebos_run_t1",
                "command": target_command,
                "args": [],
                "cwd": "/workspace",
                "env": {"PATH": "/usr/bin:/bin"}
            },
            "id": 3
        })

        # Process real-time streaming output data packets
        try:
            while True:
                packet = self.receive_message()
                if not packet:
                    break
                if "type" in packet and packet["type"] in ["stdout", "stderr"]:
                    print(f"[{packet['type'].upper()}]: {packet['data']}", end="")
        except KeyboardInterrupt:
            self.send_message({"method": "kill", "params": {"id": "erebos_run_t1"}, "id": 4})
        finally:
            self.close()

    def close(self):
        if self.sock:
            self.sock.close()
```