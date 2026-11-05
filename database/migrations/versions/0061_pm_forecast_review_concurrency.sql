-- S-04.5: retain the approved Forecast observed when a draft enters review.
-- The value is an optimistic-concurrency token only; it never changes a baseline
-- or an approved Forecast and is nullable when no Forecast was approved yet.
ALTER TABLE pm_schedule_versions ADD COLUMN reviewed_against_version_id CHAR(32);
CREATE INDEX ix_pm_schedule_versions_reviewed_against
  ON pm_schedule_versions(project_id, reviewed_against_version_id);
