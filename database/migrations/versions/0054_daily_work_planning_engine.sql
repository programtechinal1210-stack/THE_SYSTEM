-- DW-02: planning-only triple engine. No Actual source is created here.
ALTER TABLE dw_daily_work_items ADD COLUMN plan_id CHAR(32) REFERENCES dw_work_plans(id);
ALTER TABLE dw_daily_work_items ADD COLUMN scope_type TEXT NOT NULL DEFAULT 'project' CHECK(scope_type IN ('project','organization_unit','department','person','team','independent'));
ALTER TABLE dw_daily_work_items ADD COLUMN organization_id CHAR(32);
ALTER TABLE dw_daily_work_items ADD COLUMN department_id CHAR(32);
ALTER TABLE dw_daily_work_items ADD COLUMN source_type TEXT NOT NULL DEFAULT 'pm_activity' CHECK(source_type IN ('pm_activity','pm_work_order','hr_field_task','equipment_operation','inventory_request','independent'));
ALTER TABLE dw_daily_work_items ADD COLUMN source_id CHAR(32);
ALTER TABLE dw_daily_work_items ADD COLUMN planned_start_at TEXT;
ALTER TABLE dw_daily_work_items ADD COLUMN planned_end_at TEXT;
ALTER TABLE dw_daily_work_items ADD COLUMN committed_start_at TEXT;
ALTER TABLE dw_daily_work_items ADD COLUMN committed_end_at TEXT;
ALTER TABLE dw_daily_work_items ADD COLUMN planned_minutes TEXT NOT NULL DEFAULT '0';
ALTER TABLE dw_daily_work_items ADD COLUMN committed_minutes TEXT NOT NULL DEFAULT '0';
ALTER TABLE dw_daily_work_items ADD COLUMN committed_quantity TEXT NOT NULL DEFAULT '0';
ALTER TABLE dw_daily_work_items ADD COLUMN unit_precision INTEGER NOT NULL DEFAULT 6 CHECK(unit_precision BETWEEN 0 AND 12);
ALTER TABLE dw_daily_work_items ADD COLUMN commitment_status TEXT NOT NULL DEFAULT 'proposed' CHECK(commitment_status IN ('proposed','assigned','accepted','committed','declined'));
ALTER TABLE dw_daily_work_items ADD COLUMN outcome_status TEXT NOT NULL DEFAULT 'not_started' CHECK(outcome_status IN ('not_started','partial','completed','blocked','cancelled','carried_over'));
ALTER TABLE dw_daily_work_items ADD COLUMN estimated_cost_status TEXT NOT NULL DEFAULT 'unavailable' CHECK(estimated_cost_status IN ('available','partial','unavailable'));
ALTER TABLE dw_daily_work_items ADD COLUMN currency_id TEXT;
ALTER TABLE dw_daily_work_items ADD COLUMN estimate_total TEXT NOT NULL DEFAULT '0';
ALTER TABLE dw_daily_work_items ADD COLUMN carryover_of_id CHAR(32) REFERENCES dw_daily_work_items(id);
ALTER TABLE dw_daily_work_items ADD COLUMN emergency_flag INTEGER NOT NULL DEFAULT 0 CHECK(emergency_flag IN (0,1));
ALTER TABLE dw_daily_work_items ADD COLUMN overrun_allowed INTEGER NOT NULL DEFAULT 0 CHECK(overrun_allowed IN (0,1));

CREATE TABLE dw_work_plans (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
  scope_type TEXT NOT NULL CHECK(scope_type IN ('project','organization_unit','department','person','team','independent')),
  scope_id CHAR(32),
  project_id CHAR(32) REFERENCES pm_projects(id),
  plan_date TEXT NOT NULL,
  period_start TEXT NOT NULL,
  period_end TEXT NOT NULL,
  timezone_name_snapshot TEXT NOT NULL DEFAULT 'Asia/Riyadh',
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','ready_for_commitment','committed','in_progress','closed','reopened','cancelled')),
  version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
  owner_user_id CHAR(32) NOT NULL REFERENCES users(id),
  committed_at TEXT,
  closed_at TEXT,
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT,
  UNIQUE(organization_id, scope_type, scope_id, plan_date, version),
  CHECK(period_end >= period_start)
);
CREATE INDEX ix_dw_plans_scope_date ON dw_work_plans(organization_id, scope_type, scope_id, plan_date, status);

CREATE TABLE dw_work_item_assignments (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  daily_work_id CHAR(32) NOT NULL REFERENCES dw_daily_work_items(id),
  subject_type TEXT NOT NULL CHECK(subject_type IN ('user','employee','team','department','equipment')),
  subject_id CHAR(32) NOT NULL,
  role TEXT NOT NULL DEFAULT 'worker',
  is_lead INTEGER NOT NULL DEFAULT 0 CHECK(is_lead IN (0,1)),
  planned_minutes TEXT NOT NULL DEFAULT '0',
  status TEXT NOT NULL DEFAULT 'assigned' CHECK(status IN ('assigned','accepted','declined','released')),
  accepted_at TEXT,
  released_at TEXT,
  source_reference_type TEXT,
  source_reference_id CHAR(32),
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(daily_work_id, subject_type, subject_id, role)
);
CREATE INDEX ix_dw_assignments_subject ON dw_work_item_assignments(subject_type, subject_id, status);

CREATE TABLE dw_work_item_updates (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  daily_work_id CHAR(32) NOT NULL REFERENCES dw_daily_work_items(id),
  event_type TEXT NOT NULL CHECK(event_type IN ('status','note','quantity','time','cost')),
  quantity_delta TEXT,
  minutes_delta INTEGER,
  cost_delta TEXT,
  unit TEXT,
  currency_id TEXT,
  fx_rate TEXT,
  fx_as_of TEXT,
  source_type TEXT NOT NULL DEFAULT 'independent',
  source_event_id CHAR(32),
  idempotency_key TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  business_date TEXT NOT NULL,
  actor_user_id CHAR(32) NOT NULL REFERENCES users(id),
  note TEXT NOT NULL DEFAULT '',
  UNIQUE(idempotency_key),
  UNIQUE(source_type, source_event_id)
);
CREATE INDEX ix_dw_updates_item_time ON dw_work_item_updates(daily_work_id, occurred_at, id);

CREATE TABLE dw_work_item_estimates (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  daily_work_id CHAR(32) NOT NULL REFERENCES dw_daily_work_items(id),
  estimate_kind TEXT NOT NULL CHECK(estimate_kind IN ('labor','equipment','material','expense')),
  quantity TEXT NOT NULL CHECK(CAST(quantity AS NUMERIC) >= 0),
  unit TEXT NOT NULL,
  unit_rate TEXT NOT NULL CHECK(CAST(unit_rate AS NUMERIC) >= 0),
  currency_id TEXT NOT NULL,
  fx_rate TEXT NOT NULL DEFAULT '1' CHECK(CAST(fx_rate AS NUMERIC) > 0),
  fx_as_of TEXT NOT NULL,
  source_type TEXT,
  source_id CHAR(32),
  confidence TEXT NOT NULL DEFAULT 'medium' CHECK(confidence IN ('high','medium','low')),
  version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
  is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0,1)),
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_dw_estimates_current ON dw_work_item_estimates(daily_work_id, is_current, estimate_kind);

CREATE TABLE dw_work_item_evidence (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  daily_work_id CHAR(32) NOT NULL REFERENCES dw_daily_work_items(id),
  evidence_type TEXT NOT NULL,
  local_storage_key TEXT,
  sha256 TEXT NOT NULL,
  content_type TEXT NOT NULL DEFAULT '',
  size_bytes INTEGER CHECK(size_bytes IS NULL OR size_bytes >= 0),
  captured_at TEXT NOT NULL,
  captured_by CHAR(32) NOT NULL REFERENCES users(id),
  UNIQUE(daily_work_id, sha256)
);

CREATE TABLE dw_plan_closures (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  plan_id CHAR(32) NOT NULL REFERENCES dw_work_plans(id),
  closure_version INTEGER NOT NULL CHECK(closure_version>0),
  planned_count INTEGER NOT NULL DEFAULT 0,
  committed_count INTEGER NOT NULL DEFAULT 0,
  completed_count INTEGER NOT NULL DEFAULT 0,
  blocked_count INTEGER NOT NULL DEFAULT 0,
  carryover_count INTEGER NOT NULL DEFAULT 0,
  planned_quantity_snapshot TEXT NOT NULL DEFAULT '0',
  actual_quantity_snapshot TEXT,
  planned_minutes_snapshot TEXT NOT NULL DEFAULT '0',
  actual_minutes_snapshot INTEGER,
  planned_cost_snapshot TEXT NOT NULL DEFAULT '0',
  actual_cost_snapshot TEXT,
  coverage_json TEXT NOT NULL DEFAULT '{}',
  closed_by CHAR(32) NOT NULL REFERENCES users(id),
  closed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  summary TEXT NOT NULL DEFAULT '',
  UNIQUE(plan_id, closure_version)
);

UPDATE dw_daily_work_items
SET organization_id=(SELECT organization_id FROM pm_projects WHERE pm_projects.id=dw_daily_work_items.project_id)
WHERE organization_id IS NULL;
UPDATE dw_daily_work_items
SET source_id=COALESCE(work_order_id, activity_id),
    source_type=CASE WHEN work_order_id IS NULL THEN 'pm_activity' ELSE 'pm_work_order' END
WHERE source_id IS NULL;
CREATE INDEX ix_dw_items_plan_status ON dw_daily_work_items(plan_id, commitment_status, outcome_status);
CREATE INDEX ix_dw_items_source ON dw_daily_work_items(source_type, source_id);
