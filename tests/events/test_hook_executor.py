"""
Unit tests for HookExecutor.
"""

import json
import tempfile
import pytest
from erebos.events.bus import EventBus
from erebos.events.emitter import EventEmitter
from erebos.hooks import HookExecutor


def test_load_registry():
    """Test loading hooks registry from JSON file."""
    # Create temporary registry file
    registry = {
        "hooks": [
            {
                "id": "test-hook",
                "trigger": {"type": "session_start"},
                "executor": "test-executor.md",
            }
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(registry, f)
        registry_path = f.name

    bus = EventBus()
    executor = HookExecutor(bus, registry_path=registry_path)

    assert len(executor.registry["hooks"]) == 1
    assert executor.registry["hooks"][0]["id"] == "test-hook"


def test_load_config():
    """Test loading hooks config from JSON file."""
    config = {"enabled_hooks": ["hook-1", "hook-2"]}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(config, f)
        config_path = f.name

    bus = EventBus()
    executor = HookExecutor(bus, config_path=config_path)

    assert executor.enabled_hooks == ["hook-1", "hook-2"]


def test_hook_subscription():
    """Test that hooks subscribe to their trigger events."""
    registry = {
        "hooks": [
            {"id": "session-hook", "trigger": {"type": "session_start"}, "executor": "test.md"}
        ]
    }
    config = {"enabled_hooks": ["session-hook"]}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as reg_file:
        json.dump(registry, reg_file)
        registry_path = reg_file.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as conf_file:
        json.dump(config, conf_file)
        config_path = conf_file.name

    bus = EventBus()
    executor = HookExecutor(bus, registry_path=registry_path, config_path=config_path)

    # Check that hook was subscribed
    assert "session_start" in bus.subscribers
    assert len(bus.subscribers["session_start"]) > 0


def test_hook_execution():
    """Test that hooks execute when events fire."""
    registry = {
        "hooks": [
            {"id": "test-hook", "trigger": {"type": "test_event"}, "executor": "test-executor.md"}
        ]
    }
    config = {"enabled_hooks": ["test-hook"]}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as reg_file:
        json.dump(registry, reg_file)
        registry_path = reg_file.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as conf_file:
        json.dump(config, conf_file)
        config_path = conf_file.name

    bus = EventBus()
    executor = HookExecutor(bus, registry_path=registry_path, config_path=config_path)

    # Emit event that should trigger hook
    bus.emit({"event": "test_event", "data": "test"})

    # Check execution was logged
    history = executor.get_execution_history()
    assert len(history) == 1
    assert history[0]["hook_id"] == "test-hook"
    assert history[0]["execution_status"] == "success"


def test_disabled_hook_not_executed():
    """Test that disabled hooks don't execute."""
    registry = {
        "hooks": [{"id": "disabled-hook", "trigger": {"type": "test_event"}, "executor": "test.md"}]
    }
    config = {"enabled_hooks": []}  # Hook not enabled

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as reg_file:
        json.dump(registry, reg_file)
        registry_path = reg_file.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as conf_file:
        json.dump(config, conf_file)
        config_path = conf_file.name

    bus = EventBus()
    executor = HookExecutor(bus, registry_path=registry_path, config_path=config_path)

    # Emit event
    bus.emit({"event": "test_event", "data": "test"})

    # Should not have executed
    history = executor.get_execution_history()
    assert len(history) == 0


def test_integration_with_failure_tracker():
    """Test HookExecutor responds to failure_threshold events."""
    registry = {
        "hooks": [
            {
                "id": "auto-tool-loader",
                "trigger": {"type": "failure_threshold"},
                "executor": "auto-load-tools.md",
            }
        ]
    }
    config = {"enabled_hooks": ["auto-tool-loader"]}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as reg_file:
        json.dump(registry, reg_file)
        registry_path = reg_file.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as conf_file:
        json.dump(config, conf_file)
        config_path = conf_file.name

    bus = EventBus()
    emitter = EventEmitter(bus)
    executor = HookExecutor(bus, registry_path=registry_path, config_path=config_path)

    # Simulate failure threshold event
    bus.emit({"event": "failure_threshold", "tool_family": "Filesystem", "consecutive_failures": 3})

    # Hook should have executed
    history = executor.get_execution_history()
    assert len(history) == 1
    assert history[0]["hook_id"] == "auto-tool-loader"
    assert history[0]["event_type"] == "failure_threshold"


def test_execution_history():
    """Test execution history tracking."""
    registry = {
        "hooks": [
            {"id": "hook-1", "trigger": {"type": "event_1"}, "executor": "test.md"},
            {"id": "hook-2", "trigger": {"type": "event_2"}, "executor": "test.md"},
        ]
    }
    config = {"enabled_hooks": ["hook-1", "hook-2"]}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as reg_file:
        json.dump(registry, reg_file)
        registry_path = reg_file.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as conf_file:
        json.dump(config, conf_file)
        config_path = conf_file.name

    bus = EventBus()
    executor = HookExecutor(bus, registry_path=registry_path, config_path=config_path)

    # Emit multiple events
    bus.emit({"event": "event_1"})
    bus.emit({"event": "event_2"})
    bus.emit({"event": "event_1"})

    # Check history
    history = executor.get_execution_history()
    assert len(history) == 3
    assert history[0]["hook_id"] == "hook-1"
    assert history[1]["hook_id"] == "hook-2"
    assert history[2]["hook_id"] == "hook-1"
