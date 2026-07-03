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
