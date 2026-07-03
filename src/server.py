"""MCP server wrapper for the X data router."""

from __future__ import annotations

from typing import Any

from src.contracts import ProviderResult
from src.router import XDataRouter


DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_FETCH_URLS = 25
MAX_COLLECT_LIMIT = 500
FOLLOW_GRAPHS = {"followers", "following"}


def clamp_limit(limit: int | None, *, default: int = DEFAULT_LIMIT, maximum: int = MAX_LIMIT) -> int:
    if limit is None:
        return default
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, maximum))


def _result(result: ProviderResult) -> dict[str, Any]:
    return result.to_dict()


def x_fetch_urls_handler(values: list[str], *, router: XDataRouter | None = None) -> dict[str, Any]:
    router = router or XDataRouter()
    clean_values = [str(value).strip() for value in values or [] if str(value).strip()]
    if not clean_values:
        return _result(ProviderResult.error(provider="mcp", reason="missing_values"))
    if len(clean_values) > MAX_FETCH_URLS:
        return _result(
            ProviderResult.needs_approval(
                provider="mcp",
                reason="too_many_urls",
                metadata={"max": MAX_FETCH_URLS, "requested": len(clean_values)},
            )
        )
    return _result(router.fetch_urls(clean_values))


def x_read_user_posts_handler(
    user: str,
    *,
    limit: int | None = DEFAULT_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    user = str(user or "").strip()
    if not user:
        return _result(ProviderResult.error(provider="mcp", reason="missing_user"))
    return _result(router.read_user_posts_recent(user, limit=clamp_limit(limit)))


def x_search_posts_handler(
    query: str,
    *,
    limit: int | None = DEFAULT_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    query = str(query or "").strip()
    if not query:
        return _result(ProviderResult.error(provider="mcp", reason="missing_query"))
    return _result(router.search_posts(query, limit=clamp_limit(limit)))


def x_read_owned_timeline_handler(
    *,
    limit: int | None = DEFAULT_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    return _result(router.read_owned_timeline(limit=clamp_limit(limit)))


def x_read_mentions_handler(
    *,
    limit: int | None = DEFAULT_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    return _result(router.read_mentions(limit=clamp_limit(limit)))


def x_data_status_handler(*, router: XDataRouter | None = None) -> dict[str, Any]:
    router = router or XDataRouter()
    return {
        "status": "ok",
        "server": "x-data",
        **router.status(),
    }


def x_read_thread_handler(
    value: str,
    *,
    limit: int | None = MAX_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    value = str(value or "").strip()
    if not value:
        return _result(ProviderResult.error(provider="mcp", reason="missing_value"))
    return _result(router.read_thread(value, limit=clamp_limit(limit, default=MAX_LIMIT)))


def x_read_replies_handler(
    value: str,
    *,
    limit: int | None = MAX_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    value = str(value or "").strip()
    if not value:
        return _result(ProviderResult.error(provider="mcp", reason="missing_value"))
    return _result(router.read_replies(value, limit=clamp_limit(limit, default=MAX_LIMIT)))


def x_read_quotes_handler(
    value: str,
    *,
    limit: int | None = MAX_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    value = str(value or "").strip()
    if not value:
        return _result(ProviderResult.error(provider="mcp", reason="missing_value"))
    return _result(router.read_quotes(value, limit=clamp_limit(limit, default=MAX_LIMIT)))


def x_read_follow_graph_handler(
    user: str,
    *,
    graph: str = "followers",
    limit: int | None = MAX_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    user = str(user or "").strip()
    graph = str(graph or "").strip().lower()
    if not user:
        return _result(ProviderResult.error(provider="mcp", reason="missing_user"))
    if graph not in FOLLOW_GRAPHS:
        return _result(
            ProviderResult.error(
                provider="mcp",
                reason="invalid_graph",
                metadata={"allowed": sorted(FOLLOW_GRAPHS)},
            )
        )
    return _result(router.read_follow_graph(user, graph=graph, limit=clamp_limit(limit, default=MAX_LIMIT)))


def x_collect_posts_handler(
    query: str,
    *,
    limit: int | None = MAX_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    query = str(query or "").strip()
    if not query:
        return _result(ProviderResult.error(provider="mcp", reason="missing_query"))
    return _result(router.collect_posts(query, limit=clamp_limit(limit, default=MAX_LIMIT, maximum=MAX_COLLECT_LIMIT)))


def create_mcp_server(router: XDataRouter | None = None) -> Any:
    """Create the FastMCP server.

    Imported lazily so tests and provider usage do not require MCP unless the
    server boundary is actually constructed.
    """
    from mcp.server.fastmcp import FastMCP

    active_router = router or XDataRouter()
    mcp = FastMCP(
        "x-data",
        instructions=(
            "Read-only X data tools. Use task tools only; provider routing is "
            "internal and credentials are never exposed."
        ),
    )

    @mcp.tool()
    def x_fetch_urls(values: list[str]) -> dict[str, Any]:
        """Fetch exact X/Twitter post URLs or raw post IDs."""
        return x_fetch_urls_handler(values, router=active_router)

    @mcp.tool()
    def x_read_user_posts(user: str, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        """Read recent public posts for one X user."""
        return x_read_user_posts_handler(user, limit=limit, router=active_router)

    @mcp.tool()
    def x_search_posts(query: str, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        """Search X posts through the internal provider router."""
        return x_search_posts_handler(query, limit=limit, router=active_router)

    @mcp.tool()
    def x_read_owned_timeline(limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        """Read the authenticated account timeline via the official provider."""
        return x_read_owned_timeline_handler(limit=limit, router=active_router)

    @mcp.tool()
    def x_read_mentions(limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        """Read mentions for the authenticated account via the official provider."""
        return x_read_mentions_handler(limit=limit, router=active_router)

    @mcp.tool()
    def x_read_thread(value: str, limit: int = MAX_LIMIT) -> dict[str, Any]:
        """Read a thread/conversation by X/Twitter post URL or raw post ID."""
        return x_read_thread_handler(value, limit=limit, router=active_router)

    @mcp.tool()
    def x_read_replies(value: str, limit: int = MAX_LIMIT) -> dict[str, Any]:
        """Read replies for an X/Twitter post URL or raw post ID."""
        return x_read_replies_handler(value, limit=limit, router=active_router)

    @mcp.tool()
    def x_read_quotes(value: str, limit: int = MAX_LIMIT) -> dict[str, Any]:
        """Read quote posts for an X/Twitter post URL or raw post ID."""
        return x_read_quotes_handler(value, limit=limit, router=active_router)

    @mcp.tool()
    def x_read_follow_graph(user: str, graph: str = "followers", limit: int = MAX_LIMIT) -> dict[str, Any]:
        """Read followers or following for one X user."""
        return x_read_follow_graph_handler(user, graph=graph, limit=limit, router=active_router)

    @mcp.tool()
    def x_collect_posts(query: str, limit: int = MAX_LIMIT) -> dict[str, Any]:
        """Collect posts for monitoring or bulk workflows through the router."""
        return x_collect_posts_handler(query, limit=limit, router=active_router)

    @mcp.tool()
    def x_data_status() -> dict[str, Any]:
        """Return token-safe provider and route status."""
        return x_data_status_handler(router=active_router)

    return mcp


def main() -> None:
    create_mcp_server().run()


if __name__ == "__main__":
    main()
