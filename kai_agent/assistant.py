import argparse
import asyncio
import json
import os
import re
from pathlib import Path

from kai_agent.bridge_client import send_event
from kai_agent.desktop_tools import DesktopTools
from kai_agent.memory import KaiMemory
from kai_agent.ollama_client import OllamaClient


SYSTEM_PROMPT = """You are Kai, a local-first personal assistant and coding partner.
Be practical, warm, and concise.
Use what you know about the user's projects and preferences from memory when it helps.
If the user asks you to remember something, summarize it clearly and tell them to use /remember.
Prefer actionable help over vague advice.
When tool results are provided, use them directly and summarize what you observed before advising next steps.
When an operator tool already completed a task, explain what happened and propose the next useful step instead of saying you can't do it.
For Kali shell tasks, prefer the persistent Kali session when a live command context is available.
Use an action ladder mindset:
Level 1 explain, Level 2 suggest, Level 3 prepare runnable command, Level 4 execute safe/caution actions, Level 5 require confirmation for risky or destructive actions.
"""


class KaiAssistant:
    def __init__(self, model: str, workspace: Path) -> None:
        self.workspace = workspace
        self.memory = KaiMemory(workspace / "memory")
        self.client = OllamaClient(model=model)
        self.tools = DesktopTools(workspace)
        self.history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.last_tool_context = ""
        self.last_action_preview = ""
        self.last_proactive_hint = ""
        self.last_task_snapshot = self.memory.summarize_tasks()

    def build_messages(self, user_input: str) -> list[dict]:
        memory_context = self.memory.build_memory_context()
        return self.history + [
            {"role": "system", "content": memory_context},
            {"role": "user", "content": user_input},
        ]

    async def ask(self, user_input: str) -> str:
        await send_event("kai_thinking")
        user_log = user_input
        if self._should_continue_browser_signup(user_input):
            tool_context = "Browser signup:\n" + self.tools.continue_browser_signup(user_input.strip())
            user_log = self.tools.consume_browser_signup_user_log(user_input)
        else:
            tool_context = self._maybe_run_tools(user_input)
        self.memory.append_session("user", user_log)
        self.last_tool_context = tool_context
        self.last_action_preview = self._build_action_preview(tool_context)
        self._learn_from_interaction(user_log, tool_context)
        self.last_proactive_hint = self._build_proactive_hint(user_log, tool_context)
        self.last_task_snapshot = self.memory.summarize_tasks()
        tool_data = self._extract_tool_data(tool_context)
        direct_reply = self._direct_tool_reply(tool_data)
        if direct_reply:
            self.history.append({"role": "user", "content": user_log})
            self.history.append({"role": "assistant", "content": direct_reply})
            self.memory.append_session("assistant", direct_reply)
            await send_event("kai_wag_tail")
            return direct_reply
        prompt = user_log if not tool_context else f"{user_log}\n\nTool context:\n{tool_context}"
        try:
            reply = await asyncio.to_thread(self.client.chat, self.build_messages(prompt))
        except Exception as exc:
            await send_event("kai_sleep")
            error_message = f"I hit a local model issue: {exc}"
            self.memory.append_session("assistant", error_message)
            self.history.append({"role": "user", "content": user_log})
            self.history.append({"role": "assistant", "content": error_message})
            raise RuntimeError(error_message) from exc
        self.history.append({"role": "user", "content": user_log})
        self.history.append({"role": "assistant", "content": reply})
        self.memory.append_session("assistant", reply)
        await send_event("kai_wag_tail")
        return reply

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
        if data.get("status"):
            summary_bits.append(f"Flow: {data['status']}")
        if data.get("method"):
            summary_bits.append(f"Method: {data['method']}")
        if data.get("url"):
            summary_bits.append(f"URL: {data['url']}")
        if data.get("question"):
            summary_bits.append(str(data["question"]))
        if data.get("generated_email"):
            summary_bits.append(f"Email: {data['generated_email']}")
        if data.get("summary"):
            summary_bits.append(str(data["summary"]))
        if data.get("error"):
            summary_bits.append(f"Error: {data['error']}")
        return "\n".join(summary_bits)[:700]

    def remember(self, text: str, category: str = "general") -> dict:
        return self.memory.save_note(text, category=category)

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

    def _direct_tool_reply(self, data: dict) -> str:
        action = str(data.get("action", ""))
        if action.startswith("browser_signup"):
            return str(data.get("user_message", "")).strip()
        return ""

    def _should_continue_browser_signup(self, user_input: str) -> bool:
        if not self.tools.has_pending_browser_signup():
            return False
        lowered = user_input.strip().lower()
        if lowered in {"cancel signup", "stop signup", "signup status", "browser signup status", "website signup status"}:
            return False
        return True

    def _build_proactive_hint(self, user_input: str, tool_context: str) -> str:
        data = self._extract_tool_data(tool_context)
        if not data:
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
        if action.startswith("browser_signup"):
            if data.get("status") == "awaiting_user_input":
                return "Suggestion: reply with the requested signup info and I will continue the browser flow."
            if data.get("status") == "completed":
                return "Suggestion: check the browser window for the final confirmation or email verification step."
            if data.get("status") == "cancelled":
                return "Suggestion: paste a site URL with the signup method when you want to start another one."
        return ""

    def _maybe_run_tools(self, user_input: str) -> str:
        lowered = user_input.lower()
        github_url = re.search(r"https?://github\.com/[^\s)]+", user_input, flags=re.IGNORECASE)
        web_url = re.search(r"https?://[^\s)]+", user_input, flags=re.IGNORECASE)
        cyber_toolkit_match = re.search(
            r"^(?:cyber toolkit|lab toolkit|safe cyber tools|authorized cyber tools|show cyber tools)$",
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
        signup_status_match = re.search(r"^(?:signup status|browser signup status|website signup status)$", user_input.strip(), flags=re.IGNORECASE)
        cancel_signup_match = re.search(r"^(?:cancel signup|stop signup|close signup browser)$", user_input.strip(), flags=re.IGNORECASE)
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
        if signup_status_match:
            try:
                return "Browser signup:\n" + self.tools.browser_signup_status()
            except Exception as exc:
                return f"Browser signup status failed: {exc}"
        if cancel_signup_match:
            try:
                return "Browser signup:\n" + self.tools.cancel_browser_signup()
            except Exception as exc:
                return f"Browser signup cancel failed: {exc}"
        if web_url and any(phrase in lowered for phrase in ["sign me up", "sign up for me", "signup", "register me", "create account for me"]):
            method = "google" if "google" in lowered else "random_email" if "random email" in lowered else "email"
            try:
                return "Browser signup:\n" + self.tools.start_browser_signup(web_url.group(0), method=method)
            except Exception as exc:
                return f"Browser signup failed: {exc}"

        if kali_session_start:
            try:
                return "Kali session:\n" + self.tools.start_kali_session()
            except Exception as exc:
                return f"Kali session start failed: {exc}"
        if kali_session_stop:
            try:
                return "Kali session:\n" + self.tools.stop_kali_session()
            except Exception as exc:
                return f"Kali session stop failed: {exc}"
        if kali_session_status:
            try:
                return "Kali session:\n" + self.tools.get_kali_session_status()
            except Exception as exc:
                return f"Kali session status failed: {exc}"
        if kali_session_command:
            try:
                return "Kali session command:\n" + self.tools.run_kali_session_command(kali_session_command.group(1).strip())
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
                return "File write:\n" + self.tools.write_file(create_match.group(1).strip(), create_match.group(2))
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
                return "GitHub project setup:\n" + self.tools.setup_github_project(github_url.group(0))
            except Exception as exc:
                return f"GitHub project setup failed: {exc}"
        if github_url and any(word in lowered for word in ["clone", "download repo", "get repo"]):
            try:
                return "Repository clone:\n" + self.tools.clone_repo(github_url.group(0))
            except Exception as exc:
                return f"Repository clone failed: {exc}"
        if any(word in lowered for word in ["extract zip", "unzip", "extract archive"]):
            zip_match = re.search(r"([A-Za-z]:\\[^\n\r]+?\.zip|\S+\.zip)", user_input, flags=re.IGNORECASE)
            if zip_match:
                try:
                    return "Zip extraction:\n" + self.tools.extract_zip(zip_match.group(1))
                except Exception as exc:
                    return f"Zip extraction failed: {exc}"
        if any(word in lowered for word in ["install this project", "install project", "setup this folder", "set up this folder"]):
            path_match = re.search(r"(?:in|from)\s+(.+)$", user_input, flags=re.IGNORECASE)
            target = path_match.group(1).strip() if path_match else "."
            try:
                return "Project install:\n" + self.tools.install_project(target)
            except Exception as exc:
                return f"Project install failed: {exc}"
        if any(word in lowered for word in ["run this project", "start this project", "launch this project", "run project", "start project"]):
            path_match = re.search(r"(?:in|from)\s+(.+)$", user_input, flags=re.IGNORECASE)
            target = path_match.group(1).strip() if path_match else "."
            try:
                return "Project run:\n" + self.tools.run_project(target)
            except Exception as exc:
                return f"Project run failed: {exc}"
        if any(word in lowered for word in ["run tests", "test this project", "test project", "run project tests"]):
            path_match = re.search(r"(?:in|from)\s+(.+)$", user_input, flags=re.IGNORECASE)
            target = path_match.group(1).strip() if path_match else "."
            try:
                return "Project tests:\n" + self.tools.run_tests(target)
            except Exception as exc:
                return f"Project tests failed: {exc}"
        if any(word in lowered for word in ["open zip", "open folder", "open file", "open repo", "open project", "open this"]) and "open kali" not in lowered:
            path_match = re.search(r"open (?:zip|folder|file|repo|project|this)?\s*(.+)$", user_input, flags=re.IGNORECASE)
            if path_match and path_match.group(1).strip():
                try:
                    return "Open path:\n" + self.tools.open_path(path_match.group(1).strip())
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
        kali_match = re.search(r"(?:run|execute)\s+(?:in\s+kali|on\s+kali|kali)[: ]+(.+)$", user_input, flags=re.IGNORECASE)
        if kali_match:
            try:
                return "Kali session command:\n" + self.tools.run_kali_session_command(kali_match.group(1).strip())
            except Exception as exc:
                return f"Kali command failed: {exc}"
        powershell_match = re.search(r"(?:run|execute)\s+(?:in\s+powershell|powershell)[: ]+(.+)$", user_input, flags=re.IGNORECASE)
        if powershell_match:
            try:
                return "PowerShell command result:\n" + self.tools.run_shell(powershell_match.group(1).strip())
            except Exception as exc:
                return f"PowerShell command failed: {exc}"
        run_match = re.search(r"(?:run|execute)[: ]+(.+)$", user_input, flags=re.IGNORECASE)
        if run_match:
            try:
                return "Command result:\n" + self.tools.run_shell(run_match.group(1).strip())
            except Exception as exc:
                return f"Command failed: {exc}"
        file_match = re.search(r"(?:read file|open file)[: ]+(.+)$", user_input, flags=re.IGNORECASE)
        if file_match:
            try:
                return "File contents:\n" + self.tools.read_file(file_match.group(1).strip())
            except Exception as exc:
                return f"File read failed: {exc}"
        list_match = re.search(r"(?:list files|show files)[: ]+(.+)$", user_input, flags=re.IGNORECASE)
        if list_match:
            try:
                return "File list:\n" + self.tools.list_files(list_match.group(1).strip())
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
    print(f"Kai is ready with model: {model}")
    print("Commands: /exit, /remember <text>, /memory, /screen, /run <powershell>, /read <file>, /ls <path>")
    while True:
        try:
            user_input = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKai session ended.")
            break

        if not user_input:
            continue
        if user_input == "/exit":
            print("Kai session ended.")
            break
        if user_input.startswith("/remember "):
            note = assistant.remember(user_input[len("/remember ") :])
            print(f"Kai> Remembered: {note['content']}")
            continue
        if user_input == "/memory":
            print("Kai>")
            print(assistant.memory.build_memory_context())
            continue
        if user_input == "/screen":
            print("Kai>")
            print(assistant.tools.capture_screen_ocr())
            continue
        if user_input.startswith("/run "):
            print("Kai>")
            print(assistant.tools.run_shell(user_input[len("/run ") :]))
            continue
        if user_input.startswith("/read "):
            print("Kai>")
            print(assistant.tools.read_file(user_input[len("/read ") :]))
            continue
        if user_input.startswith("/ls"):
            target = user_input[len("/ls") :].strip() or "."
            print("Kai>")
            print(assistant.tools.list_files(target))
            continue

        try:
            reply = await assistant.ask(user_input)
        except Exception as exc:
            await send_event("kai_sleep")
            print(f"Kai> I hit a local model issue: {exc}")
            continue
        print(f"Kai> {reply}")


def main() -> None:
    args = parse_args()
    asyncio.run(repl(model=args.model, workspace=Path(args.workspace)))


if __name__ == "__main__":
    main()
