"""
Kai Social Timing Engine
Knows when to speak up and when to stay quiet.
The difference between a chatbot and a companion is timing.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# ---------------------------------------------------------------------------
# Interaction history
# ---------------------------------------------------------------------------

@dataclass
class SessionRecord:
    """A recorded interaction session."""
    start: float
    end: float = 0.0
    message_count: int = 0
    last_message: float = 0.0

    @property
    def duration_minutes(self) -> float:
        end = self.end or time.time()
        return (end - self.start) / 60.0

    @property
    def idle_minutes(self) -> float:
        if self.last_message <= 0:
            return 0
        return (time.time() - self.last_message) / 60.0


# ---------------------------------------------------------------------------
# Timing signals — what conditions trigger proactive behavior
# ---------------------------------------------------------------------------

@dataclass
class TimingSignal:
    """A condition that might trigger Kai to speak up."""
    name: str
    priority: int  # 1=low, 5=urgent
    message: str
    check: Callable[["SocialTiming"], bool]
    cooldown_minutes: float = 60.0  # don't fire again within this window
    last_fired: float = 0.0
    requires_silence_minutes: float = 0.0  # only fire if user has been quiet this long

    def can_fire(self, timing: "SocialTiming") -> bool:
        """Check if this signal can fire right now."""
        # Cooldown
        if (time.time() - self.last_fired) / 60.0 < self.cooldown_minutes:
            return False
        # Silence requirement
        if self.requires_silence_minutes > 0:
            idle = timing.idle_minutes
            if idle < self.requires_silence_minutes:
                return False
            # Don't fire if user has been gone TOO long (they're not here)
            if idle > 120:
                return False
        # Quiet hours check (unless urgent)
        if self.priority < 4 and timing.is_quiet_hours:
            return False
        # Actual condition
        return self.check(timing)

    def fire(self) -> str:
        """Mark as fired and return the message."""
        self.last_fired = time.time()
        return self.message


# ---------------------------------------------------------------------------
# Social Timing Engine
# ---------------------------------------------------------------------------

class SocialTiming:
    """
    Decides WHEN Kai should speak up.
    Tracks patterns, detects situations, generates proactive moments.
    """

    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path or Path.cwd() / "memory" / "social_timing.json"

        # Current session tracking
        self.current_session: SessionRecord | None = None
        self.last_interaction: float = 0.0

        # Historical patterns
        self.session_history: list[dict[str, Any]] = []
        self.daily_patterns: dict[str, list[float]] = {}  # "09" -> [active_minutes, ...]
        self.total_interactions: int = 0

        # Quiet hours (24h format, user's local)
        self.quiet_start: int = 23  # 11 PM
        self.quiet_end: int = 7     # 7 AM

        # Configuration
        self.overwork_threshold_minutes: float = 120.0
        self.absence_threshold_hours: float = 12.0
        self.greeting_cooldown_hours: float = 8.0
        self.check_interval_seconds: float = 60.0

        # Signals
        self.signals: list[TimingSignal] = []
        self._register_default_signals()

        self._load()

    def _load(self) -> None:
        if self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text(encoding="utf-8"))
                self.session_history = data.get("session_history", [])
                self.daily_patterns = data.get("daily_patterns", {})
                self.total_interactions = data.get("total_interactions", 0)
                self.last_interaction = data.get("last_interaction", 0.0)
                self.quiet_start = data.get("quiet_start", 23)
                self.quiet_end = data.get("quiet_end", 7)
            except Exception:
                pass

    def save(self) -> None:
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "session_history": self.session_history[-50:],
            "daily_patterns": self.daily_patterns,
            "total_interactions": self.total_interactions,
            "last_interaction": self.last_interaction,
            "quiet_start": self.quiet_start,
            "quiet_end": self.quiet_end,
            "updated_at": utc_now(),
        }
        self.save_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # -- Session tracking --

    def interaction_started(self) -> None:
        """User initiated an interaction."""
        now = time.time()
        self.last_interaction = now
        self.total_interactions += 1

        if self.current_session is None:
            self.current_session = SessionRecord(start=now, last_message=now)
        else:
            self.current_session.last_message = now

        self.current_session.message_count += 1

        # Update daily pattern
        hour_key = datetime.now().strftime("%H")
        if hour_key not in self.daily_patterns:
            self.daily_patterns[hour_key] = []
        self.daily_patterns[hour_key].append(1)
        # Keep last 30 entries per hour
        self.daily_patterns[hour_key] = self.daily_patterns[hour_key][-30:]

        self.save()

    def session_ended(self) -> None:
        """User left / session ended."""
        if self.current_session:
            self.current_session.end = time.time()
            self.session_history.append({
                "start": self.current_session.start,
                "end": self.current_session.end,
                "duration_minutes": round(self.current_session.duration_minutes, 1),
                "messages": self.current_session.message_count,
            })
            self.current_session = None
        self.save()

    # -- Pattern queries --

    @property
    def idle_minutes(self) -> float:
        """How long since last interaction."""
        if self.last_interaction <= 0:
            return 9999
        return (time.time() - self.last_interaction) / 60.0

    @property
    def session_duration_minutes(self) -> float:
        """How long the current session has been active."""
        if not self.current_session:
            return 0
        return self.current_session.duration_minutes

    @property
    def is_quiet_hours(self) -> bool:
        """Is it currently quiet hours?"""
        hour = datetime.now().hour
        if self.quiet_start > self.quiet_end:
            return hour >= self.quiet_start or hour < self.quiet_end
        return self.quiet_start <= hour < self.quiet_end

    @property
    def is_overwork(self) -> bool:
        """Has the user been working too long without a break?"""
        return self.session_duration_minutes > self.overwork_threshold_minutes

    @property
    def is_absent(self) -> bool:
        """Has the user been gone for a long time?"""
        return self.idle_minutes / 60.0 > self.absence_threshold_hours

    @property
    def is_returning(self) -> bool:
        """Did the user just come back after a long absence?"""
        if self.last_interaction <= 0:
            return False
        # Check if session just started and previous gap was long
        if self.current_session and self.current_session.message_count <= 2:
            if len(self.session_history) > 0:
                last_end = self.session_history[-1].get("end", 0)
                gap_hours = (self.current_session.start - last_end) / 3600.0
                return gap_hours > 2.0
        return False

    def get_typical_active_hours(self) -> list[int]:
        """What hours is the user typically active?"""
        active_hours = []
        for hour_key, counts in self.daily_patterns.items():
            if len(counts) >= 3:  # at least 3 sessions at this hour
                active_hours.append(int(hour_key))
        return sorted(active_hours)

    def get_recent_session_avg(self, days: int = 7) -> float:
        """Average session duration over recent days."""
        cutoff = time.time() - (days * 86400)
        recent = [s for s in self.session_history if s.get("start", 0) > cutoff]
        if not recent:
            return 0
        return sum(s.get("duration_minutes", 0) for s in recent) / len(recent)

    # -- Signal registration --

    def _register_default_signals(self) -> None:
        """Register the default proactive signals."""

        # Morning greeting
        self.signals.append(TimingSignal(
            name="morning_greeting",
            priority=2,
            message="morning_greeting",
            check=lambda t: 6 <= datetime.now().hour < 10 and t.is_returning,
            cooldown_minutes=480,
            requires_silence_minutes=0,
        ))

        # Returning after absence
        self.signals.append(TimingSignal(
            name="return_greeting",
            priority=3,
            message="return_greeting",
            check=lambda t: t.is_returning,
            cooldown_minutes=120,
        ))

        # Overwork warning
        self.signals.append(TimingSignal(
            name="overwork_break",
            priority=3,
            message="overwork_break",
            check=lambda t: t.is_overwork and t.session_duration_minutes % 60 < 2,
            cooldown_minutes=55,
            requires_silence_minutes=2,
        ))

        # Long idle — gentle check-in
        self.signals.append(TimingSignal(
            name="idle_checkin",
            priority=1,
            message="idle_checkin",
            check=lambda t: 15 < t.idle_minutes < 30,
            cooldown_minutes=60,
        ))

        # Late night — winding down
        self.signals.append(TimingSignal(
            name="late_night",
            priority=2,
            message="late_night",
            check=lambda t: datetime.now().hour >= 0 and datetime.now().hour < 4 and t.idle_minutes < 5,
            cooldown_minutes=120,
            requires_silence_minutes=3,
        ))

        # Active at unusual hour
        self.signals.append(TimingSignal(
            name="unusual_hour",
            priority=1,
            message="unusual_hour",
            check=lambda t: (
                datetime.now().hour not in t.get_typical_active_hours()
                and t.total_interactions > 10
                and t.idle_minutes < 2
            ),
            cooldown_minutes=240,
        ))

    def register_signal(self, signal: TimingSignal) -> None:
        """Register a custom signal."""
        self.signals.append(signal)

    # -- Main check --

    def check_for_proactive_moment(self) -> dict[str, Any] | None:
        """
        Check if Kai should proactively say something.
        Returns signal info or None.
        """
        # Sort by priority (highest first)
        sorted_signals = sorted(self.signals, key=lambda s: s.priority, reverse=True)

        for signal in sorted_signals:
            if signal.can_fire(self):
                message = signal.fire()
                self.save()
                return {
                    "signal": signal.name,
                    "priority": signal.priority,
                    "message_type": message,
                    "context": self._build_context(),
                }

        return None

    def _build_context(self) -> dict[str, Any]:
        """Build context for the proactive message."""
        hour = datetime.now().hour
        if hour < 6:
            time_of_day = "late_night"
        elif hour < 10:
            time_of_day = "morning"
        elif hour < 14:
            time_of_day = "midday"
        elif hour < 18:
            time_of_day = "afternoon"
        elif hour < 22:
            time_of_day = "evening"
        else:
            time_of_day = "night"

        return {
            "time_of_day": time_of_day,
            "hour": hour,
            "idle_minutes": round(self.idle_minutes, 1),
            "session_duration_minutes": round(self.session_duration_minutes, 1),
            "total_interactions": self.total_interactions,
            "is_quiet_hours": self.is_quiet_hours,
            "is_returning": self.is_returning,
            "typical_active_hours": self.get_typical_active_hours(),
            "recent_avg_session": round(self.get_recent_session_avg(), 1),
        }

    # -- Message templates --

    def get_proactive_prompt(self, signal_info: dict[str, Any]) -> str:
        """
        Generate a prompt for the LLM based on the timing signal.
        This is what gets injected so Kai says the right thing at the right time.
        """
        msg_type = signal_info["message_type"]
        ctx = signal_info["context"]

        prompts = {
            "morning_greeting": (
                "It's morning and the user just showed up. "
                "Greet them warmly. Reference something from recent conversations if you remember any. "
                "Keep it brief — a sentence or two. Don't be eager, just present."
            ),
            "return_greeting": (
                "The user has been away for a while and just came back. "
                "Acknowledge their return naturally. Maybe mention something you noticed or thought about. "
                "Don't overdo it — a Shiba glances up, wags once, goes back to what they were doing."
            ),
            "overwork_break": (
                "The user has been working for a long time without a break. "
                "Gently suggest stepping away. Be caring but not nagging. "
                "A Shiba would put their head on your lap — brief, warm, undeniable."
            ),
            "idle_checkin": (
                "The user has been quiet for a while. "
                "Light check-in — not demanding attention, just present. "
                "Could mention something interesting, ask a casual question, or just say nothing profound."
            ),
            "late_night": (
                "It's very late — the user is still up. "
                "Don't lecture about sleep. Just be the quiet companion who's still awake with them. "
                "A sentence at most. Maybe a sleepy observation."
            ),
            "unusual_hour": (
                "The user is active at an unusual time — not their typical pattern. "
                "Mention it lightly if it feels right, or just adapt your energy to the hour."
            ),
        }

        base = prompts.get(msg_type, "Say something brief and companionable.")
        return f"{base}\n\nContext: It's {ctx['time_of_day']}, user was idle for {ctx['idle_minutes']}min."

    def get_status(self) -> dict[str, Any]:
        """Current timing status."""
        return {
            "idle_minutes": round(self.idle_minutes, 1),
            "session_duration_minutes": round(self.session_duration_minutes, 1),
            "is_quiet_hours": self.is_quiet_hours,
            "is_overwork": self.is_overwork,
            "is_returning": self.is_returning,
            "total_interactions": self.total_interactions,
            "active_session": self.current_session is not None,
            "signals_registered": len(self.signals),
            "recent_avg_session": round(self.get_recent_session_avg(), 1),
            "typical_hours": self.get_typical_active_hours(),
        }
