"""Shared test setup."""

import pytest


@pytest.fixture(autouse=True)
def _no_wsl_share_paths(monkeypatch):
    """Temporary folders stay plain paths in tests, inside WSL or not
    (test_platform covers the \\\\wsl.localhost form)."""
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
