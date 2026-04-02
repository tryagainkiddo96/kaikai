"""
Kai Semantic Memory
Extracts, stores, and retrieves key facts from conversations.
Kai remembers what matters — not everything, just the important stuff.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from kai_agent.time_utils import utc_now


# ---------------------------------------------------------------------------
# Memory fact
# ---------------------------------------------------------------------------

@dataclass
class MemoryFact:
    """A single remembered fact about the user or the world."""
    fact: str
    context: str = ""  # where/how Kai learned this
    category: str = "general"  # general, preference, project, personal, technical, emotional
    importance: float = 0.5  # 0 = trivial, 1 = critical
    emotional_tag: str = ""  # happy, sad, frustrated, excited, neutral
    created_at: str = ""
    last_accessed: str = ""
    access_count: int = 0
    source: str = "conversation"  # conversation, observation, explicit

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = utc_now()

    def touch(self) -> None:
        """Mark as accessed."""
        self.last_accessed = utc_now()
        self.access_count += 1

    @property
    def age_days(self) -> float:
        try:
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return max(0, (now - created).total_seconds() / 86400)
        except Exception:
            return 0

    @property
    def relevance_score(self) -> float:
        """How relevant is this fact right now? Combines importance, recency, frequency."""
        recency = max(0, 1.0 - (self.age_days / 90))  # decays over 90 days
        frequency = min(1.0, self.access_count / 10)  # maxes at 10 accesses
        return (self.importance * 0.5) + (recency * 0.3) + (frequency * 0.2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact": self.fact,
            "context": self.context,
            "category": self.category,
            "importance": self.importance,
            "emotional_tag": self.emotional_tag,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MemoryFact:
        return cls(
            fact=d["fact"],
            context=d.get("context", ""),
            category=d.get("category", "general"),
            importance=d.get("importance", 0.5),
            emotional_tag=d.get("emotional_tag", ""),
            created_at=d.get("created_at", ""),
            last_accessed=d.get("last_accessed", ""),
            access_count=d.get("access_count", 0),
            source=d.get("source", "conversation"),
        )


# ---------------------------------------------------------------------------
# Fact extraction patterns (rule-based, no LLM needed)
# ---------------------------------------------------------------------------

EXTRACTION_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    # Preferences
    (re.compile(r"i (?:like|love|enjoy|prefer|really like) (.+?)(?:\.|$)", re.I), "preference", 0.7),
    (re.compile(r"i (?:hate|dislike|can't stand|don't like) (.+?)(?:\.|$)", re.I), "preference", 0.7),
    (re.compile(r"my favorite (.+?) (?:is|are) (.+?)(?:\.|$)", re.I), "preference", 0.8),

    # Projects
    (re.compile(r"i(?:'m| am) (?:working on|building|making|creating) (.+?)(?:\.|$)", re.I), "project", 0.8),
    (re.compile(r"(?:my|the) (.+?) (?:project|app|game|tool|website) (.+?)(?:\.|$)", re.I), "project", 0.7),

    # Personal info
    (re.compile(r"my name is (.+?)(?:\.|$)", re.I), "personal", 0.9),
    (re.compile(r"i live in (.+?)(?:\.|$)", re.I), "personal", 0.8),
    (re.compile(r"i(?:'m| am) from (.+?)(?:\.|$)", re.I), "personal", 0.8),
    (re.compile(r"my (?:dog|cat|pet) (?:is named?|called) (.+?)(?:\.|$)", re.I), "personal", 0.9),
    (re.compile(r"i work (?:at|for|as) (.+?)(?:\.|$)", re.I), "personal", 0.7),

    # Technical
    (re.compile(r"i (?:use|run|have installed) (.+?)(?:\.|$)", re.I), "technical", 0.5),
    (re.compile(r"(?:my|the) (?:server|machine|computer) (?:is|runs|has) (.+?)(?:\.|$)", re.I), "technical", 0.6),

    # Emotional
    (re.compile(r"i(?:'m| am) (?:feeling |really )?(sad|happy|stressed|tired|excited|worried|frustrated|angry|bored|anxious)", re.I), "emotional", 0.6),
    (re.compile(r"(?:this is|that was) (?:amazing|awesome|terrible|awful|great|horrible|beautiful|stressful)", re.I), "emotional", 0.5),

    # Plans
    (re.compile(r"i(?:'m going to| want to| plan to| need to| should) (.+?)(?:\.|$)", re.I), "plan", 0.6),
    (re.compile(r"(?:tomorrow|next week|this weekend) i(?:'m| am| will) (.+?)(?:\.|$)", re.I), "plan", 0.5),

    # Relationships
    (re.compile(r"my (?:friend|partner|wife|husband|mom|dad|brother|sister|son|daughter) (.+?)(?:\.|$)", re.I), "personal", 0.7),
]


def extract_facts(text: str, context: str = "") -> list[MemoryFact]:
    """
    Extract facts from a message using pattern matching.
    Fast, no LLM required. Good enough for 80% of cases.
    """
    facts: list[MemoryFact] = []

    for pattern, category, importance in EXTRACTION_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            if isinstance(match, tuple):
                fact_text = " ".join(m.strip() for m in match if m.strip())
            else:
                fact_text = match.strip()

            if len(fact_text) < 3 or len(fact_text) > 200:
                continue

            # Build readable fact
            if category == "preference":
                readable = f"User {fact_text}"
            elif category == "project":
                readable = f"User is working on: {fact_text}"
            elif category == "emotional":
                readable = f"User was feeling: {fact_text}"
            elif category == "plan":
                readable = f"User plans to: {fact_text}"
            else:
                readable = fact_text

            facts.append(MemoryFact(
                fact=readable,
                context=context,
                category=category,
                importance=importance,
                source="conversation",
            ))

    return facts


# ---------------------------------------------------------------------------
# Semantic Memory Store
# ---------------------------------------------------------------------------

class SemanticMemory:
    """
    Kai's long-term semantic memory.
    Stores facts, retrieves relevant ones, manages lifecycle.
    """

    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path or Path.cwd() / "memory" / "semantic_memory.json"
        self.facts: list[MemoryFact] = []
        self.max_facts = 500
        self._load()

    def _load(self) -> None:
        if self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text(encoding="utf-8"))
                self.facts = [MemoryFact.from_dict(f) for f in data.get("facts", [])]
            except Exception:
                self.facts = []

    def save(self) -> None:
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "facts": [f.to_dict() for f in self.facts],
            "count": len(self.facts),
            "updated_at": utc_now(),
        }
        self.save_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # -- Store --

    def remember(self, fact: str, category: str = "general",
                 importance: float = 0.5, context: str = "",
                 emotional_tag: str = "", source: str = "explicit") -> MemoryFact:
        """Explicitly remember something."""
        # Check for duplicates
        for existing in self.facts:
            if existing.fact.lower() == fact.lower():
                existing.importance = max(existing.importance, importance)
                existing.touch()
                self.save()
                return existing

        mf = MemoryFact(
            fact=fact,
            context=context,
            category=category,
            importance=importance,
            emotional_tag=emotional_tag,
            source=source,
        )
        self.facts.append(mf)
        self._enforce_limit()
        self.save()
        return mf

    def learn_from_conversation(self, user_message: str, assistant_response: str = "") -> list[MemoryFact]:
        """Extract and store facts from a conversation turn."""
        extracted = extract_facts(user_message, context=user_message[:100])
        stored = []
        for fact in extracted:
            # Check for duplicates before storing
            is_dup = any(
                self._similar(f.fact, fact.fact) for f in self.facts
            )
            if not is_dup:
                self.facts.append(fact)
                stored.append(fact)

        if stored:
            self._enforce_limit()
            self.save()

        return stored

    # -- Retrieve --

    def recall(self, query: str, limit: int = 5, category: str | None = None) -> list[MemoryFact]:
        """
        Recall facts relevant to a query.
        Uses simple keyword matching — fast, no embeddings needed.
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored: list[tuple[float, MemoryFact]] = []
        for fact in self.facts:
            if category and fact.category != category:
                continue

            fact_lower = fact.fact.lower()
            fact_words = set(fact_lower.split())

            # Keyword overlap score
            overlap = len(query_words & fact_words)
            # Check if any query word appears in the fact
            substring_match = any(w in fact_lower for w in query_words if len(w) > 3)

            if overlap > 0 or substring_match:
                score = (overlap * 0.4) + (1.0 if substring_match else 0) + fact.relevance_score
                scored.append((score, fact))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for _, fact in scored[:limit]:
            fact.touch()
            results.append(fact)

        if results:
            self.save()

        return results

    def get_all_by_category(self, category: str) -> list[MemoryFact]:
        return [f for f in self.facts if f.category == category]

    def get_recent(self, days: int = 7, limit: int = 10) -> list[MemoryFact]:
        """Get recently added facts."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = []
        for fact in self.facts:
            try:
                created = datetime.fromisoformat(fact.created_at.replace("Z", ""))
                if created >= cutoff:
                    recent.append(fact)
            except Exception:
                pass
        recent.sort(key=lambda f: f.created_at, reverse=True)
        return recent[:limit]

    def get_important(self, threshold: float = 0.7) -> list[MemoryFact]:
        return [f for f in self.facts if f.importance >= threshold]

    # -- Context injection --

    def build_context_for_prompt(self, current_message: str, max_facts: int = 8) -> str:
        """
        Build a context string of relevant memories to inject into the LLM prompt.
        This is how Kai "remembers" during conversations.
        """
        relevant = self.recall(current_message, limit=max_facts)
        if not relevant:
            return ""

        lines = ["Things you remember about the user:"]
        for fact in relevant:
            age = fact.age_days
            if age < 1:
                time_note = "today"
            elif age < 2:
                time_note = "yesterday"
            elif age < 7:
                time_note = f"{int(age)} days ago"
            else:
                time_note = f"{int(age)} days ago"
            lines.append(f"- {fact.fact} ({time_note})")

        return "\n".join(lines)

    # -- Maintenance --

    def _enforce_limit(self) -> None:
        """Keep only the most relevant facts if over limit."""
        if len(self.facts) <= self.max_facts:
            return
        # Sort by relevance, keep top N
        self.facts.sort(key=lambda f: f.relevance_score, reverse=True)
        self.facts = self.facts[:self.max_facts]

    def _similar(self, a: str, b: str) -> bool:
        """Simple similarity check."""
        a_lower = a.lower().strip()
        b_lower = b.lower().strip()
        if a_lower == b_lower:
            return True
        # Check if one contains the other
        if a_lower in b_lower or b_lower in a_lower:
            return True
        # Check word overlap > 70%
        words_a = set(a_lower.split())
        words_b = set(b_lower.split())
        if not words_a or not words_b:
            return False
        overlap = len(words_a & words_b)
        return overlap / min(len(words_a), len(words_b)) > 0.7

    def forget(self, query: str) -> int:
        """Remove facts matching a query. Returns count removed."""
        before = len(self.facts)
        query_lower = query.lower()
        self.facts = [f for f in self.facts if query_lower not in f.fact.lower()]
        removed = before - len(self.facts)
        if removed:
            self.save()
        return removed

    def get_stats(self) -> dict[str, Any]:
        """Memory statistics."""
        categories: dict[str, int] = {}
        for f in self.facts:
            categories[f.category] = categories.get(f.category, 0) + 1
        return {
            "total_facts": len(self.facts),
            "categories": categories,
            "important_count": len(self.get_important()),
            "recent_count": len(self.get_recent()),
        }
