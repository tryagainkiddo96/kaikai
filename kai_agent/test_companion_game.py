#!/usr/bin/env python3
"""Tests for Kai Companion Game system."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kai_agent.companion_game import (
    ABILITY_COOLDOWNS,
    ACHIEVEMENTS,
    CompanionGame,
    CompanionGameState,
    StatusEffect,
    xp_for_level,
    title_for_level,
    make_focused,
    make_overloaded,
    make_blazing,
)


def test_xp_curve():
    assert xp_for_level(1) == 0
    assert xp_for_level(2) > 0
    assert xp_for_level(10) > xp_for_level(5)
    assert xp_for_level(50) > xp_for_level(20)


def test_titles():
    assert title_for_level(1) == "Pup"
    assert title_for_level(5) == "Good Boy"
    assert title_for_level(10) == "Clever Pup"
    assert title_for_level(25) == "Shiba Elite"
    assert title_for_level(50) == "Inugami"


def test_game_init():
    with tempfile.TemporaryDirectory() as td:
        save = Path(td) / "game.json"
        game = CompanionGame(save_path=save)
        assert game.state.level == 1
        assert game.state.xp == 0
        assert game.state.total_commands == 0


def test_award_xp():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        result = game.award_xp("command_run")
        assert result["xp_gained"] > 0
        assert game.state.xp > 0


def test_level_up():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        # Dump enough XP to level up
        for _ in range(20):
            result = game.award_xp("task_completed")
        assert game.state.level > 1 or result.get("level_up")


def test_record_action():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        result = game.record_action("command_run", success=True)
        assert game.state.total_commands == 1
        assert game.state.command_streak == 1
        assert result["xp_gained"] > 0


def test_streak_break():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        game.record_action("command_run", success=True)
        game.record_action("command_run", success=True)
        assert game.state.command_streak == 2
        game.record_action("command_run", success=False)
        assert game.state.command_streak == 0
        assert game.state.total_errors == 1


def test_ability_cooldowns():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        assert game.is_ready("bark_signal")
        game.record_ability_use("bark_signal")
        assert not game.is_ready("bark_signal")
        assert game.get_cooldown("bark_signal") > 0


def test_all_cooldowns():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        cds = game.get_all_cooldowns()
        for name in ABILITY_COOLDOWNS:
            assert name in cds
            assert cds[name]["ready"] is True
            assert "description" in cds[name]


def test_status_effects():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        game.apply_effect(make_focused())
        active = game.get_active_effects()
        assert len(active) == 1
        assert active[0]["name"] == "Focused"
        assert active[0]["bonus_xp_rate"] == 1.5


def test_status_effect_replace():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        game.apply_effect(make_overloaded())
        game.apply_effect(make_focused())
        active = game.get_active_effects()
        names = [e["name"] for e in active]
        assert "Focused" in names
        assert "Overloaded" not in names  # replaced


def test_status_effect_clear():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        game.apply_effect(make_blazing())
        assert len(game.get_active_effects()) == 1
        game.clear_effect("Blazing")
        assert len(game.get_active_effects()) == 0


def test_achievement_first_bark():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        result = game.record_action("command_run")
        assert "achievements_unlocked" in result
        assert "first_bark" in result["achievements_unlocked"]


def test_achievement_streak():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        for _ in range(10):
            game.record_action("command_run", success=True)
        assert "streak_ten" in game.state.achievements


def test_persistence():
    with tempfile.TemporaryDirectory() as td:
        save = Path(td) / "game.json"
        game1 = CompanionGame(save_path=save)
        game1.record_action("command_run")
        game1.record_action("file_analyzed")
        game1.award_xp("task_completed")
        game1.save()

        game2 = CompanionGame(save_path=save)
        assert game2.state.total_commands == 2
        assert game2.state.total_files_analyzed == 1


def test_hud():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        game.record_action("command_run")
        hud = game.get_hud()
        assert "level" in hud
        assert "xp_progress" in hud
        assert "abilities" in hud
        assert "effects" in hud
        assert "achievements" in hud


def test_status_line():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        line = game.get_status_line()
        assert "Lv.1" in line
        assert "Pup" in line


def test_xp_bonus_from_effect():
    with tempfile.TemporaryDirectory() as td:
        game = CompanionGame(save_path=Path(td) / "game.json")
        # No effect
        r1 = game.award_xp("command_run")
        base = r1["xp_gained"]

        game2 = CompanionGame(save_path=Path(td) / "game2.json")
        game2.apply_effect(make_blazing())  # 3x XP
        r2 = game2.award_xp("command_run")
        assert r2["xp_gained"] >= base * 2  # at least doubled


def main():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  ❌ {t.__name__}: {exc}")
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*50}")
    print(f"Passed: {passed}  Failed: {failed}  Total: {passed + failed}")
    if failed == 0:
        print("✅ All tests passed!")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
