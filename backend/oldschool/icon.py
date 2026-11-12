"""The app icon, drawn in code: an olive square with a green crosshair
(the same mark as the page header). No game artwork is used."""

from __future__ import annotations

OLIVE = (76, 88, 68, 255)
DARK = (42, 48, 35, 255)
LIGHT = (137, 151, 128, 255)
GREEN = (159, 210, 122, 255)
SIZES = (16, 24, 32, 48, 64, 128, 256)


def draw(size: int = 64):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    edge = max(1, size // 32)
    d.rectangle([0, 0, size - 1, size - 1], fill=OLIVE)
    d.rectangle([0, 0, size - 1, edge - 1], fill=LIGHT)  # bevel, like the menus
    d.rectangle([0, 0, edge - 1, size - 1], fill=LIGHT)
    d.rectangle([0, size - edge, size - 1, size - 1], fill=DARK)
    d.rectangle([size - edge, 0, size - 1, size - 1], fill=DARK)
    c, w = size / 2, max(2, size // 11)
    arm, gap = size * 0.36, size * 0.11
    for a, b in ((c - arm, c - gap), (c + gap, c + arm)):
        d.rectangle([a, c - w / 2, b, c + w / 2 - 1], fill=GREEN)  # horizontal arms
        d.rectangle([c - w / 2, a, c + w / 2 - 1, b], fill=GREEN)  # vertical arms
    return img


def save_ico(path) -> None:
    """Multi-size .ico for the .exe, the installer and shortcuts."""
    draw(256).save(path, format="ICO", sizes=[(s, s) for s in SIZES])
