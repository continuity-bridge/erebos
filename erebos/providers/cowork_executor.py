"""
erebos/providers/cowork_executor.py

CoworkToolExecutor — maps Anthropic `tool_use` blocks onto cowork-vm-service
methods, with a capability-gated fallback to standard MCP stdio.

Confirmed against the live daemon (2026-06-25, host probe):
  - wire framing is real; response envelope is {"success": bool, "result": {...}, "id": int}
  - isRunning / isGuestConnected answer cleanly

Tool -> method mapping (research/erebos-architectural-integration-vs-pipeline-findings.md):
  bash_tool  -> spawn
  read_file  -> readFile
  write_file -> writeStdin | mountPath+spawn   (deferred to MCP fallback for now)

NOTE: spawn streaming/exit packet shape is ASSUMED pending host confirmation
(scripts/cowork_probe.py --exec). Adjust _collect_spawn() to the real shape.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from .cowork_socket import CoworkSocketClient, CoworkProtocolError

logger = logging.getLogger(__name__)

# exceptions that mean "cowork path unavailable -> fall back to MCP"
_FALLBACK_EXC = (ConnectionError, PermissionError, FileNotFoundError, CoworkProtocolError, OSError)


class CoworkToolExecutor:
    def __init__(
        self,
        client: CoworkSocketClient,
        mcp_fallback: Optional[Callable[[str, dict], Any]] = None,
        emitter: Any = None,
        cowork_enabled: bool = True,
    ):
        self.client = client
        self.mcp_fallback = mcp_fallback
        self.emitter = emitter
        self.cowork_enabled = cowork_enabled

    # ---- envelope ---------------------------------------------------- #
    @staticmethod
    def _unwrap(resp: Optional[dict]) -> dict:
        if resp is None:
            raise CoworkProtocolError("no response from daemon")
        if not resp.get("success", False):
            raise CoworkProtocolError(resp.get("error") or f"daemon error: {resp!r}")
        return resp.get("result", {})

    # ---- public ------------------------------------------------------ #
    def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        """Capability-gated: try cowork, fall back to MCP. Mirrors the
        _execute_mcp_tool pattern from security-implications-fallback-to-mcp-path.md."""
        name = tool_name.split(":")[-1]  # tolerate "anthropic:bash_tool"
        if self.cowork_enabled:
            try:
                return self._via_cowork(name, arguments)
            except _FALLBACK_EXC as e:
                logger.warning("cowork path failed for %s: %s — falling back to MCP", name, e)
                if self.emitter is not None:
                    try:
                        self.emitter.tool_failed(tool_name, "cowork", type(e).__name__, str(e))
                    except Exception:
                        pass
                # fallthrough
        return self._via_mcp(name, arguments)

    # ---- cowork path ------------------------------------------------- #
    def _via_cowork(self, name: str, args: dict) -> Any:
        if name in ("bash", "bash_tool"):
            return self._spawn(args)
        if name in ("read_file", "readFile"):
            return self._read_file(args)
        if name in ("write_file", "writeFile", "str_replace_editor", "text_editor"):
            # write semantics not yet confirmed on the daemon -> use MCP for now
            raise CoworkProtocolError(f"{name}: write path not yet wired for cowork")
        raise CoworkProtocolError(f"unmapped tool for cowork: {name}")

    def _read_file(self, args: dict) -> str:
        path = args.get("path") or args.get("file") or args.get("filename")
        # daemon signature (host probe 2026-06-25): readFile takes a POSITIONAL paths
        # array as its params payload (params IS the array, not {"paths": [...]}).
        result = self._unwrap(self.client.call("readFile", [path]))
        return self._extract_file_content(result, path)

    @staticmethod
    def _extract_file_content(result, path) -> str:
        # success result shape not yet pinned; handle the likely forms defensively
        if isinstance(result, str):
            return result
        if isinstance(result, list):
            return result[0] if result else ""
        if isinstance(result, dict):
            if path in result:
                return result[path]
            for k in ("content", "contents", "data", "text"):
                if k in result:
                    v = result[k]
                    return v[0] if isinstance(v, list) and v else v
            # single-entry map: {<path>: <content>}
            if len(result) == 1:
                return next(iter(result.values()))
        return str(result)

    def _spawn(self, args: dict) -> str:
        command = args.get("command") or args.get("cmd")
        proc_id = args.get("id", "erebos_spawn")
        params = {
            "id": proc_id,
            "command": command,
            "args": args.get("args", []),
            "cwd": args.get("cwd", "/workspace"),
            "env": args.get("env", {"PATH": "/usr/bin:/bin"}),
        }
        # spawn is fire-and-ack: you must subscribe BEFORE spawning, then read events.
        self._unwrap(self.client.call("subscribeEvents", {}))
        return self._collect_spawn(self.client.stream("spawn", params), proc_id)

    @staticmethod
    def _collect_spawn(packets, proc_id=None) -> str:
        """Read frames after spawn: skip the fire-and-ack reply, accumulate stdout/stderr
        events for our process id, stop on exit. CONFIRMED shapes (host probe 2026-06-25):
        stdout = {"type":"stdout","id":<proc>,"data":<str>}; exit = {"type":"exit",
        "id":<proc>,"exitCode":N}. Extra tolerated forms kept harmless."""
        out = []
        for pkt in packets:
            if not isinstance(pkt, dict):
                continue
            # the spawn ack: {"success":bool,"result":{...},"id":N} with no "type"
            if "type" not in pkt and "success" in pkt:
                if pkt.get("success") is False:
                    raise CoworkProtocolError(pkt.get("error") or f"spawn rejected: {pkt!r}")
                continue
            ev_id = pkt.get("id", pkt.get("processId"))
            if proc_id and ev_id is not None and ev_id != proc_id:
                continue  # event for a different process
            ptype = pkt.get("type")
            if ptype in ("stdout", "stderr", "data", "output"):
                out.append(pkt.get("data") or pkt.get("chunk") or pkt.get("output") or "")
            elif ptype in ("exit", "exited", "done", "close") or "exitCode" in pkt or "code" in pkt:
                break
        return "".join(out)

    # ---- mcp fallback ------------------------------------------------ #
    def _via_mcp(self, name: str, args: dict) -> Any:
        if self.mcp_fallback is None:
            raise CoworkProtocolError(
                f"cowork unavailable for {name} and no MCP fallback configured"
            )
        return self.mcp_fallback(name, args)
