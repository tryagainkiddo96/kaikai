# Kai 🦊

A personal AI companion inspired by a Shiba Inu named Kai.

Kai is a local-first AI assistant with a 3D desktop companion — a black and tan Shiba Inu that lives on your desktop, patrols, reacts to events, and chats with you through a local Ollama model.

## What's inside

```
kai_agent/          Python-side Kai brain (Ollama, memory, tools)
bridge/             WebSocket event bridge (brain ↔ companion)
kai_companion/      Godot desktop avatar (3D Shiba, animations, chat)
widget/             Web chat widget (browser-based companion interface)
tools/              Launchers, rigging, texture workflows
memory/             Persistent notes and session history
```

## Identity

- **Breed:** Shiba Inu
- **Coat:** Black and tan
- **Markings:** White/cream chest, muzzle, and paw accents
- **Style:** Realistic 3D desktop companion with procedural animation

## Design system

All UI surfaces share a warm Shiba Inu palette:

| Token | Hex | Description |
|-------|-----|-------------|
| `kai-charcoal` | `#1A1612` | Deep background (black coat) |
| `kai-rust` | `#C4783A` | Primary accent (tan markings) |
| `kai-amber` | `#D4943A` | Secondary accent |
| `kai-chest` | `#F5E6D0` | Text / cream markings |
| `kai-cream` | `#FFF5E1` | Bright text |

Applied to: web widget, tkinter desktop panel, Godot companion UI.

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the bridge

```bash
python bridge/server.py
```

### 3. Launch the companion

```powershell
# Full stack (brain + companion + bridge)
powershell -ExecutionPolicy Bypass -File tools/launch_kai_stack.ps1

# Widget only
powershell -ExecutionPolicy Bypass -File tools/launch_kai_widget.ps1

# Desktop panel
powershell -ExecutionPolicy Bypass -File tools/launch_kai_panel.ps1
```

### 4. Chat

Open http://127.0.0.1:8127 in a browser, or right-click Kai on the desktop.

## Companion controls

- **Left click + drag** — move Kai around the desktop
- **Right click** — open/close chat panel
- **Chat** button — toggle conversation
- Kai patrols the desktop on his own (walking, sniffing, barking, resting)

## Desktop panel

Always-on-top command center with four tabs:

| Tab | Purpose |
|-----|---------|
| Chat | Full conversation stream + prompt box |
| Mission | Action preview, hints, recovery, tasks, autonomy |
| Kali | Live terminal feed + command bar |
| Tools | OCR, playbooks, logs, security toolkit |

Controls: drag title bar to move, `Dock Left`/`Dock Right` to snap, opacity slider for HUD mode.

## Chat commands

| Command | What it does |
|---------|-------------|
| `/remember <text>` | Save something for Kai to learn |
| `/memory` | Show stored memory |
| `/screen` | Capture screen + OCR |
| `/run <cmd>` | Run a shell command |
| `/read <file>` | Read a file |
| `/ls <path>` | List files |
| `/autonomy on` | Enable guarded autonomy |
| `/autonomy tick` | Run one autonomous step |
| `/autonomy off` | Disable autonomy |

## Recovery mode

When a tool step fails, Kai builds a recovery summary:
- Failure point
- Likely cause
- Smallest fix
- Next command to try

When the primary model fails, Kai auto-recovers:
1. Fallback local models
2. Live web research (if `TAVILY_API_KEY` is set)

Set `KAI_FALLBACK_MODELS=qwen3:4b-q4_K_M,llama2:latest` to customize.

## 3D model

### Assets

| File | Role |
|------|------|
| `kai_textured.glb` | Canonical photo-replica (runtime identity) |
| `kai_textured_rigged.glb` | Provisional rigged candidate |
| `kai-lite.glb` | Motion reference donor only |
| `kai_mixamo_ready.fbx` | Staging file for Mixamo auto-rig |

### Rigging pipeline

1. Upload `kai_mixamo_ready.fbx` to [Mixamo](https://www.mixamo.com)
2. Auto-rig with marker placement
3. Download rigged result as `kai_mixamo_rigged_source.fbx`
4. Run rig prep:
   ```powershell
   powershell -ExecutionPolicy Bypass -File tools/prepare_kai_rig_runtime.ps1
   ```
5. Export validated `kai_textured_rigged.glb`

### Texturing workflow

```bash
# Open Blender workspace
blender kai_companion/assets/kai/kai_texture_workspace.blend

# Export textured mesh
blender -b --python tools/export_kai_runtime_glb.py

# Preview render
blender -b --python tools/render_kai_texture_preview.py
```

## Checkpoint and restore

```powershell
powershell -ExecutionPolicy Bypass -File tools/checkpoint_kai.ps1 -Name before-upgrade
powershell -ExecutionPolicy Bypass -File tools/restore_kai_checkpoint.ps1 -Branch codex/before-upgrade
```

## Logs

Structured interaction logs are written to `logs/events.jsonl`. The desktop panel has an `OPEN LOGS` button.

## Notes

- Default model: `qwen3:4b-q4_K_M` (lighter on 8 GB RAM)
- For heavier models, try: `python -m kai_agent.assistant --model <model>`
- Set `TAVILY_API_KEY` for live web research
- The companion only loads `kai_textured.glb` as runtime identity — do not substitute other assets silently
