"""
erebos/providers/mcp_executor.py

MCP-stdio tool execution — the PRIMARY path for free-tier accounts (which don't have
Cowork). Mirrors CoworkToolExecutor's interface (execute_tool(name, args) -> str) so
_run_agent() is transport-agnostic.

Why this matters: the operator has ONE Pro account (cowork) and three free accounts.
So MCP-stdio is the path for 3/4 of the fleet — not a "fallback".

A concrete server: `npx -y @modelcontextprotocol/server-filesystem <root>` provides
read_file / write_file / list_directory over stdio.
"""
from __future__ import annotations

import asyncio
import os
import threading
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .cowork_executor import CoworkToolExecutor


def _normalize(result: Any) -> str:
    """Flatten an MCP CallToolResult into text; flag tool-level errors."""
    parts = []
    for block in getattr(result, "content", None) or []:
        text = getattr(block, "text", None)
        parts.append(text if text is not None else str(block))
    out = "\n".join(parts)
    if getattr(result, "isError", False):
        return f"[tool error] {out}"
    return out


class MCPToolExecutor:
    """Duck-typed: `session` needs call_tool(name, arguments) (sync). Use StdioMCPSession
    for a real stdio server, or any object with call_tool for tests."""

    def __init__(self, session: Any, emitter: Any = None):
        self.session = session
        self.emitter = emitter

    def execute_tool(self, tool_name: str, arguments: dict) -> str:
        name = tool_name.split(":")[-1]
        try:
            result = self.session.call_tool(name, arguments)
        except Exception as e:  # transport/tool failure -> report to the model, not fatal
            if self.emitter is not None:
                try:
                    self.emitter.tool_failed(tool_name, "mcp", type(e).__name__, str(e))
                except Exception:
                    pass
            return f"[tool error] {e}"
        return _normalize(result)


class MCPSession:
    """Transport-agnostic MCP session interface. Anything with sync list_tools() and
    call_tool(name, args) works as a session for MCPToolExecutor — stdio today, a
    shared Unix-socket / streamable-HTTP server later (operator's 'less state' idea).
    The executor never sees the transport."""
    def list_tools(self): ...          # pragma: no cover
    def call_tool(self, name, arguments): ...  # pragma: no cover


class StdioMCPSession(MCPSession):
    """Sync facade over the async MCP stdio client. A SINGLE long-lived coroutine owns
    the stdio_client + ClientSession context and processes call requests from a queue —
    so the anyio cancel scopes are entered AND exited in the same task.

        with StdioMCPSession("npx", ["-y", "@modelcontextprotocol/server-filesystem", root]) as s:
            s.call_tool("read_text_file", {"path": "/x"})
    """
    def __init__(self, command: str, args: Optional[list] = None,
                 env: Optional[dict] = None, timeout: float = 60.0):
        self.params = StdioServerParameters(
            command=command, args=args or [], env=env or dict(os.environ)
        )
        self.timeout = timeout
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._queue: Optional[asyncio.Queue] = None
        self._runner_fut = None
        self._ready = threading.Event()
        self._init_error: Optional[BaseException] = None

    async def _runner(self):
        self._queue = asyncio.Queue()
        try:
            async with stdio_client(self.params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    self._ready.set()
                    while True:
                        item = await self._queue.get()
                        if item is None:        # close sentinel
                            break
                        make_coro, fut = item
                        try:
                            fut.set_result(await make_coro(session))
                        except BaseException as e:  # noqa: BLE001
                            fut.set_exception(e)
        except BaseException as e:  # startup failure
            self._init_error = e
            self._ready.set()

    def _submit(self, make_coro):
        import concurrent.futures
        fut = concurrent.futures.Future()
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (make_coro, fut))
        return fut.result(self.timeout)

    def __enter__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._runner_fut = asyncio.run_coroutine_threadsafe(self._runner(), self._loop)
        if not self._ready.wait(self.timeout):
            raise TimeoutError("MCP server did not initialize in time")
        if self._init_error:
            raise self._init_error
        return self

    def __exit__(self, *exc):
        try:
            if self._queue is not None:
                self._loop.call_soon_threadsafe(self._queue.put_nowait, None)
            if self._runner_fut is not None:
                self._runner_fut.result(self.timeout)  # runner exits its OWN contexts
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def list_tools(self):
        return self._submit(lambda s: s.list_tools())

    def call_tool(self, name: str, arguments: dict):
        return self._submit(lambda s: s.call_tool(name, arguments))


def build_executor(cowork_enabled: bool, *, cowork_client=None, mcp_session=None, emitter=None):
    """Capability-flag router (per nodule): Pro -> Cowork (with MCP fallback if a session
    is provided); free -> MCP-stdio primary. Both expose execute_tool(name, args)."""
    if cowork_enabled and cowork_client is not None:
        fb = MCPToolExecutor(mcp_session, emitter).execute_tool if mcp_session is not None else None
        return CoworkToolExecutor(cowork_client, mcp_fallback=fb, emitter=emitter, cowork_enabled=True)
    if mcp_session is None:
        raise ValueError("free-tier nodule needs an mcp_session (no cowork available)")
    return MCPToolExecutor(mcp_session, emitter)
