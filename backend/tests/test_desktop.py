"""The Windows launcher's pieces that can run anywhere: port choice, icon, bundled files, welcome flag."""

import socket

from fastapi.testclient import TestClient
from PIL import Image

from oldschool import config, desktop, icon
from oldschool.api.app import create_app


def test_free_port_skips_a_taken_one():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        taken = busy.getsockname()[1]
        assert desktop.free_port("127.0.0.1", taken) != taken


def test_icon_has_every_windows_size(tmp_path):
    path = tmp_path / "app.ico"
    icon.save_ico(path)
    with Image.open(path) as img:
        assert img.format == "ICO"
        assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= set(img.info["sizes"])
    corner, centre = icon.draw(64).getpixel((32, 4)), icon.draw(64).getpixel((10, 32))
    assert centre == icon.GREEN and corner == icon.OLIVE


def test_bundled_paths_outside_the_package():
    assert not config.FROZEN
    assert config.frontend_dist() == config.resource_dir() / "frontend" / "dist"
    assert (config.resource_dir() / "backend" / "oldschool").is_dir()


def test_welcome_flag(tmp_path):
    c = TestClient(create_app(tmp_path / "t.sqlite", scan_on_start=False))
    assert c.get("/api/settings").json()["welcomed"] is False
    r = c.put("/api/settings", json={"welcomed": True}, headers={"X-Oldschool": "1"})
    assert r.json()["welcomed"] is True


def test_one_running_copy_per_library(tmp_path, monkeypatch):
    monkeypatch.delenv("OLDSCHOOL_DATA_DIR", raising=False)
    assert desktop.mutex_name(tmp_path) == desktop.MUTEX_NAME  # the name the setup program checks
    monkeypatch.setenv("OLDSCHOOL_DATA_DIR", str(tmp_path))
    other = desktop.mutex_name(tmp_path)
    assert other.startswith(desktop.MUTEX_NAME + "-") and other != desktop.mutex_name(tmp_path / "x")
