#!/usr/bin/env bash
# claude-title <profile> <session_dir> — find the Claude window belonging to the
# instance launched with --user-data-dir=<session_dir> and set its titlebar text.
PROFILE="$1"; SESSION="$2"
TITLE="Claude — $PROFILE"

for i in $(seq 1 30); do        # up to ~15s for the window to appear
    sleep 0.5
    # PID of the claude-desktop instance using THIS session dir:
    PID=$(pgrep -af 'user-data-dir' | grep -F "$SESSION" | grep -v claude-title | awk '{print $1}' | head -1)
    [ -z "$PID" ] && continue
    # Find that PID's visible X11 window (full-size, not the 10x10 helpers):
    for w in $(xdotool search --pid "$PID" 2>/dev/null); do
        geo=$(xdotool getwindowgeometry "$w" 2>/dev/null)
        echo "$geo" | grep -q 'Geometry: [0-9]\{3,\}x[0-9]\{3,\}' || continue
        xdotool set_window --name "$TITLE" "$w"
        # nudge labwc to repaint the titlebar:
        W=$(echo "$geo" | sed -n 's/.*Geometry: \([0-9]*\)x.*/\1/p')
        H=$(echo "$geo" | sed -n 's/.*Geometry: [0-9]*x\([0-9]*\).*/\1/p')
        xdotool windowsize "$w" $((W-1)) "$H"; sleep 0.2; xdotool windowsize "$w" "$W" "$H"
        exit 0
    done
done
