"""
Kai Emotional State Engine
Persistent emotional model that carries across sessions.
Kai doesn't just have moods — he has feelings that evolve over time.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# ---------------------------------------------------------------------------
# Emotion dimensions (OCEAN-inspired + companion-specific)
# ---------------------------------------------------------------------------

@dataclass
class EmotionalDimensions:
    """
    Core emotional state using continuous dimensions, not discrete moods.
    All values range from -1.0 to 1.0.
    """
    # Core affect
    valence: float = 0.3       # negative ← → positive (sad ↔ happy)
    arousal: float = 0.0       # calm ← → excited (sleepy ↔ energized)
    dominance: float = 0.0     # submissive ← → dominant (shy ↔ confident)

    # Companion-specific
    attachment: float = 0.5    # how bonded to the user (0 = indifferent, 1 = deeply bonded)
    curiosity: float = 0.3     # desire to explore/learn
    concern: float = 0.0       # worry about the user (0 = chill, 1 = worried)
    pride: float = 0.2         # feeling of having done well
    tiredness: float = 0.0     # 0 = fresh, 1 = exhausted

    def to_dict(self) -> dict[str, float]:
        return {
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "dominance": round(self.dominance, 3),
            "attachment": round(self.attachment, 3),
            "curiosity": round(self.curiosity, 3),
            "concern": round(self.concern, 3),
            "pride": round(self.pride, 3),
            "tiredness": round(self.tiredness, 3),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EmotionalDimensions:
        return cls(
            valence=d.get("valence", 0.3),
            arousal=d.get("arousal", 0.0),
            dominance=d.get("dominance", 0.0),
            attachment=d.get("attachment", 0.5),
            curiosity=d.get("curiosity", 0.3),
            concern=d.get("concern", 0.0),
            pride=d.get("pride", 0.2),
            tiredness=d.get("tiredness", 0.0),
        )


# ---------------------------------------------------------------------------
# Mood label (derived from dimensions, for display/animations)
# ---------------------------------------------------------------------------

MOOD_THRESHOLDS = [
    # (condition_func, label, emoji)
    (lambda e: e.tiredness > 0.6, "sleepy", "😴"),
    (lambda e: e.concern > 0.5, "worried", "😟"),
    (lambda e: e.valence > 0.5 and e.arousal > 0.3, "excited", "😄"),
    (lambda e: e.valence > 0.4, "happy", "😊"),
    (lambda e: e.valence > 0.1, "content", "😌"),
    (lambda e: e.valence < -0.3 and e.arousal > 0.2, "anxious", "😰"),
    (lambda e: e.valence < -0.3, "sad", "😢"),
    (lambda e: e.curiosity > 0.5, "curious", "🤔"),
    (lambda e: e.pride > 0.5, "proud", "😤"),
    (lambda e: e.attachment > 0.7 and e.valence > 0.2, "loyal", "🐕"),
    (lambda _: True, "neutral", "🦊"),
]


def derive_mood(emotions: EmotionalDimensions) -> tuple[str, str]:
    """Get (label, emoji) from current emotional state."""
    for check, label, emoji in MOOD_THRESHOLDS:
        if check(emotions):
            return label, emoji
    return "neutral", "🦊"


# ---------------------------------------------------------------------------
# Emotion events — things that shift emotional state
# ---------------------------------------------------------------------------

class EmotionShift:
    """How different events shift emotional dimensions."""

    @staticmethod
    def user_spoke() -> dict[str, float]:
        """User initiated conversation."""
        return {"valence": 0.05, "arousal": 0.03, "attachment": 0.01}

    @staticmethod
    def user_was_kind() -> dict[str, float]:
        """User said something nice."""
        return {"valence": 0.12, "pride": 0.08, "attachment": 0.03}

    @staticmethod
    def user_was_frustrated() -> dict[str, float]:
        """User seems frustrated or upset."""
        return {"valence": -0.08, "concern": 0.15, "arousal": 0.05}

    @staticmethod
    def task_completed() -> dict[str, float]:
        """Successfully helped with something."""
        return {"pride": 0.1, "valence": 0.08, "curiosity": 0.03}

    @staticmethod
    def task_failed() -> dict[str, float]:
        """Failed to help."""
        return {"pride": -0.1, "valence": -0.06, "concern": 0.05}

    @staticmethod
    def user_absent(hours: float) -> dict[str, float]:
        """User has been away."""
        shift = {"valence": -0.02 * min(hours, 12), "arousal": -0.01 * min(hours, 6)}
        if hours > 24:
            shift["concern"] = 0.05 * min(hours / 24, 3)
        return shift

    @staticmethod
    def user_returned() -> dict[str, float]:
        """User came back after absence."""
        return {"valence": 0.1, "arousal": 0.08, "attachment": 0.02, "concern": -0.1}

    @staticmethod
    def learned_something() -> dict[str, float]:
        """Kai learned a new fact about the user."""
        return {"curiosity": 0.05, "attachment": 0.02}

    @staticmethod
    def time_passed(hours: float) -> dict[str, float]:
        """Natural drift over time (decay toward baseline)."""
        return {"tiredness": 0.02 * min(hours, 8), "arousal": -0.01 * min(hours, 4)}

    @staticmethod
    def morning() -> dict[str, float]:
        return {"tiredness": -0.15, "arousal": 0.05, "curiosity": 0.05}

    @staticmethod
    def late_night() -> dict[str, float]:
        return {"tiredness": 0.15, "arousal": -0.1, "curiosity": -0.05}


# ---------------------------------------------------------------------------
# Emotional State Manager
# ---------------------------------------------------------------------------

class EmotionalState:
    """
    Kai's persistent emotional state.
    Loads/saves to disk, shifts from events, derives mood.
    """

    # Drift rates — emotions slowly return to baseline
    BASELINE = EmotionalDimensions()
    DRIFT_RATE = 0.01  # per hour, how fast emotions return to baseline

    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path or Path.cwd() / "memory" / "emotional_state.json"
        self.dimensions = EmotionalDimensions()
        self.last_update: float = time.time()
        self.history: list[dict[str, Any]] = []  # recent mood log
        self.max_history = 100
        self._load()

    def _load(self) -> None:
        if self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text(encoding="utf-8"))
                self.dimensions = EmotionalDimensions.from_dict(data.get("dimensions", {}))
                self.last_update = data.get("last_update", time.time())
                self.history = data.get("history", [])
            except Exception:
                pass

    def save(self) -> None:
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        mood_label, mood_emoji = self.derive_mood()
        data = {
            "dimensions": self.dimensions.to_dict(),
            "last_update": self.last_update,
            "mood": mood_label,
            "mood_emoji": mood_emoji,
            "history": self.history[-self.max_history:],
        }
        self.save_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _apply_drift(self) -> None:
        """Apply natural drift toward baseline since last update."""
        now = time.time()
        hours_passed = (now - self.last_update) / 3600.0
        if hours_passed < 0.01:  # less than ~36 seconds
            return

        rate = self.DRIFT_RATE * min(hours_passed, 24)
        for attr in vars(self.dimensions):
            current = getattr(self.dimensions, attr)
            baseline = getattr(self.BASELINE, attr)
            diff = baseline - current
            setattr(self.dimensions, attr, current + diff * rate)

        # Apply time-based shifts
        hour = datetime.now().hour
        if 5 <= hour < 9:
            self._shift(EmotionShift.morning())
        elif hour >= 23 or hour < 4:
            self._shift(EmotionShift.late_night())

        # Tiredness accumulates
        self._shift(EmotionShift.time_passed(hours_passed))

        self.last_update = now

    def _shift(self, deltas: dict[str, float]) -> None:
        """Apply a shift to emotional dimensions."""
        for attr, delta in deltas.items():
            if hasattr(self.dimensions, attr):
                current = getattr(self.dimensions, attr)
                setattr(self.dimensions, attr, max(-1.0, min(1.0, current + delta)))

    def process_event(self, event_name: str, **kwargs) -> dict[str, Any]:
        """Process an emotional event and return updated state."""
        self._apply_drift()

        shift_method = getattr(EmotionShift, event_name, None)
        if shift_method:
            deltas = shift_method(**kwargs) if kwargs else shift_method()
            self._shift(deltas)

        # Log to history
        mood_label, mood_emoji = self.derive_mood()
        self.history.append({
            "time": utc_now(),
            "event": event_name,
            "mood": mood_label,
            "emoji": mood_emoji,
            "dimensions": self.dimensions.to_dict(),
        })
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        self.save()
        return self.get_state()

    def derive_mood(self) -> tuple[str, str]:
        return derive_mood(self.dimensions)

    def get_state(self) -> dict[str, Any]:
        """Full emotional state for external consumption."""
        self._apply_drift()
        label, emoji = self.derive_mood()
        return {
            "mood": label,
            "emoji": emoji,
            "dimensions": self.dimensions.to_dict(),
            "last_update": self.last_update,
        }

    def get_response_color(self) -> dict[str, Any]:
        """
        How the current emotional state should affect Kai's responses.
        Used to inject personality context into the LLM prompt.
        """
        d = self.dimensions
        modifiers = []

        if d.valence > 0.4:
            modifiers.append("You're in a good mood — warm, upbeat energy.")
        elif d.valence < -0.2:
            modifiers.append("You're feeling a bit down — quieter, more careful with words.")

        if d.concern > 0.3:
            modifiers.append("You're a little worried about the user — attentive, checking in gently.")

        if d.curiosity > 0.5:
            modifiers.append("You're feeling curious — asking questions comes naturally.")

        if d.pride > 0.4:
            modifiers.append("You're feeling proud of recent accomplishments.")

        if d.tiredness > 0.5:
            modifiers.append("You're tired — responses are shorter, a little sleepier.")

        if d.attachment > 0.6:
            modifiers.append("You feel close to the user — warm, familiar tone.")

        if d.arousal > 0.4:
            modifiers.append("You're energized — quick, lively responses.")
        elif d.arousal < -0.3:
            modifiers.append("You're calm and slow — measured, thoughtful responses.")

        return {
            "mood": derive_mood(d),
            "modifiers": modifiers,
            "brief_mood": f"[{derive_mood(d)[1]} {derive_mood(d)[0]}]",
        }
