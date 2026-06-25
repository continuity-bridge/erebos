"""
erebos/providers/cowork_socket.py

Client for the Claude Desktop `cowork-vm-service` daemon — a Node process that
manages a bwrap/qemu sandbox and listens on a Unix domain socket. No Electron
required: erebos can launch/talk to this daemon directly.

Wire protocol (reverse-engineered; see research/erebos-protocol-and-orchestration-documentation.md):
    [ 4-byte big-endian uint32 length ][ UTF-8 JSON payload ]
Payload is a JSON-RPC-ish object: {"method": str, "params": dict, "id": int}.

Status: framing validated against a mock server (test_cowork_socket.py). The live
protocol-match against a real daemon must be run ON THE EREBOS HOST — do NOT fire
RPCs at the cowork socket of a session you are running inside.
"""
from __future__ import annotations

import json
import os
import socket
import struct
from typing import Any, Iterator, Optional


class CoworkProtocolError(RuntimeError):
    """Framing or transport error talking to the cowork daemon."""


class CoworkSocketClient:
    def __init__(self, socket_path: Optional[str] = None, timeout: float = 10.0):
        if socket_path is None:
            xdg = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
            socket_path = os.path.join(xdg, "cowork-vm-service.sock")
        self.socket_path = socket_path
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self._id = 0

    # -- lifecycle -------------------------------------------------------- #
    def connect(self) -> "CoworkSocketClient":
        if not os.path.exists(self.socket_path):
            raise FileNotFoundError(f"cowork daemon socket not found at {self.socket_path}")
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)
        return self

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()

    # -- framing ---------------------------------------------------------- #
    def _send(self, message: dict) -> None:
        if not self.sock:
            raise CoworkProtocolError("not connected")
        payload = json.dumps(message).encode("utf-8")
        self.sock.sendall(struct.pack(">I", len(payload)) + payload)

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise CoworkProtocolError("socket closed mid-frame")
            buf += chunk
        return buf

    def _recv(self) -> Optional[dict]:
        header = self.sock.recv(4)
        if not header:
            return None
        if len(header) < 4:
            header += self._recv_exact(4 - len(header))
        (length,) = struct.unpack(">I", header)
        return json.loads(self._recv_exact(length).decode("utf-8"))

    # -- high-level ------------------------------------------------------- #
    def call(self, method: str, params: Optional[dict] = None) -> Optional[dict]:
        """One request -> one response. For non-streaming methods."""
        self._id += 1
        self._send({"method": method, "params": params or {}, "id": self._id})
        return self._recv()

    def stream(self, method: str, params: Optional[dict] = None) -> Iterator[dict]:
        """Send a request, then yield framed packets until the socket closes
        (for `spawn` + `subscribeEvents` style streaming stdout/stderr)."""
        self._id += 1
        self._send({"method": method, "params": params or {}, "id": self._id})
        while True:
            packet = self._recv()
            if packet is None:
                break
            yield packet
