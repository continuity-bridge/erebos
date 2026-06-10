#!/usr/bin/env bash
# erebos-embed-all.sh — launch + embed all 4 accounts STRICTLY ONE AT A TIME.
# INSTRUMENTED build: heavy stdout + logfile tracing to see exactly what happens.
#
# Usage: ./erebos-embed-all.sh            (logs to stdout AND ./erebos-embed.log)
#        ./erebos-embed-all.sh --no-host  (skip building/using a host; just launch+trace)

set -uo pipefail

# Harden against terminal job-control: the app's single-instance handoff
# emits a stop signal that was suspending this script at the 2nd launch.
trap '' TSTP TTIN TTOU   # ignore suspend / background-IO stops


ACCOUNTS=(pro free1 free2 free3)
ROOT="$HOME/.config/claude-harness"
HARNESS_DIR="$HOME/Scriptorium/multisession-claude-testing"
CANVAS_W=1820
CANVAS_H=980
HOST_TITLE="erebos-host"
STATE="$ROOT/.erebos-embed-state"
LOG="$HARNESS_DIR/erebos-embed.log"
LAUNCH_WAIT=7
POLL_TRIES=20
DO_HOST=1
[ "${1:-}" = "--no-host" ] && DO_HOST=0

# ── logging ──────────────────────────────────────────────────────────────────
ts() { date '+%H:%M:%S.%3N'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }
: > "$LOG"

# ── dump: every claude-desktop main process, its --user-data-dir, and windows ──
dump_state() {
    log "  --- state dump ($1) ---"
    # main electron processes that carry a --user-data-dir (the per-account ones)
    while read -r pid cmd; do
        [ -z "$pid" ] && continue
        # extract the session dir from the cmdline
        local udd
        udd=$(echo "$cmd" | grep -o -- '--user-data-dir=[^ ]*' | head -1 | sed 's/--user-data-dir=//')
        [ -z "$udd" ] && continue
        local prof="${udd%/session-data}"; prof="${prof##*/}"
        log "    PID $pid  profile=$prof"
        for w in $(xdotool search --pid "$pid" 2>/dev/null); do
            local g name parent
            g=$(xdotool getwindowgeometry "$w" 2>/dev/null | grep -o 'Geometry: [0-9]*x[0-9]*' | sed 's/Geometry: //')
            name=$(xdotool getwindowname "$w" 2>/dev/null)
            parent=$(xwininfo -id "$w" -tree 2>/dev/null | awk -F'[ x]' '/Parent window id/{print $4}')
            log "      win $w  geo=${g:-?}  parent=${parent:-?}  name=[$name]"
        done
    done < <(pgrep -af claude-desktop | grep -v 'erebos-embed' | awk '{pid=$1; $1=""; print pid, $0}' | sort -u -k1,1)
    log "  --- end dump ---"
}

find_toplevel() {  # $1 = session dir -> largest-area window id
    local S="$1" best="" besta=0
    for PID in $(pgrep -af claude-desktop | grep -F "$S" | awk '{print $1}'); do
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

count_claude_pids() { pgrep -af claude-desktop | grep -v erebos-embed | grep -c . ; }

# ── MANDATORY teardown: prior runs leave instances + hosts that poison results ──
log_pre() { echo "[$(date '+%H:%M:%S.%3N')] $*"; }
log_pre "TEARDOWN: killing any existing claude-desktop instances + erebos hosts..."
pkill -9 -f claude-desktop 2>/dev/null
for oldh in $(xdotool search --name "erebos-host" 2>/dev/null); do xdotool windowkill "$oldh" 2>/dev/null; done
pkill -f "sleep 999999" 2>/dev/null
sleep 3
LEFT=$(pgrep -af claude-desktop | grep -v erebos | grep -c .)
if [ "$LEFT" -ne 0 ]; then
    log_pre "ABORT: $LEFT claude-desktop process(es) survived teardown. Investigate before embedding:"
    pgrep -af claude-desktop | grep -v erebos
    exit 1
fi
log_pre "TEARDOWN: clean (0 claude-desktop processes)."

log "=== erebos-embed-all START (host=$DO_HOST, wait=${LAUNCH_WAIT}s) ==="
log "PRE-FLIGHT: existing claude windows BEFORE we do anything:"
dump_state "pre-flight"
n=$(count_claude_pids)
log "PRE-FLIGHT: $n existing claude --user-data-dir processes."
[ "$n" -gt 0 ] && log "  !! NOTE: instances already running. These can absorb new launches. Consider: pkill -f claude-desktop; sleep 2"

HOST=""
if [ "$DO_HOST" = "1" ]; then
    log "Killing any stale '$HOST_TITLE' hosts first..."
    for oldh in $(xdotool search --name "$HOST_TITLE" 2>/dev/null); do
        log "  killing stale host window $oldh"
        xdotool windowkill "$oldh" 2>/dev/null
    done
    pkill -f "sleep 999999" 2>/dev/null
    sleep 1
    log "Building host window ($HOST_TITLE)..."
    xterm -geometry 120x55 -T "$HOST_TITLE" -e 'sleep 999999' & disown
    sleep 2
    # take the NEWEST matching window (last id), never a leftover
    HOST=$(xdotool search --name "$HOST_TITLE" | tail -1)
    if [ -z "$HOST" ]; then log "ABORT: host window did not appear"; exit 1; fi
    xdotool windowsize "$HOST" "$CANVAS_W" "$CANVAS_H"
    log "  host = $HOST"
fi

: > "$STATE"; echo "HOST=$HOST" >> "$STATE"

for A in "${ACCOUNTS[@]}"; do
    log "================ $A ================"
    S="$ROOT/$A/session-data"; mkdir -p "$S"

    BEFORE_WID=$(find_toplevel "$S")
    BEFORE_PIDS=$(count_claude_pids)
    log "$A: before launch -> existing window for this session = [${BEFORE_WID:-none}]; total claude pids = $BEFORE_PIDS"

    log "$A: exec claude-desktop --user-data-dir=$S"
    # setsid = own session/process-group, fully detached from this terminal so the
    # app's single-instance handoff can't send a stop signal to THIS script.
    # stdio -> /dev/null so it can never grab the controlling terminal.
    setsid env COWORK_VM_BACKEND=host claude-desktop \
        --ozone-platform-hint=auto --enable-features=WaylandWindowDecorations \
        --disable-gpu-compositing --ignore-gpu-blocklist \
        --user-data-dir="$S" </dev/null >/dev/null 2>&1 & disown
    LAUNCH_RET=$?
    log "$A: launch command returned $LAUNCH_RET (backgrounded). Waiting ${LAUNCH_WAIT}s..."
    sleep "$LAUNCH_WAIT"

    AFTER_PIDS=$(count_claude_pids)
    log "$A: claude pids after wait = $AFTER_PIDS (was $BEFORE_PIDS) -> $([ "$AFTER_PIDS" -gt "$BEFORE_PIDS" ] && echo 'NEW process appeared (good)' || echo 'NO new process -> single-instance REUSE likely!')"
    dump_state "after $A launch+wait"

    WID=""
    for ((i=0; i<POLL_TRIES; i++)); do
        WID=$(find_toplevel "$S"); [ -n "$WID" ] && break; sleep 0.5
    done
    log "$A: resolved window = [${WID:-NONE}] (was [${BEFORE_WID:-none}] before)"

    if [ -z "$WID" ]; then log "$A: NONE — skipping (authenticated? window up?)"; continue; fi
    if [ -n "$BEFORE_WID" ] && [ "$WID" = "$BEFORE_WID" ]; then
        log "$A: !! resolved to PRE-EXISTING window $WID -> SINGLE-INSTANCE REUSE confirmed."
    fi

    if [ "$DO_HOST" = "1" ]; then
        log "$A: pre-size $WID -> ${CANVAS_W}x${CANVAS_H}, then reparent into host $HOST"
        xdotool windowsize "$WID" "$CANVAS_W" "$CANVAS_H"
        xdotool windowreparent "$WID" "$HOST"; rc=$?
        log "$A: reparent exit $rc"
        xdotool windowmap "$WID" 2>/dev/null; xdotool windowraise "$WID" 2>/dev/null
    fi
    echo "${A}=${WID}" >> "$STATE"
    sleep 1
done

log "=== DONE. Full log at $LOG ==="
[ "$DO_HOST" = "1" ] && { "$HARNESS_DIR/erebos-switch.sh" pro 2>/dev/null || log "(run ./erebos-switch.sh pro manually)"; }
