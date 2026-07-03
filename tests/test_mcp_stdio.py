import sys
from pathlib import Path

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]


def test_mcp_stdio_lists_tools_and_calls_status():
    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "src.server"],
            cwd=str(ROOT),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                tools = {tool.name: tool for tool in tools_result.tools}

                assert set(tools) == {
                    "x_fetch_urls",
                    "x_read_user_posts",
                    "x_search_posts",
                    "x_read_owned_timeline",
                    "x_read_mentions",
                    "x_data_status",
                }
                for tool in tools.values():
                    properties = tool.inputSchema.get("properties", {})
                    assert "provider" not in properties

                status = await session.call_tool("x_data_status", {})

                assert status.isError is False
                assert status.structuredContent["status"] == "ok"
                assert status.structuredContent["server"] == "x-data"
                assert status.structuredContent["providers"]["syndication"]["implemented"] is True

    anyio.run(run)
