# x-ray

Read-only X data MCP server for Hermes Agent.

This project will provide a small, task-oriented MCP interface for collecting
data from X. The server should encapsulate credentials, provider selection,
rate limits, fallback behavior, and normalized result shapes so Hermes can ask
for X data without choosing or misusing a raw backend.

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
