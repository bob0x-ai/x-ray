from types import SimpleNamespace

from src.providers.official_x import OfficialXProvider


class _Users:
    def get_by_username(self, username):
        assert username == "alice"
        return SimpleNamespace(data={"id": "42", "username": "alice"})

    def get_posts(self, **kwargs):
        assert kwargs["id"] == "42"
        return [
            SimpleNamespace(
                data=[
                    {
                        "id": "1",
                        "text": "official one",
                        "author_id": "42",
                        "created_at": "2026-07-03T00:00:00Z",
                        "public_metrics": {"like_count": 1},
                    }
                ]
            )
        ]

    def get_me(self):
        return SimpleNamespace(data={"id": "99"})

    def get_timeline(self, **kwargs):
        assert kwargs["id"] == "99"
        return [SimpleNamespace(data=[{"id": "2", "text": "home", "author_id": "42"}])]

    def get_mentions(self, **kwargs):
        assert kwargs["id"] == "99"
        return [SimpleNamespace(data=[])]


class _Posts:
    def search_recent(self, **kwargs):
        assert kwargs["query"] == "ai"
        return [SimpleNamespace(data=[{"id": "3", "text": "search", "author_id": "42"}])]


class _Client:
    users = _Users()
    posts = _Posts()


def test_missing_auth_returns_unavailable(monkeypatch):
    monkeypatch.delenv("X_OAUTH2_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("X_ACCESS_TOKEN", raising=False)

    provider = OfficialXProvider(client_factory=lambda token: _Client())
    result = provider.fetch_urls(["1234567890"])

    assert result.status == "unavailable"
    assert result.reason == "auth_required"


def test_missing_sdk_returns_unavailable_when_no_factory(monkeypatch):
    monkeypatch.setenv("X_OAUTH2_ACCESS_TOKEN", "token")
    monkeypatch.setattr("src.providers.official_x._load_xdk_client_factory", lambda: None)

    result = OfficialXProvider().fetch_urls(["1234567890"])

    assert result.status == "unavailable"
    assert result.reason == "sdk_missing"


def test_read_user_posts_resolves_username_and_normalizes(monkeypatch):
    monkeypatch.setenv("X_OAUTH2_ACCESS_TOKEN", "token")
    provider = OfficialXProvider(client_factory=lambda token: _Client())

    result = provider.read_user_posts("@alice", limit=10)

    assert result.status == "ok"
    assert result.items[0].id == "1"
    assert result.items[0].metrics.likes == 1
    assert result.cost.amount_usd > 0


def test_owned_timeline_uses_owned_read_cost(monkeypatch):
    monkeypatch.setenv("X_OAUTH2_ACCESS_TOKEN", "token")
    provider = OfficialXProvider(client_factory=lambda token: _Client())

    result = provider.read_owned_timeline(limit=10)

    assert result.status == "ok"
    assert result.items[0].text == "home"
    assert result.cost.basis == "$0.001/owned read"


def test_search_recent(monkeypatch):
    monkeypatch.setenv("X_OAUTH2_ACCESS_TOKEN", "token")
    provider = OfficialXProvider(client_factory=lambda token: _Client())

    result = provider.search_recent("ai", limit=10)

    assert result.status == "ok"
    assert result.items[0].id == "3"


def test_official_provider_exposes_no_write_methods():
    provider = OfficialXProvider(client_factory=lambda token: _Client())

    forbidden = {"post", "delete", "like", "unlike", "repost", "follow", "unfollow", "dm_send"}

    assert forbidden.isdisjoint(set(dir(provider)))
