"""Windows <-> local path conversion (the app runs under WSL during development)."""

from pathlib import Path

import pytest

from oldschool.player import platform as pf


def test_drive_paths_round_trip():
    if not pf.IS_WSL:
        pytest.skip("WSL conversion")
    assert pf.to_local(r"E:\CounterStrike\game") == Path("/mnt/e/CounterStrike/game")
    assert pf.to_native("/mnt/e/CounterStrike/game") == r"E:\CounterStrike\game"


def test_wsl_folders_are_shown_as_explorer_paths(monkeypatch):
    monkeypatch.setattr(pf, "IS_WSL", True)
    monkeypatch.setattr(pf, "IS_WINDOWS", False)
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    native = pf.to_native("/home/user/library/Drop")
    assert native == r"\\wsl.localhost\Ubuntu\home\user\library\Drop"
    assert pf.to_local(native) == Path("/home/user/library/Drop")
    assert pf.to_local(r"\\wsl$\Ubuntu\home\x") == Path("/home/x")
