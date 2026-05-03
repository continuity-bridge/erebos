"""
erebos/main.py

Erebos CLI — network-agnostic LLM harness.

Routes requests to configured provider nodules. Currently supports
Ollama (local and network). Cloud providers (Anthropic, Gemini) planned.

Commands:
    discover  — scan for Ollama instances (mDNS + threaded polling)
    list      — show configured nodules with live status
    run       — send a prompt to the best available nodule
    add       — manually add a nodule
    remove    — remove a nodule by index
    config    — show or reset configuration

Routing priority:
    1. Lowest priority number wins
    2. Must pass health_check() to be considered
    3. --nodule flag overrides auto-selection
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .discovery import (
    NoduleConfig,
    OllamaDiscovery,
    discover_and_save,
    DEFAULT_CONFIG_PATH,
    DEFAULT_SUBNET,
    DEFAULT_PORT,
    MDNS_TIMEOUT,
)
from .providers.base import (
    ProviderError,
    ProviderConnectionError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderModelNotFoundError,
    ProviderResponseError,
    ProviderCapabilityError,
)
from .providers.ollama import OllamaClient
from .hooks import HookExecutor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provider Client Factory
# ---------------------------------------------------------------------------

def _client_for_nodule(nodule: dict) -> OllamaClient:
    """
    Instantiate the correct provider client for a nodule config dict.

    Currently only Ollama is implemented. Cloud providers will be
    added here as they land in providers/.

    Raises:
        ValueError: Unknown provider type.
    """
    provider = nodule.get("provider", "ollama")

    if provider == "ollama":
        return OllamaClient(
            base_url=nodule["url"],
            label=nodule.get("label"),
        )

    # Future:
    # if provider == "anthropic":
    #     return ClaudeClient(api_key=os.environ[nodule["api_key_env"]])
    # if provider == "google":
    #     return GeminiClient(api_key=os.environ[nodule["api_key_env"]])

    raise ValueError(
        f"Unknown provider '{provider}' in nodule '{nodule.get('label')}'. "
        f"Supported: ollama"
    )


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def _select_nodule(config: NoduleConfig,
                   nodule_index: Optional[int] = None) -> tuple[dict, OllamaClient]:
    """
    Select a nodule and return it with its instantiated client.

    If nodule_index given: use that specific nodule (1-based).
    Otherwise: auto-select highest priority available nodule.

    Raises:
        SystemExit: No nodules configured, invalid index, or none reachable.
    """
    nodules = config.all(enabled_only=True)

    if not nodules:
        print("❌ No nodules configured. Run 'erebos discover' first.")
        sys.exit(1)

    if nodule_index is not None:
        if nodule_index < 1 or nodule_index > len(nodules):
            print(f"❌ Invalid nodule index: {nodule_index} "
                  f"(have {len(nodules)} nodule(s))")
            sys.exit(1)
        nodule = nodules[nodule_index - 1]
        client = _client_for_nodule(nodule)
        status = client.health_check()
        if not status.available:
            print(f"❌ Nodule {nodule_index} ({nodule['label']}) is unreachable.")
            print(f"   {status}")
            sys.exit(1)
        return nodule, client

    # Auto-select: walk priority order, return first healthy
    for nodule in nodules:
        client = _client_for_nodule(nodule)
        status = client.health_check()
        if status.available:
            return nodule, client
        logger.debug(f"Skipping {nodule['label']}: {status}")

    print("❌ No nodules are currently reachable.")
    print("   Run 'erebos list' to see status.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------------------------

def cmd_discover(args):
    """Discover Ollama instances via mDNS + threaded polling."""
    subnet = args.subnet or DEFAULT_SUBNET
    port = args.port or DEFAULT_PORT

    print(f"🔍 Starting discovery on {subnet} (mDNS + polling)...")

    if args.save:
        new, updated = discover_and_save(
            subnet=subnet,
            port=port,
            config_path=Path(args.config) if args.config else DEFAULT_CONFIG_PATH,
            mdns_timeout=MDNS_TIMEOUT,
        )
        all_found = new + updated

        if not all_found:
            print(f"\n❌ No Ollama instances found on {subnet}")
            return

        print(f"\n✓ Discovery complete: "
              f"{len(new)} new, {len(updated)} updated\n")
        _print_discovery_results(all_found, mark_new={n['url'] for n in new})

    else:
        # Dry run — discover but don't save
        found = OllamaDiscovery.discover(subnet=subnet, port=port)

        if not found:
            print(f"\n❌ No Ollama instances found on {subnet}")
            return

        print(f"\n✓ Found {len(found)} instance(s) "
              f"(use --save to add to config)\n")
        _print_discovery_results(found)


def _print_discovery_results(nodules: list[dict],
                              mark_new: Optional[set] = None):
    """Print discovered nodules in a readable format."""
    print("-" * 80)
    for i, nodule in enumerate(nodules, 1):
        is_new = mark_new and nodule["url"] in mark_new
        tag = " [NEW]" if is_new else " [UPDATED]" if mark_new else ""
        print(f"{i}. {nodule['label']}{tag}")
        print(f"   URL:      {nodule['url']}")
        if nodule.get("hostname"):
            print(f"   Hostname: {nodule['hostname']}")
        models = nodule.get("models", [])
        print(f"   Models:   {len(models)} available")
        if models:
            preview = ", ".join(models[:3])
            overflow = f" (+{len(models) - 3} more)" if len(models) > 3 else ""
            print(f"   → {preview}{overflow}")
        print()


def cmd_list(args):
    """List configured nodules with live health status."""
    config = NoduleConfig(
        Path(args.config) if args.config else DEFAULT_CONFIG_PATH
    )
    nodules = config.all()

    if not nodules:
        print("No nodules configured. Run 'erebos discover' to find instances.")
        return

    print(f"\n📡 Configured Nodules ({len(nodules)} total):")
    print("-" * 80)

    for i, nodule in enumerate(nodules, 1):
        client = _client_for_nodule(nodule)
        status = client.health_check()

        indicator = "🟢" if status.available else "🔴"
        enabled = "" if nodule.get("enabled", True) else " [DISABLED]"
        latency = f" {status.latency_ms:.0f}ms" if status.latency_ms else ""

        print(f"{i}. {indicator} {nodule['label']}{enabled}")
        print(f"   URL:      {nodule['url']}")
        if nodule.get("hostname"):
            print(f"   Hostname: {nodule['hostname']}")
        print(f"   Provider: {nodule['provider']} | "
              f"Location: {nodule['location']} | "
              f"Priority: {nodule['priority']}{latency}")

        if status.available:
            models = nodule.get("models", [])
            print(f"   Models:   {len(models)} available")
            if models:
                preview = ", ".join(models[:3])
                overflow = f" (+{len(models) - 3} more)" if len(models) > 3 else ""
                print(f"   → {preview}{overflow}")
        else:
            print(f"   Status:   {status.error_message or 'unreachable'}")
            if status.last_healthy:
                print(f"   Last seen: {status.last_healthy.strftime('%Y-%m-%d %H:%M UTC')}")

        print()


def cmd_run(args):
    """Send a prompt to the best available nodule."""
    config_path = Path(args.config) if args.config else DEFAULT_CONFIG_PATH
    config = NoduleConfig(config_path)

    # Select the nodule and client (e.g., Sisyphus)
    nodule, client = _select_nodule(config, nodule_index=args.nodule)

    # ---------------------------------------------------------
    # NEW: Initialize the Hook System for this session
    # ---------------------------------------------------------
    # These paths should point to your Substrate symlinks
    registry_path = "erebos/config/hooks-registry.json"
    hooks_config_path = "erebos/config/hooks-config.json"
    
    executor = HookExecutor(
        event_bus=client.event_bus, # Assuming bus is attached to client
        provider_client=client,      # Pass client to the Dispatcher
        registry_path=registry_path,
        config_path=hooks_config_path
    )
    # ---------------------------------------------------------

    messages = [{"role": "user", "content": args.prompt}]

    print(f"🚀 Routing to: {nodule['label']} ({nodule['url']})")
    print(f"🤖 Model: {args.model}")
    print(f"📝 Prompt: {args.prompt}")
    print("-" * 80)

    try:
        if args.stream:
            print("\n💬 Response:")
            for chunk in client.chat(
                model=args.model,
                messages=messages,
                stream=True
            ):
                print(chunk, end="", flush=True)
            print()
        else:
            response = client.chat(
                model=args.model,
                messages=messages,
                stream=False
            )
            print(f"\n💬 Response:\n{response}")

        print("-" * 80)
        print(f"✓ Completed via {nodule['label']}")

    except ProviderModelNotFoundError as e:
        print(f"\n❌ Model not found: {e}")
        print(f"   Available models on {nodule['label']}:")
        for m in nodule.get("models", []):
            print(f"   • {m}")
        sys.exit(1)

    except ProviderConnectionError as e:
        print(f"\n❌ Connection failed: {e}")
        print("   The nodule may have gone offline. Run 'erebos list' to check.")
        sys.exit(1)

    except ProviderRateLimitError as e:
        print(f"\n❌ Rate limited: {e}")
        if e.retry_after:
            print(f"   Retry after {e.retry_after}s")
        sys.exit(1)

    except ProviderError as e:
        print(f"\n❌ Provider error: {e}")
        sys.exit(1)


def cmd_add(args):
    """Manually add a nodule."""
    config = NoduleConfig(
        Path(args.config) if args.config else DEFAULT_CONFIG_PATH
    )

    host = args.host
    port = args.port or DEFAULT_PORT
    url = f"http://{host}:{port}"

    # Verify it's reachable before adding
    client = OllamaClient(base_url=url)
    status = client.health_check()

    if not status.available:
        print(f"⚠ Warning: {url} is not currently reachable.")
        print(f"  {status.error_message}")
        if not args.force:
            print("  Use --force to add anyway.")
            sys.exit(1)
        models = []
    else:
        print(f"✓ Reachable ({status.latency_ms:.0f}ms)")
        models = client.list_models()

    # Resolve hostname
    hostname = OllamaClient.resolve_hostname(host) if not args.label else None
    label = args.label or (
        f"Ollama-{hostname}" if hostname else f"Ollama-{host.split('.')[-1]}"
    )

    from .discovery import _build_nodule
    nodule = _build_nodule(
        host_ip=host,
        port=port,
        hostname=hostname,
        models=models,
        priority=args.priority or (len(config) + 1)
    )
    nodule["label"] = label

    result, was_new = config.add_or_update(nodule)
    config.save()

    action = "Added" if was_new else "Updated"
    print(f"✓ {action} nodule: {result['label']} ({url})")
    if models:
        print(f"  Models: {', '.join(models[:3])}"
              + (f" (+{len(models)-3} more)" if len(models) > 3 else ""))


def cmd_remove(args):
    """Remove a nodule by index."""
    config = NoduleConfig(
        Path(args.config) if args.config else DEFAULT_CONFIG_PATH
    )
    nodules = config.all()

    if not nodules:
        print("No nodules configured.")
        sys.exit(1)

    if args.index < 1 or args.index > len(nodules):
        print(f"❌ Invalid index: {args.index} (have {len(nodules)} nodule(s))")
        sys.exit(1)

    nodule = nodules[args.index - 1]

    if not args.yes:
        confirm = input(f"Remove '{nodule['label']}' ({nodule['url']})? [y/N] ")
        if confirm.lower() != "y":
            print("Cancelled.")
            return

    config.remove(nodule["url"])
    config.save()
    print(f"✓ Removed: {nodule['label']}")


def cmd_config(args):
    """Show or reset configuration."""
    config_path = Path(args.config) if args.config else DEFAULT_CONFIG_PATH

    if args.show:
        print(f"\n📄 Config: {config_path}")
        if config_path.exists():
            with open(config_path, "r") as f:
                print(f.read())
        else:
            print("(No config file exists yet)")

    if args.reset:
        if config_path.exists():
            if not args.yes:
                confirm = input(f"Reset config at {config_path}? [y/N] ")
                if confirm.lower() != "y":
                    print("Cancelled.")
                    return
            config_path.unlink()
            print(f"✓ Removed: {config_path}")
        else:
            print("No config file to remove.")


# ---------------------------------------------------------------------------
# CLI Definition
# ---------------------------------------------------------------------------

def _add_common_args(parser):
    """Add arguments shared across all subcommands."""
    parser.add_argument(
        "--config",
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})",
        metavar="PATH"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging"
    )


def main():
    parser = argparse.ArgumentParser(
        prog="erebos",
        description="Erebos — network-agnostic LLM harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  erebos discover --save
  erebos discover --subnet 192.168.1.0/24 --save
  erebos list
  erebos run "What is 2+2?" --model llama3.1:8b
  erebos run "Explain Python" --model llama3.1:8b --stream
  erebos run "Hello" --nodule 1
  erebos add 192.168.12.50 --label "Desktop"
  erebos remove 2
  erebos config --show
  erebos config --reset
        """
    )

    _add_common_args(parser)
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # discover
    p = subparsers.add_parser("discover", help="Discover Ollama instances")
    p.add_argument("--subnet", help=f"CIDR subnet (default: {DEFAULT_SUBNET})")
    p.add_argument("--port", type=int, help=f"Port (default: {DEFAULT_PORT})")
    p.add_argument("--save", action="store_true", help="Save results to config")
    _add_common_args(p)
    p.set_defaults(func=cmd_discover)

    # list
    p = subparsers.add_parser("list", help="List configured nodules")
    _add_common_args(p)
    p.set_defaults(func=cmd_list)

    # run
    p = subparsers.add_parser("run", help="Send a prompt to a nodule")
    p.add_argument("prompt", help="Prompt text")
    p.add_argument("--model", default="llama3.2",
                   help="Model identifier (default: llama3.2)")
    p.add_argument("--nodule", type=int, metavar="N",
                   help="Nodule index to use (default: auto)")
    p.add_argument("--stream", action="store_true",
                   help="Stream response chunks as they arrive")
    _add_common_args(p)
    p.set_defaults(func=cmd_run)

    # add
    p = subparsers.add_parser("add", help="Manually add a nodule")
    p.add_argument("host", help="IP address or hostname")
    p.add_argument("--port", type=int, help=f"Port (default: {DEFAULT_PORT})")
    p.add_argument("--label", help="Display label")
    p.add_argument("--priority", type=int, help="Priority (1=highest)")
    p.add_argument("--force", action="store_true",
                   help="Add even if unreachable")
    _add_common_args(p)
    p.set_defaults(func=cmd_add)

    # remove
    p = subparsers.add_parser("remove", help="Remove a nodule")
    p.add_argument("index", type=int, help="Nodule index (from 'erebos list')")
    p.add_argument("--yes", "-y", action="store_true",
                   help="Skip confirmation prompt")
    _add_common_args(p)
    p.set_defaults(func=cmd_remove)

    # config
    p = subparsers.add_parser("config", help="Configuration management")
    p.add_argument("--show", action="store_true", help="Print config file")
    p.add_argument("--reset", action="store_true", help="Delete config file")
    p.add_argument("--yes", "-y", action="store_true",
                   help="Skip confirmation prompt")
    _add_common_args(p)
    p.set_defaults(func=cmd_config)

    # Parse
    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if getattr(args, "verbose", False) else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s"
    )

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted.")
        sys.exit(1)
    except Exception as e:
        logger.debug("Unhandled exception", exc_info=True)
        print(f"\n❌ Unexpected error: {e}")
        print("   Run with --verbose for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()