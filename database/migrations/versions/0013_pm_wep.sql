-- PM-05 additive weekly execution plan (WEP) schema. Baselines and history are immutable/append-only.
CREATE TABLE pm_weekly_plans (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  name TEXT NOT NULL,
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT, deleted_by CHAR(32) REFERENCES users(id), restored_by CHAR(32) REFERENCES users(id),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  week_code TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','review','approved','in_progress','closed','reopened','cancelled')),
  closure TEXT,
  carried_over INTEGER NOT NULL DEFAULT 0,
  UNIQUE(id, project_id),
  UNIQUE(project_id, week_code)
);
CREATE INDEX ix_pm_weekly_plans_project ON pm_weekly_plans(project_id, deleted_at);

CREATE TABLE pm_weekly_plan_items (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  name TEXT NOT NULL,
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT, deleted_by CHAR(32) REFERENCES users(id), restored_by CHAR(32) REFERENCES users(id),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  plan_id CHAR(32) NOT NULL,
  activity_id CHAR(32) NOT NULL,
  weekly_target TEXT NOT NULL,
  assignee_user_id CHAR(32) REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'planned',
  FOREIGN KEY(plan_id, project_id) REFERENCES pm_weekly_plans(id, project_id),
  FOREIGN KEY(activity_id, project_id) REFERENCES pm_activities(id, project_id),
  UNIQUE(plan_id, activity_id)
);
CREATE INDEX ix_pm_weekly_plan_items_plan ON pm_weekly_plan_items(plan_id, deleted_at);

CREATE TABLE pm_weekly_plan_baselines (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  plan_id CHAR(32) NOT NULL,
  project_id CHAR(32) NOT NULL,
  version INTEGER NOT NULL,
  approved_by CHAR(32) NOT NULL REFERENCES users(id),
  approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  snapshot TEXT NOT NULL,
  FOREIGN KEY(plan_id, project_id) REFERENCES pm_weekly_plans(id, project_id),
  UNIQUE(plan_id, version)
);
CREATE INDEX ix_pm_weekly_plan_baselines_plan ON pm_weekly_plan_baselines(plan_id, version);

CREATE TABLE pm_weekly_plan_history (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  plan_id CHAR(32) NOT NULL,
  project_id CHAR(32) NOT NULL,
  event TEXT NOT NULL,
  actor CHAR(32) NOT NULL REFERENCES users(id),
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_pm_weekly_plan_history_plan ON pm_weekly_plan_history(plan_id, created_at);
