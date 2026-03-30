#!/usr/bin/env python3
"""Tests for Environment Awareness and Ghost Mode."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kai_agent.environment import EnvironmentReading, WiFiSensor, EnvironmentMonitor
from kai_agent.ghost_mode import GhostMode, GhostEvent


# -- Environment Reading --

def test_reading_init():
    r = EnvironmentReading(timestamp=0.0)
    assert r.detection_count == 0
    assert r.is_clear == True
    assert r.threat_level == "clear"


def test_reading_detection():
    r = EnvironmentReading(
        timestamp=0.0,
        wifi_signal=-50,  # Strong = someone nearby
        bluetooth_devices=["iPhone"],
        audio_level=0.3,
    )
    assert r.detection_count > 0
    assert r.is_clear == False
    assert r.threat_level != "clear"


def test_reading_threat_levels():
    clear = EnvironmentReading(timestamp=0.0)
    assert clear.threat_level == "clear"

    low = EnvironmentReading(timestamp=0.0, wifi_signal=-55)
    assert low.threat_level == "low"

    high = EnvironmentReading(
        timestamp=0.0,
        wifi_signal=-40,
        bluetooth_devices=["a", "b"],
        audio_level=0.5,
        webcam_motion=True,
        webcam_face=True,
    )
    assert high.threat_level == "high"


def test_reading_to_dict():
    r = EnvironmentReading(timestamp=0.0, wifi_signal=-60)
    d = r.to_dict()
    assert "wifi_signal" in d
    assert "threat_level" in d


# -- Ghost Mode --

def test_ghost_init():
    env = EnvironmentMonitor(save_path=Path(tempfile.mktemp()))
    ghost = GhostMode(env, save_path=Path(tempfile.mktemp()))
    assert ghost.is_active == False
    assert ghost.is_frozen == False


def test_ghost_activate():
    env = EnvironmentMonitor(save_path=Path(tempfile.mktemp()))
    ghost = GhostMode(env, save_path=Path(tempfile.mktemp()))
    result = ghost.activate()
    assert "active" in result
    assert ghost.is_active == True


def test_ghost_deactivate():
    env = EnvironmentMonitor(save_path=Path(tempfile.mktemp()))
    ghost = GhostMode(env, save_path=Path(tempfile.mktemp()))
    ghost.activate()
    result = ghost.deactivate()
    assert ghost.is_active == False


def test_ghost_action_when_inactive():
    env = EnvironmentMonitor(save_path=Path(tempfile.mktemp()))
    ghost = GhostMode(env, save_path=Path(tempfile.mktemp()))
    result = ghost.request_action("walk")
    assert result["go"] == True  # Not in ghost mode, so always go


def test_ghost_status_line():
    env = EnvironmentMonitor(save_path=Path(tempfile.mktemp()))
    ghost = GhostMode(env, save_path=Path(tempfile.mktemp()))
    assert "OFF" in ghost.get_status_line()

    ghost.activate()
    line = ghost.get_status_line()
    assert "Ghost" in line


def test_ghost_stats():
    env = EnvironmentMonitor(save_path=Path(tempfile.mktemp()))
    ghost = GhostMode(env, save_path=Path(tempfile.mktemp()))
    ghost.activate()
    ghost.scan()
    stats = ghost.get_stats()
    assert "total_scans" in stats
    assert stats["total_scans"] >= 1


def test_ghost_event():
    e = GhostEvent(
        timestamp=0.0,
        event_type="scan",
        threat_level="clear",
        blockers=[],
    )
    d = e.to_dict()
    assert d["event_type"] == "scan"


# -- WiFi Sensor --

def test_wifi_sensor_init():
    wifi = WiFiSensor()
    assert wifi.system in ("Linux", "Windows", "Darwin")


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
    assert "threat_level" in check


def test_monitor_summary():
    env = EnvironmentMonitor(save_path=Path(tempfile.mktemp()))
    summary = env.get_summary()
    assert "WiFi" in summary
    assert "Detection" in summary


def test_monitor_status():
    env = EnvironmentMonitor(save_path=Path(tempfile.mktemp()))
    status = env.get_status()
    assert "reading" in status
    assert "ghost_mode" in status


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
