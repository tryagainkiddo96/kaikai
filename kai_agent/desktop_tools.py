from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import threading
import time
import uuid
from queue import Empty, Queue
from pathlib import Path

from kai_agent.tavily_client import TavilyClient


TESSERACT_PATH = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")


class DesktopTools:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.tmp_dir = workspace / "tmp"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.kali_process: subprocess.Popen[bytes] | None = None
        self.kali_queue: Queue[str] = Queue()
        self.kali_reader_thread: threading.Thread | None = None
        self.kali_lock = threading.Lock()
        self.kali_session_cwd = self._to_wsl_path(self.workspace)
        self.tavily = TavilyClient()

    def classify_command(self, command: str, shell: str = "powershell") -> dict:
        lowered = command.strip().lower()
        tags: list[str] = []
        level = 3

        safe_prefixes = [
            "pwd",
            "ls",
            "dir",
            "whoami",
            "echo ",
            "cat ",
            "type ",
            "ss ",
            "ip ",
            "ifconfig",
            "journalctl",
            "systemctl status",
            "Get-ChildItem".lower(),
            "Get-Content".lower(),
        ]
        caution_terms = [
            "apt install",
            "pip install",
            "npm install",
            "winget install",
            "git clone",
            "curl ",
            "wget ",
            "Invoke-WebRequest".lower(),
            "Start-Process".lower(),
        ]
        destructive_terms = [
            "rm ",
            "del ",
            "rmdir ",
            "format ",
            "mkfs",
            "shutdown",
            "reboot",
            "poweroff",
            "sc delete",
            "reg delete",
            "Remove-Item".lower(),
        ]

        if any(term in lowered for term in destructive_terms):
            tags.extend(["destructive", "system-changing"])
            level = 5
        elif any(term in lowered for term in caution_terms):
            tags.append("caution")
            level = 4
        elif any(lowered == prefix or lowered.startswith(prefix) for prefix in safe_prefixes):
            tags.append("safe")
            level = 2
        else:
            tags.append("caution")
            level = 3

        if any(term in lowered for term in ["curl ", "wget ", "invoke-webrequest", "nmap", "ffuf", "ping ", "nslookup", "dig "]):
            tags.append("network-active")
        if any(term in lowered for term in ["apt ", "dpkg ", "pip ", "npm ", "winget ", "choco ", "systemctl ", "service "]):
            tags.append("system-changing")
        if not tags:
            tags.append("safe")

        return {
            "command": command,
            "shell": shell,
            "confidence": tags[0],
            "tags": tags,
            "action_level": level,
            "requires_confirmation": level >= 4 or "destructive" in tags,
        }

    def preview_command(self, command: str, shell: str = "powershell") -> str:
        payload = {
            "action": "command_preview",
            "ok": True,
            **self.classify_command(command, shell=shell),
        }
        return json.dumps(payload, indent=2)

    def run_shell(self, command: str, timeout: int = 30) -> str:
        meta = self.classify_command(command, shell="powershell")
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = completed.stdout.strip()
            stderr = completed.stderr.strip()
            payload = {
                "action": "run_shell",
                "command": command,
                "returncode": completed.returncode,
                "stdout": stdout[:8000],
                "stderr": stderr[:4000],
                **meta,
            }
        except subprocess.TimeoutExpired:
            payload = {
                "action": "run_shell",
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                **meta,
            }
        except Exception as exc:
            payload = {
                "action": "run_shell",
                "command": command,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command failed: {exc}",
                **meta,
            }
        return json.dumps(payload, indent=2)

    def run_wsl(self, command: str, timeout: int = 60, distro: str = "kali-linux") -> str:
        meta = self.classify_command(command, shell="bash")
        try:
            completed = subprocess.run(
                ["wsl.exe", "-d", distro, "--", "bash", "-lc", command],
                cwd=str(self.workspace),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            payload = {
                "action": "run_wsl",
                "command": command,
                "distro": distro,
                "returncode": completed.returncode,
                "stdout": completed.stdout.strip()[:8000],
                "stderr": completed.stderr.strip()[:4000],
                **meta,
            }
        except subprocess.TimeoutExpired:
            payload = {
                "action": "run_wsl",
                "command": command,
                "distro": distro,
                "returncode": -1,
                "stdout": "",
                "stderr": f"WSL command timed out after {timeout}s",
                **meta,
            }
        except Exception as exc:
            payload = {
                "action": "run_wsl",
                "command": command,
                "distro": distro,
                "returncode": -1,
                "stdout": "",
                "stderr": f"WSL command failed: {exc}",
                **meta,
            }
        return json.dumps(payload, indent=2)

    def _kali_reader(self) -> None:
        if not self.kali_process or not self.kali_process.stdout:
            return
        for raw_line in self.kali_process.stdout:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            self.kali_queue.put(line)

    def ensure_kali_session(self) -> None:
        if self.kali_process and self.kali_process.poll() is None:
            return

        self.kali_process = subprocess.Popen(
            ["wsl.exe", "-d", "kali-linux", "--", "bash", "--noprofile", "--norc"],
            cwd=str(self.workspace),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
        self.kali_queue = Queue()
        self.kali_reader_thread = threading.Thread(target=self._kali_reader, daemon=True)
        self.kali_reader_thread.start()

        ready_token = f"__KAI_READY__{uuid.uuid4().hex}"
        init_cmd = (
            "export TERM=dumb\n"
            "unset PROMPT_COMMAND\n"
            "PS1=''\n"
            f"cd {shlex.quote(self.kali_session_cwd)}\n"
            f"echo {ready_token}\n"
        )
        assert self.kali_process.stdin is not None
        self.kali_process.stdin.write(init_cmd.encode("utf-8"))
        self.kali_process.stdin.flush()

        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                line = self.kali_queue.get(timeout=0.5)
                if line == ready_token:
                    return
            except Empty:
                continue
        raise RuntimeError("Timed out starting persistent Kali session.")

    def stop_kali_session(self) -> str:
        with self.kali_lock:
            if not self.kali_process or self.kali_process.poll() is not None:
                return json.dumps({"action": "kali_session_stop", "ok": True, "message": "Kali session was not running."}, indent=2)
            try:
                if self.kali_process.stdin:
                    self.kali_process.stdin.write(b"exit\n")
                    self.kali_process.stdin.flush()
                self.kali_process.wait(timeout=5)
            except Exception:
                self.kali_process.kill()
            finally:
                self.kali_process = None
            return json.dumps({"action": "kali_session_stop", "ok": True, "message": "Stopped Kali session."}, indent=2)

    def start_kali_session(self) -> str:
        with self.kali_lock:
            try:
                self.ensure_kali_session()
                payload = {
                    "action": "kali_session_start",
                    "ok": True,
                    "cwd": self.kali_session_cwd,
                    "message": "Persistent Kali session is ready.",
                }
            except Exception as exc:
                payload = {
                    "action": "kali_session_start",
                    "ok": False,
                    "cwd": self.kali_session_cwd,
                    "error": str(exc),
                }
        return json.dumps(payload, indent=2)

    def get_kali_session_status(self) -> str:
        running = bool(self.kali_process and self.kali_process.poll() is None)
        payload = {
            "action": "kali_session_status",
            "ok": True,
            "running": running,
            "cwd": self.kali_session_cwd,
        }
        return json.dumps(payload, indent=2)

    def complete_kali_input(self, partial: str, limit: int = 12) -> str:
        fragment = partial.strip()
        if not fragment:
            target = ""
            base_prefix = ""
        elif partial.endswith(" "):
            target = ""
            base_prefix = partial
        else:
            if " " in fragment:
                base_prefix, target = fragment.rsplit(" ", 1)
                base_prefix += " "
            else:
                base_prefix = ""
                target = fragment

        quoted_target = shlex.quote(target)
        command = (
            "target="
            + quoted_target
            + "\n"
            + "compgen -cdfa -- \"$target\" | head -n "
            + str(limit)
        )
        result = json.loads(self.run_kali_session_command(command, timeout=30))
        raw_output = result.get("stdout", "")
        suggestions = []
        for item in raw_output.splitlines():
            item = item.strip()
            if not item:
                continue
            suggestions.append(f"{base_prefix}{item}")

        payload = {
            "action": "kali_completion",
            "ok": result.get("ok", False),
            "partial": partial,
            "cwd": result.get("cwd", self.kali_session_cwd),
            "suggestions": suggestions[:limit],
        }
        if result.get("stderr"):
            payload["stderr"] = result["stderr"]
        return json.dumps(payload, indent=2)

    def run_kali_session_command(self, command: str, timeout: int = 180) -> str:
        with self.kali_lock:
            self.ensure_kali_session()
            assert self.kali_process is not None and self.kali_process.stdin is not None
            token = uuid.uuid4().hex
            start = f"__KAI_START__{token}"
            cwd_marker = f"__KAI_CWD__{token}__"
            end = f"__KAI_END__{token}__"
            wrapped = (
                f"echo {start}\n"
                f"{command}\n"
                f"status=$?\n"
                "printf '\\n'\n"
                f"printf '{cwd_marker}%s\\n' \"$(pwd)\"\n"
                f"printf '{end}%s\\n' \"$status\"\n"
            )
            self.kali_process.stdin.write(wrapped.encode("utf-8"))
            self.kali_process.stdin.flush()

            lines: list[str] = []
            current_cwd = self.kali_session_cwd
            status: int | None = None
            started = False
            deadline = time.time() + timeout

            while time.time() < deadline:
                try:
                    line = self.kali_queue.get(timeout=0.5)
                except Empty:
                    continue

                if not started:
                    if line == start:
                        started = True
                    continue

                if line.startswith(cwd_marker):
                    current_cwd = line[len(cwd_marker) :]
                    continue
                if line.startswith(end):
                    try:
                        status = int(line[len(end) :])
                    except ValueError:
                        status = -1
                    break
                lines.append(line)

            if status is None:
                raise RuntimeError("Timed out waiting for Kali session command to finish.")

            self.kali_session_cwd = current_cwd
            payload = {
                "action": "kali_session_command",
                "command": command,
                "cwd": current_cwd,
                "returncode": status,
                "stdout": "\n".join(lines).strip()[:12000],
                "stderr": "",
                "ok": status == 0,
                **self.classify_command(command, shell="bash"),
            }
            return json.dumps(payload, indent=2)

    def ask_kali_helper(self, prompt: str, use_web: bool = False) -> str:
        kai_cmd = "/home/tryagain/.local/bin/kai"
        args = ["wsl.exe", "-d", "kali-linux", "--", kai_cmd]
        if use_web:
            args.append("--web")
        args.append(prompt)
        result = self._run_native(args, timeout=240)
        payload = {
            "action": "ask_kali_helper",
            "prompt": prompt,
            "use_web": use_web,
            **result,
        }
        payload["ok"] = result["returncode"] == 0
        return json.dumps(payload, indent=2)

    def search_web(self, query: str, max_results: int = 5) -> str:
        return json.dumps(self.tavily.search(query=query, max_results=max_results), indent=2)

    def _run_native(self, args: list[str], timeout: int = 120, cwd: Path | None = None) -> dict:
        try:
            completed = subprocess.run(
                args,
                cwd=str(cwd or self.workspace),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "command": args,
                "returncode": completed.returncode,
                "stdout": completed.stdout.strip()[:12000],
                "stderr": completed.stderr.strip()[:6000],
            }
        except subprocess.TimeoutExpired:
            return {
                "command": args,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
            }
        except Exception as exc:
            return {
                "command": args,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command failed: {exc}",
            }

    def _ensure_command(self, command: str) -> tuple[bool, str]:
        candidates = {
            "git": ["git", "--version"],
            "node": ["node", "--version"],
            "npm": ["npm.cmd", "--version"],
            "python": ["python", "--version"],
            "tesseract": [str(TESSERACT_PATH), "--version"],
        }
        if command in candidates:
            check = self._run_native(candidates[command], timeout=20)
            if check["returncode"] == 0:
                return True, f"{command} already available."

        installers = {
            "git": ["winget", "install", "--id", "Git.Git", "--exact", "--accept-package-agreements", "--accept-source-agreements"],
            "node": ["winget", "install", "--id", "OpenJS.NodeJS", "--exact", "--accept-package-agreements", "--accept-source-agreements"],
            "npm": ["winget", "install", "--id", "OpenJS.NodeJS", "--exact", "--accept-package-agreements", "--accept-source-agreements"],
            "python": ["winget", "install", "--id", "Python.Python.3.12", "--exact", "--accept-package-agreements", "--accept-source-agreements"],
            "tesseract": ["winget", "install", "--id", "UB-Mannheim.TesseractOCR", "--exact", "--accept-package-agreements", "--accept-source-agreements"],
        }
        install_args = installers.get(command)
        if not install_args:
            return False, f"No automatic installer is configured for {command}."

        result = self._run_native(install_args, timeout=900)
        if result["returncode"] == 0:
            return True, f"Installed {command}."
        return False, result["stderr"] or result["stdout"] or f"Failed to install {command}."

    def _resolve_path(self, raw_path: str) -> Path:
        raw_path = raw_path.strip().strip('"').strip("'")
        candidate = Path(raw_path)
        if candidate.is_absolute():
            return candidate
        return (self.workspace / candidate).resolve()

    def _to_wsl_path(self, path: Path) -> str:
        path = path.resolve()
        drive = path.drive.rstrip(":").lower()
        parts = [part for part in path.parts[1:] if part not in (path.drive, "\\", "/")]
        joined = "/".join(parts)
        return f"/mnt/{drive}/{joined}"

    def open_path(self, path: str) -> str:
        target = self._resolve_path(path)
        if not target.exists():
            return json.dumps({"action": "open_path", "ok": False, "error": f"Path not found: {target}"}, indent=2)
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
            return json.dumps({"action": "open_path", "ok": True, "path": str(target)}, indent=2)
        except Exception as exc:
            return json.dumps({"action": "open_path", "ok": False, "path": str(target), "error": str(exc)}, indent=2)

    def write_file(self, path: str, content: str) -> str:
        target = self._resolve_path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return json.dumps(
                {
                    "action": "write_file",
                    "ok": True,
                    "path": str(target),
                    "chars_written": len(content),
                },
                indent=2,
            )
        except Exception as exc:
            return json.dumps({"action": "write_file", "ok": False, "path": str(target), "error": str(exc)}, indent=2)

    def append_file(self, path: str, content: str) -> str:
        target = self._resolve_path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as handle:
                handle.write(content)
            return json.dumps(
                {
                    "action": "append_file",
                    "ok": True,
                    "path": str(target),
                    "chars_appended": len(content),
                },
                indent=2,
            )
        except Exception as exc:
            return json.dumps({"action": "append_file", "ok": False, "path": str(target), "error": str(exc)}, indent=2)

    def replace_in_file(self, path: str, old_text: str, new_text: str) -> str:
        target = self._resolve_path(path)
        if not target.exists():
            return json.dumps({"action": "replace_in_file", "ok": False, "path": str(target), "error": "File not found."}, indent=2)
        try:
            original = target.read_text(encoding="utf-8", errors="replace")
            if old_text not in original:
                return json.dumps(
                    {
                        "action": "replace_in_file",
                        "ok": False,
                        "path": str(target),
                        "error": "Target text was not found in the file.",
                    },
                    indent=2,
                )
            updated = original.replace(old_text, new_text, 1)
            target.write_text(updated, encoding="utf-8")
            return json.dumps(
                {
                    "action": "replace_in_file",
                    "ok": True,
                    "path": str(target),
                    "replaced_chars": len(old_text),
                    "new_chars": len(new_text),
                },
                indent=2,
            )
        except Exception as exc:
            return json.dumps({"action": "replace_in_file", "ok": False, "path": str(target), "error": str(exc)}, indent=2)

    def extract_zip(self, archive_path: str, destination: str | None = None) -> str:
        archive = self._resolve_path(archive_path)
        if not archive.exists():
            return json.dumps({"action": "extract_zip", "ok": False, "error": f"Archive not found: {archive}"}, indent=2)
        target_dir = self._resolve_path(destination) if destination else archive.with_suffix("")
        target_dir.mkdir(parents=True, exist_ok=True)
        result = self._run_native(
            ["powershell", "-NoProfile", "-Command", f"Expand-Archive -LiteralPath '{archive}' -DestinationPath '{target_dir}' -Force"],
            timeout=600,
        )
        payload = {"action": "extract_zip", "archive": str(archive), "destination": str(target_dir), **result}
        payload["ok"] = result["returncode"] == 0
        return json.dumps(payload, indent=2)

    def clone_repo(self, repo_url: str, destination: str | None = None) -> str:
        ok, ensure_msg = self._ensure_command("git")
        if not ok:
            return json.dumps({"action": "clone_repo", "ok": False, "error": ensure_msg}, indent=2)
        repo_name = Path(repo_url.rstrip("/")).stem or "repo"
        target = self._resolve_path(destination) if destination else (self.workspace / repo_name)
        result = self._run_native(["git", "clone", repo_url, str(target)], timeout=1200)
        payload = {"action": "clone_repo", "repo_url": repo_url, "destination": str(target), "setup": ensure_msg, **result}
        payload["ok"] = result["returncode"] == 0
        return json.dumps(payload, indent=2)

    def install_project(self, target_path: str) -> str:
        target = self._resolve_path(target_path)
        if not target.exists():
            return json.dumps({"action": "install_project", "ok": False, "error": f"Project path not found: {target}"}, indent=2)

        steps: list[dict] = []
        if (target / "package.json").exists():
            ok, msg = self._ensure_command("npm")
            steps.append({"tool": "npm", "setup": msg})
            if ok:
                steps.append(self._run_native(["npm.cmd", "install"], cwd=target, timeout=1800))
        if (target / "requirements.txt").exists():
            ok, msg = self._ensure_command("python")
            steps.append({"tool": "python", "setup": msg})
            if ok:
                steps.append(self._run_native(["python", "-m", "pip", "install", "-r", "requirements.txt"], cwd=target, timeout=1800))
        if (target / "pyproject.toml").exists() and not (target / "requirements.txt").exists():
            ok, msg = self._ensure_command("python")
            steps.append({"tool": "python", "setup": msg})
            if ok:
                steps.append(self._run_native(["python", "-m", "pip", "install", "-e", "."], cwd=target, timeout=1800))

        if not steps:
            return json.dumps(
                {
                    "action": "install_project",
                    "ok": False,
                    "path": str(target),
                    "error": "No supported project manifest found. I looked for package.json, requirements.txt, and pyproject.toml.",
                },
                indent=2,
            )

        ok = any(isinstance(step, dict) and step.get("returncode") == 0 for step in steps)
        return json.dumps({"action": "install_project", "path": str(target), "ok": ok, "steps": steps}, indent=2)

    def run_project(self, target_path: str) -> str:
        target = self._resolve_path(target_path)
        if not target.exists():
            return json.dumps({"action": "run_project", "ok": False, "error": f"Project path not found: {target}"}, indent=2)

        stack_launcher = target / "tools" / "launch_kai_stack.ps1"
        panel_launcher = target / "tools" / "launch_kai_panel.ps1"
        if stack_launcher.exists() or panel_launcher.exists():
            launcher = stack_launcher if stack_launcher.exists() else panel_launcher
            result = self._run_native(
                ["powershell", "-NoProfile", "-Command", f"Start-Process powershell -ArgumentList '-ExecutionPolicy','Bypass','-File','{launcher}'"],
                timeout=60,
            )
            payload = {"action": "run_project", "path": str(target), "runner": str(launcher), **result}
            payload["ok"] = result["returncode"] == 0
            return json.dumps(payload, indent=2)

        if (target / "package.json").exists():
            ok, msg = self._ensure_command("npm")
            if not ok:
                return json.dumps({"action": "run_project", "ok": False, "path": str(target), "error": msg}, indent=2)

            package_text = (target / "package.json").read_text(encoding="utf-8", errors="replace")
            script = "dev" if '"dev"' in package_text else "start" if '"start"' in package_text else None
            if not script:
                return json.dumps(
                    {"action": "run_project", "ok": False, "path": str(target), "error": "No npm dev/start script found."},
                    indent=2,
                )
            result = self._run_native(
                ["powershell", "-NoProfile", "-Command", f"Start-Process powershell -ArgumentList '-NoExit','-Command','cd \"{target}\"; npm.cmd run {script}'"],
                timeout=60,
            )
            payload = {"action": "run_project", "path": str(target), "runner": f"npm run {script}", **result}
            payload["ok"] = result["returncode"] == 0
            return json.dumps(payload, indent=2)

        for candidate in ("main.py", "app.py"):
            file_path = target / candidate
            if file_path.exists():
                ok, msg = self._ensure_command("python")
                if not ok:
                    return json.dumps({"action": "run_project", "ok": False, "path": str(target), "error": msg}, indent=2)
                result = self._run_native(
                    ["powershell", "-NoProfile", "-Command", f"Start-Process powershell -ArgumentList '-NoExit','-Command','cd \"{target}\"; python \"{candidate}\"'"],
                    timeout=60,
                )
                payload = {"action": "run_project", "path": str(target), "runner": f"python {candidate}", **result}
                payload["ok"] = result["returncode"] == 0
                return json.dumps(payload, indent=2)

        return json.dumps(
            {
                "action": "run_project",
                "ok": False,
                "path": str(target),
                "error": "No supported runnable entrypoint found. I looked for package.json scripts and main.py/app.py.",
            },
            indent=2,
        )

    def run_tests(self, target_path: str) -> str:
        target = self._resolve_path(target_path)
        if not target.exists():
            return json.dumps({"action": "run_tests", "ok": False, "error": f"Project path not found: {target}"}, indent=2)

        if (target / "package.json").exists():
            ok, msg = self._ensure_command("npm")
            if not ok:
                return json.dumps({"action": "run_tests", "ok": False, "path": str(target), "error": msg}, indent=2)
            package_text = (target / "package.json").read_text(encoding="utf-8", errors="replace")
            if '"test"' not in package_text:
                return json.dumps({"action": "run_tests", "ok": False, "path": str(target), "error": "No npm test script found."}, indent=2)
            result = self._run_native(["npm.cmd", "test", "--", "--runInBand"], cwd=target, timeout=1800)
            payload = {"action": "run_tests", "path": str(target), "runner": "npm test", **result}
            payload["ok"] = result["returncode"] == 0
            return json.dumps(payload, indent=2)

        if (target / "pytest.ini").exists() or (target / "pyproject.toml").exists() or any(target.glob("test_*.py")) or (target / "tests").exists():
            ok, msg = self._ensure_command("python")
            if not ok:
                return json.dumps({"action": "run_tests", "ok": False, "path": str(target), "error": msg}, indent=2)
            result = self._run_native(["python", "-m", "pytest"], cwd=target, timeout=1800)
            payload = {"action": "run_tests", "path": str(target), "runner": "python -m pytest", **result}
            payload["ok"] = result["returncode"] == 0
            return json.dumps(payload, indent=2)

        return json.dumps(
            {
                "action": "run_tests",
                "ok": False,
                "path": str(target),
                "error": "No supported test entrypoint found. I looked for npm test and pytest-style layouts.",
            },
            indent=2,
        )

    def setup_github_project(self, repo_url: str, destination: str | None = None) -> str:
        clone_data = json.loads(self.clone_repo(repo_url=repo_url, destination=destination))
        if not clone_data.get("ok"):
            return json.dumps({"action": "setup_github_project", "ok": False, "clone": clone_data}, indent=2)
        install_data = json.loads(self.install_project(clone_data["destination"]))
        return json.dumps(
            {
                "action": "setup_github_project",
                "ok": bool(clone_data.get("ok") and install_data.get("ok")),
                "clone": clone_data,
                "install": install_data,
            },
            indent=2,
        )

    def codex_edit(self, instruction: str, target_path: str | None = None) -> str:
        target = self._resolve_path(target_path) if target_path else self.workspace
        if not target.exists():
            return json.dumps({"action": "codex_edit", "ok": False, "error": f"Target path not found: {target}"}, indent=2)

        output_path = self.tmp_dir / "kai_codex_last_message.txt"
        wsl_target = self._to_wsl_path(target if target.is_dir() else target.parent)
        prompt = (
            "You are editing code for Kai's local operator workspace. "
            "Make the requested changes directly in files. Keep changes focused. "
            "At the end, provide a short summary and a flat list of changed file paths.\n\n"
            f"Task:\n{instruction}\n"
        )
        command = (
            f"cd '{wsl_target}' && "
            f"codex exec --skip-git-repo-check --sandbox workspace-write "
            f"--output-last-message '/mnt/c/{self._to_wsl_path(output_path).split('/mnt/c/',1)[1]}' "
            f"\"{prompt.replace(chr(34), chr(92) + chr(34))}\""
        )
        result = self.run_wsl(command, timeout=1800)
        payload = json.loads(result)
        summary = ""
        try:
            if output_path.exists():
                summary = output_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            summary = ""
        payload.update(
            {
                "action": "codex_edit",
                "ok": payload.get("returncode") == 0,
                "target": str(target),
                "summary": summary,
            }
        )
        return json.dumps(payload, indent=2)

    def codex_edit_and_test(self, instruction: str, target_path: str | None = None) -> str:
        edit_data = json.loads(self.codex_edit(instruction=instruction, target_path=target_path))
        target = target_path or str(self.workspace)
        if not edit_data.get("ok"):
            return json.dumps({"action": "codex_edit_and_test", "ok": False, "edit": edit_data}, indent=2)
        test_data = json.loads(self.run_tests(target))
        return json.dumps(
            {
                "action": "codex_edit_and_test",
                "ok": bool(edit_data.get("ok") and test_data.get("ok")),
                "edit": edit_data,
                "tests": test_data,
            },
            indent=2,
        )

    def read_file(self, path: str, max_chars: int = 8000) -> str:
        target = Path(path)
        if not target.is_absolute():
            target = (self.workspace / target).resolve()
        if not target.exists():
            return f"File not found: {target}"
        if target.is_dir():
            return f"Path is a directory: {target}"
        try:
            return target.read_text(encoding="utf-8", errors="replace")[:max_chars]
        except Exception as exc:
            return f"File read failed: {exc}"

    def list_files(self, relative: str = ".", limit: int = 200) -> str:
        root = (self.workspace / relative).resolve()
        if not root.exists():
            return f"Path not found: {root}"
        if root.is_file():
            return str(root)
        ignore_dirs = {".git", "node_modules", ".venv", ".godot", "__pycache__", "dist", "build"}
        entries = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ignore_dirs]
            for name in sorted(filenames):
                entries.append(str(Path(dirpath) / name))
                if len(entries) >= limit:
                    return "\n".join(entries)
        return "\n".join(entries)

    def _ocr_image(self, image_path: Path, text_base: Path) -> str:
        if not TESSERACT_PATH.exists():
            return f"Tesseract not found at {TESSERACT_PATH}"
        completed = subprocess.run(
            [str(TESSERACT_PATH), str(image_path), str(text_base)],
            cwd=str(self.workspace),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if completed.returncode != 0:
            return json.dumps(
                {"error": "ocr_failed", "stderr": completed.stderr.strip()},
                indent=2,
            )
        text_path = text_base.with_suffix(".txt")
        if not text_path.exists():
            return "OCR finished but no text file was produced."
        return text_path.read_text(encoding="utf-8", errors="replace")[:12000]

    def capture_screen_ocr(self) -> str:
        image_path = self.tmp_dir / "kai_screen_ocr.png"
        text_base = self.tmp_dir / "kai_screen_ocr"
        capture_command = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            "$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            "$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height; "
            "$graphics = [System.Drawing.Graphics]::FromImage($bmp); "
            "$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size); "
            f"$bmp.Save('{image_path}', [System.Drawing.Imaging.ImageFormat]::Png); "
            "$graphics.Dispose(); "
            "$bmp.Dispose()"
        )
        self.run_shell(capture_command, timeout=20)
        if not image_path.exists():
            return "Screen capture failed: no image produced."
        return self._ocr_image(image_path=image_path, text_base=text_base)

    def capture_active_window_ocr(self) -> str:
        image_path = self.tmp_dir / "kai_active_window_ocr.png"
        text_base = self.tmp_dir / "kai_active_window_ocr"
        capture_command = (
            "Add-Type -AssemblyName System.Drawing; "
            "Add-Type @'\n"
            "using System;\n"
            "using System.Runtime.InteropServices;\n"
            "public static class KaiWin32 {\n"
            "  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }\n"
            "  [DllImport(\"user32.dll\")] public static extern IntPtr GetForegroundWindow();\n"
            "  [DllImport(\"user32.dll\")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);\n"
            "}\n"
            "'@; "
            "$hwnd = [KaiWin32]::GetForegroundWindow(); "
            "if ($hwnd -eq [IntPtr]::Zero) { exit 2 }; "
            "$rect = New-Object KaiWin32+RECT; "
            "if (-not [KaiWin32]::GetWindowRect($hwnd, [ref]$rect)) { exit 3 }; "
            "$width = [Math]::Max(1, $rect.Right - $rect.Left); "
            "$height = [Math]::Max(1, $rect.Bottom - $rect.Top); "
            "$bmp = New-Object System.Drawing.Bitmap $width, $height; "
            "$graphics = [System.Drawing.Graphics]::FromImage($bmp); "
            "$graphics.CopyFromScreen((New-Object System.Drawing.Point($rect.Left, $rect.Top)), [System.Drawing.Point]::Empty, (New-Object System.Drawing.Size($width, $height))); "
            f"$bmp.Save('{image_path}', [System.Drawing.Imaging.ImageFormat]::Png); "
            "$graphics.Dispose(); "
            "$bmp.Dispose()"
        )
        result = self.run_shell(capture_command, timeout=20)
        if not image_path.exists():
            return "Active window capture failed, falling back to full screen.\n\n" + self.capture_screen_ocr()
        return self._ocr_image(image_path=image_path, text_base=text_base)
