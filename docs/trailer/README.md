# Trailer

`oldschool-cs-demos-trailer.mp4`: 38 s, 1920×1080, 30 fps, H.264 + AAC, -14 LUFS (made for X and other social networks).

The picture is an HTML page animated frame by frame (`trailer.html`, `render(t)` draws time `t`) from screens of the app, captured by Chrome. The sound is one orchestral piece plus effects synthesised in code (`audio.py`).

## Rebuild

On Windows, with Google Chrome and Python 3.12:

```
python -m venv venv
venv\Scripts\pip install playwright numpy imageio-ffmpeg
venv\Scripts\python build.py
```

`build.py 12` leaves a 12-second slot after the ▶ R7 click (for in-game footage); the scene timings are in `trailer.html` and mirrored in `audio.py`.

## Credits

- Music: "Battle Theme A" by cynicmusic, [CC0 1.0](https://opengameart.org/content/battle-theme-a) (public domain).
- Sound effects: synthesised by `audio.py`.
- Pictures: screens of the app; no Valve artwork.
