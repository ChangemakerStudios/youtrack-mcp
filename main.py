#!/usr/bin/env python3
"""
YouTrack MCP Server - A Model Context Protocol server for JetBrains YouTrack.
Uses FastMCP directly for stdio, SSE, and streamable HTTP transports.
"""
import functools
import inspect
import json
import logging
import os
import stat
import sys

from mcp.server.fastmcp import FastMCP

from youtrack_mcp.version import __version__ as APP_VERSION
from youtrack_mcp.config import config
from youtrack_mcp.tools.loader import load_all_tools

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# FastMCP 1.x names the remote HTTP transport "streamable-http".
# Accept "http" as an alias so the npm --http flag keeps working.
_HTTP_TRANSPORTS = {"http", "streamable-http"}


def _flatten_result(result):
    """Collapse JSON-string returns and MCP resource envelopes into plain objects.

    Tools historically return JSON *strings*, which FastMCP wraps as
    {"result": "<escaped json>"} — clients end up with double/triple-encoded
    output. Parsing here (and unwrapping {"contents":[{"text": ...}]} resource
    envelopes) lets FastMCP serialize the object exactly once.
    """
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except (ValueError, TypeError):
            return {"text": result}
        if isinstance(parsed, (dict, list)):
            return _flatten_result(parsed)
        return {"result": parsed}
    if isinstance(result, dict):
        contents = result.get("contents")
        if (
            set(result.keys()) == {"contents"}
            and isinstance(contents, list)
            and len(contents) == 1
            and isinstance(contents[0], dict)
            and "text" in contents[0]
        ):
            return _flatten_result(contents[0]["text"])
        return result
    if isinstance(result, list):
        return {"items": result, "count": len(result)}
    return {"result": result}


def _clean_tool(func):
    """Wrap a tool so it returns a parsed dict instead of a JSON string."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return _flatten_result(func(*args, **kwargs))

    sig = inspect.signature(func)
    wrapper.__signature__ = sig.replace(return_annotation=dict)
    return wrapper


def create_server(host: str = "0.0.0.0", port: int = 8000) -> FastMCP:
    """Create and configure the FastMCP server with all tools registered."""
    mcp = FastMCP(
        config.MCP_SERVER_NAME,
        instructions=config.MCP_SERVER_DESCRIPTION,
        host=host,
        port=port,
    )

    # Load and register all tools
    tools = load_all_tools()
    for name, func in tools.items():
        mcp.add_tool(_clean_tool(func), name=name)

    logger.info(f"Registered {len(tools)} tools with FastMCP")
    return mcp


def _normalize_transport(transport: str) -> str:
    if transport in _HTTP_TRANSPORTS:
        return "streamable-http"
    return transport


def _stdin_is_mcp_client() -> bool:
    """True when stdin is a pipe/socket from an MCP host (docker -i, Claude, Cursor)."""
    try:
        mode = os.fstat(sys.stdin.fileno()).st_mode
    except OSError:
        return False
    return stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode)


def _should_fallback_to_http() -> bool:
    """True when stdio would just EOF (Compose, docker without -i), not a TTY or pipe."""
    if _stdin_is_mcp_client():
        return False
    try:
        return not sys.stdin.isatty()
    except (OSError, ValueError):
        return True


def main():
    """Run the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="YouTrack MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http", "http"],
        default=None,
        help="Transport mode (default: from TRANSPORT env var, fallback stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE / streamable HTTP")
    parser.add_argument("--port", type=int, default=None, help="Port for SSE / streamable HTTP")
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    args = parser.parse_args()

    if args.version:
        print(f"YouTrack MCP Server v{APP_VERSION}")
        sys.exit(0)

    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Determine transport: CLI arg > env var > default stdio
    transport = _normalize_transport(args.transport or os.getenv("TRANSPORT", "stdio"))
    port = args.port or int(os.getenv("PORT", "8000"))

    # Docker Compose (no stdin) looks like a crash: stdio starts, then EOF exits.
    # Switch to streamable HTTP so a long-running service actually stays up.
    # Explicit --transport stdio skips this (Dockerfile ENV TRANSPORT=stdio does not).
    if (
        transport == "stdio"
        and args.transport != "stdio"
        and _should_fallback_to_http()
    ):
        logger.warning(
            "No MCP client on stdin (typical of docker compose without -i). "
            "Switching to streamable-http on 0.0.0.0:%s. "
            "Pass --transport stdio to keep stdio, or set TRANSPORT=streamable-http "
            "and publish port %s.",
            port,
            port,
        )
        transport = "streamable-http"

    logger.info(f"Starting YouTrack MCP Server v{APP_VERSION} [{transport}]")

    mcp = create_server(host=args.host, port=port)
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
