"""Stub provider for planned-but-unimplemented backends."""

from __future__ import annotations

from src.contracts import ProviderResult


class StubProvider:
    """Return explicit unavailable results for unimplemented providers."""

    def __init__(self, name: str) -> None:
        self.name = name

    def fetch_urls(self, values: list[str]) -> ProviderResult:
        del values
        return self._not_implemented("fetch_urls")

    def read_user_posts(self, user: str, *, limit: int = 20) -> ProviderResult:
        del user, limit
        return self._not_implemented("read_user_posts")

    def search_posts(self, query: str, *, limit: int = 20) -> ProviderResult:
        del query, limit
        return self._not_implemented("search_posts")

    def read_owned_timeline(self, *, limit: int = 20) -> ProviderResult:
        del limit
        return self._not_implemented("read_owned_timeline")

    def read_mentions(self, *, limit: int = 20) -> ProviderResult:
        del limit
        return self._not_implemented("read_mentions")

    def _not_implemented(self, task: str) -> ProviderResult:
        return ProviderResult.unavailable(
            provider=self.name,
            reason="not_implemented",
            metadata={"task": task},
        )
