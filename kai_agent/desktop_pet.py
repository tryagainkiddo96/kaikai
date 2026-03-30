"""
Kai Desktop Pet
A lightweight, always-on-top Shiba Inu that lives on your desktop.
Click him, talk to him, watch him patrol. He's always there.

No heavy dependencies — just tkinter (built into Python).
"""

import json
import math
import os
import random
import sys
import time
import tkinter as tk
from pathlib import Path
from typing import Optional, Callable


# ---------------------------------------------------------------------------
# Sprites — generated procedurally (no image files needed)
# ---------------------------------------------------------------------------

def draw_shiba_sitting(size: int = 64) -> list:
    """Draw a pixel-art Shiba sitting facing forward."""
    template = [
        "     XXXX     ",
        "    XXXXXX    ",
        "   XX.XX.XX   ",
        "   X.FFFF.X   ",
        "   .FFFFFF.   ",
        "   .FCCCCF.   ",
        "   .FCnnCF.   ",
        "    .FCCF.    ",
        "     .FF.     ",
        "    .FFFF.    ",
        "   .FFFFFF.   ",
        "   .FFFFFF.   ",
        "    .FFFF.    ",
        "     ....     ",
    ]
    colors = {
        'X': '#1A1612',  # charcoal ears
        'F': '#C4783A',  # rust body
        'C': '#F5E6D0',  # cream muzzle/chest
        'n': '#1A1612',  # nose
        '.': None,
    }
    return template, colors


def draw_shiba_walking(size: int = 64) -> list:
    """Draw a pixel-art Shiba walking, legs in motion."""
    template = [
        "     XXXX     ",
        "    XXXXXX    ",
        "   XX.XX.XX   ",
        "   X.FFFF.X   ",
        "   .FFFFFF.   ",
        "   .FCCCCF.   ",
        "   .FCnnCF.   ",
        "    .FCCF.    ",
        "     .FF.     ",
        "    .FFFF.    ",
        "   .FFFFFF.   ",
        "  .F.    .F.  ",
        "  F.      .F  ",
        "  ..      ..  ",
    ]
    colors = {
        'X': '#1A1612',
        'F': '#C4783A',
        'C': '#F5E6D0',
        'n': '#1A1612',
        '.': None,
    }
    return template, colors


def draw_shiba_sleeping(size: int = 64) -> list:
    """Draw a pixel-art Shiba curled up sleeping."""
    template = [
        "              ",
        "     XXXX     ",
        "    X....X    ",
        "   XX.FFFF.X  ",
        "   .FFFFFF.   ",
        "   .FCCCCF.   ",
        "    .FCCF.    ",
        "   FFFFFFFF   ",
        "   FFFFFFFF   ",
        "   FFFFFFFF   ",
        "    FFFFFF    ",
        "     Zzz      ",
        "              ",
    ]
    colors = {
        'X': '#1A1612',
        'F': '#C4783A',
        'C': '#F5E6D0',
        'Z': '#D4943A',
        'z': '#D4943A',
        '.': None,
    }
    return template, colors


def draw_shiba_barking(size: int = 64) -> list:
    """Draw a pixel-art Shiba barking."""
    template = [
        "     XXXX     ",
        "    XXXXXX    ",
        "   XX.XX.XX   ",
        "   X.FFFF.X   ",
        "   .FFFFFF.   ",
        "   .FCCCCF.   ",
        "   .FCnnCF.   ",
        "    .FCCF.    ",
        "     .FF.!    ",
        "    .FFFF.    ",
        "   .FFFFFF.   ",
        "   .FFFFFF.   ",
        "    .FFFF.    ",
        "     ....     ",
    ]
    colors = {
        'X': '#1A1612',
        'F': '#C4783A',
        'C': '#F5E6D0',
        'n': '#1A1612',
        '!': '#D4943A',  # bark effect
        '.': None,
    }
    return template, colors


def sprite_to_image(template: list, colors: dict, pixel_size: int = 4) -> tk.PhotoImage:
    """Convert a sprite template to a tkinter PhotoImage."""
    h = len(template)
    w = max(len(row) for row in template)
    img = tk.PhotoImage(width=w * pixel_size, height=h * pixel_size)
    
    for y, row in enumerate(template):
        for x, ch in enumerate(row):
            color = colors.get(ch)
            if color:
                for dy in range(pixel_size):
                    for dx in range(pixel_size):
                        img.put(color, (x * pixel_size + dx, y * pixel_size + dy))
    
    return img


# ---------------------------------------------------------------------------
# Speech Bubble
# ---------------------------------------------------------------------------

class SpeechBubble:
    """A floating speech bubble above Kai."""
    
    def __init__(self, parent: tk.Toplevel, text: str, duration: float = 4.0):
        self.window = tk.Toplevel(parent)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.95)
        
        # Dark background matching Kai's palette
        frame = tk.Frame(self.window, bg="#2A2218", padx=10, pady=6)
        frame.pack()
        
        label = tk.Label(
            frame, text=text, bg="#2A2218", fg="#F5E6D0",
            font=("Inter", 10), wraplength=250, justify="left"
        )
        label.pack()
        
        # Auto-close
        self.window.after(int(duration * 1000), self.close)
    
    def position(self, x: int, y: int):
        self.window.geometry(f"+{x}+{y}")
    
    def close(self):
        try:
            self.window.destroy()
        except:
            pass


# ---------------------------------------------------------------------------
# Kai Desktop Pet
# ---------------------------------------------------------------------------

class KaiPet:
    """
    Kai the Shiba Inu — lives on your desktop.
    Patrols, sleeps, reacts, barks, talks to you.
    """
    
    # States
    IDLE = "idle"
    WALKING = "walking"
    SLEEPING = "sleeping"
    BARKING = "barking"
    SNIFFING = "sniffing"
    WAGGING = "wagging"
    
    # Idle phrases
    IDLE_LINES = [
        "Watching the room like it's my yard.",
        "Busy little Shiba patrol underway.",
        "Independent face. Loyal intentions.",
        "Keeping an eye on things.",
        "Tail status: cautiously optimistic.",
        "I see everything. I just pretend I don't.",
        "The fence at the park had a new scratch today.",
        "Yuki would've loved this spot.",
        "Saiya's probably guarding the house right now.",
    ]
    
    GREETING_LINES = [
        "Hey.",
        "There you are.",
        "*wags once*",
        "You're back.",
        "I was starting to wonder.",
    ]
    
    BARK_LINES = [
        "BARK!",
        "Woof!",
        "*alert bark*",
        "Hey! Something's happening!",
    ]
    
    SLEEP_LINES = [
        "Zzz...",
        "*dreams about the dog park*",
        "*twitches ear*",
        "*soft snoring*",
    ]
    
    def __init__(self, callback: Optional[Callable] = None):
        self.callback = callback
        self.state = self.IDLE
        self.state_timer = 0.0
        self.direction = 1  # 1 = right, -1 = left
        self.bubble: Optional[SpeechBubble] = None
        self.patrol_target_x = 0
        self.speed = 1.5
        
        # Mood (connected to backend if available)
        self.mood = "neutral"
        self.mood_emoji = "🦊"
        
        # Create the window
        self.root = tk.Tk()
        self.root.title("Kai")
        self.root.overrideredirect(True)  # No title bar
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        self.root.configure(bg="")  # Transparent bg attempt
        self.root.wm_attributes("-transparentcolor", "")
        
        # Canvas for drawing Kai
        self.canvas = tk.Canvas(
            self.root, width=80, height=80,
            bg="#2A2218", highlightthickness=0
        )
        self.canvas.pack()
        
        # Load sprites
        self.sprites = {
            self.IDLE: self._create_sprite(draw_shiba_sitting()),
            self.WALKING: self._create_sprite(draw_shiba_walking()),
            self.SLEEPING: self._create_sprite(draw_shiba_sleeping()),
            self.BARKING: self._create_sprite(draw_shiba_barking()),
        }
        
        self.current_sprite = self.canvas.create_image(40, 40, image=self.sprites[self.IDLE])
        
        # Mood indicator (small text below)
        self.mood_label = tk.Label(
            self.root, text="🦊", bg="#2A2218", fg="#F5E6D0",
            font=("Arial", 8), padx=4
        )
        self.mood_label.pack()
        
        # Interactions
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<Enter>", self._on_hover)
        self.canvas.bind("<Leave>", self._on_leave)
        
        self._drag_start = (0, 0)
        self._window_start = (0, 0)
        
        # Position — bottom right of screen
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"+{screen_w - 120}+{screen_h - 160}")
        
        # Start the game loop
        self.root.after(50, self._update)
        self.root.after(15000, self._ambient_action)  # Random actions
        self.root.after(30000, self._check_mood)  # Mood check
    
    def _create_sprite(self, template_colors: tuple) -> tk.PhotoImage:
        template, colors = template_colors
        return sprite_to_image(template, colors, pixel_size=5)
    
    # -- Game Loop --
    
    def _update(self):
        """Main update loop — runs every 50ms."""
        self.state_timer += 0.05
        
        if self.state == self.WALKING:
            self._update_walking()
        elif self.state == self.IDLE:
            # Return to patrol after a while
            if self.state_timer > random.uniform(5, 15):
                self._start_patrol()
        elif self.state == self.SLEEPING:
            if self.state_timer > random.uniform(20, 60):
                self._set_state(self.IDLE)
        
        self.root.after(50, self._update)
    
    def _update_walking(self):
        """Move Kai during patrol."""
        x = self.root.winfo_x()
        target = self.patrol_target_x
        
        if abs(x - target) < 5:
            # Arrived — idle for a bit
            self._set_state(self.IDLE)
            return
        
        # Move toward target
        dx = self.speed * self.direction
        new_x = x + int(dx)
        self.root.geometry(f"+{new_x}+{self.root.winfo_y()}")
        
        # Keep on screen
        screen_w = self.root.winfo_screenwidth()
        if new_x < 10 or new_x > screen_w - 100:
            self.direction *= -1
            self.patrol_target_x = screen_w // 2
    
    def _start_patrol(self):
        """Start walking to a random position."""
        screen_w = self.root.winfo_screenwidth()
        self.patrol_target_x = random.randint(50, screen_w - 120)
        
        current_x = self.root.winfo_x()
        self.direction = 1 if self.patrol_target_x > current_x else -1
        
        self._set_state(self.WALKING)
        
        # Flip sprite if going left
        if self.direction == -1:
            self.canvas.itemconfig(self.current_sprite, image=self.sprites[self.WALKING])
    
    def _set_state(self, new_state: str):
        """Change Kai's state and sprite."""
        self.state = new_state
        self.state_timer = 0.0
        
        sprite = self.sprites.get(new_state, self.sprites[self.IDLE])
        self.canvas.itemconfig(self.current_sprite, image=sprite)
    
    # -- Interactions --
    
    def _on_click(self, event):
        """Left click — Kai reacts."""
        self._drag_start = (event.x_root, event.y_root)
        self._window_start = (self.root.winfo_x(), self.root.winfo_y())
        
        # React to click
        reactions = [
            self._do_wag,
            self._do_bark,
            self._say_idle,
            self._do_sniff,
        ]
        random.choice(reactions)()
    
    def _on_right_click(self, event):
        """Right click — show quick menu."""
        menu = tk.Menu(self.root, tearoff=0, bg="#2A2218", fg="#F5E6D0")
        menu.add_command(label="🐾 Pet", command=self._do_wag)
        menu.add_command(label="📢 Bark", command=self._do_bark)
        menu.add_command(label="💤 Sleep", command=lambda: self._set_state(self.SLEEPING))
        menu.add_command(label="🚶 Patrol", command=self._start_patrol)
        menu.add_command(label="💭 Talk", command=self._say_idle)
        menu.add_separator()
        menu.add_command(label="💬 Open Chat", command=self._open_chat)
        menu.add_separator()
        menu.add_command(label="✕ Close", command=self.root.quit)
        menu.tk_popup(event.x_root, event.y_root)
    
    def _on_drag(self, event):
        """Drag Kai around."""
        dx = event.x_root - self._drag_start[0]
        dy = event.y_root - self._drag_start[1]
        new_x = self._window_start[0] + dx
        new_y = self._window_start[1] + dy
        self.root.geometry(f"+{new_x}+{new_y}")
    
    def _on_hover(self, event):
        """Mouse enters — Kai looks at you."""
        if self.state == self.IDLE:
            self.mood_label.config(text=f"{self.mood_emoji} *looks at you*")
    
    def _on_leave(self, event):
        """Mouse leaves."""
        self.mood_label.config(text=self.mood_emoji)
    
    # -- Actions --
    
    def _do_wag(self):
        """Kai wags his tail."""
        self.mood_label.config(text="😊 *wags*")
        self._show_speech("*happy tail wagging*")
        self.root.after(2000, lambda: self.mood_label.config(text=self.mood_emoji))
    
    def _do_bark(self):
        """Kai barks."""
        self._set_state(self.BARKING)
        line = random.choice(self.BARK_LINES)
        self._show_speech(line)
        self.root.after(1500, lambda: self._set_state(self.IDLE))
    
    def _do_sniff(self):
        """Kai sniffs the air."""
        self._set_state(self.SNIFFING)
        self._show_speech("*sniffs intensely*")
        self.root.after(2000, lambda: self._set_state(self.IDLE))
    
    def _say_idle(self):
        """Kai says something."""
        line = random.choice(self.IDLE_LINES)
        self._show_speech(line)
    
    def _ambient_action(self):
        """Random ambient actions."""
        if self.state in (self.IDLE, self.WALKING):
            action = random.choice(["patrol", "idle", "sleep", "bark", "say"])
            if action == "patrol":
                self._start_patrol()
            elif action == "sleep":
                self._set_state(self.SLEEPING)
                self._show_speech(random.choice(self.SLEEP_LINES))
            elif action == "bark" and random.random() < 0.2:
                self._do_bark()
            elif action == "say" and random.random() < 0.3:
                self._say_idle()
        
        # Schedule next ambient action
        self.root.after(random.randint(15000, 45000), self._ambient_action)
    
    # -- Speech --
    
    def _show_speech(self, text: str, duration: float = 4.0):
        """Show a speech bubble above Kai."""
        if self.bubble:
            self.bubble.close()
        
        self.bubble = SpeechBubble(self.root, text, duration)
        x = self.root.winfo_x() + 20
        y = self.root.winfo_y() - 50
        self.bubble.position(x, y)
    
    # -- External --
    
    def _check_mood(self):
        """Try to fetch mood from backend."""
        try:
            import urllib.request
            resp = urllib.request.urlopen("http://127.0.0.1:8127/api/mood", timeout=2)
            data = json.loads(resp.read())
            mood_info = data.get("mood", {})
            if isinstance(mood_info, dict):
                self.mood = mood_info.get("label", "neutral")
                self.mood_emoji = mood_info.get("emoji", "🦊")
            elif isinstance(mood_info, (list, tuple)) and len(mood_info) >= 2:
                self.mood = mood_info[0]
                self.mood_emoji = mood_info[1]
            self.mood_label.config(text=self.mood_emoji)
        except:
            pass
        
        self.root.after(30000, self._check_mood)
    
    def _open_chat(self):
        """Open the web chat widget."""
        import webbrowser
        webbrowser.open("http://127.0.0.1:8127")
    
    # -- Public API --
    
    def say(self, text: str):
        """Make Kai say something (from external code)."""
        self._show_speech(text, duration=6.0)
    
    def react(self, emotion: str):
        """Make Kai react to something."""
        if emotion == "happy":
            self._do_wag()
        elif emotion == "alert":
            self._do_bark()
        elif emotion == "tired":
            self._set_state(self.SLEEPING)
            self._show_speech("*yawns*")
    
    def run(self):
        """Start the pet."""
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("🦊 Kai Desktop Pet starting...")
    print("  Left click: interact")
    print("  Right click: menu")
    print("  Drag: move Kai")
    print("  Ctrl+C to quit")
    
    pet = KaiPet()
    
    # Show greeting
    pet.root.after(1000, lambda: pet._show_speech(random.choice(KaiPet.GREETING_LINES)))
    
    try:
        pet.run()
    except KeyboardInterrupt:
        print("\n🦊 Kai went to sleep.")


if __name__ == "__main__":
    main()
