import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _safe_load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        backup = path.with_suffix(path.suffix + f".bad-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}")
        try:
            path.rename(backup)
        except Exception:
            pass
        path.write_text(json.dumps(default, indent=2), encoding="utf-8")
        return default


def _atomic_write_text(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


@dataclass
class KaiMemory:
    root: Path
    profile_path: Path = field(init=False)
    notes_path: Path = field(init=False)
    sessions_path: Path = field(init=False)
    tasks_path: Path = field(init=False)

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.profile_path = self.root / "profile.json"
        self.notes_path = self.root / "notes.json"
        self.sessions_path = self.root / "sessions.jsonl"
        self.tasks_path = self.root / "tasks.json"
        if not self.profile_path.exists():
            _atomic_write_text(
                self.profile_path,
                json.dumps(
                    {
                        "name": "Kai",
                        "created_at": utc_now(),
                        "user_preferences": [],
                        "project_focus": [],
                    },
                    indent=2,
                ),
            )
        if not self.notes_path.exists():
            _atomic_write_text(self.notes_path, "[]\n")
        if not self.sessions_path.exists():
            _atomic_write_text(self.sessions_path, "")
        if not self.tasks_path.exists():
            _atomic_write_text(self.tasks_path, "[]\n")

    def load_profile(self) -> dict:
        profile = _safe_load_json(
            self.profile_path,
            {
                "name": "Kai",
                "created_at": utc_now(),
                "user_preferences": [],
                "project_focus": [],
            },
        )
        if not isinstance(profile, dict):
            profile = {"name": "Kai", "created_at": utc_now(), "user_preferences": [], "project_focus": []}
            _atomic_write_text(self.profile_path, json.dumps(profile, indent=2))
        return profile

    def load_notes(self) -> list[dict]:
        notes = _safe_load_json(self.notes_path, [])
        if not isinstance(notes, list):
            notes = []
            _atomic_write_text(self.notes_path, "[]\n")
        return notes

    def save_note(self, content: str, category: str = "general") -> dict:
        notes = self.load_notes()
        note = {
            "content": content.strip(),
            "category": category,
            "created_at": utc_now(),
        }
        notes.append(note)
        _atomic_write_text(self.notes_path, json.dumps(notes, indent=2))
        return note

    def update_profile(self, **updates) -> dict:
        profile = self.load_profile()
        for key, value in updates.items():
            profile[key] = value
        _atomic_write_text(self.profile_path, json.dumps(profile, indent=2))
        return profile

    def learn_preference(self, preference: str) -> None:
        preference = preference.strip()
        if not preference:
            return
        profile = self.load_profile()
        prefs = profile.setdefault("user_preferences", [])
        if preference not in prefs:
            prefs.append(preference)
            _atomic_write_text(self.profile_path, json.dumps(profile, indent=2))

    def learn_project_focus(self, focus: str) -> None:
        focus = focus.strip()
        if not focus:
            return
        profile = self.load_profile()
        items = profile.setdefault("project_focus", [])
        if focus not in items:
            items.append(focus)
            _atomic_write_text(self.profile_path, json.dumps(profile, indent=2))

    def append_session(self, role: str, content: str) -> None:
        entry = {"role": role, "content": content, "created_at": utc_now()}
        with self.sessions_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def load_tasks(self) -> list[dict]:
        tasks = _safe_load_json(self.tasks_path, [])
        if not isinstance(tasks, list):
            tasks = []
            _atomic_write_text(self.tasks_path, "[]\n")
        return tasks

    def save_tasks(self, tasks: list[dict]) -> None:
        _atomic_write_text(self.tasks_path, json.dumps(tasks, indent=2))

    def add_task(self, title: str, details: str = "") -> dict:
        tasks = self.load_tasks()
        task = {
            "id": f"task-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
            "title": title.strip(),
            "details": details.strip(),
            "status": "active" if not any(t.get("status") == "active" for t in tasks) else "queued",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        tasks.append(task)
        self.save_tasks(tasks)
        return task

    def get_active_task(self) -> dict | None:
        for task in self.load_tasks():
            if task.get("status") == "active":
                return task
        return None

    def set_active_task(self, task_id: str) -> dict | None:
        tasks = self.load_tasks()
        chosen = None
        for task in tasks:
            if task.get("status") == "active":
                task["status"] = "queued"
                task["updated_at"] = utc_now()
            if task.get("id") == task_id:
                task["status"] = "active"
                task["updated_at"] = utc_now()
                chosen = task
        self.save_tasks(tasks)
        return chosen

    def complete_task(self, task_id: str) -> dict | None:
        tasks = self.load_tasks()
        completed = None
        activated_next = False
        for task in tasks:
            if task.get("id") == task_id:
                task["status"] = "done"
                task["updated_at"] = utc_now()
                completed = task
        for task in tasks:
            if not activated_next and task.get("status") == "queued":
                task["status"] = "active"
                task["updated_at"] = utc_now()
                activated_next = True
                break
        self.save_tasks(tasks)
        return completed

    def summarize_tasks(self, limit: int = 6) -> str:
        tasks = self.load_tasks()[:limit]
        if not tasks:
            return "No saved tasks."
        lines = []
        for task in tasks:
            lines.append(f"[{task.get('status', 'queued')}] {task.get('title', '')}")
        return "\n".join(lines)

    def build_memory_context(self, limit: int = 8) -> str:
        profile = self.load_profile()
        notes = self.load_notes()[-limit:]
        tasks = self.load_tasks()[:limit]
        parts = [
            "Kai memory profile:",
            json.dumps(profile, indent=2),
            "Recent learned notes:",
            json.dumps(notes, indent=2),
            "Task queue:",
            json.dumps(tasks, indent=2),
        ]
        return "\n".join(parts)
