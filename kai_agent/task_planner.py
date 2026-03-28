"""
Kai Task Planner
Breaks complex real-world tasks into executable steps.
Turns natural language requests into multi-step plans that Kai can execute.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class TaskStep:
    """A single step in a task plan."""
    step_id: int
    action: str  # browse, search, click, download, fill_form, read, write, email, run_command, wait
    description: str
    params: dict = field(default_factory=dict)
    status: str = "pending"  # pending, running, done, failed, skipped
    result: str = ""
    completed_at: str = ""


@dataclass
class TaskPlan:
    """A plan for completing a real-world task."""
    plan_id: str
    title: str
    description: str
    steps: list[TaskStep] = field(default_factory=list)
    status: str = "created"  # created, running, paused, completed, failed
    created_at: str = ""
    completed_at: str = ""
    files_downloaded: list[str] = field(default_factory=list)
    summary: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = utc_now()


class TaskPlanner:
    """
    Plans and manages multi-step real-world tasks.

    Usage:
        planner = TaskPlanner(workspace, tools)
        plan = planner.create_plan("Get the patient release form from St. Francis Hospital")
        result = planner.execute_plan(plan)
    """

    def __init__(self, workspace: Path, tools=None):
        self.workspace = workspace
        self.tools = tools
        self.plans_dir = workspace / "memory" / "plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.active_plan: TaskPlan | None = None

    def create_plan(self, task_description: str) -> TaskPlan:
        """Create a task plan from a natural language description."""
        task_lower = task_description.lower()
        plan_id = f"plan-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        # Detect task type and generate appropriate plan
        if self._is_hospital_form_task(task_lower):
            plan = self._plan_hospital_form(plan_id, task_description)
        elif self._is_portal_signup_task(task_lower):
            plan = self._plan_portal_signup(plan_id, task_description)
        elif self._is_research_task(task_lower):
            plan = self._plan_research(plan_id, task_description)
        elif self._is_file_task(task_lower):
            plan = self._plan_file_operation(plan_id, task_description)
        elif self._is_web_task(task_lower):
            plan = self._plan_web_browsing(plan_id, task_description)
        else:
            plan = self._plan_general(plan_id, task_description)

        self._save_plan(plan)
        self.active_plan = plan
        return plan

    def execute_plan(self, plan: TaskPlan, tools=None) -> dict:
        """Execute a task plan step by step."""
        t = tools or self.tools
        if not t:
            return {"ok": False, "error": "No tools available"}

        plan.status = "running"
        results = []

        for step in plan.steps:
            step.status = "running"
            try:
                result = self._execute_step(step, t)
                step.result = json.dumps(result) if isinstance(result, dict) else str(result)
                step.status = "done" if result.get("ok", True) else "failed"
                step.completed_at = utc_now()
                results.append({"step": step.step_id, "status": step.status, "result": result})

                # Capture downloaded files
                if result.get("path"):
                    plan.files_downloaded.append(result["path"])

            except Exception as exc:
                step.status = "failed"
                step.result = str(exc)
                step.completed_at = utc_now()
                results.append({"step": step.step_id, "status": "failed", "error": str(exc)})

                # Don't stop on failure — report and continue
                continue

        # Determine overall status
        failed_steps = [s for s in plan.steps if s.status == "failed"]
        done_steps = [s for s in plan.steps if s.status == "done"]

        if not failed_steps:
            plan.status = "completed"
        elif done_steps:
            plan.status = "partially_completed"
        else:
            plan.status = "failed"

        plan.completed_at = utc_now()
        plan.summary = self._build_summary(plan)
        self._save_plan(plan)

        return {
            "ok": plan.status in ("completed", "partially_completed"),
            "plan_id": plan.plan_id,
            "title": plan.title,
            "status": plan.status,
            "steps_completed": len(done_steps),
            "steps_failed": len(failed_steps),
            "files_downloaded": plan.files_downloaded,
            "summary": plan.summary,
            "results": results,
        }

    def get_plan_status(self, plan_id: str = None) -> dict:
        """Get the status of a plan."""
        plan = self.active_plan
        if plan_id:
            plan = self._load_plan(plan_id)
        if not plan:
            return {"ok": False, "error": "No active plan"}
        return {
            "ok": True,
            "plan_id": plan.plan_id,
            "title": plan.title,
            "status": plan.status,
            "steps": [{"id": s.step_id, "action": s.action, "desc": s.description, "status": s.status} for s in plan.steps],
            "summary": plan.summary,
        }

    # Step execution
    def _execute_step(self, step: TaskStep, tools) -> dict:
        """Execute a single step."""
        action = step.action
        params = step.params

        if action == "browse":
            return json.loads(tools.browse(params["url"]))
        elif action == "search":
            query = params.get("query", "")
            site = params.get("site", "")
            if hasattr(tools, "search_browser"):
                return json.loads(tools.search_browser(query, site))
            return json.loads(tools.search_web(query))
        elif action == "click_link":
            return json.loads(tools.click_link(params["text"]))
        elif action == "get_page_content":
            return json.loads(tools.get_page_content())
        elif action == "get_links":
            return json.loads(tools.get_page_links())
        elif action == "find_forms":
            return json.loads(tools.find_forms())
        elif action == "fill_form":
            return json.loads(tools.fill_form(params.get("data", {}), params.get("form_index", 0)))
        elif action == "download":
            return json.loads(tools.download_file(params.get("url"), params.get("filename")))
        elif action == "screenshot":
            return json.loads(tools.screenshot(params.get("filename", "kai_step.png")))
        elif action == "read_file":
            content = tools.read_file(params["path"])
            return {"ok": True, "content": content}
        elif action == "write_file":
            return json.loads(tools.write_file(params["path"], params["content"]))
        elif action == "run_command":
            return json.loads(tools.run_shell(params["command"]))
        elif action == "run_kali":
            return json.loads(tools.run_kali_session_command(params["command"]))
        elif action == "web_research":
            return json.loads(tools.search_web(params["query"]))
        elif action == "wait":
            import time
            time.sleep(params.get("seconds", 2))
            return {"ok": True, "message": f"Waited {params.get('seconds', 2)}s"}
        else:
            return {"ok": False, "error": f"Unknown action: {action}"}

    # Plan generators
    def _is_hospital_form_task(self, task: str) -> bool:
        keywords = ["form", "release", "paperwork", "download", "patient form", "medical form"]
        return any(kw in task for kw in keywords) and any(h in task for h in ["hospital", "clinic", "medical", "health", "st.", "st "])

    def _is_portal_signup_task(self, task: str) -> bool:
        keywords = ["portal", "sign up", "register", "account", "patient portal", "mychart"]
        return any(kw in task for kw in keywords)

    def _is_research_task(self, task: str) -> bool:
        keywords = ["find", "search", "look up", "what is", "information about", "research"]
        return any(kw in task for kw in keywords)

    def _is_file_task(self, task: str) -> bool:
        keywords = ["save", "create file", "write file", "organize", "rename"]
        return any(kw in task for kw in keywords)

    def _is_web_task(self, task: str) -> bool:
        keywords = ["website", "browse", "go to", "open", "navigate"]
        return any(kw in task for kw in keywords)

    def _plan_hospital_form(self, plan_id: str, task: str) -> TaskPlan:
        """Plan for downloading hospital patient forms."""
        hospital = self._extract_entity(task, ["hospital", "clinic", "medical center", "health"])
        location = self._extract_location(task)

        return TaskPlan(
            plan_id=plan_id,
            title=f"Get patient form from {hospital or 'hospital'}",
            description=task,
            steps=[
                TaskStep(1, "search", f"Search for {hospital} patient forms download", {"query": f"{hospital} {location} patient release form download pdf"}),
                TaskStep(2, "get_links", "Get links from search results"),
                TaskStep(3, "click_link", f"Click the most relevant form link", {"text": "form"}),
                TaskStep(4, "get_page_content", "Read the forms page"),
                TaskStep(5, "find_forms", "Check for downloadable forms on the page"),
                TaskStep(6, "download", "Download the patient release form", {"filename": f"{hospital}_release_form.pdf" if hospital else "patient_form.pdf"}),
                TaskStep(7, "screenshot", "Take screenshot of the download page"),
            ],
        )

    def _plan_portal_signup(self, plan_id: str, task: str) -> TaskPlan:
        """Plan for finding and navigating to a patient portal."""
        hospital = self._extract_entity(task, ["hospital", "clinic", "medical center", "health"])

        return TaskPlan(
            plan_id=plan_id,
            title=f"Find patient portal for {hospital or 'hospital'}",
            description=task,
            steps=[
                TaskStep(1, "search", f"Search for {hospital} patient portal", {"query": f"{hospital} patient portal sign up"}),
                TaskStep(2, "get_links", "Get search result links"),
                TaskStep(3, "click_link", "Click patient portal link", {"text": "portal"}),
                TaskStep(4, "get_page_content", "Read portal page"),
                TaskStep(5, "get_links", "Find sign-up or register link"),
                TaskStep(6, "click_link", "Click sign up or register", {"text": "sign up"}),
                TaskStep(7, "find_forms", "Check for registration forms"),
                TaskStep(8, "screenshot", "Screenshot the portal page"),
            ],
        )

    def _plan_research(self, plan_id: str, task: str) -> TaskPlan:
        """Plan for research tasks."""
        return TaskPlan(
            plan_id=plan_id,
            title=f"Research: {task[:60]}",
            description=task,
            steps=[
                TaskStep(1, "web_research", f"Research: {task}", {"query": task}),
                TaskStep(2, "search", f"Additional browser search", {"query": task}),
                TaskStep(3, "get_links", "Get relevant links"),
                TaskStep(4, "click_link", "Visit top result", {"text": ""}),
                TaskStep(5, "get_page_content", "Read page content"),
            ],
        )

    def _plan_file_operation(self, plan_id: str, task: str) -> TaskPlan:
        """Plan for file operations."""
        return TaskPlan(
            plan_id=plan_id,
            title=f"File task: {task[:60]}",
            description=task,
            steps=[
                TaskStep(1, "get_page_content", "Read current context"),
                TaskStep(2, "run_command", "Execute file operation", {"command": task}),
            ],
        )

    def _plan_web_browsing(self, plan_id: str, task: str) -> TaskPlan:
        """Plan for web browsing tasks."""
        url = self._extract_url(task)
        return TaskPlan(
            plan_id=plan_id,
            title=f"Browse: {url or task[:50]}",
            description=task,
            steps=[
                TaskStep(1, "browse", f"Navigate to {url or 'website'}", {"url": url or task}),
                TaskStep(2, "get_page_content", "Read page content"),
                TaskStep(3, "get_links", "Get available links"),
            ],
        )

    def _plan_general(self, plan_id: str, task: str) -> TaskPlan:
        """General plan for unrecognized tasks."""
        return TaskPlan(
            plan_id=plan_id,
            title=f"Task: {task[:60]}",
            description=task,
            steps=[
                TaskStep(1, "search", f"Research: {task}", {"query": task}),
                TaskStep(2, "get_links", "Get relevant links"),
                TaskStep(3, "get_page_content", "Read top result"),
            ],
        )

    # Helpers
    def _extract_entity(self, text: str, entity_types: list[str]) -> str:
        """Extract a named entity from text."""
        # Look for capitalized words that might be names
        words = text.split()
        for i, word in enumerate(words):
            if word[0].isupper() and word.lower() not in ["the", "a", "an", "get", "find", "from", "at", "in", "for", "and", "or"]:
                # Collect consecutive capitalized words
                entity = []
                for w in words[i:]:
                    if w[0].isupper() or w.lower() in ["of", "the", "and", "&"]:
                        entity.append(w)
                    else:
                        break
                if entity:
                    return " ".join(entity[:5])
        return ""

    def _extract_location(self, text: str) -> str:
        """Extract location from text."""
        # State abbreviations
        state_match = re.search(r'\b([A-Z]{2})\b', text)
        if state_match:
            return state_match.group(1)

        # City patterns
        city_match = re.search(r'in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', text)
        if city_match:
            return city_match.group(1)

        return ""

    def _extract_url(self, text: str) -> str:
        """Extract URL from text."""
        url_match = re.search(r'https?://[^\s]+', text)
        if url_match:
            return url_match.group(0)

        # Domain pattern
        domain_match = re.search(r'\b([a-zA-Z0-9-]+\.(?:com|org|net|edu|gov|io))\b', text)
        if domain_match:
            return domain_match.group(1)

        return ""

    def _build_summary(self, plan: TaskPlan) -> str:
        """Build a human-readable summary of the plan results."""
        done = [s for s in plan.steps if s.status == "done"]
        failed = [s for s in plan.steps if s.status == "failed"]

        lines = [f"Plan: {plan.title}", f"Status: {plan.status}", ""]

        if done:
            lines.append(f"Completed ({len(done)}/{len(plan.steps)}):")
            for s in done:
                lines.append(f"  ✅ Step {s.step_id}: {s.description}")

        if failed:
            lines.append(f"\nFailed ({len(failed)}):")
            for s in failed:
                lines.append(f"  ❌ Step {s.step_id}: {s.description} — {s.result[:100]}")

        if plan.files_downloaded:
            lines.append(f"\nDownloaded files:")
            for f in plan.files_downloaded:
                lines.append(f"  📄 {f}")

        return "\n".join(lines)

    def _save_plan(self, plan: TaskPlan):
        """Save plan to disk."""
        path = self.plans_dir / f"{plan.plan_id}.json"
        data = {
            "plan_id": plan.plan_id,
            "title": plan.title,
            "description": plan.description,
            "status": plan.status,
            "created_at": plan.created_at,
            "completed_at": plan.completed_at,
            "files_downloaded": plan.files_downloaded,
            "summary": plan.summary,
            "steps": [
                {
                    "step_id": s.step_id,
                    "action": s.action,
                    "description": s.description,
                    "params": s.params,
                    "status": s.status,
                    "result": s.result,
                    "completed_at": s.completed_at,
                }
                for s in plan.steps
            ],
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_plan(self, plan_id: str) -> TaskPlan | None:
        """Load plan from disk."""
        path = self.plans_dir / f"{plan_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            steps = [
                TaskStep(
                    step_id=s["step_id"],
                    action=s["action"],
                    description=s["description"],
                    params=s.get("params", {}),
                    status=s.get("status", "pending"),
                    result=s.get("result", ""),
                    completed_at=s.get("completed_at", ""),
                )
                for s in data.get("steps", [])
            ]
            return TaskPlan(
                plan_id=data["plan_id"],
                title=data["title"],
                description=data["description"],
                steps=steps,
                status=data.get("status", "created"),
                created_at=data.get("created_at", ""),
                completed_at=data.get("completed_at", ""),
                files_downloaded=data.get("files_downloaded", []),
                summary=data.get("summary", ""),
            )
        except Exception:
            return None
