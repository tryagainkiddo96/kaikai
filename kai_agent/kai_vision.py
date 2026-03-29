"""
Kai Vision — webcam awareness for the companion.

Captures frames from the webcam and provides:
- Motion detection (did something move?)
- Presence detection (is someone there?)
- Scene description (what's happening)
- Frame capture for AI analysis

Usage:
    from kai_agent.kai_vision import KaiVision
    vision = KaiVision()
    if vision.is_available:
        result = vision.capture_and_analyze()
        print(result)

Requires: opencv-python (pip install opencv-python)
Optional: PIL for frame saving
"""

import os
import time
import threading
from pathlib import Path
from typing import Optional

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class KaiVision:
    def __init__(self, camera_index: int = 0, workspace: Optional[Path] = None):
        self.camera_index = camera_index
        self.workspace = workspace or Path.cwd()
        self._cap = None
        self._last_frame = None
        self._prev_frame = None
        self._last_motion = 0.0
        self._running = False
        self._lock = threading.Lock()

    @property
    def is_available(self) -> bool:
        return HAS_CV2

    def start(self) -> bool:
        """Start the webcam capture."""
        if not HAS_CV2:
            return False
        try:
            self._cap = cv2.VideoCapture(self.camera_index)
            if not self._cap.isOpened():
                self._cap = None
                return False
            # Set lower resolution for performance
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._running = True
            return True
        except Exception:
            return False

    def stop(self):
        """Release the webcam."""
        self._running = False
        if self._cap:
            self._cap.release()
            self._cap = None

    def capture_frame(self):
        """Capture a single frame from the webcam."""
        if not self._cap or not self._running:
            if not self.start():
                return None
        try:
            ret, frame = self._cap.read()
            if ret:
                with self._lock:
                    self._prev_frame = self._last_frame
                    self._last_frame = frame
                return frame
        except Exception:
            pass
        return None

    def save_frame(self, filename: str = "kai_webcam.png") -> Optional[str]:
        """Capture and save a frame to disk."""
        frame = self.capture_frame()
        if frame is None:
            return None
        path = str(self.workspace / filename)
        try:
            if HAS_PIL:
                # Convert BGR to RGB for PIL
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                Image.fromarray(rgb).save(path)
            else:
                cv2.imwrite(path, frame)
            return path
        except Exception:
            return None

    def detect_motion(self, threshold: float = 25.0) -> dict:
        """Detect motion between current and previous frame."""
        frame = self.capture_frame()
        if frame is None or self._prev_frame is None:
            return {"motion": False, "level": 0.0, "areas": []}

        try:
            # Convert to grayscale
            gray_curr = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_prev = cv2.cvtColor(self._prev_frame, cv2.COLOR_BGR2GRAY)

            # Gaussian blur to reduce noise
            gray_curr = cv2.GaussianBlur(gray_curr, (21, 21), 0)
            gray_prev = cv2.GaussianBlur(gray_prev, (21, 21), 0)

            # Frame difference
            delta = cv2.absdiff(gray_prev, gray_curr)
            thresh = cv2.threshold(delta, threshold, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)

            # Find contours (motion areas)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            areas = []
            total_motion = 0
            for c in contours:
                area = cv2.contourArea(c)
                if area < 500:  # Filter small noise
                    continue
                x, y, w, h = cv2.boundingRect(c)
                areas.append({"x": int(x), "y": int(y), "w": int(w), "h": int(h), "area": int(area)})
                total_motion += area

            frame_area = frame.shape[0] * frame.shape[1]
            motion_level = total_motion / frame_area if frame_area > 0 else 0.0
            has_motion = motion_level > 0.005  # 0.5% of frame

            if has_motion:
                self._last_motion = time.time()

            return {
                "motion": has_motion,
                "level": round(motion_level, 4),
                "areas": areas[:5],  # Top 5 areas
                "total_pixels": total_motion,
            }
        except Exception as e:
            return {"motion": False, "level": 0.0, "areas": [], "error": str(e)}

    def detect_presence(self) -> dict:
        """Detect if a person is present in the frame (face detection)."""
        frame = self.capture_frame()
        if frame is None:
            return {"present": False, "faces": 0}

        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Load face cascade
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            if not os.path.exists(cascade_path):
                return {"present": False, "faces": 0, "error": "cascade not found"}

            face_cascade = cv2.CascadeClassifier(cascade_path)
            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(60, 60)
            )

            face_list = []
            for (x, y, w, h) in faces:
                face_list.append({"x": int(x), "y": int(y), "w": int(w), "h": int(h)})

            return {
                "present": len(face_list) > 0,
                "faces": len(face_list),
                "locations": face_list,
            }
        except Exception as e:
            return {"present": False, "faces": 0, "error": str(e)}

    def analyze_scene(self) -> dict:
        """Full scene analysis: motion + presence + brightness."""
        frame = self.capture_frame()
        if frame is None:
            return {"available": False}

        motion = self.detect_motion()
        presence = self.detect_presence()

        # Brightness analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean()) / 255.0

        # Scene summary
        events = []
        if motion["motion"]:
            events.append("motion_detected")
        if presence["present"]:
            events.append(f"person_detected({presence['faces']})")
        if brightness < 0.15:
            events.append("dark_room")
        elif brightness > 0.8:
            events.append("bright_light")
        time_since_motion = time.time() - self._last_motion
        if time_since_motion > 60:
            events.append("quiet_60s")

        return {
            "available": True,
            "motion": motion,
            "presence": presence,
            "brightness": round(brightness, 2),
            "events": events,
            "summary": self._build_summary(motion, presence, brightness),
        }

    def _build_summary(self, motion: dict, presence: dict, brightness: float) -> str:
        """Build a human-readable scene summary."""
        parts = []

        if presence["present"]:
            if presence["faces"] == 1:
                parts.append("Someone is here.")
            else:
                parts.append(f"{presence['faces']} people detected.")

        if motion["motion"]:
            level = motion["level"]
            if level > 0.05:
                parts.append("Significant movement.")
            elif level > 0.01:
                parts.append("Some movement.")
            else:
                parts.append("Slight movement.")

        if brightness < 0.15:
            parts.append("It's dark.")
        elif brightness < 0.3:
            parts.append("Low light.")

        if not parts:
            parts.append("All quiet.")

        return " ".join(parts)

    def get_gaze_direction(self) -> dict:
        """Estimate where the person is looking (left/center/right)."""
        presence = self.detect_presence()
        if not presence["present"] or not presence["locations"]:
            return {"direction": "none", "confidence": 0.0}

        frame = self.capture_frame()
        if frame is None:
            return {"direction": "none", "confidence": 0.0}

        # Use the largest face
        face = max(presence["locations"], key=lambda f: f["w"] * f["h"])
        face_center_x = face["x"] + face["w"] // 2
        frame_center_x = frame.shape[1] // 2

        # Determine horizontal position
        offset = (face_center_x - frame_center_x) / frame_center_x
        if offset < -0.2:
            direction = "left"
        elif offset > 0.2:
            direction = "right"
        else:
            direction = "center"

        return {
            "direction": direction,
            "offset": round(offset, 2),
            "face": face,
        }
