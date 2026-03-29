#!/usr/bin/env python3
"""Tests for Social Timing and Inner Monologue."""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kai_agent.social_timing import SocialTiming, TimingSignal
from kai_agent.inner_monologue import InnerMonologue, Thought


# ---------------------------------------------------------------------------
# Social Timing
# ---------------------------------------------------------------------------

def test_init():
    st = SocialTiming(save_path=Path(tempfile.mktemp()))
    assert st.total_interactions == 0
    assert st.current_session is None


def test_interaction_tracking():
    st = SocialTiming(save_path=Path(tempfile.mktemp()))
    st.interaction_started()
    assert st.current_session is not None
    assert st.current_session.message_count == 1
    assert st.total_interactions == 1

    st.interaction_started()
    assert st.current_session.message_count == 2
    assert st.total_interactions == 2


def test_session_end():
    st = SocialTiming(save_path=Path(tempfile.mktemp()))
    st.interaction_started()
    st.session_ended()
    assert st.current_session is None
    assert len(st.session_history) == 1


def test_idle_tracking():
    st = SocialTiming(save_path=Path(tempfile.mktemp()))
    st.interaction_started()
    time.sleep(0.1)
    assert st.idle_minutes < 1


def test_quiet_hours():
    st = SocialTiming(save_path=Path(tempfile.mktemp()))
    # Default quiet: 23-7
    st.quiet_start = 23
    st.quiet_end = 7
    # Can't easily test without mocking time, just verify property exists
    assert isinstance(st.is_quiet_hours, bool)


def test_pattern_learning():
    st = SocialTiming(save_path=Path(tempfile.mktemp()))
    for _ in range(5):
        st.interaction_started()
    hour_key = str(time.localtime().tm_hour).zfill(2)
    assert hour_key in st.daily_patterns
    assert len(st.daily_patterns[hour_key]) == 5


def test_signal_system():
    st = SocialTiming(save_path=Path(tempfile.mktemp()))
    # Register a test signal that always fires
    fired = []
    st.register_signal(TimingSignal(
        name="test_signal",
        priority=5,
        message="test_fired",
        check=lambda t: True,
        cooldown_minutes=0,
    ))
    result = st.check_for_proactive_moment()
    assert result is not None
    assert result["signal"] == "test_signal"


def test_signal_cooldown():
    st = SocialTiming(save_path=Path(tempfile.mktemp()))
    st.register_signal(TimingSignal(
        name="cooldown_test",
        priority=5,
        message="test",
        check=lambda t: True,
        cooldown_minutes=60,
    ))
    result1 = st.check_for_proactive_moment()
    assert result1 is not None
    result2 = st.check_for_proactive_moment()
    # Should be None because cooldown
    assert result2 is None or result2["signal"] != "cooldown_test"


def test_persistence():
    with tempfile.TemporaryDirectory() as td:
        save = Path(td) / "timing.json"
        st1 = SocialTiming(save_path=save)
        st1.interaction_started()
        st1.interaction_started()
        st1.save()

        st2 = SocialTiming(save_path=save)
        assert st2.total_interactions == 2


def test_status():
    st = SocialTiming(save_path=Path(tempfile.mktemp()))
    status = st.get_status()
    assert "idle_minutes" in status
    assert "signals_registered" in status


# ---------------------------------------------------------------------------
# Inner Monologue
# ---------------------------------------------------------------------------

def test_think():
    im = InnerMonologue(save_path=Path(tempfile.mktemp()))
    # Force think by setting last_think_time far back
    im.last_think_time = 0
    thought = im.think()
    assert thought is not None
    assert len(thought.content) > 0
    assert thought.category in ("reflection", "observation", "memory", "dream", "plan")


def test_think_cooldown():
    im = InnerMonologue(save_path=Path(tempfile.mktemp()))
    im.last_think_time = time.time()  # just thought
    thought = im.think()
    assert thought is None  # too soon


def test_delivery():
    im = InnerMonologue(save_path=Path(tempfile.mktemp()))
    im.last_think_time = 0
    thought = im.think()
    assert thought is not None
    assert not thought.delivered

    pending = im.get_next_thought()
    assert pending is not None

    im.mark_delivered(pending)
    assert pending.delivered


def test_pending_summary():
    im = InnerMonologue(save_path=Path(tempfile.mktemp()))
    im.last_think_time = 0
    im.think()
    summary = im.get_pending_summary()
    assert summary is not None
    assert "thinking" in summary.lower()


def test_max_undelivered():
    im = InnerMonologue(save_path=Path(tempfile.mktemp()))
    im.max_undelivered = 3
    for _ in range(5):
        im.last_think_time = 0
        im.think()
    undelivered = [t for t in im.thoughts if not t.delivered]
    assert len(undelivered) <= 3


def test_persistence():
    with tempfile.TemporaryDirectory() as td:
        save = Path(td) / "monologue.json"
        im1 = InnerMonologue(save_path=save)
        im1.last_think_time = 0
        im1.think()
        im1.save()

        im2 = InnerMonologue(save_path=save)
        assert len(im2.thoughts) == 1


def test_stats():
    im = InnerMonologue(save_path=Path(tempfile.mktemp()))
    im.last_think_time = 0
    im.think_interval_minutes = 0  # no cooldown for test
    im.think()
    im.think()
    stats = im.get_stats()
    assert stats["total_thoughts"] >= 2


def test_thought_dataclass():
    t = Thought(content="test thought", category="reflection")
    d = t.to_dict()
    assert d["content"] == "test thought"
    t2 = Thought.from_dict(d)
    assert t2.content == "test thought"


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

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
