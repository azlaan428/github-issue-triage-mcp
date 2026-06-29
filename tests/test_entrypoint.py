"""Tests for the production entrypoint (`python -m github_issue_triage_mcp`).

`main` is the real composition root: it builds the authenticated client from
the environment and boots the stdio MCP server. We stub only the boundary
(`mcp.run`, which would otherwise block on stdio) — never the factory under
test — so these prove the boot wiring, not a mock of it.
"""

import httpx
import pytest

from github_issue_triage_mcp import __main__ as entrypoint
from github_issue_triage_mcp import server


def test_main_boots_server_with_authenticated_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret123")

    ran: list[bool] = []
    monkeypatch.setattr(server.mcp, "run", lambda: ran.append(True))

    entrypoint.main()

    # The server was booted...
    assert ran == [True]
    # ...with a real authenticated client attached for tools to use.
    client = server.github_client()
    assert isinstance(client, httpx.Client)
    assert client.headers["Authorization"] == "Bearer ghp_secret123"
    client.close()


def test_main_fails_fast_without_token_and_does_not_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    ran: list[bool] = []
    monkeypatch.setattr(server.mcp, "run", lambda: ran.append(True))

    with pytest.raises(server.MissingGitHubTokenError):
        entrypoint.main()

    # Fail-fast: the unauthenticated server must never have been started.
    assert ran == []
