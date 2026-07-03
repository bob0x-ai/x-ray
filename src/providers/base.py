"""Common provider interface."""

from __future__ import annotations

from typing import Protocol

from src.contracts import ProviderResult


class XDataProvider(Protocol):
    name: str

    def fetch_urls(self, values: list[str]) -> ProviderResult:
        """Fetch exact post URLs or raw post IDs."""
        ...

    def read_user_posts(self, user: str, *, limit: int = 20) -> ProviderResult:
        """Read recent posts for one public user."""
        ...
