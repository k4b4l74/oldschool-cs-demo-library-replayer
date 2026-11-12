"""API response models. The frontend's TypeScript types are generated from
these (``python3 tasks.py api-types``), so changing a field here is a typed
change on both sides."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Health(BaseModel):
    app: str
    version: str
    schema_version: int


class Facet(BaseModel):
    value: str
    count: int


class LibraryStats(BaseModel):
    matches: int
    demos: int
    rounds: int
    kills: int
    player_names: int
    teams: int
    releases: list[Facet]
    maps: list[Facet]
    years: list[Facet]


class MatchSummary(BaseModel):
    id: int
    release: str | None
    year: str | None
    year_basis: str | None
    file_date: str | None  # earliest .dem member timestamp: a file write time, never a played date
    map: str | None
    team1: str | None
    team2: str | None
    pov: str | None
    sides: str | None
    servers: list[str]
    scores: str
    demos: int
    duration_s: int
    kills: int


class MatchPage(BaseModel):
    total: int
    page: int
    size: int
    items: list[MatchSummary]


class LineupPlayer(BaseModel):
    name_id: int
    name: str
    steamid: str
    aliases: list[str]
    kills: int
    deaths: int
    headshots: int


class Lineup(BaseModel):
    key: str
    tag: str | None
    players: list[LineupPlayer]


class MatchDemo(BaseModel):
    sha1: str
    part: int
    member: str
    label: str
    recorder_kind: str | None
    recorder_name: str | None
    net_protocol: int | None
    duration_s: float | None
    kills: int | None
    rounds: int
    final_score: dict[str, int]
    engine: str | None  # install that would play it
    play_problem: str | None  # why it cannot be played, when no install fits


class Source(BaseModel):
    file_name: str
    source_path: str
    member: str


class MatchDetail(BaseModel):
    summary: MatchSummary
    release_basis: list[str]
    team_basis: str | None
    library_name: str
    lineups: list[Lineup]
    demos: list[MatchDemo]
    sources: list[Source]


class Kill(BaseModel):
    t: float
    killer: str | None
    killer_id: int | None
    killer_side: str | None
    victim: str | None
    victim_id: int | None
    victim_side: str | None
    weapon: str | None
    headshot: bool | None


class Round(BaseModel):
    no: int
    start: float
    start_basis: str
    end: float
    winner: str | None
    reason: str | None
    score_ct: int | None
    score_t: int | None
    kills: list[Kill]


class DemoRounds(BaseModel):
    sha1: str
    rounds: list[Round]
    other_kills: int


class PlayerSummary(BaseModel):
    name_id: int
    name: str
    steamid: str
    matches: int
    kills: int
    deaths: int


class PlayerMatch(BaseModel):
    match: MatchSummary
    team_key: str
    kills: int
    deaths: int
    headshots: int


class PlayerDetail(BaseModel):
    player: PlayerSummary
    headshots: int
    same_steamid: list[PlayerSummary]  # other names seen with the same SteamID
    same_name: list[PlayerSummary]  # the same name with another (or no) SteamID: maybe not the same person
    matches: list[PlayerMatch]


class TeamSummary(BaseModel):
    id: int
    tag: str
    matches: int


class TeamDetail(BaseModel):
    team: TeamSummary
    players: list[PlayerSummary]  # names seen in this team's line-ups, most matches first
    matches: list[MatchSummary]


# ---------------------------------------------------------------- engines


class Engine(BaseModel):
    id: int
    name: str
    path: str
    source: str  # 'scan' or 'manual'
    enabled: bool
    missing: bool
    status: str  # ok / warning / broken / unchecked
    problems: list[str]
    kind: str | None
    build: str | None
    protocol: int | None
    release: str | None
    seek_method: str | None
    video: str | None
    args: list[str]
    detected: dict[str, Any]
    overrides: dict[str, Any]


class EngineRoute(BaseModel):
    protocol: int
    release: str
    demos: int
    engine_id: int | None  # install that plays it now
    chosen_id: int | None  # set by the user; None = automatic
    how: str
    candidate_ids: list[int]


class EnginesView(BaseModel):
    engines: list[Engine]
    routes: list[EngineRoute]


class EnginePatch(BaseModel):
    """Fields to change; null puts a field back to the detected value."""

    protocol: int | None = None
    release: str | None = None
    seek_method: str | None = None
    video: str | None = None
    args: list[str] | None = None
    kind: str | None = None
    enabled: bool | None = None


class EngineAdd(BaseModel):
    path: str


class RouteChange(BaseModel):
    protocol: int
    release: str
    engine_id: int | None  # None = back to automatic


class ScanResult(BaseModel):
    found: int
    roots: int


class Root(BaseModel):
    path: str
    source: str  # settings / default / environment
    exists: bool


class Bind(BaseModel):
    key: str  # the engine's key name, lower case (f5, kp_plus, mwheelup, a…)
    command: str  # console command(s), ';'-separated, no double quote


class ControlAction(BaseModel):
    id: str
    group: str
    label: str
    command: str
    defaults: list[str]
    hint: str


class ControlGroup(BaseModel):
    id: str
    label: str
    hint: str


class Settings(BaseModel):
    engine_roots: list[str]
    map_folders: list[str]
    won_resolution: str
    windowed: bool
    seek_framerate: float
    seek_retime_factor: float
    welcomed: bool
    binds: list[Bind]
    controls: dict[str, list[str]]  # every action: [key, alternate]
    actions: list[ControlAction]
    control_groups: list[ControlGroup]
    effective_roots: list[Root]
    won_modes: list[str]
    data_dir: str


class SettingsChange(BaseModel):
    engine_roots: list[str] | None = None
    map_folders: list[str] | None = None
    won_resolution: str | None = None
    windowed: bool | None = None
    seek_framerate: float | None = None
    seek_retime_factor: float | None = None
    welcomed: bool | None = None
    binds: list[Bind] | None = None
    controls: dict[str, list[str]] | None = None


class PlayRequest(BaseModel):
    sha1: str
    seek: float | None = None  # demo-clock seconds; None or < 1 plays from the start


class PlayResponse(BaseModel):
    engine: str
    engine_path: str
    chosen: str
    release: str | None
    protocol: int | None
    seek: float | None
    seek_method: str | None
    window: str | None
    map_note: str | None
    command: list[str]


# ---------------------------------------------------------------- imports (M4)


class ImportCounts(BaseModel):
    imported: int = 0
    already: int = 0
    no_demo: int = 0
    failed: int = 0
    matches: int = 0
    demos_new: int = 0


class Job(BaseModel):
    id: int
    kind: str  # import | reanalyse
    origin: str | None  # drop | folder | retry (imports)
    state: str  # queued | running | done | failed | cancelled
    paths: list[str]  # what was given (Windows paths when on a drive)
    copy_demos: bool
    done: int
    total: int
    current: str | None
    counts: ImportCounts
    error: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None


class ImportFolder(BaseModel):
    path: str
    copy_demos: bool
    last_job_id: int
    last_run: str


class ImportsView(BaseModel):
    drop_dir: str
    active: list[Job]  # running first, then queued
    recent: list[Job]
    folders: list[ImportFolder]  # folders imported from the app: can be checked again for new files
    open_failures: int  # failed files not retried since
    outdated_files: int  # files read by an older version of the app (re-analyse)
    library_files: int


class MatchLink(BaseModel):
    id: int
    name: str


class JobFile(BaseModel):
    id: int
    path: str
    label: str
    status: str  # imported | already | no-demo | failed | missing | reanalysed
    matches: list[MatchLink]
    demos_new: int
    message: str | None
    moved_to: str | None
    retry_job_id: int | None
    original_id: int | None


class JobDetail(BaseModel):
    job: Job
    status_counts: dict[str, int]
    files: list[JobFile]
    total_files: int
    page: int
    size: int


class FolderImport(BaseModel):
    path: str
    copy_demos: bool = True


class Reanalyse(BaseModel):
    only_outdated: bool = False


class Uploaded(BaseModel):
    name: str
    size: int
