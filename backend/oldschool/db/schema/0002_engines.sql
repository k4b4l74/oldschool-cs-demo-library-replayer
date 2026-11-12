-- 0002: engine registry (docs/ARCHITECTURE.md §8).
-- Each install keeps what the scan found ("detected") apart from what the
-- user changed ("overrides"); the effective values are detected + overrides.
-- kind/build/protocols/releases/status of 0001 hold the effective values.
ALTER TABLE engines ADD COLUMN name TEXT;
ALTER TABLE engines ADD COLUMN detected TEXT NOT NULL DEFAULT '{}';
ALTER TABLE engines ADD COLUMN overrides TEXT NOT NULL DEFAULT '{}';
ALTER TABLE engines ADD COLUMN source TEXT NOT NULL DEFAULT 'scan' CHECK (source IN ('scan', 'manual'));
ALTER TABLE engines ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1;
ALTER TABLE engines ADD COLUMN missing INTEGER NOT NULL DEFAULT 0;  -- folder gone at the last scan

-- Which install plays which (network protocol, release). Rows exist only
-- where the user chose; otherwise the best install is picked automatically.
CREATE TABLE engine_routes (
    protocol      INTEGER NOT NULL,
    release       TEXT NOT NULL,
    engine_id     INTEGER NOT NULL REFERENCES engines(id) ON DELETE CASCADE,
    PRIMARY KEY (protocol, release)
);
