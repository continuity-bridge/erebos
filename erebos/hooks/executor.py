import json
import logging
import yaml  # Added PyYAML dependency
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class ActionDispatcher:
    """
    The 'muscles' of the Hook System. 
    Executes specific system and model actions defined in YAML executors.
    """
    def __init__(self, provider_client):
        self.client = provider_client

    def dispatch(self, action_type: str, params: Dict[str, Any], event: Dict[str, Any]):
        """Routes execution to the appropriate handler."""
        method_name = f"_handle_{action_type}"
        handler = getattr(self, method_name, self._handle_unknown)
        return handler(params, event)

    def _handle_tool_search(self, params: Dict, event: Dict):
        """Dispatches a tool_search call to the active provider (e.g., Sisyphus)."""
        query = params.get("query", "").format(
            family_search_terms=" ".join(event.get("search_terms", []))
        )
        limit = params.get("search_limit", 10)
        
        logger.info(f"[DISPATCH] Auto-loading tools for {event.get('tool_family')}: {query}")
        
        # In Phase 3, this calls self.client.chat with the tool_search prompt
        # For now, we simulate the successful trigger
        return True

    def _handle_file_write(self, params: Dict, event: Dict):
        """Handles local filesystem persistence for session summaries."""
        path = Path(params.get("path", "logs/sessions/temp.md"))
        content = params.get("content", "Empty Summary")
        
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            logger.info(f"[DISPATCH] File written: {path}")
            return True
        except Exception as e:
            logger.error(f"[DISPATCH] File write failed: {e}")
            return False

    def _handle_unknown(self, params, event):
        logger.warning(f"[DISPATCH] Unknown action type encountered")
        return False

class HookExecutor:
    def __init__(
        self, event_bus, provider_client=None,
        registry_path: str = None, config_path: str = None,
        on_fire=None
    ):
        self.bus = event_bus
        self.dispatcher = ActionDispatcher(provider_client) if provider_client else None
        self.registry = self._load_json(registry_path) if registry_path else {}
        self.config = self._load_json(config_path) if config_path else {}
        self.enabled_hooks = self.config.get("enabled_hooks", [])
        self.execution_log = []
        self.on_fire = on_fire  # callable(hook_id, event_type, executor_path, success, error)

        self._subscribe_hooks()

    def _load_json(self, path: str) -> Dict:
        if Path(path).exists():
            with open(path) as f:
                return json.load(f)
        return {}

    def _subscribe_hooks(self):
        for hook in self.registry.get("hooks", []):
            if hook["id"] in self.enabled_hooks:
                self.bus.subscribe(hook["trigger"]["type"], 
                                  lambda e, h=hook: self._execute_hook(h, e))

    def _execute_hook(self, hook: Dict, event: Dict[str, Any]):
        hook_id = hook["id"]
        
        if not self._conditions_met(hook, event):
            return

        # Resolve YAML executor path (mirrors Substrate structure)
        raw_executor = hook.get("executor", "")
        executor_path = Path(raw_executor).with_suffix(".yaml") if raw_executor else None

        try:
            if executor_path and executor_path.exists():
                # Phase 3: parse and run YAML steps
                with open(executor_path, 'r') as f:
                    plan = yaml.safe_load(f)

                logger.info(f"Executing hook: {hook_id}")
                if self.dispatcher:
                    for step in plan.get("steps", []):
                        self.dispatcher.dispatch(step["action"], step["params"], event)
            else:
                # Stub: log intent, no executor file required
                logger.info(f"[STUB] Would execute: {raw_executor or 'No executor defined'}")

            self._log_execution(hook_id, event, True)
            if self.on_fire:
                self.on_fire(hook_id, event.get("event"),
                             str(executor_path) if executor_path else None, True, None)
        except Exception as e:
            logger.error(f"Hook {hook_id} failed: {e}")
            self._log_execution(hook_id, event, False, str(e))
            if self.on_fire:
                self.on_fire(hook_id, event.get("event"),
                             str(executor_path) if executor_path else None, False, str(e))

    def _conditions_met(self, hook: Dict, event: Dict) -> bool:
        """
        Check if hook conditions are satisfied.
        Filters based on tool_family and domain context.
        """
        # Phase 3: Implement domain-aware filtering
        trigger_config = hook.get("trigger", {})
        conditions = trigger_config.get("conditions", [])
        
        # If 'same_tool_family' is required, check event family against hook family
        if "same_tool_family: true" in conditions:
            # Logic to verify tool family from failure_tracker
            pass
            
        return True

    def _log_execution(self, hook_id, event, success, error=None):
        log_entry = {
            "timestamp": event.get("timestamp"),
            "session_id": event.get("session_id"),
            "event_type": event.get("event"),
            "hook_id": hook_id,
            "execution_status": "success" if success else "failed",
            "error_message": error,
        }
        self.execution_log.append(log_entry)

    def get_execution_history(self) -> list:
        """Get execution history for this session."""
        return self.execution_log.copy()