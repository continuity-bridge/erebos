# Erebos POC — X11 Multi-Account Claude Harness

Working proof-of-concept for running multiple isolated Claude Desktop
instances sharing a single Substrate. This is the reference implementation
for the eventual GTK4-native Erebos app.

## What It Does

Launches up to 4 Claude Desktop accounts simultaneously, each with:
- **Isolated session data** (login tokens, cookies) via `--user-data-dir`
- **Shared Substrate** (filesystem MCP access to `/srv/Reliquary/`)
- **Shared MCP config** (`~/.config/Claude/claude_desktop_config.json`)

All 4 windows are reparented into a single xterm host window. `erebos-switch.sh`
provides tab-like switching by mapping/unmapping windows. No tab bar UI yet —
that's the GTK4 app's job.

---

## Prerequisites

- Claude Desktop installed via the aaddrick APT repository
- `xdotool` installed (`sudo apt install xdotool`)
- Tailscale running (if Substrate lives on a remote NFS mount)
- `/srv/Reliquary/` accessible with user-level read/write
- `~/.config/Claude/claude_desktop_config.json` configured with the
  shared Filesystem MCP server entry
- `claude-harness-dispatch.sh` registered as the `claude://` URL handler
  (see OAuth Setup below)

---

## Scripts

| Script | Purpose |
|--------|---------|
| `launch-harness.sh` | Launch all 4 accounts (or one: `./launch-harness.sh pro`) |
| `erebos-embed-all.sh` | Embed all running instances into xterm host |
| `erebos-switch.sh` | Switch visible "tab": `./erebos-switch.sh pro\|free1\|free2\|free3` |
| `erebos-wids.sh` | Diagnostic — print current window IDs for all accounts |
| `claude-login.sh` | Authenticate one profile (see OAuth Setup) |
| `claude-harness-dispatch.sh` | System `claude://` URL handler — routes OAuth callbacks |
| `claude-title.sh` | Set per-profile window titles (called internally) |

---

## First Run: Account Setup

Each account needs to be authenticated once before the harness works.
Do them one at a time:

```bash
# 1. Focus the Chrome window signed into the matching Google account FIRST.
#    Google auth opens against whichever Chrome profile has focus — this is
#    the most common source of accounts getting crossed.

# 2. Launch login for one profile
./claude-login.sh pro

# 3. Log in via the Claude window that appears
#    The OAuth callback will be routed to the correct session store
#    by claude-harness-dispatch.sh (valid for 5 minutes)

# 4. Repeat for free1, free2, free3
```

**Why the Chrome focus step matters:** Claude Desktop's OAuth flow opens
a browser window. If the wrong Chrome profile has focus, you'll authenticate
the wrong Google account and the session lands in the wrong store.

---

## OAuth Setup

`claude-harness-dispatch.sh` must be registered as the system handler for
`claude://` URLs so OAuth callbacks route to the correct profile.

```bash
# Create .desktop entry
cat > ~/.local/share/applications/claude-harness-dispatch.desktop << 'EOF'
[Desktop Entry]
Name=Claude Harness Dispatcher
Exec=/home/tallest/Scriptorium/multisession-claude-testing/claude-harness-dispatch.sh %u
Type=Application
MimeType=x-scheme-handler/claude;
NoDisplay=true
EOF

# Register it
xdg-mime default claude-harness-dispatch.desktop x-scheme-handler/claude
update-desktop-database ~/.local/share/applications/
```

---

## Normal Usage (After Setup)

```bash
# Launch all 4 accounts
./launch-harness.sh

# Embed them into the host window
./erebos-embed-all.sh

# Switch between accounts
./erebos-switch.sh pro
./erebos-switch.sh free1
./erebos-switch.sh free2
./erebos-switch.sh free3

# Check window state
./erebos-wids.sh
```

---

## Architecture Notes

### Why COWORK_VM_BACKEND=host

Claude Desktop's aaddrick build uses bubblewrap to sandbox the app.
By default, bubblewrap mounts `$HOME` read-only and blocks access to
paths outside it. `/srv/Reliquary/` is outside `$HOME`.

Setting `COWORK_VM_BACKEND=host` disables the bubblewrap sandbox,
allowing the Filesystem MCP server to access `/srv/Reliquary/` directly.
This is the intended escape hatch for exactly this use case.

### Why setsid + TSTP trap

Electron's single-instance handoff mechanism sends a `SIGTSTP` to the
process group when a second instance tries to launch. Without protection,
this suspends the launch script mid-sequence — the second, third, and
fourth accounts never launch.

`erebos-embed-all.sh` guards against this with:
```bash
trap '' TSTP TTIN TTOU
```
and launches each account with `setsid` to put it in its own session,
fully detached from the controlling terminal.

### Why xterm as host

The host window needs to be a stable X11 container that won't interfere
with reparented Electron windows. xterm with `sleep 999999` is the
simplest possible stable X11 window. The GTK4 app will replace this
with a proper container + tab bar.

### MCP config is shared, session data is isolated

All 4 accounts read the same `~/.config/Claude/claude_desktop_config.json`.
This means all 4 instances get the same MCP tools (Filesystem, Notion, etc.)
pointing at the same Substrate. Session data (auth tokens, cookies, local
storage) is isolated per account via `--user-data-dir`.

---

## Known Limitations (POC)

- **X11 only** — depends on xdotool/xwininfo; not Wayland-native
- **No tab bar** — switching requires running `erebos-switch.sh` from terminal
- **labwc titlebar quirk** — requires 1px resize nudge to repaint after rename
- **7-second launch wait** — conservative; may be reducible on faster machines
- **xterm host** — unstyled, functional only
- **Single host window** — all 4 accounts share one fixed canvas size

All of these are presentation/UX issues. The underlying architecture
(isolation, shared substrate, OAuth routing) is sound and carries forward
to the GTK4 rewrite unchanged.

---

## Relationship to GTK4 App

This POC establishes and validates the complete architecture. The GTK4
app replaces only the presentation layer:

| POC | GTK4 App |
|-----|----------|
| xterm host window | GTK4 ApplicationWindow |
| `erebos-switch.sh` | Tab bar widget |
| `erebos-wids.sh` | Internal window registry |
| `launch-harness.sh` | Launch manager / account picker |
| `claude-title.sh` | Window label in tab bar |

The OAuth flow, `COWORK_VM_BACKEND=host`, `--user-data-dir` isolation,
and shared MCP config carry forward unchanged.

---

**Status**: Working POC — all 4 accounts functional on Sisyphus (Debian 13, labwc/Wayland via XWayland)  
**Next**: GTK4 native app with tab bar UI  
**Reference**: See root `README.md` for full Erebos project context
