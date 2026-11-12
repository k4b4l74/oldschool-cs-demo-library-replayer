---
name: db-migration
description: Change the SQLite schema with a numbered migration, keep existing libraries working, and update the tests that pin the schema version. Use when adding a table, column or index, or when stored data must be back-filled.
---

# Schema change

Migrations are `backend/oldschool/db/schema/NNNN_name.sql`, applied in order by `db/migrate.py`, each in one transaction, recorded in `schema_migrations`. Numbers are `1..n` without gaps.

**Released migrations are never edited.** Every change is a new file.

## Steps

1. Add `000N_what.sql` (next number). Prefer `ALTER TABLE … ADD COLUMN … DEFAULT …` and `CREATE TABLE/INDEX IF NOT EXISTS`. SQLite cannot drop or retype columns easily: rebuild a table only when unavoidable (create new, copy, drop, rename) inside the same file.
2. **Back-fill** in SQL when the value can be computed from what is stored (e.g. `UPDATE originals SET demo_copies = 0 WHERE …`). Users have libraries of tens of thousands of matches: keep it set-based, no per-row Python.
3. Values that need the files again (new parser output) are not back-filled: bump `importer.PARSE_VERSION` instead, and the Import page's "Re-analyse the older ones" picks them up (see the demo-parser skill).
4. Update the code that writes the table (`importer.Writer`, `jobs.py`, `player/engines.py`…) and the reads (`api/*.py`).
5. Tests:
   - `tests/test_api.py::test_health` pins `schema_version`: bump it.
   - Add a test that a database at the previous version migrates and keeps its rows (open an old schema in a temp file, insert rows, run `open_database`).
6. Document the table in `docs/ARCHITECTURE.md` §6 (Data model).

## Rules that shape the schema

- Names and tags are stored **as printed** (`name_as_printed`, `tag_as_printed`); never merge players or teams in a migration.
- Every estimate has its basis column (`year_est` + `year_basis`, `release` + `release_basis`, `team_basis`).
- Times inside a demo are demo-clock seconds (`t`, `start_t`), never dates; a file timestamp is never a played date.
- The database runs in WAL mode with one writer (the import job thread); API reads open their own connection.
