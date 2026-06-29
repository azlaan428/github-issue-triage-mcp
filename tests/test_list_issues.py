"""Tests for the `list_issues` MCP tool — the first Claude-facing capability.

These prove the whole path: the tool is registered on the PRODUCTION ``mcp``
server, calls the authenticated GitHub client attached at boot, and returns a
structured list of issues with pull requests excluded. Only the GitHub HTTP
boundary is mocked (via ``httpx.MockTransport``) — the real tool function, the
real ``github_client()`` lookup, and the real server registration all run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx
import pytest

from github_issue_triage_mcp import server


def _attach_mock_client(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    """Attach a real client whose only mock is the HTTP transport boundary."""
    client = httpx.Client(
        base_url="https://api.github.com",
        headers={"Authorization": "Bearer ghp_test"},
        transport=httpx.MockTransport(handler),
    )
    server.attach_github_client(client)


# A realistic /issues payload: GitHub returns PRs alongside issues, so the
# second item carries a ``pull_request`` field and must be filtered out.
_ISSUES_PAYLOAD = [
    {
        "number": 7,
        "title": "Server crashes on empty repo",
        "state": "open",
        "labels": [{"name": "bug"}, {"name": "p1"}],
        "assignee": {"login": "alice"},
        "html_url": "https://github.com/octocat/hello-world/issues/7",
    },
    {
        "number": 8,
        "title": "Add retry to client (this is a PR, not an issue)",
        "state": "open",
        "labels": [],
        "assignee": None,
        "html_url": "https://github.com/octocat/hello-world/pull/8",
        "pull_request": {"url": "https://api.github.com/.../pulls/8"},
    },
    {
        "number": 9,
        "title": "Docs are stale",
        "state": "open",
        "labels": [],
        "assignee": None,
        "html_url": "https://github.com/octocat/hello-world/issues/9",
    },
]


def test_list_issues_registered_on_production_server() -> None:
    """The tool must appear in the production server's tool list."""
    tools = asyncio.run(server.mcp.list_tools())
    names = [t.name for t in tools]
    assert "list_issues" in names


def test_list_issues_end_to_end_returns_parsed_issues_excluding_prs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["state"] = request.url.params.get("state", "")
        return httpx.Response(200, json=_ISSUES_PAYLOAD)

    _attach_mock_client(monkeypatch, handler)

    # Call the tool AS REGISTERED on the production server.
    _content, structured = asyncio.run(
        server.mcp.call_tool("list_issues", {"repo": "octocat/hello-world"})
    )

    # Hit the right endpoint with the default state filter.
    assert seen["path"] == "/repos/octocat/hello-world/issues"
    assert seen["state"] == "open"

    result = structured["result"]
    # The PR (number 8) is excluded; only the two real issues remain.
    assert [i["number"] for i in result] == [7, 9]

    first = result[0]
    assert first["number"] == 7
    assert first["title"] == "Server crashes on empty repo"
    assert first["state"] == "open"
    assert first["labels"] == ["bug", "p1"]
    assert first["assignee"] == "alice"
    assert first["url"] == "https://github.com/octocat/hello-world/issues/7"

    # An unassigned, unlabelled issue surfaces with empty/null fields.
    second = result[1]
    assert second["number"] == 9
    assert second["labels"] == []
    assert second["assignee"] is None


def test_list_issues_passes_through_state_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["state"] = request.url.params.get("state", "")
        return httpx.Response(200, json=[])

    _attach_mock_client(monkeypatch, handler)

    asyncio.run(
        server.mcp.call_tool(
            "list_issues", {"repo": "octocat/hello-world", "state": "closed"}
        )
    )
    assert seen["state"] == "closed"


def test_list_issues_surfaces_api_error_not_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 401 from GitHub must surface as a clear error, never a silent []."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Bad credentials"})

    _attach_mock_client(monkeypatch, handler)

    with pytest.raises(Exception) as excinfo:
        asyncio.run(
            server.mcp.call_tool("list_issues", {"repo": "octocat/hello-world"})
        )

    message = str(excinfo.value)
    assert "401" in message
    assert "octocat/hello-world" in message


def test_list_issues_function_called_directly_filters_prs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real tool function (not just via call_tool) excludes PRs."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_ISSUES_PAYLOAD)

    _attach_mock_client(monkeypatch, handler)

    issues = server.list_issues("octocat/hello-world")
    assert [i.number for i in issues] == [7, 9]
    assert all(i.url and "/pull/" not in i.url for i in issues)


def test_list_issues_rejects_malformed_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP must not be called for a malformed repo")

    _attach_mock_client(monkeypatch, handler)

    with pytest.raises(ValueError, match="owner/repo"):
        server.list_issues("not-a-valid-repo")
