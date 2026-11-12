-- M4: imports from the app (Drop folder, uploads, folders), per-file results, re-analysis.

-- The name the file was imported under, relative to the folder given (e.g. "2002/[aAa]_[GG]_[de_dust2].zip"):
-- folder names hint at teams and year, so re-analysis needs it. NULL: the file name.
ALTER TABLE originals ADD COLUMN label TEXT;
-- 0: the demos of this file were not copied into the store (read from the file when played).
ALTER TABLE originals ADD COLUMN demo_copies INTEGER NOT NULL DEFAULT 1;
ALTER TABLE originals ADD COLUMN analysed_at TEXT;

UPDATE originals SET demo_copies = 0 WHERE EXISTS (
    SELECT 1 FROM archive_members a JOIN demos d ON d.sha1 = a.demo_sha1
    WHERE a.original_id = originals.id AND d.store_path = ''
);

-- One row per file handled by an import or re-analysis job.
CREATE TABLE job_files (
    id            INTEGER PRIMARY KEY,
    job_id        INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    path          TEXT NOT NULL,              -- where the file was read (Windows path when on a drive)
    label         TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('imported', 'already', 'no-demo', 'failed', 'missing', 'reanalysed')),
    original_id   INTEGER REFERENCES originals(id) ON DELETE SET NULL,
    matches       INTEGER NOT NULL DEFAULT 0,
    demos_new     INTEGER NOT NULL DEFAULT 0,
    message       TEXT,                       -- why it failed, or the archive warnings
    moved_to      TEXT,                       -- Drop files that could not be imported are moved aside (_failed…)
    retry_job_id  INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    at            TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX job_files_job ON job_files(job_id, status);
CREATE INDEX job_files_failed ON job_files(status, id);
