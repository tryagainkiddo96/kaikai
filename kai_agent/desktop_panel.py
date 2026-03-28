import argparse
import asyncio
import json
import os
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import scrolledtext

from kai_agent.assistant import KaiAssistant

# Shiba Inu warm palette
BG = "#1A1612"
PANEL = "#2A2218"
PANEL_ALT = "#3A3028"
LINE = "#6B5A3D"
TEXT = "#F5E6D0"
TEXT_DIM = "#8B7355"
TEXT_BRIGHT = "#FFF5E1"
ACCENT = "#E8733A"
WARN = "#E8C547"
USER_TEXT = "#E8733A"
KAI_TEXT = "#FFF5E1"
SYSTEM_TEXT = "#D4943A"
WINDOW_REFRESH_MS = 4000


class KaiPanel:
    def __init__(self, assistant: KaiAssistant, model_label: str) -> None:
        self.assistant = assistant
        self.model_label = model_label
        self.root = tk.Tk()
        self.result_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.drag_origin: tuple[int, int] | None = None
        self.always_on_top = tk.BooleanVar(value=True)
        self.opacity = tk.DoubleVar(value=0.92)
        self.status_text = tk.StringVar(value="ONLINE")
        self.kali_status = tk.StringVar(value="OFFLINE")
        self.window_link_status = tk.StringVar(value="UNLINKED")
        self.action_preview_text = tk.StringVar(value="No operator action yet.")
        self.proactive_hint_text = tk.StringVar(value="Kai hints will show up here when something useful comes to mind.")
        self.recovery_text = tk.StringVar(value="Recovery mode will appear here when something fails.")
        self.task_queue_text = tk.StringVar(value=self.assistant.memory.summarize_tasks())
        self.command_safety_text = tk.StringVar(value="No command classified yet.")
        self.playbooks_text = tk.StringVar(value="triage_garak_results | set_up_pyrit | summarize_art_findings")
        self.cached_window_context = ""
        self.kali_history: list[str] = []
        self.kali_history_index: int | None = None
        self.kali_completion_index = -1
        self.kali_completion_items: list[str] = []
        self.window_link_enabled = False
        self.capture_inflight = False
        self._build_window()
        self.root.after(120, self._poll_queue)
        self.root.after(WINDOW_REFRESH_MS, self._auto_refresh_window_link)

    def _build_window(self) -> None:
        self.root.title("Kai Nexus")
        self.root.geometry("460x820+40+40")
        self.root.minsize(380, 640)
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", self.opacity.get())

        frame = tk.Frame(self.root, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        titlebar = tk.Frame(frame, bg=PANEL_ALT, height=56, cursor="fleur")
        titlebar.pack(fill="x", padx=12, pady=(12, 8))
        titlebar.bind("<ButtonPress-1>", self._start_drag)
        titlebar.bind("<B1-Motion>", self._drag_window)

        title = tk.Label(
            titlebar,
            text="🦊 KAI",
            fg=ACCENT,
            bg=PANEL_ALT,
            font=("Segoe UI Semibold", 20, "bold"),
        )
        title.pack(anchor="w", padx=12, pady=(10, 0))
        title.bind("<ButtonPress-1>", self._start_drag)
        title.bind("<B1-Motion>", self._drag_window)

        subtitle = tk.Label(
            titlebar,
            text="companion chat · local assistant",
            fg=TEXT_DIM,
            bg=PANEL_ALT,
            font=("Inter", 9),
        )
        subtitle.pack(anchor="w", padx=12, pady=(0, 10))
        subtitle.bind("<ButtonPress-1>", self._start_drag)
        subtitle.bind("<B1-Motion>", self._drag_window)

        status_row = tk.Frame(frame, bg=PANEL)
        status_row.pack(fill="x", padx=12, pady=(0, 10))

        self._build_status_card(status_row, "LINK", self.status_text).pack(side="left", expand=True, fill="x", padx=(0, 8))
        self._build_status_card(status_row, "KALI", self.kali_status).pack(side="left", expand=True, fill="x", padx=(0, 8))
        self._build_status_card(status_row, "WINDOW", self.window_link_status).pack(side="left", expand=True, fill="x")

        toggles = tk.Frame(frame, bg=PANEL)
        toggles.pack(fill="x", padx=12, pady=(0, 8))

        top_check = tk.Checkbutton(
            toggles,
            text="Always On Top",
            variable=self.always_on_top,
            command=self._toggle_topmost,
            selectcolor=PANEL_ALT,
            activebackground=PANEL,
            activeforeground=TEXT_BRIGHT,
            fg=TEXT,
            bg=PANEL,
            font=("Segoe UI", 10, "bold"),
        )
        top_check.pack(side="left")

        self.link_button = tk.Button(
            toggles,
            text="LINK WINDOW",
            command=self._toggle_window_link,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=6,
            highlightbackground=LINE,
        )
        self.link_button.pack(side="left", padx=(10, 0))

        dock_left = tk.Button(
            toggles,
            text="DOCK LEFT",
            command=lambda: self._dock("left"),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=6,
            highlightbackground=LINE,
        )
        dock_left.pack(side="left", padx=(10, 6))

        dock_right = tk.Button(
            toggles,
            text="DOCK RIGHT",
            command=lambda: self._dock("right"),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=6,
            highlightbackground=LINE,
        )
        dock_right.pack(side="left")

        clear_btn = tk.Button(
            toggles,
            text="CLEAR",
            command=self._clear_messages,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=10,
            pady=6,
            highlightbackground=LINE,
        )
        clear_btn.pack(side="right")

        opacity_row = tk.Frame(frame, bg=PANEL)
        opacity_row.pack(fill="x", padx=12, pady=(0, 10))

        tk.Label(
            opacity_row,
            text="AURA OPACITY",
            fg=TEXT_DIM,
            bg=PANEL,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        opacity_scale = tk.Scale(
            opacity_row,
            from_=0.55,
            to=1.0,
            resolution=0.01,
            orient="horizontal",
            variable=self.opacity,
            command=self._set_opacity,
            bg=PANEL,
            fg=TEXT_BRIGHT,
            troughcolor="#141010",
            activebackground=ACCENT,
            highlightthickness=0,
            length=180,
        )
        opacity_scale.pack(side="right")

        self.messages = scrolledtext.ScrolledText(
            frame,
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
        self.messages.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.messages.tag_configure("kai", foreground=KAI_TEXT, spacing1=8, spacing3=10)
        self.messages.tag_configure("user", foreground=USER_TEXT, spacing1=8, spacing3=10)
        self.messages.tag_configure("system", foreground=SYSTEM_TEXT, spacing1=8, spacing3=10)
        self.messages.insert("end", "KAI> Link stable. Drop a question, an error, or a mission and I’ll help you work through it.\n\n", "kai")
        self.messages.configure(state="disabled")

        terminal_frame = tk.Frame(frame, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        terminal_frame.pack(fill="x", padx=12, pady=(0, 10))

        terminal_header = tk.Frame(terminal_frame, bg=PANEL_ALT)
        terminal_header.pack(fill="x", padx=12, pady=(10, 4))

        tk.Label(terminal_header, text="KALI FEED", fg=WARN, bg=PANEL_ALT, font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Button(
            terminal_header,
            text="CONNECT KALI",
            command=self._connect_kali_session,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=4,
            highlightbackground=LINE,
        ).pack(side="right", padx=(0, 8))
        tk.Button(
            terminal_header,
            text="CLEAR FEED",
            command=self._clear_kali_feed,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=4,
            highlightbackground=LINE,
        ).pack(side="right")

        self.kali_feed = scrolledtext.ScrolledText(
            terminal_frame,
            wrap="word",
            height=10,
            bg="#141010",
            fg=SYSTEM_TEXT,
            insertbackground=TEXT_BRIGHT,
            relief="flat",
            borderwidth=0,
            font=("Cascadia Code", 9),
            padx=12,
            pady=10,
        )
        self.kali_feed.pack(fill="x", padx=12, pady=(0, 10))
        self.kali_feed.tag_configure("prompt", foreground=ACCENT)
        self.kali_feed.tag_configure("output", foreground=SYSTEM_TEXT)
        self.kali_feed.tag_configure("meta", foreground=TEXT_DIM)
        self.kali_feed.insert("end", "# Kali session is offline. Press CONNECT KALI to start.\n", "meta")
        self.kali_feed.configure(state="disabled")

        tk.Label(
            terminal_frame,
            text="KALI COMMAND LINE (NOT CHAT)",
            fg=TEXT_DIM,
            bg=PANEL_ALT,
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 6))

        shell_bar = tk.Frame(terminal_frame, bg=PANEL_ALT)
        shell_bar.pack(fill="x", padx=12, pady=(0, 10))

        self.kali_input = tk.Entry(
            shell_bar,
            bg="#1E1A15",
            fg=TEXT_BRIGHT,
            insertbackground=TEXT_BRIGHT,
            relief="flat",
            font=("Cascadia Code", 10),
        )
        self.kali_input.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=6)
        self.kali_input.bind("<Return>", self._handle_kali_enter)
        self.kali_input.bind("<Up>", self._handle_kali_history_up)
        self.kali_input.bind("<Down>", self._handle_kali_history_down)
        self.kali_input.bind("<Tab>", self._handle_kali_tab_complete)

        tk.Button(
            shell_bar,
            text="RUN",
            command=self._submit_kali_command,
            fg="#1A1612",
            bg=WARN,
            activebackground="#F0D878",
            activeforeground="#1A1612",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=6,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            shell_bar,
            text="PWD",
            command=lambda: self._submit_kali_command("pwd"),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=6,
            highlightbackground=LINE,
        ).pack(side="left", padx=(0, 6))

        tk.Button(
            shell_bar,
            text="RESET",
            command=self._reset_kali_session,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=6,
            highlightbackground=LINE,
        ).pack(side="left")

        self.kali_completion_label = tk.Label(
            terminal_frame,
            text="",
            fg=TEXT_DIM,
            bg=PANEL_ALT,
            justify="left",
            anchor="w",
            font=("Cascadia Code", 8),
        )
        self.kali_completion_label.pack(fill="x", padx=12, pady=(0, 10))

        preview_frame = tk.Frame(frame, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        preview_frame.pack(fill="x", padx=12, pady=(0, 10))

        tk.Label(
            preview_frame,
            text="LAST ACTION",
            fg=TEXT_DIM,
            bg=PANEL_ALT,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 4))

        tk.Label(
            preview_frame,
            textvariable=self.action_preview_text,
            fg=SYSTEM_TEXT,
            bg=PANEL_ALT,
            justify="left",
            anchor="w",
            wraplength=400,
            font=("Cascadia Code", 9),
        ).pack(fill="x", padx=12, pady=(0, 10))

        tk.Label(
            preview_frame,
            textvariable=self.command_safety_text,
            fg=TEXT_DIM,
            bg=PANEL_ALT,
            justify="left",
            anchor="w",
            wraplength=400,
            font=("Cascadia Code", 8),
        ).pack(fill="x", padx=12, pady=(0, 10))

        hint_frame = tk.Frame(frame, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        hint_frame.pack(fill="x", padx=12, pady=(0, 10))

        tk.Label(
            hint_frame,
            text="KAI HINT",
            fg=WARN,
            bg=PANEL_ALT,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 4))

        tk.Label(
            hint_frame,
            textvariable=self.proactive_hint_text,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            justify="left",
            anchor="w",
            wraplength=400,
            font=("Segoe UI", 9),
        ).pack(fill="x", padx=12, pady=(0, 10))

        recovery_frame = tk.Frame(frame, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        recovery_frame.pack(fill="x", padx=12, pady=(0, 10))

        tk.Label(
            recovery_frame,
            text="RECOVERY",
            fg=ACCENT,
            bg=PANEL_ALT,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 4))

        tk.Label(
            recovery_frame,
            textvariable=self.recovery_text,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            justify="left",
            anchor="w",
            wraplength=400,
            font=("Segoe UI", 9),
        ).pack(fill="x", padx=12, pady=(0, 10))

        task_frame = tk.Frame(frame, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        task_frame.pack(fill="x", padx=12, pady=(0, 10))

        task_header = tk.Frame(task_frame, bg=PANEL_ALT)
        task_header.pack(fill="x", padx=12, pady=(10, 4))

        tk.Label(
            task_header,
            text="TASK QUEUE",
            fg=ACCENT,
            bg=PANEL_ALT,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left")

        tk.Button(
            task_header,
            text="REFRESH",
            command=lambda: self._submit_prompt("show tasks"),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=4,
            highlightbackground=LINE,
        ).pack(side="right")

        tk.Label(
            task_frame,
            textvariable=self.task_queue_text,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            justify="left",
            anchor="w",
            wraplength=400,
            font=("Cascadia Code", 9),
        ).pack(fill="x", padx=12, pady=(0, 10))

        task_bar = tk.Frame(task_frame, bg=PANEL_ALT)
        task_bar.pack(fill="x", padx=12, pady=(0, 10))

        self.task_input = tk.Entry(
            task_bar,
            bg="#1E1A15",
            fg=TEXT_BRIGHT,
            insertbackground=TEXT_BRIGHT,
            relief="flat",
            font=("Cascadia Code", 10),
        )
        self.task_input.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=6)
        self.task_input.bind("<Return>", self._handle_task_add_enter)

        tk.Button(
            task_bar,
            text="ADD TASK",
            command=self._submit_task_add,
            fg="#1A1612",
            bg=ACCENT,
            activebackground="#E8733A",
            activeforeground="#1A1612",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=6,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            task_bar,
            text="DONE ACTIVE",
            command=self._complete_active_task,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=6,
            highlightbackground=LINE,
        ).pack(side="left")

        playbooks_frame = tk.Frame(frame, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        playbooks_frame.pack(fill="x", padx=12, pady=(0, 10))

        playbooks_header = tk.Frame(playbooks_frame, bg=PANEL_ALT)
        playbooks_header.pack(fill="x", padx=12, pady=(10, 4))

        tk.Label(
            playbooks_header,
            text="PLAYBOOKS",
            fg=WARN,
            bg=PANEL_ALT,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left")

        tk.Button(
            playbooks_header,
            text="SHOW",
            command=lambda: self._submit_prompt("show playbooks"),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=8,
            pady=4,
            highlightbackground=LINE,
        ).pack(side="right")

        tk.Label(
            playbooks_frame,
            textvariable=self.playbooks_text,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            justify="left",
            anchor="w",
            wraplength=400,
            font=("Cascadia Code", 8),
        ).pack(fill="x", padx=12, pady=(0, 8))

        playbooks_bar = tk.Frame(playbooks_frame, bg=PANEL_ALT)
        playbooks_bar.pack(fill="x", padx=12, pady=(0, 10))

        tk.Button(
            playbooks_bar,
            text="GARAK",
            command=lambda: self._seed_prompt("triage garak results: "),
            fg="#1A1612",
            bg=WARN,
            activebackground="#F0D878",
            activeforeground="#1A1612",
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=6,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            playbooks_bar,
            text="PYRIT",
            command=lambda: self._seed_prompt("setup pyrit: "),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=6,
            highlightbackground=LINE,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            playbooks_bar,
            text="ART",
            command=lambda: self._seed_prompt("summarize art findings: "),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=6,
            highlightbackground=LINE,
        ).pack(side="left")

        utility_row = tk.Frame(frame, bg=PANEL)
        utility_row.pack(fill="x", padx=12, pady=(0, 8))

        open_kali = tk.Button(
            utility_row,
            text="OPEN KALI",
            command=self._open_kali_terminal,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            highlightbackground=LINE,
        )
        open_kali.pack(side="left")

        open_kali_here = tk.Button(
            utility_row,
            text="KALI HERE",
            command=self._open_kali_here,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            highlightbackground=LINE,
        )
        open_kali_here.pack(side="left", padx=(10, 0))

        open_workspace = tk.Button(
            utility_row,
            text="OPEN WORKSPACE",
            command=self._open_workspace,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            highlightbackground=LINE,
        )
        open_workspace.pack(side="left", padx=(10, 0))

        open_logs = tk.Button(
            utility_row,
            text="OPEN LOGS",
            command=self._open_logs,
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            highlightbackground=LINE,
        )
        open_logs.pack(side="left", padx=(10, 0))

        utility_row_2 = tk.Frame(frame, bg=PANEL)
        utility_row_2.pack(fill="x", padx=12, pady=(0, 10))

        run_project = tk.Button(
            utility_row_2,
            text="RUN PROJECT",
            command=lambda: self._submit_prompt("run this project in ."),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            highlightbackground=LINE,
        )
        run_project.pack(side="left", padx=(10, 0))

        run_tests = tk.Button(
            utility_row_2,
            text="RUN TESTS",
            command=lambda: self._submit_prompt("run tests in ."),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            highlightbackground=LINE,
        )
        run_tests.pack(side="left", padx=(10, 0))

        kali_mode = tk.Button(
            utility_row_2,
            text="KALI CHAT",
            command=lambda: self._seed_prompt("kali: "),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            highlightbackground=LINE,
        )
        kali_mode.pack(side="left", padx=(10, 0))

        kali_shell = tk.Button(
            utility_row_2,
            text="KALI SHELL",
            command=lambda: self._seed_prompt("kali run: "),
            fg=TEXT_BRIGHT,
            bg=PANEL_ALT,
            activebackground="#3A3028",
            activeforeground=TEXT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            padx=12,
            pady=8,
            highlightbackground=LINE,
        )
        kali_shell.pack(side="left", padx=(10, 0))

        compose = tk.Frame(frame, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        compose.pack(fill="x", padx=12, pady=(0, 12), before=terminal_frame)

        label = tk.Label(
            compose,
            text="CHAT TO KAI",
            fg=TEXT_DIM,
            bg=PANEL_ALT,
            font=("Segoe UI", 9, "bold"),
        )
        label.pack(anchor="w", padx=12, pady=(10, 4))

        self.input = tk.Text(
            compose,
            height=4,
            wrap="word",
            bg="#1E1A15",
            fg=TEXT_BRIGHT,
            insertbackground=TEXT_BRIGHT,
            relief="flat",
            borderwidth=0,
            font=("Cascadia Code", 11),
            padx=12,
            pady=10,
        )
        self.input.pack(fill="x", padx=12, pady=(0, 10))
        self.input.bind("<Control-Return>", lambda event: self._submit_prompt())
        self.input.bind("<Return>", self._handle_enter_submit)

        send = tk.Button(
            compose,
            text="SEND",
            command=self._submit_prompt,
            fg="#1A1612",
            bg=ACCENT,
            activebackground="#E8733A",
            activeforeground="#1A1612",
            relief="flat",
            font=("Segoe UI", 11, "bold"),
            padx=12,
            pady=10,
        )
        send.pack(anchor="e", padx=12, pady=(0, 12))

    def _build_status_card(self, parent: tk.Widget, label: str, value: str | tk.StringVar) -> tk.Frame:
        card = tk.Frame(parent, bg=PANEL_ALT, highlightbackground=LINE, highlightthickness=1)
        tk.Label(card, text=label, fg=TEXT_DIM, bg=PANEL_ALT, font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        if isinstance(value, tk.StringVar):
            tk.Label(card, textvariable=value, fg=TEXT_BRIGHT, bg=PANEL_ALT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(0, 8))
        else:
            tk.Label(card, text=value, fg=TEXT_BRIGHT, bg=PANEL_ALT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(0, 8))
        return card

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag_window(self, event: tk.Event) -> None:
        if not self.drag_origin:
            return
        offset_x, offset_y = self.drag_origin
        self.root.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

    def _toggle_topmost(self) -> None:
        self.root.attributes("-topmost", self.always_on_top.get())

    def _set_opacity(self, _value: str) -> None:
        self.root.attributes("-alpha", self.opacity.get())

    def _dock(self, side: str) -> None:
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        y = max(20, (screen_height - height) // 2)

        if side == "left":
            x = 20
        else:
            x = max(20, screen_width - width - 20)

        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _open_kali_terminal(self) -> None:
        try:
            subprocess.Popen(["wsl.exe", "-d", "kali-linux"])
            self._append_message("KAI>", "Opened Kali terminal.", "system")
            self.action_preview_text.set("Action: open_kali\nStatus: ok")
            self._refresh_kali_status()
        except Exception as exc:
            self._append_message("WARN>", f"Could not open Kali terminal: {exc}", "system")
            self.action_preview_text.set(f"Action: open_kali\nStatus: needs attention\nError: {exc}")

    def _open_kali_here(self) -> None:
        try:
            wsl_path = str(self.assistant.workspace).replace("\\", "/")
            drive = wsl_path[0].lower()
            rest = wsl_path[2:].lstrip("/")
            target = f"/mnt/{drive}/{rest}"
            subprocess.Popen(["wsl.exe", "-d", "kali-linux", "--", "bash", "-lc", f"cd '{target}'; exec bash"])
            self._append_message("KAI>", "Opened Kali in the workspace.", "system")
            self.action_preview_text.set(f"Action: open_kali_here\nStatus: ok\nPath: {self.assistant.workspace}")
        except Exception as exc:
            self._append_message("WARN>", f"Could not open Kali in workspace: {exc}", "system")
            self.action_preview_text.set(f"Action: open_kali_here\nStatus: needs attention\nError: {exc}")

    def _open_workspace(self) -> None:
        try:
            subprocess.Popen(["explorer.exe", str(self.assistant.workspace)])
            self._append_message("KAI>", "Opened workspace folder.", "system")
            self.action_preview_text.set(f"Action: open_workspace\nStatus: ok\nPath: {self.assistant.workspace}")
        except Exception as exc:
            self._append_message("WARN>", f"Could not open workspace: {exc}", "system")
            self.action_preview_text.set(f"Action: open_workspace\nStatus: needs attention\nError: {exc}")

    def _open_logs(self) -> None:
        try:
            logs_path = self.assistant.workspace / "logs"
            logs_path.mkdir(parents=True, exist_ok=True)
            subprocess.Popen(["explorer.exe", str(logs_path)])
            self._append_message("KAI>", "Opened logs folder.", "system")
            self.action_preview_text.set(f"Action: open_logs\nStatus: ok\nPath: {logs_path}")
        except Exception as exc:
            self._append_message("WARN>", f"Could not open logs: {exc}", "system")
            self.action_preview_text.set(f"Action: open_logs\nStatus: needs attention\nError: {exc}")

    def _prime_kali_session(self) -> None:
        worker = threading.Thread(target=self._run_kali_session_start, daemon=True)
        worker.start()

    def _connect_kali_session(self) -> None:
        self.status_text.set("KALI")
        self._append_kali_feed("# connecting Kali session...", "meta")
        self._prime_kali_session()

    def _refresh_kali_status(self) -> None:
        worker = threading.Thread(target=self._run_kali_session_status, daemon=True)
        worker.start()

    def _run_kali_session_start(self) -> None:
        try:
            payload = self.assistant.tools.start_kali_session()
            self.result_queue.put(("kali_session", payload))
        except Exception as exc:
            self.result_queue.put(("kali_session_error", str(exc)))

    def _run_kali_session_status(self) -> None:
        try:
            payload = self.assistant.tools.get_kali_session_status()
            self.result_queue.put(("kali_status", payload))
        except Exception as exc:
            self.result_queue.put(("kali_session_error", str(exc)))

    def _toggle_window_link(self) -> None:
        if self.window_link_enabled:
            self.window_link_enabled = False
            self.capture_inflight = False
            self.cached_window_context = ""
            self.window_link_status.set("UNLINKED")
            self.link_button.configure(text="LINK WINDOW")
            self._append_message("KAI>", "Window link disabled.", "system")
            self.action_preview_text.set("Action: link_window\nStatus: idle")
            return

        self._start_capture(linking=True)

    def _start_capture(self, linking: bool = False, background: bool = False) -> None:
        if self.capture_inflight:
            return
        self.capture_inflight = True
        self.window_link_status.set("CAPTURING")
        if linking:
            self.link_button.configure(text="LINKING...")
        worker = threading.Thread(target=self._run_capture, args=(background,), daemon=True)
        worker.start()

    def _run_capture(self, background: bool = False) -> None:
        try:
            text = self.assistant.tools.capture_active_window_ocr()
            self.result_queue.put(("capture_bg" if background else "capture", text))
        except Exception as exc:
            self.result_queue.put(("capture_error_bg" if background else "capture_error", str(exc)))

    def _auto_refresh_window_link(self) -> None:
        if self.window_link_enabled and not self.capture_inflight:
            self._start_capture(background=True)
        self.root.after(WINDOW_REFRESH_MS, self._auto_refresh_window_link)

    def _clear_messages(self) -> None:
        self.messages.configure(state="normal")
        self.messages.delete("1.0", "end")
        self.messages.insert("end", "KAI> Chat buffer cleared. We’re still linked.\n\n", "system")
        self.messages.configure(state="disabled")

    def _append_message(self, prefix: str, text: str, tag: str) -> None:
        self.messages.configure(state="normal")
        self.messages.insert("end", f"{prefix} {text}\n\n", tag)
        self.messages.configure(state="disabled")
        self.messages.see("end")

    def _clear_kali_feed(self) -> None:
        self.kali_feed.configure(state="normal")
        self.kali_feed.delete("1.0", "end")
        self.kali_feed.insert("end", "# Kali feed cleared.\n", "meta")
        self.kali_feed.configure(state="disabled")

    def _append_kali_feed(self, text: str, tag: str = "output") -> None:
        self.kali_feed.configure(state="normal")
        self.kali_feed.insert("end", text.rstrip() + "\n", tag)
        self.kali_feed.configure(state="disabled")
        self.kali_feed.see("end")

    def _sync_kali_feed_from_tool_context(self) -> None:
        tool_context = self.assistant.last_tool_context or ""
        if not tool_context or ":\n{" not in tool_context:
            return
        _label, json_text = tool_context.split(":\n", 1)
        try:
            data = json.loads(json_text)
        except Exception:
            return

        action = data.get("action", "")
        if action == "kali_session_start":
            self._append_kali_feed(f"# session ready @ {data.get('cwd', '')}", "meta")
            return
        if action == "kali_session_stop":
            self._append_kali_feed("# session stopped", "meta")
            return
        if action != "kali_session_command":
            return

        self._append_kali_feed(f"$ {data.get('command', '')}", "prompt")
        stdout = data.get("stdout", "")
        stderr = data.get("stderr", "")
        if stdout:
            self._append_kali_feed(stdout, "output")
        if stderr:
            self._append_kali_feed(stderr, "output")
        self._append_kali_feed(f"[exit {data.get('returncode', '')}] cwd={data.get('cwd', '')}", "meta")

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
        self._show_kali_history_entry()
        return "break"

    def _handle_kali_history_down(self, _event: tk.Event) -> str:
        if not self.kali_history:
            return "break"
        if self.kali_history_index is None:
            self.kali_input.delete(0, "end")
            return "break"
        if self.kali_history_index >= len(self.kali_history) - 1:
            self.kali_history_index = None
            self.kali_input.delete(0, "end")
            return "break"
        self.kali_history_index += 1
        self._show_kali_history_entry()
        return "break"

    def _show_kali_history_entry(self) -> None:
        if self.kali_history_index is None or not self.kali_history:
            return
        self.kali_input.delete(0, "end")
        self.kali_input.insert(0, self.kali_history[self.kali_history_index])

    def _handle_kali_tab_complete(self, _event: tk.Event) -> str:
        current = self.kali_input.get()
        try:
            payload = json.loads(self.assistant.tools.complete_kali_input(current))
        except Exception as exc:
            self.kali_completion_label.configure(text=f"completion error: {exc}")
            return "break"

        suggestions = payload.get("suggestions", [])
        if not suggestions:
            self.kali_completion_items = []
            self.kali_completion_index = -1
            self.kali_completion_label.configure(text="no completion matches")
            return "break"

        if suggestions != self.kali_completion_items:
            self.kali_completion_items = suggestions
            self.kali_completion_index = 0
        else:
            self.kali_completion_index = (self.kali_completion_index + 1) % len(self.kali_completion_items)

        choice = self.kali_completion_items[self.kali_completion_index]
        self.kali_input.delete(0, "end")
        self.kali_input.insert(0, choice)
        preview = " | ".join(self.kali_completion_items[:5])
        if len(self.kali_completion_items) > 5:
            preview += " | ..."
        self.kali_completion_label.configure(text=preview)
        return "break"

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
            self.proactive_hint_text.set("Suggestion: there is no active task yet. Add one in the task bar.")
            return
        self._submit_prompt(f"complete task: {active.get('title', '')}")

    def _refresh_task_queue(self) -> None:
        self.task_queue_text.set(self.assistant.memory.summarize_tasks())

    def _submit_kali_command(self, command: str | None = None) -> None:
        kali_command = (command or self.kali_input.get()).strip()
        if not kali_command:
            return
        if not self.kali_history or self.kali_history[-1] != kali_command:
            self.kali_history.append(kali_command)
        self.kali_history_index = None
        if command is None:
            self.kali_input.delete(0, "end")
        self.kali_completion_items = []
        self.kali_completion_index = -1
        self.kali_completion_label.configure(text="")
        preview = self.assistant.tools.classify_command(kali_command, shell="bash")
        self.command_safety_text.set(
            f"Risk: {preview['confidence']} | Level: {preview['action_level']} | Tags: {', '.join(preview['tags'])}"
        )
        self.status_text.set("KALI")
        worker = threading.Thread(target=self._run_kali_command, args=(kali_command,), daemon=True)
        worker.start()

    def _run_kali_command(self, command: str) -> None:
        try:
            # Lazy-start Kali only when the user explicitly uses Kali controls.
            self.assistant.tools.start_kali_session()
            payload = self.assistant.tools.run_kali_session_command(command)
            self.result_queue.put(("kali_command", payload))
        except Exception as exc:
            self.result_queue.put(("kali_session_error", str(exc)))

    def _reset_kali_session(self) -> None:
        self.status_text.set("KALI")
        worker = threading.Thread(target=self._run_kali_reset, daemon=True)
        worker.start()

    def _run_kali_reset(self) -> None:
        try:
            stop_payload = self.assistant.tools.stop_kali_session()
            start_payload = self.assistant.tools.start_kali_session()
            self.result_queue.put(("kali_reset", json.dumps({"stop": json.loads(stop_payload), "start": json.loads(start_payload)})))
        except Exception as exc:
            self.result_queue.put(("kali_session_error", str(exc)))

    def _seed_prompt(self, text: str) -> None:
        self.input.delete("1.0", "end")
        self.input.insert("1.0", text)
        self.input.focus_set()

    def _handle_enter_submit(self, event: tk.Event) -> str | None:
        if event.state & 0x1:
            return None
        self._submit_prompt()
        return "break"

    def _submit_prompt(self, prompt: str | None = None) -> None:
        message = prompt or self.input.get("1.0", "end").strip()
        if not message:
            return
        if prompt is None:
            self.input.delete("1.0", "end")

        self._append_message("YOU>", message, "user")
        self.status_text.set("THINKING")
        worker = threading.Thread(target=self._run_ask, args=(message,), daemon=True)
        worker.start()

    def _run_ask(self, message: str) -> None:
        try:
            prompt = message
            if self.window_link_enabled:
                screen_text = self.cached_window_context or self.assistant.tools.capture_active_window_ocr()
                self.cached_window_context = screen_text
                prompt = (
                    f"{message}\n\n"
                    f"Live active-window OCR context:\n{screen_text[:10000]}"
                )
            reply = asyncio.run(self.assistant.ask(prompt))
            self.result_queue.put(("reply", reply))
        except Exception as exc:
            self.result_queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.result_queue.get_nowait()
                self.capture_inflight = False
                self.status_text.set("ONLINE")
                if kind == "reply":
                    if self.assistant.last_action_preview:
                        self.action_preview_text.set(self.assistant.last_action_preview)
                    if self.assistant.last_proactive_hint:
                        self.proactive_hint_text.set(self.assistant.last_proactive_hint)
                    if self.assistant.last_recovery_plan:
                        self.recovery_text.set(self.assistant.last_recovery_plan)
                    self._refresh_task_queue()
                    self._append_message("KAI>", payload, "kai")
                    self._sync_kali_feed_from_tool_context()
                    self._refresh_kali_status()
                elif kind == "kali_session":
                    data = self._parse_json_payload(payload)
                    if data.get("ok"):
                        self.kali_status.set("READY")
                        self._append_kali_feed(f"# session ready @ {data.get('cwd', '')}", "meta")
                        self.action_preview_text.set(
                            f"Action: {data.get('action', 'kali_session_start')}\nStatus: ok\nCwd: {data.get('cwd', '')}"
                        )
                    else:
                        self.kali_status.set("ERROR")
                        self.action_preview_text.set(
                            f"Action: {data.get('action', 'kali_session_start')}\nStatus: needs attention\nError: {data.get('error', 'unknown')}"
                        )
                elif kind == "kali_status":
                    data = self._parse_json_payload(payload)
                    if data.get("running"):
                        self.kali_status.set("READY")
                    else:
                        self.kali_status.set("OFFLINE")
                elif kind == "kali_command":
                    data = self._parse_json_payload(payload)
                    self.command_safety_text.set(
                        f"Risk: {data.get('confidence', 'unknown')} | Level: {data.get('action_level', '?')} | Tags: {', '.join(data.get('tags', []))}"
                    )
                    if data.get("ok"):
                        self.kali_status.set("READY")
                        if str(data.get("command", "")).strip().lower() == "pwd":
                            self.proactive_hint_text.set("Suggestion: try `ls`, `cd <folder>`, or press Tab for completions.")
                        self.recovery_text.set("Recovery idle: last Kali command completed successfully.")
                    else:
                        self.kali_status.set("ERROR")
                        self.proactive_hint_text.set("Suggestion: that Kali command failed. I can help research the error from chat or you can edit and retry here.")
                        self.recovery_text.set(
                            "Failure Point: command execution\n"
                            "Likely Cause: the command did not complete cleanly\n"
                            "Smallest Fix: review the stderr and retry the smallest safe next step\n"
                            f"Next Command: {data.get('command', '')}"
                        )
                    self._append_kali_feed(f"$ {data.get('command', '')}", "prompt")
                    if data.get("stdout"):
                        self._append_kali_feed(data["stdout"], "output")
                    if data.get("stderr"):
                        self._append_kali_feed(data["stderr"], "output")
                    self._append_kali_feed(f"[exit {data.get('returncode', '')}] cwd={data.get('cwd', '')}", "meta")
                    self.action_preview_text.set(
                        f"Action: {data.get('action', 'kali_session_command')}\n"
                        f"Status: {'ok' if data.get('ok') else 'needs attention'}\n"
                        f"Cwd: {data.get('cwd', '')}\n"
                        f"Command: {data.get('command', '')}"
                    )
                elif kind == "kali_reset":
                    data = self._parse_json_payload(payload)
                    start_data = data.get("start", {})
                    self.kali_status.set("READY" if start_data.get("ok") else "ERROR")
                    self._append_kali_feed("# session reset", "meta")
                    self.proactive_hint_text.set("Suggestion: the Kali session was reset cleanly. `pwd` is a good quick check.")
                    self.recovery_text.set("Recovery idle: Kali session reset cleanly.")
                    if start_data.get("cwd"):
                        self._append_kali_feed(f"# session ready @ {start_data.get('cwd', '')}", "meta")
                    self.action_preview_text.set(
                        f"Action: kali_session_reset\n"
                        f"Status: {'ok' if start_data.get('ok') else 'needs attention'}\n"
                        f"Cwd: {start_data.get('cwd', '')}"
                    )
                elif kind == "kali_session_error":
                    self.kali_status.set("ERROR")
                    self._append_kali_feed(f"# session error: {payload}", "meta")
                    self.proactive_hint_text.set("Suggestion: the Kali bridge hit an error. `RESET` should usually recover it.")
                    self.recovery_text.set(
                        "Failure Point: Kali bridge\n"
                        "Likely Cause: the session bridge threw an error\n"
                        "Smallest Fix: press RESET to restart the session and retry with a smaller validation command"
                    )
                elif kind == "capture":
                    self.cached_window_context = payload
                    self.window_link_status.set("READY")
                    self.window_link_enabled = True
                    self.link_button.configure(text="UNLINK WINDOW")
                    preview = payload[:700].strip() or "No readable text found."
                    self._append_message("KAI>", f"Captured active window context.\n\n{preview}", "system")
                    self.action_preview_text.set("Action: link_window\nStatus: ok\nWindow context captured.")
                elif kind == "capture_bg":
                    self.cached_window_context = payload
                    self.window_link_status.set("LIVE")
                    self.window_link_enabled = True
                    self.link_button.configure(text="UNLINK WINDOW")
                    self.action_preview_text.set("Action: link_window\nStatus: live\nBackground refresh active.")
                elif kind == "capture_error":
                    self.window_link_status.set("ERROR")
                    self.window_link_enabled = False
                    self.link_button.configure(text="LINK WINDOW")
                    self._append_message("WARN>", payload, "system")
                    self.action_preview_text.set(f"Action: link_window\nStatus: needs attention\nError: {payload}")
                elif kind == "capture_error_bg":
                    self.window_link_status.set("ERROR")
                    self.link_button.configure(text="UNLINK WINDOW")
                    self.action_preview_text.set(f"Action: link_window\nStatus: needs attention\nError: {payload}")
                else:
                    self._append_message("WARN>", payload, "system")
        except queue.Empty:
            pass
        finally:
            self.root.after(120, self._poll_queue)

    def run(self) -> None:
        self.root.bind("<F10>", lambda _event: self._dock("left"))
        self.root.bind("<F11>", lambda _event: self._dock("right"))
        self.input.focus_set()
        self.root.mainloop()

    def _parse_json_payload(self, payload: str) -> dict:
        try:
            return json.loads(payload)
        except Exception:
            return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kai floating desktop panel")
    parser.add_argument("--model", default=os.environ.get("KAI_MODEL", "qwen3:4b-q4_K_M"))
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1]))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assistant = KaiAssistant(model=args.model, workspace=Path(args.workspace))
    KaiPanel(assistant=assistant, model_label=args.model).run()


if __name__ == "__main__":
    main()
