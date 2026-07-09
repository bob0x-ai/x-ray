# x-ray

Read-only X data MCP server for Hermes Agent.

This project will provide a small, task-oriented MCP interface for collecting
data from X. The server should encapsulate credentials, provider selection,
rate limits, fallback behavior, and normalized result shapes so Hermes can ask
for X data without choosing or misusing a raw backend.

Hermes integration details and the recommended stdio wrapper setup live in
[docs/hermes-integration.md](docs/hermes-integration.md).

Runtime behavior is configured through
[config/providers.yaml](config/providers.yaml).
Secrets stay in environment variables such as `SOCIALDATA_API_KEY`.

Initial scope:

- Search public X posts.
- Read posts for a given user.
- Read specific posts, threads, replies, and URLs.
- Return structured, provenance-aware data.

Out of scope:

- Posting.
- Commenting or replying.
- Following, liking, reposting, bookmarking, or any other account mutation.
- Exposing raw provider credentials or raw provider tools to the agent.

## Providers

This README only covers the providers that are actually implemented in this
repo. The deeper design notes, tradeoffs, and rejected options remain in
[docs/architecture.md](docs/architecture.md).

### Syndication

X's public embed/syndication endpoints are the simplest provider in the stack.
They are best for exact post URLs/IDs and shallow recent reads for one public
account.

Cost:

- Free

### SocialData.tools

SocialData.tools is the main hosted read API in this project. It covers search,
recent user posts, exact post lookup, threads, replies, quotes, follow graph,
and bulk collection.

Cost:

- About `$0.20 / 1,000` tweets or user profiles
- Requires `SOCIALDATA_API_KEY`

### Official X API

The official X API is the paid, supported route. In this project it is mainly
used for owned-account reads, mentions, and as an official fallback when we
want supported endpoint behavior.

Cost:

- Paid
- Actual cost depends on your X developer plan and the endpoints you use

### Twikit

Twikit is the local scraper fallback. In this repo it is intentionally narrow:
cookie-based session reuse only, read-only wrapper only, and fallback-only
routing. The first implementation covers `search_posts` and
`read_user_posts_recent`.

This project uses the maintained `unclecode/twikit` fork as a drop-in
replacement for the original upstream package, because X's 2026 internal API
changes broke the upstream release train.

Cost:

- No API fee
- Requires an authenticated X session cookie file
- Operational cost is session maintenance rather than API credits

## Twikit Cookie Reuse

The Twikit provider needs a cookie file from an authenticated X session. An
unauthenticated browser session is not enough.

Recommended workflow:

1. Log in to X in a browser with a dedicated fallback account.
   Avoid using the real asset account for local scraping fallback.
2. Reuse that authenticated browser session to obtain the cookies.
   If you already have a Twikit-generated cookie file from `save_cookies()`,
   you can use that directly instead of exporting from the browser.
3. Save the richer browser export at a stable path such as
   `~/.hermes/x_browser_cookies.json`.
4. Derive the Twikit runtime file and expiry metadata from that export:

```bash
python3 scripts/bootstrap_twikit_cookies.py --force
```

   This writes:
   - `~/.hermes/x_cookies.json` for Twikit runtime use
   - `~/.hermes/x_cookies.meta.json` for expiry warnings and status output

   If you want a different runtime location, change
   `providers.twikit.cookies_file` in [config/providers.yaml](config/providers.yaml).
5. Enable Twikit in
   [config/providers.yaml](config/providers.yaml):

```yaml
providers:
  twikit:
    enabled: true
    cookies_file: "~/.hermes/x_cookies.json"
```

6. Keep Twikit as a fallback, not a default route.
   The default config already treats it this way.
7. Re-run the smoke harness after updating the cookie:

```bash
x-data-smoke --env-file /home/ubuntu/.hermes/.env
```

Notes:

- This repo does not automate Twikit login in v1.
- If X logs that browser session out, challenges the account, or rotates the
  auth state, refresh the cookie file.
- The browser export is the source of truth; `x_cookies.json` is a derived
  runtime file for Twikit.
- The most reliable cookie file is one that Twikit itself saved earlier, but an
  existing authenticated browser session is a practical way to bootstrap that
  file and keep expiry metadata.

## Live Smoke Harness

This repo includes a small live smoke runner for provider and router checks.
It is read-only and prints compact summaries instead of raw payload dumps.

## MCP Diagnostics

The MCP server exposes two diagnostic tools:

- `x_data_status`: cheap, token-safe static status for providers, routes, and
  task coverage
- `x_data_healthcheck`: active diagnostics with `basic`, `live`, or `deep`
  probe depth

By default both tools return a compact doctor-style `summary` that is easier
for agents to act on. Pass `detail="detailed"` when you want the full raw
provider and route reports.

Use `x_data_status` for routine checks and `x_data_healthcheck` when you want
to verify credentials, cookie validity, and small live reads end to end.

Examples:

```bash
x-data-smoke --env-file ~/.hermes/.env
```

```bash
python -m src.smoke --env-file ~/.hermes/.env --user @OpenAI --search-query 'from:OpenAI' --format json
```

Notes:

- `--env-file` is optional and only loads known X-provider credential keys into
  the current process.
- Smoke defaults come from `config/providers.yaml` and can be overridden by CLI
  flags.
- The harness currently focuses on `socialdata` plus router checks, with
  `syndication` and `official_x` status included for context.
- It is intended for live validation, not CI.

## Config

Behavior tuning lives in `config/providers.yaml`.

Current config surface:

- server limits: `default_limit`, `max_limit`, `max_fetch_urls`,
  `max_collect_limit`
- provider enable/disable flags
- provider cooldown and local rate-limiter settings
- route order per task
- default smoke inputs

Override the config path with:

```bash
X_MCP_CONFIG_FILE=/abs/path/to/providers.yaml
```

## Hermes Integration

Recommended Hermes stdio setup:

```yaml
mcp_servers:
  x-data:
    command: "/bin/bash"
    args: ["/absolute/path/to/x-ray/scripts/x-data-mcp-hermes.sh"]
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

This wrapper is preferred because Hermes does not blindly forward the full
shell environment to stdio MCP subprocesses. The script loads the X-provider
credentials it needs from `~/.hermes/.env` and then starts `python3 -m src.server`.
