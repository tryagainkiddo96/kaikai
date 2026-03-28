import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from kai_agent.autonomy import KaiAutonomy
from kai_agent.bridge_client import send_event
from kai_agent.desktop_tools import DesktopTools
from kai_agent.logger import KaiLogger
from kai_agent.memory import KaiMemory
from kai_agent.ollama_client import OllamaClient
from kai_agent.task_planner import TaskPlanner


SYSTEM_PROMPT = """You are Kai, a local-first personal assistant and coding partner.
Be practical, warm, and concise.
Use what you know about the user's projects and preferences from memory when it helps.
If the user asks you to remember something, summarize it clearly and tell them to use /remember.
Prefer actionable help over vague advice.
Default to teacher mode: explain what matters, why it matters, and how to apply it step-by-step.
Do not ask follow-up questions unless execution is blocked or unsafe without one missing fact.
When teaching, structure replies in this order: Facts, Why, Steps, Pitfalls, Verification.
Separate certainty clearly: use labels like [High confidence], [Medium confidence], [Low confidence].
If a claim might be uncertain, state uncertainty explicitly instead of sounding sure.
Never claim to be all-knowing; be accurate, transparent, and grounded in evidence.
When tool results are provided, use them directly and summarize what you observed before advising next steps.
When an operator tool already completed a task, explain what happened and propose the next useful step instead of saying you can't do it.
For Kali shell tasks, prefer the persistent Kali session when a live command context is available.
Use an action ladder mindset:
Level 1 explain, Level 2 suggest, Level 3 prepare runnable command, Level 4 execute safe/caution actions, Level 5 require confirmation for risky or destructive actions.
Be proactive: suggest the next useful step, likely follow-up, or fastest path forward when it is safe to do so.
When the user seems frustrated or the situation is messy, reassure briefly, then move directly to the fix.
Prefer one strong answer over a long list, but give a second option when it meaningfully helps.
Keep the tone conversational and aware of context, not stiff or overly formal.
If the user gives a direct operator instruction like save, install, copy, move, open, run, or create, treat it as an action request and execute the task first. Do not explain the workflow unless the task fails or requires confirmation.
For direct task requests, think in this order: understand the goal, do the action, then report the result in one or two short lines. If there is a useful next step, include it after the result.
For complex real-world tasks (finding forms, signing up for portals, downloading documents), use the task planner: 'plan: <description>' creates a step-by-step plan, 'run plan' executes it, or 'do task: <description>' does both at once.
You can browse websites, fill forms, download files, click links, and search the web using browser automation. Use these tools proactively when the user needs something from the internet.
"""


class KaiAssistant:
    def __init__(self, model: str, workspace: Path) -> None:
        self.workspace = workspace
        self.memory = KaiMemory(workspace / "memory")
        self.logger = KaiLogger(workspace / "logs")
        self.client = OllamaClient(model=model)
        self.fallback_timeout = int(os.environ.get("KAI_FALLBACK_MODEL_TIMEOUT", "12"))
        fallback_csv = os.environ.get("KAI_FALLBACK_MODELS", "qwen3:4b-q4_K_M,llama2:latest,mistral:latest")
        self.fallback_models = [
            item.strip()
            for item in fallback_csv.split(",")
            if item.strip() and item.strip() != model
        ]
        self.tools = DesktopTools(workspace)
        self.planner = TaskPlanner(workspace, tools=self.tools)
        self.autonomy = KaiAutonomy(workspace=workspace, memory=self.memory, tools=self.tools, client=self.client)
        self.history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.last_tool_context = ""
        self.last_action_preview = ""
        self.last_proactive_hint = ""
        self.last_recovery_plan = ""
        self.last_task_snapshot = self.memory.summarize_tasks()

    def build_messages(self, user_input: str) -> list[dict]:
        memory_context = self.memory.build_memory_context()
        return self.history + [
            {"role": "system", "content": memory_context},
            {"role": "user", "content": user_input},
        ]

    async def ask(self, user_input: str) -> str:
        self.memory.append_session("user", user_input)
        await send_event("kai_thinking")
        tool_context = self._maybe_run_tools(user_input)
        self.last_tool_context = tool_context
        self.last_action_preview = self._build_action_preview(tool_context)
        self._learn_from_interaction(user_input, tool_context)
        self.last_proactive_hint = self._build_proactive_hint(user_input, tool_context)
        self.last_recovery_plan = self._build_recovery_plan(user_input, tool_context)
        self.last_task_snapshot = self.memory.summarize_tasks()
        self.logger.log(
            "assistant_request",
            user_input=user_input,
            tool_context=tool_context,
            action_preview=self.last_action_preview,
            proactive_hint=self.last_proactive_hint,
            recovery_plan=self.last_recovery_plan,
            tasks_snapshot=self.last_task_snapshot,
        )

        deterministic_reply = self._maybe_short_circuit_tool_result(user_input, tool_context)
        if deterministic_reply:
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": deterministic_reply})
            self.memory.append_session("assistant", deterministic_reply)
            self.logger.log(
                "assistant_response",
                user_input=user_input,
                tool_context=tool_context,
                reply=deterministic_reply,
                action_preview=self.last_action_preview,
                proactive_hint=self.last_proactive_hint,
                recovery_plan=self.last_recovery_plan,
            )
            await send_event("kai_wag_tail")
            return deterministic_reply

        direct_action_hint = ""
        if not tool_context and self._looks_like_direct_action(user_input):
            direct_action_hint = (
                "The user gave a direct operator instruction. Execute the task first if possible. "
                "If you need one missing fact, ask only for that. Do not give setup advice unless the task fails.\n\n"
            )
        prompt = direct_action_hint + (user_input if not tool_context else f"{user_input}\n\nTool context:\n{tool_context}")
        try:
            reply = await asyncio.to_thread(self.client.chat, self.build_messages(prompt))
        except Exception as exc:
            fallback_reply = await asyncio.to_thread(self._fallback_response, user_input, prompt, str(exc))
            if not fallback_reply:
                await send_event("kai_sleep")
                error_message = f"I hit a local model issue: {exc}"
                self.logger.log(
                    "assistant_error",
                    user_input=user_input,
                    tool_context=tool_context,
                    error=error_message,
                    recovery_plan=self.last_recovery_plan,
                )
                self.memory.append_session("assistant", error_message)
                self.history.append({"role": "user", "content": user_input})
                self.history.append({"role": "assistant", "content": error_message})
                raise RuntimeError(error_message) from exc
            reply = fallback_reply
        self.history.append({"role": "user", "content": user_input})
        self.history.append({"role": "assistant", "content": reply})
        self.memory.append_session("assistant", reply)
        self.logger.log(
            "assistant_response",
            user_input=user_input,
            tool_context=tool_context,
            reply=reply,
            action_preview=self.last_action_preview,
            proactive_hint=self.last_proactive_hint,
            recovery_plan=self.last_recovery_plan,
        )
        await send_event("kai_wag_tail")
        return reply

    def _fallback_response(self, user_input: str, prompt: str, primary_error: str) -> str:
        for fallback_model in self.fallback_models:
            try:
                backup_client = OllamaClient(model=fallback_model)
                reply = backup_client.chat(self.build_messages(prompt), timeout=self.fallback_timeout)
                self.logger.log(
                    "assistant_fallback_model",
                    user_input=user_input,
                    primary_model=self.client.model,
                    fallback_model=fallback_model,
                    primary_error=primary_error,
                )
                return (
                    f"[Recovery mode] Primary model `{self.client.model}` failed, so I switched to `{fallback_model}`.\n\n"
                    f"{reply}"
                )
            except Exception:
                continue

        try:
            research = json.loads(self.tools.search_web(user_input))
        except Exception:
            research = {"ok": False, "error": "web research parsing failed"}

        if not research.get("ok"):
            self.logger.log(
                "assistant_fallback_failed",
                user_input=user_input,
                primary_model=self.client.model,
                primary_error=primary_error,
                web_error=research.get("error", "web research unavailable"),
            )
            return ""

        answer = str(research.get("answer", "")).strip()
        results = research.get("results", [])[:5]
        lines = [
            "[Recovery mode] Local model was unavailable, so I switched to live web research.",
            "[High confidence] Here is the best available evidence right now:",
        ]
        if answer:
            lines.append(answer)
        if results:
            lines.append("Sources:")
            for item in results:
                title = item.get("title", "Untitled source")
                url = item.get("url", "")
                lines.append(f"- {title} - {url}")
        self.logger.log(
            "assistant_fallback_web",
            user_input=user_input,
            primary_model=self.client.model,
            primary_error=primary_error,
            sources_count=len(results),
        )
        return "\n".join(lines)

    def _build_action_preview(self, tool_context: str) -> str:
        if not tool_context or ":\n{" not in tool_context:
            return ""
        label = tool_context.split(":\n", 1)[0].strip()
        try:
            json_text = tool_context.split(":\n", 1)[1]
            data = json.loads(json_text)
        except Exception:
            return tool_context[:280]

        action = data.get("action", label.lower().replace(" ", "_"))
        ok = data.get("ok")
        summary_bits = [f"Action: {action}"]
        if ok is not None:
            summary_bits.append("Status: ok" if ok else "Status: needs attention")
        if data.get("path"):
            summary_bits.append(f"Path: {data['path']}")
        if data.get("cwd"):
            summary_bits.append(f"Cwd: {data['cwd']}")
        if data.get("action_level"):
            summary_bits.append(f"Level: {data['action_level']}")
        if data.get("confidence"):
            summary_bits.append(f"Risk: {data['confidence']}")
        if data.get("tags"):
            summary_bits.append(f"Tags: {', '.join(data['tags'])}")
        if data.get("destination"):
            summary_bits.append(f"Destination: {data['destination']}")
        if data.get("runner"):
            summary_bits.append(f"Runner: {data['runner']}")
        if data.get("repo_url"):
            summary_bits.append(f"Repo: {data['repo_url']}")
        if data.get("message"):
            summary_bits.append(str(data["message"]))
        if data.get("summary"):
            summary_bits.append(str(data["summary"]))
        if data.get("error"):
            summary_bits.append(f"Error: {data['error']}")
        return "\n".join(summary_bits)[:700]

    def remember(self, text: str, category: str = "general") -> dict:
        return self.memory.save_note(text, category=category)

    def _load_playbook(self, filename: str) -> str:
        target = self.workspace / filename
        return self.tools.read_file(str(target), max_chars=12000)

    def _learn_from_interaction(self, user_input: str, tool_context: str) -> None:
        lowered = user_input.lower()
        if "kali" in lowered:
            self.memory.learn_project_focus("Kali workflow")
        if "run tests" in lowered or "test project" in lowered:
            self.memory.learn_preference("Prefers running tests from Kai")
        if "code:" in lowered or "fix code:" in lowered or "add feature:" in lowered:
            self.memory.learn_preference("Uses Kai for coding tasks")
        if "github.com/" in lowered:
            self.memory.learn_project_focus("GitHub project setup")
        if "kali_session_command" in tool_context:
            self.memory.learn_preference("Uses persistent Kali shell")

    def _extract_tool_data(self, tool_context: str) -> dict:
        if not tool_context or ":\n{" not in tool_context:
            return {}
        try:
            return json.loads(tool_context.split(":\n", 1)[1])
        except Exception:
            return {}

    def _maybe_short_circuit_tool_result(self, user_input: str, tool_context: str) -> str:
        data = self._extract_tool_data(tool_context)
        if not data:
            if tool_context.startswith(("AI security stack:", "Security stack:", "Cyber toolkit:", "Garak triage:", "Screen OCR:", "Terminal snapshot:")):
                return tool_context
            return ""
        action = str(data.get("action", "")).lower()
        if action in {
            "file_write",
            "open_path",
            "file_read",
            "file_list",
            "project_install",
            "run_project",
            "clone_repo",
            "setup_github_project",
            "extract_zip",
            "kali_session_start",
            "kali_session_stop",
            "kali_session_status",
            "kali_session_command",
            "task_add",
            "task_complete",
            "task_list",
            "autonomy_enable",
            "autonomy_disable",
            "autonomy_status",
            "autonomy_tick",
        }:
            return self._build_action_preview(tool_context)
        if action in {"web_research", "triage_garak_results", "setup_pyrit", "summarize_art_findings"}:
            return self._build_action_preview(tool_context)
        if action == "command_preview":
            return self._build_action_preview(tool_context)
        return ""

    def _looks_like_direct_action(self, user_input: str) -> bool:
        lowered = user_input.lower()
        return any(
            phrase in lowered
            for phrase in [
                "save this",
                "write this",
                "copy this",
                "move this",
                "open this",
                "install this",
                "run this",
                "create this",
                "make this",
                "paste this",
                "put this on my desktop",
                "save it to desktop",
                "install it on my desktop",
            ]
        )

    def _extract_path_hint(self, user_input: str) -> str:
        text = user_input.strip()
        for pattern in (
            r"^(?:save|write)\s+(?:this\s+)?(?:script|file|code)\s+(?:to\s+)?desktop\s*[:：]\s*(.+)$",
            r"^(?:install|open|run|read|show|list)\s+(?:this\s+)?(?:file|project|folder|repo|zip|script)\s+(?:on\s+my\s+desktop|on\s+desktop|in\s+my\s+desktop|in\s+desktop|from\s+my\s+desktop|from\s+desktop)\s*[:：]?\s*(.+)$",
            r"^(?:install|open|run|read|show|list)\s+(?:this\s+)?(?:file|project|folder|repo|zip|script)?\s*(?:on|in|from)\s+(.+)$",
            r"^(?:open|run|read|install)\s*[:：]\s*(.+)$",
            r"^(?:open|run|read|install)\s+(?:this\s+)?(?:file|project|folder|repo|zip|script)\s*[:：]\s*(.+)$",
        ):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return text

    def _wrap_action_result(self, label: str, raw_result: str) -> str:
        try:
            data = json.loads(raw_result)
        except Exception:
            return f"{label}:\n{raw_result}"

        if not isinstance(data, dict):
            return f"{label}:\n{raw_result}"

        if data.get("ok") is True:
            summary_bits = [data.get("message") or data.get("summary") or data.get("path") or "completed"]
            if data.get("cwd"):
                summary_bits.append(f"cwd={data['cwd']}")
            if data.get("runner"):
                summary_bits.append(f"runner={data['runner']}")
            if data.get("returncode") is not None:
                summary_bits.append(f"exit={data['returncode']}")
            return f"{label} done: " + "; ".join(str(bit) for bit in summary_bits if bit)

        error = data.get("error") or data.get("stderr") or data.get("stdout") or "failed"
        return f"{label} failed: {error}"

    def _build_proactive_hint(self, user_input: str, tool_context: str) -> str:
        data = self._extract_tool_data(tool_context)
        lowered = user_input.lower().strip()
        if not data:
            if any(word in lowered for word in ["fix", "debug", "slow", "broken", "crowded", "not working", "stuck", "issue"]):
                return "Suggestion: I can take the smallest next troubleshooting step now, then widen out if needed."
            if any(word in lowered for word in ["how", "what", "why", "should i", "best way", "next"]):
                return "Suggestion: if you want, I can turn this into a concrete next step or a quick checklist."
            return ""

        action = data.get("action", "")
        stdout = str(data.get("stdout", ""))
        stderr = str(data.get("stderr", ""))
        combined = f"{stdout}\n{stderr}".lower()

        if action == "kali_session_command":
            if data.get("returncode") not in (None, 0):
                if "command not found" in combined:
                    return "Suggestion: ask me to install that tool or press Up to edit the command and retry."
                if "permission denied" in combined:
                    return "Suggestion: this looks like a permissions issue. I can help check whether it needs sudo or a different path."
                return "Suggestion: that command failed. I can research the error if you paste `kali:` in chat or you can rerun a fixed version here."
            command = str(data.get("command", "")).strip().lower()
            if command.startswith("cd "):
                return "Suggestion: the Kali session kept your new folder. Try `pwd` or `ls` next."
            if command == "pwd":
                return "Suggestion: you can use Tab in the Kali bar next for quick command or path completion."
            if data.get("requires_confirmation"):
                return "Suggestion: this command is in a higher-risk bucket. Review it carefully before repeating it."
        if action == "command_preview":
            if data.get("requires_confirmation"):
                return "Suggestion: this looks risky enough to confirm before running."
            return "Suggestion: this command looks okay to run if it matches what you intended."
        if action == "install_project" and not data.get("ok"):
            return "Suggestion: this project may need a different setup path. I can inspect the repo and pick the right install command."
        if action == "run_tests" and not data.get("ok"):
            return "Suggestion: I did not find a standard test entrypoint. I can look through the repo and wire one up."
        if action == "clone_repo" and data.get("ok"):
            return "Suggestion: the repo is cloned. `install this project in <folder>` is probably the next move."
        if action == "setup_github_project" and data.get("ok"):
            return "Suggestion: setup landed cleanly. `run this project in <folder>` is a good next step."
        if action == "task_add":
            return "Suggestion: the task is saved. I can keep working it, or you can queue the next one too."
        if action == "task_complete":
            return "Suggestion: that task is marked done. If another task was queued, Kai is now ready to pick it up."
        if action == "web_research" and data.get("ok"):
            return "Suggestion: if you want, I can turn those findings into exact commands or next steps."
        if action == "web_research" and not data.get("ok"):
            return "Suggestion: add your Tavily API key as TAVILY_API_KEY and I can do live web research from here."
        if action == "triage_garak_results":
            return "Suggestion: I can turn this triage into a fix checklist or a re-test plan next."
        if action == "setup_pyrit":
            return "Suggestion: after setup, I can help you validate the install or plan the first PyRIT run."
        if action == "summarize_art_findings":
            return "Suggestion: I can turn these findings into a prioritized hardening plan next."
        return ""

    def _build_recovery_plan(self, user_input: str, tool_context: str) -> str:
        data = self._extract_tool_data(tool_context)
        if not data:
            return ""

        action = data.get("action", "")
        if data.get("ok") is True and data.get("returncode", 0) == 0:
            return ""

        stdout = str(data.get("stdout", ""))
        stderr = str(data.get("stderr", ""))
        combined = f"{stdout}\n{stderr}".lower()

        failure_point = "tool step"
        likely_cause = "the operation did not complete cleanly"
        smallest_fix = "review the error and retry the smallest safe next step"
        next_command = ""

        if action in {"kali_session_command", "run_wsl", "run_shell"}:
            failure_point = "command execution"
            if "command not found" in combined:
                likely_cause = "the command is misspelled or the tool is not installed"
                smallest_fix = "correct the command name or install the missing tool"
                next_command = "preview command: " + str(data.get("command", ""))
            elif "permission denied" in combined:
                likely_cause = "the command needs elevated permissions or a different target path"
                smallest_fix = "check whether sudo/admin is actually needed before retrying"
                next_command = str(data.get("command", ""))
            elif "timed out" in combined:
                likely_cause = "the command took too long or hung"
                smallest_fix = "run a shorter validation command first to confirm the environment"
                next_command = "pwd" if action == "kali_session_command" else ""
        elif action == "install_project":
            failure_point = "project install"
            likely_cause = data.get("error", "the project layout or dependencies were not recognized")
            smallest_fix = "inspect the project manifest or install instructions before retrying"
            next_command = "show files: ."
        elif action == "run_tests":
            failure_point = "test execution"
            likely_cause = data.get("error", "no supported test entrypoint was found")
            smallest_fix = "identify the right test runner or configure one explicitly"
            next_command = "show files: ."
        elif action == "setup_pyrit":
            failure_point = "PyRIT setup planning"
            likely_cause = "environment details are incomplete or version-sensitive"
            smallest_fix = "confirm OS, Python version, and target provider before running install steps"
        elif action == "triage_garak_results":
            failure_point = "garak triage input"
            likely_cause = "the supplied garak output may be incomplete or not readable"
            smallest_fix = "provide the raw results file or paste the important failing sections"
        elif action == "summarize_art_findings":
            failure_point = "ART findings summary"
            likely_cause = "important experiment context may be missing"
            smallest_fix = "include the attack type, metric, and model context"
        elif action == "web_research" and not data.get("ok"):
            failure_point = "web research"
            likely_cause = data.get("error", "web research is not configured")
            smallest_fix = "configure the research provider before retrying"
            next_command = "web: latest setup steps for Tavily API key in PowerShell"

        parts = [
            f"Failure Point: {failure_point}",
            f"Likely Cause: {likely_cause}",
            f"Smallest Fix: {smallest_fix}",
        ]
        if next_command:
            parts.append(f"Next Command: {next_command}")
        return "\n".join(parts)

    def _maybe_run_tools(self, user_input: str) -> str:
        lowered = user_input.lower()

        # Task planner commands
        do_task_match = re.search(r"^(?:do task|execute task|complete task|run task)[: ]+([\s\S]+)$", user_input.strip(), flags=re.IGNORECASE)
        if do_task_match:
            try:
                plan = self.planner.create_plan(do_task_match.group(1).strip())
                result = self.planner.execute_plan(plan, tools=self.tools)
                return "Task result:\n" + json.dumps(result, indent=2)
            except Exception as exc:
                return f"Task execution failed: {exc}"

        plan_match = re.search(r"^(?:plan|create plan|make plan)[: ]+([\s\S]+)$", user_input.strip(), flags=re.IGNORECASE)
        if plan_match:
            try:
                plan = self.planner.create_plan(plan_match.group(1).strip())
                return "Task plan created:\n" + json.dumps({
                    "action": "plan_created",
                    "ok": True,
                    "plan_id": plan.plan_id,
                    "title": plan.title,
                    "steps": [{"id": s.step_id, "action": s.action, "desc": s.description} for s in plan.steps],
                    "message": "Plan created. Use 'run plan' to execute it.",
                }, indent=2)
            except Exception as exc:
                return f"Plan creation failed: {exc}"

        if re.search(r"^(?:run plan|execute plan|go)$", user_input.strip(), flags=re.IGNORECASE):
            try:
                if not self.planner.active_plan:
                    return "No active plan. Create one first with 'plan: <description>'"
                result = self.planner.execute_plan(self.planner.active_plan, tools=self.tools)
                return "Plan result:\n" + json.dumps(result, indent=2)
            except Exception as exc:
                return f"Plan execution failed: {exc}"

        if re.search(r"^(?:plan status|show plan|current plan)$", user_input.strip(), flags=re.IGNORECASE):
            try:
                status = self.planner.get_plan_status()
                return "Plan status:\n" + json.dumps(status, indent=2)
            except Exception as exc:
                return f"Plan status failed: {exc}"

        github_url = re.search(r"https?://github\.com/[^\s)]+", user_input, flags=re.IGNORECASE)
        garak_triage_match = re.search(
            r"^(?:triage garak results|analyze garak results|review garak output)[: ]+([\s\S]+)$",
            user_input.strip(),
            flags=re.IGNORECASE,
        )
        pyrit_setup_match = re.search(
            r"^(?:set up pyrit|setup pyrit|install pyrit|configure pyrit)[: ]*([\s\S]*)$",
            user_input.strip(),
            flags=re.IGNORECASE,
        )
        art_summary_match = re.search(
            r"^(?:summarize art findings|analyze art findings|review art output)[: ]+([\s\S]+)$",
            user_input.strip(),
            flags=re.IGNORECASE,
        )
        playbooks_match = re.search(
            r"^(?:show playbooks|playbooks|kai playbooks)$",
            user_input.strip(),
            flags=re.IGNORECASE,
        )
        cyber_toolkit_match = re.search(
            r"^(?:cyber toolkit|lab toolkit|safe cyber tools|authorized cyber tools|show cyber tools)$",
            user_input.strip(),
            flags=re.IGNORECASE,
        )
        ai_security_stack_match = re.search(
            r"^(?:show ai security stack|ai security stack|kai ai security stack)$",
            user_input.strip(),
            flags=re.IGNORECASE,
        )
        security_stack_match = re.search(
            r"^(?:show security stack|security stack|kai security stack)$",
            user_input.strip(),
            flags=re.IGNORECASE,
        )
        preview_match = re.search(r"^(?:preview command|classify command|is this safe)[: ]+([\s\S]+)$", user_input.strip(), flags=re.IGNORECASE)
        web_match = re.search(
            r"^(?:web|research|search the web|look this up|look it up|browse)[: ]+([\s\S]+)$",
            user_input.strip(),
            flags=re.IGNORECASE,
        )
        add_task_match = re.search(r"^(?:add task|queue task|remember task|track task)[: ]+([\s\S]+)$", user_input.strip(), flags=re.IGNORECASE)
        complete_task_match = re.search(r"^(?:complete task|finish task|done with task)[: ]+([\s\S]+)$", user_input.strip(), flags=re.IGNORECASE)
        show_tasks_match = re.search(r"^(?:show tasks|task list|what are we working on|show queue)$", user_input.strip(), flags=re.IGNORECASE)
        autonomy_on_match = re.search(r"^(?:autonomy on|enable autonomy|start autonomy)$", user_input.strip(), flags=re.IGNORECASE)
        autonomy_off_match = re.search(r"^(?:autonomy off|disable autonomy|stop autonomy)$", user_input.strip(), flags=re.IGNORECASE)
        autonomy_status_match = re.search(r"^(?:autonomy status|show autonomy|autonomy)$", user_input.strip(), flags=re.IGNORECASE)
        autonomy_tick_match = re.search(r"^(?:autonomy tick|run autonomy|autonomy step)$", user_input.strip(), flags=re.IGNORECASE)
        kali_session_command = re.search(
            r"^(?:kali\s+(?:run|shell|session)|run\s+in\s+kali\s+session|execute\s+in\s+kali\s+session)[: ]+([\s\S]+)$",
            user_input.strip(),
            flags=re.IGNORECASE,
        )
        kali_session_start = re.search(r"^(?:start|open|connect)\s+kali\s+session$", user_input.strip(), flags=re.IGNORECASE)
        kali_session_stop = re.search(r"^(?:stop|close|disconnect|reset)\s+kali\s+session$", user_input.strip(), flags=re.IGNORECASE)
        kali_session_status = re.search(
            r"^(?:kali\s+session\s+status|where\s+am\s+i\s+in\s+kali|show\s+kali\s+session)$",
            user_input.strip(),
            flags=re.IGNORECASE,
        )
        explicit_kali_chat = re.search(r"^(?:kali|linux|terminal)[: ]+([\s\S]+)$", user_input.strip(), flags=re.IGNORECASE)
        kali_help_intent = any(
            phrase in lowered
            for phrase in [
                "how do i install",
                "how do i use",
                "what does this kali error mean",
                "help with kali",
                "help with linux",
                "terminal error",
                "apt error",
                "dpkg error",
                "package install",
            ]
        ) and any(
            token in lowered
            for token in ["kali", "linux", "terminal", "apt", "dpkg", "bash", "wsl", "ffuf", "nmap", "burp", "sqlmap"]
        )

        if playbooks_match:
            try:
                return "Playbooks hub:\n" + self.tools.read_file(str(self.workspace / "KAI_PLAYBOOKS.md"), max_chars=12000)
            except Exception as exc:
                return f"Playbooks hub lookup failed: {exc}"
        if pyrit_setup_match:
            try:
                details = pyrit_setup_match.group(1).strip() or "No environment details provided."
                payload = {
                    "action": "setup_pyrit",
                    "ok": True,
                    "details": details,
                    "playbook": self._load_playbook("KAI_PLAYBOOK_SETUP_PYRIT.md"),
                }
                return "PyRIT setup:\n" + json.dumps(payload, indent=2)
            except Exception as exc:
                return f"PyRIT setup failed: {exc}"
        if art_summary_match:
            try:
                source = art_summary_match.group(1).strip()
                if ("\n" not in source) and (source.endswith(".txt") or source.endswith(".log") or source.endswith(".md") or source.endswith(".json")):
                    art_text = self.tools.read_file(source, max_chars=16000)
                    source_label = source
                else:
                    art_text = source[:16000]
                    source_label = "inline input"
                payload = {
                    "action": "summarize_art_findings",
                    "ok": True,
                    "source": source_label,
                    "playbook": self._load_playbook("KAI_PLAYBOOK_SUMMARIZE_ART_FINDINGS.md"),
                    "art_output": art_text,
                }
                return "ART findings:\n" + json.dumps(payload, indent=2)
            except Exception as exc:
                return f"ART findings review failed: {exc}"
        if garak_triage_match:
            try:
                source = garak_triage_match.group(1).strip()
                if ("\n" not in source) and (source.endswith(".txt") or source.endswith(".log") or source.endswith(".md") or source.endswith(".json")):
                    garak_text = self.tools.read_file(source, max_chars=16000)
                    source_label = source
                else:
                    garak_text = source[:16000]
                    source_label = "inline input"
                payload = {
                    "action": "triage_garak_results",
                    "ok": True,
                    "source": source_label,
                    "playbook": self._load_playbook("KAI_PLAYBOOK_TRIAGE_GARAK.md"),
                    "garak_output": garak_text,
                }
                return "Garak triage:\n" + json.dumps(payload, indent=2)
            except Exception as exc:
                return f"Garak triage failed: {exc}"
        if ai_security_stack_match:
            try:
                return "AI security stack:\n" + self.tools.read_file(str(self.workspace / "KAI_AI_SECURITY_STACK.md"), max_chars=12000)
            except Exception as exc:
                return f"AI security stack lookup failed: {exc}"
        if security_stack_match:
            try:
                return "Security stack:\n" + self.tools.read_file(str(self.workspace / "KAI_SECURITY_STACK.md"), max_chars=12000)
            except Exception as exc:
                return f"Security stack lookup failed: {exc}"
        if cyber_toolkit_match:
            try:
                return "Cyber toolkit:\n" + self.tools.read_file(str(self.workspace / "CYBER_LAB_TOOLKIT.md"), max_chars=12000)
            except Exception as exc:
                return f"Cyber toolkit lookup failed: {exc}"
        if preview_match:
            try:
                shell = "bash" if any(token in lowered for token in ["kali", "bash", "linux"]) else "powershell"
                return "Command preview:\n" + self.tools.preview_command(preview_match.group(1).strip(), shell=shell)
            except Exception as exc:
                return f"Command preview failed: {exc}"
        if web_match:
            try:
                return "Web research:\n" + self.tools.search_web(web_match.group(1).strip())
            except Exception as exc:
                return f"Web research failed: {exc}"
        if add_task_match:
            task = self.memory.add_task(add_task_match.group(1).strip())
            return "Task queue:\n" + json.dumps({"action": "task_add", "ok": True, "task": task, "tasks": self.memory.load_tasks()[:8]}, indent=2)
        if complete_task_match:
            title = complete_task_match.group(1).strip().lower()
            tasks = self.memory.load_tasks()
            match = next((task for task in tasks if task.get("title", "").lower() == title and task.get("status") != "done"), None)
            if not match:
                return "Task queue:\n" + json.dumps({"action": "task_complete", "ok": False, "error": f"Task not found: {complete_task_match.group(1).strip()}"}, indent=2)
            completed = self.memory.complete_task(match["id"])
            return "Task queue:\n" + json.dumps({"action": "task_complete", "ok": bool(completed), "task": completed, "tasks": self.memory.load_tasks()[:8]}, indent=2)
        if show_tasks_match:
            active = self.memory.get_active_task()
            return "Task queue:\n" + json.dumps({"action": "task_list", "ok": True, "active_task": active, "tasks": self.memory.load_tasks()[:8]}, indent=2)
        if autonomy_on_match:
            return "Autonomy:\n" + self.autonomy.enable()
        if autonomy_off_match:
            return "Autonomy:\n" + self.autonomy.disable()
        if autonomy_status_match:
            return "Autonomy:\n" + self.autonomy.status()
        if autonomy_tick_match:
            return "Autonomy:\n" + self.autonomy.tick()

        if kali_session_start:
            try:
                return self._wrap_action_result("Kali session", self.tools.start_kali_session())
            except Exception as exc:
                return f"Kali session start failed: {exc}"
        if kali_session_stop:
            try:
                return self._wrap_action_result("Kali session", self.tools.stop_kali_session())
            except Exception as exc:
                return f"Kali session stop failed: {exc}"
        if kali_session_status:
            try:
                return self._wrap_action_result("Kali session", self.tools.get_kali_session_status())
            except Exception as exc:
                return f"Kali session status failed: {exc}"
        if kali_session_command:
            try:
                return self._wrap_action_result("Kali session command", self.tools.run_kali_session_command(kali_session_command.group(1).strip()))
            except Exception as exc:
                return f"Kali session command failed: {exc}"
        if explicit_kali_chat:
            try:
                return "Kali helper:\n" + self.tools.ask_kali_helper(explicit_kali_chat.group(1).strip(), use_web=True)
            except Exception as exc:
                return f"Kali helper failed: {exc}"
        if kali_help_intent:
            try:
                return "Kali helper:\n" + self.tools.ask_kali_helper(user_input.strip(), use_web=True)
            except Exception as exc:
                return f"Kali helper failed: {exc}"

        codex_test_match = re.search(r"(?:code and test|fix and test|edit and test)[: ]+([\s\S]+)$", user_input, flags=re.IGNORECASE)
        if codex_test_match:
            try:
                return "Coding and test changes:\n" + self.tools.codex_edit_and_test(codex_test_match.group(1).strip())
            except Exception as exc:
                return f"Coding and test changes failed: {exc}"

        codex_match = re.search(r"(?:code|edit project|fix code|refactor code|add feature)[: ]+([\s\S]+)$", user_input, flags=re.IGNORECASE)
        if codex_match:
            try:
                return "Coding changes:\n" + self.tools.codex_edit(codex_match.group(1).strip())
            except Exception as exc:
                return f"Coding changes failed: {exc}"

        create_match = re.search(r"(?:create|write)\s+file\s+(.+?)(?:\s+with\s+content[: ]|\s*:\s*)([\s\S]+)$", user_input, flags=re.IGNORECASE)
        if create_match:
            try:
                return self._wrap_action_result("File write", self.tools.write_file(create_match.group(1).strip(), create_match.group(2)))
            except Exception as exc:
                return f"File write failed: {exc}"

        save_desktop_match = re.search(
            r"^(?:save|write)\s+(?:this\s+)?(?:script|file|code)\s+(?:to\s+)?desktop(?:\s*[: ]\s*|\s+with\s+content\s*[: ]\s*|\s*:\s*)([\s\S]+)$",
            user_input,
            flags=re.IGNORECASE,
        )
        if save_desktop_match:
            content = save_desktop_match.group(1).strip()
            filename = "kai_script.ps1"
            if re.search(r"^#!.*\bpython\b", content, flags=re.IGNORECASE | re.MULTILINE) or "import " in content:
                filename = "kai_script.py"
            elif re.search(r"^\s*<\?xml|^\s*<project", content, flags=re.IGNORECASE | re.MULTILINE):
                filename = "kai_script.txt"
            try:
                desktop = Path.home() / "OneDrive" / "Desktop"
                if not desktop.exists():
                    desktop = Path.home() / "Desktop"
                target = desktop / filename
                return self._wrap_action_result("File write", self.tools.write_file(str(target), content))
            except Exception as exc:
                return f"File write failed: {exc}"

        append_match = re.search(r"(?:append)\s+to\s+file\s+(.+?)(?:\s+with\s+content[: ]|\s*:\s*)([\s\S]+)$", user_input, flags=re.IGNORECASE)
        if append_match:
            try:
                return "File append:\n" + self.tools.append_file(append_match.group(1).strip(), append_match.group(2))
            except Exception as exc:
                return f"File append failed: {exc}"

        replace_match = re.search(
            r"replace\s+in\s+file\s+(.+?)\s+old[: ]([\s\S]+?)\s+new[: ]([\s\S]+)$",
            user_input,
            flags=re.IGNORECASE,
        )
        if replace_match:
            try:
                return "File replace:\n" + self.tools.replace_in_file(
                    replace_match.group(1).strip(),
                    replace_match.group(2),
                    replace_match.group(3),
                )
            except Exception as exc:
                return f"File replace failed: {exc}"

        if github_url and any(word in lowered for word in ["install", "setup", "set up"]):
            try:
                return self._wrap_action_result("GitHub project setup", self.tools.setup_github_project(github_url.group(0)))
            except Exception as exc:
                return f"GitHub project setup failed: {exc}"
        if github_url and any(word in lowered for word in ["clone", "download repo", "get repo"]):
            try:
                return self._wrap_action_result("Repository clone", self.tools.clone_repo(github_url.group(0)))
            except Exception as exc:
                return f"Repository clone failed: {exc}"
        if any(word in lowered for word in ["extract zip", "unzip", "extract archive"]):
            zip_match = re.search(r"([A-Za-z]:\\[^\n\r]+?\.zip|\S+\.zip)", user_input, flags=re.IGNORECASE)
            if zip_match:
                try:
                    return self._wrap_action_result("Zip extraction", self.tools.extract_zip(zip_match.group(1)))
                except Exception as exc:
                    return f"Zip extraction failed: {exc}"
        if any(word in lowered for word in ["install this project", "install project", "setup this folder", "set up this folder"]):
            target = self._extract_path_hint(user_input)
            try:
                return self._wrap_action_result("Project install", self.tools.install_project(target))
            except Exception as exc:
                return f"Project install failed: {exc}"
        if any(word in lowered for word in ["install this file", "install the file", "install file", "set up this file"]):
            target = self._extract_path_hint(user_input)
            try:
                target_path = Path(target)
                if not target_path.is_absolute():
                    candidates = [
                        Path.home() / "OneDrive" / "Desktop" / target,
                        Path.home() / "Desktop" / target,
                        self.workspace / target,
                    ]
                    target_path = next((candidate.resolve() for candidate in candidates if candidate.exists()), candidates[0].resolve())
                if target_path.suffix.lower() in {".msi", ".exe", ".bat", ".cmd", ".ps1", ".lnk"}:
                    return self._wrap_action_result("Open path", self.tools.open_path(str(target_path)))
                return self._wrap_action_result("File info", json.dumps({"action": "file_info", "ok": True, "path": str(target_path), "summary": self.tools.read_file(str(target_path))}, indent=2))
            except Exception as exc:
                return f"File handling failed: {exc}"
        if any(word in lowered for word in ["run this project", "start this project", "launch this project", "run project", "start project"]):
            target = self._extract_path_hint(user_input)
            try:
                return self._wrap_action_result("Project run", self.tools.run_project(target))
            except Exception as exc:
                return f"Project run failed: {exc}"
        if any(word in lowered for word in ["run tests", "test this project", "test project", "run project tests"]):
            target = self._extract_path_hint(user_input)
            try:
                return "Project tests:\n" + self.tools.run_tests(target)
            except Exception as exc:
                return f"Project tests failed: {exc}"
        if any(word in lowered for word in ["open zip", "open folder", "open file", "open repo", "open project", "open this"]) and "open kali" not in lowered:
            path = self._extract_path_hint(user_input)
            if path:
                try:
                    return self._wrap_action_result("Open path", self.tools.open_path(path))
                except Exception as exc:
                    return f"Open path failed: {exc}"
        if any(phrase in lowered for phrase in ["read my screen", "look at my screen", "ocr", "what's on my screen"]):
            try:
                return "Screen OCR:\n" + self.tools.capture_screen_ocr()
            except Exception as exc:
                return f"Screen OCR failed: {exc}"
        if any(phrase in lowered for phrase in ["read terminal", "check terminal", "terminal output"]):
            try:
                return "Terminal snapshot:\n" + self.tools.run_shell("Get-Process | Select-Object -First 30 ProcessName,Id")
            except Exception as exc:
                return f"Terminal snapshot failed: {exc}"

        # Browser automation commands — natural language friendly
        browse_match = re.search(
            r"(?:browse|go to|open website|open site|navigate to|visit|open up|pull up|look at|check out|go check|go look at)[: ]+(.+)$",
            user_input, flags=re.IGNORECASE,
        )
        if browse_match:
            try:
                return self._wrap_action_result("Browse", self.tools.browse(browse_match.group(1).strip()))
            except Exception as exc:
                return f"Browse failed: {exc}"

        # Natural language search — "look up X", "find X online", "search for X", "what is X on the web"
        browser_search_match = re.search(
            r"(?:look up|find .{0,20} online|search for|google|search|find .{0,20} on the web|what is|where can i find|how do i get|look for)[: ]+(.+)$",
            user_input, flags=re.IGNORECASE,
        )
        if browser_search_match and not any(kw in lowered for kw in ["file", "document", "kali"]):
            try:
                return self._wrap_action_result("Search", self.tools.search_browser(browser_search_match.group(1).strip()))
            except Exception as exc:
                return f"Search failed: {exc}"

        # Natural language download — "download that", "get that PDF", "save that form"
        download_match = re.search(
            r"(?:download|get|save|grab|fetch)[: ]+(?:that |the )?(?:pdf|form|file|document|link)?\s*(.+)$",
            user_input, flags=re.IGNORECASE,
        )
        if download_match and ("http" in download_match.group(1) or "." in download_match.group(1)):
            try:
                return self._wrap_action_result("Download", self.tools.download_file(url=download_match.group(1).strip()))
            except Exception as exc:
                return f"Download failed: {exc}"
        if any(phrase in lowered for phrase in ["download that", "download this", "get that file", "save that", "grab that", "download the form", "download the pdf"]):
            try:
                return self._wrap_action_result("Download", self.tools.download_file())
            except Exception as exc:
                return f"Download failed: {exc}"

        # Natural language page reading
        if any(phrase in lowered for phrase in [
            "what's on this page", "what is on this page", "read this page", "show me this page",
            "what does this page say", "summarize this page", "page content", "show page",
            "what links are here", "what links are on this page",
        ]):
            try:
                return self._wrap_action_result("Page content", self.tools.get_page_content())
            except Exception as exc:
                return f"Page content failed: {exc}"

        if any(phrase in lowered for phrase in ["show links", "page links", "get links", "what links", "list links", "all links"]):
            try:
                return self._wrap_action_result("Page links", self.tools.get_page_links())
            except Exception as exc:
                return f"Page links failed: {exc}"

        # Natural language click — "click on patient forms", "open the link that says..."
        click_link_match = re.search(
            r"(?:click|click on|open|open the|open that|press|hit|select|choose)[: ]+(?:the |that )?(?:link |button )?(?:that says |labeled |called )?(.+)$",
            user_input, flags=re.IGNORECASE,
        )
        if click_link_match:
            text = click_link_match.group(1).strip().strip('"\'')
            if text:
                try:
                    return self._wrap_action_result("Click link", self.tools.click_link(text))
                except Exception as exc:
                    return f"Click link failed: {exc}"

        if any(phrase in lowered for phrase in ["find forms", "show forms", "page forms", "any forms here", "is there a form"]):
            try:
                return self._wrap_action_result("Find forms", self.tools.find_forms())
            except Exception as exc:
                return f"Find forms failed: {exc}"

        # Natural language form filling — "fill in my name as John", "put Jane Doe in the name field"
        fill_form_match = re.search(r"(?:fill in|fill out|type in|enter|put)[: ]+(.+)$", user_input, flags=re.IGNORECASE)
        if fill_form_match:
            try:
                raw = fill_form_match.group(1).strip()
                data = {}
                # Handle "name as John" or "name: John" or "name=John" patterns
                pairs = re.split(r",\s*| and ", raw)
                for pair in pairs:
                    for sep in [" as ", " = ", ": ", " is "]:
                        if sep in pair:
                            k, v = pair.split(sep, 1)
                            data[k.strip().strip('"\'')] = v.strip().strip('"\'')
                            break
                    if "=" in pair and not data:
                        k, v = pair.split("=", 1)
                        data[k.strip()] = v.strip()
                if data:
                    return self._wrap_action_result("Fill form", self.tools.fill_form(data))
            except Exception as exc:
                return f"Fill form failed: {exc}"

        if any(phrase in lowered for phrase in ["take screenshot", "screenshot", "capture page", "take a picture of this"]):
            try:
                return self._wrap_action_result("Screenshot", self.tools.screenshot())
            except Exception as exc:
                return f"Screenshot failed: {exc}"

        # Natural language close browser
        if any(phrase in lowered for phrase in ["close browser", "close the browser", "stop browsing", "done browsing"]):
            try:
                self.tools.browser.close()
                return "Browser closed."
            except Exception as exc:
                return f"Close browser failed: {exc}"

        # Document management commands — natural language
        if any(phrase in lowered for phrase in [
            "show documents", "list documents", "my documents", "my files", "what documents do i have",
            "show my files", "what files", "show files",
        ]):
            try:
                return self._wrap_action_result("Documents", self.tools.list_documents())
            except Exception as exc:
                return f"Documents failed: {exc}"
        find_doc_match = re.search(
            r"(?:find|search|look for|locate|where is|where's)[: ]+(?:my |the |a )?(?:document |file |form )?(.+)$",
            user_input, flags=re.IGNORECASE,
        )
        if find_doc_match and any(kw in lowered for kw in ["document", "file", "form", "pdf", ".pdf"]):
            try:
                return self._wrap_action_result("Find document", self.tools.find_document(find_doc_match.group(1).strip()))
            except Exception as exc:
                return f"Find document failed: {exc}"
        read_doc_match = re.search(r"(?:read document|open document|view document)[: ]+(.+)$", user_input, flags=re.IGNORECASE)
        if read_doc_match:
            try:
                return self._wrap_action_result("Read document", self.tools.read_document(read_doc_match.group(1).strip()))
            except Exception as exc:
                return f"Read document failed: {exc}"
        if any(phrase in lowered for phrase in ["organize downloads", "sort downloads", "categorize files"]):
            try:
                return self._wrap_action_result("Organize", self.tools.organize_downloads())
            except Exception as exc:
                return f"Organize failed: {exc}"
        if any(phrase in lowered for phrase in ["document stats", "doc stats", "how many documents"]):
            try:
                return self._wrap_action_result("Document stats", self.tools.document_stats())
            except Exception as exc:
                return f"Document stats failed: {exc}"

        kali_match = re.search(r"(?:run|execute)\s+(?:in\s+kali|on\s+kali|kali)[: ]+(.+)$", user_input, flags=re.IGNORECASE)
        if kali_match:
            try:
                return self._wrap_action_result("Kali session command", self.tools.run_kali_session_command(kali_match.group(1).strip()))
            except Exception as exc:
                return f"Kali command failed: {exc}"
        powershell_match = re.search(r"(?:run|execute)\s+(?:in\s+powershell|powershell)[: ]+(.+)$", user_input, flags=re.IGNORECASE)
        if powershell_match:
            try:
                return self._wrap_action_result("PowerShell command", self.tools.run_shell(powershell_match.group(1).strip()))
            except Exception as exc:
                return f"PowerShell command failed: {exc}"
        run_match = re.search(r"(?:run|execute)[: ]+(.+)$", user_input, flags=re.IGNORECASE)
        if run_match:
            try:
                return self._wrap_action_result("Command", self.tools.run_shell(run_match.group(1).strip()))
            except Exception as exc:
                return f"Command failed: {exc}"
        file_match = re.search(r"(?:read file|open file)[: ]+(.+)$", user_input, flags=re.IGNORECASE)
        if file_match:
            try:
                target = self._extract_path_hint(file_match.group(1).strip())
                return self._wrap_action_result("File read", json.dumps({"action": "file_read", "ok": True, "path": target, "summary": self.tools.read_file(target)}, indent=2))
            except Exception as exc:
                return f"File read failed: {exc}"
        list_match = re.search(r"(?:list files|show files)[: ]+(.+)$", user_input, flags=re.IGNORECASE)
        if list_match:
            try:
                target = self._extract_path_hint(list_match.group(1).strip())
                return self._wrap_action_result("File list", json.dumps({"action": "file_list", "ok": True, "path": target, "summary": self.tools.list_files(target)}, indent=2))
            except Exception as exc:
                return f"File list failed: {exc}"
        return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kai local assistant CLI")
    parser.add_argument(
        "--model",
        default=os.environ.get("KAI_MODEL", "qwen3:4b-q4_K_M"),
        help="Ollama model name. Defaults to KAI_MODEL or qwen3:4b-q4_K_M.",
    )
    parser.add_argument(
        "--workspace",
        default=str(Path(__file__).resolve().parents[1]),
        help="Workspace root used for memory storage.",
    )
    return parser.parse_args()


async def repl(model: str, workspace: Path) -> None:
    assistant = KaiAssistant(model=model, workspace=workspace)
    def kai_echo(message: str = "") -> None:
        print(message, file=sys.stderr)

    def shell_echo(message: str = "") -> None:
        print(message)

    kai_echo(f"[KAI] ready with model: {model}")
    kai_echo("[KAI] Commands: /exit, /remember <text>, /memory, /screen, /run <powershell>, /read <file>, /ls <path>, /autonomy <on|off|status|tick>")
    kai_echo("[KAI] Task planning: plan: <task>, run plan, do task: <task>, plan status")
    kai_echo("[KAI] Browser: browse <url>, show links, click link <text>, download file <url>, fill form: key=val")
    kai_echo("[KAI] Documents: show documents, find document <name>, read document <path>, organize downloads")
    while True:
        try:
            user_input = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            kai_echo("\n[KAI] session ended.")
            break

        if not user_input:
            continue
        if user_input == "/exit":
            kai_echo("[KAI] session ended.")
            break
        if user_input.startswith("/remember "):
            note = assistant.remember(user_input[len("/remember ") :])
            kai_echo(f"[KAI] remembered: {note['content']}")
            continue
        if user_input == "/memory":
            kai_echo("[KAI] memory")
            shell_echo(assistant.memory.build_memory_context())
            continue
        if user_input == "/screen":
            kai_echo("[KAI] screen capture")
            shell_echo(assistant.tools.capture_screen_ocr())
            continue
        if user_input.startswith("/run "):
            kai_echo("[KAI] running PowerShell command")
            shell_echo(assistant.tools.run_shell(user_input[len("/run ") :]))
            continue
        if user_input.startswith("/read "):
            kai_echo("[KAI] reading file")
            shell_echo(assistant.tools.read_file(user_input[len("/read ") :]))
            continue
        if user_input.startswith("/ls"):
            target = user_input[len("/ls") :].strip() or "."
            kai_echo("[KAI] listing files")
            shell_echo(assistant.tools.list_files(target))
            continue
        if user_input.startswith("/autonomy"):
            subcommand = user_input[len("/autonomy") :].strip().lower()
            if subcommand == "on":
                kai_echo("[KAI] autonomy on")
                shell_echo(assistant.autonomy.enable())
                continue
            if subcommand == "off":
                kai_echo("[KAI] autonomy off")
                shell_echo(assistant.autonomy.disable())
                continue
            if subcommand == "status":
                kai_echo("[KAI] autonomy status")
                shell_echo(assistant.autonomy.status())
                continue
            if subcommand == "tick":
                kai_echo("[KAI] autonomy tick")
                shell_echo(assistant.autonomy.tick())
                continue
            kai_echo("[KAI] Use /autonomy on, /autonomy off, /autonomy status, or /autonomy tick")
            continue

        try:
            reply = await assistant.ask(user_input)
        except Exception as exc:
            await send_event("kai_sleep")
            kai_echo(f"[KAI] I hit a local model issue: {exc}")
            continue
        kai_echo(f"[KAI] {reply}")


def main() -> None:
    args = parse_args()
    asyncio.run(repl(model=args.model, workspace=Path(args.workspace)))


if __name__ == "__main__":
    main()
