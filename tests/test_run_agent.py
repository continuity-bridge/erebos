"""Mock-SDK tests for the _run_agent() agentic loop and CoworkToolExecutor dispatch.
No real API, no real daemon."""
import types
import pytest
from unittest.mock import patch, MagicMock
from erebos.providers.claude import ClaudeClient
from erebos.providers.cowork_executor import CoworkToolExecutor
from erebos.providers.cowork_socket import CoworkProtocolError

def _usage(i=5, o=5): return types.SimpleNamespace(input_tokens=i, output_tokens=o)
def _text(t): return types.SimpleNamespace(type="text", text=t)
def _tool(id, name, inp): return types.SimpleNamespace(type="tool_use", id=id, name=name, input=inp)
def _resp(content, i=5, o=5): return types.SimpleNamespace(content=content, usage=_usage(i,o))

class _Exec:
    def __init__(self): self.calls=[]
    def execute_tool(self, name, args): self.calls.append((name,args)); return "file1\nfile2"

@patch("erebos.providers.claude.Anthropic")
def test_run_agent_tool_then_final(MockAnthropic):
    fake = MagicMock()
    # turn 1: model asks for a tool; turn 2: model gives final text
    fake.messages.create.side_effect = [
        _resp([_text("let me look"), _tool("t1","bash",{"command":"ls"})]),
        _resp([_text("done: 2 files")]),
    ]
    MockAnthropic.return_value = fake
    c = ClaudeClient(api_key="test-key"); c.token_monitor = types.SimpleNamespace(update=lambda *_:None)
    ex = _Exec()
    out = c._run_agent("claude-haiku-4-5", [{"role":"user","content":"list files"}], ex)
    assert out == "done: 2 files"
    # executor was called with the tool block's name+input
    assert ex.calls == [("bash", {"command":"ls"})]
    # second API call carried the tool_result with the right tool_use_id
    second_msgs = fake.messages.create.call_args_list[1].kwargs["messages"]
    tr = second_msgs[-1]["content"][0]
    assert tr["type"]=="tool_result" and tr["tool_use_id"]=="t1" and "file1" in tr["content"]

@patch("erebos.providers.claude.Anthropic")
def test_run_agent_tool_error_is_reported_not_fatal(MockAnthropic):
    fake = MagicMock()
    fake.messages.create.side_effect = [
        _resp([_tool("t1","bash",{"command":"boom"})]),
        _resp([_text("recovered")]),
    ]
    MockAnthropic.return_value = fake
    class _Boom:
        def execute_tool(self,n,a): raise RuntimeError("nope")
    c = ClaudeClient(api_key="test-key"); c.token_monitor=types.SimpleNamespace(update=lambda *_:None)
    out = c._run_agent("m", [{"role":"user","content":"x"}], _Boom())
    assert out == "recovered"
    tr = fake.messages.create.call_args_list[1].kwargs["messages"][-1]["content"][0]
    assert tr.get("is_error") is True and "nope" in tr["content"]

@patch("erebos.providers.claude.Anthropic")
def test_run_agent_max_turns_guard(MockAnthropic):
    from erebos.providers.base import ProviderResponseError
    fake = MagicMock()
    fake.messages.create.return_value = _resp([_tool("t","bash",{"command":"loop"})])  # never stops
    MockAnthropic.return_value = fake
    c = ClaudeClient(api_key="test-key"); c.token_monitor=types.SimpleNamespace(update=lambda *_:None)
    with pytest.raises(ProviderResponseError):
        c._run_agent("m", [{"role":"user","content":"x"}], _Exec(), max_turns=3)
    assert fake.messages.create.call_count == 3

# ---- executor dispatch + fallback ----
class _Client:
    """stand-in CoworkSocketClient"""
    def __init__(self, call_resp=None, stream_pkts=None, raise_exc=None):
        self._call_resp=call_resp; self._stream=stream_pkts or []; self._raise=raise_exc
    def call(self, method, params=None):
        if self._raise: raise self._raise
        return self._call_resp
    def stream(self, method, params=None):
        if self._raise: raise self._raise
        return iter(self._stream)

def test_executor_read_file_unwraps_envelope():
    cl=_Client(call_resp={"success":True,"result":{"content":"hello"},"id":1})
    ex=CoworkToolExecutor(cl)
    assert ex.execute_tool("read_file", {"path":"/x"}) == "hello"

def test_executor_spawn_collects_stdout_until_exit():
    pkts=[{"type":"stdout","data":"a\n"},{"type":"stdout","data":"b\n"},{"type":"exit","code":0}]
    ex=CoworkToolExecutor(_Client(stream_pkts=pkts))
    assert ex.execute_tool("bash", {"command":"ls"}) == "a\nb\n"

def test_executor_falls_back_to_mcp_on_cowork_error():
    got={}
    def mcp(name,args): got["x"]=(name,args); return "via-mcp"
    cl=_Client(raise_exc=ConnectionError("socket down"))
    ex=CoworkToolExecutor(cl, mcp_fallback=mcp)
    assert ex.execute_tool("read_file", {"path":"/x"}) == "via-mcp"
    assert got["x"][0]=="read_file"

def test_executor_disabled_uses_mcp_directly():
    ex=CoworkToolExecutor(_Client(), mcp_fallback=lambda n,a:"mcp", cowork_enabled=False)
    assert ex.execute_tool("bash", {"command":"ls"}) == "mcp"

def test_executor_no_fallback_raises():
    ex=CoworkToolExecutor(_Client(raise_exc=ConnectionError("down")))
    with pytest.raises(CoworkProtocolError):
        ex.execute_tool("read_file", {"path":"/x"})
