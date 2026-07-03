# x-ray

Read-only X data MCP server for Hermes Agent.

This project will provide a small, task-oriented MCP interface for collecting
data from X. The server should encapsulate credentials, provider selection,
rate limits, fallback behavior, and normalized result shapes so Hermes can ask
for X data without choosing or misusing a raw backend.

Hermes integration details and the recommended stdio wrapper setup live in
[docs/hermes-integration.md](/home/ubuntu/projects/x_mcp/docs/hermes-integration.md).

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

## Live Smoke Harness

This repo includes a small live smoke runner for provider and router checks.
It is read-only and prints compact summaries instead of raw payload dumps.

Examples:

```bash
x-data-smoke --env-file /home/ubuntu/.hermes/.env
```

```bash
python -m src.smoke --env-file /home/ubuntu/.hermes/.env --user @OpenAI --search-query 'from:OpenAI' --format json
```

Notes:

- `--env-file` is optional and only loads known X-provider credential keys into
  the current process.
- The harness currently focuses on `socialdata` plus router checks, with
  `syndication` and `official_x` status included for context.
- It is intended for live validation, not CI.

## Hermes Integration

Recommended Hermes stdio setup:

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

This wrapper is preferred because Hermes does not blindly forward the full
shell environment to stdio MCP subprocesses. The script loads the X-provider
credentials it needs from `~/.hermes/.env` and then starts `python3 -m src.server`.
