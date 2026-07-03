"""Read-only official X API provider using the Python XDK directly."""

from __future__ import annotations

import os
from typing import Any, Callable

from src.contracts import CostEstimate, Metrics, Post, ProviderResult, UserProfile, UserRef
from src.providers.syndication import extract_post_id, normalize_handle


PROVIDER_NAME = "official_x"
POST_READ_COST_USD = 0.005
OWNED_READ_COST_USD = 0.001
USER_READ_COST_USD = 0.010


ClientFactory = Callable[[str], Any]


def _env_value(primary: str, fallback: str | None = None) -> str | None:
    value = os.getenv(primary)
    if value:
        return value
    if fallback:
        return os.getenv(fallback)
    return None


def _load_xdk_client_factory() -> ClientFactory | None:
    try:
        from xdk import Client  # type: ignore
    except Exception:
        return None
    return lambda access_token: Client(access_token=access_token)


def _data_items(response: Any) -> list[Any]:
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    if data is None:
        return []
    if isinstance(data, list):
        return data
    return [data]


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _metrics_from_obj(obj: Any) -> Metrics | None:
    public_metrics = _value(obj, "public_metrics")
    if not isinstance(public_metrics, dict):
        public_metrics = {}
    metrics = Metrics(
        replies=_maybe_int(public_metrics.get("reply_count")),
        reposts=_maybe_int(public_metrics.get("retweet_count")),
        likes=_maybe_int(public_metrics.get("like_count")),
        quotes=_maybe_int(public_metrics.get("quote_count")),
        views=_maybe_int(public_metrics.get("impression_count")),
    )
    if all(value is None for value in metrics.__dict__.values()):
        return None
    return metrics


def _user_public_metrics_from_obj(obj: Any) -> dict[str, int] | None:
    public_metrics = _value(obj, "public_metrics")
    if not isinstance(public_metrics, dict):
        return None
    metrics = {
        key: int(value)
        for key, value in public_metrics.items()
        if isinstance(value, int) or (isinstance(value, str) and value.isdigit())
    }
    if not metrics:
        return None
    return metrics


def _maybe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _post_from_obj(obj: Any) -> Post | None:
    post_id = str(_value(obj, "id", "") or "").strip()
    text = str(_value(obj, "text", "") or "").strip()
    if not post_id or not text:
        return None
    author_id = _value(obj, "author_id")
    return Post(
        id=post_id,
        text=text,
        author=UserRef(id=str(author_id)) if author_id else None,
        created_at=_value(obj, "created_at"),
        metrics=_metrics_from_obj(obj),
        source_url=f"https://x.com/i/web/status/{post_id}",
        raw=obj if isinstance(obj, dict) else getattr(obj, "__dict__", {}),
    )


def _user_from_obj(obj: Any) -> UserProfile | None:
    user_id = str(_value(obj, "id", "") or "").strip()
    username = str(_value(obj, "username", "") or "").strip() or None
    if not user_id:
        return None
    return UserProfile(
        id=user_id,
        username=username,
        name=_value(obj, "name"),
        description=_value(obj, "description"),
        public_metrics=_user_public_metrics_from_obj(obj),
        source_url=f"https://x.com/{username}" if username else None,
        raw=obj if isinstance(obj, dict) else getattr(obj, "__dict__", {}),
    )


def _with_extra_context(
    result: ProviderResult,
    *,
    warning: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProviderResult:
    return ProviderResult(
        status=result.status,
        provider=result.provider,
        items=result.items,
        reason=result.reason,
        warnings=[*result.warnings, *([warning] if warning else [])],
        cost=result.cost,
        raw_ref=result.raw_ref,
        metadata={**result.metadata, **(metadata or {})},
    )


class OfficialXProvider:
    """Read-only official X provider.

    This provider intentionally does not refresh or write tokens in v1. Token
    refresh can be added later as a contained credential component.
    """

    name = PROVIDER_NAME

    def __init__(self, *, client_factory: ClientFactory | None = None) -> None:
        self._client_factory = client_factory

    def _access_token(self) -> str | None:
        return _env_value("X_OAUTH2_ACCESS_TOKEN", "X_ACCESS_TOKEN")

    def _client(self) -> tuple[Any | None, ProviderResult | None]:
        token = self._access_token()
        if not token:
            return None, ProviderResult.unavailable(
                provider=self.name,
                reason="auth_required",
                warnings=["missing X_OAUTH2_ACCESS_TOKEN/X_ACCESS_TOKEN"],
            )
        factory = self._client_factory or _load_xdk_client_factory()
        if factory is None:
            return None, ProviderResult.unavailable(
                provider=self.name,
                reason="sdk_missing",
                warnings=["install xdk or the official-x optional dependency"],
            )
        try:
            return factory(token), None
        except Exception as exc:
            return None, ProviderResult.error(
                provider=self.name,
                reason="client_init_failed",
                warnings=[str(exc)],
            )

    def status(self) -> dict[str, Any]:
        return {
            "auth_required": True,
            "auth_present": bool(self._access_token()),
            "sdk_available": self._client_factory is not None
            or _load_xdk_client_factory() is not None,
            "token_refresh": "deferred",
            "read_only": True,
        }

    def fetch_urls(self, values: list[str]) -> ProviderResult:
        client, unavailable = self._client()
        if unavailable:
            return unavailable
        assert client is not None

        posts: list[Post] = []
        warnings: list[str] = []
        tweet_fields = ["created_at", "public_metrics", "text", "author_id"]
        for value in values:
            post_id = extract_post_id(value)
            if not post_id:
                warnings.append(f"invalid_post_reference:{value}")
                continue
            try:
                response = client.posts.get_by_id(id=post_id, tweet_fields=tweet_fields)
            except Exception as exc:
                return ProviderResult.error(
                    provider=self.name,
                    reason="api_error",
                    warnings=[str(exc), *warnings],
                )
            items = [_post_from_obj(item) for item in _data_items(response)]
            posts.extend([item for item in items if item is not None])
        if posts:
            return ProviderResult.ok(
                provider=self.name,
                items=posts,
                warnings=warnings,
                cost=CostEstimate(
                    amount_usd=len(posts) * POST_READ_COST_USD,
                    basis="$0.005/post read",
                ),
            )
        if warnings:
            return ProviderResult.empty(provider=self.name, reason="no_fetchable_posts", warnings=warnings)
        return ProviderResult.empty(provider=self.name)

    def read_user_posts(self, user: str, *, limit: int = 20) -> ProviderResult:
        client, unavailable = self._client()
        if unavailable:
            return unavailable
        assert client is not None

        handle_or_id = normalize_handle(user)
        if not handle_or_id:
            return ProviderResult.error(provider=self.name, reason="missing_user")
        try:
            user_id = handle_or_id if handle_or_id.isdigit() else self._resolve_user_id(client, handle_or_id)
            posts = self._collect_pages(
                client.users.get_posts,
                {"id": user_id},
                limit=limit,
            )
        except Exception as exc:
            return ProviderResult.error(provider=self.name, reason="api_error", warnings=[str(exc)])
        if posts:
            return ProviderResult.ok(
                provider=self.name,
                items=posts,
                cost=CostEstimate(
                    amount_usd=len(posts) * POST_READ_COST_USD,
                    basis="$0.005/post read; may be $0.001 owned read for owned account",
                ),
            )
        return ProviderResult.empty(provider=self.name)

    def read_owned_timeline(self, *, limit: int = 20) -> ProviderResult:
        client, unavailable = self._client()
        if unavailable:
            return unavailable
        assert client is not None
        try:
            user_id = self._get_me_id(client)
            posts = self._collect_pages(client.users.get_timeline, {"id": user_id}, limit=limit)
        except Exception as exc:
            return ProviderResult.error(provider=self.name, reason="api_error", warnings=[str(exc)])
        if posts:
            return ProviderResult.ok(
                provider=self.name,
                items=posts,
                cost=CostEstimate(
                    amount_usd=len(posts) * OWNED_READ_COST_USD,
                    basis="$0.001/owned read",
                ),
            )
        return ProviderResult.empty(provider=self.name)

    def read_mentions(self, *, limit: int = 20) -> ProviderResult:
        client, unavailable = self._client()
        if unavailable:
            return unavailable
        assert client is not None
        try:
            user_id = self._get_me_id(client)
            posts = self._collect_pages(client.users.get_mentions, {"id": user_id}, limit=limit)
        except Exception as exc:
            return ProviderResult.error(provider=self.name, reason="api_error", warnings=[str(exc)])
        if posts:
            return ProviderResult.ok(
                provider=self.name,
                items=posts,
                cost=CostEstimate(
                    amount_usd=len(posts) * OWNED_READ_COST_USD,
                    basis="$0.001/owned read",
                ),
            )
        return ProviderResult.empty(provider=self.name)

    def search_recent(self, query: str, *, limit: int = 20) -> ProviderResult:
        client, unavailable = self._client()
        if unavailable:
            return unavailable
        assert client is not None
        if not query.strip():
            return ProviderResult.error(provider=self.name, reason="missing_query")
        try:
            posts = self._collect_pages(
                client.posts.search_recent,
                {"query": query},
                limit=limit,
            )
        except Exception as exc:
            return ProviderResult.error(provider=self.name, reason="api_error", warnings=[str(exc)])
        if posts:
            return ProviderResult.ok(
                provider=self.name,
                items=posts,
                cost=CostEstimate(
                    amount_usd=len(posts) * POST_READ_COST_USD,
                    basis="$0.005/post read",
                ),
            )
        return ProviderResult.empty(provider=self.name)

    def read_thread(self, value: str, *, limit: int = 100) -> ProviderResult:
        post_id = extract_post_id(value)
        if not post_id:
            return ProviderResult.error(provider=self.name, reason="invalid_post_reference")
        query = f"conversation_id:{post_id}"
        result = self._search_recent_query(query, limit=limit)
        if result.status == "ok":
            return _with_extra_context(
                result,
                warning="official_recent_search_only",
                metadata={"query": query},
            )
        return result

    def read_replies(self, value: str, *, limit: int = 100) -> ProviderResult:
        post_id = extract_post_id(value)
        if not post_id:
            return ProviderResult.error(provider=self.name, reason="invalid_post_reference")
        query = f"conversation_id:{post_id} is:reply"
        result = self._search_recent_query(query, limit=limit)
        if result.status == "ok":
            return _with_extra_context(
                result,
                warning="official_recent_search_only",
                metadata={"query": query},
            )
        return result

    def read_quotes(self, value: str, *, limit: int = 100) -> ProviderResult:
        post_id = extract_post_id(value)
        if not post_id:
            return ProviderResult.error(provider=self.name, reason="invalid_post_reference")
        client, unavailable = self._client()
        if unavailable:
            return unavailable
        assert client is not None
        try:
            posts = self._collect_pages(
                client.posts.get_quoted,
                {"id": post_id},
                limit=limit,
            )
        except AttributeError:
            return ProviderResult.unavailable(provider=self.name, reason="sdk_method_missing")
        except Exception as exc:
            return ProviderResult.error(provider=self.name, reason="api_error", warnings=[str(exc)])
        if posts:
            return ProviderResult.ok(
                provider=self.name,
                items=posts,
                cost=CostEstimate(
                    amount_usd=len(posts) * POST_READ_COST_USD,
                    basis="$0.005/post read",
                ),
            )
        return ProviderResult.empty(provider=self.name)

    def read_follow_graph(self, user: str, *, graph: str = "followers", limit: int = 100) -> ProviderResult:
        if graph not in {"followers", "following"}:
            return ProviderResult.error(provider=self.name, reason="invalid_graph")
        client, unavailable = self._client()
        if unavailable:
            return unavailable
        assert client is not None

        handle_or_id = normalize_handle(user)
        if not handle_or_id:
            return ProviderResult.error(provider=self.name, reason="missing_user")
        try:
            user_id = handle_or_id if handle_or_id.isdigit() else self._resolve_user_id(client, handle_or_id)
            method = client.users.get_followers if graph == "followers" else client.users.get_following
            users = self._collect_user_pages(method, {"id": user_id}, limit=limit)
        except AttributeError:
            return ProviderResult.unavailable(provider=self.name, reason="sdk_method_missing")
        except Exception as exc:
            return ProviderResult.error(provider=self.name, reason="api_error", warnings=[str(exc)])
        if users:
            return ProviderResult.ok(
                provider=self.name,
                items=users,
                cost=CostEstimate(
                    amount_usd=len(users) * USER_READ_COST_USD,
                    basis="$0.010/user graph read",
                ),
                metadata={"graph": graph, "user_id": user_id},
            )
        return ProviderResult.empty(provider=self.name)

    def _search_recent_query(self, query: str, *, limit: int) -> ProviderResult:
        client, unavailable = self._client()
        if unavailable:
            return unavailable
        assert client is not None
        try:
            posts = self._collect_pages(
                client.posts.search_recent,
                {"query": query},
                limit=limit,
            )
        except Exception as exc:
            return ProviderResult.error(provider=self.name, reason="api_error", warnings=[str(exc)])
        if posts:
            return ProviderResult.ok(
                provider=self.name,
                items=posts,
                cost=CostEstimate(
                    amount_usd=len(posts) * POST_READ_COST_USD,
                    basis="$0.005/post read",
                ),
            )
        return ProviderResult.empty(provider=self.name)

    def _collect_pages(self, method: Callable[..., Any], base_kwargs: dict[str, Any], *, limit: int) -> list[Post]:
        capped_limit = max(1, min(int(limit), 100))
        tweet_fields = ["created_at", "public_metrics", "text", "author_id"]
        kwargs = {**base_kwargs, "max_results": capped_limit, "tweet_fields": tweet_fields}
        results: list[Post] = []
        for page in method(**kwargs):
            for item in _data_items(page):
                post = _post_from_obj(item)
                if post:
                    results.append(post)
                    if len(results) >= capped_limit:
                        return results
        return results

    def _collect_user_pages(
        self,
        method: Callable[..., Any],
        base_kwargs: dict[str, Any],
        *,
        limit: int,
    ) -> list[UserProfile]:
        capped_limit = max(1, min(int(limit), 100))
        user_fields = ["created_at", "description", "public_metrics", "username", "name"]
        kwargs = {**base_kwargs, "max_results": capped_limit, "user_fields": user_fields}
        results: list[UserProfile] = []
        for page in method(**kwargs):
            for item in _data_items(page):
                user = _user_from_obj(item)
                if user:
                    results.append(user)
                    if len(results) >= capped_limit:
                        return results
        return results

    def _resolve_user_id(self, client: Any, username: str) -> str:
        response = client.users.get_by_username(username=username)
        items = _data_items(response)
        if not items:
            raise ValueError(f"user_not_found:{username}")
        user_id = _value(items[0], "id")
        if not user_id:
            raise ValueError(f"user_id_missing:{username}")
        return str(user_id)

    def _get_me_id(self, client: Any) -> str:
        response = client.users.get_me()
        items = _data_items(response)
        if not items:
            raise ValueError("authenticated_user_not_found")
        user_id = _value(items[0], "id")
        if not user_id:
            raise ValueError("authenticated_user_id_missing")
        return str(user_id)
