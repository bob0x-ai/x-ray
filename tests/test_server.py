from src.contracts import Post, ProviderResult
from src.server import (
    MAX_FETCH_URLS,
    clamp_limit,
    create_mcp_server,
    x_data_status_handler,
    x_fetch_urls_handler,
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


def test_status_handler_is_token_safe_shape():
    result = x_data_status_handler(router=_Router())

    assert result["status"] == "ok"
    assert result["server"] == "x-data"
    assert result["providers"]["official_x"]["auth_present"] is True
    assert "token" not in str(result).lower()


def test_mcp_server_constructs():
    server = create_mcp_server(router=_Router())

    assert server is not None
