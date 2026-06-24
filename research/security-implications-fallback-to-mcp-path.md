# Security Implications: the 'Fallback-to-MCP' path

Based on the provided architecture and the implementation of the `anthropic-openwebui-pipeline.py` script, a concrete implementation of a "Graceful Fallback" would involve modifying the tool execution logic to check for account capabilities and transport availability before deciding on the execution path.

### Concrete Implementation Logic

The fallback mechanism would be integrated into the `_execute_mcp_tool` method within the pipeline script. Instead of blindly calling the MCP session, it would follow this logic flow:

**1. Capability Check (The Valve Guard)**
The system would first consult the "valves" to see if the current account is flagged for Cowork support.
*   **Input:** The routed account key (e.g., `acc1_`).
*   **Check:** If `self.valves.ACC1_COWORK_ENABLED` is `True`, attempt the Erebos path.

**2. The "Try-Erebos" Path (Primary)**
The script would attempt to utilize the `CoworkSocketClient` to communicate with the daemon at `$XDG_RUNTIME_DIR/cowork-vm-service.sock` [19, 68].
*   **Action:** Map the tool call to a JSON-RPC `spawn` or `readFile` request [19, 70].
*   **Validation:** If the socket is unavailable or returns an authentication error (indicating the account is actually on a free tier despite the valve setting), the system catches the exception.

**3. The "Fallback-to-MCP" Path (Secondary)**
If the Erebos path fails or is disabled, the script falls back to the standard `stdio` transport used by the existing pipeline [69].
*   **Action:** Execute `self.mcp_session.call_tool(tool_name, arguments)` [69].
*   **User Feedback:** The system can emit a notification (e.g., "Cowork unavailable for this account; falling back to standard MCP tools").

### Pseudocode Implementation

```python
async def _execute_mcp_tool(self, tool_name: str, arguments: dict) -> Any:
    # 1. Determine if current account has Cowork capabilities
    account_id = self._get_current_routed_account() # e.g., 'ACC1'
    cowork_enabled = getattr(self.valves, f"{account_id}_COWORK_ENABLED", False)

    if cowork_enabled:
        try:
            # 2. Attempt Erebos Execution Path
            # Uses the length-prefixed JSON-RPC protocol [19, 70]
            return await self.cowork_client.execute_tool(tool_name, arguments)
        except (ConnectionError, PermissionError) as e:
            logger.warn(f"Erebos transport failed for {account_id}: {e}. Falling back...")
            # Fallthrough to standard MCP

    # 3. Standard MCP Fallback Path [69]
    if not self._mcp_initialized or not self.mcp_session:
        await self._initialize_mcp()
    
    try:
        return await self.mcp_session.call_tool(tool_name, arguments)
    except Exception as e:
        # Further escalation to FailureTracker [11] if failures persist
        self.emitter.tool_failed(tool_name, family, "execution_error", str(e))
        return f"Error: Tool execution failed: {str(e)}"
```

### Integration with Erebos Components
To make this "robust," the fallback would be supported by two other Erebos systems:
*   **FailureTracker:** If the fallback also fails, the `FailureTracker` monitors the consecutive failure count. Once it reaches the threshold (e.g., 3 failures), it triggers the `auto-tool-loader` hook to attempt a `tool_search` to find a different provider for that tool family [10, 11, 12].
*   **EventBus:** Every transition from the primary (Erebos) to the fallback (MCP) would be emitted as an event, allowing the operator to track account limitations via `logs/hooks/hook-execution.jsonl` [14, 26].