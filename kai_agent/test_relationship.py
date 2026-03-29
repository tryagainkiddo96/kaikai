#!/usr/bin/env python3
"""Tests for Relationship Model."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kai_agent.relationship_model import RelationshipModel, analyze_message, UserPreferences


def test_analyze_message():
    a = analyze_message("hey can you help me with this lol")
    assert a["casual_score"] > 0
    assert a["uses_slang"] == True
    assert a["is_question"] == False


def test_analyze_question():
    a = analyze_message("what's the best way to do this?")
    assert a["is_question"] == True


def test_analyze_formal():
    a = analyze_message("Could you please help me with this? Thank you.")
    assert a["formal_score"] > 0


def test_analyze_frustration():
    a = analyze_message("this is broken and doesn't work, so frustrating")
    assert a["frustration"] == True


def test_analyze_excitement():
    a = analyze_message("this is awesome and amazing!")
    assert a["excitement"] == True


def test_init():
    rm = RelationshipModel(save_path=Path(tempfile.mktemp()))
    assert rm.interaction_count == 0
    assert rm.prefs.formality >= 0


def test_process_message():
    rm = RelationshipModel(save_path=Path(tempfile.mktemp()))
    rm.process_message("hey what's up lol")
    assert rm.interaction_count == 1
    assert rm.prefs.uses_slang == True


def test_learn_casual():
    rm = RelationshipModel(save_path=Path(tempfile.mktemp()))
    for _ in range(10):
        rm.process_message("hey lol nah yeah sup bruh")
    assert rm.prefs.formality < 0.3


def test_learn_emoji():
    rm = RelationshipModel(save_path=Path(tempfile.mktemp()))
    rm.process_message("this is great 😄")
    assert rm.prefs.uses_emoji == True


def test_learn_name():
    rm = RelationshipModel(save_path=Path(tempfile.mktemp()))
    rm.set_name("Jake")
    assert rm.prefs.preferred_name == "Jake"


def test_learn_project():
    rm = RelationshipModel(save_path=Path(tempfile.mktemp()))
    rm.add_project("Kai Big City")
    assert "Kai Big City" in rm.prefs.active_projects


def test_inside_joke():
    rm = RelationshipModel(save_path=Path(tempfile.mktemp()))
    rm.add_inside_joke("Saiya would never")
    assert "Saiya would never" in rm.inside_jokes


def test_experience():
    rm = RelationshipModel(save_path=Path(tempfile.mktemp()))
    rm.add_experience("Built the game together", "happy")
    assert len(rm.shared_experiences) == 1


def test_communication_style():
    rm = RelationshipModel(save_path=Path(tempfile.mktemp()))
    style = rm.get_communication_style()
    assert "tone" in style
    assert "length" in style


def test_relationship_context():
    rm = RelationshipModel(save_path=Path(tempfile.mktemp()))
    rm.set_name("Jake")
    rm.add_project("Kai Big City")
    ctx = rm.get_relationship_context()
    assert "Jake" in ctx
    assert "Kai Big City" in ctx


def test_persistence():
    with tempfile.TemporaryDirectory() as td:
        save = Path(td) / "rel.json"
        rm1 = RelationshipModel(save_path=save)
        rm1.set_name("Jake")
        rm1.add_project("Test")
        rm1.process_message("hello there")

        rm2 = RelationshipModel(save_path=save)
        assert rm2.prefs.preferred_name == "Jake"
        assert rm2.interaction_count == 1


def test_stats():
    rm = RelationshipModel(save_path=Path(tempfile.mktemp()))
    rm.process_message("test")
    stats = rm.get_stats()
    assert stats["interactions"] == 1


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
