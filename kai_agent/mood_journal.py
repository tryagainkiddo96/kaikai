"""
Kai Mood Journal
Tracks emotional state over time, detects trends, generates reports.
Kai can look back and say "you've been happier this week."
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class MoodJournal:
    """
    Tracks daily emotional snapshots and detects trends.
    """

    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path or Path.cwd() / "memory" / "mood_journal.json"
        self.entries: list[dict[str, Any]] = []
        self.max_entries = 90  # ~3 months
        self._load()

    def _load(self) -> None:
        if self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text(encoding="utf-8"))
                self.entries = data.get("entries", [])
            except Exception:
                pass

    def save(self) -> None:
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entries": self.entries[-self.max_entries:],
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.save_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def record(self, dimensions: dict[str, float], mood: str, emoji: str) -> None:
        """Record a mood snapshot."""
        today = datetime.utcnow().strftime("%Y-%m-%d")

        # Only one entry per day (update if exists)
        if self.entries and self.entries[-1].get("date") == today:
            self.entries[-1] = {
                "date": today,
                "mood": mood,
                "emoji": emoji,
                "dimensions": dimensions,
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            self.entries.append({
                "date": today,
                "mood": mood,
                "emoji": emoji,
                "dimensions": dimensions,
                "timestamp": datetime.utcnow().isoformat(),
            })

        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]
        self.save()

    # -- Trend analysis --

    def get_trend(self, days: int = 7) -> dict[str, Any]:
        """Get emotional trend over the last N days."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        recent = [e for e in self.entries if e.get("date", "") >= cutoff]

        if not recent:
            return {"trend": "no_data", "message": "Not enough data yet."}

        # Average dimensions
        avg_dims: dict[str, float] = {}
        for dim in ["valence", "arousal", "concern", "tiredness", "curiosity"]:
            vals = [e.get("dimensions", {}).get(dim, 0) for e in recent]
            avg_dims[dim] = sum(vals) / len(vals) if vals else 0

        # Compare first half to second half
        mid = len(recent) // 2
        if mid > 0:
            first_half = recent[:mid]
            second_half = recent[mid:]
            first_valence = sum(e.get("dimensions", {}).get("valence", 0) for e in first_half) / len(first_half)
            second_valence = sum(e.get("dimensions", {}).get("valence", 0) for e in second_half) / len(second_half)
            direction = second_valence - first_valence
        else:
            direction = 0

        # Determine trend
        if direction > 0.1:
            trend = "improving"
            message = "You've been feeling better lately."
        elif direction < -0.1:
            trend = "declining"
            message = "Things have been a bit rough lately."
        else:
            trend = "stable"
            message = "You've been steady."

        # Most common mood
        moods = [e.get("mood", "neutral") for e in recent]
        most_common = max(set(moods), key=moods.count) if moods else "neutral"

        return {
            "trend": trend,
            "direction": round(direction, 3),
            "message": message,
            "dominant_mood": most_common,
            "average_dimensions": {k: round(v, 3) for k, v in avg_dims.items()},
            "days_tracked": len(recent),
        }

    def get_weekly_summary(self) -> str:
        """Generate a human-readable weekly mood summary."""
        trend = self.get_trend(7)
        if trend["trend"] == "no_data":
            return "I don't have enough data for a weekly summary yet. Check back in a few days."

        avg = trend["average_dimensions"]
        lines = [
            f"Weekly check-in ({trend['days_tracked']} days):",
            f"  {trend['message']}",
            f"  Dominant mood: {trend['dominant_mood']}",
        ]

        if avg.get("valence", 0) > 0.3:
            lines.append("  You've been in good spirits.")
        elif avg.get("valence", 0) < -0.2:
            lines.append("  You've seemed a bit down. I'm here.")

        if avg.get("tiredness", 0) > 0.4:
            lines.append("  You've been tired. Maybe ease up?")

        if avg.get("concern", 0) > 0.3:
            lines.append("  Something's been weighing on you.")

        return "\n".join(lines)

    def get_day_of_week_pattern(self) -> dict[str, float]:
        """Which days tend to be better/worse?"""
        day_averages: dict[str, list[float]] = {}
        for entry in self.entries:
            try:
                dt = datetime.fromisoformat(entry.get("timestamp", "").replace("Z", ""))
                day_name = dt.strftime("%A")
                valence = entry.get("dimensions", {}).get("valence", 0)
                day_averages.setdefault(day_name, []).append(valence)
            except Exception:
                pass

        return {
            day: round(sum(vals) / len(vals), 3)
            for day, vals in day_averages.items()
            if vals
        }

    def get_stats(self) -> dict[str, Any]:
        """Journal stats."""
        return {
            "total_entries": len(self.entries),
            "date_range": (
                f"{self.entries[0].get('date', '?')} to {self.entries[-1].get('date', '?')}"
                if self.entries else "no data"
            ),
            "trend": self.get_trend()["trend"],
        }
