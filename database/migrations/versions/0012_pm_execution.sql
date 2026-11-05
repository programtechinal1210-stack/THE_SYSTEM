-- PM-04 additive execution schema. Quantity events are immutable; actual_quantity_snapshot is a current summary only.
CREATE TABLE pm_work_orders (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  name TEXT NOT NULL,
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT, deleted_by CHAR(32) REFERENCES users(id), restored_by CHAR(32) REFERENCES users(id),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  activity_id CHAR(32) NOT NULL,
  work_order_code TEXT NOT NULL,
  assignee_user_id CHAR(32) REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'issued' CHECK(status IN ('issued','in_progress','completed','closed','rejected')),
  issue_date TEXT,
  start_date TEXT,
  completion_date TEXT,
  closure_date TEXT,
  actual_quantity_snapshot TEXT NOT NULL DEFAULT '0',
  notes TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(activity_id, project_id) REFERENCES pm_activities(id, project_id),
  UNIQUE(id, project_id),
  UNIQUE(project_id, work_order_code)
);
CREATE INDEX ix_pm_work_orders_project ON pm_work_orders(project_id, deleted_at);
CREATE INDEX ix_pm_work_orders_activity ON pm_work_orders(activity_id);

CREATE TABLE pm_work_order_consumptions (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  name TEXT NOT NULL,
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT, deleted_by CHAR(32) REFERENCES users(id), restored_by CHAR(32) REFERENCES users(id),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  work_order_id CHAR(32) NOT NULL,
  consumption_code TEXT NOT NULL,
  item_name TEXT NOT NULL,
  item_type TEXT NOT NULL DEFAULT '',
  quantity TEXT NOT NULL,
  unit TEXT NOT NULL DEFAULT '',
  unit_price TEXT NOT NULL,
  currency TEXT NOT NULL REFERENCES core_currencies(code),
  rate_date TEXT NOT NULL,
  exchange_rate_snapshot TEXT NOT NULL,
  reference TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(work_order_id, project_id) REFERENCES pm_work_orders(id, project_id),
  UNIQUE(project_id, consumption_code)
);
CREATE INDEX ix_pm_work_order_consumptions_wo ON pm_work_order_consumptions(work_order_id, deleted_at);

CREATE TABLE pm_execution_quantity_events (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  work_order_id CHAR(32) NOT NULL,
  activity_id CHAR(32) NOT NULL,
  before_quantity TEXT NOT NULL,
  after_quantity TEXT NOT NULL,
  delta TEXT NOT NULL,
  event_type TEXT NOT NULL DEFAULT 'quantity_update',
  recorded_by CHAR(32) NOT NULL REFERENCES users(id),
  recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  notes TEXT NOT NULL DEFAULT '',
  FOREIGN KEY(work_order_id, project_id) REFERENCES pm_work_orders(id, project_id),
  FOREIGN KEY(activity_id, project_id) REFERENCES pm_activities(id, project_id)
);
CREATE INDEX ix_pm_execution_quantity_events_wo ON pm_execution_quantity_events(work_order_id, recorded_at);
