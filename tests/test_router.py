from src.contracts import CostEstimate, Post, ProviderResult
from src.providers.stub import StubProvider
from src.router import XDataRouter


class _Provider:
    def __init__(self, name, result):
        self.name = name
        self.result = result
        self.calls = []

    def fetch_urls(self, values):
        self.calls.append(("fetch_urls", values))
        return self.result

    def read_user_posts(self, user, *, limit=20):
        self.calls.append(("read_user_posts", user, limit))
        return self.result

    def search_posts(self, query, *, limit=20):
        self.calls.append(("search_posts", query, limit))
        return self.result


class _SearchRecentOnlyProvider:
    name = "official_x"

    def search_recent(self, query, *, limit=20):
        return ProviderResult.ok(
            provider=self.name,
            items=[Post(id="s1", text=f"{query}:{limit}")],
        )


def test_router_returns_first_non_empty_result():
    first = _Provider("first", ProviderResult.empty(provider="first"))
    second = _Provider("second", ProviderResult.ok(provider="second", items=[Post(id="1", text="ok")]))
    third = _Provider("third", ProviderResult.ok(provider="third", items=[Post(id="2", text="skip")]))
    router = XDataRouter(
        providers={"first": first, "second": second, "third": third},
        routes={"fetch_urls": ["first", "second", "third"]},
    )

    result = router.fetch_urls(["123"])

    assert result.status == "ok"
    assert result.provider == "second"
    assert result.items[0].id == "1"
    assert [attempt["provider"] for attempt in result.metadata["providers_attempted"]] == [
        "first",
        "second",
    ]
    assert third.calls == []


def test_router_continues_past_unavailable_error_and_empty():
    providers = {
        "a": _Provider("a", ProviderResult.unavailable(provider="a", reason="not_configured")),
        "b": _Provider("b", ProviderResult.error(provider="b", reason="boom")),
        "c": _Provider("c", ProviderResult.empty(provider="c")),
        "d": _Provider("d", ProviderResult.ok(provider="d", items=[Post(id="1", text="ok")])),
    }
    router = XDataRouter(providers=providers, routes={"fetch_urls": ["a", "b", "c", "d"]})

    result = router.fetch_urls(["123"])

    assert result.status == "ok"
    assert result.provider == "d"
    assert [attempt["status"] for attempt in result.metadata["providers_attempted"]] == [
        "unavailable",
        "error",
        "empty",
        "ok",
    ]


def test_router_stops_on_needs_approval():
    first = _Provider(
        "first",
        ProviderResult.needs_approval(
            provider="first",
            reason="budget_required",
            cost=CostEstimate(amount_usd=1.0, basis="test"),
        ),
    )
    second = _Provider("second", ProviderResult.ok(provider="second", items=[Post(id="1", text="skip")]))
    router = XDataRouter(
        providers={"first": first, "second": second},
        routes={"fetch_urls": ["first", "second"]},
    )

    result = router.fetch_urls(["123"])

    assert result.status == "needs_approval"
    assert result.provider == "first"
    assert result.metadata["providers_attempted"][0]["reason"] == "budget_required"
    assert second.calls == []


def test_router_returns_empty_when_all_routes_exhausted():
    router = XDataRouter(
        providers={"stub": StubProvider("stub")},
        routes={"fetch_urls": ["stub"]},
    )

    result = router.fetch_urls(["123"])

    assert result.status == "empty"
    assert result.provider == "router"
    assert result.reason == "all_routes_exhausted"
    assert result.metadata["providers_attempted"][0]["reason"] == "not_implemented"


def test_unknown_task_returns_error():
    result = XDataRouter(providers={}, routes={}).run_task("nope")

    assert result.status == "error"
    assert result.reason == "unknown_task"


def test_router_uses_search_recent_fallback_method_name():
    router = XDataRouter(
        providers={"official_x": _SearchRecentOnlyProvider()},
        routes={"search_posts": ["official_x"]},
    )

    result = router.search_posts("ai", limit=5)

    assert result.status == "ok"
    assert result.items[0].text == "ai:5"


def test_read_user_posts_passes_user_and_limit():
    provider = _Provider("p", ProviderResult.ok(provider="p", items=[Post(id="1", text="ok")]))
    router = XDataRouter(
        providers={"p": provider},
        routes={"read_user_posts_recent": ["p"]},
    )

    result = router.read_user_posts_recent("@alice", limit=7)

    assert result.status == "ok"
    assert provider.calls == [("read_user_posts", "@alice", 7)]
