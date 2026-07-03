from src.contracts import Post, ProviderResult
from src.server import (
    MAX_FETCH_URLS,
    clamp_limit,
    create_mcp_server,
    x_collect_posts_handler,
    x_data_status_handler,
    x_fetch_urls_handler,
    x_read_follow_graph_handler,
    x_read_quotes_handler,
    x_read_replies_handler,
    x_read_thread_handler,
    x_read_user_posts_handler,
    x_search_posts_handler,
)


class _Router:
    def __init__(self):
        self.calls = []

    def fetch_urls(self, values):
        self.calls.append(("fetch_urls", values))
        return ProviderResult.ok(provider="test", items=[Post(id="1", text="ok")])

    def read_user_posts_recent(self, user, *, limit=20):
        self.calls.append(("read_user_posts_recent", user, limit))
        return ProviderResult.ok(provider="test", items=[Post(id="2", text="user")])

    def search_posts(self, query, *, limit=20):
        self.calls.append(("search_posts", query, limit))
        return ProviderResult.empty(provider="router", reason="all_routes_exhausted")

    def read_thread(self, value, *, limit=100):
        self.calls.append(("read_thread", value, limit))
        return ProviderResult.empty(provider="router", reason="all_routes_exhausted")

    def read_replies(self, value, *, limit=100):
        self.calls.append(("read_replies", value, limit))
        return ProviderResult.empty(provider="router", reason="all_routes_exhausted")

    def read_quotes(self, value, *, limit=100):
        self.calls.append(("read_quotes", value, limit))
        return ProviderResult.empty(provider="router", reason="all_routes_exhausted")

    def read_follow_graph(self, user, *, graph="followers", limit=100):
        self.calls.append(("read_follow_graph", user, graph, limit))
        return ProviderResult.empty(provider="router", reason="all_routes_exhausted")

    def collect_posts(self, query, *, limit=100):
        self.calls.append(("collect_posts", query, limit))
        return ProviderResult.empty(provider="router", reason="all_routes_exhausted")

    def status(self):
        return {
            "providers": {
                "official_x": {
                    "implemented": True,
                    "auth_present": True,
                    "sdk_available": True,
                }
            },
            "routes": {"fetch_urls": ["test"]},
            "effective_routes": {"fetch_urls": ["test"]},
            "preferred_providers": {"fetch_urls": "test"},
            "tasks": ["fetch_urls"],
        }


def test_clamp_limit_defaults_and_bounds():
    assert clamp_limit(None) == 20
    assert clamp_limit("bad") == 20
    assert clamp_limit(0) == 1
    assert clamp_limit(999) == 100
    assert clamp_limit(7) == 7


def test_fetch_urls_handler_limits_batch_size():
    values = [str(i) for i in range(MAX_FETCH_URLS + 1)]

    result = x_fetch_urls_handler(values, router=_Router())

    assert result["status"] == "needs_approval"
    assert result["reason"] == "too_many_urls"


def test_fetch_urls_handler_calls_router_with_clean_values():
    router = _Router()

    result = x_fetch_urls_handler([" 123 ", "", "https://x.com/a/status/1"], router=router)

    assert result["status"] == "ok"
    assert router.calls == [("fetch_urls", ["123", "https://x.com/a/status/1"])]


def test_read_user_posts_handler_clamps_limit():
    router = _Router()

    result = x_read_user_posts_handler("@alice", limit=999, router=router)

    assert result["status"] == "ok"
    assert router.calls == [("read_user_posts_recent", "@alice", 100)]


def test_search_posts_handler_returns_router_result():
    result = x_search_posts_handler("ai", limit=5, router=_Router())

    assert result["status"] == "empty"
    assert result["reason"] == "all_routes_exhausted"


def test_new_handlers_validate_and_call_router():
    router = _Router()

    assert x_read_thread_handler("123", limit=999, router=router)["status"] == "empty"
    assert x_read_replies_handler("123", limit=8, router=router)["status"] == "empty"
    assert x_read_quotes_handler("123", limit=9, router=router)["status"] == "empty"
    assert x_read_follow_graph_handler("@alice", graph="following", limit=10, router=router)["status"] == "empty"
    assert x_collect_posts_handler("ai", limit=9999, router=router)["status"] == "empty"

    assert router.calls == [
        ("read_thread", "123", 100),
        ("read_replies", "123", 8),
        ("read_quotes", "123", 9),
        ("read_follow_graph", "@alice", "following", 10),
        ("collect_posts", "ai", 500),
    ]


def test_new_handlers_reject_missing_or_invalid_inputs():
    assert x_read_thread_handler("", router=_Router())["reason"] == "missing_value"
    assert x_read_replies_handler("", router=_Router())["reason"] == "missing_value"
    assert x_read_quotes_handler("", router=_Router())["reason"] == "missing_value"
    assert x_read_follow_graph_handler("", router=_Router())["reason"] == "missing_user"
    assert x_read_follow_graph_handler("@alice", graph="likes", router=_Router())["reason"] == "invalid_graph"
    assert x_collect_posts_handler("", router=_Router())["reason"] == "missing_query"


def test_status_handler_is_token_safe_shape():
    result = x_data_status_handler(router=_Router())

    assert result["status"] == "ok"
    assert result["server"] == "x-data"
    assert result["providers"]["official_x"]["auth_present"] is True
    assert result["effective_routes"]["fetch_urls"] == ["test"]
    assert result["preferred_providers"]["fetch_urls"] == "test"
    assert "token" not in str(result).lower()


def test_mcp_server_constructs():
    server = create_mcp_server(router=_Router())

    assert server is not None
