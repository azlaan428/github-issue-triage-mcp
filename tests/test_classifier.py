"""Tests for the pure keyword classifier.

The classifier maps an issue's ``title + body`` to exactly one of
``bug`` / ``feature`` / ``question`` via documented keyword heuristics with a
deterministic default. It is a plain function — no LLM, no network — so it is
exhaustively unit-testable here.
"""

from __future__ import annotations

import pytest

from github_issue_triage_mcp.classifier import classify_issue


def test_classifies_bug_from_error_signal() -> None:
    label = classify_issue(
        "Server crashes on startup",
        "It throws a NullPointer exception and the traceback shows a crash.",
    )
    assert label == "bug"


def test_classifies_feature_from_request_signal() -> None:
    label = classify_issue(
        "Please add dark mode support",
        "It would be nice to have an option to enable a dark theme.",
    )
    assert label == "feature"


def test_classifies_question_from_how_do_i_signal() -> None:
    label = classify_issue(
        "How do I configure the timeout?",
        "Is it possible to change the request timeout setting?",
    )
    assert label == "question"


def test_no_signal_defaults_to_question() -> None:
    """With no bug/feature signal at all, the deterministic default is question."""
    label = classify_issue("Weekly sync notes", "Notes from the meeting on Tuesday.")
    assert label == "question"


def test_bug_outranks_feature_on_tie() -> None:
    """Documented tie-break: bug is the most actionable, so it wins ties."""
    # One bug keyword ("error") and one feature keyword ("add") => tie => bug.
    label = classify_issue("Add validation", "There is an error in the form.")
    assert label == "bug"


def test_empty_input_defaults_to_question() -> None:
    assert classify_issue("", "") == "question"


@pytest.mark.parametrize("label", ["bug", "feature", "question"])
def test_returns_only_the_three_known_labels(label: str) -> None:
    """Sanity: every output is one of the three known classes."""
    samples = {
        "bug": ("crash", "exception"),
        "feature": ("add feature", "would be nice"),
        "question": ("how do i", "is it possible?"),
    }
    title, body = samples[label]
    assert classify_issue(title, body) in {"bug", "feature", "question"}
