# Kai AI

Kai is now split into two pieces:

- a local assistant brain that runs against Ollama
- a Godot companion that reacts to websocket events

Temporary avatar direction for the companion build:

- breed: Shiba Inu
- sex: male
- coat: black and tan
- markings: white / cream chest, muzzle, and paw accents
- style: realistic desktop companion placeholder until the final Kai model is ready

Project layout:

- `kai_agent/` for the Python-side Kai brain
- `bridge/` for websocket or IPC handoff
- `kai_companion/` for the Godot desktop avatar
- `tools/` and `plugins/` for supporting integrations

Current placeholder avatar asset:

- `kai_companion/assets/kai/kai_textured.glb` is the canonical Kai photo-replica appearance asset
- `kai_companion/assets/kai/kai-lite.glb` is motion-reference only and must not silently replace Kai at runtime

Current Godot entry points:

- `kai_companion/project.godot`
- `kai_companion/scenes/kai_3d.tscn`
- `kai_companion/scripts/kai_3d.gd`

Bridge and agent:

- `bridge/server.py` hosts the websocket event bridge on `ws://127.0.0.1:8765`
- `kai_agent/emit_event.py` sends `kai_thinking`, `kai_walk`, `kai_sleep`, or `kai_wag_tail`
- `kai_agent/assistant.py` runs a local Kai CLI backed by Ollama
- `memory/` stores lightweight persistent notes and session history for Kai

Quick start:

```bash
python -m pip install -r requirements.txt
python bridge/server.py
python -m kai_agent.assistant --model xploiter/the-xploiter:latest
```

Unified local launcher:

```powershell
powershell -ExecutionPolicy Bypass -File tools/launch_kai_stack.ps1
```

Checkpoint and restore:

```powershell
powershell -ExecutionPolicy Bypass -File tools/checkpoint_kai.ps1 -Name before-upgrade
powershell -ExecutionPolicy Bypass -File tools/restore_kai_checkpoint.ps1 -Branch codex/before-upgrade
```

Structured logs:

- Kai now writes structured interaction logs to `logs/events.jsonl`
- the desktop panel includes an `OPEN LOGS` button for quick access

Recovery mode:

- when a tool step fails, Kai now builds a recovery summary with:
  - failure point
  - likely cause
  - smallest fix
  - next command when useful
- when the primary local model fails, Kai now auto-recovers in this order:
  - fallback local model(s)
  - live web research (if `TAVILY_API_KEY` is configured)
- set `KAI_FALLBACK_MODELS` to customize fallback order (comma-separated), for example:
  - `KAI_FALLBACK_MODELS=qwen3:4b-q4_K_M,llama2:latest,mistral:latest`

Futuristic chat widget:

```powershell
powershell -ExecutionPolicy Bypass -File tools/launch_kai_widget.ps1
```

Always-on-top desktop panel:

```powershell
powershell -ExecutionPolicy Bypass -File tools/launch_kai_panel.ps1
```

Panel layout (single command center):

- `Chat` tab: full conversation stream + prompt box
- `Mission` tab: action preview, hints, recovery, tasks, autonomy controls
- `Kali` tab: live terminal feed + command bar + reset/connect
- `Tools` tab: OCR, playbooks, security stack, toolkit, logs access

No-background-shell launcher (double-click):

- `tools/launch_kai_panel.vbs`
- starts Kai Panel as a detached GUI process and immediately exits

Panel controls:

- drag the title bar to move it
- `Dock Left` and `Dock Right` snap it to the screen edge
- `F10` docks left and `F11` docks right
- use the opacity slider for a more HUD-like transparent look

Kai companion notes:

- The companion now uses a lightweight 3D desktop-pet flow rendered in a transparent viewport.
- Left click and drag Kai to move the desktop window.
- Right click Kai to open or close the chat panel.
- The companion can chat directly with local Ollama from Godot.
- Default model in the companion is `qwen3:4b-q4_K_M` for better performance on lower-RAM systems.
- The active runtime loads only `kai_companion/assets/kai/kai_textured.glb` as Kai's identity asset.
- `kai_companion/assets/kai/kai-lite.glb` remains a motion-reference donor and is not used as a visible runtime swap.
- The next rig target is `kai_companion/assets/kai/kai_textured_rigged.glb`.

Rig runtime prep:

```powershell
powershell -ExecutionPolicy Bypass -File tools/prepare_kai_rig_runtime.ps1
```

- This now expects a validated `kai_companion/assets/kai/kai_mixamo_rigged_source.fbx` with a real armature and walk-like clip before it will export `kai_textured_rigged.glb`.
- For local evaluation only, `tools/bootstrap_kai_donor_rig.ps1` can generate `kai_companion/assets/kai/kai_donor_bootstrap_rig_source.fbx` by binding the canonical Kai mesh to the donor armature.

Kai 3D texturing workflow:

- `tools/prepare_kai_texture_workspace.py` copies Kai photo references, the source model, and extracted viewer frames into `kai_companion/assets/kai/reference`.
- `tools/setup_kai_blender_scene.py` creates `kai_companion/assets/kai/kai_texture_workspace.blend` from the canonical `kai_textured.glb` when present, with lighting and reference boards.
- `tools/open_kai_texture_workspace.ps1` opens that Blender workspace directly.
- `tools/export_kai_runtime_glb.py` exports the active textured Blender mesh to `kai_companion/assets/kai/kai_textured.glb`.
- `tools/export_kai_runtime.ps1` runs the Blender export and then reimports the asset into Godot.
- `tools/render_kai_texture_preview.py` renders a quick workbench preview to `tmp/renders/kai_texture_preview.png`.
- `kai_texture_paint.png` changes do not affect runtime until the mesh is re-exported back into `kai_textured.glb`.

Current 3D texture workspace assets:

- `kai_companion/assets/kai/modelToUsed.glb` as the legacy external base-mesh lineage input, not a runtime asset
- `kai_companion/assets/kai/kai_texture_workspace.blend`
- `kai_companion/assets/kai/kai_texture_paint.png`
- `kai_companion/assets/kai/reference/`

Useful commands inside Kai:

- `/remember <text>` saves something Kai should learn
- `/memory` shows Kai's current stored memory
- `/screen` captures the current screen and OCRs visible text
- `/run <powershell>` runs a PowerShell command in the repo workspace
- `/read <file>` reads a file
- `/ls <path>` lists files
- `/autonomy on` enables guarded autonomy
- `/autonomy status` shows autonomy state and last run result
- `/autonomy tick` runs one autonomous step against the active task
- `/autonomy off` disables autonomy
- `/exit` closes the session

Guarded autonomy policy:

- Kai only executes low-risk (`action_level < 4`) commands during autonomous ticks.
- Medium/high-risk commands are blocked and surfaced for explicit human approval.
- State is persisted in `memory/autonomy.json`.

Live web research:

- set `TAVILY_API_KEY` in your environment to enable live research inside Kai
- then ask things like:
  - `web: latest install method for n8n on Windows`
  - `research: current package name for ffuf on Kali`
  - `look it up: how Tavily search depth works`

Authorized cyber lab helper:

- ask `show cyber tools` to load Kai's local authorized-lab toolkit notes
- current reference file: `CYBER_LAB_TOOLKIT.md`

Notes:

- `xploiter/the-xploiter:latest` is installed locally on this machine but is heavy for 8 GB RAM.
- If responses are too slow, try `python -m kai_agent.assistant --model qwen3:4b-q4_K_M`
