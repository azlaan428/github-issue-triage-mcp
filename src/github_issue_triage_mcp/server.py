"""The MCP server instance and the seam triage tools register on.

This module owns the singleton :data:`mcp` server that ``@mcp.tool()``
decorators attach to, plus a small holder for the authenticated GitHub client
so tools can reach the client the entrypoint built at boot. Subsequent slices
(e.g. the ``list_issues`` tool) extend this module by registering tools on
:data:`mcp` and reading the client via :func:`github_client`.
"""

from typing import Literal

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from .github_client import MissingGitHubTokenError, build_github_client

__all__ = [
    "mcp",
    "attach_github_client",
    "github_client",
    "MissingGitHubTokenError",
    "build_github_client",
    "GitHubAPIError",
    "Issue",
    "list_issues",
]

IssueState = Literal["open", "closed", "all"]

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


class GitHubAPIError(RuntimeError):
    """Raised when the GitHub issues request fails.

    Surfaced to the caller as a clear tool error (auth failure, rate limit,
    missing repo, network error, ...) so a failed request is never mistaken for
    a repo that legitimately has no open issues.
    """


class Issue(BaseModel):
    """A single GitHub issue, normalised to the fields triage tools need."""

    number: int
    title: str
    state: str
    labels: list[str]
    assignee: str | None
    url: str


def _parse_repo(repo: str) -> tuple[str, str]:
    """Split an ``owner/repo`` identifier, rejecting anything malformed."""
    parts = repo.split("/")
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise ValueError(
            f"repo must be in 'owner/repo' form, got {repo!r}."
        )
    return parts[0], parts[1]


@mcp.tool()
def list_issues(repo: str, state: IssueState = "open") -> list[Issue]:
    """List a repository's issues, excluding pull requests.

    Args:
        repo: The repository identifier in ``owner/repo`` form.
        state: Which issues to return — ``open`` (default), ``closed`` or
            ``all``.

    Returns the issues' number, title, state, labels, assignee and url. Pull
    requests, which GitHub's issues endpoint returns alongside issues, are
    filtered out. A GitHub API/auth/network failure raises
    :class:`GitHubAPIError` rather than returning an empty list.
    """
    owner, name = _parse_repo(repo)
    client = github_client()

    try:
        response = client.get(
            f"/repos/{owner}/{name}/issues",
            params={"state": state, "per_page": 100},
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise GitHubAPIError(
            f"GitHub API request for issues in '{repo}' failed with status "
            f"{exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise GitHubAPIError(
            f"GitHub API request for issues in '{repo}' failed: {exc}"
        ) from exc

    issues: list[Issue] = []
    for item in response.json():
        # GitHub returns PRs from the issues endpoint; they carry this field.
        if item.get("pull_request") is not None:
            continue
        assignee = item.get("assignee")
        issues.append(
            Issue(
                number=item["number"],
                title=item["title"],
                state=item["state"],
                labels=[label["name"] for label in item.get("labels", [])],
                assignee=assignee["login"] if assignee else None,
                url=item["html_url"],
            )
        )
    return issues
