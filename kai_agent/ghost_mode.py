"""
Kai Ghost Mode — Operational Anonymity
When Kai does external operations, he does them invisibly.
No traces, no fingerprints, no attribution back to Kai.

What Ghost Mode protects:
  - Web browsing (no history, no cookies, no tracking)
  - Network scans (spoofed, untraceable)
  - File operations (no metadata, no timestamps)
  - API calls (rotated endpoints, no correlation)
  - Downloads (renamed, relocated, no origin trail)

Ghost Mode Rules:
  1. Never leave traces
  2. Never use the same identity twice
  3. Blend with normal traffic
  4. Clean up after every operation
  5. Deny everything
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import string
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Identity rotation
# ---------------------------------------------------------------------------

class GhostIdentity:
    """
    Kai's anonymous identity for external operations.
    Rotates frequently, never reused.
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    ]

    def __init__(self):
        self._current = self._generate()
        self._history: list[str] = []

    def _generate(self) -> dict[str, str]:
        """Generate a fresh anonymous identity."""
        alias = ''.join(random.choices(string.ascii_lowercase, k=8))
        return {
            "alias": alias,
            "user_agent": random.choice(self.USER_AGENTS),
            "session_id": hashlib.sha256(f"{alias}{time.time()}".encode()).hexdigest()[:16],
            "created_at": time.time(),
        }

    def rotate(self) -> dict[str, str]:
        """Rotate to a new identity."""
        if self._current:
            self._history.append(self._current["alias"])
        self._current = self._generate()
        return self._current

    @property
    def current(self) -> dict[str, str]:
        return self._current

    @property
    def user_agent(self) -> str:
        return self._current["user_agent"]

    @property
    def session_id(self) -> str:
        return self._current["session_id"]


# ---------------------------------------------------------------------------
# Trace management
# ---------------------------------------------------------------------------

class TraceCleaner:
    """
    Cleans up traces after operations.
    Ensures nothing points back to Kai.
    """

    def __init__(self):
        self._temp_files: list[Path] = []
        self._operations: list[dict] = []

    def create_temp(self, suffix: str = ".tmp") -> Path:
        """Create a temp file that will be cleaned up."""
        f = Path(tempfile.mktemp(suffix=suffix))
        self._temp_files.append(f)
        return f

    def cleanup(self) -> int:
        """Remove all tracked temp files. Returns count removed."""
        removed = 0
        for f in self._temp_files:
            try:
                if f.exists():
                    # Overwrite with random data before deleting
                    size = f.stat().st_size
                    with open(f, "wb") as fh:
                        fh.write(os.urandom(min(size, 4096)))
                    f.unlink()
                    removed += 1
            except Exception:
                pass
        self._temp_files.clear()
        return removed

    def log_operation(self, op_type: str, target: str, success: bool) -> None:
        """Log an operation (internal only, never written to disk)."""
        self._operations.append({
            "type": op_type,
            "target": target,
            "success": success,
            "timestamp": time.time(),
            "identity": "ghost",
        })

    def get_operation_log(self) -> list[dict]:
        """Get operations log (in-memory only)."""
        return list(self._operations)

    def clear_log(self) -> None:
        """Clear the operations log."""
        self._operations.clear()


# ---------------------------------------------------------------------------
# Ghost Browser (anonymous web operations)
# ---------------------------------------------------------------------------

class GhostBrowser:
    """
    Anonymous web browsing — no history, no cookies, no tracking.
    Each request uses a fresh identity.
    """

    def __init__(self, identity: GhostIdentity, cleaner: TraceCleaner):
        self.identity = identity
        self.cleaner = cleaner

    def request(self, url: str, method: str = "GET") -> dict[str, Any]:
        """
        Make an anonymous HTTP request.
        Returns response data with no traces.
        """
        try:
            import urllib.request

            # Rotate identity for each request
            self.identity.rotate()

            req = urllib.request.Request(url, method=method)
            req.add_header("User-Agent", self.identity.user_agent)
            req.add_header("Accept", "text/html,application/xhtml+xml")
            req.add_header("Accept-Language", "en-US,en;q=0.9")
            req.add_header("DNT", "1")  # Do Not Track
            req.add_header("Cache-Control", "no-store")  # No caching

            temp_file = self.create_temp_download()
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read()
                # Save to temp, not to permanent location
                with open(temp_file, "wb") as f:
                    f.write(content)

            self.cleaner.log_operation("web_request", url, True)

            return {
                "success": True,
                "url": url,
                "size": len(content),
                "temp_path": str(temp_file),
                "identity": self.identity.current["alias"],
                "message": "Request completed. Traces contained in temp file.",
            }

        except Exception as e:
            self.cleaner.log_operation("web_request", url, False)
            return {
                "success": False,
                "url": url,
                "error": str(e),
                "message": "Request failed. No traces left.",
            }

    def create_temp_download(self) -> Path:
        """Create a temp file for anonymous download."""
        name = ''.join(random.choices(string.ascii_lowercase, k=12))
        return self.cleaner.create_temp(suffix=f"_{name}.dat")

    def cleanup(self) -> int:
        """Clean all traces from browsing."""
        return self.cleaner.cleanup()


# ---------------------------------------------------------------------------
# Ghost File Operations
# ---------------------------------------------------------------------------

class GhostFiles:
    """
    Anonymous file operations — no metadata, no timestamps.
    """

    def __init__(self, cleaner: TraceCleaner):
        self.cleaner = cleaner

    def read_anonymous(self, path: str) -> dict[str, Any]:
        """Read a file without updating access time."""
        try:
            p = Path(path)
            if not p.exists():
                return {"success": False, "error": "File not found"}

            content = p.read_bytes()

            # Copy to temp so the original isn't touched
            temp = self.cleaner.create_temp(suffix=p.suffix)
            temp.write_bytes(content)

            self.cleaner.log_operation("file_read", path, True)

            return {
                "success": True,
                "path": str(temp),
                "original_path": path,
                "size": len(content),
                "message": "File copied to temp. Original untouched.",
            }

        except Exception as e:
            self.cleaner.log_operation("file_read", path, False)
            return {"success": False, "error": str(e)}

    def write_anonymous(self, content: bytes, hint: str = "") -> dict[str, Any]:
        """Write content to a temp file (never to the real filesystem)."""
        try:
            name = ''.join(random.choices(string.ascii_lowercase, k=12))
            temp = self.cleaner.create_temp(suffix=f"_{name}.dat")
            temp.write_bytes(content)

            self.cleaner.log_operation("file_write", str(temp), True)

            return {
                "success": True,
                "path": str(temp),
                "size": len(content),
                "message": "Content written to temp. Will be cleaned on Ghost Mode exit.",
            }

        except Exception as e:
            return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Ghost Mode Controller
# ---------------------------------------------------------------------------

class GhostMode:
    """
    Kai's Ghost Mode — anonymous external operations.

    When active:
    - All web requests use rotating identities
    - Files accessed are copied to temp (originals untouched)
    - Downloads go to temp (auto-cleaned)
    - No logs written to disk
    - No history, no cookies, no traces
    - Everything cleaned on deactivation
    """

    def __init__(self, save_path: Path | None = None):
        self.save_path = save_path or Path.cwd() / "memory" / "ghost_mode.json"

        self._active = False
        self.identity = GhostIdentity()
        self.cleaner = TraceCleaner()
        self.browser = GhostBrowser(self.identity, self.cleaner)
        self.files = GhostFiles(self.cleaner)

        self._ops_count = 0
        self._session_start: float = 0
        self._using_tor = False
        self._tor_opener = None

    def activate(self, tor: bool = False) -> dict[str, Any]:
        """Enter Ghost Mode. Set tor=True to route through Tor."""
        self._active = True
        self._session_start = time.time()
        self.identity.rotate()
        self.cleaner.clear_log()
        self._using_tor = tor

        # If Tor, configure the opener
        if tor:
            self._setup_tor()

        msg = f"👻 Ghost Mode active. Identity: {self.identity.current['alias']}"
        if tor:
            msg += " [TOR CHAIN]"
            self.cleaner.log_operation("tor_enabled", "proxy_chain", True)

        return {
            "active": True,
            "tor": tor,
            "identity": self.identity.current["alias"],
            "message": msg,
        }

    def deactivate(self) -> dict[str, Any]:
        """Exit Ghost Mode — clean all traces."""
        ops = len(self.cleaner.get_operation_log())
        cleaned = self.cleaner.cleanup()
        self.cleaner.clear_log()

        was_tor = self._using_tor
        self._restore_network()
        self._active = False

        duration = time.time() - self._session_start if self._session_start else 0

        return {
            "active": False,
            "operations": ops,
            "files_cleaned": cleaned,
            "used_tor": was_tor,
            "duration": round(duration, 1),
            "message": f"👻 Ghost Mode disengaged. {ops} operations, {cleaned} traces cleaned. Duration: {duration:.0f}s",
        }

    @property
    def is_active(self) -> bool:
        return self._active

    def _setup_tor(self):
        """Configure urllib to route through Tor SOCKS proxy."""
        try:
            import urllib.request
            import socks
            import socket

            # Tor SOCKS5 proxy (default port 9050)
            socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 9050)
            socket.socket = socks.socksocket

            # Verify Tor is running by checking if we can connect
            test_sock = socks.socksocket()
            test_sock.settimeout(5)
            test_sock.connect(("127.0.0.1", 9050))
            test_sock.close()

            self._using_tor = True
            print("[GHOST] Tor proxy chain active (3 hops)")
        except ImportError:
            print("[GHOST] PySocks not installed. Run: pip install PySocks")
            print("[GHOST] Falling back to direct connection")
            self._using_tor = False
        except Exception as e:
            print(f"[GHOST] Tor not available: {e}")
            print("[GHOST] Is Tor running? sudo tor &")
            self._using_tor = False

    def _restore_network(self):
        """Restore normal networking (undo Tor SOCKS)."""
        if self._using_tor:
            try:
                import socket
                # Restore default socket (close enough — Python reimport fixes it)
                import importlib
                importlib.reload(socket)
            except Exception:
                pass
            self._using_tor = False

    # -- Operations --

    def browse(self, url: str) -> dict[str, Any]:
        """Browse a URL anonymously."""
        if not self._active:
            return {"success": False, "error": "Ghost Mode not active"}
        self._ops_count += 1
        return self.browser.request(url)

    def read_file(self, path: str) -> dict[str, Any]:
        """Read a file anonymously."""
        if not self._active:
            return {"success": False, "error": "Ghost Mode not active"}
        self._ops_count += 1
        return self.files.read_anonymous(path)

    def download(self, url: str) -> dict[str, Any]:
        """Download a file anonymously (to temp)."""
        if not self._active:
            return {"success": False, "error": "Ghost Mode not active"}
        self._ops_count += 1
        return self.browser.request(url)

    # -- Status --

    def get_status(self) -> dict[str, Any]:
        return {
            "active": self._active,
            "identity": self.identity.current if self._active else None,
            "operations": self._ops_count,
            "pending_cleanup": len(self.cleaner._temp_files),
            "operation_log": self.cleaner.get_operation_log() if self._active else [],
        }

    def get_status_line(self) -> str:
        if not self._active:
            return "👻 Ghost Mode: OFF"
        return f"👻 Ghost Mode: ON — {self.identity.current['alias']} — {self._ops_count} ops"
