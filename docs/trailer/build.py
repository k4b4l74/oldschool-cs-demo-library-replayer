"""Build the trailer: picture (render.py), sound (audio.py), then both into
oldschool-cs-demos-trailer.mp4 next to this file (loudness -14 LUFS for social networks).

Needs Windows, Google Chrome, and a Python 3.12 with: playwright, numpy, imageio-ffmpeg.

    python build.py [GAME_SECONDS]
"""

import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import audio  # noqa: E402
import render  # noqa: E402


def main() -> None:
    render.main()
    audio.main()
    out = HERE / "oldschool-cs-demos-trailer.mp4"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
         "-i", str(HERE / "out" / "trailer.mp4"), "-i", str(HERE / "out" / "soundtrack.wav"),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", str(out)],
        check=True,
    )  # fmt: skip
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
