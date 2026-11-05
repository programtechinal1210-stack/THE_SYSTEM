-- S-01A: PM-owned execution scheduling calendars.
-- Planned, WEP, Daily Work and Actual ownership are intentionally unchanged.

CREATE TABLE pm_schedule_calendars (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
  project_id CHAR(32) REFERENCES pm_projects(id),
  name TEXT NOT NULL,
  timezone TEXT NOT NULL,
  calendar_type TEXT NOT NULL CHECK(calendar_type IN ('organization','project','activity')),
  weekly_pattern_json TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT,
  deleted_by CHAR(32) REFERENCES users(id),
  CHECK(length(trim(name)) > 0),
  CHECK(length(trim(timezone)) > 0),
  CHECK((calendar_type = 'organization' AND project_id IS NULL)
     OR (calendar_type IN ('project','activity') AND project_id IS NOT NULL))
);
CREATE UNIQUE INDEX ux_pm_schedule_calendars_name_active
  ON pm_schedule_calendars(organization_id, name)
  WHERE deleted_at IS NULL;
CREATE INDEX ix_pm_schedule_calendars_scope
  ON pm_schedule_calendars(organization_id, project_id, is_active, deleted_at);

CREATE TABLE pm_schedule_calendar_exceptions (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  calendar_id CHAR(32) NOT NULL REFERENCES pm_schedule_calendars(id),
  starts_at TEXT NOT NULL,
  ends_at TEXT NOT NULL,
  exception_type TEXT NOT NULL CHECK(exception_type IN ('holiday','leave','planned_stop','overtime','replacement_hours')),
  availability_mode TEXT NOT NULL CHECK(availability_mode IN ('close','add','replace')),
  reason TEXT NOT NULL,
  approved_by CHAR(32) REFERENCES users(id),
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT,
  deleted_by CHAR(32) REFERENCES users(id),
  CHECK(starts_at < ends_at),
  CHECK(length(trim(reason)) > 0)
);
CREATE INDEX ix_pm_schedule_calendar_exceptions_window
  ON pm_schedule_calendar_exceptions(calendar_id, starts_at, ends_at, deleted_at);

CREATE TABLE pm_schedule_activity_settings (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  activity_id CHAR(32) NOT NULL,
  calendar_id CHAR(32) REFERENCES pm_schedule_calendars(id),
  priority INTEGER NOT NULL DEFAULT 0 CHECK(priority BETWEEN 0 AND 1000),
  scheduling_mode TEXT NOT NULL DEFAULT 'automatic'
    CHECK(scheduling_mode IN ('automatic','constrained','manual_approved')),
  earliest_start TEXT,
  latest_finish TEXT,
  readiness_policy TEXT NOT NULL DEFAULT 'require_ready'
    CHECK(readiness_policy IN ('require_ready','allow_warning','manual_override')),
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT,
  deleted_by CHAR(32) REFERENCES users(id),
  FOREIGN KEY(activity_id, project_id) REFERENCES pm_activities(id, project_id),
  UNIQUE(activity_id),
  CHECK(earliest_start IS NULL OR latest_finish IS NULL OR earliest_start <= latest_finish)
);
CREATE INDEX ix_pm_schedule_activity_settings_project
  ON pm_schedule_activity_settings(project_id, deleted_at);

ALTER TABLE pm_projects ADD COLUMN default_schedule_calendar_id CHAR(32)
  REFERENCES pm_schedule_calendars(id);

