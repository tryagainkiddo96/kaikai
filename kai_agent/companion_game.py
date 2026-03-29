"""
Kai Companion Game System
Turns Kai's real actions into RPG progression.
XP, levels, achievements, status effects, ability cooldowns.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# XP & Leveling
# ---------------------------------------------------------------------------

# XP needed per level (exponential curve)
def xp_for_level(level: int) -> int:
    """XP threshold for a given level."""
    if level <= 1:
        return 0
    return int(50 * (1.4 ** (level - 1)))


# XP rewards per action type
XP_REWARDS: dict[str, int] = {
    "command_run": 5,
    "file_read": 3,
    "file_analyzed": 8,
    "code_generated": 10,
    "task_completed": 15,
    "plan_executed": 20,
    "web_search": 5,
    "document_found": 5,
    "screen_capture": 3,
    "memory_saved": 2,
    "error_recovered": 12,
    "streak_5": 25,        # 5 commands in a row without error
    "streak_10": 60,       # 10 commands
}

# Level titles
LEVEL_TITLES: dict[int, str] = {
    1: "Pup",
    5: "Good Boy",
    10: "Clever Pup",
    15: "Watchdog",
    20: "Alpha",
    25: "Shiba Elite",
    30: "Kai the Wise",
    40: "Legendary Familiar",
    50: "Inugami",
}


def title_for_level(level: int) -> str:
    """Get the title for a level."""
    best = "Pup"
    for threshold, title in sorted(LEVEL_TITLES.items()):
        if level >= threshold:
            best = title
    return best


# ---------------------------------------------------------------------------
# Ability Cooldowns
# ---------------------------------------------------------------------------

ABILITY_COOLDOWNS: dict[str, float] = {
    "bark_signal": 30.0,      # system scan
    "fetch": 10.0,            # web search / download
    "sniff_out": 5.0,         # /analyze
    "shadow_clone": 60.0,     # sub-agent
    "paw_shield": 45.0,       # error recovery
    "task_chain": 15.0,       # task planner
    "good_boy_recall": 8.0,   # /memory
    "watchdog": 120.0,        # /watch on (long passive)
}

ABILITY_DESCRIPTIONS: dict[str, str] = {
    "bark_signal": "Ping the environment — reveal system status",
    "fetch": "Retrieve something from the web",
    "sniff_out": "Analyze code or a file in detail",
    "shadow_clone": "Spawn a parallel agent to help",
    "paw_shield": "Absorb and recover from an error",
    "task_chain": "Execute a multi-step plan",
    "good_boy_recall": "Recall everything Kai remembers",
    "watchdog": "Enter proactive patrol mode",
}


# ---------------------------------------------------------------------------
# Status Effects
# ---------------------------------------------------------------------------

@dataclass
class StatusEffect:
    name: str
    emoji: str
    description: str
    started_at: float = field(default_factory=time.time)
    duration: float = 0.0  # 0 = permanent until cleared
    bonus_xp_rate: float = 1.0

    @property
    def active(self) -> bool:
        if self.duration <= 0:
            return True
        return (time.time() - self.started_at) < self.duration

    @property
    def remaining(self) -> float:
        if self.duration <= 0:
            return float("inf")
        return max(0, self.duration - (time.time() - self.started_at))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "emoji": self.emoji,
            "description": self.description,
            "active": self.active,
            "remaining": round(self.remaining, 1),
            "bonus_xp_rate": self.bonus_xp_rate,
        }


def make_focused() -> StatusEffect:
    return StatusEffect("Focused", "🟢", "Productive streak — bonus XP", duration=1800, bonus_xp_rate=1.5)

def make_idle() -> StatusEffect:
    return StatusEffect("Idle", "🟡", "No commands in a while — Kai is resting", duration=0)

def make_overloaded() -> StatusEffect:
    return StatusEffect("Overloaded", "🔴", "Too many errors — Kai is stressed", duration=120, bonus_xp_rate=0.5)

def make_in_the_zone() -> StatusEffect:
    return StatusEffect("In the Zone", "🟣", "Complex task running — Kai is locked in", duration=0, bonus_xp_rate=2.0)

def make_blazing() -> StatusEffect:
    return StatusEffect("Blazing", "🔥", "Ultimate active — all systems enhanced!", duration=30, bonus_xp_rate=3.0)


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------

ACHIEVEMENTS: dict[str, dict[str, str]] = {
    "first_bark": {"name": "First Bark", "emoji": "🐾", "desc": "Run your first command"},
    "nose_knows": {"name": "Nose Knows", "emoji": "🔍", "desc": "Analyze 50 files"},
    "speed_run": {"name": "Speed Run", "emoji": "⚡", "desc": "Complete a task plan in under 60 seconds"},
    "good_boy": {"name": "Good Boy", "emoji": "🦊", "desc": "Reach level 10"},
    "blaze_of_glory": {"name": "Blaze of Glory", "emoji": "🔥", "desc": "Run 100 commands in one session"},
    "paw_shield": {"name": "Paw Shield", "emoji": "🛡️", "desc": "Recover from 10 errors"},
    "code_smith": {"name": "Code Smith", "emoji": "⚒️", "desc": "Generate 25 code snippets"},
    "deep_sniff": {"name": "Deep Sniff", "emoji": "🧠", "desc": "Analyze a 1000+ line file"},
    "task_master": {"name": "Task Master", "emoji": "📋", "desc": "Complete 10 task plans"},
    "streak_ten": {"name": "On Fire", "emoji": "🔥", "desc": "10 commands in a row without error"},
    "night_owl": {"name": "Night Owl", "emoji": "🦉", "desc": "Use Kai past midnight"},
    "early_bird": {"name": "Early Bird", "emoji": "🐦", "desc": "Use Kai before 6 AM"},
    "jack_of_all": {"name": "Jack of All Trades", "emoji": "🃏", "desc": "Use 10 different ability types"},
    "level_20": {"name": "Alpha", "emoji": "👑", "desc": "Reach level 20"},
    "level_50": {"name": "Inugami", "emoji": "🌟", "desc": "Reach level 50"},
}


# ---------------------------------------------------------------------------
# Main game state
# ---------------------------------------------------------------------------

@dataclass
class CompanionGameState:
    """Persistent game state for Kai's RPG progression."""
    xp: int = 0
    level: int = 1
    total_commands: int = 0
    total_errors: int = 0
    total_recoveries: int = 0
    total_files_analyzed: int = 0
    total_code_generated: int = 0
    total_tasks_completed: int = 0
    command_streak: int = 0
    best_streak: int = 0
    abilities_used: dict[str, int] = field(default_factory=dict)
    achievements: list[str] = field(default_factory=list)
    cooldowns: dict[str, float] = field(default_factory=dict)
    status_effects: list[dict[str, Any]] = field(default_factory=list)
    session_start: float = field(default_factory=time.time)

    @property
    def title(self) -> str:
        return title_for_level(self.level)

    @property
    def xp_to_next(self) -> int:
        return xp_for_level(self.level + 1)

    @property
    def xp_progress(self) -> float:
        threshold = xp_for_level(self.level + 1)
        if threshold <= 0:
            return 1.0
        return min(1.0, self.xp / threshold)

    def to_dict(self) -> dict[str, Any]:
        return {
            "xp": self.xp,
            "level": self.level,
            "total_commands": self.total_commands,
            "total_errors": self.total_errors,
            "total_recoveries": self.total_recoveries,
            "total_files_analyzed": self.total_files_analyzed,
            "total_code_generated": self.total_code_generated,
            "total_tasks_completed": self.total_tasks_completed,
            "command_streak": self.command_streak,
            "best_streak": self.best_streak,
            "abilities_used": self.abilities_used,
            "achievements": self.achievements,
        }


class CompanionGame:
    """Manages Kai's RPG progression."""

    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path or Path.cwd() / "memory" / "game_state.json"
        self.state = CompanionGameState()
        self._load()

    # -- persistence --

    def _load(self) -> None:
        if self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text(encoding="utf-8"))
                # Skip computed properties that have no setter
                skip = {"status_effects", "cooldowns", "title", "xp_to_next", "xp_progress", "active_effects"}
                for key, val in data.items():
                    if hasattr(self.state, key) and key not in skip:
                        setattr(self.state, key, val)
                self.state.cooldowns = data.get("cooldowns", {})
                # Don't restore status effects — they're ephemeral
            except Exception:
                pass

    def save(self) -> None:
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        save_data = self.state.to_dict()
        save_data["cooldowns"] = self.state.cooldowns
        self.save_path.write_text(json.dumps(save_data, indent=2), encoding="utf-8")

    # -- XP & leveling --

    def award_xp(self, action: str, bonus: float = 1.0) -> dict[str, Any]:
        """Award XP for an action. Returns level-up info if applicable."""
        base_xp = XP_REWARDS.get(action, 1)
        # Apply status effect multiplier
        effect_mult = 1.0
        for e in self.state.status_effects:
            if isinstance(e, dict):
                effect_mult = max(effect_mult, e.get("bonus_xp_rate", 1.0))
            elif hasattr(e, "bonus_xp_rate"):
                effect_mult = max(effect_mult, e.bonus_xp_rate)

        total_xp = int(base_xp * bonus * effect_mult)
        self.state.xp += total_xp

        result: dict[str, Any] = {"xp_gained": total_xp, "action": action}

        # Check level up
        leveled_up = False
        while self.state.xp >= self.state.xp_to_next and self.state.xp_to_next > 0:
            self.state.xp -= self.state.xp_to_next
            self.state.level += 1
            leveled_up = True

        if leveled_up:
            result["level_up"] = True
            result["new_level"] = self.state.level
            result["new_title"] = self.state.title

        return result

    # -- action tracking --

    def record_action(self, action: str, success: bool = True) -> dict[str, Any]:
        """Record an action and award XP. Returns progression info."""
        self.state.total_commands += 1

        if success:
            self.state.command_streak += 1
            self.state.best_streak = max(self.state.best_streak, self.state.command_streak)
        else:
            self.state.command_streak = 0
            self.state.total_errors += 1

        # Track specific actions
        if action == "file_analyzed":
            self.state.total_files_analyzed += 1
        elif action == "code_generated":
            self.state.total_code_generated += 1
        elif action == "task_completed" or action == "plan_executed":
            self.state.total_tasks_completed += 1
        elif action == "error_recovered":
            self.state.total_recoveries += 1

        # Streak bonuses
        xp_result = self.award_xp(action)
        if self.state.command_streak == 5:
            streak_result = self.award_xp("streak_5")
            xp_result["streak_bonus"] = streak_result
        elif self.state.command_streak == 10:
            streak_result = self.award_xp("streak_10")
            xp_result["streak_bonus"] = streak_result

        # Check achievements
        new_achievements = self._check_achievements()
        if new_achievements:
            xp_result["achievements_unlocked"] = new_achievements

        self.save()
        return xp_result

    def record_ability_use(self, ability_name: str) -> None:
        """Record ability use and start cooldown."""
        self.state.abilities_used[ability_name] = self.state.abilities_used.get(ability_name, 0) + 1
        cooldown = ABILITY_COOLDOWNS.get(ability_name, 0)
        if cooldown > 0:
            self.state.cooldowns[ability_name] = time.time() + cooldown
        self.save()

    # -- cooldowns --

    def get_cooldown(self, ability_name: str) -> float:
        """Get remaining cooldown in seconds (0 = ready)."""
        expires = self.state.cooldowns.get(ability_name, 0)
        remaining = expires - time.time()
        return max(0, remaining)

    def is_ready(self, ability_name: str) -> bool:
        return self.get_cooldown(ability_name) <= 0

    def get_all_cooldowns(self) -> dict[str, dict[str, Any]]:
        """Get cooldown status for all abilities."""
        result = {}
        for name in ABILITY_COOLDOWNS:
            remaining = self.get_cooldown(name)
            result[name] = {
                "ready": remaining <= 0,
                "remaining": round(remaining, 1),
                "cooldown_total": ABILITY_COOLDOWNS[name],
                "description": ABILITY_DESCRIPTIONS.get(name, ""),
            }
        return result

    # -- status effects --

    def apply_effect(self, effect: StatusEffect) -> None:
        """Apply a status effect. Replaces existing effects with the same name or conflicting category."""
        # Define mutually exclusive groups
        MUTE_GROUPS = [
            {"Focused", "Idle", "Overloaded"},  # mood states — only one at a time
        ]
        # Find which mute group this effect belongs to
        mute_names: set[str] = set()
        for group in MUTE_GROUPS:
            if effect.name in group:
                mute_names = group
                break

        # Remove expired, duplicates, and conflicting effects
        cleaned = []
        for e in self.state.status_effects:
            ename = e.get("name") if isinstance(e, dict) else getattr(e, "name", None)
            eactive = e.get("active", True) if isinstance(e, dict) else getattr(e, "active", True)
            if ename == effect.name:
                continue  # always replace self
            if ename in mute_names:
                continue  # replace conflicting status
            if eactive:
                cleaned.append(e)
        self.state.status_effects = cleaned
        self.state.status_effects.append(effect.to_dict())

    def clear_effect(self, name: str) -> None:
        self.state.status_effects = [
            e for e in self.state.status_effects
            if (isinstance(e, dict) and e.get("name") != name)
            or (hasattr(e, "name") and e.name != name)
        ]

    def get_active_effects(self) -> list[dict[str, Any]]:
        """Get currently active status effects."""
        active = []
        for e in self.state.status_effects:
            if isinstance(e, dict):
                if e.get("active", True):
                    active.append(e)
        return active

    # -- achievements --

    def _check_achievements(self) -> list[str]:
        """Check and unlock any new achievements."""
        unlocked = []
        s = self.state
        checks = {
            "first_bark": s.total_commands >= 1,
            "nose_knows": s.total_files_analyzed >= 50,
            "good_boy": s.level >= 10,
            "blaze_of_glory": s.total_commands >= 100,
            "paw_shield": s.total_recoveries >= 10,
            "code_smith": s.total_code_generated >= 25,
            "task_master": s.total_tasks_completed >= 10,
            "streak_ten": s.best_streak >= 10,
            "level_20": s.level >= 20,
            "level_50": s.level >= 50,
            "jack_of_all": len(s.abilities_used) >= 10,
        }
        # Time-based
        from datetime import datetime
        hour = datetime.now().hour
        if hour >= 0 and hour < 6:
            checks["early_bird"] = True
        if hour >= 0 and hour < 4:
            checks["night_owl"] = True

        for ach_id, condition in checks.items():
            if condition and ach_id not in s.achievements:
                s.achievements.append(ach_id)
                unlocked.append(ach_id)

        return unlocked

    # -- HUD data (for UI) --

    def get_hud(self) -> dict[str, Any]:
        """Get everything needed to render the companion HUD."""
        return {
            "level": self.state.level,
            "title": self.state.title,
            "xp": self.state.xp,
            "xp_to_next": self.state.xp_to_next,
            "xp_progress": round(self.state.xp_progress * 100, 1),
            "streak": self.state.command_streak,
            "total_commands": self.state.total_commands,
            "abilities": self.get_all_cooldowns(),
            "effects": self.get_active_effects(),
            "achievements": [
                {**ACHIEVEMENTS[a], "id": a}
                for a in self.state.achievements
                if a in ACHIEVEMENTS
            ],
            "recent_achievement": (
                {**ACHIEVEMENTS[self.state.achievements[-1]], "id": self.state.achievements[-1]}
                if self.state.achievements else None
            ),
        }

    def get_status_line(self) -> str:
        """One-line status for terminal output."""
        hud = self.get_hud()
        effects = "".join(e["emoji"] for e in hud["effects"])
        return (
            f"Lv.{hud['level']} {hud['title']} "
            f"| XP: {hud['xp']}/{hud['xp_to_next']} ({hud['xp_progress']}%) "
            f"| 🔥 {hud['streak']} streak "
            f"| {hud['total_commands']} cmds"
            + (f" | {effects}" if effects else "")
        )
