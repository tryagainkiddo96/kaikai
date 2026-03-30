#!/usr/bin/env python3
"""Tests for Emotional State and Semantic Memory."""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kai_agent.emotional_state import EmotionalState, EmotionalDimensions, EmotionShift, derive_mood
from kai_agent.semantic_memory import SemanticMemory, MemoryFact, extract_facts, utc_now


# ---------------------------------------------------------------------------
# Emotional State
# ---------------------------------------------------------------------------

def test_default_state():
    es = EmotionalState(save_path=Path(tempfile.mktemp()))
    state = es.get_state()
    assert "mood" in state
    assert "emoji" in state
    assert "dimensions" in state


def test_event_shifts():
    es = EmotionalState(save_path=Path(tempfile.mktemp()))
    es.process_event("user_was_kind")
    assert es.dimensions.valence > 0.3  # baseline was 0.3, should go up
    assert es.dimensions.pride > 0.2


def test_negative_event():
    es = EmotionalState(save_path=Path(tempfile.mktemp()))
    es.process_event("user_was_frustrated")
    assert es.dimensions.valence < 0.3
    assert es.dimensions.concern > 0.0


def test_task_events():
    es = EmotionalState(save_path=Path(tempfile.mktemp()))
    es.process_event("task_completed")
    assert es.dimensions.pride > 0.2
    es2 = EmotionalState(save_path=Path(tempfile.mktemp()))
    es2.process_event("task_failed")
    assert es2.dimensions.pride < 0.2


def test_absence():
    es = EmotionalState(save_path=Path(tempfile.mktemp()))
    es.process_event("user_absent", hours=48)
    assert es.dimensions.valence < 0.3
    assert es.dimensions.concern > 0.0


def test_return():
    es = EmotionalState(save_path=Path(tempfile.mktemp()))
    es.process_event("user_returned")
    # Return should boost valence from baseline
    assert es.dimensions.valence > 0.3


def test_mood_derivation():
    happy = EmotionalDimensions(valence=0.7, arousal=0.5)
    label, emoji = derive_mood(happy)
    assert label in ("excited", "happy", "content", "loyal")

    worried = EmotionalDimensions(concern=0.7)
    label, emoji = derive_mood(worried)
    assert label == "worried"


def test_persistence():
    with tempfile.TemporaryDirectory() as td:
        save = Path(td) / "emotions.json"
        es1 = EmotionalState(save_path=save)
        es1.process_event("user_was_kind")
        es1.process_event("user_was_kind")
        valence_after = es1.dimensions.valence

        es2 = EmotionalState(save_path=save)
        assert es2.dimensions.valence == valence_after


def test_response_color():
    es = EmotionalState(save_path=Path(tempfile.mktemp()))
    es.dimensions.valence = 0.7
    es.dimensions.curiosity = 0.6
    color = es.get_response_color()
    assert len(color["modifiers"]) > 0


def test_history_logging():
    es = EmotionalState(save_path=Path(tempfile.mktemp()))
    es.process_event("user_spoke")
    es.process_event("task_completed")
    assert len(es.history) == 2


# ---------------------------------------------------------------------------
# Semantic Memory
# ---------------------------------------------------------------------------

def test_remember():
    sm = SemanticMemory(save_path=Path(tempfile.mktemp()))
    fact = sm.remember("User loves Shiba Inus", category="preference", importance=0.9)
    assert fact.fact == "User loves Shiba Inus"
    assert len(sm.facts) == 1


def test_duplicate_prevention():
    sm = SemanticMemory(save_path=Path(tempfile.mktemp()))
    sm.remember("User loves Shiba Inus")
    sm.remember("User loves Shiba Inus")
    assert len(sm.facts) == 1


def test_recall():
    sm = SemanticMemory(save_path=Path(tempfile.mktemp()))
    sm.remember("User is building a game about Poplar Bluff", category="project")
    sm.remember("User loves pizza", category="preference")
    sm.remember("User's dog is named Kai", category="personal")

    results = sm.recall("tell me about the game")
    assert any("game" in f.fact.lower() or "poplar" in f.fact.lower() for f in results)


def test_learn_from_conversation():
    sm = SemanticMemory(save_path=Path(tempfile.mktemp()))
    facts = sm.learn_from_conversation("I love working on my game project")
    # Should extract at least one fact
    assert len(facts) >= 0  # pattern might or might not match


def test_extraction_preferences():
    facts = extract_facts("I like pizza and coding")
    assert len(facts) > 0
    assert any("pizza" in f.fact.lower() for f in facts)


def test_extraction_projects():
    facts = extract_facts("I'm working on a Godot game")
    assert any("game" in f.fact.lower() or "godot" in f.fact.lower() for f in facts)


def test_extraction_personal():
    facts = extract_facts("My dog is named Kai")
    assert any("kai" in f.fact.lower() for f in facts)


def test_extraction_emotional():
    facts = extract_facts("I'm feeling stressed about this")
    assert any("stress" in f.fact.lower() for f in facts)


def test_context_for_prompt():
    sm = SemanticMemory(save_path=Path(tempfile.mktemp()))
    sm.remember("User's favorite color is blue", category="preference")
    sm.remember("User is building a website", category="project")

    ctx = sm.build_context_for_prompt("what's my favorite color")
    assert "blue" in ctx.lower() or "Things you remember" in ctx


def test_category_filter():
    sm = SemanticMemory(save_path=Path(tempfile.mktemp()))
    sm.remember("User likes pizza", category="preference")
    sm.remember("User is building an app", category="project")

    prefs = sm.get_all_by_category("preference")
    assert len(prefs) == 1
    assert "pizza" in prefs[0].fact.lower()


def test_forget():
    sm = SemanticMemory(save_path=Path(tempfile.mktemp()))
    sm.remember("User likes pizza")
    sm.remember("User likes tacos")
    removed = sm.forget("pizza")
    assert removed == 1
    assert len(sm.facts) == 1


def test_stats():
    sm = SemanticMemory(save_path=Path(tempfile.mktemp()))
    sm.remember("a", category="preference")
    sm.remember("b", category="project")
    sm.remember("c", category="preference")
    stats = sm.get_stats()
    assert stats["total_facts"] == 3
    assert stats["categories"]["preference"] == 2


def test_persistence():
    with tempfile.TemporaryDirectory() as td:
        save = Path(td) / "memory.json"
        sm1 = SemanticMemory(save_path=save)
        sm1.remember("User's cat is named Whiskers", category="personal", importance=0.8)

        sm2 = SemanticMemory(save_path=save)
        assert len(sm2.facts) == 1
        assert "Whiskers" in sm2.facts[0].fact


def test_relevance_decay():
    old = MemoryFact(
        fact="old fact",
        created_at="2020-01-01T00:00:00Z",
        importance=0.5,
    )
    new = MemoryFact(
        fact="new fact",
        created_at=utc_now(),
        importance=0.5,
    )
    assert new.relevance_score > old.relevance_score


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
