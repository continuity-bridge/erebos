---
title: "Updating Erebos After Claude Desktop Upgrades"
subtitle: "Automating Package Manager Hooks and Runtime ASAR Extraction Guards"
project: "erebos"
subsystem: "lifecycle-automation"
type: "maintenance-playbook"
status: "active"
version: "1.0.0"
date: "2026-06-23"
author: "The Architect"
automation_vectors:
  - apt-post-invoke
  - startup-integrity-check
dependencies:
  - "node-asar"
  - "sqlite3"
tags:
  - system-maintenance
  - automation
  - apt
  - asar
  - defensive-engineering
---

# Updating erebos after Claude Desktop updates

When the package manager updates `claude-desktop`, it completely replaces `app.asar`, which overrides the unpacked node modules, changes the minified JavaScript internals, and occasionally shifts how session cookies are tracked.

To make Erebos resilient to upstream updates, you have to split your automation into two pipelines: **The Data Layer (Auth)** and **The Execution Layer (Socket/Code)**.

### 1. Automating the Auth Layer (Zero-Maintenance)

Your data layer is already functionally future-proof because we used **Native Cross-Database Mirroring** (`ATTACH DATABASE`).

When `claude-desktop` updates, Chromium may introduce a new tracking column to the `cookies` table. Because your script executes a generic `SELECT * FROM default_db.cookies`, SQLite maps the columns dynamically on the fly based on whatever schema is resident on Sisyphus at that exact second.

To completely automate this so your target harness spaces update without you typing a thing, hook your `erebos-login-helper.sh` execution script directly into an **APT Post-Invoke Hook**.

Create a custom APT configuration file:

Bash

```bash
sudo typora /etc/apt/apt.conf.d/99-erebos-sync
```

Add this directive to tell APT to automatically run your synchronization pipeline immediately after any package transaction containing `claude-desktop` finishes upgrading:

Plaintext

```bash
DPkg::Post-Invoke {
    "if dpkg -s claude-desktop >/dev/null 2>&1; then HOME=/home/tallest /home/tallest/Scriptorium/erebos/research/erebos-login-helper.sh pro; fi";
};
```

*Note: Ensure `HOME` is explicitly declared inside the string hook because APT processes execute context routines as the root user.*

### 2. Automating the Execution Layer (The ASAR Extractor)

The execution layer is where updates cause breaking changes. When `claude-desktop` upgrades, it drops a fresh, unpatched `app.asar` archive into place, which will temporarily break your access to the internal `cowork-vm-service.js` source files if you are referencing a static staging folder.

To prevent this, modify your native client setup or `claude.py` framework to check for file drift on initialization. Instead of manually running `npx asar extract`, implement an **Automatic Extraction Guard** inside your Erebos startup routing loop.

#### 🐍 Add an ASAR Integrity Check to `claude.py`

Add this method to your core engine so Erebos checks if the system binary version has drifted past your extracted cache version every time it boots:

Python

```python
import os
import subprocess
import shutil

def verify_and_refresh_source_payload():
    system_asar_path = "/usr/lib/claude-desktop/node_modules/electron/dist/resources/app.asar"
    extracted_app_dir = os.path.expanduser("~/Scriptorium/erebos/research/extracted-app")
    version_marker_file = os.path.join(extracted_app_dir, ".upstream_timestamp")
    
    if not os.path.exists(system_asar_path):
        print("[EREBOS WARN] System Claude Desktop installation not found.")
        return

    # Check the actual modification time of the system's package archive
    system_mtime = os.path.getmtime(system_asar_path)
    
    # Check if we have a matching cached signature token on disk
    cached_mtime = 0
    if os.path.exists(version_marker_file):
        with open(version_marker_file, "r") as f:
            try:
                cached_mtime = float(f.read().strip())
            except ValueError:
                pass

    # If the system package has a newer timestamp, an update occurred!
    if system_mtime > cached_mtime:
        print("==> [UPDATE DETECTED] Upstream app.asar has changed. Re-extracting core modules...")
        
        # Clean out old extracted payload space to clear out stale artifacts
        if os.path.exists(extracted_app_dir):
            shutil.rmtree(extracted_app_dir)
        os.makedirs(extracted_app_dir, exist_ok=True)
        
        # Extract the fresh assets cleanly
        subprocess.run([
            "npx", "asar", "extract", system_asar_path, extracted_app_dir
        ], check=True)
        
        # Drop the current system timestamp flag into place as our token baseline
        with open(version_marker_file, "w") as f:
            f.write(str(system_mtime))
            
        print("==> [SUCCESS] Erebos orchestration assets updated to match the system upgrade.")
```

### 3. Bulletproofing the Sockets Against Upstream Changes

The brilliant part of targeting the `METHODS` schema over the Unix socket (`$XDG_RUNTIME_DIR/cowork-vm-service.sock`) is that **the API protocol surface is highly stable.** Anthropic's core product design relies on the desktop client web panel passing requests like `spawn`, `mountPath`, and `writeStdin` down to the background engine. Even if the project minifies or refactors the internal JavaScript variable names within `cowork-vm-service.js`, the JSON-RPC interface keys (`method`, `params`, `id`) cannot change without breaking compatibility with their own web stack.

By utilizing the **APT Post-Invoke Hook** to seamlessly sync your authentication layer and the **ASAR Integrity Check** to refresh your headless code cache, Erebos will cleanly absorb upstream application updates in the background without needing manual code repairs.