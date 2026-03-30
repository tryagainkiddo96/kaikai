"""
Kai Relationship Model
Learns who the user is over time — preferences, style, interests, pet peeves.
The difference between "Hi" and "Hey, how's that project going?"
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# ---------------------------------------------------------------------------
# User profile dimensions
# ---------------------------------------------------------------------------

@dataclass
class UserPreferences:
    """Things Kai learns about the user over time."""
    # Communication style (0=formal, 1=casual)
    formality: float = 0.3

    # Response length preference (0=brief, 1=detailed)
    verbosity: float = 0.4

    # Humor tolerance (0=serious, 1=loves jokes)
    humor: float = 0.6

    # Proactivity preference (0=only when asked, 1=talk whenever)
    proactivity: float = 0.5

    # Topics of interest (learned from conversations)
    interests: list[str] = field(default_factory=list)

    # Topics to avoid
    avoided_topics: list[str] = field(default_factory=list)

    # Preferred name/nickname
    preferred_name: str = ""

    # Time preferences
    morning_person: bool = False
    night_owl: bool = False

    # Project interests
    active_projects: list[str] = field(default_factory=list)

    # Communication patterns
    uses_emoji: bool = False
    uses_slang: bool = False
    average_message_length: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "formality": round(self.formality, 3),
            "verbosity": round(self.verbosity, 3),
            "humor": round(self.humor, 3),
            "proactivity": round(self.proactivity, 3),
            "interests": self.interests[-20:],  # Keep recent
            "avoided_topics": self.avoided_topics,
            "preferred_name": self.preferred_name,
            "morning_person": self.morning_person,
            "night_owl": self.night_owl,
            "active_projects": self.active_projects[-10:],
            "uses_emoji": self.uses_emoji,
            "uses_slang": self.uses_slang,
            "average_message_length": round(self.average_message_length, 1),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> UserPreferences:
        return cls(
            formality=d.get("formality", 0.3),
            verbosity=d.get("verbosity", 0.4),
            humor=d.get("humor", 0.6),
            proactivity=d.get("proactivity", 0.5),
            interests=d.get("interests", []),
            avoided_topics=d.get("avoided_topics", []),
            preferred_name=d.get("preferred_name", ""),
            morning_person=d.get("morning_person", False),
            night_owl=d.get("night_owl", False),
            active_projects=d.get("active_projects", []),
            uses_emoji=d.get("uses_emoji", False),
            uses_slang=d.get("uses_slang", False),
            average_message_length=d.get("average_message_length", 0.0),
        )


# ---------------------------------------------------------------------------
# Interaction analysis
# ---------------------------------------------------------------------------

def analyze_message(text: str) -> dict[str, Any]:
    """Analyze a user message for style signals."""
    words = text.split()
    word_count = len(words)

    # Emoji detection
    emoji_count = sum(1 for c in text if ord(c) > 127000)
    uses_emoji = emoji_count > 0

    # Formality signals
    formal_signals = ["please", "thank you", "could you", "would you", "appreciate"]
    casual_signals = ["hey", "lol", "gonna", "wanna", "nah", "yeah", "sup", "bruh"]
    formal = sum(1 for s in formal_signals if s in text.lower())
    casual = sum(1 for s in casual_signals if s in text.lower())

    # Slang detection
    slang_words = ["lol", "lmao", "bruh", "nah", "yeet", "vibe", "lowkey", "fr", "ngl"]
    uses_slang = any(w in text.lower() for w in slang_words)

    # Question detection
    is_question = "?" in text

    # Emotional signals
    frustration = any(w in text.lower() for w in ["broken", "doesn't work", "wtf", "stupid", "hate this", "ugh"])
    excitement = any(w in text.lower() for w in ["awesome", "amazing", "love this", "great", "perfect", "sick"])
    stress = any(w in text.lower() for w in ["deadline", "stressed", "rushed", "urgent", "asap", "hurry"])

    return {
        "word_count": word_count,
        "uses_emoji": uses_emoji,
        "uses_slang": uses_slang,
        "formal_score": formal,
        "casual_score": casual,
        "is_question": is_question,
        "frustration": frustration,
        "excitement": excitement,
        "stress": stress,
    }


# ---------------------------------------------------------------------------
# Relationship Model
# ---------------------------------------------------------------------------

class RelationshipModel:
    """
    Tracks and evolves the relationship between Kai and the user.
    Learns preferences, adapts communication style, remembers shared history.
    """

    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path or Path.cwd() / "memory" / "relationship.json"
        self.prefs = UserPreferences()
        self.interaction_count: int = 0
        self.first_interaction: str = ""
        self.last_interaction: str = ""
        self.shared_experiences: list[dict[str, Any]] = []
        self.inside_jokes: list[str] = []
        self.max_experiences = 50
        self._message_lengths: list[float] = []
        self._load()

    def _load(self) -> None:
        if self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text(encoding="utf-8"))
                self.prefs = UserPreferences.from_dict(data.get("preferences", {}))
                self.interaction_count = data.get("interaction_count", 0)
                self.first_interaction = data.get("first_interaction", "")
                self.last_interaction = data.get("last_interaction", "")
                self.shared_experiences = data.get("shared_experiences", [])
                self.inside_jokes = data.get("inside_jokes", [])
            except Exception:
                pass

    def save(self) -> None:
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "preferences": self.prefs.to_dict(),
            "interaction_count": self.interaction_count,
            "first_interaction": self.first_interaction,
            "last_interaction": self.last_interaction,
            "shared_experiences": self.shared_experiences[-self.max_experiences:],
            "inside_jokes": self.inside_jokes[-20:],
            "updated_at": utc_now(),
        }
        self.save_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # -- Learning from interactions --

    def process_message(self, text: str) -> None:
        """Learn from a user message."""
        now = utc_now()
        self.interaction_count += 1
        self.last_interaction = now
        if not self.first_interaction:
            self.first_interaction = now

        analysis = analyze_message(text)

        # Update message length tracking
        self._message_lengths.append(analysis["word_count"])
        if len(self._message_lengths) > 100:
            self._message_lengths = self._message_lengths[-100:]
        if self._message_lengths:
            self.prefs.average_message_length = sum(self._message_lengths) / len(self._message_lengths)

        # Update formality preference (exponential moving average)
        if analysis["formal_score"] > 0:
            self.prefs.formality = self.prefs.formality * 0.9 + 0.7 * 0.1
        elif analysis["casual_score"] > 0:
            self.prefs.formality = self.prefs.formality * 0.9 + 0.1 * 0.1

        # Update emoji preference
        if analysis["uses_emoji"]:
            self.prefs.uses_emoji = True

        # Update slang preference
        if analysis["uses_slang"]:
            self.prefs.uses_slang = True

        # Update verbosity preference based on message length
        if analysis["word_count"] > 30:
            self.prefs.verbosity = min(1.0, self.prefs.verbosity + 0.01)
        elif analysis["word_count"] < 5:
            self.prefs.verbosity = max(0.0, self.prefs.verbosity - 0.01)

        # Track time patterns
        hour = datetime.now().hour
        if 5 <= hour < 9:
            self.prefs.morning_person = True
        if hour >= 22 or hour < 3:
            self.prefs.night_owl = True

        # Extract interests from questions and excitement
        if analysis["is_question"] or analysis["excitement"]:
            # Simple keyword extraction for interests
            interest_words = [w.lower().strip("?!.,") for w in text.split() if len(w) > 4]
            for word in interest_words[:3]:
                if word not in self.prefs.interests and word not in ("about", "should", "could", "would", "think", "maybe", "there"):
                    self.prefs.interests.append(word)

        # Auto-detect name
        import re
        name_match = re.search(r"(?:my name is|call me|i'm|im|iam)\s+([A-Za-z]{2,20})", text, re.IGNORECASE)
        if name_match and not self.prefs.preferred_name:
            name = name_match.group(1).strip()
            stopwords = {"just", "really", "going", "trying", "looking", "feeling", "not", "still", "here",
                         "fine", "good", "okay", "happy", "sad", "tired", "busy", "ready", "back", "done"}
            if name.lower() not in stopwords:
                self.prefs.preferred_name = name.capitalize()
                self.save()

        self.save()

    # -- Relationship context --

    def get_communication_style(self) -> dict[str, Any]:
        """How Kai should communicate based on learned preferences."""
        style = {
            "tone": "casual" if self.prefs.formality < 0.4 else "balanced" if self.prefs.formality < 0.7 else "formal",
            "length": "brief" if self.prefs.verbosity < 0.3 else "moderate" if self.prefs.verbosity < 0.7 else "detailed",
            "humor": "light" if self.prefs.humor < 0.3 else "moderate" if self.prefs.humor < 0.7 else "playful",
            "proactivity": "low" if self.prefs.proactivity < 0.3 else "moderate" if self.prefs.proactivity < 0.7 else "high",
        }

        # Add specific guidance
        guidance = []
        if style["tone"] == "casual":
            guidance.append("Keep it casual. Skip the pleasantries.")
        if style["length"] == "brief":
            guidance.append("Short responses. The user prefers quick answers.")
        if self.prefs.uses_slang:
            guidance.append("User uses slang — match their energy lightly.")
        if self.prefs.uses_emoji:
            guidance.append("User uses emoji — you can too, sparingly.")

        style["guidance"] = " ".join(guidance)
        return style

    def get_relationship_context(self) -> str:
        """Build a context string for the LLM prompt."""
        parts = []

        if self.interaction_count > 10:
            parts.append(f"You've talked to this user {self.interaction_count} times.")

        if self.prefs.preferred_name:
            parts.append(f"Their name is {self.prefs.preferred_name}.")

        if self.prefs.active_projects:
            projects = ", ".join(self.prefs.active_projects[-3:])
            parts.append(f"Recent projects: {projects}.")

        if self.prefs.interests:
            interests = ", ".join(self.prefs.interests[-5:])
            parts.append(f"Interests: {interests}.")

        style = self.get_communication_style()
        if style["guidance"]:
            parts.append(style["guidance"])

        if self.inside_jokes:
            parts.append(f"Inside joke: \"{self.inside_jokes[-1]}\"")

        if self.prefs.morning_person and not self.prefs.night_owl:
            parts.append("User is a morning person.")
        elif self.prefs.night_owl:
            parts.append("User tends to be up late.")

        return "\n".join(parts) if parts else ""

    # -- Shared experiences --

    def add_experience(self, description: str, emotional_tag: str = "") -> None:
        """Record a shared experience."""
        self.shared_experiences.append({
            "description": description,
            "emotional_tag": emotional_tag,
            "timestamp": utc_now(),
        })
        if len(self.shared_experiences) > self.max_experiences:
            self.shared_experiences = self.shared_experiences[-self.max_experiences:]
        self.save()

    def add_inside_joke(self, joke: str) -> None:
        """Remember an inside joke."""
        if joke not in self.inside_jokes:
            self.inside_jokes.append(joke)
            self.save()

    def set_name(self, name: str) -> None:
        """Learn the user's name."""
        self.prefs.preferred_name = name
        self.save()

    def add_project(self, project: str) -> None:
        """Track an active project."""
        if project not in self.prefs.active_projects:
            self.prefs.active_projects.append(project)
            self.save()

    # -- Stats --

    def get_stats(self) -> dict[str, Any]:
        """Relationship stats."""
        days_known = 0
        if self.first_interaction:
            try:
                first = datetime.fromisoformat(self.first_interaction.replace("Z", ""))
                days_known = (datetime.utcnow() - first).days
            except Exception:
                pass

        return {
            "interactions": self.interaction_count,
            "days_known": days_known,
            "interests": len(self.prefs.interests),
            "projects": len(self.prefs.active_projects),
            "experiences": len(self.shared_experiences),
            "inside_jokes": len(self.inside_jokes),
            "style": self.get_communication_style()["tone"],
        }
