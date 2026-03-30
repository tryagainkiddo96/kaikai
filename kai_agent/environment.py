"""
Kai Environmental Awareness
Gives Kai senses beyond vision — WiFi, Bluetooth, audio, network.
Part of the spy toolkit. Powers Ghost Mode.

No exotic hardware needed — uses what's already in any computer.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Detection sources
# ---------------------------------------------------------------------------

@dataclass
class EnvironmentReading:
    """A snapshot of what Kai senses."""
    timestamp: float
    wifi_signal: float = -80.0        # dBm, stronger = closer person (-80 = no one nearby)
    wifi_devices: int = 0             # devices on network
    bluetooth_devices: list[str] = field(default_factory=list)
    audio_level: float = 0.0          # 0-1, ambient noise
    audio_class: str = "silence"      # silence, talking, music, tv, dog
    webcam_motion: bool = False       # motion detected
    webcam_face: bool = False         # face detected
    location: str = "unknown"         # home, away, unknown

    @property
    def detection_count(self) -> int:
        """How many sources could detect Kai right now."""
        count = 0
        if self.wifi_signal > -60:  # Strong signal = someone nearby
            count += 1
        if self.bluetooth_devices:
            count += len(self.bluetooth_devices)
        if self.audio_level > 0.1:
            count += 1
        if self.webcam_motion:
            count += 1
        if self.webcam_face:
            count += 1
        return count

    @property
    def is_clear(self) -> bool:
        """Is Kai's environment completely clear for stealth?"""
        return self.detection_count == 0

    @property
    def threat_level(self) -> str:
        """Human-readable threat assessment."""
        d = self.detection_count
        if d == 0:
            return "clear"
        elif d <= 2:
            return "low"
        elif d <= 4:
            return "medium"
        else:
            return "high"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "wifi_signal": round(self.wifi_signal, 1),
            "wifi_devices": self.wifi_devices,
            "bluetooth_devices": self.bluetooth_devices,
            "audio_level": round(self.audio_level, 3),
            "audio_class": self.audio_class,
            "webcam_motion": self.webcam_motion,
            "webcam_face": self.webcam_face,
            "location": self.location,
            "detection_count": self.detection_count,
            "is_clear": self.is_clear,
            "threat_level": self.threat_level,
        }


# ---------------------------------------------------------------------------
# Individual sensors
# ---------------------------------------------------------------------------

class WiFiSensor:
    """Monitor WiFi signal strength and connected devices."""

    def __init__(self):
        self.system = platform.system()
        self._baseline_rssi = -70.0  # Typical "no one nearby" baseline

    def get_signal(self) -> float:
        """Get current WiFi signal strength in dBm."""
        try:
            if self.system == "Linux":
                return self._linux_signal()
            elif self.system == "Windows":
                return self._windows_signal()
            elif self.system == "Darwin":
                return self._macos_signal()
        except Exception:
            pass
        return -80.0  # Default weak signal

    def _linux_signal(self) -> float:
        # Try iwconfig first
        try:
            result = subprocess.run(
                ["iwconfig"], capture_output=True, text=True, timeout=5
            )
            match = re.search(r"Signal level[=:]?\s*(-?\d+)\s*dBm", result.stdout)
            if match:
                return float(match.group(1))
        except FileNotFoundError:
            pass

        # Try /proc/net/wireless
        try:
            with open("/proc/net/wireless") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 4 and "." in parts[1]:
                        return float(parts[2].rstrip("."))
        except Exception:
            pass

        return -80.0

    def _windows_signal(self) -> float:
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=5
        )
        match = re.search(r"Signal\s*:\s*(\d+)%", result.stdout)
        if match:
            percent = int(match.group(1))
            # Convert percentage to approximate dBm
            return -100 + (percent / 2)
        return -80.0

    def _macos_signal(self) -> float:
        result = subprocess.run(
            ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
            capture_output=True, text=True, timeout=5
        )
        match = re.search(r"agrCtlRSSI:\s*(-?\d+)", result.stdout)
        if match:
            return float(match.group(1))
        return -80.0

    def get_connected_devices(self) -> int:
        """Count devices on the local network."""
        try:
            # Check ARP table
            if self.system == "Linux":
                result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
            elif self.system == "Windows":
                result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
            else:
                result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
            
            # Count entries (excluding broadcast/multicast)
            count = len(re.findall(r"\d+\.\d+\.\d+\.\d+", result.stdout))
            return max(0, count - 1)  # Subtract self
        except Exception:
            return 0


class BluetoothSensor:
    """Scan for nearby Bluetooth devices."""

    def __init__(self):
        self.system = platform.system()
        self._known_devices: set[str] = set()

    def scan(self, quick: bool = True) -> list[str]:
        """Scan for nearby BT devices. Returns list of device names."""
        try:
            if self.system == "Linux":
                return self._linux_scan(quick)
            elif self.system == "Windows":
                return self._windows_scan()
        except Exception:
            pass
        return []

    def _linux_scan(self, quick: bool) -> list[str]:
        """Scan using bluetoothctl."""
        timeout = 5 if quick else 15
        try:
            # Get already-paired devices that are connected
            result = subprocess.run(
                ["bluetoothctl", "devices", "Connected"],
                capture_output=True, text=True, timeout=timeout
            )
            devices = []
            for line in result.stdout.split("\n"):
                match = re.search(r"Device\s+\S+\s+(.+)$", line)
                if match:
                    name = match.group(1).strip()
                    if name and name not in ("", "n/a"):
                        devices.append(name)
            return devices
        except FileNotFoundError:
            return []

    def _windows_scan(self) -> list[str]:
        """Windows BT scan via PowerShell."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-PnpDevice | Where-Object {$_.Class -eq 'Bluetooth' -and $_.Status -eq 'OK'} | Select-Object -ExpandProperty FriendlyName"],
                capture_output=True, text=True, timeout=10
            )
            return [name.strip() for name in result.stdout.strip().split("\n") if name.strip()]
        except Exception:
            return []

    def register_known(self, name: str) -> None:
        """Register a known device (user's phone, earbuds, etc.)."""
        self._known_devices.add(name.lower())

    def is_known_nearby(self, detected: list[str]) -> bool:
        """Is any known device in range?"""
        detected_lower = {d.lower() for d in detected}
        return bool(self._known_devices & detected_lower)


class AudioSensor:
    """Monitor ambient audio levels and classify environment."""

    def __init__(self):
        self._has_audio = False
        self._check_availability()

    def _check_availability(self):
        try:
            import pyaudio
            self._has_audio = True
        except ImportError:
            self._has_audio = False

    def get_level(self) -> tuple[float, str]:
        """
        Get audio level (0-1) and environment classification.
        Returns (level, class) where class is one of:
        silence, quiet, talking, music, tv, loud
        """
        if not self._has_audio:
            return 0.0, "unavailable"

        try:
            import pyaudio
            import audioop

            CHUNK = 1024
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000

            p = pyaudio.PyAudio()
            stream = p.open(
                format=FORMAT, channels=CHANNELS,
                rate=RATE, input=True,
                frames_per_buffer=CHUNK
            )

            data = stream.read(CHUNK, exception_on_overflow=False)
            rms = audioop.rms(data, 2)

            stream.stop_stream()
            stream.close()
            p.terminate()

            # Normalize RMS to 0-1 (typical range 0-3000 for quiet room)
            level = min(1.0, rms / 3000.0)

            # Classify
            if level < 0.02:
                env_class = "silence"
            elif level < 0.1:
                env_class = "quiet"
            elif level < 0.3:
                env_class = "talking"
            elif level < 0.6:
                env_class = "music"
            else:
                env_class = "loud"

            return level, env_class

        except Exception:
            return 0.0, "unavailable"


class NetworkSensor:
    """Monitor network for device changes and activity."""

    def __init__(self):
        self._last_device_count = 0
        self._known_macs: dict[str, str] = {}  # MAC → name

    def get_device_count(self) -> int:
        """Count active devices on network."""
        try:
            result = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=5
            )
            count = len(re.findall(r"[\w:]{17}", result.stdout))
            self._last_device_count = count
            return count
        except Exception:
            return self._last_device_count

    def get_active_ips(self) -> list[str]:
        """List active IP addresses on network."""
        try:
            result = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=5
            )
            return re.findall(r"\d+\.\d+\.\d+\.\d+", result.stdout)
        except Exception:
            return []

    def register_device(self, mac: str, name: str) -> None:
        """Register a known device by MAC address."""
        self._known_macs[mac.lower()] = name


# ---------------------------------------------------------------------------
# Environment Monitor — combines all sensors
# ---------------------------------------------------------------------------

class EnvironmentMonitor:
    """
    Kai's full environmental awareness.
    Combines WiFi, Bluetooth, audio, and network sensors.
    Powers Ghost Mode and situational awareness.
    """

    def __init__(self, save_path: Path | None = None):
        self.save_path = save_path or Path.cwd() / "memory" / "environment.json"
        self.wifi = WiFiSensor()
        self.bluetooth = BluetoothSensor()
        self.audio = AudioSensor()
        self.network = NetworkSensor()

        self._last_reading: Optional[EnvironmentReading] = None
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._readings_history: list[dict] = []
        self._max_history = 100

        self._load_config()

    def _load_config(self):
        """Load known devices and preferences."""
        if self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text(encoding="utf-8"))
                for name in data.get("known_bluetooth", []):
                    self.bluetooth.register_known(name)
                for mac, name in data.get("known_devices", {}).items():
                    self.network.register_device(mac, name)
            except Exception:
                pass

    def save(self):
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "known_bluetooth": list(self.bluetooth._known_devices),
            "known_devices": self.network._known_macs,
            "last_reading": self._last_reading.to_dict() if self._last_reading else None,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.save_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # -- Reading --

    def read(self) -> EnvironmentReading:
        """Take a full environment reading."""
        wifi_rssi = self.wifi.get_signal()
        wifi_devs = self.wifi.get_connected_devices()
        bt_devices = self.bluetooth.scan(quick=True)
        audio_level, audio_class = self.audio.get_level()

        reading = EnvironmentReading(
            timestamp=time.time(),
            wifi_signal=wifi_rssi,
            wifi_devices=wifi_devs,
            bluetooth_devices=bt_devices,
            audio_level=audio_level,
            audio_class=audio_class,
            webcam_motion=False,  # Set by external vision system
            webcam_face=False,    # Set by external vision system
            location="home" if wifi_rssi > -80 else "away",
        )

        self._last_reading = reading
        self._readings_history.append(reading.to_dict())
        if len(self._readings_history) > self._max_history:
            self._readings_history = self._readings_history[-self._max_history:]

        return reading

    # -- Ghost Mode --

    def ghost_check(self) -> dict[str, Any]:
        """
        Ghost Mode check — is it safe for Kai to act?
        Returns full status with go/no-go decision.
        """
        reading = self.read()

        checks = {
            "wifi_clear": reading.wifi_signal < -65,        # No one near router
            "bluetooth_clear": len(reading.bluetooth_devices) == 0,  # No BT devices nearby
            "audio_clear": reading.audio_level < 0.05,       # Silence
            "network_quiet": reading.wifi_devices <= 1,      # Only Kai's device
            "webcam_clear": not reading.webcam_motion and not reading.webcam_face,
        }

        all_clear = all(checks.values())

        return {
            "go": all_clear,
            "threat_level": reading.threat_level,
            "checks": checks,
            "reading": reading.to_dict(),
            "recommendation": "ACT NOW" if all_clear else "HOLD — detection risk",
            "blockers": [k for k, v in checks.items() if not v],
        }

    # -- Continuous monitoring --

    def start_monitoring(self, interval: float = 5.0):
        """Start continuous environment monitoring."""
        if self._monitoring:
            return
        self._monitoring = True

        def _loop():
            while self._monitoring:
                try:
                    self.read()
                except Exception:
                    pass
                time.sleep(interval)

        self._monitor_thread = threading.Thread(target=_loop, daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self):
        self._monitoring = False

    # -- Summary --

    def get_summary(self) -> str:
        """Human-readable environment summary."""
        if not self._last_reading:
            self.read()
        r = self._last_reading

        parts = []
        parts.append(f"📡 WiFi: {r.wifi_signal:.0f} dBm ({r.wifi_devices} devices)")
        parts.append(f"🔵 BT: {len(r.bluetooth_devices)} devices")
        parts.append(f"🔊 Audio: {r.audio_class} ({r.audio_level:.1%})")
        parts.append(f"👁️ Detection: {r.detection_count} sources")
        parts.append(f"🏷️ Threat: {r.threat_level}")
        parts.append(f"📍 Location: {r.location}")

        return "\n".join(parts)

    def get_status(self) -> dict[str, Any]:
        """Full status for API/UI."""
        if not self._last_reading:
            self.read()
        return {
            "reading": self._last_reading.to_dict() if self._last_reading else None,
            "ghost_mode": self.ghost_check(),
            "monitoring": self._monitoring,
        }
