# Kai Project Structure

Kai is one project with one assistant brain and multiple frontends.

## Canonical Runtime

- Core assistant brain:
  - `kai_agent/assistant.py`
- Tool execution and capability policy:
  - `kai_agent/desktop_tools.py`
  - `kai_agent/tool_policy.py`
- Unified desktop runtime:
  - `kai_agent/kai_unified_app.py`

## Frontends

- Terminal / CLI:
  - `python -m kai_agent.assistant`
- Panel / command center:
  - `kai_agent/desktop_panel_unified.py`
- Visual companion:
  - `kai_companion/`
- Widget / lightweight web chat:
  - `kai_agent/widget_server.py`

## Bridge

- Bridge transport only:
  - `kai_agent/bridge_server.py`
  - `kai_agent/bridge_client.py`
  - `bridge/server.py`

The bridge exists so the companion can react to Kai state and the unified runtime can prove readiness. It should not own tool execution.

## Single-Brain Rule

All real tool use should flow through:

`KaiAssistant -> DesktopTools -> ToolPolicy`

The panel is a control surface.
The companion is a visual surface.
Neither should become a separate primary tool-execution engine.

## Companion Modes

- Preferred default:
  - `res://scenes/kai_3d.tscn`
- Legacy scene:
  - `res://scenes/kai.tscn`

Both companion scenes now prefer the local Kai chat server first and only fall back to direct Ollama chat when the unified Kai server is unavailable.

## What To Treat As Legacy Or External

- Nested duplicate repo:
  - `kai-ai-openclaw/`
- Snapshot/separation workspace outside this repo:
  - `..\W0rm-Gpt-kai-separated-20260403-051508`
- Separate older project:
  - `..\Kai-AI-Project`

These are not the canonical working tree for Kai going forward.
