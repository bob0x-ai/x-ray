"""Common provider interface and small provider utilities."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from src.contracts import ProviderResult


class XDataProvider(Protocol):
    name: str

    def fetch_urls(self, values: list[str]) -> ProviderResult:
        """Fetch exact post URLs or raw post IDs."""
        ...

    def read_user_posts(self, user: str, *, limit: int = 20) -> ProviderResult:
        """Read recent posts for one public user."""
        ...

    def search_posts(self, query: str, *, limit: int = 20) -> ProviderResult:
        """Search public posts."""
        ...

    def read_owned_timeline(self, *, limit: int = 20) -> ProviderResult:
        """Read the authenticated account timeline."""
        ...

    def read_mentions(self, *, limit: int = 20) -> ProviderResult:
        """Read mentions for the authenticated account."""
        ...

    def read_thread(self, value: str, *, limit: int = 100) -> ProviderResult:
        """Read a thread/conversation by URL or post ID."""
        ...

    def read_replies(self, value: str, *, limit: int = 100) -> ProviderResult:
        """Read replies for a post URL or post ID."""
        ...

    def read_quotes(self, value: str, *, limit: int = 100) -> ProviderResult:
        """Read quotes for a post URL or post ID."""
        ...

    def read_follow_graph(self, user: str, *, graph: str = "followers", limit: int = 100) -> ProviderResult:
        """Read followers or following for one user."""
        ...

    def collect_posts(self, query: str, *, limit: int = 100) -> ProviderResult:
        """Collect posts for monitoring/bulk workflows."""
        ...


class CooldownMixin:
    """Lightweight in-process cooldown state for fragile/read-limited providers."""

    def __init__(self, *, time_fn: Callable[[], float], cooldown_seconds: int) -> None:
        self._time_fn = time_fn
        self._cooldown_seconds = cooldown_seconds
        self._cooldown_until: float = 0.0
        self._cooldown_reason: str | None = None

    def _activate_cooldown(self, reason: str, *, seconds: int | None = None) -> None:
        duration = max(1, int(seconds if seconds is not None else self._cooldown_seconds))
        self._cooldown_until = self._time_fn() + duration
        self._cooldown_reason = reason

    def _cooldown_status(self) -> dict[str, Any]:
        remaining = max(0, int(self._cooldown_until - self._time_fn()))
        return {
            "cooldown_active": remaining > 0,
            "cooldown_reason": self._cooldown_reason if remaining > 0 else None,
            "cooldown_seconds_remaining": remaining,
        }

    def _cooldown_unavailable(self, provider: str) -> ProviderResult | None:
        status = self._cooldown_status()
        if not status["cooldown_active"]:
            return None
        return ProviderResult.unavailable(
            provider=provider,
            reason="cooldown_active",
            warnings=[str(status["cooldown_reason"])],
            metadata={
                "cooldown_reason": status["cooldown_reason"],
                "cooldown_seconds_remaining": status["cooldown_seconds_remaining"],
            },
        )
