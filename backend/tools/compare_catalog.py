"""M1 acceptance: compare an imported library with the research catalogue.

    uv run python tools/compare_catalog.py --db <data dir>/library.sqlite \\
        --library <sorted library> --catalog-dir <catalog folder> \\
        --releases CS1.0,CS1.1,CS1.3,CS1.4,CS1.5 > ../docs/reports/M1-import.md

Reference data (read-only, produced by the wiki tools):
* ``_catalog/plan.jsonl``: per sorted file, the identification (release, year,
  teams, POV, sides, line-ups, demo SHA-1s);
* ``_catalog/demos.jsonl``: per source archive, the parsed demos (kills, K/D);
* ``sorted/_rounds/<file>.js``: rounds per demo (demo_rounds.py).

Development tool only; not part of the app.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

FIELDS = ("version", "year", "team1", "team2", "pov", "sides", "maps", "name")


def load_plan(catalog_dir: Path, library: Path, releases: set[str]) -> dict[str, dict]:
    placed = set()
    for line in (library / "_manifest.jsonl").read_text(encoding="utf-8").splitlines():
        m = json.loads(line)
        if m.get("status") == "ok":
            placed.add((m["source"], m["target"]))
    out = {}
    for line in (catalog_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["status"] == "ok" and r["version"] in releases and (r["source"], r["target"]) in placed:
            out[r["target"]] = r
    return out


def load_catalog_demos(catalog_dir: Path, sources: set[str]) -> dict[str, dict]:
    """sha1 -> catalogue demo record (kill_count, players)."""
    out = {}
    with (catalog_dir / "demos.jsonl").open(encoding="utf-8") as f:
        for line in f:
            start = line.find('"path": "') + 9
            if line[start : line.find('"', start)] not in sources:
                continue
            for d in json.loads(line)["demos"]:
                if "error" not in d:
                    out[d["sha1"]] = d
    return out


def load_rounds(library: Path, target: str) -> dict[str, int] | None:
    p = library / "_rounds" / (target + ".js")
    if not p.exists():
        return None
    s = p.read_text(encoding="utf-8")
    data = json.loads(s[s.index(",") + 1 : s.rindex(")")].replace("<\\/", "</"))
    return {m: len(v.get("rounds", [])) for m, v in data["demos"].items() if "error" not in v}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--library", type=Path, required=True)
    ap.add_argument("--catalog-dir", type=Path, required=True)
    ap.add_argument("--releases", default="CS1.0,CS1.1,CS1.3,CS1.4,CS1.5")
    ap.add_argument("--examples", type=int, default=8)
    args = ap.parse_args(argv)
    releases = set(args.releases.split(","))
    plan = load_plan(args.catalog_dir, args.library, releases)
    cat = load_catalog_demos(args.catalog_dir, {r["source"] for r in plan.values()})
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    lib = str(args.library.resolve())

    def rel(p: str) -> str:
        return Path(p).resolve().relative_to(lib).as_posix() if p.startswith(lib) else p

    originals = {rel(r["source_path"]): r for r in db.execute("SELECT * FROM originals")}
    team = {r["id"]: r["tag_as_printed"] for r in db.execute("SELECT id, tag_as_printed FROM teams")}
    by_original = defaultdict(list)
    for m in db.execute("SELECT * FROM matches"):
        by_original[m["original_id"]].append(m)
    match_demos = defaultdict(list)
    for r in db.execute("SELECT match_id, demo_sha1 FROM match_demos ORDER BY match_id, part_no"):
        match_demos[r[0]].append(r[1])
    lineups = defaultdict(lambda: defaultdict(set))
    for r in db.execute(
        "SELECT mp.match_id, mp.team_key, p.name_as_printed FROM match_players mp"
        " JOIN player_names p ON p.id = mp.player_name_id"
    ):
        lineups[r[0]][r[1]].add(r[2])
    demo_rows = {r["sha1"]: r for r in db.execute("SELECT sha1, kill_count, parse_error FROM demos")}
    kd = defaultdict(dict)
    for r in db.execute("SELECT demo_sha1, slot, kills, deaths FROM demo_players"):
        kd[r[0]][r[1]] = (r[2], r[3])
    rounds_db = dict(db.execute("SELECT demo_sha1, count(*) FROM rounds GROUP BY demo_sha1").fetchall())

    missing = sorted(set(plan) - set(originals))
    extra = sorted(set(originals) - set(plan))
    diffs: dict[str, list] = defaultdict(list)
    not_one_match = []
    demo_set_diff = []
    lineup_diff = []
    kill_diff = []
    kd_diff = []
    rounds_cmp = Counter()
    rounds_diff = []
    checked_demos = 0
    for target, row in sorted(plan.items()):
        o = originals.get(target)
        if not o:
            continue
        ms = by_original.get(o["id"], [])
        if len(ms) != 1:
            not_one_match.append((target, len(ms)))
            if not ms:
                continue
        m = ms[0]
        mine = {
            "version": m["release"],
            "year": m["year_est"],
            "team1": team.get(m["team1_id"]),
            "team2": team.get(m["team2_id"]),
            "pov": m["pov"],
            "sides": m["sides"],
            "maps": m["map"],
            "name": m["library_name"],
        }
        ref = {
            "version": row["version"],
            "year": row["year"],
            "team1": row.get("team1"),
            "team2": row.get("team2"),
            "pov": row.get("pov"),
            "sides": row["sides"],
            "maps": "+".join(row["maps"]),
            "name": Path(target).name,
        }
        for f in FIELDS:
            if mine[f] != ref[f]:
                diffs[f].append((target, ref[f], mine[f]))
        if set(match_demos[m["id"]]) != set(row["demo_sha1"]):
            demo_set_diff.append(target)
        ref_lu = {k: set(v) for k, v in row.get("lineups", {}).items() if k in ("team1", "team2")}
        my_lu = {k: v for k, v in lineups[m["id"]].items() if k in ("team1", "team2")}
        if ref_lu != my_lu:
            lineup_diff.append((target, ref_lu, my_lu))
        rr = load_rounds(args.library, target)
        for member, sha1 in zip(row["members"], row["demo_sha1"], strict=True):
            checked_demos += 1
            c = cat.get(sha1)
            d = demo_rows.get(sha1)
            if c and d and c.get("kill_count") != d["kill_count"]:
                kill_diff.append((target, member, c.get("kill_count"), d["kill_count"]))
            if c and d:
                ref_kd = {p["slot"]: (p["kills"], p["deaths"]) for p in c["players"]}
                if ref_kd != kd.get(sha1, {}):
                    kd_diff.append((target, member))
            if rr is not None and member in rr:
                mine_n = rounds_db.get(sha1, 0)
                rounds_cmp["same" if mine_n == rr[member] else "different"] += 1
                if mine_n != rr[member]:
                    rounds_diff.append((target, member, rr[member], mine_n))
            else:
                rounds_cmp["no reference"] += 1

    totals = {
        t: db.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in ("originals", "demos", "matches", "rounds", "kills", "player_names", "teams", "chat")
    }
    parse_errors = sum(1 for d in demo_rows.values() if d["parse_error"])
    ex = args.examples
    out = ["# M1 import report", ""]
    out.append(
        f"Releases: {', '.join(sorted(releases))}. Reference: `cs-demos/_catalog` (plan, catalogue) and `sorted/_rounds`."
    )
    out += ["", "## Totals in the new library", "", "| Table | Rows |", "| --- | ---: |"]
    out += [f"| {t} | {n:,} |" for t, n in totals.items()]
    out += [f"| demos with a parse error | {parse_errors:,} |", ""]
    out += ["## Files", ""]
    out.append(f"- Sorted files expected: **{len(plan):,}**; imported: **{len(set(plan) & set(originals)):,}**.")
    out.append(f"- Missing from the import: {len(missing)}" + (f" (e.g. {', '.join(missing[:ex])})" if missing else ""))
    out.append(f"- Imported but not in the plan: {len(extra)}" + (f" (e.g. {', '.join(extra[:ex])})" if extra else ""))
    out.append(f"- Files that did not give exactly one match: {len(not_one_match)}"
               + (f" (e.g. {', '.join(f'{t} → {n}' for t, n in not_one_match[:ex])})" if not_one_match else ""))  # fmt: skip
    out += [
        "",
        "## Identification (match fields vs the catalogue plan)",
        "",
        "| Field | Different | Same |",
        "| --- | ---: | ---: |",
    ]
    compared = len(set(plan) & set(originals)) - sum(1 for _t, n in not_one_match if n == 0)
    for f in FIELDS:
        out.append(f"| {f} | {len(diffs[f]):,} | {compared - len(diffs[f]):,} |")
    for f in FIELDS:
        if diffs[f]:
            out += ["", f"Examples for **{f}** (catalogue → new):", ""]
            out += [f"- `{t}`: `{a}` → `{b}`" for t, a, b in diffs[f][:ex]]
    out += ["", "## Demos, line-ups, kills, rounds", ""]
    out.append(
        f"- Matches whose demo set differs: {len(demo_set_diff)}"
        + (f" (e.g. {', '.join(demo_set_diff[:ex])})" if demo_set_diff else "")
    )
    out.append(f"- Matches whose team1/team2 line-ups differ: {len(lineup_diff)}")
    for t, a, b in lineup_diff[:ex]:
        out.append(f"  - `{t}`: catalogue {json.dumps({k: sorted(v) for k, v in a.items()}, ensure_ascii=False)}"
                   f" → new {json.dumps({k: sorted(v) for k, v in b.items()}, ensure_ascii=False)}")  # fmt: skip
    out.append(
        f"- Demos checked: {checked_demos:,}; kill-feed count differs: {len(kill_diff)}; per-slot K/D differs: {len(kd_diff)}"
    )
    out += [f"  - `{t}` {mb}: {a} → {b}" for t, mb, a, b in kill_diff[:ex]]
    out.append(f"- Rounds per demo vs `_rounds`: same {rounds_cmp['same']:,}, different {rounds_cmp['different']:,},"
               f" no reference {rounds_cmp['no reference']:,}")  # fmt: skip
    out += [f"  - `{t}` {mb}: {a} → {b}" for t, mb, a, b in rounds_diff[:ex]]
    print("\n".join(out))


if __name__ == "__main__":
    main()
