"""The MCP server instance and the seam triage tools register on.

This module owns the singleton :data:`mcp` server that ``@mcp.tool()``
decorators attach to, plus a small holder for the authenticated GitHub client
so tools can reach the client the entrypoint built at boot. Subsequent slices
(e.g. the ``list_issues`` tool) extend this module by registering tools on
:data:`mcp` and reading the client via :func:`github_client`.
"""

import httpx
from mcp.server.fastmcp import FastMCP

from .github_client import MissingGitHubTokenError, build_github_client

__all__ = [
    "mcp",
    "attach_github_client",
    "github_client",
    "MissingGitHubTokenError",
    "build_github_client",
]

mcp = FastMCP("github-issue-triage")

_github_client: httpx.Client | None = None


def attach_github_client(client: httpx.Client) -> None:
    """Attach the authenticated client the entrypoint built at boot."""
    global _github_client
    _github_client = client


def github_client() -> httpx.Client:
    """Return the attached GitHub client for tools to use.

    Raises if the server was not booted through the production entrypoint,
    which is the only path that attaches an authenticated client.
    """
    if _github_client is None:
        raise RuntimeError(
            "GitHub client has not been attached; boot the server via "
            "`python -m github_issue_triage_mcp`."
        )
    return _github_client
