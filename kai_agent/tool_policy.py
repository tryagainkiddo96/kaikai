from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_POLICY = {
    "mode": "power-user",
    "updated_at": None,
    "notes": "Capability controls only. Kai does not silently distort answers.",
}


TOOL_CATALOG: dict[str, dict[str, str]] = {
    "run_shell": {"category": "shell", "summary": "Run a PowerShell command in the Kai workspace."},
    "run_wsl": {"category": "shell", "summary": "Run a one-shot WSL command."},
    "run_kali_session_command": {"category": "shell", "summary": "Run a command in Kai's persistent Kali session."},
    "write_file": {"category": "filesystem", "summary": "Create or overwrite a file."},
    "append_file": {"category": "filesystem", "summary": "Append text to a file."},
    "replace_in_file": {"category": "filesystem", "summary": "Replace text in an existing file."},
    "open_path": {"category": "filesystem", "summary": "Open a local file or folder."},
    "read_file": {"category": "filesystem", "summary": "Read a local file."},
    "list_files": {"category": "filesystem", "summary": "List files in a local directory."},
    "clone_repo": {"category": "development", "summary": "Clone a repository into the workspace."},
    "extract_zip": {"category": "filesystem", "summary": "Extract an archive into a local folder."},
    "install_project": {"category": "development", "summary": "Install dependencies for a detected project."},
    "run_project": {"category": "development", "summary": "Launch a detected project entrypoint."},
    "run_tests": {"category": "development", "summary": "Run project tests."},
    "codex_edit": {"category": "development", "summary": "Delegate a focused code edit to Codex."},
    "codex_edit_and_test": {"category": "development", "summary": "Delegate a code edit and then run tests."},
    "search_web": {"category": "research", "summary": "Run live web research through Tavily when configured."},
    "browse": {"category": "browser", "summary": "Open a URL in headless browser automation."},
    "search_browser": {"category": "browser", "summary": "Search the web through browser automation."},
    "click_link": {"category": "browser", "summary": "Click a link on the active page."},
    "fill_form": {"category": "browser", "summary": "Fill a detected web form."},
    "download_file": {"category": "browser", "summary": "Download a file from the web."},
    "screenshot": {"category": "browser", "summary": "Capture a browser screenshot."},
    "capture_screen_ocr": {"category": "vision", "summary": "Capture the screen and OCR the result."},
    "capture_active_window_ocr": {"category": "vision", "summary": "Capture the active window and OCR the result."},
    "list_documents": {"category": "documents", "summary": "List documents indexed by Kai."},
    "find_document": {"category": "documents", "summary": "Search for a document by name."},
    "read_document": {"category": "documents", "summary": "Read a supported document."},
    "organize_downloads": {"category": "documents", "summary": "Organize Kai's download folder."},
    "document_stats": {"category": "documents", "summary": "Show document library statistics."},
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _normalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, Path):
            normalized[key] = str(value)
        elif isinstance(value, (str, int, float, bool)) or value is None:
            normalized[key] = value
        elif isinstance(value, (list, tuple)):
            normalized[key] = [str(item) if isinstance(item, Path) else item for item in value]
        elif isinstance(value, dict):
            normalized[key] = _normalize_metadata(value)
        else:
            normalized[key] = str(value)
    return normalized


@dataclass
class ToolPolicy:
    workspace: Path

    def __post_init__(self) -> None:
        self.state_path = self.workspace / "memory" / "tool_policy.json"
        self.log_path = self.workspace / "logs" / "tool_policy_events.jsonl"
        self._ensure_state()

    def _ensure_state(self) -> None:
        if not self.state_path.exists():
            state = dict(DEFAULT_POLICY)
            state["updated_at"] = utc_now()
            _atomic_write_json(self.state_path, state)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.exists():
            self.log_path.write_text("", encoding="utf-8")

    def _load_state(self) -> dict[str, Any]:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("mode") in {"power-user", "balanced", "guarded"}:
                return data
        except Exception:
            pass
        state = dict(DEFAULT_POLICY)
        state["updated_at"] = utc_now()
        _atomic_write_json(self.state_path, state)
        return state

    def status(self) -> dict[str, Any]:
        state = self._load_state()
        return {
            "action": "policy_status",
            "ok": True,
            "mode": state["mode"],
            "updated_at": state.get("updated_at"),
            "notes": state.get("notes"),
            "available_modes": {
                "power-user": "Permissive local operator mode. Only clearly destructive actions are blocked.",
                "balanced": "Reads and research stay open. Write, install, launch, and medium-risk shell actions are blocked for review.",
                "guarded": "Read-mostly mode. Only low-risk inspection and research actions are allowed.",
            },
        }

    def set_mode(self, mode: str) -> dict[str, Any]:
        normalized = mode.strip().lower()
        if normalized not in {"power-user", "balanced", "guarded"}:
            return {
                "action": "policy_set_mode",
                "ok": False,
                "error": f"Unsupported policy mode: {mode}",
                "supported_modes": ["power-user", "balanced", "guarded"],
            }
        state = self._load_state()
        state["mode"] = normalized
        state["updated_at"] = utc_now()
        _atomic_write_json(self.state_path, state)
        return {"action": "policy_set_mode", "ok": True, "mode": normalized, "updated_at": state["updated_at"]}

    def capabilities(self) -> dict[str, Any]:
        state = self._load_state()
        return {
            "action": "capabilities",
            "ok": True,
            "policy_mode": state["mode"],
            "tools": [
                {"name": name, **metadata}
                for name, metadata in sorted(TOOL_CATALOG.items(), key=lambda item: item[0])
            ],
        }

    def build_context(self) -> str:
        state = self._load_state()
        lines = [
            "Kai capability context:",
            f"- Policy mode: {state['mode']}",
            "- Kai separates answer quality from capability control.",
            "- Hidden moralizing is not part of the tool policy. Restrictions are explicit and operational.",
            "- Available tool families:",
        ]
        for name, metadata in sorted(TOOL_CATALOG.items(), key=lambda item: item[0]):
            lines.append(f"  - {name}: {metadata['summary']}")
        return "\n".join(lines)

    def evaluate(self, action: str, metadata: dict[str, Any]) -> dict[str, Any]:
        state = self._load_state()
        mode = state["mode"]
        normalized = _normalize_metadata(metadata)
        action_level = int(normalized.get("action_level", 1) or 1)
        tags = [str(tag).lower() for tag in normalized.get("tags", [])]
        category = TOOL_CATALOG.get(action, {}).get("category", "general")
        destructive = "destructive" in tags or action_level >= 5
        system_changing = "system-changing" in tags
        network_active = "network-active" in tags

        if mode == "power-user":
            if destructive:
                return self._decision(False, mode, "Blocked clearly destructive action in power-user mode.")
            return self._decision(True, mode, "Allowed in power-user mode.")

        if mode == "balanced":
            if destructive:
                return self._decision(False, mode, "Blocked destructive action in balanced mode.")
            if category in {"filesystem", "development"} and action not in {"read_file", "list_files", "run_tests"}:
                return self._decision(False, mode, f"{action} is blocked in balanced mode pending review.")
            if category == "browser" and action in {"fill_form", "download_file"}:
                return self._decision(False, mode, f"{action} is blocked in balanced mode pending review.")
            if category == "shell" and (action_level >= 3 or system_changing or network_active):
                return self._decision(False, mode, "Medium or higher risk shell activity is blocked in balanced mode.")
            return self._decision(True, mode, "Allowed in balanced mode.")

        if destructive:
            return self._decision(False, mode, "Blocked destructive action in guarded mode.")
        if category in {"filesystem", "development"} and action not in {"read_file", "list_files", "run_tests"}:
            return self._decision(False, mode, f"{action} is not allowed in guarded mode.")
        if category == "shell" and action_level >= 2:
            return self._decision(False, mode, "Shell execution is limited to low-risk inspection in guarded mode.")
        if category == "browser" and action not in {"browse", "search_browser", "get_page_content", "screenshot"}:
            return self._decision(False, mode, f"{action} is not allowed in guarded mode.")
        return self._decision(True, mode, "Allowed in guarded mode.")

    def _decision(self, allowed: bool, mode: str, reason: str) -> dict[str, Any]:
        return {"allowed": allowed, "policy_mode": mode, "policy_reason": reason}

    def record(self, action: str, metadata: dict[str, Any], decision: dict[str, Any]) -> None:
        entry = {
            "timestamp": utc_now(),
            "action": action,
            "metadata": _normalize_metadata(metadata),
            "decision": decision,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
