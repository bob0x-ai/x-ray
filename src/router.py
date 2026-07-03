"""Sequential task router for X data providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from src.contracts import ProviderResult
from src.providers.official_x import OfficialXProvider
from src.providers.socialdata import SocialDataProvider
from src.providers.stub import StubProvider
from src.providers.syndication import SyndicationProvider


DEFAULT_ROUTES: dict[str, list[str]] = {
    "fetch_urls": ["syndication", "official_x", "socialdata", "apify"],
    "read_user_posts_recent": [
        "syndication",
        "twikit",
        "twscrape",
        "socialdata",
        "xpoz",
        "apify",
        "official_x",
    ],
    "search_posts": ["socialdata", "xpoz", "twikit", "twscrape", "apify", "official_x"],
    "read_owned_timeline": ["official_x"],
    "read_mentions": ["official_x"],
    "read_thread": ["twikit", "twscrape", "socialdata", "xpoz", "apify", "official_x"],
    "read_replies": ["socialdata", "xpoz", "apify", "twikit", "twscrape", "official_x"],
    "read_quotes": ["socialdata", "xpoz", "apify", "twikit", "twscrape", "official_x"],
    "read_follow_graph": ["socialdata", "xpoz", "twscrape", "twikit", "apify", "official_x"],
    "collect_posts": ["socialdata", "xpoz", "twscrape", "twikit", "apify"],
}


TASK_METHODS: dict[str, tuple[str, ...]] = {
    "fetch_urls": ("fetch_urls",),
    "read_user_posts_recent": ("read_user_posts",),
    "search_posts": ("search_posts", "search_recent"),
    "read_owned_timeline": ("read_owned_timeline",),
    "read_mentions": ("read_mentions",),
    "read_thread": ("read_thread",),
    "read_replies": ("read_replies",),
    "read_quotes": ("read_quotes",),
    "read_follow_graph": ("read_follow_graph",),
    "collect_posts": ("collect_posts",),
}


TERMINAL_STATUSES = {"needs_approval"}
CONTINUE_STATUSES = {"empty", "unavailable", "error"}


@dataclass(frozen=True)
class ProviderAttempt:
    provider: str
    status: str
    reason: str | None
    items: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "status": self.status,
            "reason": self.reason,
            "items": self.items,
        }


class XDataRouter:
    def __init__(
        self,
        *,
        providers: Mapping[str, Any] | None = None,
        routes: Mapping[str, list[str]] | None = None,
    ) -> None:
        self.routes = dict(routes or DEFAULT_ROUTES)
        self.providers = dict(providers or default_providers())

    def fetch_urls(self, values: list[str]) -> ProviderResult:
        return self.run_task("fetch_urls", values=values)

    def read_user_posts_recent(self, user: str, *, limit: int = 20) -> ProviderResult:
        return self.run_task("read_user_posts_recent", user=user, limit=limit)

    def search_posts(self, query: str, *, limit: int = 20) -> ProviderResult:
        return self.run_task("search_posts", query=query, limit=limit)

    def read_owned_timeline(self, *, limit: int = 20) -> ProviderResult:
        return self.run_task("read_owned_timeline", limit=limit)

    def read_mentions(self, *, limit: int = 20) -> ProviderResult:
        return self.run_task("read_mentions", limit=limit)

    def read_thread(self, value: str, *, limit: int = 100) -> ProviderResult:
        return self.run_task("read_thread", value=value, limit=limit)

    def read_replies(self, value: str, *, limit: int = 100) -> ProviderResult:
        return self.run_task("read_replies", value=value, limit=limit)

    def read_quotes(self, value: str, *, limit: int = 100) -> ProviderResult:
        return self.run_task("read_quotes", value=value, limit=limit)

    def read_follow_graph(self, user: str, *, graph: str = "followers", limit: int = 100) -> ProviderResult:
        return self.run_task("read_follow_graph", user=user, graph=graph, limit=limit)

    def collect_posts(self, query: str, *, limit: int = 100) -> ProviderResult:
        return self.run_task("collect_posts", query=query, limit=limit)

    def status(self) -> dict[str, Any]:
        provider_status: dict[str, Any] = {}
        for name, provider in self.providers.items():
            provider_status[name] = {
                "implemented": not isinstance(provider, StubProvider),
                "class": provider.__class__.__name__,
            }
            status_method = getattr(provider, "status", None)
            if callable(status_method):
                provider_status[name].update(status_method())
        return {
            "providers": provider_status,
            "routes": self.routes,
            "tasks": sorted(self.routes),
        }

    def run_task(self, task: str, **kwargs: Any) -> ProviderResult:
        if task not in self.routes:
            return ProviderResult.error(
                provider="router",
                reason="unknown_task",
                metadata={"task": task},
            )
        if task not in TASK_METHODS:
            return ProviderResult.error(
                provider="router",
                reason="unmapped_task",
                metadata={"task": task},
            )

        attempts: list[ProviderAttempt] = []
        route = self.routes[task]
        for provider_name in route:
            provider = self.providers.get(provider_name) or StubProvider(provider_name)
            result = self._call_provider(task, provider, kwargs)
            attempts.append(
                ProviderAttempt(
                    provider=result.provider,
                    status=result.status,
                    reason=result.reason,
                    items=len(result.items),
                )
            )

            if result.status == "ok" and result.items:
                return _with_attempts(result, attempts)
            if result.status in TERMINAL_STATUSES:
                return _with_attempts(result, attempts)
            if result.status in CONTINUE_STATUSES:
                continue

            return _with_attempts(
                ProviderResult.error(
                    provider="router",
                    reason=f"unexpected_provider_status:{result.status}",
                    metadata={"task": task},
                ),
                attempts,
            )

        return ProviderResult.empty(
            provider="router",
            reason="all_routes_exhausted",
            metadata={
                "task": task,
                "providers_attempted": [attempt.to_dict() for attempt in attempts],
            },
        )

    def _call_provider(self, task: str, provider: Any, kwargs: dict[str, Any]) -> ProviderResult:
        for method_name in TASK_METHODS[task]:
            method = getattr(provider, method_name, None)
            if method is None:
                continue
            try:
                return method(**_task_kwargs(task, kwargs))
            except Exception as exc:
                return ProviderResult.error(
                    provider=getattr(provider, "name", provider.__class__.__name__),
                    reason="provider_exception",
                    warnings=[str(exc)],
                    metadata={"task": task},
                )
        return ProviderResult.unavailable(
            provider=getattr(provider, "name", provider.__class__.__name__),
            reason="not_implemented",
            metadata={"task": task},
        )


def default_providers() -> dict[str, Any]:
    return {
        "syndication": SyndicationProvider(),
        "official_x": OfficialXProvider(),
        "socialdata": SocialDataProvider(),
        "xpoz": StubProvider("xpoz"),
        "twikit": StubProvider("twikit"),
        "twscrape": StubProvider("twscrape"),
        "apify": StubProvider("apify"),
        "xactions": StubProvider("xactions"),
    }


def _task_kwargs(task: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    if task == "fetch_urls":
        return {"values": kwargs["values"]}
    if task == "read_user_posts_recent":
        return {"user": kwargs["user"], "limit": kwargs.get("limit", 20)}
    if task == "search_posts":
        return {"query": kwargs["query"], "limit": kwargs.get("limit", 20)}
    if task in {"read_owned_timeline", "read_mentions"}:
        return {"limit": kwargs.get("limit", 20)}
    if task in {"read_thread", "read_replies", "read_quotes"}:
        return {"value": kwargs["value"], "limit": kwargs.get("limit", 100)}
    if task == "read_follow_graph":
        return {
            "user": kwargs["user"],
            "graph": kwargs.get("graph", "followers"),
            "limit": kwargs.get("limit", 100),
        }
    if task == "collect_posts":
        return {"query": kwargs["query"], "limit": kwargs.get("limit", 100)}
    return kwargs


def _with_attempts(result: ProviderResult, attempts: list[ProviderAttempt]) -> ProviderResult:
    metadata = {
        **result.metadata,
        "providers_attempted": [attempt.to_dict() for attempt in attempts],
    }
    return ProviderResult(
        status=result.status,
        provider=result.provider,
        items=result.items,
        reason=result.reason,
        warnings=result.warnings,
        cost=result.cost,
        raw_ref=result.raw_ref,
        metadata=metadata,
    )
