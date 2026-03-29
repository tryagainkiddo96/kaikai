"""
Kai Ambient Sounds — procedural audio for the companion.

Generates sounds programmatically (no audio files needed):
- Sniff sounds
- Tail wags (soft thumps)
- Alert huffs
- Paw steps
- Contented sighs

Usage:
    from kai_agent.kai_sounds import KaiSounds
    sounds = KaiSounds()
    sounds.sniff()
    sounds.wag()
"""

import math
import struct
import subprocess
import tempfile
import threading
import os


class KaiSounds:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.sample_rate = 22050

    def _play_wav(self, data: bytes):
        """Write temp WAV and play with system audio."""
        if not self.enabled:
            return
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(data)
                path = f.name
            # Platform playback
            if os.name == "nt":
                subprocess.run(
                    ["powershell", "-Command", f"(New-Object Media.SoundPlayer '{path}').PlaySync()"],
                    timeout=3, capture_output=True
                )
            else:
                for cmd in [["aplay", "-q", path], ["paplay", path], ["afplay", path]]:
                    if subprocess.run(cmd, timeout=3, capture_output=True).returncode == 0:
                        break
            os.unlink(path)
        except Exception:
            pass

    def _make_wav(self, samples: list[float]) -> bytes:
        """Convert float samples to 16-bit WAV bytes."""
        # Clamp
        clipped = [max(-1.0, min(1.0, s)) for s in samples]
        # Convert to 16-bit
        pcm = struct.pack(f"<{len(clipped)}h", *[int(s * 32767) for s in clipped])
        # WAV header
        data_size = len(pcm)
        header = struct.pack("<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + data_size, b"WAVE",
            b"fmt ", 16, 1, 1, self.sample_rate,
            self.sample_rate * 2, 2, 16,
            b"data", data_size)
        return header + pcm

    def sniff(self, blocking: bool = False):
        """Short sniffing sound — quick inhale bursts."""
        def _gen():
            samples = []
            duration = 0.3
            num_samples = int(self.sample_rate * duration)
            for i in range(num_samples):
                t = i / self.sample_rate
                # Two quick inhale bursts
                env = 0.0
                if 0.05 < t < 0.12:
                    env = math.sin((t - 0.05) / 0.07 * math.pi) * 0.3
                elif 0.15 < t < 0.22:
                    env = math.sin((t - 0.15) / 0.07 * math.pi) * 0.25
                # Filtered noise
                noise = (hash(i * 7919) % 1000 - 500) / 500.0
                samples.append(noise * env)
            self._play_wav(self._make_wav(samples))
        if blocking:
            _gen()
        else:
            threading.Thread(target=_gen, daemon=True).start()

    def wag(self, blocking: bool = False):
        """Soft thump for tail wag."""
        def _gen():
            samples = []
            duration = 0.15
            num_samples = int(self.sample_rate * duration)
            for i in range(num_samples):
                t = i / self.sample_rate
                # Low frequency thump
                freq = 60 + 40 * (1 - t / duration)
                val = math.sin(2 * math.pi * freq * t) * 0.4 * (1 - t / duration)
                samples.append(val)
            self._play_wav(self._make_wav(samples))
        if blocking:
            _gen()
        else:
            threading.Thread(target=_gen, daemon=True).start()

    def huff(self, blocking: bool = False):
        """Alert huff — short exhale."""
        def _gen():
            samples = []
            duration = 0.2
            num_samples = int(self.sample_rate * duration)
            for i in range(num_samples):
                t = i / self.sample_rate
                env = math.sin(t / duration * math.pi) * 0.35
                noise = (hash(i * 3571) % 1000 - 500) / 500.0
                # Low pass feel
                val = noise * env * (0.5 + 0.5 * math.sin(2 * math.pi * 200 * t))
                samples.append(val)
            self._play_wav(self._make_wav(samples))
        if blocking:
            _gen()
        else:
            threading.Thread(target=_gen, daemon=True).start()

    def paw_step(self, blocking: bool = False):
        """Soft paw step — tiny tap."""
        def _gen():
            samples = []
            duration = 0.06
            num_samples = int(self.sample_rate * duration)
            for i in range(num_samples):
                t = i / self.sample_rate
                env = (1 - t / duration) ** 3
                val = math.sin(2 * math.pi * 120 * t) * 0.2 * env
                samples.append(val)
            self._play_wav(self._make_wav(samples))
        if blocking:
            _gen()
        else:
            threading.Thread(target=_gen, daemon=True).start()

    def sigh(self, blocking: bool = False):
        """Contented sigh."""
        def _gen():
            samples = []
            duration = 0.6
            num_samples = int(self.sample_rate * duration)
            for i in range(num_samples):
                t = i / self.sample_rate
                env = math.sin(t / duration * math.pi) * 0.2
                noise = (hash(i * 2311) % 1000 - 500) / 500.0
                val = noise * env * (0.3 + 0.7 * math.sin(2 * math.pi * 150 * t))
                samples.append(val)
            self._play_wav(self._make_wav(samples))
        if blocking:
            _gen()
        else:
            threading.Thread(target=_gen, daemon=True).start()
