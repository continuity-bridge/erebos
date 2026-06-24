# Security Implications: bwrap/KVM via the daemon vs standard MCP stdio transport

Based on the provided documentation, the security implications of using `bwrap` or `KVM` via the daemon differ fundamentally from standard MCP `stdio` transport in terms of isolation, attack surface, and the "trust boundary" of the execution environment.

### 1. Isolation Depth (The Sandbox vs. The Host)
*   **Standard MCP Stdio Transport:** The pipeline script initiates MCP servers via `StdioServerParameters` [69]. In this model, the tools typically run as processes on the host machine. The security boundary is primarily defined by the permissions of the user running the pipeline; if a tool is compromised, it has the same access to the host as the pipeline process.
*   **Daemon-based Isolation (`bwrap`/`KVM`):** The `cowork-vm-service.js` daemon implements a pluggable backend system to enforce strict isolation [70]:
    *   **BwrapBackend:** Uses `bubblewrap` for namespace sandboxing [70].
    *   **KvmBackend:** Utilizes QEMU/KVM virtual machines for "stronger isolation" [70].
    *   **HostBackend:** This is a fallback that provides no isolation [70].
    *   **Implication:** By routing through the daemon, the system can move execution from the host's primary environment into a restricted namespace or a full virtual machine, preventing tools from accessing the broader host filesystem unless explicitly allowed.

### 2. Controlled Resource Access
*   **Standard MCP:** Access to the filesystem is generally handled by the MCP server's internal logic or the environment it was started in [69].
*   **Daemon-based Control:** The daemon provides a structured API for managing the environment. Specifically, the **`mountPath`** method allows the system to "bind local project directories cleanly inside the virtualization layout" [19]. 
    *   **Implication:** This creates a "white-list" approach to filesystem access. Instead of giving a tool access to the whole home directory, the operator can surgically mount only the necessary project folders into the sandbox [19].

### 3. Communication and Attack Surface
*   **Standard MCP:** Uses standard input/output (`stdio`) for communication between the client and the server [69].
*   **Daemon-based Communication:** Uses a Unix Domain Socket at `$XDG_RUNTIME_DIR/cowork-vm-service.sock` [19, 68, 70].
    *   **Implication:** The communication is shifted to a local socket with a specific, length-prefixed JSON-RPC protocol [70]. This allows for a cleaner separation between the "Controller" (the pipeline/Erebos) and the "Executor" (the daemon).

### 4. Resilience to Upstream Changes
*   **Standard MCP:** While MCP is a protocol, the specific tools and their implementations may change.
*   **Daemon-based Stability:** The daemon's `METHODS` schema (`spawn`, `mountPath`, `writeStdin`) is noted as being "highly stable" because it is a requirement for the official desktop client's web panel to function [20]. 
    *   **Implication:** Using the daemon reduces the risk of "breaking" the security or execution layer during upstream application updates, as the JSON-RPC interface keys must remain consistent to avoid breaking the product's own internal stack [20].

### Summary Comparison Table

| Security Vector     | Standard MCP Stdio             | Daemon (`bwrap`/`KVM`)             |
| :------------------ | :----------------------------- | :--------------------------------- |
| **Execution Space** | Host Process [69]              | Namespace Sandbox or VM [70]       |
| **FS Access**       | Process-level permissions [69] | Explicit `mountPath` bindings [19] |
| **Transport**       | `stdio` streams [69]           | Unix Domain Socket [19, 68]        |
| **Isolation Level** | Low (User-level)               | High (Kernel/Hardware-level) [70]  |