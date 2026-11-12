-- 0001: initial schema (see docs/ARCHITECTURE.md §9).
-- Conventions:
--   * names and tags are stored exactly as printed in the demo (*_as_printed);
--     nothing is merged automatically, merges are explicit user actions;
--   * every estimated value has a *_basis column saying where it comes from;
--   * times inside a demo are demo-clock seconds (REAL), never dates;
--   * timestamps of app events are ISO-8601 UTC text.

-- Files the user dropped, kept untouched in store/originals when enabled.
CREATE TABLE originals (
    id            INTEGER PRIMARY KEY,
    sha1          TEXT NOT NULL UNIQUE,
    file_name     TEXT NOT NULL,
    size          INTEGER NOT NULL,
    source_path   TEXT NOT NULL,              -- where it was imported from
    mode          TEXT NOT NULL CHECK (mode IN ('referenced', 'copied', 'moved')),
    kept_path     TEXT,                       -- copy inside store/originals ('copied'/'moved'), NULL when referenced
    imported_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    status        TEXT NOT NULL DEFAULT 'done' CHECK (status IN ('done', 'failed', 'no-demo')),
    demo_count    INTEGER NOT NULL DEFAULT 0,
    errors        TEXT                        -- JSON list of archive warnings
);

-- Every leaf member found while walking an original (nested archives flattened into chain).
CREATE TABLE archive_members (
    id            INTEGER PRIMARY KEY,
    original_id   INTEGER NOT NULL REFERENCES originals(id) ON DELETE CASCADE,
    chain         TEXT NOT NULL DEFAULT '',   -- containing members, outermost first, '/'-joined
    name          TEXT NOT NULL,
    size          INTEGER,
    mtime         TEXT,
    mtime_basis   TEXT,                       -- 'archive_member' | 'filesystem' | NULL
    demo_sha1     TEXT REFERENCES demos(sha1),
    text_content  TEXT                        -- small .txt/.nfo members, decoded
);
CREATE INDEX archive_members_original ON archive_members(original_id);
CREATE INDEX archive_members_demo ON archive_members(demo_sha1);

-- One row per distinct .dem file (content-addressed).
CREATE TABLE demos (
    sha1            TEXT PRIMARY KEY,
    size            INTEGER NOT NULL,
    store_path      TEXT NOT NULL,
    demo_protocol   INTEGER,
    net_protocol    INTEGER,
    map             TEXT,
    game_dir        TEXT,
    map_crc         INTEGER,
    duration_s      REAL,
    kill_count      INTEGER,
    release         TEXT,                     -- CS1.0 … CS1.6, beta…
    release_basis   TEXT,
    recorder_kind   TEXT CHECK (recorder_kind IN ('hltv', 'player', 'unknown')),
    recorder_slot   INTEGER,
    server_name     TEXT,                     -- svc_serverinfo hostname
    viewport_w      INTEGER,
    viewport_h      INTEGER,
    parse_version   INTEGER NOT NULL DEFAULT 0,
    parse_error     TEXT,
    analysis        TEXT                      -- JSON: problems, fingerprint, usermsgs, teams, scores, server names
);
CREATE INDEX demos_map ON demos(map);
CREATE INDEX demos_release ON demos(release);

CREATE TABLE teams (
    id                INTEGER PRIMARY KEY,
    tag_as_printed    TEXT NOT NULL,
    norm_tag          TEXT NOT NULL
);
CREATE INDEX teams_norm ON teams(norm_tag);

CREATE TABLE matches (
    id              INTEGER PRIMARY KEY,
    original_id     INTEGER NOT NULL REFERENCES originals(id),   -- where it was first found
    map             TEXT,                     -- maps joined with '+' when a group spans several
    team1_id        INTEGER REFERENCES teams(id),
    team2_id        INTEGER REFERENCES teams(id),
    release         TEXT,
    release_basis   TEXT,                     -- JSON list
    year_est        TEXT,                     -- 'YYYY' or 'unknown-year'
    year_basis      TEXT,
    pov             TEXT,                     -- recorder alias, or 'HLTV'
    sides           TEXT,                     -- 'ct' | 't' | 'ctt' | 'unknown' (team1 / POV player)
    team_basis      TEXT,
    library_name    TEXT NOT NULL,            -- [T1]_[T2]_[map]_[pov]_[side].ext, as in the sorted library
    servers         TEXT,                     -- JSON list of hostnames
    scores          TEXT,                     -- JSON list, last score per demo file
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX matches_map ON matches(map);
CREATE INDEX matches_original ON matches(original_id);

CREATE TABLE match_demos (
    match_id      INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    demo_sha1     TEXT NOT NULL REFERENCES demos(sha1),
    part_no       INTEGER NOT NULL,
    label         TEXT,                       -- e.g. 'aAa CT', 'OT'
    PRIMARY KEY (match_id, demo_sha1)
);
CREATE UNIQUE INDEX match_demos_demo ON match_demos(demo_sha1);   -- a demo belongs to one match

-- A person, as decided by the user. Starts empty: names are not people.
CREATE TABLE players (
    id            INTEGER PRIMARY KEY,
    display_name  TEXT NOT NULL,
    note          TEXT
);

-- A name (and SteamID when known, '' otherwise) seen in demos; may be linked to a player by the user.
CREATE TABLE player_names (
    id              INTEGER PRIMARY KEY,
    name_as_printed TEXT NOT NULL,
    steamid         TEXT NOT NULL DEFAULT '',
    player_id       INTEGER REFERENCES players(id) ON DELETE SET NULL,
    UNIQUE (name_as_printed, steamid)
);
CREATE INDEX player_names_player ON player_names(player_id);

-- One row per player slot in a demo. K/D counts follow the slot (as the parser does).
CREATE TABLE demo_players (
    demo_sha1       TEXT NOT NULL REFERENCES demos(sha1) ON DELETE CASCADE,
    slot            INTEGER NOT NULL,
    player_name_id  INTEGER NOT NULL REFERENCES player_names(id),   -- last name used in the slot
    names           TEXT NOT NULL,            -- JSON list of every name the slot used
    is_hltv         INTEGER NOT NULL DEFAULT 0,
    is_bot          INTEGER NOT NULL DEFAULT 0,
    sides           TEXT,                     -- JSON list, e.g. ["CT","TERRORIST"]
    kills           INTEGER NOT NULL DEFAULT 0,
    deaths          INTEGER NOT NULL DEFAULT 0,
    headshots       INTEGER NOT NULL DEFAULT 0,
    teamkills       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (demo_sha1, slot)
);

-- Line-ups of a match (team1 / team2 / other clusters), as identified at import.
CREATE TABLE match_players (
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    team_key        TEXT NOT NULL,            -- 'team1' | 'team2' | other tag
    player_name_id  INTEGER NOT NULL REFERENCES player_names(id),
    aliases         TEXT,                     -- JSON list of other names in the same slot
    PRIMARY KEY (match_id, team_key, player_name_id)  -- a name can appear in both line-ups (slot reuse)
);
CREATE INDEX match_players_name ON match_players(player_name_id);
CREATE INDEX demo_players_name ON demo_players(player_name_id);

CREATE TABLE rounds (
    id            INTEGER PRIMARY KEY,
    demo_sha1     TEXT NOT NULL REFERENCES demos(sha1) ON DELETE CASCADE,
    no            INTEGER NOT NULL,
    start_t       REAL NOT NULL,
    start_basis   TEXT NOT NULL,
    end_t         REAL NOT NULL,
    winner        TEXT CHECK (winner IN ('CT', 'TERRORIST') OR winner IS NULL),
    reason        TEXT,
    score_ct      INTEGER,
    score_t       INTEGER,
    UNIQUE (demo_sha1, no)
);

CREATE TABLE kills (
    id              INTEGER PRIMARY KEY,
    demo_sha1       TEXT NOT NULL REFERENCES demos(sha1) ON DELETE CASCADE,
    round_id        INTEGER REFERENCES rounds(id) ON DELETE SET NULL,
    t               REAL NOT NULL,
    killer_name_id  INTEGER REFERENCES player_names(id),
    victim_name_id  INTEGER REFERENCES player_names(id),
    weapon          TEXT,
    headshot        INTEGER,
    killer_side     TEXT,
    victim_side     TEXT
);
CREATE INDEX kills_demo ON kills(demo_sha1, t);
CREATE INDEX kills_killer ON kills(killer_name_id);
CREATE INDEX kills_victim ON kills(victim_name_id);

CREATE TABLE chat (
    id              INTEGER PRIMARY KEY,
    demo_sha1       TEXT NOT NULL REFERENCES demos(sha1) ON DELETE CASCADE,
    t               REAL NOT NULL,
    sender_entity   INTEGER,                  -- entity index = player slot + 1
    text            TEXT NOT NULL
);
CREATE INDEX chat_demo ON chat(demo_sha1, t);

-- Game installs the app can launch (docs/ARCHITECTURE.md §8).
CREATE TABLE engines (
    id            INTEGER PRIMARY KEY,
    path          TEXT NOT NULL UNIQUE,
    kind          TEXT NOT NULL CHECK (kind IN ('won', 'steam')),
    build         TEXT,                       -- e.g. '1.1.0.8'
    protocols     TEXT,                       -- JSON list of network protocols it plays
    releases      TEXT,                       -- JSON list, e.g. ["CS1.3"]
    status        TEXT NOT NULL DEFAULT 'unchecked' CHECK (status IN ('unchecked', 'ok', 'warning', 'broken')),
    status_detail TEXT,
    last_check    TEXT
);

-- Background work (imports, re-analysis), persisted so it survives restarts.
CREATE TABLE jobs (
    id            INTEGER PRIMARY KEY,
    kind          TEXT NOT NULL,
    payload       TEXT NOT NULL DEFAULT '{}', -- JSON
    state         TEXT NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'running', 'done', 'failed', 'cancelled')),
    attempts      INTEGER NOT NULL DEFAULT 0,
    progress      TEXT,
    error         TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    started_at    TEXT,
    finished_at   TEXT
);
CREATE INDEX jobs_state ON jobs(state, id);

CREATE TABLE settings (
    key           TEXT PRIMARY KEY,
    value         TEXT NOT NULL               -- JSON
);
