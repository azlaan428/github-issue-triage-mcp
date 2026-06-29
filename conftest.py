"""Best-effort hardening so a gate-injected JUnit XML report path stays writable.

The verify/CI gate runs ``pytest --junitxml=<path>`` against a temp file it
creates. If that path pre-exists as a stale, unwritable file (left read-only by
a prior run, or owned by a different user), pytest's junitxml plugin fails at
session finish with ``PermissionError`` when it opens the path for writing —
reding the whole run even though every test passed.

``ensure_junit_writable`` clears such a stale, *removable* report file before
the run so the plugin recreates it fresh and owned by us. It is purely
best-effort: a writable file is left untouched, and a file that cannot be
removed (e.g. a foreign-owned file in a sticky ``/tmp``) is left in place rather
than raising — the run is then no worse off than without this hook.
"""

from __future__ import annotations

import os
import warnings


def ensure_junit_writable(xmlpath: str | None) -> bool:
    """Make ``xmlpath`` writable for the current user if a stale file blocks it.

    Returns ``True`` when the path is unset, absent, already writable, or was
    successfully cleared; ``False`` when a blocking file remains that could not
    be removed.
    """
    if not xmlpath:
        return True
    if not os.path.exists(xmlpath):
        return True  # the plugin will create it fresh, owned by us
    if os.access(xmlpath, os.W_OK):
        return True  # already writable — leave it for the plugin to truncate
    try:
        os.remove(xmlpath)
    except OSError as exc:  # sticky dir / foreign owner — nothing we can do
        warnings.warn(
            f"junit report path {xmlpath!r} is not writable and could not be "
            f"cleared ({exc}); the run may fail when writing the report.",
            stacklevel=2,
        )
        return False
    return True


def pytest_configure(config) -> None:
    """Clear a stale, unwritable junit report path before the session runs."""
    ensure_junit_writable(getattr(config.option, "xmlpath", None))
