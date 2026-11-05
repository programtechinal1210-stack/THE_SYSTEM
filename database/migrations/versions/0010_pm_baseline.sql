-- PM-02 additive baseline + dependency schema. Baselines are immutable snapshots; no execution data.
CREATE TABLE pm_plan_baselines (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  version INTEGER NOT NULL,
  name TEXT NOT NULL,
  currency TEXT NOT NULL,
  directive_date TEXT NOT NULL,
  start_date TEXT NOT NULL,
  daily_hours TEXT NOT NULL,
  approved_by CHAR(32) NOT NULL REFERENCES users(id),
  approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(project_id, version)
);
CREATE INDEX ix_pm_plan_baselines_project ON pm_plan_baselines(project_id, version);

CREATE TABLE pm_plan_baseline_items (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  baseline_id CHAR(32) NOT NULL REFERENCES pm_plan_baselines(id),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  entity_kind TEXT NOT NULL,
  entity_id CHAR(32) NOT NULL,
  parent_entity_id CHAR(32),
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  snapshot TEXT NOT NULL,
  UNIQUE(baseline_id, entity_id)
);
CREATE INDEX ix_pm_plan_baseline_items_baseline ON pm_plan_baseline_items(baseline_id);

CREATE TABLE pm_activity_dependencies (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  predecessor_id CHAR(32) NOT NULL REFERENCES pm_activities(id),
  successor_id CHAR(32) NOT NULL REFERENCES pm_activities(id),
  dependency_type TEXT NOT NULL DEFAULT 'finish_to_start',
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(predecessor_id, successor_id),
  CHECK(predecessor_id != successor_id)
);
CREATE INDEX ix_pm_activity_dependencies_successor ON pm_activity_dependencies(successor_id);
CREATE INDEX ix_pm_activity_dependencies_predecessor ON pm_activity_dependencies(predecessor_id);
