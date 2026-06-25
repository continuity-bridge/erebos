"""MCPToolExecutor + build_executor tests with a mock MCP session (no server)."""
import types, pytest
from erebos.providers.mcp_executor import MCPToolExecutor, build_executor
from erebos.providers.cowork_executor import CoworkToolExecutor

def _result(text, is_error=False):
    return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)], isError=is_error)

class _Session:
    def __init__(self, result=None, raise_exc=None): self._r=result; self._raise=raise_exc; self.calls=[]
    def call_tool(self, name, arguments):
        self.calls.append((name,arguments))
        if self._raise: raise self._raise
        return self._r

def test_mcp_executor_returns_text():
    ex = MCPToolExecutor(_Session(_result("hello-from-mcp")))
    assert ex.execute_tool("read_file", {"path":"/x"}) == "hello-from-mcp"

def test_mcp_executor_flags_tool_error():
    ex = MCPToolExecutor(_Session(_result("nope", is_error=True)))
    assert ex.execute_tool("read_file", {"path":"/x"}).startswith("[tool error]")

def test_mcp_executor_catches_transport_error():
    ex = MCPToolExecutor(_Session(raise_exc=ConnectionError("server died")))
    out = ex.execute_tool("read_file", {"path":"/x"})
    assert out.startswith("[tool error]") and "server died" in out

def test_mcp_executor_strips_provider_prefix():
    s=_Session(_result("ok")); ex=MCPToolExecutor(s)
    ex.execute_tool("anthropic:read_file", {"path":"/x"})
    assert s.calls[0][0] == "read_file"

def test_build_executor_pro_returns_cowork_with_mcp_fallback():
    ex = build_executor(True, cowork_client=object(), mcp_session=_Session(_result("x")))
    assert isinstance(ex, CoworkToolExecutor) and ex.mcp_fallback is not None

def test_build_executor_free_returns_mcp():
    ex = build_executor(False, mcp_session=_Session(_result("x")))
    assert isinstance(ex, MCPToolExecutor)

def test_build_executor_free_without_session_raises():
    with pytest.raises(ValueError):
        build_executor(False)
