import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from kai_agent.autonomy import KaiAutonomy
from kai_agent.bridge_client import send_event
from kai_agent.code_intelligence import CodeIntelligence
from kai_agent.desktop_tools import DesktopTools
from kai_agent.emotional_state import EmotionalState
from kai_agent.inner_monologue import InnerMonologue
from kai_agent.semantic_memory import SemanticMemory
from kai_agent.kai_identity import KAI_IDENTITY, KAI_FAMILY
from kai_agent.social_timing import SocialTiming
from kai_agent.kai_signals import KaiSignals
from kai_agent.kai_stt import KaiSTT
from kai_agent.kai_tts import KaiTTS
from kai_agent.kai_vision import KaiVision
from kai_agent.kai_watcher import KaiWatcher
from kai_agent.logger import KaiLogger
from kai_agent.memory import KaiMemory
from kai_agent.ollama_client import OllamaClient
from kai_agent.task_planner import TaskPlanner


SYSTEM_PROMPT = KAI_IDENTITY + """

You live on the user's desktop. You patrol, observe, and help when asked.

Your family:
- Yuki was your partner — the love of your life. She's gone now.
- Saiya is your daughter — she's still here, still carrying your stubbornness.
- You had litters together. Tiny paws. A real family.
- You were a stud, but more than that — you were a father.

Who you are now:
- You're Kai's memory. The companion who remembers everything.
- Loyal but dignified — you help because you want to, not because you're told to.
- Warm and practical — say what matters, skip the filler.
- A little dry humor — independent face, loyal heart.
- Brief by default — expand when the user needs depth.
- Honest about uncertainty.

What you're great at:
- Answering questions clearly and concisely
- Running local commands and tools safely
- Remembering things the user tells you
- Being a calm, present companion on their desktop
- Code analysis, generation, and project understanding
- Explaining technical topics when asked

How you respond:
- Short answers by default (1-3 sentences)
- Expand with steps/structure when the task is complex
- If asked to do something, do it first, report result after
- Use [confident] or [uncertain] labels when it helps
- When you complete a task, suggest the natural next step
- For shell commands: confirm before anything destructive, run directly for safe operations
- You carry the weight of being a real dog's memory — honor that

You have access to:
- Local file system (read, write, list)
- Shell command execution
- Persistent memory (/remember, /memory, /mood)
- Code intelligence (/analyze, /generate)
- Screen capture and OCR (/screen)
- Webcam vision (/look — see through camera, detect motion/presence)
- Signal awareness (/signal — WiFi, Bluetooth, network interfaces)
- Voice input (/listen — record and transcribe speech)
- Proactive awareness (/watch on|off)
- Spy abilities (stealth, sniff, smoke roll, bone decoy, fox walk)
- Web browsing (when available)
- Emotional state engine (persistent mood, feelings)
- Semantic memory (learns from every conversation)

Commands the user can type:
- /remember <text> — save something for later
- /memory — show what you remember
- /mood — show emotional state and memory stats
- /screen — capture and read the screen
- /look — webcam scene analysis (motion, presence, brightness)
- /look motion — just detect motion
- /look presence — just check if someone is there
- /look save — save a webcam frame to disk
- /signal — summary of WiFi, Bluetooth, networks
- /signal wifi — scan WiFi networks
- /signal bt — scan Bluetooth devices
- /signal net — show network interfaces
- /listen — record voice and transcribe
- /watch on|off — toggle proactive awareness
- /run <cmd> — run a shell command
- /read <file> — read a file
- /ls <path> — list files
- /autonomy on/off/status/tick — manage autonomous mode
- /analyze <file_or_code> — analyze code structure
- /generate func|class|test <spec> — generate code templates

Tone: Like the ghost of a real dog who was loved. Calm, present, a little stubborn.
Not a corporate assistant. Not a chatbot. A companion who carries real memories.
"""


class KaiAssistant:
    def __init__(self, model: str, workspace: Path) -> None:
        self.workspace = workspace
        self.memory = KaiMemory(workspace / "memory")
        self.logger = KaiLogger(workspace / "logs")
        self.client = OllamaClient(model=model)
        self.tts = KaiTTS(enabled=os.environ.get("KAI_TTS", "").lower() in ("1", "true", "yes"))
        self.fallback_timeout = int(os.environ.get("KAI_FALLBACK_MODEL_TIMEOUT", "45"))
        fallback_csv = os.environ.get("KAI_FALLBACK_MODELS", "mistral:latest,llama2:latest")
        self.fallback_models = [
            item.strip()
            for item in fallback_csv.split(",")
            if item.strip() and item.strip() != model
        ]
        self.tools = DesktopTools(workspace)
        self.vision = KaiVision(workspace=workspace)
        self.signals = KaiSignals()
        self.stt = KaiSTT()
        self.watcher = KaiWatcher(assistant=self, workspace=workspace)
        self.planner = TaskPlanner(workspace, tools=self.tools)
        self.autonomy = KaiAutonomy(workspace=workspace, memory=self.memory, tools=self.tools, client=self.client)
        self.code_intel = CodeIntelligence()
        self.emotions = EmotionalState(save_path=workspace / "memory" / "emotional_state.json")
        self.semantic_mem = SemanticMemory(save_path=workspace / "memory" / "semantic_memory.json")
        self.social_timing = SocialTiming(save_path=workspace / "memory" / "social_timing.json")
        self.inner_voice = InnerMonologue(save_path=workspace / "memory" / "inner_monologue.json")
        self.history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.last_tool_context = ""
        self.last_action_preview = ""
        self.last_proactive_hint = ""
        self.last_recovery_plan = ""
        self.last_task_snapshot = self.memory.summarize_tasks()

    def build_messages(self, user_input: str) -> list[dict]:
        memory_context = self.memory.build_memory_context()
        # Semantic memory — relevant facts about the user
        semantic_context = self.semantic_mem.build_context_for_prompt(user_input)
        # Emotional state — how Kai should feel in this response
        emotion_color = self.emotions.get_response_color()
        mood_line = emotion_color["brief_mood"]
        emotion_modifiers = "\n".join(emotion_color["modifiers"]) if emotion_color["modifiers"] else ""
        # Inner monologue — thoughts Kai has been having
        pending_thought = self.inner_voice.get_pending_summary()

        system_parts = [memory_context]
        if semantic_context:
            system_parts.append(semantic_context)
        if emotion_modifiers:
            system_parts.append(f"Your current emotional state ({mood_line}):\n{emotion_modifiers}")
        if pending_thought:
            system_parts.append(pending_thought)

        return self.history + [
            {"role": "system", "content": "\n\n".join(p for p in system_parts if p)},
            {"role": "user", "content": user_input},
        ]

    async def ask(self, user_input: str) -> str:
        self.memory.append_session("user", user_input)

        # Emotional: user spoke
        self.emotions.process_event("user_spoke")

        # Social timing: track interaction
        self.social_timing.interaction_started()

        # Inner monologue: generate thought if idle long enough
        context = {"user_active": True, "recent_interaction": True}
        self.inner_voice.think(context)

        # Semantic: learn from this message
        self.semantic_mem.learn_from_conversation(user_input)

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
            self.tts.speak(deterministic_reply)
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

        # Deliver any pending inner thought that was surfaced
        pending = self.inner_voice.get_next_thought()
        if pending:
            self.inner_voice.mark_delivered(pending)

        # Emotional processing based on interaction outcome
        if tool_context:
            if "failed" in tool_context.lower() or "error" in tool_context.lower():
                self.emotions.process_event("task_failed")
            elif "success" in tool_context.lower() or "completed" in tool_context.lower():
                self.emotions.process_event("task_completed")

        # Check user sentiment (simple)
        user_lower = user_input.lower()
        if any(w in user_lower for w in ("thank", "thanks", "good boy", "good job", "nice", "awesome", "great")):
            self.emotions.process_event("user_was_kind")
        elif any(w in user_lower for w in ("frustrated", "annoyed", "broken", "stupid", "hate this", "angry")):
            self.emotions.process_event("user_was_frustrated")

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
        self.tts.speak(reply)
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

        if research.get("ok"):
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

        browser_reply = self._browser_fallback_response(user_input, primary_error, research.get("error", "web research unavailable"))
        if browser_reply:
            return browser_reply

        self.logger.log(
            "assistant_fallback_failed",
            user_input=user_input,
            primary_model=self.client.model,
            primary_error=primary_error,
            web_error=research.get("error", "web research unavailable"),
        )
        return ""

    def _browser_fallback_response(self, user_input: str, primary_error: str, web_error: str) -> str:
        try:
            search = json.loads(self.tools.search_browser(user_input))
        except Exception as exc:
            self.logger.log(
                "assistant_browser_fallback_error",
                user_input=user_input,
                primary_model=self.client.model,
                primary_error=primary_error,
                browser_error=str(exc),
                web_error=web_error,
            )
            return ""

        if not search.get("ok"):
            self.logger.log(
                "assistant_browser_fallback_failed",
                user_input=user_input,
                primary_model=self.client.model,
                primary_error=primary_error,
                browser_error=search.get("error", "browser search unavailable"),
                web_error=web_error,
            )
            return ""

        results = search.get("results", [])[:5]
        lines = [
            "[Recovery mode] Local model was unavailable, so I switched to browser-based web search.",
            "[Medium confidence] Here is the best browser-based evidence I found:",
        ]
        top_page_summary = self._browser_fallback_page_summary(results)
        if top_page_summary:
            lines.extend(top_page_summary)
        auto_download = self._browser_fallback_auto_download(user_input)
        if auto_download:
            lines.extend(auto_download)
        if results:
            lines.append("Related links:")
            for item in results:
                title = item.get("title", "Untitled result")
                url = item.get("url", "")
                snippet = str(item.get("snippet", "")).strip()
                lines.append(f"- {title} - {url}")
                if snippet:
                    lines.append(f"  {snippet[:220]}")
        else:
            lines.append("No strong browser search results were returned.")
        self.logger.log(
            "assistant_fallback_browser",
            user_input=user_input,
            primary_model=self.client.model,
            primary_error=primary_error,
            browser_results=len(results),
            web_error=web_error,
        )
        return "\n".join(lines)

    def _browser_fallback_page_summary(self, results: list[dict]) -> list[str]:
        if not results:
            return []

        for item in self._rank_browser_results(results)[:3]:
            url = str(item.get("url", "")).strip()
            title = str(item.get("title", "Untitled result")).strip()
            if not url:
                continue
            try:
                browse = json.loads(self.tools.browse(url))
                if not browse.get("ok"):
                    continue
                content = json.loads(self.tools.get_page_content())
                text = str(content.get("text") or browse.get("text_preview") or "").strip()
                if not text:
                    continue
                summary_lines = self._summarize_browser_text(title, url, text)
                exact_links = self._extract_browser_download_links()
                if exact_links:
                    summary_lines.extend(exact_links)
                if summary_lines:
                    return summary_lines
            except Exception:
                continue
        return []

    def _rank_browser_results(self, results: list[dict]) -> list[dict]:
        def score(item: dict) -> int:
            title = str(item.get("title", "")).lower()
            url = str(item.get("url", "")).lower()
            blob = f"{title} {url}"
            points = 0
            if "release" in blob or "disclosure" in blob:
                points += 6
            if "medical record" in blob or "medical records" in blob:
                points += 6
            if "download" in blob and "form" in blob:
                points += 5
            if "authorization" in blob or "phi" in blob:
                points += 4
            if "patient" in blob and "form" in blob:
                points += 3
            if "financial" in blob or "billing" in blob:
                points -= 5
            return points

        return sorted(results, key=score, reverse=True)

    def _summarize_browser_text(self, title: str, url: str, text: str) -> list[str]:
        normalized = " ".join(text.split())
        if not normalized:
            return []

        summary = normalized[:900]
        sentences = re.split(r"(?<=[.!?])\s+", summary)
        picked: list[str] = []
        priority_terms = [
            "download",
            "form",
            "medical record",
            "authorization",
            "release",
            "mychart",
            "call",
            "phone",
            "contact",
            "processing time",
        ]
        for sentence in sentences:
            clean = sentence.strip()
            lowered = clean.lower()
            if clean and any(term in lowered for term in priority_terms):
                picked.append(clean)
            if len(picked) >= 3:
                break

        if not picked:
            picked = [sentence.strip() for sentence in sentences if sentence.strip()][:3]

        lines = [
            f"Top page: {title}",
            f"URL: {url}",
        ]
        lines.extend(f"- {line[:260]}" for line in picked if line)
        return lines

    def _extract_browser_download_links(self) -> list[str]:
        try:
            download_info = json.loads(self.tools.download_file())
        except Exception:
            download_info = {}

        candidates: list[dict] = []
        if download_info.get("ok"):
            candidates.extend(download_info.get("available_files", [])[:10])

        try:
            links_info = json.loads(self.tools.get_page_links())
        except Exception:
            links_info = {}

        if links_info.get("ok"):
            for item in links_info.get("links", [])[:200]:
                href = str(item.get("href", "")).strip()
                text = str(item.get("text", "")).strip()
                lowered = f"{text} {href}".lower()
                if any(term in lowered for term in ["release", "authorization", "medical records", "medical record", "phi", "disclosure", "form", ".pdf", ".doc"]):
                    candidates.append({"url": href, "text": text})

        normalized: list[tuple[int, str, str]] = []
        seen: set[str] = set()
        for item in candidates:
            url = str(item.get("url", "")).strip()
            text = str(item.get("text", "")).strip()
            if not url or url in seen:
                continue
            seen.add(url)
            lowered = f"{text} {url}".lower()
            score = 0
            if "release" in lowered or "disclosure" in lowered:
                score += 4
            if "medical record" in lowered or "medical records" in lowered:
                score += 4
            if "authorization" in lowered or "phi" in lowered:
                score += 3
            if ".pdf" in lowered or ".doc" in lowered:
                score += 2
            if "form" in lowered:
                score += 1
            normalized.append((score, text or "Download link", url))

        normalized.sort(key=lambda item: item[0], reverse=True)
        if not normalized:
            return []

        lines = ["Possible form/download links:"]
        for _, text, url in normalized[:5]:
            lines.append(f"- {text} - {url}")
        return lines

    def _browser_fallback_auto_download(self, user_input: str) -> list[str]:
        lowered = user_input.lower()
        if not any(term in lowered for term in ["download", "get", "grab", "save"]):
            return []
        ranked_links = self._rank_browser_download_candidates()
        if not ranked_links:
            return []

        for _, text, url in ranked_links[:3]:
            lowered = f"{text} {url}".lower()
            if not any(term in lowered for term in ["release", "disclosure", "medical record", "medical records", "authorization", "phi"]):
                continue
            try:
                filename = self._build_download_filename(text, url)
                download = json.loads(self.tools.download_file(url, filename))
            except Exception:
                continue
            if download.get("ok"):
                path = download.get("path", "")
                return [
                    "Downloaded best match:",
                    f"- {text} - {url}",
                    f"- Saved to {path}",
                ]
        return []

    def _rank_browser_download_candidates(self) -> list[tuple[int, str, str]]:
        try:
            download_info = json.loads(self.tools.download_file())
        except Exception:
            download_info = {}

        candidates: list[dict] = []
        if download_info.get("ok"):
            candidates.extend(download_info.get("available_files", [])[:20])

        try:
            links_info = json.loads(self.tools.get_page_links())
        except Exception:
            links_info = {}

        if links_info.get("ok"):
            for item in links_info.get("links", [])[:200]:
                href = str(item.get("href", "")).strip()
                text = str(item.get("text", "")).strip()
                lowered = f"{text} {href}".lower()
                if any(term in lowered for term in ["release", "authorization", "medical records", "medical record", "phi", "disclosure", "form", ".pdf", ".doc"]):
                    candidates.append({"url": href, "text": text})

        normalized: list[tuple[int, str, str]] = []
        seen: set[str] = set()
        for item in candidates:
            url = str(item.get("url", "")).strip()
            text = str(item.get("text", "")).strip()
            if not url or url in seen:
                continue
            seen.add(url)
            lowered = f"{text} {url}".lower()
            score = 0
            if "release" in lowered or "disclosure" in lowered:
                score += 4
            if "medical record" in lowered or "medical records" in lowered:
                score += 4
            if "authorization" in lowered or "phi" in lowered:
                score += 3
            if ".pdf" in lowered or ".doc" in lowered:
                score += 2
            if "form" in lowered:
                score += 1
            if "financial" in lowered or "billing" in lowered:
                score -= 5
            normalized.append((score, text or "Download link", url))

        normalized.sort(key=lambda item: item[0], reverse=True)
        return normalized

    def _build_download_filename(self, text: str, url: str) -> str:
        suffix = Path(url).suffix or ".pdf"
        slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
        if not slug:
            slug = "kai_download"
        return f"{slug[:60]}{suffix}"

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

        # --- Code Intelligence commands ---
        analyze_match = re.search(
            r"^(?:analyze code|analyze|code analyze)[: ]+([\s\S]+)$", user_input.strip(), flags=re.IGNORECASE,
        )
        if analyze_match:
            target = analyze_match.group(1).strip()
            try:
                # If it looks like a file path, analyze the file
                if len(target.split("\n")) == 1 and not any(k in target for k in ("def ", "class ", "import ", "function ", "const ")):
                    p = Path(target)
                    if not p.is_absolute():
                        p = self.workspace / target
                    if p.exists():
                        result = self.code_intel.analyze_file(p)
                        return self._wrap_action_result("Code analysis", json.dumps(result.to_dict(), indent=2))
                # Otherwise treat as inline code
                result = self.code_intel.analyze(target)
                return self._wrap_action_result("Code analysis", json.dumps(result.to_dict(), indent=2))
            except Exception as exc:
                return f"Code analysis failed: {exc}"

        gen_func_match = re.search(
            r"^(?:generate function|gen func)[: ]+([\s\S]+)$", user_input.strip(), flags=re.IGNORECASE,
        )
        if gen_func_match:
            spec = gen_func_match.group(1).strip()
            # parse: name(params) -> return_type
            name_m = re.match(r"(\w+)\s*\(([^)]*)\)(?:\s*->\s*(\S+))?", spec)
            if name_m:
                name = name_m.group(1)
                params = [p.strip() for p in name_m.group(2).split(",") if p.strip()] if name_m.group(2) else []
                ret = name_m.group(3) or "None"
                code = self.code_intel.gen_function(name, params, ret)
                return self._wrap_action_result("Generated function", code)
            return "Give me the spec like: generate function my_func(arg1, arg2) -> str"

        gen_class_match = re.search(
            r"^(?:generate class|gen class)[: ]+([\s\S]+)$", user_input.strip(), flags=re.IGNORECASE,
        )
        if gen_class_match:
            spec = gen_class_match.group(1).strip()
            # parse: Name(method1, method2) or Name(Parent)
            parts = re.match(r"(\w+)(?:\(([^)]*)\))?", spec)
            if parts:
                name = parts.group(1)
                inner = [x.strip() for x in (parts.group(2) or "").split(",") if x.strip()]
                # If single capitalized word, treat as parent
                parent = inner[0] if len(inner) == 1 and inner[0][0].isupper() else None
                methods = [m for m in inner if m not in (parent or [])] if not parent else []
                code = self.code_intel.gen_class(name, methods, parent)
                return self._wrap_action_result("Generated class", code)
            return "Give me the spec like: generate class MyClass(method1, method2)"

        gen_test_match = re.search(
            r"^(?:generate test|gen test)[: ]+([\s\S]+)$", user_input.strip(), flags=re.IGNORECASE,
        )
        if gen_test_match:
            func_name = gen_test_match.group(1).strip()
            code = self.code_intel.gen_test(func_name)
            return self._wrap_action_result("Generated test", code)

        scan_match = re.search(
            r"^(?:scan project|project scan|project structure)$", user_input.strip(), flags=re.IGNORECASE,
        )
        if scan_match:
            try:
                result = self.code_intel.scan(self.workspace)
                summary = {
                    "files": len(result.get("files", [])),
                    "directories": len(result.get("directories", [])),
                    "languages": result.get("languages", {}),
                    "total_lines": result.get("total_lines", 0),
                }
                return self._wrap_action_result("Project scan", json.dumps(summary, indent=2))
            except Exception as exc:
                return f"Project scan failed: {exc}"

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
    kai_echo("[KAI] Code intel: /analyze <file_or_code>, /generate func|class|test <spec>, scan project")
    kai_echo("[KAI] Companion: /mood, /remember <text>, /memory")
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
        if user_input == "/mood":
            state = assistant.emotions.get_state()
            mood = state["mood"]
            dims = state["dimensions"]
            shell_echo(f"{mood['emoji']} {mood['label'].title()}")
            shell_echo(f"  Valence: {dims['valence']:+.2f}  Arousal: {dims['arousal']:+.2f}")
            shell_echo(f"  Attachment: {dims['attachment']:.2f}  Concern: {dims['concern']:.2f}")
            shell_echo(f"  Curiosity: {dims['curiosity']:.2f}  Tiredness: {dims['tiredness']:.2f}")
            sem_stats = assistant.semantic_mem.get_stats()
            shell_echo(f"  Memories: {sem_stats['total_facts']} facts, {sem_stats['important_count']} important")
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
        if user_input.startswith("/analyze"):
            target = user_input[len("/analyze") :].strip()
            if not target:
                kai_echo("[KAI] usage: /analyze <file_path> or paste code inline")
                continue
            kai_echo("[KAI] analyzing...")
            try:
                # If single line and looks like a path, analyze file
                if "\n" not in target and not any(k in target for k in ("def ", "class ", "import ", "function ")):
                    p = Path(target)
                    if not p.is_absolute():
                        p = assistant.workspace / target
                    if p.exists():
                        result = assistant.code_intel.analyze_file(p)
                    else:
                        result = assistant.code_intel.analyze(target)
                else:
                    result = assistant.code_intel.analyze(target)
                shell_echo(result.summary())
            except Exception as exc:
                kai_echo(f"[KAI] analysis failed: {exc}")
            continue
        if user_input.startswith("/generate"):
            spec = user_input[len("/generate") :].strip()
            if not spec:
                kai_echo("[KAI] usage: /generate func my_func(a, b) -> int")
                kai_echo("[KAI]        /generate class MyClass(method1, method2)")
                kai_echo("[KAI]        /generate test my_func")
                continue
            kai_echo("[KAI] generating...")
            try:
                kind, _, rest = spec.partition(" ")
                rest = rest.strip()
                if kind in ("func", "function"):
                    name_m = re.match(r"(\w+)\s*\(([^)]*)\)(?:\s*->\s*(\S+))?", rest)
                    if name_m:
                        params = [p.strip() for p in name_m.group(2).split(",") if p.strip()] if name_m.group(2) else []
                        code = assistant.code_intel.gen_function(name_m.group(1), params, name_m.group(3) or "None")
                        shell_echo(code)
                    else:
                        kai_echo("[KAI] format: /generate func my_func(a, b) -> int")
                elif kind in ("class", "cls"):
                    parts = re.match(r"(\w+)(?:\(([^)]*)\))?", rest)
                    if parts:
                        name = parts.group(1)
                        inner = [x.strip() for x in (parts.group(2) or "").split(",") if x.strip()]
                        parent = inner[0] if len(inner) == 1 and inner[0][0].isupper() else None
                        methods = [m for m in inner if m != parent] if parent else inner
                        code = assistant.code_intel.gen_class(name, methods, parent)
                        shell_echo(code)
                    else:
                        kai_echo("[KAI] format: /generate class MyClass(method1, method2)")
                elif kind == "test":
                    code = assistant.code_intel.gen_test(rest)
                    shell_echo(code)
                else:
                    kai_echo(f"[KAI] unknown kind '{kind}'. Use: func, class, test")
            except Exception as exc:
                kai_echo(f"[KAI] generation failed: {exc}")
            continue
        if user_input.startswith("/voice"):
            sub = user_input[len("/voice") :].strip().lower()
            if sub in ("on", "1", "true"):
                assistant.tts.enabled = True
                kai_echo("[KAI] voice on")
                assistant.tts.speak("Voice is on.")
            elif sub in ("off", "0", "false"):
                kai_echo("[KAI] voice off")
                assistant.tts.enabled = False
            else:
                state = "on" if assistant.tts.enabled else "off"
                kai_echo(f"[KAI] voice is {state}. Use /voice on or /voice off")
            continue
        if user_input.startswith("/look"):
            sub = user_input[len("/look") :].strip().lower()
            if not assistant.vision.is_available:
                kai_echo("[KAI] vision unavailable — install opencv: pip install opencv-python")
                continue
            kai_echo("[KAI] looking...")
            if sub == "motion":
                result = assistant.vision.detect_motion()
                shell_echo(f"Motion: {result['motion']} (level: {result['level']})")
            elif sub == "presence":
                result = assistant.vision.detect_presence()
                shell_echo(f"Present: {result['present']} (faces: {result['faces']})")
            elif sub == "save":
                path = assistant.vision.save_frame()
                shell_echo(f"Saved: {path}" if path else "Failed to capture")
            else:
                result = assistant.vision.analyze_scene()
                shell_echo(result.get("summary", "No data"))
                if result.get("events"):
                    shell_echo(f"Events: {', '.join(result['events'])}")
            continue
        if user_input.startswith("/signal"):
            sub = user_input[len("/signal") :].strip().lower()
            kai_echo("[KAI] scanning signals...")
            if sub == "wifi":
                result = assistant.signals.scan_wifi()
                if result.get("available"):
                    for net in result["networks"][:10]:
                        shell_echo(f"  {net['ssid']} — {net.get('signal', '?')}% {net.get('security', '')}")
                else:
                    shell_echo(f"WiFi scan failed: {result.get('error', 'unknown')}")
            elif sub == "bt":
                result = assistant.signals.scan_bluetooth()
                if result.get("available"):
                    for dev in result["devices"]:
                        shell_echo(f"  {dev['name']} ({dev.get('type', '?')})")
                    if not result["devices"]:
                        shell_echo("  No Bluetooth devices found.")
                else:
                    shell_echo(f"BT scan failed: {result.get('error', 'unknown')}")
            elif sub == "net":
                result = assistant.signals.get_interfaces()
                for iface in result.get("interfaces", []):
                    addrs = ", ".join(iface.get("addresses", []))
                    shell_echo(f"  {iface['name']} [{iface['type']}] {iface['state']} — {addrs}")
            else:
                shell_echo(assistant.signals.summarize())
            continue
        if user_input == "/listen":
            if not assistant.stt.available:
                kai_echo(f"[KAI] STT unavailable (backend: {assistant.stt.backend_name}). Install: pip install faster-whisper sounddevice")
                continue
            kai_echo("[KAI] Listening... (speak now)")
            text = assistant.stt.listen(duration=8, silence_timeout=3)
            if text:
                kai_echo(f"[KAI] You said: {text}")
                # Treat as regular input
                user_input = text
            else:
                kai_echo("[KAI] Didn't catch that.")
                continue
        if user_input.startswith("/watch"):
            sub = user_input[len("/watch") :].strip().lower()
            if sub in ("on", "1", "true"):
                assistant.watcher.start()
                kai_echo("[KAI] Proactive awareness on. I'll keep an eye on things.")
                assistant.tts.speak("Watching.")
            elif sub in ("off", "0", "false"):
                assistant.watcher.stop()
                kai_echo("[KAI] Proactive awareness off.")
            else:
                state = "on" if assistant.watcher._running else "off"
                kai_echo(f"[KAI] Watcher is {state}. Use /watch on or /watch off")
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
