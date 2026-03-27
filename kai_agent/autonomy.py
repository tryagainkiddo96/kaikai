from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from kai_agent.desktop_tools import DesktopTools
from kai_agent.memory import KaiMemory
from kai_agent.ollama_client import OllamaClient


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class KaiAutonomy:
    workspace: Path
    memory: KaiMemory
    tools: DesktopTools
    client: OllamaClient
    state_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.state_path = self.workspace / "memory" / "autonomy.json"
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self._save_state(
                {
                    "enabled": False,
                    "mode": "guarded",
                    "updated_at": utc_now(),
                    "last_run_at": None,
                    "last_result": "Autonomy is idle.",
                }
            )

    def _load_state(self) -> dict:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {
                "enabled": False,
                "mode": "guarded",
                "updated_at": utc_now(),
                "last_run_at": None,
                "last_result": "Autonomy state was reset after a file issue.",
            }
            self._save_state(state)
            return state

    def _save_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def enable(self) -> str:
        state = self._load_state()
        state["enabled"] = True
        state["updated_at"] = utc_now()
        state["last_result"] = "Autonomy enabled in guarded mode."
        self._save_state(state)
        return json.dumps({"action": "autonomy_enable", "ok": True, "state": state}, indent=2)

    def disable(self) -> str:
        state = self._load_state()
        state["enabled"] = False
        state["updated_at"] = utc_now()
        state["last_result"] = "Autonomy disabled."
        self._save_state(state)
        return json.dumps({"action": "autonomy_disable", "ok": True, "state": state}, indent=2)

    def status(self) -> str:
        return json.dumps({"action": "autonomy_status", "ok": True, "state": self._load_state()}, indent=2)

    def tick(self) -> str:
        state = self._load_state()
        if not state.get("enabled"):
            return json.dumps(
                {
                    "action": "autonomy_tick",
                    "ok": False,
                    "error": "Autonomy is disabled. Use `autonomy on` first.",
                    "state": state,
                },
                indent=2,
            )

        active_task = self.memory.get_active_task()
        if not active_task:
            state["last_run_at"] = utc_now()
            state["last_result"] = "No active task in queue."
            self._save_state(state)
            return json.dumps({"action": "autonomy_tick", "ok": True, "summary": state["last_result"], "state": state}, indent=2)

        planner_prompt = (
            "You are planning one guarded local operator step for Kai.\n"
            "Return only minified JSON with keys: decision, rationale, command, done.\n"
            "Rules:\n"
            "- decision must be one of run_command, complete_task, ask_user\n"
            "- command should be a single low-risk PowerShell command only when decision=run_command\n"
            "- never use delete/reset/format/reboot/shutdown/network-scanning commands\n"
            "- done is true only if the task is completed\n\n"
            f"Task title: {active_task.get('title', '')}\n"
            f"Task details: {active_task.get('details', '')}\n"
            "Output JSON only."
        )
        raw_plan = self.client.chat([{"role": "user", "content": planner_prompt}], timeout=180)
        try:
            plan = json.loads(raw_plan)
        except Exception:
            state["last_run_at"] = utc_now()
            state["last_result"] = f"Planner output was not valid JSON: {raw_plan[:200]}"
            self._save_state(state)
            return json.dumps({"action": "autonomy_tick", "ok": False, "error": state["last_result"], "state": state}, indent=2)

        decision = str(plan.get("decision", "")).strip().lower()
        if plan.get("done") or decision == "complete_task":
            completed = self.memory.complete_task(active_task["id"])
            state["last_run_at"] = utc_now()
            state["last_result"] = f"Completed task: {active_task.get('title', '')}"
            self._save_state(state)
            return json.dumps(
                {
                    "action": "autonomy_tick",
                    "ok": True,
                    "decision": "complete_task",
                    "task": completed,
                    "state": state,
                },
                indent=2,
            )

        if decision != "run_command":
            reason = str(plan.get("rationale", "Autonomy needs user guidance.")).strip()
            state["last_run_at"] = utc_now()
            state["last_result"] = reason
            self._save_state(state)
            return json.dumps(
                {"action": "autonomy_tick", "ok": True, "decision": "ask_user", "summary": reason, "state": state},
                indent=2,
            )

        command = str(plan.get("command", "")).strip()
        if not command:
            state["last_run_at"] = utc_now()
            state["last_result"] = "Planner chose run_command but returned no command."
            self._save_state(state)
            return json.dumps({"action": "autonomy_tick", "ok": False, "error": state["last_result"], "state": state}, indent=2)

        classification = self.tools.classify_command(command, shell="powershell")
        if classification.get("requires_confirmation", True) or int(classification.get("action_level", 5)) >= 4:
            state["last_run_at"] = utc_now()
            state["last_result"] = f"Blocked risky command pending approval: {command}"
            self._save_state(state)
            return json.dumps(
                {
                    "action": "autonomy_tick",
                    "ok": True,
                    "decision": "blocked_for_approval",
                    "command": command,
                    "classification": classification,
                    "state": state,
                },
                indent=2,
            )

        result = json.loads(self.tools.run_shell(command, timeout=60))
        state["last_run_at"] = utc_now()
        state["last_result"] = f"Executed guarded step: {command}"
        self._save_state(state)
        return json.dumps(
            {
                "action": "autonomy_tick",
                "ok": bool(result.get("returncode") == 0),
                "decision": "run_command",
                "command": command,
                "classification": classification,
                "result": result,
                "state": state,
            },
            indent=2,
        )
