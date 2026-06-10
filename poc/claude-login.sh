#!/usr/bin/env bash
# claude-login <profile> — log in one harness profile.
# Drops the marker so claude-harness-dispatch routes the OAuth callback into THIS profile.
# REMINDER: focus the Chrome window signed into the <profile> Google account BEFORE
#           clicking Log in, so Google auth opens against the right account.
set -euo pipefail
PROFILE="${1:?usage: claude-login <profile>}"
ROOT="$HOME/.config/claude-harness"
SESSION="$ROOT/$PROFILE/session-data"
mkdir -p "$SESSION"
echo "$SESSION" > "$ROOT/.active-login-target"
echo "Login target: $PROFILE -> $SESSION"
echo ">>> Focus the Chrome profile for '$PROFILE', THEN click Log in in the Claude window."
COWORK_VM_BACKEND=host claude-desktop \
    --ozone-platform-hint=auto --enable-features=WaylandWindowDecorations \
    --disable-gpu-compositing --ignore-gpu-blocklist \
    --user-data-dir="$SESSION" & disown
echo "Launched $PROFILE (pid $!). Terminal is free."
