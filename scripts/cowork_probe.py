#!/usr/bin/env python3
"""
cowork_probe.py — READ-ONLY protocol-match probe for the cowork-vm-service daemon.

Run this ON YOUR EREBOS HOST (your desktop), NOT inside a Cowork session — it talks
to the live daemon, and you don't want to poke the one orchestrating an active
session. It only sends health-check methods (no spawn/mount/kill/writeStdin), so the
worst case is a JSON-RPC error back (which still proves the framing is real).

What it answers: does the reverse-engineered wire protocol + method surface actually
match your installed Claude Desktop daemon?

    python3 scripts/cowork_probe.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from erebos.providers.cowork_socket import CoworkSocketClient, CoworkProtocolError

READONLY_CANDIDATES = ["isRunning", "isGuestConnected"]  # health checks only

def main():
    c = CoworkSocketClient(timeout=4)
    print(f"socket: {c.socket_path}  exists={os.path.exists(c.socket_path)}")
    try:
        c.connect()
        print("connect: OK\n")
    except Exception as e:
        print(f"connect: FAILED — {type(e).__name__}: {e}"); return 1

    framed_ok = False
    for m in READONLY_CANDIDATES:
        try:
            resp = c.call(m)
            framed_ok = True
            print(f"  {m:18s} -> {resp!r}")
        except CoworkProtocolError as e:
            print(f"  {m:18s} -> PROTOCOL ERROR: {e}")
            break  # socket likely closed; stop
        except Exception as e:
            print(f"  {m:18s} -> {type(e).__name__}: {e}")
    c.close()

    # --exec: capture the REAL shapes of the exec methods (safe ops: echo + read a temp file)
    if "--exec" in sys.argv:
        import tempfile, json
        print("\n--- exec shape probe (echo + readFile) ---")
        c2 = CoworkSocketClient(timeout=6)
        try:
            c2.connect()
            tf = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
            tf.write("erebos-probe-content"); tf.close()
            print("readFile raw:", json.dumps(c2.call("readFile", {"path": tf.name}), default=str))
            print("spawn stream packets:")
            for i, pkt in enumerate(c2.stream("spawn", {
                "command": "echo", "args": ["erebos-probe"],
                "cwd": "/tmp", "env": {"PATH": "/usr/bin:/bin"},
            })):
                print("  ", json.dumps(pkt, default=str))
                if i > 12:  # safety cap so we never hang
                    break
        except Exception as e:
            print("exec probe error:", type(e).__name__, e)
        finally:
            c2.close()

    print()
    if framed_ok:
        print("RESULT: framing is REAL — daemon returned length-prefixed JSON frames.")
        print("        (A JSON-RPC error in a response still counts: method name may")
        print("         differ, but the wire protocol matches. Note which methods answered.)")
    else:
        print("RESULT: no framed response. Either the wire format differs or the method")
        print("        names are wrong. Capture any error and we revise the spec.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
