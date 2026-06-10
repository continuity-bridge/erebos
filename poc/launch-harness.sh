#!/bin/bash
# launch-harness.sh
# Multi-account Claude Desktop harness for Sisyphus (Debian 13, aaddrick build)
#
# Architecture:
#   - MCP config: SHARED — all accounts read ~/.config/Claude/claude_desktop_config.json
#     (aaddrick build hardcodes this path; --user-data-dir does NOT redirect it)
#   - Session data: ISOLATED per account via --user-data-dir
#     (login tokens, cookies, local storage — keeps accounts from stomping each other)
#   - Substrate: SHARED — all accounts get filesystem access to the same folder
#     via the single shared MCP config
#   - bwrap bypass: COWORK_VM_BACKEND=host — substrate lives at /srv/Reliquary/
#     which is outside $HOME and would be blocked by bubblewrap's read-only home mount
#
# Prerequisites:
#   - claude-desktop installed via aaddrick APT repo
#   - ~/.config/Claude/claude_desktop_config.json already configured with
#     the shared-substrate MCP server entry (see config section below)
#   - /srv/Reliquary/ accessible with user-level read/write
#
# Usage:
#   chmod +x launch-harness.sh
#   ./launch-harness.sh
#
# To launch a single account:
#   ./launch-harness.sh pro
#   ./launch-harness.sh free1
#   ./launch-harness.sh free2
#   ./launch-harness.sh free3

# ─── CONFIG ──────────────────────────────────────────────────────────────────

# Session data root — each account gets its own subdirectory here
SESSION_ROOT="$HOME/.config/claude-harness"

# Account names — used as subdirectory names under SESSION_ROOT
# Adjust to match your actual account labels if preferred
ACCOUNTS=("pro" "free1" "free2" "free3")

# ─── FUNCTIONS ───────────────────────────────────────────────────────────────

launch_account() {
    local ACCOUNT_NAME="$1"
    local SESSION_DIR="$SESSION_ROOT/$ACCOUNT_NAME/session-data"

    mkdir -p "$SESSION_DIR"
    echo "Launching: $ACCOUNT_NAME → session data: $SESSION_DIR"

    # --class sets app_id per account (Claude-pro, Claude-free1, …) so Waybar
    #   and labwc can tell windows apart. Wayland flags match claude-login.
    # COWORK_VM_BACKEND=host bypasses bwrap (substrate at /srv/Reliquary/, outside $HOME).
    COWORK_VM_BACKEND="host" claude-desktop \
        --class="Claude-$ACCOUNT_NAME" \
        --ozone-platform-hint=auto --enable-features=WaylandWindowDecorations \
        --disable-gpu-compositing --ignore-gpu-blocklist \
        --user-data-dir="$SESSION_DIR" &

    sleep 1
}
# ─── MAIN ────────────────────────────────────────────────────────────────────

# If a specific account name was passed as argument, launch only that one
if [[ -n "$1" ]]; then
    launch_account "$1"
else
    for ACCOUNT in "${ACCOUNTS[@]}"; do
        launch_account "$ACCOUNT"
    done
fi

echo ""
echo "Harness launched. Accounts:"
for ACCOUNT in "${ACCOUNTS[@]}"; do
    echo "  $ACCOUNT → $SESSION_ROOT/$ACCOUNT/session-data"
done
echo ""
echo "MCP config (shared by all accounts): ~/.config/Claude/claude_desktop_config.json"
echo ""
echo "First run: log into each window with its respective account."
echo "Subsequent runs: sessions persist via --user-data-dir."
