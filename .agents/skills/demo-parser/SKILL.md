---
name: demo-parser
description: Change how GoldSrc demos are read or identified (parser, rounds, kill feed, release, teams, year, match grouping) and prove it with synthetic demos. Use when a demo imports with wrong teams, scores, rounds, release or year, or when the parser must read something new.
---

# Demo parsing and identification

## Where things are

| File | Does |
| --- | --- |
| `oldschool/parser/goldsrc.py` | GoldSrc `HLDEMO` container: header, directory, frames (`iter_frames`), server info, user messages (DeathMsg, TeamScore, SayText, RoundTime…), players and SteamIDs, `analyse()`, `rounds()`, team clustering, clan tags. `HL2DEMO` (Source) raises `DemoError`. |
| `oldschool/identify.py` | release (`guess_version`: network protocol + user-message fingerprint), year estimate with basis (`guess_year`), match grouping (`split_matches`), teams and line-ups (`propose`). |
| `oldschool/archives.py` | members of any archive, nested (bsdtar / 7-Zip / acefile), tolerant reads of truncated files. |
| `oldschool/importer.py` | pipeline and `PARSE_VERSION`. |

Release rules (calibrated on a curated library): protocol 43 without `AllowSpec` → 1.0, with it → 1.1; protocol 45 without `BombDrop` → 1.3, with it → 1.4; protocol 46 → 1.5, or 1.6 when the demo has FAMAS / Galil; protocol 47/48 → 1.6. Network protocol says the engine era, not the year.

## Prove changes with synthetic demos

Real demos are never committed. `tests/demo_factory.py` builds demos byte by byte:

- `build_demo(recorder_slot=0, hltv=True, steam=False)`: a small match with players, a kill feed and chat.
- `build_round_demo(frames)` with helpers `text()`, `roundtime()`, `score()`, `round_var()`: rounds, scores and round ends at chosen times (`MATCH` is a ready-made 3-round example).

Write the failing case as a demo built by these helpers, then fix the parser. For a bug seen on a real file, reduce it to the message sequence that matters and rebuild that sequence; local real files can go in `backend/tests/corpus/` (git-ignored) for a manual regression run.

## When output changes

1. Bump `importer.PARSE_VERSION`: users then see "N files read by an older version" on the Import page and can re-analyse.
2. Re-analysis rebuilds matches from the kept originals (`Writer.replace`); match ids change, which the page already warns about.
3. Check a large real library still imports cleanly (0 failed) and spot-check matches you know; `backend/tools/compare_catalog.py` compares a library with a reference catalogue.

## Rules

- Names and tags **as printed** (`aAa|KabaL`, `*aAa* Fatal`): never normalise case or strip decorations in stored values; `display_alias()` is for display only.
- Never merge players or teams automatically; same name ≠ same person.
- Every estimate carries its basis (HLTV name stamp, member file date, folder name). A file timestamp is never a played date.
- Keep reads tolerant: truncated and interrupted demos are common; keep what was decoded and record the problem.
