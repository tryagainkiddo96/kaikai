"""
Kai Ghost Mode
The ultimate stealth ability. Kai doesn't move unless he's 100% undetected.
Ties into the environment awareness system.

Ghost Mode Rules:
  1. Before ANY action, check all detection sources
  2. If ANY source detects presence → freeze
  3. Only act when ALL sources report clear
  4. Log every detection event
  5. Learn detection patterns over time
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from kai_agent.environment import EnvironmentMonitor, EnvironmentReading


@dataclass
class GhostEvent:
    """A logged ghost mode event."""
    timestamp: float
    event_type: str  # scan, freeze, act, breach, clear
    threat_level: str
    blockers: list[str]
    action: str = ""
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "threat_level": self.threat_level,
            "blockers": self.blockers,
            "action": self.action,
            "duration": round(self.duration, 2),
        }


class GhostMode:
    """
    Kai's Ghost Mode — zero detection stealth operation.
    
    When active, Kai:
    - Scans environment before every action
    - Freezes if any detection source triggers
    - Only moves when 100% clear
    - Logs every detection event
    - Learns patterns (when is the house usually empty?)
    """

    def __init__(self, environment: EnvironmentMonitor, save_path: Path | None = None):
        self.env = environment
        self.save_path = save_path or Path.cwd() / "memory" / "ghost_mode.json"

        self._active = False
        self._frozen = False
        self._freeze_reason = ""
        self._events: list[GhostEvent] = []
        self._max_events = 200
        self._action_queue: list[str] = []

        # Pattern learning
        self._quiet_hours: dict[int, float] = {}  # hour → average detection count
        self._load()

    def _load(self):
        if self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text(encoding="utf-8"))
                self._quiet_hours = data.get("quiet_hours", {})
            except Exception:
                pass

    def save(self):
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "quiet_hours": self._quiet_hours,
            "total_events": len(self._events),
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.save_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # -- Ghost State --

    def activate(self) -> dict[str, Any]:
        """Enter Ghost Mode."""
        self._active = True
        self._frozen = False

        check = self.env.ghost_check()
        self._log_event("scan", check["threat_level"], check["blockers"])

        if not check["go"]:
            self._freeze(check["blockers"])

        return {
            "active": True,
            "frozen": self._frozen,
            "status": check,
            "message": "Ghost Mode active. Scanning environment..." if not self._frozen
                       else "Ghost Mode active. FROZEN — detection present.",
        }

    def deactivate(self) -> dict[str, Any]:
        """Exit Ghost Mode."""
        self._active = False
        self._frozen = False
        self._action_queue.clear()
        self._log_event("clear", "clear", [])
        self.save()
        return {"active": False, "message": "Ghost Mode disengaged."}

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def is_frozen(self) -> bool:
        return self._frozen

    # -- Core Loop --

    def request_action(self, action: str) -> dict[str, Any]:
        """
        Request an action in Ghost Mode.
        Returns go/no-go with full status.
        """
        if not self._active:
            return {"go": True, "message": "Ghost Mode not active."}

        check = self.env.ghost_check()

        if not check["go"]:
            # Freeze
            self._freeze(check["blockers"])
            self._log_event("freeze", check["threat_level"], check["blockers"], action)
            return {
                "go": False,
                "frozen": True,
                "blockers": check["blockers"],
                "threat_level": check["threat_level"],
                "message": f"FROZEN — {', '.join(check['blockers'])} detected. Cannot execute '{action}'.",
            }

        # Clear to act
        if self._frozen:
            self._unfreeze()
            self._log_event("clear", "clear", [])

        self._log_event("act", "clear", [], action)

        # Update quiet hours pattern
        hour = datetime.now().hour
        detection = self.env._last_reading.detection_count if self.env._last_reading else 0
        if hour in self._quiet_hours:
            self._quiet_hours[hour] = (self._quiet_hours[hour] * 0.9) + (detection * 0.1)
        else:
            self._quiet_hours[hour] = float(detection)

        return {
            "go": True,
            "frozen": False,
            "threat_level": "clear",
            "action": action,
            "message": f"Clear to execute: {action}",
        }

    def scan(self) -> dict[str, Any]:
        """Full environment scan without taking action."""
        check = self.env.ghost_check()
        self._log_event("scan", check["threat_level"], check["blockers"])

        if check["go"] and self._frozen:
            self._unfreeze()
        elif not check["go"] and not self._frozen:
            self._freeze(check["blockers"])

        return check

    # -- Internal --

    def _freeze(self, blockers: list[str]):
        self._frozen = True
        self._freeze_reason = ", ".join(blockers)

    def _unfreeze(self):
        self._frozen = False
        self._freeze_reason = ""

    def _log_event(self, event_type: str, threat: str, blockers: list[str], action: str = ""):
        event = GhostEvent(
            timestamp=time.time(),
            event_type=event_type,
            threat_level=threat,
            blockers=blockers,
            action=action,
        )
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

    # -- Pattern Analysis --

    def get_quiet_windows(self) -> list[dict[str, Any]]:
        """Find the quietest hours (best time for Ghost Mode ops)."""
        if not self._quiet_hours:
            return []

        sorted_hours = sorted(self._quiet_hours.items(), key=lambda x: x[1])
        windows = []
        for hour, avg_detection in sorted_hours[:5]:
            windows.append({
                "hour": hour,
                "hour_label": f"{hour:02d}:00",
                "avg_detection": round(avg_detection, 2),
                "quality": "optimal" if avg_detection < 0.5 else "good" if avg_detection < 2 else "risky",
            })
        return windows

    def get_stats(self) -> dict[str, Any]:
        """Ghost Mode statistics."""
        scans = [e for e in self._events if e.event_type == "scan"]
        freezes = [e for e in self._events if e.event_type == "freeze"]
        acts = [e for e in self._events if e.event_type == "act"]

        return {
            "active": self._active,
            "frozen": self._frozen,
            "freeze_reason": self._freeze_reason,
            "total_scans": len(scans),
            "total_freezes": len(freezes),
            "total_actions": len(acts),
            "detection_rate": round(len(freezes) / max(1, len(scans)), 2),
            "quiet_windows": self.get_quiet_windows(),
        }

    def get_status_line(self) -> str:
        """One-line status for HUD."""
        if not self._active:
            return "👻 Ghost Mode: OFF"
        if self._frozen:
            return f"👻 FROZEN — {self._freeze_reason}"
        return "👻 Ghost Mode: CLEAR — ready to act"
