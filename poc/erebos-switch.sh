#!/usr/bin/env bash
# erebos-switch.sh <profile> — switch the embedded "tab" to one account.
# Correct discipline (POC rule #6): unmap others -> map target -> resize -> raise -> focus.
# Filters on `claude-desktop` so Steam / Chrome claude.ai tabs are never matched.
#
# Usage: ./erebos-switch.sh pro|free1|free2|free3

set -uo pipefail
TARGET="${1:?usage: erebos-switch.sh <pro|free1|free2|free3>}"
ROOT="$HOME/.config/claude-harness"
ACCOUNTS=(pro free1 free2 free3)
CANVAS_W=1820; CANVAS_H=980

find_window() {  # $1 = session dir -> largest-area window id
    local S="$1" best="" besta=0
    for PID in $(pgrep -af claude-desktop | grep -v erebos | grep -F "$S" | awk '{print $1}'); do
        for w in $(xdotool search --pid "$PID" 2>/dev/null); do
            local g wd a
            g=$(xdotool getwindowgeometry "$w" 2>/dev/null | grep -o 'Geometry: [0-9]*x[0-9]*')
            [ -z "$g" ] && continue
            wd=${g#*: }; a=$(( ${wd%x*} * ${wd#*x} ))
            if [ "$a" -gt "$besta" ]; then besta=$a; best=$w; fi
        done
    done
    echo "$best"
}

# 1. unmap every OTHER account's window (exclusivity)
for A in "${ACCOUNTS[@]}"; do
    [ "$A" = "$TARGET" ] && continue
    W=$(find_window "$ROOT/$A/session-data")
    [ -n "$W" ] && xdotool windowunmap "$W" 2>/dev/null
done

# 2. surface target: map -> resize -> raise -> focus
TW=$(find_window "$ROOT/$TARGET/session-data")
if [ -z "$TW" ]; then echo "ERROR: no window for '$TARGET' (logged in? embedded?)"; exit 1; fi
xdotool windowmap   "$TW" 2>/dev/null; sleep 0.2
xdotool windowsize  "$TW" "$CANVAS_W" "$CANVAS_H" 2>/dev/null
xdotool windowraise "$TW" 2>/dev/null
xdotool windowfocus "$TW" 2>/dev/null
echo "switched to $TARGET (wid $TW)"
