#!/usr/bin/env python3
"""Tests for Environment Awareness and Ghost Mode."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kai_agent.environment import EnvironmentReading, WiFiSensor, EnvironmentMonitor
from kai_agent.ghost_mode import GhostMode, GhostIdentity, TraceCleaner


# -- Environment Reading --

def test_reading_init():
    r = EnvironmentReading(timestamp=0.0)
    assert r.detection_count == 0
    assert r.is_clear == True
    assert r.threat_level == "clear"


def test_reading_detection():
    r = EnvironmentReading(
        timestamp=0.0,
        wifi_signal=-50,
        bluetooth_devices=["iPhone"],
        audio_level=0.3,
    )
    assert r.detection_count > 0
    assert r.is_clear == False


def test_reading_threat_levels():
    clear = EnvironmentReading(timestamp=0.0)
    assert clear.threat_level == "clear"
    high = EnvironmentReading(
        timestamp=0.0, wifi_signal=-40,
        bluetooth_devices=["a", "b"], audio_level=0.5,
        webcam_motion=True, webcam_face=True,
    )
    assert high.threat_level == "high"


# -- Ghost Identity --

def test_identity_generate():
    ident = GhostIdentity()
    assert ident.user_agent != ""
    assert ident.session_id != ""


def test_identity_rotate():
    ident = GhostIdentity()
    old_alias = ident.current["alias"]
    ident.rotate()
    assert ident.current["alias"] != old_alias


# -- Trace Cleaner --

def test_cleaner_temp():
    cleaner = TraceCleaner()
    temp = cleaner.create_temp()
    temp.write_text("test")
    assert temp.exists()
    removed = cleaner.cleanup()
    assert removed == 1
    assert not temp.exists()


def test_cleaner_log():
    cleaner = TraceCleaner()
    cleaner.log_operation("test", "target", True)
    assert len(cleaner.get_operation_log()) == 1
    cleaner.clear_log()
    assert len(cleaner.get_operation_log()) == 0


# -- Ghost Mode --

def test_ghost_init():
    ghost = GhostMode(save_path=Path(tempfile.mktemp()))
    assert ghost.is_active == False


def test_ghost_activate():
    ghost = GhostMode(save_path=Path(tempfile.mktemp()))
    result = ghost.activate()
    assert ghost.is_active == True
    assert "active" in result


def test_ghost_deactivate():
    ghost = GhostMode(save_path=Path(tempfile.mktemp()))
    ghost.activate()
    result = ghost.deactivate()
    assert ghost.is_active == False
    assert "files_cleaned" in result


def test_ghost_browse_requires_active():
    ghost = GhostMode(save_path=Path(tempfile.mktemp()))
    result = ghost.browse("http://example.com")
    assert result["success"] == False


def test_ghost_status():
    ghost = GhostMode(save_path=Path(tempfile.mktemp()))
    status = ghost.get_status()
    assert status["active"] == False

    ghost.activate()
    status = ghost.get_status()
    assert status["active"] == True
    assert status["identity"] is not None


def test_ghost_status_line():
    ghost = GhostMode(save_path=Path(tempfile.mktemp()))
    assert "OFF" in ghost.get_status_line()
    ghost.activate()
    assert "ON" in ghost.get_status_line()


# -- Environment Monitor --

def test_monitor_init():
    env = EnvironmentMonitor(save_path=Path(tempfile.mktemp()))
    assert env.wifi is not None
    assert env.bluetooth is not None


def test_monitor_ghost_check():
    env = EnvironmentMonitor(save_path=Path(tempfile.mktemp()))
    check = env.ghost_check()
    assert "go" in check
    assert "checks" in check


def test_monitor_summary():
    env = EnvironmentMonitor(save_path=Path(tempfile.mktemp()))
    summary = env.get_summary()
    assert "WiFi" in summary


# -- Run --

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
