"""Render trailer.html to an MP4 for X (1920x1080, 30 fps, H.264).

    python render.py [GAME_SECONDS]

GAME_SECONDS: length of the in-game clip slot after the match scene (0 = none).
Each frame is drawn by calling render(t) in the page (deterministic), captured
by Chrome through Playwright and piped to ffmpeg.
"""

import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
FPS = 30


def main() -> None:
    game = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
    out_dir = HERE / "out"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / ("trailer-base.mp4" if game else "trailer.mp4")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", args=["--allow-file-access-from-files"])
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.add_init_script(f"window.GAME = {game}")
        page.goto((HERE / "trailer.html").as_uri())
        page.wait_for_function("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
        duration = page.evaluate("window.DURATION")
        frames = round(duration * FPS)
        enc = subprocess.Popen(
            [ffmpeg, "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
             "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart", str(out)],
            stdin=subprocess.PIPE,
        )  # fmt: skip
        for i in range(frames):
            page.evaluate(f"render({i / FPS})")
            enc.stdin.write(page.screenshot(type="png", timeout=120_000))
            if i % 150 == 0:
                print(f"frame {i}/{frames}", flush=True)
        enc.stdin.close()
        enc.wait()
        browser.close()
    print(f"wrote {out} ({duration:.1f} s, {frames} frames)")


if __name__ == "__main__":
    main()
