-- PM-03 additive governance/control schema. No execution data; daily reports are administrative snapshots only.
CREATE TABLE pm_risks (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  name TEXT NOT NULL,
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT, deleted_by CHAR(32) REFERENCES users(id), restored_by CHAR(32) REFERENCES users(id),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  risk_code TEXT NOT NULL,
  level TEXT NOT NULL DEFAULT 'project' CHECK(level IN ('project','phase','task','activity')),
  phase_id CHAR(32) REFERENCES pm_phases(id),
  task_id CHAR(32) REFERENCES pm_tasks(id),
  activity_id CHAR(32) REFERENCES pm_activities(id),
  description TEXT NOT NULL,
  classification TEXT NOT NULL DEFAULT '',
  owner_user_id CHAR(32) REFERENCES users(id),
  probability TEXT NOT NULL DEFAULT '0',
  impact INTEGER NOT NULL DEFAULT 1 CHECK(impact BETWEEN 1 AND 5),
  importance TEXT NOT NULL DEFAULT '0',
  corrective_action TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','closed')),
  discovery_date TEXT,
  closure_date TEXT,
  UNIQUE(project_id, risk_code)
);
CREATE INDEX ix_pm_risks_project ON pm_risks(project_id, deleted_at);

CREATE TABLE pm_deviations (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  name TEXT NOT NULL,
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT, deleted_by CHAR(32) REFERENCES users(id), restored_by CHAR(32) REFERENCES users(id),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  deviation_code TEXT NOT NULL,
  level TEXT NOT NULL DEFAULT 'project' CHECK(level IN ('project','phase','task','activity')),
  phase_id CHAR(32) REFERENCES pm_phases(id),
  task_id CHAR(32) REFERENCES pm_tasks(id),
  activity_id CHAR(32) REFERENCES pm_activities(id),
  deviation_type TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  causes TEXT NOT NULL DEFAULT '',
  impact INTEGER NOT NULL DEFAULT 3 CHECK(impact BETWEEN 1 AND 5),
  corrective_action TEXT NOT NULL DEFAULT '',
  responsible_user_id CHAR(32) REFERENCES users(id),
  target_date TEXT,
  actual_date TEXT,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
  UNIQUE(project_id, deviation_code)
);
CREATE INDEX ix_pm_deviations_project ON pm_deviations(project_id, deleted_at);

CREATE TABLE pm_cash_flow_items (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  name TEXT NOT NULL,
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT, deleted_by CHAR(32) REFERENCES users(id), restored_by CHAR(32) REFERENCES users(id),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  item_code TEXT NOT NULL,
  cash_flow_type TEXT NOT NULL DEFAULT 'outflow' CHECK(cash_flow_type IN ('inflow','outflow')),
  amount TEXT NOT NULL,
  currency TEXT NOT NULL REFERENCES core_currencies(code),
  period TEXT NOT NULL,
  rate_date TEXT NOT NULL,
  exchange_rate_snapshot TEXT NOT NULL,
  notes TEXT NOT NULL DEFAULT '',
  UNIQUE(project_id, item_code)
);
CREATE INDEX ix_pm_cash_flow_items_project ON pm_cash_flow_items(project_id, deleted_at);

CREATE TABLE pm_communication_plan_items (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  name TEXT NOT NULL,
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT, deleted_by CHAR(32) REFERENCES users(id), restored_by CHAR(32) REFERENCES users(id),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  item_code TEXT NOT NULL,
  report_type TEXT NOT NULL DEFAULT '',
  purpose TEXT NOT NULL DEFAULT '',
  frequency TEXT NOT NULL DEFAULT '',
  sender_user_id CHAR(32) REFERENCES users(id),
  receivers TEXT NOT NULL DEFAULT '',
  mechanism TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  UNIQUE(project_id, item_code)
);
CREATE INDEX ix_pm_communication_plan_items_project ON pm_communication_plan_items(project_id, deleted_at);

CREATE TABLE pm_daily_reports (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  name TEXT NOT NULL,
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT, deleted_by CHAR(32) REFERENCES users(id), restored_by CHAR(32) REFERENCES users(id),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  report_code TEXT NOT NULL,
  report_date TEXT NOT NULL,
  activities_count INTEGER NOT NULL DEFAULT 0,
  planned_volume TEXT NOT NULL DEFAULT '0',
  executed_volume TEXT NOT NULL DEFAULT '0',
  daily_cost TEXT NOT NULL DEFAULT '0',
  actual_workers INTEGER NOT NULL DEFAULT 0,
  work_hours TEXT NOT NULL DEFAULT '0',
  equipment_used TEXT NOT NULL DEFAULT '',
  materials_used TEXT NOT NULL DEFAULT '',
  problems TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','submitted','approved','rejected')),
  notes TEXT NOT NULL DEFAULT '',
  prepared_by CHAR(32) REFERENCES users(id),
  approved_by CHAR(32) REFERENCES users(id),
  approved_at TEXT,
  UNIQUE(project_id, report_code)
);
CREATE INDEX ix_pm_daily_reports_project ON pm_daily_reports(project_id, deleted_at);
