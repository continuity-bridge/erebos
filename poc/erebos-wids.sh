#!/usr/bin/env bash
# erebos-wids.sh — print the CURRENT real (largest-area) window id for each account.
# Filters on `claude-desktop` (NOT the broad `user-data-dir`, which also matches Steam
# and Chrome claude.ai tabs). Window ids rot across respawns — always re-derive.
#
# Usage: ./erebos-wids.sh

ROOT="$HOME/.config/claude-harness"
ACCOUNTS=(pro free1 free2 free3)

claude_pids_for() {  # $1 = session dir
    pgrep -af claude-desktop | grep -v erebos | grep -F "$1" | awk '{print $1}'
}

for A in "${ACCOUNTS[@]}"; do
    S="$ROOT/$A/session-data"
    best=""; besta=0
    for PID in $(claude_pids_for "$S"); do
        for w in $(xdotool search --pid "$PID" 2>/dev/null); do
            g=$(xdotool getwindowgeometry "$w" 2>/dev/null | grep -o 'Geometry: [0-9]*x[0-9]*')
            [ -z "$g" ] && continue
            wd=${g#*: }; a=$(( ${wd%x*} * ${wd#*x} ))
            if [ "$a" -gt "$besta" ]; then besta=$a; best=$w; fi
        done
    done
    printf "%-6s = %-10s (area %s)\n" "$A" "${best:-NONE}" "$besta"
done

HOST=$(xdotool search --name "erebos-host" | head -1)
printf "%-6s = %-10s\n" "host" "${HOST:-NONE}"
