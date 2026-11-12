# M1 import report

Snapshot of 2026-11-11. The app imported `cs-demos/sorted` for CS 1.0–1.5, the research library sorted on 2026-11-08: 2,104 archives, about 16.5 GB. The archives were only read. This report compares the new database with the research catalogue that built that library. Regenerate it with `backend/tools/compare_catalog.py`.

## Summary

- **Nothing lost.** All 2,104 files and all 4,253 distinct demos were imported, with 0 read or parse errors.
- **Same data.** All 4,270 demo files checked have the same kill-feed counts, per-slot K/D and number of rounds as the reference. Release matches on all 2,092 matches.
- **Identification** (year, teams, POV, sides) is the same for 98–99.6 % of matches. The differences fall into these groups:
  - **12 files gave no match, and 36 names differ only by a "(2)" suffix.** The old library holds the same demo twice in some places: 32 demos appear in two files. The new database keeps each demo in one match only, and records the second file as another place where it was found. This is intended.
  - **Year, 10 files:** `unknown-year` became `2002`. The old sorting tool repacked loose `.dem` files into zips and stamped them with the date the file had on disk. On re-import, that date reads as an archive timestamp. The research catalogue's `unknown-year` is the more careful answer. Importing from the original collections does not have this problem.
  - **POV, 25 matches:** these are mostly improvements. The POV now follows the name a person wrote in the curated file name (`trance`, `CmdrTom`, `raal`) instead of a joke name the player used for a moment (`yes`, `los`, `harrell`).
  - **Teams and line-ups, about 12 matches:** these are LAN HLTV demos where many clans passed through the server (`[S]`, `[e]`, `[3 D]`) and one-letter tags. Team 1 and team 2 can come out swapped or regrouped. To revisit when matches can be edited in the app (M6).
- **Size:** demo store 16 GB (gzip), database 115 MB. A first import took about 40 minutes with 6 workers. A re-import with the demos already stored took 4 minutes.

## Details

Releases: CS1.0, CS1.1, CS1.3, CS1.4, CS1.5. Reference: `cs-demos/_catalog` (plan, catalogue) and `sorted/_rounds`.

## Totals in the new library

| Table | Rows |
| --- | ---: |
| originals | 2,104 |
| demos | 4,253 |
| matches | 2,092 |
| rounds | 46,476 |
| kills | 279,442 |
| player_names | 10,716 |
| teams | 869 |
| chat | 156,312 |
| demos with a parse error | 0 |

## Files

- Sorted files expected: **2,104**; imported: **2,104**.
- Missing from the import: 0
- Imported but not in the plan: 0
- Files that did not give exactly one match: 12 (e.g. CS1.3/2001/[X3]_[NiP]_[de_nuke]_[HLTV]_[ctt].zip → 0, CS1.3/unknown-year/[ATF]_[JCCT]_[de_cbble]_[HLTV]_[ct].zip → 0, CS1.3/unknown-year/[TSO]_[unknown]_[de_clan2_fire]_[HLTV]_[ct].zip → 0, CS1.3/unknown-year/[W.E.W]_[DoP]_[de_clan2_fire]_[HLTV]_[ct].zip → 0, CS1.3/unknown-year/[X3]_[GB]_[de_clan2_fire]_[HLTV]_[t].zip → 0, CS1.5/2003/[9.esu]_[xPerience.se]_[de_train]_[HLTV]_[t].rar → 0, CS1.5/2003/[GoL]_[matrix]_[de_dust2]_[Hyb]_[ct].zip → 0, CS1.5/2003/[LuLAN]_[KABOM]_[de_dust2]_[walle]_[t].zip → 0)

## Identification (match fields vs the catalogue plan)

| Field | Different | Same |
| --- | ---: | ---: |
| version | 0 | 2,092 |
| year | 10 | 2,082 |
| team1 | 9 | 2,083 |
| team2 | 13 | 2,079 |
| pov | 25 | 2,067 |
| sides | 3 | 2,089 |
| maps | 0 | 2,092 |
| name | 36 | 2,056 |

Examples for **year** (catalogue → new):

- `CS1.3/unknown-year/[NiP]_[Massive Attack]_[de_inferno]_[HLTV]_[t].zip`: `unknown-year` → `2002`
- `CS1.3/unknown-year/[X3]_[DS]_[de_cbble]_[HLTV]_[ct].zip`: `unknown-year` → `2002`
- `CS1.3/unknown-year/[X3]_[DS]_[de_cbble]_[HLTV]_[t].zip`: `unknown-year` → `2002`
- `CS1.3/unknown-year/[X3]_[F]_[de_train]_[HLTV]_[ct].zip`: `unknown-year` → `2002`
- `CS1.3/unknown-year/[X3]_[F]_[de_train]_[HLTV]_[t].zip`: `unknown-year` → `2002`
- `CS1.3/unknown-year/[X3]_[GGA]_[de_prodigy]_[HLTV]_[ct].zip`: `unknown-year` → `2002`
- `CS1.3/unknown-year/[X3]_[GGA]_[de_prodigy]_[HLTV]_[t].zip`: `unknown-year` → `2002`
- `CS1.3/unknown-year/[X3]_[rs]_[de_prodigy]_[HLTV]_[ct].zip`: `unknown-year` → `2002`

Examples for **team1** (catalogue → new):

- `CS1.3/2001/[mTw.pca]_[p]_[de_dust]_[HLTV]_[ctt].ace`: `mTw.pca` → `p`
- `CS1.5/2002/[3 D]_[zEx]_[de_dust2]_[CALConroy]_[t].zip`: `3 D` → `zEx`
- `CS1.5/2002/[S]_[TAU.LanShark]_[de_inferno]_[HLTV]_[t].zip`: `S` → `TAU.LanShark`
- `CS1.5/2002/[S]_[eDu]_[de_dust2]_[HLTV]_[ctt].zip`: `S` → `ds`
- `CS1.5/2002/[S]_[ws]_[de_train]_[HLTV]_[ct].zip`: `S` → `ds`
- `CS1.5/2002/[e]_[HxS]_[de_inferno]_[HLTV]_[t].zip`: `e` → `Adrenaline`
- `CS1.5/2002/[e]_[Jk0]_[de_cbble]_[HLTV]_[ct].zip`: `e` → `NetZone`
- `CS1.5/2002/[e]_[hs]_[de_aztec]_[HLTV]_[ctt].zip`: `e` → `ExS`

Examples for **team2** (catalogue → new):

- `CS1.3/2001/[mTw.pca]_[p]_[de_dust]_[HLTV]_[ctt].ace`: `p` → `mTw.pca`
- `CS1.5/2002/[3 D]_[zEx]_[de_dust2]_[CALConroy]_[t].zip`: `zEx` → `3 D`
- `CS1.5/2002/[S]_[JoE]_[de_aztec]_[HLTV]_[ctt].zip`: `JoE` → `ws`
- `CS1.5/2002/[S]_[TAU.LanShark]_[de_inferno]_[HLTV]_[t].zip`: `TAU.LanShark` → `ws`
- `CS1.5/2002/[S]_[eDu]_[de_dust2]_[HLTV]_[ctt].zip`: `eDu` → `rs`
- `CS1.5/2002/[S]_[ws]_[de_train]_[HLTV]_[ct].zip`: `ws` → `LanMadness`
- `CS1.5/2002/[e]_[BiO]_[de_dust2]_[HLTV]_[ct].zip`: `BiO` → `Adrenaline`
- `CS1.5/2002/[e]_[HxS]_[de_inferno]_[HLTV]_[t].zip`: `HxS` → `e`

Examples for **pov** (catalogue → new):

- `CS1.1/2001/[SK.de]_[SoA]_[de_nuke]_[Untouch]_[ctt].zip`: `[ untouch]` → `[ Untouch]`
- `CS1.1/2001/[swe]_[no]_[de_nuke]_[trance]_[ct].zip`: `MAFIA|trance` → `trance`
- `CS1.1/unknown-year/[if]_[TAMM]_[de_dust2]_[unreal]_[ctt].rar`: `los` → `unreal`
- `CS1.3/2001/[NoTeaM]_[FFA]_[de_aztec]_[CmdrTom]_[ctt].zip`: `[Mafia|XV|CmdrTom]` → `CmdrTom`
- `CS1.3/2002/[cK]_[DoP]_[de_prodigy]_[zany]_[t].rar`: `harrell` → `zany`
- `CS1.4/2002/[GER]_[slo]_[de_dust2]_[raal]_[ctt].rar`: `yes` → `raal`
- `CS1.4/2002/[sb]_[iwa]_[de_clan1_mill]_[destrukt]_[ct].zip`: `flander` → `destrukt`
- `CS1.5/2002/[3D]_[DoP]_[de_cbble]_[Bullseye]_[ct].zip`: `bullseye` → `Bullseye`

Examples for **sides** (catalogue → new):

- `CS1.5/2002/[S]_[TAU.LanShark]_[de_inferno]_[HLTV]_[t].zip`: `t` → `ctt`
- `CS1.5/2002/[S]_[ws]_[de_train]_[HLTV]_[ct].zip`: `ct` → `ctt`
- `CS1.5/2002/[e]_[HxS]_[de_inferno]_[HLTV]_[t].zip`: `t` → `ct`

Examples for **name** (catalogue → new):

- `CS1.3/2002/[sxe]_[malvinas]_[de_aztec]_[HLTV]_[ctt] (2).zip`: `[sxe]_[malvinas]_[de_aztec]_[HLTV]_[ctt] (2).zip` → `[sxe]_[malvinas]_[de_aztec]_[HLTV]_[ctt].zip`
- `CS1.3/unknown-year/[ATF]_[JCCT]_[de_cbble]_[HLTV]_[ct] (2).zip`: `[ATF]_[JCCT]_[de_cbble]_[HLTV]_[ct] (2).zip` → `[ATF]_[JCCT]_[de_cbble]_[HLTV]_[ct].zip`
- `CS1.3/unknown-year/[ATF]_[KhabaL.Com]_[de_aztec]_[HLTV]_[t] (2).zip`: `[ATF]_[KhabaL.Com]_[de_aztec]_[HLTV]_[t] (2).zip` → `[ATF]_[KhabaL.Com]_[de_aztec]_[HLTV]_[t].zip`
- `CS1.3/unknown-year/[NiP]_[Massive Attack]_[de_inferno]_[HLTV]_[t] (2).zip`: `[NiP]_[Massive Attack]_[de_inferno]_[HLTV]_[t] (2).zip` → `[NiP]_[Massive Attack]_[de_inferno]_[HLTV]_[t].zip`
- `CS1.3/unknown-year/[TSO]_[DoP]_[de_prodigy]_[HLTV]_[t] (2).zip`: `[TSO]_[DoP]_[de_prodigy]_[HLTV]_[t] (2).zip` → `[TSO]_[DoP]_[de_prodigy]_[HLTV]_[t].zip`
- `CS1.3/unknown-year/[X3]_[F]_[de_train]_[HLTV]_[ct] (2).zip`: `[X3]_[F]_[de_train]_[HLTV]_[ct] (2).zip` → `[X3]_[F]_[de_train]_[HLTV]_[ct].zip`
- `CS1.3/unknown-year/[X3]_[F]_[de_train]_[HLTV]_[t] (2).zip`: `[X3]_[F]_[de_train]_[HLTV]_[t] (2).zip` → `[X3]_[F]_[de_train]_[HLTV]_[t].zip`
- `CS1.5/2002/[DoP]_[mTw.alternate]_[de_clan1_mill]_[HLTV]_[ctt] (2).zip`: `[DoP]_[mTw.alternate]_[de_clan1_mill]_[HLTV]_[ctt] (2).zip` → `[DoP]_[mTw.alternate]_[de_clan1_mill]_[HLTV]_[ctt].zip`

## Demos, line-ups, kills, rounds

- Matches whose demo set differs: 12 (e.g. CS1.3/2002/[DoP]_[X3]_[de_dust2]_[cHeRn]_[ctt].zip, CS1.3/2002/[mTw]_[RuSh]_[de_dust2]_[Hsa]_[ctt].zip, CS1.5/2002/[3D]_[GoL]_[de_dust2]_[HLTV]_[ctt].zip, CS1.5/2002/[SK]_[asc]_[de_dust2]_[HLTV]_[ctt].zip, CS1.5/2002/[SK]_[esu]_[de_inferno]_[HLTV]_[ctt].zip, CS1.5/2002/[eoL]_[SK]_[de_cbble]_[HLTV]_[ctt].zip, CS1.5/2003/[3D]_[fzer0.inf]_[de_aztec]_[HLTV]_[ctt].zip, CS1.5/2003/[Frontline ' EYE]_[xPerience]_[de_inferno]_[HLTV]_[ctt].zip)
- Matches whose team1/team2 line-ups differ: 12
  - `CS1.5/2002/[3 D]_[zEx]_[de_dust2]_[CALConroy]_[t].zip`: catalogue {"team1": ["3 D | G E F F O N", "3 D | G U E O R G U I E V", "3 D | K I M", "3 D | M I L L E R", "3 D | M O R G A N", "CAL|Conroy"], "team2": ["CAL|Conroy", "zEx | D_CLARK<titus>", "zEx | Garozzo<Volcano>", "zEx | Ja$pal<gladiator>", "zEx | roDriguez<silk>", "zEx | summy<sunman>"]} → new {"team1": ["CAL|Conroy", "zEx | D_CLARK<titus>", "zEx | Garozzo<Volcano>", "zEx | Ja$pal<gladiator>", "zEx | roDriguez<silk>", "zEx | summy<sunman>"], "team2": ["3 D | G E F F O N", "3 D | G U E O R G U I E V", "3 D | K I M", "3 D | M I L L E R", "3 D | M O R G A N", "CAL|Conroy"]}
  - `CS1.5/2002/[S]_[JoE]_[de_aztec]_[HLTV]_[ctt].zip`: catalogue {"team2": ["-|Lw|-Premium", "-|Lw|-Reppa", "Vixxen", "[JoE]ArchAngeL", "[JoE]Bayne<Atrocity>", "[JoE]Bob<woof>", "[JoE]Dirt<PLuMpY>", "[JoE]Dorsey", "[rs]-LeKtriK", "[rs]-icesalmon", "[rs]-sick", "[sr]-firetrout", "tap1 - nick"], "team1": ["#crossfire | eNtropy", "(S) AngRy >:-o", "(S) Angry", "(S) Angry Talents", "(S) Fendie", "(S) FoPPy", "(S) fenix", "(S) worfless", "(S) ~fendie~", "(S) ~worfless~", "(S) ~~~~~fendie~~~~~", "Awptical", "TAU.LanShark | Fontana", "TAU.LanShark | Griffin", "TAU.LanShark | Le", "TAU.LanShark | R e e D", "TAU.LanShark | wakefield", "[JoE]ArchAngeL", "[JoE]Bayne<Atrocity>", "[JoE]Dirt<PLuMpY>", "[rs]-Jaden LanMadness", "[rs]-LeKtriK LanMadness", "[rs]-grasle LanMadness", "[rs]-icesalmon Lanmadness", "[rs]-sickness LanMadness", "empty", "tap1 - trackball ownage", "ws * siniSTEREO", "ws | Jamuraan", "ws | Sp3tz!", "ws | r3d^j5", "ws | theory^", "|CF|-Mr.SmOoTh", "|CF|-Sobe", "|CF|-t o K s i k"]} → new {"team1": ["#crossfire | eNtropy", "Awptical", "TAU.LanShark | Fontana", "TAU.LanShark | Griffin", "TAU.LanShark | Le", "TAU.LanShark | R e e D", "TAU.LanShark | wakefield", "[JoE]ArchAngeL", "[JoE]Bayne<Atrocity>", "[JoE]Dirt<PLuMpY>", "[rs]-Jaden LanMadness", "[rs]-LeKtriK LanMadness", "[rs]-grasle LanMadness", "[rs]-icesalmon Lanmadness", "[rs]-sickness LanMadness", "empty", "tap1 - trackball ownage", "|CF|-Mr.SmOoTh", "|CF|-Sobe", "|CF|-t o K s i k"], "team2": ["(S) AngRy >:-o", "(S) Angry", "(S) Angry Talents", "(S) Fendie", "(S) FoPPy", "(S) fenix", "(S) worfless", "(S) ~fendie~", "(S) ~worfless~", "(S) ~~~~~fendie~~~~~", "-|Lw|-Premium", "-|Lw|-Reppa", "Vixxen", "[rs]-LeKtriK", "[rs]-icesalmon", "[rs]-sick", "[sr]-firetrout", "tap1 - nick", "ws * siniSTEREO", "ws | Jamuraan", "ws | Sp3tz!", "ws | r3d^j5", "ws | theory^"]}
  - `CS1.5/2002/[S]_[TAU.LanShark]_[de_inferno]_[HLTV]_[t].zip`: catalogue {"team2": ["(S) Angry Talents", "(S) FoPPy", "(S) fenix", "(S) worf|ess.", "CHANGE MAP", "OJA|-DirtyGorilla", "OJA|-bobear", "OJA|-s133p1ngt1g3r", "TAU.LanShark | Fontana", "TAU.LanShark | JEONGGGGG", "TAU.LanShark | Jeong", "TAU.LanShark | Le", "TAU.LanShark | R e e D", "TAU.LanShark | wakefield", "[JoE]Billy<el_elephante>", "[JoE]Bob<woof>", "[JoE]Dorsey", "[rs]-Jaden LanMadness", "[rs]-LeKtriK LanMadness", "[rs]-grasle LanMadness", "[rs]-icesalmon Lanmadness", "[rs]-sickness LanMadness", "aEnergy | theory^", "bb", "ds ~ Iron", "ds ~ Rodriguez [Glass-Joe]", "ds ~ evenflow [ire]", "ds ~ zarac <peeny> [swe]", "empty", "tap1 - nick", "tap1 - smash", "tap1 - trackball ownage", "ws * siniSTEREO", "ws | Jamuraan", "ws | r3d^j5"], "team1": ["#crossfire | Awptical", "#crossfire | eNtropy", "*ViGoRuS*", ".:iOn:.PrescottX", "Markilous", "OJA|-Drowning.Swordfish", "OJA|-Piranah", "OJA|-Swordfish", "OJA|-bobear", "OJA|-s133p1ngt1g3r", "To0n<tango>", "[JoE]ArchAngeL", "[JoE]Bayne<Atrocity>", "[rs]-Jaden LanMadness", "[rs]-LeKtriK", "[rs]-sickness LanMadness", "^vibe", "bloogy", "ds ~ Hadley [Iron]", "ds ~ Rodriguez [Glass-Joe]", "ds ~ evenflow [ire]", "ds ~ su", "ds ~ zarac <peeny> [swe]", "eDu | Vujita", "eDu^Brandon", "eDu^crutch", "fabolous", "ws * bink bink", "ws * siniSTEREO", "ws | Jamuraan", "ws | Sp3tz!", "ws | r3d^j5", "ws | theory^", "|CF|-Mr.SmOoTh", "|CF|-t o K s i k"]} → new {"team1": ["#crossfire | Awptical", "#crossfire | eNtropy", "Markilous", "OJA|-Drowning.Swordfish", "OJA|-Piranah", "OJA|-Swordfish", "OJA|-bobear", "OJA|-s133p1ngt1g3r", "TAU.LanShark | Fontana", "TAU.LanShark | JEONGGGGG", "TAU.LanShark | Jeong", "TAU.LanShark | Le", "TAU.LanShark | R e e D", "TAU.LanShark | wakefield", "To0n<tango>", "[JoE]ArchAngeL", "[JoE]Bayne<Atrocity>", "[rs]-Jaden LanMadness", "[rs]-LeKtriK", "[rs]-sickness LanMadness", "^vibe", "bloogy", "eDu | Vujita", "eDu^Brandon", "eDu^crutch", "fabolous", "|CF|-Mr.SmOoTh", "|CF|-t o K s i k"], "team2": ["(S) Angry Talents", "(S) FoPPy", "(S) fenix", "(S) worf|ess.", ".:iOn:.PrescottX", "CHANGE MAP", "OJA|-DirtyGorilla", "OJA|-bobear", "OJA|-s133p1ngt1g3r", "[JoE]Billy<el_elephante>", "[JoE]Bob<woof>", "[JoE]Dorsey", "[rs]-Jaden LanMadness", "[rs]-LeKtriK LanMadness", "[rs]-grasle LanMadness", "[rs]-icesalmon Lanmadness", "[rs]-sickness LanMadness", "aEnergy | theory^", "bb", "ds ~ Iron", "ds ~ Rodriguez [Glass-Joe]", "ds ~ evenflow [ire]", "ds ~ zarac <peeny> [swe]", "empty", "tap1 - nick", "tap1 - smash", "tap1 - trackball ownage", "ws * bink bink", "ws * siniSTEREO", "ws | Jamuraan", "ws | Sp3tz!", "ws | r3d^j5", "ws | theory^"]}
  - `CS1.5/2002/[S]_[eDu]_[de_dust2]_[HLTV]_[ctt].zip`: catalogue {"team1": ["(S) Angry", "(S) Angry Talents", "(S) Angry mofo", "(S) Fendie", "(S) Fendie~", "(S) FoPPy", "(S) fenix", "(S) worfless", "(S) ~fendie~", "BabyWolf", "CowboyWolf", "Markilous", "MindlessWolf", "PIayer", "SilverWolf", "SonicWolf", "TAU.LanShark | Fontana", "TAU.LanShark | Griffin", "TAU.LanShark | JE O  N   G", "TAU.LanShark | Le", "TAU.LanShark | R e e D", "TAU.LanShark | wakefield", "[JoE]Dorsey", "[rs]-Jaden", "[rs]-Jaden LanMadness", "[rs]-JadenanMadness", "[rs]-LeKtriK", "[rs]-LeKtriK LanMadness", "[rs]-grasle LanMadness", "[rs]-icesalmon", "[rs]-icesalmon Lanmadness", "[rs]-sick", "[rs]-sickness LanMadness", "^vibe", "aEnergy | theory^", "cfg", "disputed ~ Rodriguez Glass-Joe", "ds ~ Hadley [Iron]", "ds ~ Iron [ger]", "ds ~ Rodriguez [Glass-Joe]", "ds ~ evenflow [ire]", "ds ~ su", "ds ~ su [black]", "ds ~ zarac <peeny> [swe]", "eDu^Brandon", "eDu^Vujita", "eDu^crutch", "femalegamer *", "nub", "tap1 - co|tz", "tap1 - nick", "tap1 - ranger", "ws * bink bink", "ws * siniSTEREO", "ws | Jamuraan", "ws | Sp3tz!", "ws | r3d@J5", "ws | r3d^j5", "ws | theory^", "x.Iron"], "team2": ["(S) AngRy >:-o", "(S) worf|ess.", "(S) ~fendie~", "-|Lw|-Premium", "BabyWolf", "CHANGE MAP TO CBBLE", "CHANGE THE MAP", "CowboyWolf", "MindlessWolf", "OJA|-s133p1ngt1g3r", "SilverWolf", "Sonicwolf", "TAU.LanShark | Fontana", "TAU.LanShark | Le", "[rs]-Jaden LanMadness", "[rs]-LeKtriK LanMadness", "[rs]-grasle LanMadness", "[rs]-icesalmon", "[rs]-icesalmon Lanmadness", "bloggy", "cfg", "eDu^BRandon", "eDu^International house of Vu", "eDu^Markilous", "eDu^The Legend that is Vu", "eDu^Vujita", "eDu^crutch", "eDu^vibe", "tap1 - frzr7", "tap1 - orbflux", "tap1 - smash", "ws | Sp3tz!", "ws | r3d^j5"]} → new {"team1": ["(S) FoPPy", "(S) fenix", "BabyWolf", "CowboyWolf", "Markilous", "MindlessWolf", "SilverWolf", "SonicWolf", "TAU.LanShark | Fontana", "TAU.LanShark | Le", "TAU.LanShark | R e e D", "[rs]-sickness LanMadness", "^vibe", "cfg", "disputed ~ Rodriguez Glass-Joe", "ds ~ Hadley [Iron]", "ds ~ Iron [ger]", "ds ~ Rodriguez [Glass-Joe]", "ds ~ evenflow [ire]", "ds ~ su", "ds ~ su [black]", "ds ~ zarac <peeny> [swe]", "eDu^Brandon", "eDu^Vujita", "eDu^crutch", "femalegamer *", "nub", "tap1 - co|tz", "tap1 - nick", "tap1 - ranger", "ws * siniSTEREO", "ws | Jamuraan", "ws | theory^"], "team2": ["(S) AngRy >:-o", "(S) Angry", "(S) Angry Talents", "(S) Angry mofo", "(S) Fendie", "(S) Fendie~", "(S) FoPPy", "(S) fenix", "(S) worfless", "(S) worf|ess.", "(S) ~fendie~", "BabyWolf", "CHANGE MAP TO CBBLE", "CHANGE THE MAP", "CowboyWolf", "MindlessWolf", "OJA|-s133p1ngt1g3r", "PIayer", "SilverWolf", "Sonicwolf", "TAU.LanShark | Fontana", "TAU.LanShark | Le", "[JoE]Dorsey", "[rs]-Jaden", "[rs]-Jaden LanMadness", "[rs]-JadenanMadness", "[rs]-LeKtriK", "[rs]-LeKtriK LanMadness", "[rs]-grasle LanMadness", "[rs]-icesalmon", "[rs]-icesalmon Lanmadness", "[rs]-sick", "[rs]-sickness LanMadness", "bloggy", "cfg", "tap1 - frzr7", "tap1 - orbflux", "tap1 - smash", "ws | Sp3tz!", "ws | r3d^j5", "x.Iron"]}
  - `CS1.5/2002/[S]_[ws]_[de_train]_[HLTV]_[ct].zip`: catalogue {"team1": ["(S) worfless", "-|Lw|-FiRe-DaDy", "-|Lw|-Premium", "-|Lw|-Reppa", ".:iOn:.Ghetto Fabulous", "Markilous", "OJA|-Drowning.Swordfish", "RepWolf", "TAU.LanShark | Fontana", "TAU.LanShark | Gr", "TAU.LanShark | Griffin", "TAU.LanShark | JEONGGGGGGGGGGGG", "TAU.LanShark | Le", "TAU.LanShark | R e e D", "TAU.LanShark | wakefield", "[JoE]ArchAngeL", "[rs]-Jaden LanMadness", "[rs]-JadenanMadness", "[rs]-LeKtriK", "[rs]-LeKtriK LanMadness", "[rs]-grasle LanMadness", "[rs]-icesalmon Lanmadness", "[rs]-sick", "[rs]-sickness LanMadness", "^vibe", "bl0ogy", "bloggy", "cfg", "disputed ~ Rodriguez Glass-Joe", "ds ~ Hadley [Iron]", "ds ~ Rodriguez [Glass-Joe]", "ds ~ evenflow [ire]", "ds ~ hi", "ds ~ su [black]", "ds ~ su [blackanese]", "ds ~ zarac <peeny> [swe]", "eDu | Vujita", "eDu^Brandon", "eDu^crutch", "tap1 - co|tz", "tap1 - frzr7", "tap1 - nick", "tap1 - ranger", "tap1 - smash", "thomas", "ws * siniSTEREO", "ws | Jamuraan", "ws | Sp3tz", "ws | r3d^j5", "ws | theory^"], "team2": ["#iOncs | d|stur|3ed", "(S) Angry", "(S) Fendie~~", "(S) FoPPy", "(S) fenix", "-|Lw|-Nero", ".:iOn:.PrescottX", ".:iOn:.Sereno", ".:iOn:.eXoduS", "OJA|-bobear", "TAU.LanShark | Fontana", "Vixxen", "[JoE]Bayne<Atrocity>", "[JoE]Bob<woof>", "[JoE]Dorsey", "[rs]-grasle LanMadness", "[rs]-icesalmon", "bloogy", "disputed ~ Rodriguez Glass-Joe", "ds ~ Hadley [Iron]", "ds ~ evenflow [ire]", "ds ~ zarac <peeny> [swe]", "fabolous", "penii", "tap1 - nick?", "tap1 - ranger", "ws * siniSTEREO", "ws | Jamuraan", "ws | Sp3tz!", "ws | r3d@J5", "ws | r3d^j5", "ws | theory^"]} → new {"team1": ["(S) worfless", "-|Lw|-FiRe-DaDy", "-|Lw|-Premium", "-|Lw|-Reppa", ".:iOn:.Ghetto Fabulous", "Markilous", "OJA|-Drowning.Swordfish", "RepWolf", "TAU.LanShark | Gr", "TAU.LanShark | Le", "TAU.LanShark | R e e D", "TAU.LanShark | wakefield", "[rs]-LeKtriK", "[rs]-sickness LanMadness", "^vibe", "bl0ogy", "bloggy", "disputed ~ Rodriguez Glass-Joe", "ds ~ Hadley [Iron]", "ds ~ Rodriguez [Glass-Joe]", "ds ~ evenflow [ire]", "ds ~ hi", "ds ~ su [black]", "ds ~ su [blackanese]", "ds ~ zarac <peeny> [swe]", "eDu | Vujita", "eDu^Brandon", "eDu^crutch", "tap1 - co|tz", "tap1 - frzr7", "tap1 - nick", "tap1 - ranger", "tap1 - smash", "thomas", "ws * siniSTEREO", "ws | Jamuraan", "ws | Sp3tz", "ws | r3d^j5", "ws | theory^"], "team2": ["#iOncs | d|stur|3ed", "(S) Angry", "(S) Fendie~~", "(S) FoPPy", "(S) fenix", "-|Lw|-Nero", ".:iOn:.PrescottX", ".:iOn:.Sereno", ".:iOn:.eXoduS", "OJA|-bobear", "Vixxen", "[JoE]Bayne<Atrocity>", "[JoE]Bob<woof>", "[JoE]Dorsey", "[rs]-Jaden LanMadness", "[rs]-JadenanMadness", "[rs]-LeKtriK LanMadness", "[rs]-grasle LanMadness", "[rs]-icesalmon", "[rs]-icesalmon Lanmadness", "[rs]-sickness LanMadness", "bloogy", "disputed ~ Rodriguez Glass-Joe", "ds ~ Hadley [Iron]", "ds ~ evenflow [ire]", "ds ~ zarac <peeny> [swe]", "fabolous", "penii", "tap1 - nick?", "tap1 - ranger"]}
  - `CS1.5/2002/[e]_[BiO]_[de_dust2]_[HLTV]_[ct].zip`: catalogue {"team1": ["-e. enmity", "-e. envy", "-e. revenge", "-e. vengeance", "Adrenaline ~ Donkey_Punch", "Adrenaline ~ Gosu^_^", "Adrenaline ~ OwNz", "Adrenaline ~ Zeus", "Adrenaline ~ butthead007", "Adrenaline ~ g3n", "BorderPatrol | 187", "BorderPatrol | Dorsey", "BorderPatrol | GunAce", "BorderPatrol | Tiny", "BorderPatrol | optical", "DiscoBob42", "F^Funk @ NetZone", "F^Skinner @ NetZone", "I Sux0rz", "Player", "[62Fe]dillon", "[hs]-20_to_life", "[hs]-Surge", "brazen^", "h0b", "trauma^"], "team2": ["F^Zetterlund @ NetZone", "IAM |midget|", "IAM |repro|", "Riot-Squad | daywa1ker LM", "[BiO]Ball<Ball>", "[BiO]Dj^Trip", "[BiO]Loki", "[BiO]Loki<Loki>", "[BiO]Malakai", "[BiO]SlicedAcid", "[BiO]Wilhoit<Malakai>", "[TAU]-RJ", "[hs]-20_to_life", "[hs]-Joeeeey", "[hs]-dillon", "joe^", "trauma^"]} → new {"team1": ["Adrenaline ~ OwNz", "BorderPatrol | 187", "BorderPatrol | Dorsey", "BorderPatrol | GunAce", "BorderPatrol | Tiny", "BorderPatrol | optical", "DiscoBob42", "F^Funk @ NetZone", "F^Skinner @ NetZone", "I Sux0rz", "[62Fe]dillon", "[hs]-20_to_life", "[hs]-Surge", "brazen^", "h0b", "trauma^"], "team2": ["-e. enmity", "-e. envy", "-e. revenge", "-e. vengeance", "Adrenaline ~ Donkey_Punch", "Adrenaline ~ Gosu^_^", "Adrenaline ~ OwNz", "Adrenaline ~ Zeus", "Adrenaline ~ butthead007", "Adrenaline ~ g3n", "F^Zetterlund @ NetZone", "IAM |midget|", "IAM |repro|", "Player", "Riot-Squad | daywa1ker LM", "[TAU]-RJ", "[hs]-20_to_life", "[hs]-Joeeeey", "[hs]-dillon", "joe^", "trauma^"]}
  - `CS1.5/2002/[e]_[HxS]_[de_inferno]_[HLTV]_[t].zip`: catalogue {"team1": ["-Jk0-eViL jEsTeR", "-e revenge", "-e. enmity", "-e. envy", "-e. forlorn", "-e. revenge", "-e. vengeance", "Adrenaline ~ Gosu^_^", "Adrenaline ~ OwNz", "Adrenaline ~ Zeus", "Adrenaline ~ butthead007", "Adrenaline ~ g3n", "BorderPatrol | 187", "BorderPatrol | Dorsey", "BorderPatrol | GunAce", "BorderPatrol | optical", "F^Fender @ NetZone", "F^Funk @ NetZone", "F^Zetterlund @ NetZone", "F^bob @ NetZone", "F^tissue? @ NetZone", "Puff the magic Dragon", "Riot-Squad | cayle LM", "Riot-Squad | fl4zh LM", "Riot-Squad | no1special LM", "TAU | beavis007", "Untouchables | Chern", "Untouchables | HeavyArms", "Untouchables | Sladek", "[TAU]-tRiGGa-", "[hs]-TenderFoot", "brazen^", "trauma^", "untouchables | -tRiGGa-"], "team2": ["-e. envy", "-e. vengeance", "DiscoBob42", "Neo", "Riot-Squad | daywa1ker LM", "Riot-Squad | icesalmon LM", "[HxS]UnKn0wN", "[HxS]ViperX", "[TAU]-RJ", "[TX]-JameZ", "[hs]-20_to_life", "[hs]-Joeeeey", "[hs]-Joey", "[hs]-Surge", "[hs]-TenderFoot", "[hs]-dillon", "allah"]} → new {"team1": ["-e. enmity", "-e. forlorn", "-e. revenge", "Adrenaline ~ g3n", "Riot-Squad | cayle LM", "Riot-Squad | fl4zh LM", "Riot-Squad | no1special LM", "[TAU]-tRiGGa-", "[hs]-TenderFoot", "brazen^", "trauma^"], "team2": ["-Jk0-eViL jEsTeR", "-e revenge", "-e. enmity", "-e. envy", "-e. forlorn", "-e. revenge", "-e. vengeance", "Adrenaline ~ Gosu^_^", "Adrenaline ~ OwNz", "Adrenaline ~ Zeus", "Adrenaline ~ butthead007", "Adrenaline ~ g3n", "BorderPatrol | 187", "BorderPatrol | Dorsey", "BorderPatrol | GunAce", "BorderPatrol | optical", "F^Fender @ NetZone", "F^Funk @ NetZone", "F^Zetterlund @ NetZone", "F^bob @ NetZone", "F^tissue? @ NetZone", "Puff the magic Dragon", "Riot-Squad | daywa1ker LM", "Riot-Squad | icesalmon LM", "TAU | beavis007", "Untouchables | Chern", "Untouchables | HeavyArms", "Untouchables | Sladek", "[TAU]-RJ", "[TX]-JameZ", "allah", "untouchables | -tRiGGa-"]}
  - `CS1.5/2002/[e]_[Jk0]_[de_cbble]_[HLTV]_[ct].zip`: catalogue {"team2": ["-Jk0-Nuyen", "-Jk0-RATT", "-Jk0-Rty^BrokenHeadphones^", "-Jk0-eViL jEsTeR", "-Jk0-trancis", "Adrenaline ~ butthead007", "Puff the magic Dragon"], "team1": ["-e. enmity", "-e. envy", "-e. forlorn", "-e. revenge", "-e. vengeance", "F^Eraser @ NetZone", "F^billyboy @ NetZone", "g"]} → new {"team2": ["-e. enmity", "-e. envy", "-e. forlorn", "-e. revenge", "-e. vengeance", "Adrenaline ~ butthead007", "F^Eraser @ NetZone", "F^billyboy @ NetZone", "Puff the magic Dragon", "g"]}
- Demos checked: 4,270; kill-feed count differs: 0; per-slot K/D differs: 0
- Rounds per demo vs `_rounds`: same 4,270, different 0, no reference 0
