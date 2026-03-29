#!/usr/bin/env python3
"""Tests for Mood Journal."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kai_agent.mood_journal import MoodJournal


def test_init():
    j = MoodJournal(save_path=Path(tempfile.mktemp()))
    assert len(j.entries) == 0


def test_record():
    j = MoodJournal(save_path=Path(tempfile.mktemp()))
    j.record({"valence": 0.5, "arousal": 0.2}, "happy", "😊")
    assert len(j.entries) == 1
    assert j.entries[0]["mood"] == "happy"


def test_same_day_update():
    j = MoodJournal(save_path=Path(tempfile.mktemp()))
    j.record({"valence": 0.3}, "neutral", "🦊")
    j.record({"valence": 0.7}, "happy", "😊")
    assert len(j.entries) == 1  # Updated, not added
    assert j.entries[0]["mood"] == "happy"


def test_trend_no_data():
    j = MoodJournal(save_path=Path(tempfile.mktemp()))
    trend = j.get_trend()
    assert trend["trend"] == "no_data"


def test_trend_improving():
    j = MoodJournal(save_path=Path(tempfile.mktemp()))
    # Simulate 7 days of improving mood
    from datetime import datetime, timedelta
    for i in range(7):
        day = (datetime.utcnow() - timedelta(days=6-i)).strftime("%Y-%m-%d")
        j.entries.append({
            "date": day,
            "mood": "happy" if i > 3 else "neutral",
            "emoji": "😊",
            "dimensions": {"valence": -0.2 + i * 0.1, "arousal": 0.0, "concern": 0.0, "tiredness": 0.0, "curiosity": 0.3},
            "timestamp": (datetime.utcnow() - timedelta(days=6-i)).isoformat(),
        })
    trend = j.get_trend(7)
    assert trend["trend"] == "improving"


def test_weekly_summary():
    j = MoodJournal(save_path=Path(tempfile.mktemp()))
    j.record({"valence": 0.5, "arousal": 0.1, "concern": 0.0, "tiredness": 0.2, "curiosity": 0.3}, "happy", "😊")
    summary = j.get_weekly_summary()
    assert len(summary) > 0


def test_day_of_week():
    j = MoodJournal(save_path=Path(tempfile.mktemp()))
    j.record({"valence": 0.5}, "happy", "😊")
    pattern = j.get_day_of_week_pattern()
    assert isinstance(pattern, dict)


def test_persistence():
    with tempfile.TemporaryDirectory() as td:
        save = Path(td) / "journal.json"
        j1 = MoodJournal(save_path=save)
        j1.record({"valence": 0.5}, "happy", "😊")

        j2 = MoodJournal(save_path=save)
        assert len(j2.entries) == 1


def test_stats():
    j = MoodJournal(save_path=Path(tempfile.mktemp()))
    j.record({"valence": 0.5}, "happy", "😊")
    stats = j.get_stats()
    assert stats["total_entries"] == 1


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
