import argparse
import asyncio
import json
import os
import queue
import subprocess
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext, ttk

from kai_agent.assistant import KaiAssistant

# Shiba Inu warm palette — fox tones, cream, charcoal
BG = "#1A1612"
PANEL = "#2A2218"
PANEL_ALT = "#3A3028"
LINE = "#6B5A3D"  # warm amber border
TEXT = "#F5E6D0"
TEXT_DIM = "#8B7355"
TEXT_BRIGHT = "#FFF5E1"
ACCENT = "#E8733A"
WARN = "#E8C547"
USER_TEXT = "#E8733A"
KAI_TEXT = "#FFF5E1"
SYSTEM_TEXT = "#D4943A"
WINDOW_REFRESH_MS = 4000
WINDOW_CONTEXT_TTL_SEC = 20.0


class KaiPanelUnified:
    def __init__(
        self,
        assistant: KaiAssistant,
        model_label: str,
        open_companion_callback=None,
        close_companion_callback=None,
        restart_companion_callback=None,
        companion_status_callback=None,
        on_close_callback=None,
    ) -> None:
        self.assistant = assistant
        self.model_label = model_label
        self.open_companion_callback = open_companion_callback
        self.close_companion_callback = close_companion_callback
        self.restart_companion_callback = restart_companion_callback
        self.companion_status_callback = companion_status_callback
        self.on_close_callback = on_close_callback
        self.root = tk.Tk()
        self.result_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.drag_origin: tuple[int, int] | None = None
        self.always_on_top = tk.BooleanVar(value=True)
        self.opacity = tk.DoubleVar(value=0.93)
        self.status_text = tk.StringVar(value="ONLINE")
        self.kali_status = tk.StringVar(value="OFFLINE")
        self.window_link_status = tk.StringVar(value="UNLINKED")
        self.action_preview_text = tk.StringVar(value="No operator action yet.")
        self.proactive_hint_text = tk.StringVar(value="Hints will appear here.")
        self.recovery_text = tk.StringVar(value="Recovery plan will appear here when needed.")
        self.task_queue_text = tk.StringVar(value=self.assistant.memory.summarize_tasks())
        self.cached_window_context = ""
        self.cached_window_context_at = 0.0
        self.window_link_enabled = False
        self.window_link_generation = 0
        self.companion_status_text = tk.StringVar(value="UNKNOWN")
        self.chat_inflight = False
        self.capture_inflight = False
        self.kali_inflight = False
        self.kali_history: list[str] = []
        self.kali_history_index: int | None = None
        self.companion_inflight = False
        self._build_window()
        self._update_controls()
        self._refresh_companion_status()
        self._update_global_status()
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close_request)
        self.root.after(120, self._poll_queue)
        self.root.after(WINDOW_REFRESH_MS, self._auto_refresh_window_link)
        self.root.after(1500, self._poll_companion_status)

    def _build_window(self) -> None:
        self.root.title("Kai Command Center")
        self.root.geometry("1240x820+30+30")
        self.root.minsize(1080, 700)
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", self.opacity.get())
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("KaiDeck.TNotebook", background=PANEL, borderwidth=0)
        style.configure("KaiDeck.TNotebook.Tab", background=PANEL_ALT, foreground=TEXT, padding=(14, 8), borderwidth=0)
        style.map("KaiDeck.TNotebook.Tab", background=[("selected", LINE)], foreground=[("selected", TEXT_BRIGHT)])

        frame = tk.Frame(self.root, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        titlebar = tk.Frame(frame, bg=PANEL_ALT, cursor="fleur")
        titlebar.pack(fill="x", padx=12, pady=(12, 8))
        titlebar.bind("<ButtonPress-1>", self._start_drag)
        titlebar.bind("<B1-Motion>", self._drag_window)

        tk.Label(
            titlebar,
            text="KAI COMMAND DECK",
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            font=("Segoe UI Semibold", 17, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 0))
        tk.Label(
            titlebar,
            text=f"MODEL: {self.model_label}  |  CHAT, EXECUTION, STATE",
            fg=TEXT_DIM,
            bg=PANEL_ALT,
            font=("Cascadia Code", 9, "bold"),
        ).pack(anchor="w", padx=12, pady=(0, 10))

        top_row = tk.Frame(frame, bg=PANEL)
        top_row.pack(fill="x", padx=12, pady=(0, 8))
        self._build_status_card(top_row, "LINK", self.status_text).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._build_status_card(top_row, "KALI", self.kali_status).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._build_status_card(top_row, "WINDOW", self.window_link_status).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._build_status_card(top_row, "COMPANION", self.companion_status_text).pack(side="left", fill="x", expand=True)

        deck = tk.PanedWindow(frame, orient="horizontal", bg=PANEL, sashwidth=6, sashrelief="flat", bd=0, showhandle=False)
        deck.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        main_lane = tk.Frame(deck, bg=PANEL)
        rail_lane = tk.Frame(deck, bg=PANEL)
        deck.add(main_lane, stretch="always")
        deck.add(rail_lane, minsize=340)

        controls = tk.Frame(rail_lane, bg=PANEL)
        controls.pack(fill="x", padx=0, pady=(0, 10))

        tk.Checkbutton(
            controls,
            text="Always On Top",
            variable=self.always_on_top,
            command=self._toggle_topmost,
            selectcolor=PANEL_ALT,
            activebackground=PANEL,
            activeforeground=TEXT_BRIGHT,
            fg=TEXT,
            bg=PANEL,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        tk.Button(
            controls,
            text="Dock Left",
            command=lambda: self._dock("left"),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            relief="flat",
            padx=10,
            pady=6,
        ).pack(side="left", padx=(10, 6))

        tk.Button(
            controls,
            text="Dock Right",
            command=lambda: self._dock("right"),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            relief="flat",
            padx=10,
            pady=6,
        ).pack(side="left", padx=(0, 6))

        self.link_window_button = tk.Button(
            controls,
            text="Link Window",
            command=self._toggle_window_link,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            relief="flat",
            padx=10,
            pady=6,
        )
        self.link_window_button.pack(side="left")

        self.open_companion_button = tk.Button(
            controls,
            text="Open Companion",
            command=self._open_companion,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            relief="flat",
            padx=10,
            pady=6,
        )
        self.open_companion_button.pack(side="left", padx=(10, 6))

        self.restart_companion_button = tk.Button(
            controls,
            text="Restart Companion",
            command=self._restart_companion,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            relief="flat",
            padx=10,
            pady=6,
        )
        self.restart_companion_button.pack(side="left", padx=(0, 6))

        self.close_companion_button = tk.Button(
            controls,
            text="Close Companion",
            command=self._close_companion,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            relief="flat",
            padx=10,
            pady=6,
        )
        self.close_companion_button.pack(side="left", padx=(0, 6))

        self._build_action_strip(rail_lane)

        self._build_chat_lane(main_lane)
        notebook = ttk.Notebook(rail_lane, style="KaiDeck.TNotebook")
        notebook.pack(fill="both", expand=True)

        mission_tab = tk.Frame(notebook, bg=PANEL)
        kali_tab = tk.Frame(notebook, bg=PANEL)
        tools_tab = tk.Frame(notebook, bg=PANEL)
        notebook.add(mission_tab, text="Mission")
        notebook.add(kali_tab, text="Kali")
        notebook.add(tools_tab, text="Tools")
        self._build_mission_tab(mission_tab)
        self._build_kali_tab(kali_tab)
        self._build_tools_tab(tools_tab)

    def _build_action_strip(self, parent: tk.Frame) -> None:
        strip = tk.Frame(parent, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        strip.pack(fill="x", pady=(0, 10))
        tk.Label(strip, text="COMMAND STRIP", fg=ACCENT, bg=PANEL_ALT, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(8, 4))
        row = tk.Frame(strip, bg=PANEL_ALT)
        row.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(row, text="Dock Left", command=lambda: self._dock("left"), fg=TEXT_BRIGHT, bg=PANEL_ALT, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=6).pack(side="left", padx=(0, 6))
        tk.Button(row, text="Dock Right", command=lambda: self._dock("right"), fg=TEXT_BRIGHT, bg=PANEL_ALT, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=6).pack(side="left", padx=(0, 6))
        tk.Button(row, text="Link Window", command=self._toggle_window_link, fg=TEXT_BRIGHT, bg=PANEL_ALT, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=6).pack(side="left")
        op_row = tk.Frame(strip, bg=PANEL_ALT)
        op_row.pack(fill="x", padx=10, pady=(0, 10))
        tk.Label(op_row, text="Opacity", fg=TEXT_DIM, bg=PANEL_ALT, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Scale(
            op_row,
            from_=0.55,
            to=1.0,
            resolution=0.01,
            orient="horizontal",
            variable=self.opacity,
            command=self._set_opacity,
            bg=PANEL_ALT,
            fg=TEXT_BRIGHT,
            highlightthickness=0,
            length=220,
        ).pack(fill="x")

        tk.Label(
            strip,
            text="Direct actions, file drops, and live control all stay in the same lane.",
            fg=TEXT_DIM,
            bg=PANEL_ALT,
            font=("Segoe UI", 8),
            wraplength=260,
            justify="left",
        ).pack(anchor="w", padx=10, pady=(0, 10))

    def _build_chat_lane(self, parent: tk.Frame) -> None:
        chat_card = tk.Frame(parent, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        chat_card.pack(fill="both", expand=True)
        header = tk.Frame(chat_card, bg=PANEL_ALT)
        header.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(header, text="CHAT", fg=ACCENT, bg=PANEL_ALT, font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(header, text="Primary conversation surface", fg=TEXT_DIM, bg=PANEL_ALT, font=("Segoe UI", 8)).pack(side="right")

        self.messages = scrolledtext.ScrolledText(
            chat_card,
            wrap="word",
            bg="#1E1A15",
            fg=TEXT,
            insertbackground=TEXT_BRIGHT,
            relief="flat",
            borderwidth=0,
            font=("Cascadia Code", 11),
            padx=14,
            pady=14,
        )
        self.messages.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.messages.tag_configure("kai", foreground=KAI_TEXT, spacing1=8, spacing3=10)
        self.messages.tag_configure("user", foreground=USER_TEXT, spacing1=8, spacing3=10)
        self.messages.tag_configure("system", foreground=SYSTEM_TEXT, spacing1=8, spacing3=10)
        self.messages.insert("end", "KAI> Command center online. Give me a mission.\n\n", "kai")
        self.messages.configure(state="disabled")

        input_row = tk.Frame(chat_card, bg=PANEL_ALT)
        input_row.pack(fill="x", padx=12, pady=(0, 12))

        self.input = tk.Text(
            input_row,
            height=3,
            bg="#1E1A15",
            fg=TEXT_BRIGHT,
            insertbackground=TEXT_BRIGHT,
            relief="flat",
            font=("Cascadia Code", 10),
        )
        self.input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.input.bind("<Return>", self._handle_enter_submit)

        self.send_button = tk.Button(
            input_row,
            text="Send",
            command=self._submit_prompt,
            fg="#1A1612",
            bg=ACCENT,
            activebackground="#E8733A",
            activeforeground="#1A1612",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=6,
        )
        self.send_button.pack(side="left", padx=(0, 6))

        tk.Button(
            input_row,
            text="Clear",
            command=self._clear_messages,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=6,
        ).pack(side="left")

    def _build_mission_tab(self, parent: tk.Frame) -> None:
        self._build_info_card(parent, "Last Action", self.action_preview_text, SYSTEM_TEXT).pack(fill="x", padx=10, pady=(10, 6))
        self._build_info_card(parent, "Kai Hint", self.proactive_hint_text, TEXT_BRIGHT).pack(fill="x", padx=10, pady=6)
        self._build_info_card(parent, "Recovery", self.recovery_text, TEXT_BRIGHT).pack(fill="x", padx=10, pady=6)

        task_card = self._build_section_card(parent, "Task Queue", "Active queue and quick controls.")
        task_card.pack(fill="both", expand=True, padx=10, pady=6)
        tk.Label(
            task_card,
            textvariable=self.task_queue_text,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            justify="left",
            anchor="w",
            wraplength=340,
            font=("Cascadia Code", 9),
        ).pack(fill="x", padx=12, pady=(0, 8))

        row = tk.Frame(task_card, bg=PANEL_ALT)
        row.pack(fill="x", padx=12, pady=(0, 10))
        self.task_input = tk.Entry(row, bg="#1E1A15", fg=TEXT_BRIGHT, insertbackground=TEXT_BRIGHT, relief="flat", font=("Cascadia Code", 10))
        self.task_input.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=6)
        self.task_input.bind("<Return>", self._handle_task_add_enter)
        tk.Button(row, text="Add Task", command=self._submit_task_add, fg="#1A1612", bg=ACCENT, activebackground="#C4622B", activeforeground="#1A1612", relief="flat", padx=10, pady=6).pack(side="left", padx=(0, 6))
        tk.Button(row, text="Done Active", command=self._complete_active_task, fg=TEXT_BRIGHT, bg=PANEL, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=6).pack(side="left", padx=(0, 6))
        tk.Button(row, text="Refresh", command=lambda: self._submit_prompt("show tasks"), fg=TEXT_BRIGHT, bg=PANEL, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=6).pack(side="left")

        auto_row = tk.Frame(task_card, bg=PANEL_ALT)
        auto_row.pack(fill="x", padx=12, pady=(0, 10))
        tk.Button(auto_row, text="Autonomy On", command=lambda: self._submit_prompt("autonomy on"), fg=TEXT_BRIGHT, bg=PANEL, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=6).pack(side="left", padx=(0, 6))
        tk.Button(auto_row, text="Autonomy Step", command=lambda: self._submit_prompt("autonomy tick"), fg=TEXT_BRIGHT, bg=PANEL, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=6).pack(side="left", padx=(0, 6))
        tk.Button(auto_row, text="Autonomy Status", command=lambda: self._submit_prompt("autonomy status"), fg=TEXT_BRIGHT, bg=PANEL, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=6).pack(side="left")

    def _build_kali_tab(self, parent: tk.Frame) -> None:
        actions = self._build_section_card(parent, "Kali Session", "Persistent shell and command feed.")
        actions.pack(fill="x", padx=10, pady=(10, 6))
        btn_row = tk.Frame(actions, bg=PANEL_ALT)
        btn_row.pack(fill="x", padx=12, pady=(0, 8))
        self.kali_connect_button = tk.Button(btn_row, text="Connect", command=self._connect_kali_session, fg=TEXT_BRIGHT, bg=PANEL_ALT, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=6)
        self.kali_connect_button.pack(side="left", padx=(0, 6))
        self.kali_reset_button = tk.Button(btn_row, text="Reset", command=self._reset_kali_session, fg=TEXT_BRIGHT, bg=PANEL_ALT, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=6)
        self.kali_reset_button.pack(side="left", padx=(0, 6))
        tk.Button(btn_row, text="PWD", command=lambda: self._submit_kali_command("pwd"), fg=TEXT_BRIGHT, bg=PANEL_ALT, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=6).pack(side="left", padx=(0, 6))
        tk.Button(btn_row, text="Clear Feed", command=self._clear_kali_feed, fg=TEXT_BRIGHT, bg=PANEL_ALT, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=6).pack(side="left")

        self.kali_feed = scrolledtext.ScrolledText(
            actions,
            wrap="word",
            height=20,
            bg="#141010",
            fg=SYSTEM_TEXT,
            insertbackground=TEXT_BRIGHT,
            relief="flat",
            borderwidth=0,
            font=("Cascadia Code", 9),
            padx=12,
            pady=10,
        )
        self.kali_feed.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.kali_feed.insert("end", "# Kali session offline. Press Connect.\n")
        self.kali_feed.configure(state="disabled")

        shell_bar = tk.Frame(actions, bg=PANEL_ALT)
        shell_bar.pack(fill="x", padx=12, pady=(0, 10))
        self.kali_input = tk.Entry(shell_bar, bg="#1E1A15", fg=TEXT_BRIGHT, insertbackground=TEXT_BRIGHT, relief="flat", font=("Cascadia Code", 10))
        self.kali_input.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=6)
        self.kali_input.bind("<Return>", self._handle_kali_enter)
        self.kali_input.bind("<Up>", self._handle_kali_history_up)
        self.kali_input.bind("<Down>", self._handle_kali_history_down)
        self.kali_run_button = tk.Button(shell_bar, text="Run", command=self._submit_kali_command, fg="#1A1612", bg=WARN, activebackground="#F0D878", activeforeground="#1A1612", relief="flat", padx=12, pady=6)
        self.kali_run_button.pack(side="left")

    def _build_tools_tab(self, parent: tk.Frame) -> None:
        btns = [
            ("Capture Screen OCR", lambda: self._submit_prompt("read my screen")),
            ("Show Playbooks", lambda: self._submit_prompt("show playbooks")),
            ("Show Security Stack", lambda: self._submit_prompt("show security stack")),
            ("Show AI Security Stack", lambda: self._submit_prompt("show ai security stack")),
            ("Show Cyber Toolkit", lambda: self._submit_prompt("show cyber tools")),
            ("Open Logs Folder", self._open_logs),
        ]
        grid = self._build_section_card(parent, "Quick Tools", "One-click actions and references.")
        grid.pack(fill="x", padx=10, pady=(10, 6))
        btn_grid = tk.Frame(grid, bg=PANEL_ALT)
        btn_grid.pack(fill="x", padx=12, pady=(0, 10))
        for i, (label, handler) in enumerate(btns):
            tk.Button(btn_grid, text=label, command=handler, fg=TEXT_BRIGHT, bg=PANEL_ALT, activebackground=LINE, activeforeground=TEXT_BRIGHT, relief="flat", padx=10, pady=8).grid(
                row=i // 2, column=i % 2, sticky="ew", padx=6, pady=6
            )
        btn_grid.columnconfigure(0, weight=1)
        btn_grid.columnconfigure(1, weight=1)

        tk.Label(
            grid,
            text="Everything you need is in this panel: chat, tasks/autonomy, Kali terminal, and research tools.",
            fg=TEXT_DIM,
            bg=PANEL_ALT,
            font=("Segoe UI", 10),
            justify="left",
            wraplength=760,
        ).pack(fill="x", padx=12, pady=(0, 10))

    def _build_section_card(self, parent: tk.Frame, title: str, subtitle: str) -> tk.Frame:
        card = tk.Frame(parent, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        header = tk.Frame(card, bg=PANEL_ALT)
        header.pack(fill="x", padx=12, pady=(10, 6))
        tk.Label(header, text=title, fg=ACCENT, bg=PANEL_ALT, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        tk.Label(header, text=subtitle, fg=TEXT_DIM, bg=PANEL_ALT, font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 0))
        return card

    def _build_status_card(self, parent: tk.Frame, title: str, var: tk.StringVar) -> tk.Frame:
        card = tk.Frame(parent, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        tk.Label(card, text=title, fg=TEXT_DIM, bg=PANEL_ALT, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=8, pady=(6, 0))
        tk.Label(card, textvariable=var, fg=TEXT_BRIGHT, bg=PANEL_ALT, font=("Cascadia Code", 10, "bold")).pack(anchor="w", padx=8, pady=(0, 6))
        return card

    def _build_info_card(self, parent: tk.Frame, title: str, text_var: tk.StringVar, body_color: str) -> tk.Frame:
        card = tk.Frame(parent, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        tk.Label(card, text=title, fg=TEXT_DIM, bg=PANEL_ALT, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        tk.Label(card, textvariable=text_var, fg=body_color, bg=PANEL_ALT, justify="left", anchor="w", wraplength=760, font=("Cascadia Code", 9)).pack(
            fill="x", padx=12, pady=(0, 10)
        )
        return card

    def _open_logs(self) -> None:
        logs = self.assistant.workspace / "logs"
        try:
            logs.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["explorer.exe", str(logs)])
            self._append_message("KAI>", "Opened logs folder.", "system")
        except Exception as exc:
            self._append_message("WARN>", f"Could not open logs: {exc}", "system")

    def _toggle_topmost(self) -> None:
        self.root.attributes("-topmost", self.always_on_top.get())

    def _set_opacity(self, _value: str) -> None:
        self.root.attributes("-alpha", self.opacity.get())

    def _dock(self, side: str) -> None:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height()
        y = max(0, (screen_h - win_h) // 2)
        x = 0 if side == "left" else max(0, screen_w - win_w)
        self.root.geometry(f"+{x}+{y}")

    def _handle_close_request(self) -> None:
        if self.on_close_callback is not None:
            try:
                self.on_close_callback()
            except Exception as exc:
                self._append_message("WARN>", f"Close handler error: {exc}", "system")
        self.root.destroy()

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_origin = (event.x_root, event.y_root)

    def _drag_window(self, event: tk.Event) -> None:
        if not self.drag_origin:
            return
        dx = event.x_root - self.drag_origin[0]
        dy = event.y_root - self.drag_origin[1]
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        self.root.geometry(f"+{x}+{y}")
        self.drag_origin = (event.x_root, event.y_root)

    def _clear_messages(self) -> None:
        self.messages.configure(state="normal")
        self.messages.delete("1.0", "end")
        self.messages.insert("end", "KAI> Chat cleared.\n\n", "system")
        self.messages.configure(state="disabled")

    def _append_message(self, prefix: str, text: str, tag: str) -> None:
        self.messages.configure(state="normal")
        self.messages.insert("end", f"{prefix} {text}\n\n", tag)
        self.messages.configure(state="disabled")
        self.messages.see("end")

    def _clear_kali_feed(self) -> None:
        self.kali_feed.configure(state="normal")
        self.kali_feed.delete("1.0", "end")
        self.kali_feed.insert("end", "# Kali feed cleared.\n")
        self.kali_feed.configure(state="disabled")

    def _append_kali_feed(self, text: str) -> None:
        self.kali_feed.configure(state="normal")
        self.kali_feed.insert("end", text.rstrip() + "\n")
        self.kali_feed.configure(state="disabled")
        self.kali_feed.see("end")

    def _enqueue_event(self, kind: str, **payload: object) -> None:
        self.result_queue.put((kind, json.dumps(payload)))

    def _next_request_id(self, prefix: str) -> str:
        return f"{prefix}-{time.time_ns()}"

    def _set_chat_inflight(self, busy: bool) -> None:
        self.chat_inflight = busy
        self._update_controls()
        self._update_global_status()

    def _set_capture_inflight(self, busy: bool) -> None:
        self.capture_inflight = busy
        self._update_controls()
        self._update_global_status()

    def _set_kali_inflight(self, busy: bool) -> None:
        self.kali_inflight = busy
        self._update_controls()
        self._update_global_status()

    def _set_companion_inflight(self, busy: bool) -> None:
        self.companion_inflight = busy
        self._update_controls()
        self._update_global_status()

    def _update_controls(self) -> None:
        if hasattr(self, "send_button"):
            self.send_button.configure(state="disabled" if self.chat_inflight else "normal")
        if hasattr(self, "link_window_button"):
            self.link_window_button.configure(state="disabled" if self.capture_inflight else "normal")
        if hasattr(self, "open_companion_button"):
            has_companion_controls = any(
                callback is not None
                for callback in (
                    self.open_companion_callback,
                    self.close_companion_callback,
                    self.restart_companion_callback,
                )
            )
            state = "disabled" if (self.companion_inflight or not has_companion_controls) else "normal"
            self.open_companion_button.configure(state=state)
            self.restart_companion_button.configure(state=state)
            self.close_companion_button.configure(state=state)
        if hasattr(self, "kali_connect_button"):
            state = "disabled" if self.kali_inflight else "normal"
            self.kali_connect_button.configure(state=state)
            self.kali_reset_button.configure(state=state)
            self.kali_run_button.configure(state=state)

    def _update_global_status(self) -> None:
        if self.kali_status.get() == "ERROR" or self.window_link_status.get() == "ERROR":
            self.status_text.set("ERROR")
            return
        if self.window_link_status.get() == "DEGRADED":
            self.status_text.set("DEGRADED")
            return
        if self.chat_inflight or self.capture_inflight or self.kali_inflight or self.companion_inflight:
            self.status_text.set("RUNNING")
            return
        self.status_text.set("IDLE")

    def _refresh_companion_status(self) -> None:
        if self.companion_status_callback is None:
            self.companion_status_text.set("PANEL-ONLY")
            return
        try:
            status = str(self.companion_status_callback()).strip().upper()
        except Exception as exc:
            status = f"ERROR: {exc}"
        self.companion_status_text.set(status if status else "UNKNOWN")

    def _poll_companion_status(self) -> None:
        self._refresh_companion_status()
        self._update_global_status()
        self.root.after(1500, self._poll_companion_status)

    def _run_companion_action(self, action_name: str, callback) -> None:
        try:
            message = callback()
            self._enqueue_event("companion_action", action=action_name, message=message)
        except Exception as exc:
            self._enqueue_event("companion_action_error", action=action_name, error=str(exc))

    def _start_companion_action(self, action_name: str, callback) -> None:
        if callback is None or self.companion_inflight:
            return
        self._set_companion_inflight(True)
        threading.Thread(target=self._run_companion_action, args=(action_name, callback), daemon=True).start()

    def _open_companion(self) -> None:
        self._start_companion_action("open", self.open_companion_callback)

    def _close_companion(self) -> None:
        self._start_companion_action("close", self.close_companion_callback)

    def _restart_companion(self) -> None:
        self._start_companion_action("restart", self.restart_companion_callback)

    def _toggle_window_link(self) -> None:
        if self.window_link_enabled:
            self.window_link_generation += 1
            self.window_link_enabled = False
            self.cached_window_context = ""
            self.cached_window_context_at = 0.0
            self.window_link_status.set("UNLINKED")
            self._update_global_status()
            self._append_message("KAI>", "Window link disabled.", "system")
            return
        self.window_link_generation += 1
        self._start_capture(linking=True, generation=self.window_link_generation)

    def _start_capture(self, linking: bool = False, background: bool = False, generation: int | None = None) -> None:
        if self.capture_inflight:
            return
        self._set_capture_inflight(True)
        if not background:
            self.window_link_status.set("CAPTURING")
        request_id = self._next_request_id("capture")
        capture_generation = self.window_link_generation if generation is None else generation
        threading.Thread(target=self._run_capture, args=(request_id, background, linking, capture_generation), daemon=True).start()

    def _run_capture(self, request_id: str, background: bool = False, linking: bool = False, generation: int = 0) -> None:
        started_at = time.perf_counter()
        try:
            text = self.assistant.tools.capture_active_window_ocr()
            self._enqueue_event(
                "capture_bg" if background else "capture",
                request_id=request_id,
                text=text,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
                linking=linking,
                generation=generation,
            )
        except Exception as exc:
            self._enqueue_event(
                "capture_error_bg" if background else "capture_error",
                request_id=request_id,
                error=str(exc),
                duration_ms=int((time.perf_counter() - started_at) * 1000),
                linking=linking,
                generation=generation,
            )

    def _auto_refresh_window_link(self) -> None:
        if self.window_link_enabled and not self.capture_inflight:
            self._start_capture(background=True, generation=self.window_link_generation)
        self.root.after(WINDOW_REFRESH_MS, self._auto_refresh_window_link)

    def _current_window_context(self) -> str:
        if not self.window_link_enabled:
            return ""
        if not self.cached_window_context:
            return ""
        if (time.time() - self.cached_window_context_at) > WINDOW_CONTEXT_TTL_SEC:
            return ""
        return self.cached_window_context

    def _connect_kali_session(self) -> None:
        if self.kali_inflight:
            self._append_kali_feed("# kali request already running")
            return
        self._set_kali_inflight(True)
        self.kali_status.set("RUNNING")
        threading.Thread(target=self._run_kali_session_start, daemon=True).start()

    def _run_kali_session_start(self) -> None:
        request_id = self._next_request_id("kali-connect")
        started_at = time.perf_counter()
        try:
            payload = self.assistant.tools.start_kali_session()
            self._enqueue_event("kali_session", request_id=request_id, payload=payload, duration_ms=int((time.perf_counter() - started_at) * 1000))
        except Exception as exc:
            self._enqueue_event("kali_session_error", request_id=request_id, error=str(exc), duration_ms=int((time.perf_counter() - started_at) * 1000))

    def _reset_kali_session(self) -> None:
        if self.kali_inflight:
            self._append_kali_feed("# kali request already running")
            return
        self._set_kali_inflight(True)
        self.kali_status.set("RUNNING")
        threading.Thread(target=self._run_kali_reset, daemon=True).start()

    def _run_kali_reset(self) -> None:
        request_id = self._next_request_id("kali-reset")
        started_at = time.perf_counter()
        try:
            stop_payload = self.assistant.tools.stop_kali_session()
            start_payload = self.assistant.tools.start_kali_session()
            self._enqueue_event(
                "kali_reset",
                request_id=request_id,
                payload={"stop": json.loads(stop_payload), "start": json.loads(start_payload)},
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        except Exception as exc:
            self._enqueue_event("kali_session_error", request_id=request_id, error=str(exc), duration_ms=int((time.perf_counter() - started_at) * 1000))

    def _handle_kali_enter(self, _event: tk.Event) -> str:
        self._submit_kali_command()
        return "break"

    def _handle_kali_history_up(self, _event: tk.Event) -> str:
        if not self.kali_history:
            return "break"
        if self.kali_history_index is None:
            self.kali_history_index = len(self.kali_history) - 1
        else:
            self.kali_history_index = max(0, self.kali_history_index - 1)
        self.kali_input.delete(0, "end")
        self.kali_input.insert(0, self.kali_history[self.kali_history_index])
        return "break"

    def _handle_kali_history_down(self, _event: tk.Event) -> str:
        if not self.kali_history:
            return "break"
        if self.kali_history_index is None:
            return "break"
        if self.kali_history_index >= len(self.kali_history) - 1:
            self.kali_history_index = None
            self.kali_input.delete(0, "end")
            return "break"
        self.kali_history_index += 1
        self.kali_input.delete(0, "end")
        self.kali_input.insert(0, self.kali_history[self.kali_history_index])
        return "break"

    def _submit_kali_command(self, command: str | None = None) -> None:
        kali_command = (command or self.kali_input.get()).strip()
        if not kali_command:
            return
        if self.kali_inflight:
            self._append_kali_feed("# kali request already running")
            return
        if not self.kali_history or self.kali_history[-1] != kali_command:
            self.kali_history.append(kali_command)
        self.kali_history_index = None
        if command is None:
            self.kali_input.delete(0, "end")
        self._set_kali_inflight(True)
        self.kali_status.set("RUNNING")
        threading.Thread(target=self._run_kali_command, args=(kali_command,), daemon=True).start()

    def _run_kali_command(self, command: str) -> None:
        request_id = self._next_request_id("kali-command")
        started_at = time.perf_counter()
        try:
            self.assistant.tools.start_kali_session()
            payload = self.assistant.tools.run_kali_session_command(command)
            self._enqueue_event(
                "kali_command",
                request_id=request_id,
                payload=payload,
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
        except Exception as exc:
            self._enqueue_event("kali_session_error", request_id=request_id, error=str(exc), duration_ms=int((time.perf_counter() - started_at) * 1000))

    def _handle_task_add_enter(self, _event: tk.Event) -> str:
        self._submit_task_add()
        return "break"

    def _submit_task_add(self) -> None:
        task_text = self.task_input.get().strip()
        if not task_text:
            return
        self.task_input.delete(0, "end")
        self._submit_prompt(f"add task: {task_text}")

    def _complete_active_task(self) -> None:
        active = self.assistant.memory.get_active_task()
        if not active:
            self.proactive_hint_text.set("No active task yet.")
            return
        self._submit_prompt(f"complete task: {active.get('title', '')}")

    def _refresh_task_queue(self) -> None:
        self.task_queue_text.set(self.assistant.memory.summarize_tasks())

    def _handle_enter_submit(self, event: tk.Event) -> str | None:
        if event.state & 0x1:
            return None
        self._submit_prompt()
        return "break"

    def _submit_prompt(self, prompt: str | None = None) -> None:
        message = prompt or self.input.get("1.0", "end").strip()
        if not message:
            return
        if self.chat_inflight:
            self._append_message("WARN>", "A Kai request is already running. Wait for it to finish before sending another.", "system")
            return
        if prompt is None:
            self.input.delete("1.0", "end")
        self._append_message("YOU>", message, "user")
        self._set_chat_inflight(True)
        threading.Thread(target=self._run_ask, args=(self._next_request_id("chat"), message), daemon=True).start()

    def _run_ask(self, request_id: str, message: str) -> None:
        started_at = time.perf_counter()
        try:
            prompt = message
            if self.window_link_enabled:
                screen_text = self._current_window_context()
                if not screen_text and not self.capture_inflight:
                    self._enqueue_event("request_capture_bg", generation=self.window_link_generation)
                if screen_text:
                    prompt = f"{message}\n\nLive active-window OCR context:\n{screen_text[:10000]}"
            reply = asyncio.run(self.assistant.ask(prompt))
            self._enqueue_event("reply", request_id=request_id, reply=reply, duration_ms=int((time.perf_counter() - started_at) * 1000))
        except Exception as exc:
            self._enqueue_event("error", request_id=request_id, error=str(exc), duration_ms=int((time.perf_counter() - started_at) * 1000))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.result_queue.get_nowait()
                data = self._parse_json_payload(payload)
                if data.get("_parse_error"):
                    self._append_message("WARN>", f"Panel payload parse failed for {kind}: {data.get('_parse_error')}", "system")
                    if kind.startswith("kali_"):
                        self.kali_status.set("ERROR")
                    self._update_global_status()
                    continue
                if kind == "reply":
                    self._set_chat_inflight(False)
                    if self.assistant.last_action_preview:
                        self.action_preview_text.set(self.assistant.last_action_preview)
                    if self.assistant.last_proactive_hint:
                        self.proactive_hint_text.set(self.assistant.last_proactive_hint)
                    if self.assistant.last_recovery_plan:
                        self.recovery_text.set(self.assistant.last_recovery_plan)
                    self._refresh_task_queue()
                    if self.assistant.last_action_preview:
                        self._append_message("PLAN>", self.assistant.last_action_preview, "system")
                    if self.assistant.last_proactive_hint:
                        self._append_message("NEXT>", self.assistant.last_proactive_hint, "system")
                    self._append_message("KAI>", data.get("reply", ""), "kai")
                elif kind == "request_capture_bg":
                    if self.window_link_enabled and not self.capture_inflight and int(data.get("generation", -1)) == self.window_link_generation:
                        self._start_capture(background=True, generation=self.window_link_generation)
                elif kind == "kali_session":
                    self._set_kali_inflight(False)
                    data = self._parse_json_payload(str(data.get("payload", "")))
                    if data.get("_parse_error"):
                        self.kali_status.set("ERROR")
                        self._append_kali_feed(f"# kali session parse error: {data.get('_parse_error')}")
                        self._update_global_status()
                        continue
                    self.kali_status.set("READY" if data.get("ok") else "ERROR")
                    self._append_kali_feed(f"# kali session: {'ready' if data.get('ok') else 'error'}")
                elif kind == "kali_command":
                    self._set_kali_inflight(False)
                    data = self._parse_json_payload(str(data.get("payload", "")))
                    if data.get("_parse_error"):
                        self.kali_status.set("ERROR")
                        self._append_kali_feed(f"# kali command parse error: {data.get('_parse_error')}")
                        self._update_global_status()
                        continue
                    self.kali_status.set("READY" if data.get("ok") else "ERROR")
                    self._append_kali_feed(f"$ {data.get('command', '')}")
                    if data.get("stdout"):
                        self._append_kali_feed(data["stdout"])
                    if data.get("stderr"):
                        self._append_kali_feed(data["stderr"])
                    self._append_kali_feed(f"[exit {data.get('returncode', '')}] cwd={data.get('cwd', '')}")
                elif kind == "kali_reset":
                    self._set_kali_inflight(False)
                    reset_payload = data.get("payload", {})
                    stop_payload = reset_payload.get("stop", {}) if isinstance(reset_payload, dict) else {}
                    start_payload = reset_payload.get("start", {}) if isinstance(reset_payload, dict) else {}
                    start_ok = bool(start_payload.get("ok"))
                    self.kali_status.set("READY" if start_ok else "ERROR")
                    stop_msg = stop_payload.get("message") or stop_payload.get("error") or "stop result unavailable"
                    start_msg = start_payload.get("message") or start_payload.get("error") or "start result unavailable"
                    self._append_kali_feed(f"# kali stop: {'ok' if stop_payload.get('ok') else 'error'} - {stop_msg}")
                    self._append_kali_feed(f"# kali start: {'ok' if start_ok else 'error'} - {start_msg}")
                    if start_payload.get("cwd"):
                        self._append_kali_feed(f"# kali cwd: {start_payload.get('cwd')}")
                elif kind == "kali_session_error":
                    self._set_kali_inflight(False)
                    self.kali_status.set("ERROR")
                    self._append_kali_feed(f"# kali error: {data.get('error', payload)}")
                elif kind == "capture":
                    self._set_capture_inflight(False)
                    if int(data.get("generation", -1)) != self.window_link_generation:
                        self._update_global_status()
                        continue
                    self.cached_window_context = str(data.get("text", ""))
                    self.cached_window_context_at = time.time()
                    self.window_link_status.set("READY")
                    self.window_link_enabled = True
                    self._append_message("KAI>", "Window context linked.", "system")
                elif kind == "capture_bg":
                    self._set_capture_inflight(False)
                    if int(data.get("generation", -1)) != self.window_link_generation or not self.window_link_enabled:
                        self._update_global_status()
                        continue
                    self.cached_window_context = str(data.get("text", ""))
                    self.cached_window_context_at = time.time()
                    self.window_link_status.set("LIVE")
                    self.window_link_enabled = True
                elif kind == "capture_error":
                    self._set_capture_inflight(False)
                    if int(data.get("generation", -1)) != self.window_link_generation:
                        self._update_global_status()
                        continue
                    self.window_link_status.set("ERROR")
                    self.window_link_enabled = False
                    self.cached_window_context = ""
                    self.cached_window_context_at = 0.0
                    self._append_message("WARN>", str(data.get("error", payload)), "system")
                elif kind == "capture_error_bg":
                    self._set_capture_inflight(False)
                    if int(data.get("generation", -1)) != self.window_link_generation:
                        self._update_global_status()
                        continue
                    self.window_link_status.set("DEGRADED")
                    self.cached_window_context = ""
                    self.cached_window_context_at = 0.0
                    self._append_message("WARN>", f"Window link refresh failed: {data.get('error', payload)}", "system")
                elif kind == "error":
                    self._set_chat_inflight(False)
                    self._append_message("WARN>", str(data.get("error", payload)), "system")
                elif kind == "companion_action":
                    self._set_companion_inflight(False)
                    self._refresh_companion_status()
                    self._append_message("KAI>", str(data.get("message", "Companion action completed.")), "system")
                elif kind == "companion_action_error":
                    self._set_companion_inflight(False)
                    self._refresh_companion_status()
                    self._append_message("WARN>", f"Companion {data.get('action', 'action')} failed: {data.get('error', payload)}", "system")
                else:
                    self._append_message("WARN>", payload, "system")
                self._update_global_status()
        except queue.Empty:
            pass
        finally:
            self.root.after(120, self._poll_queue)

    def _parse_json_payload(self, payload: str) -> dict:
        try:
            return json.loads(payload)
        except Exception as exc:
            return {"_parse_error": str(exc), "raw": payload}

    def run(self) -> None:
        self.root.bind("<F10>", lambda _event: self._dock("left"))
        self.root.bind("<F11>", lambda _event: self._dock("right"))
        self.input.focus_set()
        self.root.mainloop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kai unified desktop panel")
    parser.add_argument("--model", default=os.environ.get("KAI_MODEL", "qwen3:4b-q4_K_M"))
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assistant = KaiAssistant(model=args.model, workspace=Path(args.workspace))
    KaiPanelUnified(assistant=assistant, model_label=args.model).run()


if __name__ == "__main__":
    main()
