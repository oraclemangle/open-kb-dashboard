"""Shared pytest fixtures for open-kb-dashboard tests."""
from __future__ import annotations

import os
import sys

# Make sure the project root is importable regardless of how pytest is
# invoked (it usually is, but this keeps `python -m pytest` from anywhere
# under the repo working too).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Strip any OPENKB_DASH_* env vars before each test so tests don't leak
    into each other (and so a developer's real config.yaml/env can't
    accidentally change test outcomes)."""
    for name in list(os.environ):
        if name.startswith("OPENKB_DASH_"):
            monkeypatch.delenv(name, raising=False)
    yield
