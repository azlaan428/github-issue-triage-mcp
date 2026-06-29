"""Tests for the ``classify_and_label_issue`` MCP tool — first state mutation.

These prove the whole path end-to-end: the tool is registered on the PRODUCTION
``mcp`` server, fetches the issue via the authenticated client, classifies it,
and POSTs the matching label back to GitHub. Only the GitHub HTTP boundary is
mocked (via ``httpx.MockTransport``) — the real tool function, the real
``classify_issue`` heuristic, the real ``github_client()`` lookup, and the real
``mcp.call_tool`` registration all run.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable

import httpx
import pytest

from github_issue_triage_mcp import server


def _attach_mock_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    """Attach a real client whose only mock is the HTTP transport boundary."""
    client = httpx.Client(
        base_url="https://api.github.com",
        headers={"Authorization": "Bearer ghp_test"},
        transport=httpx.MockTransport(handler),
    )
    server.attach_github_client(client)


def _issue_payload(title: str, body: str, number: int = 42) -> dict[str, object]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": "open",
        "html_url": f"https://github.com/octocat/hello-world/issues/{number}",
    }


def test_tool_registered_on_production_server() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    names = [t.name for t in tools]
    assert "classify_and_label_issue" in names


def test_end_to_end_labels_issue_with_classified_type() -> None:
    """A bug-shaped issue gets GET → classify → POST {"labels": ["bug"]}."""
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            seen["get_path"] = request.url.path
            return httpx.Response(
                200,
                json=_issue_payload(
                    "App crashes on launch",
                    "Throws an exception every time, clearly a bug.",
                ),
            )
        # POST to the labels endpoint
        seen["post_path"] = request.url.path
        seen["post_body"] = json.loads(request.content)
        return httpx.Response(200, json=[{"name": "bug"}])

    _attach_mock_client(handler)

    _content, structured = asyncio.run(
        server.mcp.call_tool(
            "classify_and_label_issue",
            {"repo": "octocat/hello-world", "issue_number": 42},
        )
    )

    assert seen["get_path"] == "/repos/octocat/hello-world/issues/42"
    assert seen["post_path"] == "/repos/octocat/hello-world/issues/42/labels"
    # The POST body must carry EXACTLY the classified label name.
    assert seen["post_body"] == {"labels": ["bug"]}

    # A BaseModel return serialises its fields directly into structured output.
    assert structured["issue_number"] == 42
    assert structured["label"] == "bug"


def test_end_to_end_feature_issue_posts_feature_label() -> None:
    """The label POSTed must match the classification, not a fixed default."""
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json=_issue_payload(
                    "Please add CSV export",
                    "It would be nice to support exporting reports to CSV.",
                ),
            )
        seen["post_body"] = json.loads(request.content)
        return httpx.Response(200, json=[{"name": "feature"}])

    _attach_mock_client(handler)

    _content, structured = asyncio.run(
        server.mcp.call_tool(
            "classify_and_label_issue",
            {"repo": "octocat/hello-world", "issue_number": 7},
        )
    )

    assert seen["post_body"] == {"labels": ["feature"]}
    assert structured["label"] == "feature"


def test_get_failure_raises_github_api_error_not_silent() -> None:
    """A 404 on the fetch surfaces as an error and never POSTs a label."""
    posted = {"called": False}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            posted["called"] = True  # pragma: no cover
        return httpx.Response(404, json={"message": "Not Found"})

    _attach_mock_client(handler)

    with pytest.raises(Exception) as excinfo:
        asyncio.run(
            server.mcp.call_tool(
                "classify_and_label_issue",
                {"repo": "octocat/hello-world", "issue_number": 99},
            )
        )

    message = str(excinfo.value)
    assert "404" in message
    assert "octocat/hello-world" in message
    assert posted["called"] is False


def test_label_post_failure_raises_github_api_error() -> None:
    """A 403 on the label POST surfaces as a GitHubAPIError, not a silent success."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200, json=_issue_payload("How do I use this?", "Just a question.")
            )
        return httpx.Response(403, json={"message": "Forbidden"})

    _attach_mock_client(handler)

    with pytest.raises(server.GitHubAPIError) as excinfo:
        server.classify_and_label_issue("octocat/hello-world", 5)

    assert "403" in str(excinfo.value)


def test_malformed_repo_raises_value_error_without_http() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("HTTP must not be called for a malformed repo")

    _attach_mock_client(handler)

    with pytest.raises(ValueError, match="owner/repo"):
        server.classify_and_label_issue("not-a-valid-repo", 1)
