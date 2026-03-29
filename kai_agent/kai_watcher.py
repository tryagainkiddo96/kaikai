"""
Kai Proactive Awareness — the companion watches and speaks up.

Monitors:
- Idle time (user inactive for too long)
- New files (downloads, desktop)
- WiFi changes
- Time of day (greetings, reminders)
- Webcam motion/presence
- Clipboard changes
- Battery level (laptops)

And reacts:
- Speaks observations
- Emits events to the companion
- Triggers behaviors

Usage:
    from kai_agent.kai_watcher import KaiWatcher
    watcher = KaiWatcher(assistant=assistant)
    watcher.start()
"""

import os
import platform
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


class KaiWatcher:
    def __init__(self, assistant=None, workspace: Optional[Path] = None):
        self.assistant = assistant
        self.workspace = workspace or Path.cwd()
        self._running = False
        self._threads = []
        self._last_seen_motion = 0.0
        self._last_seen_person = 0.0
        self._last_wifi_ssid = ""
        self._last_download_count = 0
        self._greeted_today = False
        self._last_idle_notice = 0.0
        self._last_clipboard = ""
        self._callbacks = []

    def on_event(self, callback):
        """Register a callback for proactive events: callback(event_type, message)"""
        self._callbacks.append(callback)

    def _emit(self, event_type: str, message: str, speak: bool = True):
        """Emit an event to all registered callbacks and optionally speak."""
        for cb in self._callbacks:
            try:
                cb(event_type, message)
            except Exception:
                pass

        if speak and self.assistant:
            try:
                self.assistant.tts.speak(message)
            except Exception:
                pass

    def start(self):
        """Start all watchers."""
        if self._running:
            return
        self._running = True

        watchers = [
            self._watch_time_of_day,
            self._watch_idle_time,
            self._watch_downloads,
            self._watch_wifi,
            self._watch_battery,
            self._watch_clipboard,
        ]

        for watcher_fn in watchers:
            t = threading.Thread(target=watcher_fn, daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self):
        """Stop all watchers."""
        self._running = False

    # ─── Time of Day ───

    def _watch_time_of_day(self):
        """Morning greeting, evening wind-down."""
        while self._running:
            now = datetime.now()
            hour = now.hour

            # Morning greeting (8-9 AM)
            if 8 <= hour < 9 and not self._greeted_today:
                self._greeted_today = True
                self._emit("greeting", "Good morning. I've been keeping watch.")

            # Evening (9-10 PM)
            if 21 <= hour < 22 and now.minute < 5:
                if time.time() - self._last_idle_notice > 3600:
                    self._last_idle_notice = time.time()
                    self._emit("evening", "Getting late. Want me to dim things down?")

            # Reset greeting at midnight
            if hour == 0 and now.minute < 5:
                self._greeted_today = False

            time.sleep(300)  # Check every 5 minutes

    # ─── Idle Time ───

    def _watch_idle_time(self):
        """Notice when the user has been idle."""
        idle_threshold = 600  # 10 minutes
        last_check = time.time()

        while self._running:
            time.sleep(60)

            try:
                idle_secs = self._get_idle_time()
                if idle_secs and idle_secs > idle_threshold:
                    if time.time() - self._last_idle_notice > 1800:  # Don't nag more than every 30 min
                        self._last_idle_notice = time.time()
                        minutes = int(idle_secs / 60)
                        self._emit("idle", f"You've been idle for {minutes} minutes.")
            except Exception:
                pass

    def _get_idle_time(self) -> Optional[float]:
        """Get seconds since last user input."""
        system = platform.system()
        try:
            if system == "Linux":
                # Use xprintidle if available
                import subprocess
                result = subprocess.run(["xprintidle"], capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    return float(result.stdout.strip()) / 1000.0
            elif system == "Windows":
                import ctypes
                class LASTINPUTINFO(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
                lii = LASTINPUTINFO()
                lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
                if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                    millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
                    return millis / 1000.0
            elif system == "Darwin":
                import subprocess
                result = subprocess.run(
                    ["ioreg", "-c", "IOHIDSystem"],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    if "HIDIdleTime" in line:
                        val = line.split("=")[-1].strip()
                        return float(val) / 1_000_000_000.0  # nanoseconds
        except Exception:
            pass
        return None

    # ─── Downloads Folder ───

    def _watch_downloads(self):
        """Watch for new files in Downloads."""
        downloads = Path.home() / "Downloads"
        if not downloads.exists():
            return

        try:
            self._last_download_count = len(list(downloads.iterdir()))
        except Exception:
            return

        while self._running:
            time.sleep(15)
            try:
                current_count = len(list(downloads.iterdir()))
                if current_count > self._last_download_count:
                    diff = current_count - self._last_download_count
                    self._last_download_count = current_count

                    # Find the newest files
                    files = sorted(downloads.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True)
                    newest = files[0].name if files else "something"

                    self._emit("download", f"New file in Downloads: {newest}")
            except Exception:
                pass

    # ─── WiFi Changes ───

    def _watch_wifi(self):
        """Detect WiFi network changes."""
        # Import lazily to avoid circular
        time.sleep(10)  # Let system settle

        while self._running:
            try:
                from kai_agent.kai_signals import KaiSignals
                signals = KaiSignals()
                current = signals.get_current_wifi()
                ssid = current.get("ssid", "")

                if ssid and ssid != self._last_wifi_ssid:
                    if self._last_wifi_ssid:
                        self._emit("wifi", f"Switched WiFi: {self._last_wifi_ssid} → {ssid}")
                    else:
                        self._emit("wifi", f"Connected to {ssid}")
                    self._last_wifi_ssid = ssid
            except Exception:
                pass

            time.sleep(30)

    # ─── Battery ───

    def _watch_battery(self):
        """Monitor battery level."""
        while self._running:
            time.sleep(120)  # Check every 2 minutes
            try:
                level = self._get_battery_level()
                if level is not None:
                    if level <= 15 and level > 0:
                        self._emit("battery", f"Battery at {level}%. Getting low.")
                    elif level <= 5:
                        self._emit("battery", f"Battery critical: {level}%!")
            except Exception:
                pass

    def _get_battery_level(self) -> Optional[int]:
        system = platform.system()
        try:
            if system == "Linux":
                path = Path("/sys/class/power_supply/BAT0/capacity")
                if path.exists():
                    return int(path.read_text().strip())
            elif system == "Windows":
                import ctypes
                class SYSTEM_POWER_STATUS(ctypes.Structure):
                    _fields_ = [
                        ("ACLineStatus", ctypes.c_byte),
                        ("BatteryFlag", ctypes.c_byte),
                        ("BatteryLifePercent", ctypes.c_byte),
                        ("Reserved1", ctypes.c_byte),
                        ("BatteryLifeTime", ctypes.c_ulong),
                        ("BatteryFullLifeTime", ctypes.c_ulong),
                    ]
                sps = SYSTEM_POWER_STATUS()
                if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
                    if sps.BatteryLifePercent != 255:
                        return sps.BatteryLifePercent
            elif system == "Darwin":
                import subprocess
                result = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5)
                import re
                match = re.search(r"(\d+)%", result.stdout)
                if match:
                    return int(match.group(1))
        except Exception:
            pass
        return None

    # ─── Clipboard ───

    def _watch_clipboard(self):
        """Watch clipboard for changes."""
        while self._running:
            time.sleep(3)
            try:
                clipboard = self._get_clipboard()
                if clipboard and clipboard != self._last_clipboard and len(clipboard) > 10:
                    self._last_clipboard = clipboard
                    # Don't emit for very long text (probably code)
                    if len(clipboard) < 200:
                        preview = clipboard[:80].replace("\n", " ")
                        self._emit("clipboard", f"Copied: {preview}", speak=False)
            except Exception:
                pass

    def _get_clipboard(self) -> str:
        system = platform.system()
        try:
            if system == "Linux":
                import subprocess
                for cmd in [["xclip", "-selection", "clipboard", "-o"], ["xsel", "--clipboard", "--output"]]:
                    try:
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                        if result.returncode == 0:
                            return result.stdout
                    except FileNotFoundError:
                        continue
            elif system == "Windows":
                import subprocess
                result = subprocess.run(
                    ["powershell", "-Command", "Get-Clipboard"],
                    capture_output=True, text=True, timeout=3
                )
                return result.stdout.strip()
            elif system == "Darwin":
                import subprocess
                result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
                return result.stdout
        except Exception:
            pass
        return ""
