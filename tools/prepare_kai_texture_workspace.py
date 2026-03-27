from __future__ import annotations

from pathlib import Path
import shutil

import cv2
import numpy as np


ROOT = Path(r"C:\Users\7nujy6xc\OneDrive\Documents\Playground\kai-ai")
REFERENCE_DIR = ROOT / "kai_companion" / "assets" / "kai" / "reference"
VIDEO_FRAMES_DIR = REFERENCE_DIR / "video_frames"

PHOTO_SOURCES = {
    "kai_standing.jpg": Path(r"C:\Users\7nujy6xc\OneDrive\Desktop\120499416_1299613773712108_5269934955558643883_n.jpg"),
    "kai_two_dogs_left.jpg": Path(r"C:\Users\7nujy6xc\OneDrive\Desktop\487206273_2514021962271277_7775697273374682267_n.jpg"),
    "kai_lounging_1.jpg": Path(r"C:\Users\7nujy6xc\OneDrive\Desktop\93006975_1155668444773309_9094441284747132928_n.jpg"),
    "kai_lounging_2.jpg": Path(r"C:\Users\7nujy6xc\OneDrive\Desktop\93610588_1155668468106640_7166817540910350336_n.jpg"),
}

VIDEO_SOURCE = Path(r"C:\Users\7nujy6xc\Downloads\VID_20260318_080649254.mp4")
# `modelToUsed.glb` is retained only as the original external base-mesh lineage source
# that was used to derive the current `kai_textured.glb` photo replica.
MODEL_SOURCE = Path(r"C:\Users\7nujy6xc\Downloads\glb_6e3065c7-fc22-43ae-9d07-48cd87b34fac\modelToUsed.glb")
MODEL_TARGET = ROOT / "kai_companion" / "assets" / "kai" / "modelToUsed.glb"


def copy_sources() -> None:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    VIDEO_FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    for target_name, source in PHOTO_SOURCES.items():
        if source.exists():
            shutil.copy2(source, REFERENCE_DIR / target_name)

    if MODEL_SOURCE.exists():
        shutil.copy2(MODEL_SOURCE, MODEL_TARGET)


def extract_frames() -> list[Path]:
    if not VIDEO_SOURCE.exists():
        return []

    capture = cv2.VideoCapture(str(VIDEO_SOURCE))
    if not capture.isOpened():
        return []

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    desired_indices = np.linspace(0, max(total_frames - 1, 0), 8, dtype=int)
    written: list[Path] = []

    for i, frame_index in enumerate(desired_indices):
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame_index))
        ok, frame = capture.read()
        if not ok:
            continue
        output = VIDEO_FRAMES_DIR / f"model_ref_{i + 1:02d}.jpg"
        cv2.imwrite(str(output), frame)
        written.append(output)

    capture.release()
    return written


def build_contact_sheet(paths: list[Path]) -> None:
    if not paths:
        return

    tiles = []
    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            continue
        image = cv2.resize(image, (420, 420), interpolation=cv2.INTER_AREA)
        cv2.putText(
            image,
            path.stem,
            (18, 394),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        tiles.append(image)

    if not tiles:
        return

    rows = []
    for index in range(0, len(tiles), 2):
        pair = tiles[index:index + 2]
        if len(pair) == 1:
            pair.append(np.zeros_like(pair[0]))
        rows.append(np.hstack(pair))

    sheet = np.vstack(rows)
    cv2.imwrite(str(REFERENCE_DIR / "model_reference_contact_sheet.jpg"), sheet)


def main() -> None:
    copy_sources()
    extracted = extract_frames()
    build_contact_sheet(extracted)
    print(f"Prepared Kai texture workspace in: {REFERENCE_DIR}")


if __name__ == "__main__":
    main()
