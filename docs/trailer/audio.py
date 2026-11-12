"""Soundtrack for the trailer: synthesised sound effects (original, no licence
needed) on the scene timings of trailer.html, under one CC0 orchestral piece
played from its first note.

    python audio.py [GAME_SECONDS]  ->  out/soundtrack.wav

Music: "Battle Theme A" by cynicmusic, CC0 (public domain),
https://opengameart.org/content/battle-theme-a
"""

import subprocess
import sys
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np

HERE = Path(__file__).resolve().parent
SR = 48000
RNG = np.random.default_rng(7)


# ------------------------------------------------------------------ timings (mirror trailer.html)
def timings(game: float) -> dict:
    after = 21.6 + game
    t = {"after": after, "a5": after - 0.2, "a6": after + 5.4, "a7": after + 10.4}
    t["end"] = after + 17.0
    return t


# ------------------------------------------------------------------ synthesis helpers
def secs(d):
    return np.arange(int(d * SR)) / SR


def env(n, attack=0.002, decay=0.1, sustain=0.0):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    d = np.exp(-np.maximum(t - attack, 0) / max(decay, 1e-4))
    return a * (sustain + (1 - sustain) * d)


def lowpass(x, cutoff):
    """One-pole low-pass with a cutoff that may change per sample."""
    cutoff = np.broadcast_to(np.asarray(cutoff, dtype=float), x.shape)
    a = 1 - np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def glide(f0, f1, d, curve="exp"):
    t = secs(d)
    f = f0 * (f1 / f0) ** (t / d) if curve == "exp" else f0 + (f1 - f0) * t / d
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def stereo(x, pan=0.0):
    left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    return np.stack([x * left, x * right], axis=1)


def ui_click(gain=0.5, pitch=1.0):
    n = int(0.03 * SR)
    noise = RNG.standard_normal(n)
    hp = np.diff(noise, prepend=0) * env(n, 0.0005, 0.004)
    tone = np.sin(2 * np.pi * 2100 * pitch * secs(0.03)) * env(n, 0.0005, 0.012)
    return stereo(gain * (0.5 * hp + 0.6 * tone))


def key(gain=0.35):
    n = int(0.05 * SR)
    p = RNG.uniform(0.85, 1.2)
    noise = lowpass(RNG.standard_normal(n), 3500) * env(n, 0.0005, 0.008)
    body = np.sin(2 * np.pi * 380 * p * secs(0.05)) * env(n, 0.0005, 0.018)
    return stereo(gain * (1.6 * noise + 0.5 * body), RNG.uniform(-0.25, 0.25))


def tick(gain=0.18, f=3200):
    n = int(0.012 * SR)
    return stereo(gain * np.sin(2 * np.pi * f * secs(0.012)) * env(n, 0.0003, 0.003))


def whoosh(d=0.7, gain=0.45, lo=300, hi=5000, pan_from=-0.6, pan_to=0.6):
    n = int(d * SR)
    t = np.arange(n) / n
    bell = np.sin(np.pi * t) ** 1.6
    cut = lo + (hi - lo) * np.sin(np.pi * t) ** 2
    x = lowpass(RNG.standard_normal(n), cut) * bell
    pans = pan_from + (pan_to - pan_from) * t
    left, right = np.cos((pans + 1) * np.pi / 4), np.sin((pans + 1) * np.pi / 4)
    return gain * np.stack([x * left, x * right], axis=1) / (np.abs(x).max() + 1e-9)


def thud(gain=0.6, f0=110, f1=42, d=0.45):
    n = int(d * SR)
    body = glide(f0, f1, d) * env(n, 0.002, d / 3.5)
    click = lowpass(RNG.standard_normal(n), 1800) * env(n, 0.0005, 0.01)
    return stereo(gain * (body + 0.5 * click))


def boom(gain=0.8, d=2.2):
    n = int(d * SR)
    body = glide(70, 30, d) * env(n, 0.003, d / 3)
    rumble = lowpass(RNG.standard_normal(n), 220) * env(n, 0.003, d / 2.5)
    rumble /= np.abs(rumble).max() + 1e-9
    return stereo(gain * (body + 0.6 * rumble))


def riser(d=2.0, gain=0.4):
    n = int(d * SR)
    t = np.arange(n) / n
    noise = lowpass(RNG.standard_normal(n), 200 + 7000 * t**2)
    noise /= np.abs(noise).max() + 1e-9
    tone = glide(180, 900, d) * 0.35
    amp = t**2.2
    return stereo(gain * amp * (noise + tone))


def chime(f=880, gain=0.28, d=1.1):
    n = int(d * SR)
    x = sum(a * np.sin(2 * np.pi * f * m * secs(d)) for m, a in ((1, 1.0), (2.01, 0.35), (3.02, 0.15)))
    return stereo(gain * x * env(n, 0.002, d / 4), 0.15)


def blip(f1=660, f2=990, gain=0.25):
    a = np.sin(2 * np.pi * f1 * secs(0.06)) * env(int(0.06 * SR), 0.001, 0.03)
    b = np.sin(2 * np.pi * f2 * secs(0.12)) * env(int(0.12 * SR), 0.001, 0.05)
    return stereo(gain * np.concatenate([a, b]))


# ------------------------------------------------------------------ cues
# Soft, discreet effects: the orchestra carries the energy, the effects only
# underline what happens on screen.
def cues(T):
    c = []
    add = lambda t, snd: c.append((t, snd))  # noqa: E731
    # 1 · hook: the crosshair locks on, the texts slide in
    for k in range(1, 5):
        add(0.25 + k * 0.09, tick(0.06, 1500 + 150 * k))
    add(1.0, whoosh(0.9, 0.08, 150, 1400))
    add(2.1, whoosh(0.9, 0.07, 150, 1300, 0.6, -0.6))
    # 2 · import: archives dropping in, counters
    for i in range(7):
        s = 4.5 + i * 0.32
        add(s, whoosh(0.55, 0.05, 250, 1800, -0.8 if i % 2 == 0 else 0.4, 0.0))
    for k in range(1, 13):  # a few soft ticks following the counters' ease-out
        q = k / 13
        add(5.6 + 2.6 * (1 - (1 - q) ** (1 / 3)), tick(0.04, 1800))
    add(8.2, chime(880, 0.07, 0.9))
    # 3 · library search
    add(8.85, whoosh(0.9, 0.1, 150, 1600))
    for k in range(12):
        add(10.9 + (k + 1) / 12 * 1.3 - 0.05, key(0.12))
    add(13.5, chime(784, 0.09, 1.0))
    # 4 · match, click on ▶ R7, the game starts
    add(14.85, whoosh(0.9, 0.1, 150, 1600, 0.6, -0.6))
    add(19.38, ui_click(0.16, 0.7))
    add(19.7, blip(523, 784, 0.07))
    add(20.9, whoosh(0.9, 0.12, 200, 2200))
    # 5 · versions: a soft rising chime per version
    a5 = T["a5"]
    add(a5 + 0.2, whoosh(0.9, 0.09, 150, 1600))
    for i in range(6):
        add(a5 + 1.1 + i * 0.32 + 0.42, chime(523 * 2 ** (i * 2 / 12), 0.06, 0.8))
    # 6 · keys
    a6 = T["a6"]
    add(a6 - 0.1, whoosh(0.9, 0.09, 150, 1600, -0.6, 0.6))
    add(a6 + 1.4, key(0.14))
    # 7 · outro: a soft low swell under the orchestra's hit
    a7 = T["a7"]
    add(a7 - 0.15, whoosh(1.0, 0.1, 120, 1500))
    add(a7 + 0.2, thud(0.18, 70, 35, 1.2))
    return c


# ------------------------------------------------------------------ music edit
def load_music(path: Path) -> np.ndarray:
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    raw = subprocess.run(
        [ff, "-loglevel", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
        capture_output=True, check=True,
    ).stdout  # fmt: skip
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def music_track(T, n) -> np.ndarray:
    """One piece, played from its first note: its opening lands on the
    crosshair, a hit at 3.8 s before the archives drop in, another at 32.35 s
    on the logo. Fade-out over the last seconds."""
    m = load_music(HERE / "music" / "battle-theme-a.mp3")
    out = np.zeros((n, 2))
    k = min(n, len(m))
    out[:k] = m[:k]
    v = np.arange(n) / SR
    fade = np.clip((T["end"] - v) / 2.6, 0, 1)
    return out * (fade**1.5)[:, None]


def main() -> None:
    game = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
    T = timings(game)
    n = int((T["end"] + 0.05) * SR)
    music = music_track(T, n)
    music *= 0.6 / (np.abs(music).max() + 1e-9)
    sfx = np.zeros((n, 2))
    cue_list = cues(T)
    for t, snd in cue_list:
        i = int(t * SR)
        j = min(n, i + len(snd))
        sfx[i:j] += snd[: j - i]
    mix = music + sfx
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)  # gentle limiter
    pcm = (np.clip(mix, -1, 1) * 32000).astype(np.int16)
    out = HERE / "out" / "soundtrack.wav"
    out.parent.mkdir(exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print(f"wrote {out} ({n / SR:.1f} s, {len(cue_list)} sound effects)")


if __name__ == "__main__":
    main()
