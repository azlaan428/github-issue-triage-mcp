"""Production factory for the authenticated GitHub API client.

This is the real composition root the running server boots from: it reads the
``GITHUB_TOKEN`` environment variable and returns an ``httpx.Client`` pointed at
the GitHub REST API with the auth headers attached. It fails fast when the token
is missing or blank so an unauthenticated client never ships.
"""

import os

import httpx

GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"


class MissingGitHubTokenError(RuntimeError):
    """Raised at startup when ``GITHUB_TOKEN`` is unset or blank."""


def build_github_client(token: str | None = None) -> httpx.Client:
    """Build an authenticated GitHub REST API client.

    When ``token`` is not supplied it is read from the ``GITHUB_TOKEN``
    environment variable. A missing or blank token raises
    :class:`MissingGitHubTokenError` rather than producing an unauthenticated
    client.
    """
    if token is None:
        token = os.environ.get("GITHUB_TOKEN")

    if token is None or not token.strip():
        raise MissingGitHubTokenError(
            "GITHUB_TOKEN environment variable is not set or is empty; "
            "cannot build an authenticated GitHub client. "
            "Set GITHUB_TOKEN to a GitHub personal access token and retry."
        )

    return httpx.Client(
        base_url=GITHUB_API_BASE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
    )
