"""
Kai Bridge Auth
Token-based authentication for device connections.
Each device gets a unique token. Kai trusts tokens, not IPs.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _generate_token() -> str:
    """Generate a secure device token."""
    return secrets.token_urlsafe(32)


def _hash_token(token: str, salt: str) -> str:
    """Hash a token for storage."""
    return hashlib.pbkdf2_hmac("sha256", token.encode(), salt.encode(), 100_000).hex()


@dataclass
class DeviceRegistration:
    """A registered device that can connect to Kai."""
    device_id: str
    device_name: str  # "iPhone", "Desktop", "Tablet"
    device_type: str  # "phone", "desktop", "tablet", "browser"
    token_hash: str
    salt: str
    created_at: float
    last_seen: float = 0.0
    push_endpoint: str = ""  # Web Push subscription endpoint
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "token_hash": self.token_hash,
            "salt": self.salt,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "push_endpoint": self.push_endpoint,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> DeviceRegistration:
        return cls(**d)


class KaiBridgeAuth:
    """
    Manages device authentication for the Kai bridge.
    Stores registered devices, validates tokens, tracks presence.
    """

    def __init__(self, save_path: Path | None = None) -> None:
        self.save_path = save_path or Path.cwd() / "memory" / "devices.json"
        self.devices: dict[str, DeviceRegistration] = {}
        self.active_sessions: dict[str, str] = {}  # device_id -> session_id
        self._load()

    def _load(self) -> None:
        if self.save_path.exists():
            try:
                data = json.loads(self.save_path.read_text(encoding="utf-8"))
                for d in data.get("devices", []):
                    reg = DeviceRegistration.from_dict(d)
                    self.devices[reg.device_id] = reg
            except Exception:
                pass

    def save(self) -> None:
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "devices": [d.to_dict() for d in self.devices.values()],
            "updated_at": time.time(),
        }
        self.save_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # -- Device registration --

    def register_device(self, device_name: str, device_type: str = "browser") -> dict[str, str]:
        """
        Register a new device. Returns the token (only shown once!).
        """
        device_id = secrets.token_hex(8)
        token = _generate_token()
        salt = secrets.token_hex(16)
        token_hash = _hash_token(token, salt)

        reg = DeviceRegistration(
            device_id=device_id,
            device_name=device_name,
            device_type=device_type,
            token_hash=token_hash,
            salt=salt,
            created_at=time.time(),
            last_seen=time.time(),
        )
        self.devices[device_id] = reg
        self.save()

        return {
            "device_id": device_id,
            "device_name": device_name,
            "token": token,  # Only time this is shown!
            "message": "Save this token — it won't be shown again.",
        }

    # -- Authentication --

    def authenticate(self, device_id: str, token: str) -> bool:
        """Validate a device token."""
        reg = self.devices.get(device_id)
        if not reg or not reg.is_active:
            return False

        expected_hash = _hash_token(token, reg.salt)
        if not hmac.compare_digest(expected_hash, reg.token_hash):
            return False

        reg.last_seen = time.time()
        self.save()
        return True

    def revoke_device(self, device_id: str) -> bool:
        """Revoke a device's access."""
        reg = self.devices.get(device_id)
        if reg:
            reg.is_active = False
            self.save()
            return True
        return False

    # -- Presence --

    def set_active(self, device_id: str, session_id: str) -> None:
        """Mark a device as the active session."""
        self.active_sessions[device_id] = session_id
        # Deactivate other sessions of same type
        reg = self.devices.get(device_id)
        if reg:
            for other_id, other_reg in self.devices.items():
                if other_id != device_id and other_reg.device_type == reg.device_type:
                    self.active_sessions.pop(other_id, None)

    def get_active_device(self) -> str | None:
        """Get the currently active device ID."""
        for device_id, session_id in self.active_sessions.items():
            reg = self.devices.get(device_id)
            if reg and reg.is_active:
                return device_id
        return None

    def get_device_info(self, device_id: str) -> dict[str, Any] | None:
        """Get info about a device."""
        reg = self.devices.get(device_id)
        if reg:
            return {
                "device_id": reg.device_id,
                "device_name": reg.device_name,
                "device_type": reg.device_type,
                "last_seen": reg.last_seen,
                "is_active": reg.is_active,
                "has_push": bool(reg.push_endpoint),
            }
        return None

    def list_devices(self) -> list[dict[str, Any]]:
        """List all registered devices."""
        return [
            {
                "device_id": d.device_id,
                "device_name": d.device_name,
                "device_type": d.device_type,
                "last_seen": d.last_seen,
                "is_active": d.is_active,
            }
            for d in self.devices.values()
        ]

    def set_push_endpoint(self, device_id: str, endpoint: str) -> bool:
        """Store a Web Push subscription for a device."""
        reg = self.devices.get(device_id)
        if reg:
            reg.push_endpoint = endpoint
            self.save()
            return True
        return False
