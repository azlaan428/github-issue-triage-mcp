"""Tests for the production GitHub client factory (the real composition root).

These exercise `build_github_client` directly — the same factory the running
server boots from in `__main__.main` — for both the token-present and
token-missing cases, rather than a test-only injected client.
"""

import httpx
import pytest

from github_issue_triage_mcp.github_client import (
    MissingGitHubTokenError,
    build_github_client,
)


def test_build_github_client_with_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret123")

    client = build_github_client()
    try:
        assert isinstance(client, httpx.Client)
        assert str(client.base_url) == "https://api.github.com"
        assert client.headers["Authorization"] == "Bearer ghp_secret123"
        # GitHub recommends pinning the REST API version + JSON accept header.
        assert client.headers["Accept"] == "application/vnd.github+json"
        assert client.headers["X-GitHub-Api-Version"] == "2022-11-28"
    finally:
        client.close()


def test_build_github_client_missing_token_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(MissingGitHubTokenError) as excinfo:
        build_github_client()

    assert "GITHUB_TOKEN" in str(excinfo.value)


def test_build_github_client_empty_token_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "")

    with pytest.raises(MissingGitHubTokenError):
        build_github_client()


def test_build_github_client_whitespace_token_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A token that is only whitespace is as unauthenticated as an empty one.
    monkeypatch.setenv("GITHUB_TOKEN", "   ")

    with pytest.raises(MissingGitHubTokenError):
        build_github_client()
