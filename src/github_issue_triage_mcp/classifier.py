"""Pure keyword classifier mapping an issue to a triage label.

This module is deliberately plain — no LLM call, no network, no I/O — so the
triage decision is deterministic and exhaustively unit-testable. It maps an
issue's ``title + body`` to exactly one of ``bug`` / ``feature`` / ``question``.

Heuristic (documented so the behaviour is auditable):

* Each candidate label owns a list of lowercase keyword/phrase signals.
* We count how many distinct signals for each label appear in the combined,
  lower-cased ``title + body`` text.
* The label with the highest count wins.
* **Default:** when there is no ``bug`` and no ``feature`` signal at all, the
  result is ``question`` — most issues with no problem/request signal are
  someone asking something.
* **Tie-break:** when counts are equal, a fixed priority order decides —
  ``bug`` before ``feature`` before ``question``. ``bug`` is the most
  actionable/urgent class, so it is preferred when the text is ambiguous.
"""

from __future__ import annotations

from typing import Literal

Label = Literal["bug", "feature", "question"]

# Distinct lowercase signals per label. Kept small and explicit on purpose:
# the heuristic is meant to be readable and auditable, not exhaustive.
_BUG_SIGNALS: tuple[str, ...] = (
    "bug",
    "error",
    "crash",
    "broken",
    "fail",
    "exception",
    "traceback",
    "regression",
    "stack trace",
    "doesn't work",
    "does not work",
    "not working",
    "unexpected",
    "incorrect",
)

_FEATURE_SIGNALS: tuple[str, ...] = (
    "feature",
    "add ",
    "support",
    "enhancement",
    "would be nice",
    "request",
    "please add",
    "implement",
    "ability to",
    "it would be great",
    "wish",
)

_QUESTION_SIGNALS: tuple[str, ...] = (
    "how do i",
    "how to",
    "how can i",
    "question",
    "what is",
    "why does",
    "can i",
    "is it possible",
    "help",
    "?",
)

# Fixed tie-break priority: bug is most actionable, question is the fallback.
_PRIORITY: tuple[Label, ...] = ("bug", "feature", "question")


def _count(signals: tuple[str, ...], text: str) -> int:
    return sum(1 for signal in signals if signal in text)


def classify_issue(title: str, body: str | None) -> Label:
    """Classify an issue as ``bug``, ``feature`` or ``question``.

    Args:
        title: The issue title.
        body: The issue body (GitHub may return ``None`` for an empty body).

    Returns the single best-matching label per the heuristic documented in the
    module docstring.
    """
    text = f"{title}\n{body or ''}".lower()

    scores: dict[Label, int] = {
        "bug": _count(_BUG_SIGNALS, text),
        "feature": _count(_FEATURE_SIGNALS, text),
        "question": _count(_QUESTION_SIGNALS, text),
    }

    # Default: no problem and no request signal => it's a question.
    if scores["bug"] == 0 and scores["feature"] == 0:
        return "question"

    best = max(scores.values())
    for label in _PRIORITY:
        if scores[label] == best:
            return label
    # Unreachable: ``best`` always equals at least one score above.
    return "question"  # pragma: no cover
