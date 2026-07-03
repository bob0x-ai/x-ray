"""MCP server wrapper for the X data router."""

from __future__ import annotations

from typing import Any

from src.contracts import ProviderResult
from src.router import XDataRouter


DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MAX_FETCH_URLS = 25


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
    def x_data_status() -> dict[str, Any]:
        """Return token-safe provider and route status."""
        return x_data_status_handler(router=active_router)

    return mcp


def main() -> None:
    create_mcp_server().run()


if __name__ == "__main__":
    main()
