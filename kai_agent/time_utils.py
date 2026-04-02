"""Shared time utilities for Kai."""

from datetime import datetime, timezone


def utc_now() -> str:
    """Current UTC time as ISO string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
