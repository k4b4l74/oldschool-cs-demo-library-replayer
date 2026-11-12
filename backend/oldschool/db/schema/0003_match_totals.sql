-- 0003: per-match totals stored at import, so that listing, sorting and
-- paging stay fast on the full library (~39k matches) instead of summing
-- each match's demos on every request.
ALTER TABLE matches ADD COLUMN demo_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE matches ADD COLUMN duration_s REAL NOT NULL DEFAULT 0;
ALTER TABLE matches ADD COLUMN kill_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE matches ADD COLUMN file_date TEXT;   -- earliest .dem member timestamp (a file write time, never a played date)

UPDATE matches SET
    demo_count = (SELECT count(*) FROM match_demos md WHERE md.match_id = matches.id),
    duration_s = (SELECT coalesce(sum(d.duration_s), 0) FROM match_demos md JOIN demos d ON d.sha1 = md.demo_sha1
                  WHERE md.match_id = matches.id),
    kill_count = (SELECT coalesce(sum(d.kill_count), 0) FROM match_demos md JOIN demos d ON d.sha1 = md.demo_sha1
                  WHERE md.match_id = matches.id),
    file_date = (SELECT min(a.mtime) FROM match_demos md JOIN archive_members a ON a.demo_sha1 = md.demo_sha1
                 WHERE md.match_id = matches.id AND a.original_id = matches.original_id
                   AND a.mtime_basis = 'archive_member');

CREATE INDEX matches_year ON matches(year_est, file_date, id);
CREATE INDEX matches_release ON matches(release);
CREATE INDEX matches_team1 ON matches(team1_id);
CREATE INDEX matches_team2 ON matches(team2_id);
