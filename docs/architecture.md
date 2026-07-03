# X Data MCP Architecture

This document is the working architecture and option-analysis record for the
read-only X data MCP server in this repository.

It is based on:

- `/home/ubuntu/.hermes/neurosovereign/X-OPS.md`, which contains the fuller X
  operations research.
- Fresh verification on 2026-07-03 of public provider docs and project pages.

Do not treat older copied notes under `/home/ubuntu/projects/x-account/` as the
authoritative source for this project.

## Goal

Build a read-only MCP server for Hermes Agent that exposes a small set of
high-level X data tasks. Hermes should ask for data; the server should choose
the backend.

Hard constraints:

- No posting, replying, liking, reposting, following, bookmarking, DMs, or any
  account-mutating action.
- No raw provider tools exposed to Hermes.
- No model-visible provider selector in v1.
- Credentials are encapsulated and never returned, logged, or committed.
- Results are normalized across providers and include provider provenance,
  degradation, warnings, and cost signals.

## Current Local Context

### x-wing official API

`x-wing` is a Hermes skill that wraps the official X API through
`~/.hermes/skills/x-wing/scripts/x_client.py`. It is already working locally and
uses OAuth 2.0 User Context tokens from `~/.hermes/.env`.

Current role for this MCP project:

- Use as the safe paid fallback for official API reads.
- Best for owned-account data such as our timeline, mentions, followers,
  following, and exact official reads.
- Do not expose write commands through this MCP server.

Cost model, verified against current X docs:

- X API is pay-per-use with no subscription.
- Third-party post reads cost `$0.005` per post resource.
- User/follower/following reads cost `$0.010` per resource.
- Owned Reads cost `$0.001` per resource when the authenticated user owns the
  developer app and the request targets that user's own data.

#### Official X provider implementation decision

Do **not** implement the official route by shelling out to, importing, or
linking back to `~/.hermes/skills/x-wing/scripts/x_client.py`.

Reasoning:

- `x-wing` is a Hermes skill CLI, not a stable library API for this MCP server.
- It mixes read and write commands in one surface.
- Some command output is human-oriented text, not a clean provider contract.
- It can mutate token state by updating `~/.hermes/.env` during refresh.
- It lives outside this repository, so depending on its path would make this
  project depend on a profile-local skill layout.

Implementation direction:

- Build our own official-X provider module in this repository.
- Use the official Python XDK directly (`xdk`, installed and pinned by this
  project).
- Keep the provider strictly read-only.
- Reuse x-wing's credential naming for compatibility:
  - `X_OAUTH2_CLIENT_ID`
  - `X_OAUTH2_CLIENT_SECRET`
  - `X_OAUTH2_ACCESS_TOKEN`
  - `X_OAUTH2_REFRESH_TOKEN`
  - optional legacy aliases: `X_CLIENT_ID`, `X_CLIENT_SECRET`,
    `X_ACCESS_TOKEN`, `X_REFRESH_TOKEN`
- Reuse x-wing only as a reference for known-good endpoint behavior, OAuth
  lessons, token-refresh edge cases, and tests.

The provider module is named `official_x`. The x-wing skill remains only a
reference for local proof, credentials, endpoint behavior, and tests.

Implemented read coverage:

- Exact post URL/ID lookup through `posts.get_by_id`.
- Recent public posts for one user through `users.get_posts`.
- Owned timeline and mentions through authenticated user endpoints.
- Recent search through `posts.search_recent`.
- Thread and reply fallback through recent search using `conversation_id:<id>`
  and `conversation_id:<id> is:reply`. This is explicitly a recent-search
  fallback, not full historical thread reconstruction.
- Quote reads through `posts.get_quoted`.
- Followers/following reads through `users.get_followers` and
  `users.get_following`.

Do not use official X as the default bulk collection provider. Keep it as an
owned-account route or paid fallback when free/cheap providers fail or when
official fields are required.

### XActions + Camoufox

XActions + Camoufox is installed, but it failed during the prior setup attempt.
The fuller ops file records selector drift and delegated-auth visibility issues.
Treat it as **unproven** until we investigate it directly.

Current role for this MCP project:

- Do not rely on it in v1 routing.
- Keep it as an investigation candidate only.
- If it is revived, expose only read-only browser-backed reads through this MCP
  server; never expose its raw MCP surface because it includes mutating actions.

## Provider Options

### Syndication Endpoints

X's embed/syndication endpoints can fetch specific public tweets and recent
profile timelines without auth. They are cheap and useful for lookup-shaped
problems, but they are not a general data pipeline.

Use for:

- Exact tweet/post URL or ID lookup.
- Recent public posts for one handle when ~20 posts is enough.

Avoid for:

- Search.
- Full timeline/history.
- Replies, followers, or engagement graph collection.

#### Syndication provider implementation decision

Implement this provider with raw HTTP calls and our own small parser. Do **not**
add a wrapper dependency for v1.

Wrappers found during evaluation:

- `Owen3H/twittxr`: a small Node.js wrapper around the X/Twitter syndication
  endpoints. It is useful as a reference, but it would add a Node dependency
  for a tiny HTTP surface.
- `vercel/react-tweet`: a React/Next ecosystem library for rendering embedded
  tweets. It uses the same general syndication idea, but it is UI-oriented and
  not a Python data-provider dependency.

Raw endpoints:

- Single post lookup:
  - `GET https://cdn.syndication.twimg.com/tweet-result?id=<POST_ID>&token=a`
  - Returns JSON for a public post when available.
- Recent public profile timeline:
  - `GET https://syndication.twitter.com/srv/timeline-profile/screen-name/<HANDLE>`
  - Returns an HTML widget document containing embedded tweet data.
  - Some older notes use `screen-name=<HANDLE>`; implementation should support
    the slash form first and keep the exact URL in one constant for easy
    correction.

Provider responsibilities:

- Extract post IDs from `x.com`, `twitter.com`, and `mobile.twitter.com` status
  URLs.
- Normalize handles by stripping leading `@`.
- Use a short timeout and a conservative user-agent.
- Return `unavailable` for HTTP 403/404 on unavailable, protected, deleted, or
  age-restricted content rather than treating that as a fatal router error.
- Return `empty` when the timeline endpoint is reachable but no posts can be
  parsed.
- Return `error` only for unexpected transport/parsing failures.
- Parse only fields needed by the common result contract: id, text, author,
  created_at, public metrics if present, media/entities if present, and source
  URL.
- Save no credentials; this provider is unauthenticated.

Limitations:

- No search.
- No pagination.
- No home timeline.
- No follower/following graph.
- No reliable replies/quotes/reaction enumeration.
- Unofficial endpoint; it exists for embeds and can change without notice.

Recommended module name: `providers/syndication.py`.

### XPOZ

XPOZ is an AI/MCP-oriented social data provider. The older ops research scored
it highest and described a 100K/month free tier. Current public XPOZ pricing no
longer matches that: it advertises **2,500 free credits**, Pro at `$20/mo` for
30K credits, and Max at `$200/mo` for 600K credits.

Use for:

- MCP-friendly read/search workflows if the current credit model fits.
- Natural-language social intelligence if we want a hosted AI-agent interface.

Caveat:

- Re-evaluate pricing before adoption. The 100K free-tier claim is stale.

### SocialData.tools

SocialData.tools is a separate API provider for X data. Current public docs
advertise usage-based pricing at about `$0.20 / 1,000` tweets or user profiles,
with API endpoints for search, user timelines, tweet details, user profiles,
followers/following, and related public data.

Use for:

- Cheap hosted API reads when we want REST-style integration.
- Search and user timeline reads without maintaining local scraper accounts.
- Thread, replies, quotes, and follow-graph reads through documented REST
  endpoints.

Caveat:

- It is paid usage-based, not the same thing as XPOZ's MCP-style product.
- Several useful endpoints are marked "Limited Access" in the public docs.
- Requires `Authorization: Bearer <API_KEY>` on every request.
- Runtime env var for this project: `SOCIALDATA_API_KEY`

### Twikit

Twikit is a Python library that uses X's internal/web APIs and scraping. It can
search tweets and perform many account actions without an official API key.
For this project, only read-only methods are relevant.

Use for:

- Local free search and profile scraping.
- Experiments where we can tolerate breakage and use throwaway accounts.
- A cautious single-account fallback when hosted providers are unavailable and
  we deliberately accept lower reliability.

Avoid for:

- Running as the real asset account.
- Any mutating action.

Implementation notes if we add it later:

- Treat Twikit as a fragile fallback, not a default path.
- Keep the wrapper strictly read-only even though the library supports many
  mutating operations.
- Prefer cookie/session reuse over repeated login flows.
- Use low concurrency, small page sizes, randomized delay/jitter, and explicit
  backoff after rate-limit-like or suspicious empty responses.
- If Twikit appears throttled, soft-blocked, or auth-broken, the provider
  should quickly return `unavailable` and let the router move on.
- Expose token-safe health/status fields such as `session_present`,
  `cooldown_active`, `last_rate_limit`, or `last_soft_failure` rather than
  hiding the failure mode completely.

### twscrape

twscrape is an async Python library/CLI for X search and GraphQL endpoints. It
keeps sessions in SQLite and rotates across an account pool when endpoints hit
rate limits.

Use for:

- Sustained local scraping when Twikit's single-account model hits limits.
- Search/profile/follower collection where local operation matters.

Caveat:

- More setup than Twikit and still depends on account/session health.

### Apify

Apify provides hosted scraping actors. The older ops note focused on
`apidojo/tweet-scraper`; current Apify listing shows `apidojo/tweet-scraper`
at about `$0.40 / 1,000` tweets, while other actors can be cheaper.

Use for:

- Bulk/historical datasets.
- Reply graph mining, competitor research, or follower/audience mapping when
  free/local paths are insufficient.

Caveat:

- Paid and variable-cost. Use only with explicit per-run budget caps.

### Sorsa

Sorsa is a hosted read-only X API. Current pricing starts at `$49/mo` for 10K
requests/month, with all endpoints included and a 20 req/sec rate limit. It can
be cost-effective at larger read volumes because one request can return many
items.

Use for:

- Predictable flat-price production reads once volume justifies a subscription.

Avoid for now:

- Our current budget and early-stage research needs.

### twitter-api-client

`trevorhobenshield/twitter-api-client` is an implementation of X/Twitter v1,
v2, and GraphQL APIs. It is a possible backup for local scraping/internal API
work, but Twikit and twscrape are stronger first choices for our use case.

### twint-fork

Twint-style tooling is no longer a good bet. The fuller ops research recorded a
local install failure involving `cchardet`, and public Python discussions show
similar wheel-build failures on modern Python.

Decision: skip unless the dependency/maintenance situation changes.

### Web Search Engines

Search engines can occasionally find indexed public X pages via `site:x.com` or
`site:twitter.com` queries. This is a last resort and not a pipeline.

## Task Option Score Matrix

Scores are 1-10 and combine expected cost efficiency plus reliability for this
specific task. A higher score means a better default for the MCP router.

Legend:

- `10`: best available default for the task.
- `8-9`: strong, with minor caveats.
- `6-7`: usable, but cost, reliability, or setup caveats matter.
- `4-5`: possible, but not a good default.
- `1-3`: poor fit.
- `TBD`: do not route here until we investigate locally.

Column key:

- `URL`: exact post URL/ID
- `Recent`: recent posts by one user
- `Hist`: historical posts by one user
- `Search`: topic or advanced search
- `Thread`: thread/conversation
- `React`: replies, quotes, and reactions
- `Owned`: owned timeline/mentions
- `Graph`: followers/following
- `Bulk`: monitoring/datasets

| Option | URL | Recent | Hist | Search | Thread | React | Owned | Graph | Bulk |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Syndication endpoints | 9 | 7 | 2 | 1 | 3 | 2 | 1 | 1 | 2 |
| XPOZ | 8 | 8 | 7 | 8 | 7 | 7 | 5 | 7 | 5 |
| SocialData.tools | 8 | 8 | 8 | 8 | 7 | 8 | 5 | 8 | 7 |
| Twikit | 8 | 9 | 8 | 8 | 8 | 7 | 4 | 7 | 5 |
| twscrape | 8 | 9 | 8 | 8 | 8 | 6 | 4 | 8 | 7 |
| x-wing official API | 9 | 8 | 7 | 5 | 7 | 8 | 10 | 9 | 4 |
| Sorsa | 8 | 8 | 8 | 8 | 7 | 8 | 5 | 8 | 7 |
| Apify | 8 | 8 | 9 | 8 | 8 | 8 | 4 | 8 | 8 |
| twitter-api-client | 7 | 8 | 7 | 7 | 7 | 6 | 4 | 7 | 5 |
| twint-fork | 4 | 4 | 4 | 4 | 3 | 3 | 2 | 3 | 2 |
| Web search engines | 3 | 3 | 2 | 3 | 1 | 1 | 1 | 1 | 1 |
| XActions + Camoufox | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## Provider Module And Router Design

Each provider should be implemented as an encapsulated module behind a common
interface. Providers that are planned but not implemented yet should still have
stubs, but stubs must return an explicit normalized status rather than a plain
empty result.

Recommended provider modules:

- `syndication`
- `official_x`
- `socialdata`
- `xpoz`
- `twikit`
- `twscrape`
- `apify`
- `xactions`

Provider calls should return a normalized result object:

- `status`: `ok`, `empty`, `unavailable`, `error`, or `needs_approval`
- `items`: normalized result items
- `provider`: provider identifier
- `reason`: machine-readable reason such as `not_implemented`,
  `not_configured`, `no_results`, `rate_limited`, or `budget_required`
- `warnings`: human-readable caveats
- `cost`: estimated cost for the call, if known
- `raw_ref`: optional pointer to saved raw output, not raw data inline by
  default

Status semantics:

- `ok`: provider succeeded and returned usable items.
- `empty`: provider ran successfully but found no data.
- `unavailable`: provider is not implemented, not configured, disabled, or
  missing credentials.
- `error`: provider attempted the call and failed unexpectedly.
- `needs_approval`: provider could continue only by spending money, exceeding a
  configured limit, or using a riskier backend.

Router behavior:

1. Each task has an ordered provider list derived from the routing rules below.
2. The router calls providers sequentially.
3. Return immediately on `status: ok` with non-empty `items`.
4. Continue on `empty`, `unavailable`, or `not_implemented`.
5. Stop and return `needs_approval` when the next useful route would exceed a
   budget/risk threshold.
6. Return a final normalized empty result with `providers_attempted` when all
   routes are exhausted.

Example route table shape:

```python
ROUTES = {
    "fetch_urls": ["syndication", "official_x", "socialdata", "apify"],
    "read_user_posts_recent": [
        "syndication",
        "twikit",
        "twscrape",
        "socialdata",
        "xpoz",
        "apify",
    ],
    "search_posts": ["socialdata", "xpoz", "twikit", "twscrape", "apify"],
    "read_owned_timeline": ["official_x"],
}
```

This gives us incremental implementation without changing the public MCP tool
surface. The agent sees task-level tools; the code owns backend choice.

Implemented starting point:

- Shared contracts: `src/contracts.py`
- Router: `src/router.py`
- Stub provider: `src/providers/stub.py`
- Real providers: `src/providers/syndication.py`,
  `src/providers/official_x.py`, and `src/providers/socialdata.py`
- MCP wrapper: `src/server.py`

## MCP Server Wrapper

The MCP wrapper is intentionally thin. It exposes task-level tools and delegates
all provider choice to `XDataRouter`.

Tools:

- `x_fetch_urls(values: list[str])`
- `x_read_user_posts(user: str, limit: int = 20)`
- `x_search_posts(query: str, limit: int = 20)`
- `x_read_owned_timeline(limit: int = 20)`
- `x_read_mentions(limit: int = 20)`
- `x_read_thread(value: str, limit: int = 100)`
- `x_read_replies(value: str, limit: int = 100)`
- `x_read_quotes(value: str, limit: int = 100)`
- `x_read_follow_graph(user: str, graph: str = "followers", limit: int = 100)`
- `x_collect_posts(query: str, limit: int = 100)`
- `x_data_status()`

Tool constraints:

- No tool accepts a provider parameter.
- `limit` defaults to `20` and clamps to `1..100`.
- `x_fetch_urls` accepts at most `25` values per call in v1.
- `x_collect_posts` clamps to `1..500`.
- Tool handlers return normalized JSON-serializable provider results.
- `x_data_status` reports only token-safe booleans and provider status.
- A stdio MCP integration test verifies tool listing, absence of provider
  parameters, and `x_data_status` structured content.

Local entry point:

```bash
python -m src.server
```

Installed console script:

```bash
x-data-mcp
```

Expected Hermes stdio config shape:

```yaml
mcp_servers:
  x-data:
    command: "/bin/bash"
    args: ["/home/ubuntu/projects/x_mcp/scripts/x-data-mcp-hermes.sh"]
    tools:
      include:
        - x_fetch_urls
        - x_read_user_posts
        - x_search_posts
        - x_read_owned_timeline
        - x_read_mentions
        - x_read_thread
        - x_read_replies
        - x_read_quotes
        - x_read_follow_graph
        - x_collect_posts
        - x_data_status
```

Recommended integration note:

- Hermes stdio MCP subprocesses do not inherit the full shell environment by
  default.
- Use the wrapper script to load only the small allowlist of X-provider env
  vars from `~/.hermes/.env` before starting `python3 -m src.server`.
- Full operator-facing setup notes live in
  [docs/hermes-integration.md](/home/ubuntu/projects/x_mcp/docs/hermes-integration.md).

Use-case coverage:

| Matrix axis | MCP tool | Current provider status |
|---|---|---|
| `URL` | `x_fetch_urls` | `syndication`, `official_x`, `socialdata` |
| `Recent` | `x_read_user_posts` | `syndication`, `socialdata`, `official_x` fallback |
| `Hist` | Deferred | Ignored for now |
| `Search` | `x_search_posts` | `socialdata`, `official_x` recent fallback |
| `Thread` | `x_read_thread` | `socialdata`, `official_x` recent-search fallback |
| `React` replies | `x_read_replies` | `socialdata`, `official_x` recent-search fallback |
| `React` quotes | `x_read_quotes` | `socialdata`, `official_x` quote endpoint fallback |
| `Owned` | `x_read_owned_timeline`, `x_read_mentions` | `official_x` |
| `Graph` | `x_read_follow_graph` | `socialdata`, `official_x` followers/following fallback |
| `Bulk` | `x_collect_posts` | `socialdata` |

## Operator Note

This server should remain useful in both paid and free configurations.

- Paid path today: `socialdata` for most public reads, `official_x` for
  owned-account reads and official paid fallback.
- Free path today: `syndication` for exact URL lookups and shallow recent user
  reads, with the rest returning `empty` only after all configured providers
  are exhausted.
- Future local scrapers such as Twikit should be optional fallbacks, not
  required for basic server operation.
- A missing credential should normally make the provider return `unavailable`,
  not `empty`, so the router can skip it truthfully and continue to the next
  option.

## Provisional Routing Rules

These are recommendations for design discussion, not yet implementation.

### Exact post URL/ID

1. Syndication endpoint.
2. x-wing official API if the post is unavailable through syndication or if we
   need official fields.
3. SocialData/XPOZ/Apify only if hosted fallback is already configured.

### Recent posts by one public user

1. SocialData when hosted API reads are available and we want the default path
   to be reliable, structured, and simple for the agent.
2. Syndication timeline for exact free shallow reads when ~20 recent posts is
   enough.
3. Twikit or twscrape for deeper local scraping.
4. Apify for larger research pulls.

### Historical posts by one user

1. SocialData or Apify for hosted structured reads.
2. Twikit/twscrape if we want local free scraping and accept account/session
   risk.
3. x-wing only when official cost/coverage is acceptable.

### Topic or advanced search

1. SocialData/XPOZ if configured and within budget/credits.
2. Twikit for local free search.
3. twscrape for sustained local search with account rotation.
4. Apify when the dataset is large or historical.
5. Web search only as a manual/ad-hoc last resort.

### Thread/conversation

1. Twikit/twscrape for local reconstruction.
2. SocialData/Apify for hosted structured collection.
3. x-wing if official API fields and costs fit.

### Replies, quotes, reactions

1. SocialData/Sorsa/Apify for hosted graph-style collection.
2. x-wing for our own mentions/reactions where official API reliability matters.
3. Twikit/twscrape for local scraping, with account-risk caveats.

### Owned timeline, mentions, followers, following

1. x-wing official API.
2. No local scraper should run as the real asset account.
3. Hosted public-data APIs can be used only when official API cost is unjustified
   and the data does not require privileged account context.

### Bulk monitoring or datasets

1. twscrape if local account-pool scraping is acceptable and volume is moderate.
2. SocialData/Sorsa if hosted API economics fit.
3. Apify when we need a managed scraping actor, historical data, or >local
   scraper reliability.
4. XPOZ only if its current credit plan fits the desired volume.

## Adoption Sequence

1. Keep x-wing for owned-account reads and paid official fallback.
2. Add syndication endpoints first because they are simple, free, and reliable
   for exact public lookups.
3. Choose one hosted read API candidate for v1 evaluation: SocialData.tools or
   XPOZ. SocialData currently looks clearer for REST-style implementation;
   XPOZ looks more MCP/agent-oriented but its free-tier claim changed.
4. Add Twikit only if we want local free search and can create throwaway X
   accounts for scraping sessions.
5. Add twscrape only if Twikit hits sustained-volume limits.
6. Keep Apify as the bulk/historical escape valve with per-run budget caps.
7. Do not use XActions + Camoufox until a local investigation proves it works.
8. Skip twint-fork.

## Open Questions

- Should v1 include any hosted provider, or should v1 start with syndication +
  x-wing fallback only?
- If we include one hosted provider, should it be SocialData.tools or XPOZ?
- Do we want local scraper accounts for Twikit/twscrape, or should this server
  avoid account-cookie scraping entirely?
- What budget limit should trigger `needs_paid_backend` instead of automatic
  fallback?
- Where should cache data live: project-local `data/cache`, Hermes profile
  state, or configurable path?
- Should XActions + Camoufox be investigated before or after the first MCP
  server skeleton exists?

## Source Notes

- X API pricing and Owned Reads: current X Developer Platform pricing docs.
- XPOZ: current public pricing says 2,500 free credits, not the older 100K free
  results claim.
- SocialData.tools: current pricing says `$0.0002` per tweet/user profile,
  roughly `$0.20 / 1,000` items.
- Sorsa: current pricing starts at `$49/mo` for 10K requests/month.
- Apify `apidojo/tweet-scraper`: current listing says from `$0.40 / 1,000`
  tweets; cheaper actors may exist.
- Twikit and twscrape: current GitHub project pages confirm the advertised
  capabilities and local-scraper nature.
