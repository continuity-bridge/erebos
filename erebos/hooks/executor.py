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
        self, event_bus, provider_client, registry_path: str, config_path: str
    ):
        self.bus = event_bus
        self.dispatcher = ActionDispatcher(provider_client)
        self.registry = self._load_json(registry_path)
        self.config = self._load_json(config_path)
        self.enabled_hooks = self.config.get("enabled_hooks", [])
        self.execution_log = []

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
        executor_path = Path(hook["executor"]).with_suffix(".yaml")
        
        if not executor_path.exists():
            logger.error(f"Executor not found: {executor_path}")
            return

        try:
            with open(executor_path, 'r') as f:
                plan = yaml.safe_load(f)

            logger.info(f"Executing hook: {hook_id}")
            
            # Execute the steps defined in the YAML file
            for step in plan.get("steps", []):
                self.dispatcher.dispatch(step["action"], step["params"], event)

            self._log_execution(hook_id, event, True)
        except Exception as e:
            logger.error(f"Hook {hook_id} failed: {e}")
            self._log_execution(hook_id, event, False, str(e))

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
            "hook_id": hook_id,
            "success": success,
            "error": error
        }
        self.execution_log.append(log_entry)