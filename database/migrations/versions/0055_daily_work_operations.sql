-- DW-02.2: independent actuals, emergency items, versioned reopen and safe history.
-- Daily Work only. External actuals remain owned by their source modules.
PRAGMA foreign_keys=OFF;

CREATE TABLE dw_daily_work_items_next (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  activity_id CHAR(32),
  work_order_id CHAR(32),
  work_date TEXT NOT NULL,
  title TEXT NOT NULL,
  target_quantity TEXT NOT NULL DEFAULT '0',
  unit TEXT NOT NULL DEFAULT '',
  assignee_user_id CHAR(32) REFERENCES users(id),
  team_name TEXT NOT NULL DEFAULT '',
  shift TEXT NOT NULL DEFAULT '',
  location TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','ready','in_progress','blocked','completed','closed')),
  readiness_status TEXT NOT NULL DEFAULT 'not_ready' CHECK(readiness_status IN ('ready','warnings','not_ready')),
  notes TEXT NOT NULL DEFAULT '',
  blocker_summary TEXT NOT NULL DEFAULT '',
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT,
  deleted_by CHAR(32) REFERENCES users(id),
  plan_id CHAR(32) REFERENCES dw_work_plans(id),
  scope_type TEXT NOT NULL DEFAULT 'project' CHECK(scope_type IN ('project','organization_unit','department','person','team','independent')),
  organization_id CHAR(32),
  department_id CHAR(32),
  source_type TEXT NOT NULL DEFAULT 'pm_activity' CHECK(source_type IN ('pm_activity','pm_work_order','hr_field_task','equipment_operation','inventory_request','independent')),
  source_id CHAR(32),
  planned_start_at TEXT,
  planned_end_at TEXT,
  committed_start_at TEXT,
  committed_end_at TEXT,
  planned_minutes TEXT NOT NULL DEFAULT '0',
  committed_minutes TEXT NOT NULL DEFAULT '0',
  committed_quantity TEXT NOT NULL DEFAULT '0',
  unit_precision INTEGER NOT NULL DEFAULT 6 CHECK(unit_precision BETWEEN 0 AND 12),
  commitment_status TEXT NOT NULL DEFAULT 'proposed' CHECK(commitment_status IN ('proposed','assigned','accepted','committed','declined')),
  outcome_status TEXT NOT NULL DEFAULT 'not_started' CHECK(outcome_status IN ('not_started','partial','completed','blocked','cancelled','carried_over')),
  estimated_cost_status TEXT NOT NULL DEFAULT 'unavailable' CHECK(estimated_cost_status IN ('available','partial','unavailable')),
  currency_id TEXT,
  estimate_total TEXT NOT NULL DEFAULT '0',
  carryover_of_id CHAR(32) REFERENCES dw_daily_work_items(id),
  emergency_flag INTEGER NOT NULL DEFAULT 0 CHECK(emergency_flag IN (0,1)),
  emergency_reason TEXT NOT NULL DEFAULT '',
  overrun_allowed INTEGER NOT NULL DEFAULT 0 CHECK(overrun_allowed IN (0,1)),
  FOREIGN KEY(activity_id, project_id) REFERENCES pm_activities(id, project_id),
  FOREIGN KEY(work_order_id, project_id) REFERENCES pm_work_orders(id, project_id),
  CHECK((source_type='independent' AND activity_id IS NULL AND work_order_id IS NULL)
     OR (source_type<>'independent' AND activity_id IS NOT NULL)),
  CHECK(emergency_flag=0 OR length(trim(emergency_reason))>0)
);

INSERT INTO dw_daily_work_items_next (
  id,project_id,activity_id,work_order_id,work_date,title,target_quantity,unit,assignee_user_id,
  team_name,shift,location,status,readiness_status,notes,blocker_summary,created_by,created_at,
  updated_at,deleted_at,deleted_by,plan_id,scope_type,organization_id,department_id,source_type,
  source_id,planned_start_at,planned_end_at,committed_start_at,committed_end_at,planned_minutes,
  committed_minutes,committed_quantity,unit_precision,commitment_status,outcome_status,
  estimated_cost_status,currency_id,estimate_total,carryover_of_id,emergency_flag,emergency_reason,
  overrun_allowed
 )
 SELECT id,project_id,activity_id,work_order_id,work_date,title,target_quantity,unit,assignee_user_id,
  team_name,shift,location,status,readiness_status,notes,blocker_summary,created_by,created_at,
  updated_at,deleted_at,deleted_by,plan_id,scope_type,organization_id,department_id,source_type,
  source_id,planned_start_at,planned_end_at,committed_start_at,committed_end_at,planned_minutes,
  committed_minutes,committed_quantity,unit_precision,commitment_status,outcome_status,
  estimated_cost_status,currency_id,estimate_total,carryover_of_id,emergency_flag,'',overrun_allowed
 FROM dw_daily_work_items;

DROP TABLE dw_daily_work_items;
ALTER TABLE dw_daily_work_items_next RENAME TO dw_daily_work_items;
PRAGMA foreign_keys=ON;

CREATE INDEX ix_dw_items_project_date ON dw_daily_work_items(project_id, work_date, deleted_at);
CREATE INDEX ix_dw_items_assignee ON dw_daily_work_items(assignee_user_id, work_date);
CREATE INDEX ix_dw_items_plan_status ON dw_daily_work_items(plan_id, commitment_status, outcome_status);
CREATE INDEX ix_dw_items_source ON dw_daily_work_items(source_type, source_id);
CREATE UNIQUE INDEX ux_dw_items_source_day ON dw_daily_work_items(project_id, activity_id, work_date)
  WHERE deleted_at IS NULL AND emergency_flag=0 AND activity_id IS NOT NULL;

ALTER TABLE dw_work_plans ADD COLUMN reopened_from_plan_id CHAR(32) REFERENCES dw_work_plans(id);
ALTER TABLE dw_work_plans ADD COLUMN reopen_reason TEXT NOT NULL DEFAULT '';
