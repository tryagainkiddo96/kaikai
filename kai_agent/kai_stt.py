"""
Kai STT — speech-to-text for the companion.

Supports multiple backends:
- faster-whisper (best quality, needs GPU or CPU)
- Vosk (lightweight, offline, works everywhere)
- OpenAI Whisper API (if API key set)

Usage:
    from kai_agent.kai_stt import KaiSTT
    stt = KaiSTT()
    if stt.available:
        text = stt.listen(duration=5)
        print(f"You said: {text}")

Install:
    pip install faster-whisper   # best quality
    pip install vosk             # lightweight offline
    pip install sounddevice      # audio capture
"""

import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

try:
    import sounddevice as sd
    import numpy as np
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

try:
    import vosk
    import wave
    import json as json_mod
    HAS_VOSK = True
except ImportError:
    HAS_VOSK = False


class KaiSTT:
    def __init__(
        self,
        backend: str = "auto",
        model_path: str = "",
        sample_rate: int = 16000,
        language: str = "en",
    ):
        self.sample_rate = sample_rate
        self.language = language
        self._model = None
        self._vosk_model = None
        self._recording = False
        self._backend = self._detect_backend(backend)
        self._load_model(model_path)

    def _detect_backend(self, backend: str) -> str:
        if backend == "auto":
            if HAS_WHISPER:
                return "whisper"
            elif HAS_VOSK:
                return "vosk"
            return "none"
        return backend

    def _load_model(self, model_path: str):
        """Load the STT model."""
        if self._backend == "whisper" and HAS_WHISPER:
            try:
                # Use small model for balance of quality/speed
                size = os.environ.get("KAI_WHISPER_MODEL", "small")
                self._model = WhisperModel(size, device="auto", compute_type="auto")
            except Exception as e:
                print(f"[KAI_STT] Whisper load failed: {e}")
                self._backend = "none"

        elif self._backend == "vosk" and HAS_VOSK:
            try:
                if model_path and os.path.exists(model_path):
                    self._vosk_model = vosk.Model(model_path)
                else:
                    # Try default model path
                    default_path = os.path.expanduser("~/.vosk/model")
                    if os.path.exists(default_path):
                        self._vosk_model = vosk.Model(default_path)
                    else:
                        print("[KAI_STT] Vosk model not found. Download from https://alphacephei.com/vosk/models")
                        self._backend = "none"
            except Exception as e:
                print(f"[KAI_STT] Vosk load failed: {e}")
                self._backend = "none"

    @property
    def available(self) -> bool:
        return self._backend != "none" and HAS_AUDIO

    @property
    def backend_name(self) -> str:
        return self._backend

    def listen(self, duration: float = 5.0, silence_timeout: float = 2.0) -> Optional[str]:
        """
        Record audio and transcribe.

        Args:
            duration: Max recording length in seconds
            silence_timeout: Stop early if silence detected for this long

        Returns:
            Transcribed text or None
        """
        if not self.available:
            return None

        audio = self._record_audio(duration, silence_timeout)
        if audio is None or len(audio) == 0:
            return None

        return self._transcribe(audio)

    def transcribe_file(self, path: str) -> Optional[str]:
        """Transcribe an audio file."""
        if not self.available:
            return None

        try:
            import soundfile as sf
            audio, sr = sf.read(path, dtype="float32")
            if sr != self.sample_rate:
                # Resample if needed
                import scipy.signal
                audio = scipy.signal.resample(audio, int(len(audio) * self.sample_rate / sr))
            return self._transcribe(audio)
        except ImportError:
            # Fallback: use wave module
            try:
                with wave.open(path, "rb") as wf:
                    raw = wf.readframes(wf.getnframes())
                    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    return self._transcribe(audio)
            except Exception:
                pass
        except Exception:
            pass
        return None

    def _record_audio(self, duration: float, silence_timeout: float):
        """Record audio from microphone with silence detection."""
        if not HAS_AUDIO:
            return None

        try:
            frames = []
            silence_start = None
            chunk_size = int(self.sample_rate * 0.1)  # 100ms chunks
            total_chunks = int(duration / 0.1)
            threshold = 0.01  # Silence threshold

            def callback(indata, frame_count, time_info, status):
                frames.append(indata.copy())

            # Stream recording
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=chunk_size,
            )

            with stream:
                for _ in range(total_chunks):
                    data, _ = stream.read(chunk_size)
                    frames.append(data)

                    # Silence detection
                    rms = np.sqrt(np.mean(data ** 2))
                    if rms < threshold:
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start > silence_timeout:
                            break
                    else:
                        silence_start = None

            if not frames:
                return None

            audio = np.concatenate(frames, axis=0).flatten()
            return audio

        except Exception as e:
            print(f"[KAI_STT] Recording failed: {e}")
            return None

    def _transcribe(self, audio) -> Optional[str]:
        """Transcribe audio array."""
        try:
            if self._backend == "whisper":
                return self._transcribe_whisper(audio)
            elif self._backend == "vosk":
                return self._transcribe_vosk(audio)
        except Exception as e:
            print(f"[KAI_STT] Transcription failed: {e}")
        return None

    def _transcribe_whisper(self, audio) -> Optional[str]:
        if self._model is None:
            return None
        segments, info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        text = " ".join(seg.text for seg in segments).strip()
        return text if text else None

    def _transcribe_vosk(self, audio) -> Optional[str]:
        if self._vosk_model is None:
            return None

        # Convert float32 to int16 for Vosk
        audio_int16 = (audio * 32767).astype(np.int16)

        rec = vosk.KaldiRecognizer(self._vosk_model, self.sample_rate)
        rec.AcceptWaveform(audio_int16.tobytes())
        result = json_mod.loads(rec.FinalResult())
        return result.get("text", "").strip() or None

    def listen_and_respond(self, callback=None) -> Optional[str]:
        """
        Non-blocking listen: records in background, calls callback with text.

        Args:
            callback: function(str) called with transcribed text

        Returns:
            None (runs in background thread)
        """
        if not self.available:
            return None

        def _worker():
            text = self.listen(duration=10, silence_timeout=3)
            if text and callback:
                callback(text)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return None

    def continuous_listen(self, callback, wake_word: str = ""):
        """
        Continuous listening mode with optional wake word detection.

        Args:
            callback: function(str) called with each transcription
            wake_word: if set, only trigger callback when this word is heard
        """
        if not self.available:
            return

        def _worker():
            while True:
                text = self.listen(duration=5, silence_timeout=2)
                if text:
                    if wake_word:
                        if wake_word.lower() in text.lower():
                            # Strip wake word from the beginning
                            cleaned = text.lower().replace(wake_word.lower(), "").strip()
                            if cleaned:
                                callback(cleaned)
                    else:
                        callback(text)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
