"""Tests for the best-effort JUnit-report-path hardening in the root conftest.

The verify/CI gate runs ``pytest --junitxml=<path>`` against a temp file. When
that path pre-exists as a stale, unwritable file (e.g. left by a prior run),
the junitxml plugin fails at session finish with ``PermissionError`` even though
every test passed. ``ensure_junit_writable`` clears such a removable stale file
so the plugin can recreate it fresh, while leaving a writable file untouched and
never raising when it cannot help.
"""

import os

from conftest import ensure_junit_writable


def test_unset_path_is_noop() -> None:
    assert ensure_junit_writable(None) is True
    assert ensure_junit_writable("") is True


def test_missing_file_is_left_for_plugin_to_create(tmp_path) -> None:
    path = tmp_path / "report.xml"
    assert not path.exists()
    # Nothing to clear; the plugin will create it fresh and owned by us.
    assert ensure_junit_writable(str(path)) is True
    assert not path.exists()


def test_writable_file_is_left_intact(tmp_path) -> None:
    path = tmp_path / "report.xml"
    path.write_text("<old/>")
    assert ensure_junit_writable(str(path)) is True
    # A writable report file must NOT be removed.
    assert path.exists()


def test_unwritable_stale_file_is_cleared(tmp_path) -> None:
    path = tmp_path / "report.xml"
    path.write_text("<stale/>")
    os.chmod(path, 0)  # owner loses write -> not W_OK for the non-root owner

    # In a directory we own the stale, unwritable file can be removed so the
    # junitxml plugin recreates it fresh and owned by us.
    assert ensure_junit_writable(str(path)) is True
    assert not path.exists()
