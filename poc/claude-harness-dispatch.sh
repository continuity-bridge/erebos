#!/usr/bin/env bash
# Routes claude:// OAuth callbacks to the profile that's mid-login.
# Reads the marker claude-login drops; re-invokes claude-desktop bound to that
# profile's --user-data-dir so the auth cookie lands in the right session store.
ROOT="$HOME/.config/claude-harness"
MARKER="$ROOT/.active-login-target"
FLAGS=(--ozone-platform-hint=auto --enable-features=WaylandWindowDecorations
       --disable-gpu-compositing --ignore-gpu-blocklist)

TARGET=""
# Honor the marker only if fresh (<5 min), so a stray later callback isn't misrouted.
if [[ -f "$MARKER" ]] && (( $(date +%s) - $(stat -c %Y "$MARKER") < 300 )); then
    TARGET="$(cat "$MARKER")"
fi

if [[ -n "$TARGET" ]]; then
    exec env COWORK_VM_BACKEND=host claude-desktop "${FLAGS[@]}" --user-data-dir="$TARGET" "$@"
else
    exec claude-desktop "${FLAGS[@]}" "$@"
fi
