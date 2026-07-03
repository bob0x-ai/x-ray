# Hermes Integration

This project is intended to run as a local stdio MCP server under Hermes.

## Why a wrapper script

Hermes stdio MCP servers do not inherit your full shell environment by default.
Per the local Hermes docs, only explicitly configured `env` plus a safe
baseline are passed to the subprocess.

To avoid duplicating secrets like `SOCIALDATA_API_KEY` into
`~/.hermes/config.yaml`, this repo includes a small wrapper script:

`/home/ubuntu/projects/x_mcp/scripts/x-data-mcp-hermes.sh`

The wrapper:

- loads a narrow allowlist of X-provider env vars from `~/.hermes/.env`
- changes into the repo root
- starts the MCP server with `python3 -m src.server`

## Recommended Hermes config

Add this under `mcp_servers` in `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  x-data:
    command: "/bin/bash"
    args:
      - "/home/ubuntu/projects/x_mcp/scripts/x-data-mcp-hermes.sh"
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

## Optional explicit env

If you prefer not to use the wrapper, Hermes also supports explicit stdio env
in config:

```yaml
mcp_servers:
  x-data:
    command: "python3"
    args: ["-m", "src.server"]
    env:
      SOCIALDATA_API_KEY: "..."
```

This is simpler, but it duplicates credentials into Hermes config. The wrapper
keeps credential sourcing in `~/.hermes/.env`.

## Validation

Local validation command:

```bash
python -m src.smoke --env-file /home/ubuntu/.hermes/.env
```

Installed script:

```bash
x-data-smoke --env-file /home/ubuntu/.hermes/.env
```
