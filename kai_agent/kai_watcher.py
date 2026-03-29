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
            self._watch_social_timing,
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

    # ─── Social Timing (proactive conversations) ───

    def _watch_social_timing(self):
        """
        Periodically check if Kai should proactively speak up.
        Uses the social timing engine to detect the right moment,
        then generates a message via inner monologue or template.
        """
        time.sleep(30)  # Let everything settle on startup

        while self._running:
            try:
                if self.assistant and hasattr(self.assistant, 'social_timing'):
                    signal = self.assistant.social_timing.check_for_proactive_moment()
                    if signal:
                        # Get context for message generation
                        prompt = self.assistant.social_timing.get_proactive_prompt(signal)

                        # Check inner monologue for something to say
                        thought = None
                        if hasattr(self.assistant, 'inner_voice'):
                            thought = self.assistant.inner_voice.get_next_thought()

                        # Generate the message
                        message = self._generate_proactive_message(signal, thought, prompt)

                        if message:
                            self._emit("proactive", message, speak=False)

                            # Also deliver via the assistant's chat if available
                            self._deliver_proactive_via_chat(message)

                            # Mark thought as delivered if we used it
                            if thought and hasattr(self.assistant, 'inner_voice'):
                                self.assistant.inner_voice.mark_delivered(thought)

            except Exception:
                pass

            time.sleep(60)  # Check every minute

    def _generate_proactive_message(self, signal: dict, thought, prompt: str) -> str:
        """Generate a proactive message from signal + thought context."""
        msg_type = signal.get("message_type", "")

        # If we have an inner monologue thought, use it (with some probability)
        import random
        if thought and random.random() < 0.4:
            return thought.content

        # Otherwise use template messages based on signal type
        templates = {
            "morning_greeting": [
                "Morning. You're up early.",
                "Hey. Good to see you.",
                "Morning. Saiya's been watching the window.",
                "Morning. I dreamed about the dog park.",
                "Hey. The sun's in my eyes but I'm not moving.",
            ],
            "return_greeting": [
                "Hey. Been a while.",
                "Welcome back. I was getting bored.",
                "There you are.",
                "I counted the seconds. All twelve thousand of them.",
                "Saiya pretended she didn't notice you left. She did.",
            ],
            "overwork_break": [
                "You've been at this a while. Take a break?",
                "Even Kai takes naps. Just saying.",
                "Your eyes are gonna fall out. Step away for a minute.",
                "Yuki would have put her head on your lap by now. Take the hint.",
                "You've earned a walk. I'll come with.",
            ],
            "idle_checkin": [
                "Still there?",
                "Just checking in.",
                "I'm here if you need me.",
                "The house is quiet. I don't hate it.",
                "I've been watching the window. Nothing happened. Still worth it.",
            ],
            "late_night": [
                "It's late. I'm still up, but I'm a Shiba.",
                "Can't sleep? Me neither.",
                "The house is quiet tonight.",
                "3am thoughts hit different. I should know.",
                "Saiya's asleep. She'd be disappointed in both of us.",
            ],
            "unusual_hour": [
                "You're up at a weird time.",
                "Everything okay? You don't usually do this.",
                "This isn't like you. I'm not judging. I'm noting.",
            ],
        }

        options = templates.get(msg_type, [])
        if options:
            return random.choice(options)

        return ""

    def _deliver_proactive_via_chat(self, message: str) -> None:
        """Try to deliver a proactive message through the assistant's chat system."""
        if not self.assistant:
            return
        try:
            # Add to chat history so it appears in conversations
            if hasattr(self.assistant, 'history'):
                self.assistant.history.append({"role": "assistant", "content": message})
            # Log to session
            if hasattr(self.assistant, 'memory'):
                self.assistant.memory.append_session("assistant", f"[proactive] {message}")
            # Emit event for desktop panel / widget
            from kai_agent.bridge_client import send_event
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(send_event("kai_proactive", message=message))
            except Exception:
                pass
        except Exception:
            pass
