from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class KaiLogger:
    root: Path
    events_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.events_path = self.root / "events.jsonl"
        if not self.events_path.exists():
            self.events_path.write_text("", encoding="utf-8")

    def log(self, event_type: str, **payload) -> None:
        entry = {
            "timestamp": utc_now(),
            "event_type": event_type,
            **payload,
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
