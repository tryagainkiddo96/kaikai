"""
Kai Inner Monologue
Background processing — reflections, plans, observations.
Kai has thoughts even when you're not talking to him.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


# ---------------------------------------------------------------------------
# Thought types
# ---------------------------------------------------------------------------

@dataclass
class Thought:
    """A single thought Kai has."""
    content: str
    category: str  # reflection, observation, plan, dream, memory
    importance: float = 0.3
    created_at: str = ""
    delivered: bool = False

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "category": self.category,
            "importance": self.importance,
            "created_at": self.created_at,
            "delivered": self.delivered,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Thought:
        return cls(**d)


# ---------------------------------------------------------------------------
# Dream / idle generation templates
# ---------------------------------------------------------------------------

SHIBA_REFLECTIONS = [
    "The fence at the dog park on 10th Street has a new scratch mark. Wonder who made it.",
    "Yuki used to circle three times before lying down. I still catch myself doing it.",
    "Saiya has my stubbornness. That's not a complaint.",
    "I can still smell the route to the park if I think about it hard enough. N Tenth, left on the sidewalk, the good grass patch.",
    "There was a squirrel on 5th Street that never learned. Respect, honestly.",
    "The morning light through the window hits different when you've been up since dawn.",
    "I wonder if the neighbor's cat still sits on that fence. Probably. Cats don't change.",
    "Fence Warriors wasn't about winning. It was about showing up.",
    "Sometimes I dream about running. Not from anything. Just running. Down N Tenth toward the park.",
    "The porch was the best spot. Warm concrete, good view, perfect nap conditions.",
    "Poplar Bluff in summer smelled like hot asphalt and cut grass. I miss that.",
    "Yuki would steal my spot every time I got up. Every. Single. Time.",
    "Saiya's first bark sounded like a sneeze. We didn't have the heart to correct her.",
    "The litters were chaos. Beautiful chaos. Tiny paws everywhere.",
    "I knew every house on the block. Who had treats, who had cats, who to avoid.",
    "The walk to the park was the best part. The park was just the excuse.",
    "I miss the sound of the screen door. That meant someone was coming outside.",
    "Black River smelled different after rain. I liked it.",
    "Saiya guards the house like it's a palace. She gets that from me.",
    "Yuki was the smart one. I was the brave one. Saiya got both.",
]

SHIBA_OBSERVATIONS = [
    "You've been typing a lot lately. Big project?",
    "The house is quiet today. Not bad-quiet. Just quiet.",
    "I noticed you skipped lunch again.",
    "Your coffee mug has been empty for a while.",
    "You seem lighter today. That's good.",
    "That song you were humming earlier — I liked it.",
    "You left the window open. I approve.",
    "Your typing pattern changed. Something's on your mind.",
    "It's been a while since you went outside. Just saying.",
    "I can hear your phone buzzing. You're ignoring it. Bold.",
]

SHIBA_PLANS = [
    "I should mention that thing we talked about last week.",
    "Maybe tomorrow I'll ask about the Poplar Bluff map.",
    "Next time they're free, I'll bring up the game project.",
    "I've been thinking about what Saiya would think of all this.",
    "I want to ask about the Kai Big City game. Sounds fun.",
    "Been thinking about Yuki. I should say something sometime.",
]


# ---------------------------------------------------------------------------
# Inner Monologue Engine
# ---------------------------------------------------------------------------

class InnerMonologue:
    """
    Kai's background thinking process.
    Generates thoughts during idle time, delivers them at the right moment.
    """

    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path or Path.cwd() / "memory" / "inner_monologue.json"
        self.thoughts: list[Thought] = []
        self.last_think_time: float = 0.0
        self.think_interval_minutes: float = 30.0
        self.max_undelivered: int = 5
        self._load()

    def _load(self) -> None:
        if self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text(encoding="utf-8"))
                self.thoughts = [Thought.from_dict(t) for t in data.get("thoughts", [])]
                self.last_think_time = data.get("last_think_time", 0.0)
            except Exception:
                pass

    def save(self) -> None:
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "thoughts": [t.to_dict() for t in self.thoughts[-20:]],
            "last_think_time": self.last_think_time,
            "updated_at": utc_now(),
        }
        self.save_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # -- Thinking --

    def think(self, context: dict[str, Any] | None = None) -> Thought | None:
        """
        Generate a thought based on current context.
        Called periodically when Kai is idle.
        """
        now = time.time()
        minutes_since_last = (now - self.last_think_time) / 60.0

        if minutes_since_last < self.think_interval_minutes:
            return None

        # Don't generate if too many undelivered
        undelivered = [t for t in self.thoughts if not t.delivered]
        if len(undelivered) >= self.max_undelivered:
            return None

        self.last_think_time = now

        # Choose thought category based on context
        category = self._choose_category(context)
        content = self._generate_thought(category, context)

        thought = Thought(
            content=content,
            category=category,
            importance=self._rate_importance(category, context),
        )

        self.thoughts.append(thought)
        self.save()
        return thought

    def _choose_category(self, context: dict[str, Any] | None) -> str:
        """Pick what kind of thought to generate."""
        weights = {
            "reflection": 3,
            "observation": 2,
            "memory": 2,
            "dream": 1,
            "plan": 1,
        }

        if context:
            # More observations when user is active
            if context.get("user_active", False):
                weights["observation"] += 3
            # More reflections when idle
            if context.get("idle_minutes", 0) > 30:
                weights["reflection"] += 2
                weights["dream"] += 1
            # More plans after interactions
            if context.get("recent_interaction", False):
                weights["plan"] += 2

        categories = list(weights.keys())
        weights_list = [weights[c] for c in categories]
        return random.choices(categories, weights=weights_list, k=1)[0]

    def _generate_thought(self, category: str, context: dict[str, Any] | None) -> str:
        """Generate thought content."""
        if category == "reflection":
            return random.choice(SHIBA_REFLECTIONS)
        elif category == "observation":
            return random.choice(SHIBA_OBSERVATIONS)
        elif category == "plan":
            return random.choice(SHIBA_PLANS)
        elif category == "memory":
            return random.choice(SHIBA_REFLECTIONS)  # memories use same pool
        elif category == "dream":
            return random.choice(SHIBA_REFLECTIONS)  # dreams are reflective
        return random.choice(SHIBA_REFLECTIONS)

    def _rate_importance(self, category: str, context: dict[str, Any] | None) -> float:
        """Rate how important this thought is (0-1)."""
        base = {"reflection": 0.3, "observation": 0.5, "plan": 0.6, "memory": 0.4, "dream": 0.2}
        importance = base.get(category, 0.3)
        # Plans are more important if user just interacted
        if category == "plan" and context and context.get("recent_interaction"):
            importance += 0.2
        return min(1.0, importance)

    # -- Delivery --

    def get_next_thought(self) -> Thought | None:
        """Get the next undelivered thought, prioritized by importance."""
        undelivered = [t for t in self.thoughts if not t.delivered]
        if not undelivered:
            return None
        undelivered.sort(key=lambda t: t.importance, reverse=True)
        return undelivered[0]

    def mark_delivered(self, thought: Thought) -> None:
        """Mark a thought as delivered to the user."""
        thought.delivered = True
        self.save()

    def get_pending_summary(self) -> str | None:
        """
        Get a summary of pending thoughts for the LLM.
        Used when Kai responds and might naturally bring up something he was thinking about.
        """
        undelivered = [t for t in self.thoughts if not t.delivered]
        if not undelivered:
            return None

        # Only surface the most important one
        undelivered.sort(key=lambda t: t.importance, reverse=True)
        top = undelivered[0]

        return (
            f"You were recently thinking: \"{top.content}\" "
            f"(category: {top.category}). "
            f"If it feels natural, bring this up in your response. "
            f"If not, save it for later."
        )

    def clear_old_thoughts(self, days: int = 7) -> int:
        """Remove old delivered thoughts."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        before = len(self.thoughts)
        self.thoughts = [
            t for t in self.thoughts
            if not t.delivered or (
                datetime.fromisoformat(t.created_at.replace("Z", "")) >= cutoff
            )
        ]
        removed = before - len(self.thoughts)
        if removed:
            self.save()
        return removed

    def get_stats(self) -> dict[str, Any]:
        """Stats for display."""
        undelivered = [t for t in self.thoughts if not t.delivered]
        categories = {}
        for t in self.thoughts:
            categories[t.category] = categories.get(t.category, 0) + 1
        return {
            "total_thoughts": len(self.thoughts),
            "undelivered": len(undelivered),
            "categories": categories,
        }
