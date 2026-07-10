# Read-Only X Data Stack For Hermes

This repository contains a read-only X data MCP server for Hermes Agent.

The design goal is to make X data collection unambiguous and difficult for an
agent to misuse. Hermes should choose the data task, not the backend. Provider
selection, credentials, limits, retries, fallback behavior, and result
normalization belong inside this server.

## Summary

Build a single read-only X MCP server that exposes task-level tools, not
provider-level tools. The MCP server owns provider selection, credentials,
limits, retries, result normalization, and provenance. Hermes sees only a
small, unambiguous X data interface.

Use a Hermes plugin only later as the packaging/config layer: enable the MCP,
collect credentials, ship a skill, expose status/doctor commands, and hide raw
provider details from the agent. The first implementation step is the MCP
server itself.

## Recommended Architecture

- Create an MCP server named `x-data`.
- Follow the provider-module and router design in
  `docs/architecture.md#provider-module-and-router-design`.
- Expose only read-only task-level tools:
  - `x_fetch_urls`
  - `x_read_user_posts`
  - `x_search_posts`
  - `x_read_owned_timeline`
  - `x_read_mentions`
  - `x_read_thread`
  - `x_read_replies`
  - `x_read_quotes`
  - `x_read_follow_graph`
  - `x_collect_posts`
  - `x_data_status`
  - `x_data_healthcheck`
- Do not expose posting, liking, following, replying, browser navigation, or
  raw provider tools.
- Do not expose a `provider` parameter to the model. Provider choice is
  internal policy.
- Every result returns:
  - normalized posts/users/metrics
  - `provider_used`
  - `confidence`
  - `partial` or `degraded` flags
  - cost estimate where applicable
  - source URLs or IDs

## Provider Policy

Use a deterministic router with encapsulated provider modules:

- Providers are modules behind a common interface.
- Providers that are not implemented yet must return an explicit normalized
  `unavailable` / `not_implemented` status rather than pretending to have run.
- Each task owns an ordered provider list.
- The router calls providers sequentially and returns the first successful
  non-empty result.
- The router must distinguish `empty`, `unavailable`, `error`, and
  `needs_approval`.
- Provider routing details belong in code and `docs/architecture.md`, not in
  model-visible tool parameters.

Router examples:

- Exact post URL/ID -> syndication first, then x-wing or hosted fallback.
- Recent public user posts -> syndication for shallow reads, then scraper/API
  providers.
- Search -> hosted API or local scraper providers, then paid bulk fallback.
- Owned timeline/mentions -> x-wing official API.
- XActions + Camoufox -> investigation candidate only until proven locally.

## Official X Provider

- Do not shell out to, import, or link back to
  `~/.hermes/skills/x-wing/scripts/x_client.py`.
- Implement the official X route as a provider module in this repository using
  the official Python XDK directly.
- The x-wing skill is a reference for credentials, endpoint behavior, and tests;
  it is not this project's runtime dependency.
- Keep the official provider strictly read-only.
- Preserve compatibility with existing x-wing credential names where practical.

## Syndication Provider

- Implement syndication endpoints with raw HTTP calls and a small in-repo
  parser.
- Do not add Node/UI wrapper dependencies such as `twittxr` or `react-tweet`.
- The provider is unauthenticated and must never read credentials.
- Treat deleted, protected, age-restricted, or unavailable posts as
  `unavailable` or `empty`, not as fatal router failures.
- Keep endpoint URLs isolated in constants because these are unofficial embed
  endpoints and may drift.

## Hermes Integration

The eventual Hermes plugin should:

- Install and enable the MCP server.
- Declare required credentials via plugin/MCP config.
- Provide `hermes x-data status`.
- Provide `hermes x-data doctor`.
- Register a bundled skill that tells Hermes: "For X data collection, use only
  `mcp_x_data_*` tools."

Store credentials outside tool schemas:

- X `auth_token` / browser session for XActions.
- Apify token if enabled.
- xAI OAuth/API key through the existing Hermes xAI auth path.

Add MCP tool filtering so Hermes only sees the task-level router tools, never
raw provider tools.

## Guardrails

- Enforce read-only behavior: no write-capable provider calls, no browser
  actions that mutate X state.
- Add capability checks at startup and in `x_data_status`.
- Use cost guardrails:
  - default free/local first
  - require config approval above a per-call result or cost threshold
  - return `needs_paid_backend` instead of silently escalating to Apify for
    large jobs
- Rate-limit and failure handling:
  - provider-specific retry/backoff
  - fallback only when semantically equivalent
  - never invent missing data; return partial/degraded state
- Local cache:
  - cache by post ID, user handle, query hash, date window, and provider
  - short TTL for search/trends
  - longer TTL for immutable post/thread reads

## Why This Design

This should be MCP-first because the capability is structured external data
access and Hermes already treats MCP as the clean edge for external tools.

It should later have a Hermes plugin wrapper because installation, credentials,
status checks, and skill guidance are Hermes-specific. The plugin is not the
main runtime interface; it is the control plane.

The key design principle: the agent chooses the task, not the backend. Backend
choice belongs to code.
