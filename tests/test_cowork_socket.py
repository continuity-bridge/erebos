"""Framing tests for CoworkSocketClient against a mock Unix-socket server.
Proves the client's length-prefixed wire protocol is correct WITHOUT touching
any real cowork daemon."""
import json, os, socket, struct, tempfile, threading
from erebos.providers.cowork_socket import CoworkSocketClient


def _mock_server(sock_path, handler, ready):
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(sock_path); srv.listen(1); ready.set()
    conn, _ = srv.accept()
    def recv_frame():
        h = b""
        while len(h) < 4:
            h += conn.recv(4 - len(h))
        (n,) = struct.unpack(">I", h)
        d = b""
        while len(d) < n:
            d += conn.recv(n - len(d))
        return json.loads(d.decode())
    def send_frame(obj):
        p = json.dumps(obj).encode()
        conn.sendall(struct.pack(">I", len(p)) + p)
    handler(recv_frame, send_frame)
    conn.close(); srv.close()


def test_call_roundtrip():
    d = tempfile.mkdtemp(); sp = os.path.join(d, "mock.sock"); ready = threading.Event()
    def handler(recv, send):
        req = recv()
        assert req["method"] == "isRunning"
        assert req["id"] == 1 and req["params"] == {}
        send({"id": 1, "result": {"running": True}})
    t = threading.Thread(target=_mock_server, args=(sp, handler, ready), daemon=True); t.start()
    ready.wait(2)
    with CoworkSocketClient(socket_path=sp) as c:
        resp = c.call("isRunning")
    assert resp == {"id": 1, "result": {"running": True}}


def test_stream_until_close():
    d = tempfile.mkdtemp(); sp = os.path.join(d, "mock2.sock"); ready = threading.Event()
    def handler(recv, send):
        recv()  # the spawn request
        for line in ["erebos.py\n", "providers/\n"]:
            send({"type": "stdout", "data": line})
        # then close (server returns) -> client stream ends
    t = threading.Thread(target=_mock_server, args=(sp, handler, ready), daemon=True); t.start()
    ready.wait(2)
    with CoworkSocketClient(socket_path=sp) as c:
        packets = list(c.stream("spawn", {"command": "ls"}))
    assert [p["data"] for p in packets] == ["erebos.py\n", "providers/\n"]


def test_large_payload_framing():
    """Header must correctly frame a payload > one recv chunk."""
    d = tempfile.mkdtemp(); sp = os.path.join(d, "mock3.sock"); ready = threading.Event()
    big = "x" * 200000
    def handler(recv, send):
        recv(); send({"id": 1, "result": {"blob": big}})
    t = threading.Thread(target=_mock_server, args=(sp, handler, ready), daemon=True); t.start()
    ready.wait(2)
    with CoworkSocketClient(socket_path=sp) as c:
        resp = c.call("readFile")
    assert resp["result"]["blob"] == big
