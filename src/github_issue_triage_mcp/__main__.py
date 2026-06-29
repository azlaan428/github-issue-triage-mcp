"""Production entrypoint: ``python -m github_issue_triage_mcp``.

Builds the authenticated GitHub client from ``GITHUB_TOKEN`` (failing fast if it
is missing), attaches it to the server, and boots the MCP server over stdio.
"""

from .github_client import build_github_client
from .server import attach_github_client, mcp


def main() -> None:
    """Boot the stdio MCP server with an authenticated GitHub client.

    Raises :class:`~github_issue_triage_mcp.github_client.MissingGitHubTokenError`
    before the server starts when ``GITHUB_TOKEN`` is unset or blank, so an
    unauthenticated server is never started.
    """
    # Build the client first so a missing token aborts boot before mcp.run().
    attach_github_client(build_github_client())
    mcp.run()


if __name__ == "__main__":
    main()
