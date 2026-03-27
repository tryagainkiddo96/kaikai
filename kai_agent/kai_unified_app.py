import argparse
import asyncio
import csv
import io
import json
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

from kai_agent.assistant import KaiAssistant
from kai_agent.desktop_panel_unified import KaiPanelUnified


APP_NAME = "KaiUnified"
SOURCE_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 8765
BRIDGE_URL = f"ws://{BRIDGE_HOST}:{BRIDGE_PORT}"
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
CHAT_HOST = "127.0.0.1"
CHAT_PORT = 8127
_BRIDGE_THREAD: threading.Thread | None = None
_BRIDGE_ERROR: str | None = None
_CHAT_SERVER = None
_CHAT_SERVER_THREAD: threading.Thread | None = None


def _candidate_roots() -> list[Path]:
    candidates: list[Path] = []
    for env_key in ("KAI_ROOT", "KAI_WORKSPACE"):
        raw_value = os.environ.get(env_key, "").strip()
        if raw_value:
            candidates.append(Path(raw_value).expanduser())
    candidates.append(Path.cwd())
    if sys.executable:
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([exe_dir.parent, exe_dir])
    candidates.append(SOURCE_ROOT)
    return candidates


def _looks_like_workspace(path: Path) -> bool:
    return (path / "kai_agent").exists() and (path / "kai_companion").exists()


def _resolve_workspace_root() -> Path:
    seen: set[str] = set()
    for candidate in _candidate_roots():
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if _looks_like_workspace(resolved):
            return resolved
    return SOURCE_ROOT


WORKSPACE_ROOT = _resolve_workspace_root()


def _resolve_data_root() -> Path:
    raw_value = os.environ.get("KAI_DATA_ROOT", "").strip()
    if raw_value:
        return Path(raw_value).expanduser().resolve()
    if WORKSPACE_ROOT.exists():
        return WORKSPACE_ROOT
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local_app_data / APP_NAME


DATA_ROOT = _resolve_data_root()


def _resolve_log_root() -> Path:
    raw_value = os.environ.get("KAI_LOG_ROOT", "").strip()
    if raw_value:
        return Path(raw_value).expanduser().resolve()
    return DATA_ROOT / "logs"


LOG_ROOT = _resolve_log_root()


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def _wait_for_port(host: str, port: int, seconds: float) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if _port_open(host, port):
            return True
        time.sleep(0.25)
    return False


def _append_launch_log(event_type: str, payload: dict[str, object]) -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event_type": event_type,
    }
    record.update(payload)
    try:
        with (LOG_ROOT / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
    except Exception:
        # Last-resort logging must never crash startup.
        pass


def _resolve_godot() -> str | None:
    candidates = [
        os.environ.get("KAI_GODOT", "").strip(),
        r"C:\Users\7nujy6xc\AppData\Local\Microsoft\WinGet\Links\godot.exe",
        r"C:\Program Files\Godot\Godot.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _resolve_companion_path() -> Path | None:
    candidates: list[Path] = []
    raw_value = os.environ.get("KAI_COMPANION_PATH", "").strip()
    if raw_value:
        candidates.append(Path(raw_value).expanduser())
    candidates.extend(
        [
            WORKSPACE_ROOT / "kai_companion",
            SOURCE_ROOT / "kai_companion",
            Path.cwd() / "kai_companion",
        ]
    )
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if (resolved / "project.godot").exists():
            return resolved
    return None


def _resolve_model(default_model: str) -> str:
    env_model = os.environ.get("KAI_MODEL", "").strip()
    if env_model:
        return env_model
    return default_model


def _window_title_running(fragment: str) -> bool:
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/v", "/fo", "csv"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return False
    if result.returncode != 0 or not result.stdout:
        return False
    lowered_fragment = fragment.lower()
    try:
        reader = csv.DictReader(io.StringIO(result.stdout))
    except Exception:
        return lowered_fragment in result.stdout.lower()
    for row in reader:
        title = str(row.get("Window Title", "")).strip()
        if lowered_fragment in title.lower():
            return True
    return False


def _panel_window_running() -> bool:
    return _window_title_running("Kai Command Center")


def _companion_window_running() -> bool:
    return _window_title_running("Kai Companion")


def _start_ollama_if_needed() -> None:
    if _port_open(OLLAMA_HOST, OLLAMA_PORT):
        return
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            cwd=str(WORKSPACE_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if not _wait_for_port(OLLAMA_HOST, OLLAMA_PORT, seconds=20):
            _append_launch_log(
                "ollama_start_warning",
                {"message": "Ollama did not become ready on http://127.0.0.1:11434"},
            )
    except Exception as exc:
        _append_launch_log("ollama_start_warning", {"message": str(exc)})
        return


def _probe_bridge() -> tuple[bool, str]:
    async def _run_probe() -> tuple[bool, str]:
        import websockets

        probe_id = f"probe-{time.time_ns()}"
        async with websockets.connect(
            BRIDGE_URL,
            open_timeout=1.5,
            close_timeout=1.5,
            ping_interval=None,
        ) as websocket:
            await asyncio.wait_for(
                websocket.send(json.dumps({"event": "bridge_probe", "id": probe_id})),
                timeout=1.5,
            )
            deadline = time.time() + 1.5
            while time.time() < deadline:
                timeout = max(0.1, deadline - time.time())
                raw_message = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                try:
                    payload = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue
                if payload.get("event") == "bridge_probe" and payload.get("id") == probe_id:
                    return True, ""
        return False, "bridge probe did not echo back"

    try:
        return asyncio.run(_run_probe())
    except Exception as exc:
        return False, str(exc)


def _wait_for_bridge_ready(seconds: float) -> tuple[bool, str]:
    deadline = time.time() + seconds
    last_error = ""
    while time.time() < deadline:
        if _port_open(BRIDGE_HOST, BRIDGE_PORT):
            ready, error = _probe_bridge()
            if ready:
                return True, ""
            last_error = error
        time.sleep(0.25)
    return False, last_error


def _start_bridge_if_needed() -> None:
    global _BRIDGE_ERROR, _BRIDGE_THREAD
    if _port_open(BRIDGE_HOST, BRIDGE_PORT):
        ready, error = _wait_for_bridge_ready(seconds=2)
        if ready:
            return
        raise RuntimeError(f"Kai bridge probe failed on {BRIDGE_URL}: {error}")
    _BRIDGE_ERROR = None

    def _run_bridge() -> None:
        global _BRIDGE_ERROR
        try:
            from kai_agent.bridge_server import main as bridge_main

            asyncio.run(bridge_main())
        except Exception as exc:
            _BRIDGE_ERROR = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            _append_launch_log(
                "bridge_startup_error",
                {
                    "error": _BRIDGE_ERROR,
                    "traceback": traceback.format_exc().strip(),
                },
            )

    if _BRIDGE_THREAD is None or not _BRIDGE_THREAD.is_alive():
        _BRIDGE_THREAD = threading.Thread(target=_run_bridge, name="kai-bridge", daemon=True)
        _BRIDGE_THREAD.start()
    ready, bridge_probe_error = _wait_for_bridge_ready(seconds=12)
    if not ready:
        if _BRIDGE_ERROR:
            raise RuntimeError(f"Kai bridge failed to start: {_BRIDGE_ERROR}")
        if bridge_probe_error:
            raise RuntimeError(f"Kai bridge did not become ready on {BRIDGE_URL}: {bridge_probe_error}")
        raise RuntimeError(f"Kai bridge did not become ready on {BRIDGE_URL}")


def _start_chat_server_if_needed(assistant: KaiAssistant) -> None:
    global _CHAT_SERVER, _CHAT_SERVER_THREAD
    if _port_open(CHAT_HOST, CHAT_PORT):
        return
    try:
        from kai_agent.widget_server import Handler, KaiWidgetServer

        _CHAT_SERVER = KaiWidgetServer((CHAT_HOST, CHAT_PORT), Handler, assistant)
        _CHAT_SERVER_THREAD = threading.Thread(target=_CHAT_SERVER.serve_forever, name="kai-chat-server", daemon=True)
        _CHAT_SERVER_THREAD.start()
        if not _wait_for_port(CHAT_HOST, CHAT_PORT, seconds=5):
            raise RuntimeError(f"Kai chat server did not become ready on http://{CHAT_HOST}:{CHAT_PORT}")
    except Exception as exc:
        _append_launch_log("chat_server_warning", {"error": str(exc), "host": CHAT_HOST, "port": CHAT_PORT})


def _start_companion(scene: str) -> None:
    godot = _resolve_godot()
    if not godot:
        _append_launch_log("companion_warning", {"message": "Godot executable was not found"})
        return
    companion_path = _resolve_companion_path()
    if companion_path is None:
        _append_launch_log(
            "companion_warning",
            {"message": "Companion project path was not found", "workspace_root": str(WORKSPACE_ROOT)},
        )
        return
    args = [godot, "--path", str(companion_path)]
    if scene:
        args.append(scene)
    proc = subprocess.Popen(
        args,
        cwd=str(companion_path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _spawn_companion_process(scene: str) -> subprocess.Popen | None:
    if _companion_window_running():
        return None
    godot = _resolve_godot()
    if not godot:
        raise RuntimeError("Godot executable was not found")
    companion_path = _resolve_companion_path()
    if companion_path is None:
        raise RuntimeError(f"Companion project path was not found under {WORKSPACE_ROOT}")
    args = [godot, "--path", str(companion_path)]
    if scene:
        args.append(scene)
    return subprocess.Popen(
        args,
        cwd=str(companion_path),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _verify_companion_started(companion_process: subprocess.Popen | None, scene: str) -> None:
    if companion_process is None:
        return
    time.sleep(2.0)
    exit_code = companion_process.poll()
    if exit_code is None:
        return
    _append_launch_log(
        "companion_startup_error",
        {
            "message": "Companion exited during startup",
            "scene": scene,
            "exit_code": exit_code,
        },
    )
    raise RuntimeError(f"Kai companion exited during startup for scene {scene} with exit code {exit_code}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kai unified desktop app")
    parser.add_argument("--model", default="qwen3:4b-q4_K_M")
    parser.add_argument("--workspace", default=str(WORKSPACE_ROOT))
    parser.add_argument("--scene", default=os.environ.get("KAI_SCENE", "res://scenes/kai.tscn"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace = Path(args.workspace).resolve()
    model = _resolve_model(args.model)
    children: list[subprocess.Popen] = []
    companion_process: subprocess.Popen | None = None
    start_companion = os.environ.get("KAI_START_COMPANION", "0").strip() == "1"

    try:
        if _panel_window_running():
            _append_launch_log("launch_skip", {"message": "Kai Command Center is already running"})
            return
        _append_launch_log(
            "launch_start",
            {
                "workspace": str(workspace),
                "workspace_root": str(WORKSPACE_ROOT),
                "data_root": str(DATA_ROOT),
                "log_root": str(LOG_ROOT),
                "frozen": bool(getattr(sys, "frozen", False)),
            },
        )
        _start_ollama_if_needed()
        _start_bridge_if_needed()
        if start_companion:
            companion_process = _spawn_companion_process(args.scene)
            _verify_companion_started(companion_process, args.scene)
        assistant = KaiAssistant(model=model, workspace=workspace)
        _start_chat_server_if_needed(assistant)

        def companion_status() -> str:
            nonlocal companion_process
            if _companion_window_running():
                return "RUNNING"
            if companion_process is None:
                return "STOPPED"
            return "RUNNING" if companion_process.poll() is None else "STOPPED"

        def open_companion() -> str:
            nonlocal companion_process
            if _companion_window_running():
                return "Companion is already running."
            if companion_process is not None and companion_process.poll() is None:
                return "Companion is already running."
            companion_process = _spawn_companion_process(args.scene)
            if companion_process is None:
                return "Companion is already running."
            _verify_companion_started(companion_process, args.scene)
            return "Companion opened."

        def close_companion() -> str:
            nonlocal companion_process
            if companion_process is None or companion_process.poll() is not None:
                companion_process = None
                return "Companion was already closed."
            companion_process.terminate()
            try:
                companion_process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                companion_process.kill()
                companion_process.wait(timeout=2)
            companion_process = None
            return "Companion closed."

        def restart_companion() -> str:
            close_companion()
            return open_companion().replace("opened", "restarted")

        app = KaiPanelUnified(
            assistant=assistant,
            model_label=model,
            open_companion_callback=open_companion,
            close_companion_callback=close_companion,
            restart_companion_callback=restart_companion,
            companion_status_callback=companion_status,
            on_close_callback=None,
        )
        app.run()
        _append_launch_log("launch_exit", {"message": "KaiUnified exited cleanly"})
    except Exception as exc:
        _append_launch_log(
            "launch_error",
            {"error": str(exc), "traceback": traceback.format_exc().strip()},
        )
        raise
    finally:
        global _CHAT_SERVER
        if _CHAT_SERVER is not None:
            try:
                _CHAT_SERVER.shutdown()
                _CHAT_SERVER.server_close()
            except Exception:
                pass
            _CHAT_SERVER = None
        if not start_companion:
            companion_process = None
        for child in children:
            try:
                if child.poll() is None:
                    child.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()
