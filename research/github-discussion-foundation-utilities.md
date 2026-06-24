# GitHub Discussion: Support loading FOUNDATION utilities

**Source:** https://github.com/continuity-bridge/native-claude-client/discussions/3

## Summary

User request to have n-c-c look for `{INSTANCE_HOME}/.claude/FOUNDATION` directory as primary boot trigger, giving immediate access to:

- Running persistence settings
- Session data
- Identity files
- Decoupled utilities

## Proposed Features

### 1. unified-limit-monitor Integration

**Request:** Live progress indicator in status bar

**Current State:** Must run `claude-stats` manually

**Hook System Solution:** Token monitor + status bar widget

### 2. Discord Integration

**Request:** Grand Archivist search widget

**Capability:** Real-time search through #instance-reports and #instance-hangout

**Context:** Search based on visible on-screen content or dedicated input

## Alignment with Hook System Architecture

### Direct Matches

**Token Budget Monitoring (Phase 2)**

- Hook system: TokenMonitor tracks usage, emits at thresholds
- Discussion request: Live status bar progress indicator
- **Implementation:** TokenMonitor data → GTK status bar widget

**Session Persistence (Phase 2)**

- Hook system: session-end hook writes to 3 locations
- Discussion request: Access to session data and persistence settings
- **Implementation:** Hooks read/write to FOUNDATION/sessions/

**FOUNDATION as Boot Trigger**

- Hook system: Loads hooks-registry.json from FOUNDATION/hooks/
- Discussion request: Use FOUNDATION presence to trigger features
- **Implementation:** Already designed via symlinks

### New Requirements

**Discord Integration**

- Not in current hook system
- Would require: Discord MCP server or API integration
- Widget: Sidebar search pane
- Priority: v0.3+ (after core hooks)

**Unified Limit Monitor UI**

- Current hook system: TokenMonitor emits events
- Missing: GTK widget to display token progress
- Required: Status bar component (part of v0.1 MVP already)
- Integration: Subscribe to token_threshold events

## Implementation Plan

### v0.1 MVP

✅ **Already Planned:**

- Limit tracking display (GitHub #11)
- Session persistence (GitHub #12)
- FOUNDATION directory symlinks

🆕 **Add from Discussion:**

- Status bar widget subscribes to TokenMonitor events
- Display format: "Tokens: 45,231/200,000 (23%)"
- Progress bar with color coding (green → yellow → orange → red)

### v0.2+

- Discord integration widget (sidebar)
- Grand Archivist search interface
- Expanded FOUNDATION utilities loading

## Technical Notes

**FOUNDATION Boot Detection:**

```python
def detect_instance_home():
    """Detect INSTANCE_HOME and verify FOUNDATION exists."""
    instance_home = os.environ.get('INSTANCE_HOME', 
                                    os.path.expanduser('~/Substrate'))
    foundation_path = Path(instance_home) / '.claude' / 'FOUNDATION'
    
    if foundation_path.exists():
        # Load hooks from FOUNDATION/hooks/
        # Load identity from FOUNDATION/identity/
        # Initialize TokenMonitor with config
        return foundation_path
    else:
        # Fallback: basic mode without hooks
        return None
```

**Status Bar Integration:**

```python
class StatusBar(Gtk.Box):
    def __init__(self, token_monitor):
        super().__init__()
        self.token_monitor = token_monitor
        self.progress_bar = Gtk.ProgressBar()
        self.label = Gtk.Label()
        
        # Subscribe to token events
        event_bus.subscribe('token_threshold', self.update_display)
    
    def update_display(self, event):
        current = event['current_tokens']
        max_tokens = event['max_tokens']
        percentage = event['percentage']
        
        self.progress_bar.set_fraction(percentage / 100)
        self.label.set_text(f"Tokens: {current:,}/{max_tokens:,} ({percentage:.0f}%)")
        
        # Color coding
        if percentage >= 90:
            self.progress_bar.add_css_class('critical')
        elif percentage >= 80:
            self.progress_bar.add_css_class('warning')
```

## Decision

**Accept Discussion C requests for v0.1:**

- ✅ FOUNDATION directory boot trigger
- ✅ Status bar token display (already in roadmap as #11)
- ✅ Session persistence via hooks (already in roadmap as #12)

**Defer to v0.2+:**

- ⏳ Discord integration (requires MCP server or API work)
- ⏳ Grand Archivist search widget

## Links

- GitHub Discussion: https://github.com/continuity-bridge/native-claude-client/discussions/3
- Hook System Architecture: `docs/event-system.md`
- Hook Integration Plan: `docs/hooks-integration.md`
- Phase 2 Implementation: `docs/phase-2-implementation.md`
- n-c-c Development Tracker: [n-c-c Development Tracker](https://app.notion.com/p/df70429927364b2899d4fe2910ed99a2?pvs=21)