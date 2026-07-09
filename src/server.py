"""MCP server wrapper for the X data router."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field
from src.config import load_config
from src.contracts import ProviderResult
from src.diagnostics import doctor_summary_from_healthcheck, doctor_summary_from_status
from src.providers.syndication import normalize_handle
from src.router import XDataRouter

_SERVER_CONFIG = load_config()["server"]
DEFAULT_LIMIT = int(_SERVER_CONFIG["default_limit"])
MAX_LIMIT = int(_SERVER_CONFIG["max_limit"])
MAX_FETCH_URLS = int(_SERVER_CONFIG["max_fetch_urls"])
MAX_COLLECT_LIMIT = int(_SERVER_CONFIG["max_collect_limit"])
FOLLOW_GRAPHS = {"followers", "following"}
HEALTHCHECK_MODES = {"basic", "live", "deep"}
DETAIL_LEVELS = {"summary", "detailed"}
DetailLevel = Literal["summary", "detailed"]
HealthcheckMode = Literal["basic", "live", "deep"]
FollowGraph = Literal["followers", "following"]
MaxCostUsd = Annotated[
    float,
    Field(description="Hard spend cap in USD for this request. Use 0 for free-only routing.", ge=0),
]


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


def validate_max_cost_usd(value: float | int | str | None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def x_fetch_urls_handler(
    values: list[str],
    *,
    max_cost_usd: float | int | str | None,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    budget = validate_max_cost_usd(max_cost_usd)
    if budget is None:
        return _result(ProviderResult.error(provider="mcp", reason="missing_or_invalid_max_cost_usd"))
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
    return _result(router.fetch_urls(clean_values, max_cost_usd=budget))


def x_read_user_posts_handler(
    user: str,
    *,
    max_cost_usd: float | int | str | None,
    limit: int | None = DEFAULT_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    budget = validate_max_cost_usd(max_cost_usd)
    if budget is None:
        return _result(ProviderResult.error(provider="mcp", reason="missing_or_invalid_max_cost_usd"))
    user = normalize_handle(user)
    if not user:
        return _result(ProviderResult.error(provider="mcp", reason="missing_user"))
    return _result(router.read_user_posts_recent(f"@{user}", max_cost_usd=budget, limit=clamp_limit(limit)))


def x_search_posts_handler(
    query: str,
    *,
    max_cost_usd: float | int | str | None,
    limit: int | None = DEFAULT_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    budget = validate_max_cost_usd(max_cost_usd)
    if budget is None:
        return _result(ProviderResult.error(provider="mcp", reason="missing_or_invalid_max_cost_usd"))
    query = str(query or "").strip()
    if not query:
        return _result(ProviderResult.error(provider="mcp", reason="missing_query"))
    return _result(router.search_posts(query, max_cost_usd=budget, limit=clamp_limit(limit)))


def x_read_owned_timeline_handler(
    *,
    max_cost_usd: float | int | str | None,
    limit: int | None = DEFAULT_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    budget = validate_max_cost_usd(max_cost_usd)
    if budget is None:
        return _result(ProviderResult.error(provider="mcp", reason="missing_or_invalid_max_cost_usd"))
    return _result(router.read_owned_timeline(max_cost_usd=budget, limit=clamp_limit(limit)))


def x_read_mentions_handler(
    *,
    max_cost_usd: float | int | str | None,
    limit: int | None = DEFAULT_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    budget = validate_max_cost_usd(max_cost_usd)
    if budget is None:
        return _result(ProviderResult.error(provider="mcp", reason="missing_or_invalid_max_cost_usd"))
    return _result(router.read_mentions(max_cost_usd=budget, limit=clamp_limit(limit)))


def x_data_status_handler(*, detail: str = "summary", router: XDataRouter | None = None) -> dict[str, Any]:
    router = router or XDataRouter()
    detail = str(detail or "summary").strip().lower()
    if detail not in DETAIL_LEVELS:
        return {
            "status": "error",
            "server": "x-data",
            "reason": "invalid_detail_level",
            "metadata": {"allowed": sorted(DETAIL_LEVELS)},
        }
    payload = router.status()
    response = {
        "status": "ok",
        "server": "x-data",
        "summary": doctor_summary_from_status(payload),
    }
    if detail == "detailed":
        response["details"] = payload
    return response


def x_data_healthcheck_handler(
    *,
    mode: str = "live",
    detail: str = "summary",
    provider: str | None = None,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    mode = str(mode or "live").strip().lower()
    detail = str(detail or "summary").strip().lower()
    provider = str(provider or "").strip() or None
    if mode not in HEALTHCHECK_MODES:
        return {
            "status": "error",
            "server": "x-data",
            "reason": "invalid_healthcheck_mode",
            "metadata": {"allowed": sorted(HEALTHCHECK_MODES)},
        }
    if detail not in DETAIL_LEVELS:
        return {
            "status": "error",
            "server": "x-data",
            "reason": "invalid_detail_level",
            "metadata": {"allowed": sorted(DETAIL_LEVELS)},
        }
    payload = router.healthcheck(mode=mode, provider=provider)
    response = {
        "status": "ok",
        "server": "x-data",
        "summary": doctor_summary_from_healthcheck(payload),
    }
    if detail == "detailed":
        response["details"] = payload
    return response


def x_read_thread_handler(
    value: str,
    *,
    max_cost_usd: float | int | str | None,
    limit: int | None = MAX_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    budget = validate_max_cost_usd(max_cost_usd)
    if budget is None:
        return _result(ProviderResult.error(provider="mcp", reason="missing_or_invalid_max_cost_usd"))
    value = str(value or "").strip()
    if not value:
        return _result(ProviderResult.error(provider="mcp", reason="missing_value"))
    return _result(router.read_thread(value, max_cost_usd=budget, limit=clamp_limit(limit, default=MAX_LIMIT)))


def x_read_replies_handler(
    value: str,
    *,
    max_cost_usd: float | int | str | None,
    limit: int | None = MAX_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    budget = validate_max_cost_usd(max_cost_usd)
    if budget is None:
        return _result(ProviderResult.error(provider="mcp", reason="missing_or_invalid_max_cost_usd"))
    value = str(value or "").strip()
    if not value:
        return _result(ProviderResult.error(provider="mcp", reason="missing_value"))
    return _result(router.read_replies(value, max_cost_usd=budget, limit=clamp_limit(limit, default=MAX_LIMIT)))


def x_read_quotes_handler(
    value: str,
    *,
    max_cost_usd: float | int | str | None,
    limit: int | None = MAX_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    budget = validate_max_cost_usd(max_cost_usd)
    if budget is None:
        return _result(ProviderResult.error(provider="mcp", reason="missing_or_invalid_max_cost_usd"))
    value = str(value or "").strip()
    if not value:
        return _result(ProviderResult.error(provider="mcp", reason="missing_value"))
    return _result(router.read_quotes(value, max_cost_usd=budget, limit=clamp_limit(limit, default=MAX_LIMIT)))


def x_read_follow_graph_handler(
    user: str,
    *,
    max_cost_usd: float | int | str | None,
    graph: str = "followers",
    limit: int | None = MAX_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    budget = validate_max_cost_usd(max_cost_usd)
    if budget is None:
        return _result(ProviderResult.error(provider="mcp", reason="missing_or_invalid_max_cost_usd"))
    user = normalize_handle(user)
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
    return _result(
        router.read_follow_graph(f"@{user}", max_cost_usd=budget, graph=graph, limit=clamp_limit(limit, default=MAX_LIMIT))
    )


def x_collect_posts_handler(
    query: str,
    *,
    max_cost_usd: float | int | str | None,
    limit: int | None = MAX_LIMIT,
    router: XDataRouter | None = None,
) -> dict[str, Any]:
    router = router or XDataRouter()
    budget = validate_max_cost_usd(max_cost_usd)
    if budget is None:
        return _result(ProviderResult.error(provider="mcp", reason="missing_or_invalid_max_cost_usd"))
    query = str(query or "").strip()
    if not query:
        return _result(ProviderResult.error(provider="mcp", reason="missing_query"))
    return _result(
        router.collect_posts(
            query,
            max_cost_usd=budget,
            limit=clamp_limit(limit, default=MAX_LIMIT, maximum=MAX_COLLECT_LIMIT),
        )
    )


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
            "Read-only X data tools. Use task tools only; provider routing and "
            "credentials are internal. Every data request must include "
            "`max_cost_usd`. Use `0` for free-only routing. Prefer summary "
            "diagnostics unless detailed output is explicitly needed."
        ),
    )

    @mcp.tool()
    def x_fetch_urls(
        values: Annotated[list[str], Field(description="Exact post URLs or raw post IDs.")],
        max_cost_usd: MaxCostUsd,
    ) -> dict[str, Any]:
        """Fetch exact posts only. Use `0` to forbid paid fallback."""
        return x_fetch_urls_handler(values, max_cost_usd=max_cost_usd, router=active_router)

    @mcp.tool()
    def x_read_user_posts(
        user: Annotated[str, Field(description="X handle, with or without @.")],
        max_cost_usd: MaxCostUsd,
        limit: Annotated[int, Field(description="Max posts to return.", ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Read recent public posts for one user. Use `0` for free-only routing."""
        return x_read_user_posts_handler(user, max_cost_usd=max_cost_usd, limit=limit, router=active_router)

    @mcp.tool()
    def x_search_posts(
        query: Annotated[str, Field(description="X search query.")],
        max_cost_usd: MaxCostUsd,
        limit: Annotated[int, Field(description="Max posts to return.", ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Search public X posts. Use `0` for free-only routing."""
        return x_search_posts_handler(query, max_cost_usd=max_cost_usd, limit=limit, router=active_router)

    @mcp.tool()
    def x_read_owned_timeline(
        max_cost_usd: MaxCostUsd,
        limit: Annotated[int, Field(description="Max posts to return.", ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Read the authenticated account timeline. Usually paid."""
        return x_read_owned_timeline_handler(max_cost_usd=max_cost_usd, limit=limit, router=active_router)

    @mcp.tool()
    def x_read_mentions(
        max_cost_usd: MaxCostUsd,
        limit: Annotated[int, Field(description="Max posts to return.", ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Read mentions for the authenticated account. Usually paid."""
        return x_read_mentions_handler(max_cost_usd=max_cost_usd, limit=limit, router=active_router)

    @mcp.tool()
    def x_read_thread(
        value: Annotated[str, Field(description="Post URL or raw post ID.")],
        max_cost_usd: MaxCostUsd,
        limit: Annotated[int, Field(description="Max posts to return.", ge=1, le=MAX_LIMIT)] = MAX_LIMIT,
    ) -> dict[str, Any]:
        """Read a thread from one post URL or ID."""
        return x_read_thread_handler(value, max_cost_usd=max_cost_usd, limit=limit, router=active_router)

    @mcp.tool()
    def x_read_replies(
        value: Annotated[str, Field(description="Post URL or raw post ID.")],
        max_cost_usd: MaxCostUsd,
        limit: Annotated[int, Field(description="Max replies to return.", ge=1, le=MAX_LIMIT)] = MAX_LIMIT,
    ) -> dict[str, Any]:
        """Read replies for one post URL or ID."""
        return x_read_replies_handler(value, max_cost_usd=max_cost_usd, limit=limit, router=active_router)

    @mcp.tool()
    def x_read_quotes(
        value: Annotated[str, Field(description="Post URL or raw post ID.")],
        max_cost_usd: MaxCostUsd,
        limit: Annotated[int, Field(description="Max quote posts to return.", ge=1, le=MAX_LIMIT)] = MAX_LIMIT,
    ) -> dict[str, Any]:
        """Read quote posts for one post URL or ID."""
        return x_read_quotes_handler(value, max_cost_usd=max_cost_usd, limit=limit, router=active_router)

    @mcp.tool()
    def x_read_follow_graph(
        user: Annotated[str, Field(description="X handle, with or without @.")],
        max_cost_usd: MaxCostUsd,
        graph: Annotated[FollowGraph, Field(description="Read followers or following.")] = "followers",
        limit: Annotated[int, Field(description="Max users to return.", ge=1, le=MAX_LIMIT)] = MAX_LIMIT,
    ) -> dict[str, Any]:
        """Read followers or following for one user."""
        return x_read_follow_graph_handler(user, max_cost_usd=max_cost_usd, graph=graph, limit=limit, router=active_router)

    @mcp.tool()
    def x_collect_posts(
        query: Annotated[str, Field(description="Collection query or monitor term.")],
        max_cost_usd: MaxCostUsd,
        limit: Annotated[int, Field(description="Max posts to return.", ge=1, le=MAX_COLLECT_LIMIT)] = MAX_LIMIT,
    ) -> dict[str, Any]:
        """Collect posts for monitoring. Often paid; set budget carefully."""
        return x_collect_posts_handler(query, max_cost_usd=max_cost_usd, limit=limit, router=active_router)

    @mcp.tool()
    def x_data_status(
        detail: Annotated[DetailLevel, Field(description="Use summary by default; detailed only when needed.")] = "summary",
    ) -> dict[str, Any]:
        """Return server status. Prefer `summary`; request `detailed` only when debugging."""
        return x_data_status_handler(detail=detail, router=active_router)

    @mcp.tool()
    def x_data_healthcheck(
        mode: Annotated[HealthcheckMode, Field(description="basic=no live reads, live=small probe, deep=multiple probes.")] = "live",
        detail: Annotated[DetailLevel, Field(description="Use summary by default; detailed only when needed.")] = "summary",
    ) -> dict[str, Any]:
        """Run diagnostics. Prefer `basic` or `live`; use `deep` only for troubleshooting."""
        return x_data_healthcheck_handler(mode=mode, detail=detail, router=active_router)

    return mcp


def main() -> None:
    create_mcp_server().run()


if __name__ == "__main__":
    main()
