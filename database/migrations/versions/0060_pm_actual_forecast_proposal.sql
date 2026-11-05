-- S-04.3: immutable Actual measurement context for a draft Forecast proposal.
-- These columns are snapshots used to explain a calculation; they do not become
-- an additional Actual source and never alter WO, WEP, a baseline, or an approved version.
ALTER TABLE pm_schedule_versions ADD COLUMN actual_as_of TEXT;
ALTER TABLE pm_schedule_versions ADD COLUMN actual_input_hash TEXT;
ALTER TABLE pm_schedule_versions ADD COLUMN actual_output_hash TEXT;
ALTER TABLE pm_schedule_versions ADD COLUMN actual_source_event_ids_json TEXT;

ALTER TABLE pm_schedule_items ADD COLUMN planned_quantity TEXT;
ALTER TABLE pm_schedule_items ADD COLUMN actual_quantity_at_measurement TEXT;
ALTER TABLE pm_schedule_items ADD COLUMN remaining_quantity TEXT;

CREATE UNIQUE INDEX ux_pm_schedule_versions_actual_draft
  ON pm_schedule_versions(project_id, baseline_id, actual_input_hash)
  WHERE status='draft' AND actual_input_hash IS NOT NULL;
