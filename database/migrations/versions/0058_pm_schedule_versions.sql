-- S-01B: calculated schedule snapshots. They reference an immutable PM baseline
-- and never mutate planning, WEP, Daily Work, work orders, or Actual data.
CREATE TABLE pm_schedule_versions (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  baseline_id CHAR(32) NOT NULL REFERENCES pm_plan_baselines(id),
  version_no INTEGER NOT NULL CHECK(version_no > 0),
  status TEXT NOT NULL DEFAULT 'draft'
    CHECK(status IN ('draft','proposed','approved','rejected','superseded')),
  calculation_inputs_hash TEXT NOT NULL CHECK(length(trim(calculation_inputs_hash)) > 0),
  reason TEXT,
  effective_from TEXT,
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  proposed_at TEXT,
  approved_by CHAR(32) REFERENCES users(id),
  approved_at TEXT,
  rejected_by CHAR(32) REFERENCES users(id),
  rejected_at TEXT,
  rejection_reason TEXT,
  UNIQUE(project_id, version_no),
  CHECK((status <> 'approved') OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)),
  CHECK((status <> 'rejected') OR (rejected_by IS NOT NULL AND rejected_at IS NOT NULL AND rejection_reason IS NOT NULL))
);
CREATE UNIQUE INDEX ux_pm_schedule_versions_one_approved
  ON pm_schedule_versions(project_id) WHERE status='approved';
CREATE INDEX ix_pm_schedule_versions_baseline ON pm_schedule_versions(baseline_id, status);

CREATE TABLE pm_schedule_items (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  schedule_version_id CHAR(32) NOT NULL REFERENCES pm_schedule_versions(id),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  activity_id CHAR(32) NOT NULL REFERENCES pm_activities(id),
  scheduling_state TEXT NOT NULL CHECK(scheduling_state IN
    ('ready','warning','blocked_dependency','blocked_calendar','blocked_resource',
     'blocked_insufficient_estimate','blocked_external')),
  block_reason TEXT,
  remaining_work_minutes INTEGER CHECK(remaining_work_minutes >= 0),
  early_start TEXT,
  early_finish TEXT,
  late_start TEXT,
  late_finish TEXT,
  total_float_minutes INTEGER,
  is_critical INTEGER NOT NULL DEFAULT 0 CHECK(is_critical IN (0,1)),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(schedule_version_id, activity_id),
  FOREIGN KEY(activity_id, project_id) REFERENCES pm_activities(id, project_id),
  CHECK((early_start IS NULL AND early_finish IS NULL)
     OR (early_start IS NOT NULL AND early_finish IS NOT NULL AND early_start <= early_finish)),
  CHECK((late_start IS NULL AND late_finish IS NULL)
     OR (late_start IS NOT NULL AND late_finish IS NOT NULL AND late_start <= late_finish)),
  CHECK((scheduling_state LIKE 'blocked_%' AND early_start IS NULL AND is_critical=0)
     OR (scheduling_state NOT LIKE 'blocked_%'))
);
CREATE INDEX ix_pm_schedule_items_version ON pm_schedule_items(schedule_version_id, activity_id);
