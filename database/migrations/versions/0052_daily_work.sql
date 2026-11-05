-- Daily Work owns daily commitment, readiness and coordination. Actual remains PM execution events.
CREATE TABLE dw_daily_work_items (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
  activity_id CHAR(32) NOT NULL,
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
  FOREIGN KEY(activity_id, project_id) REFERENCES pm_activities(id, project_id),
  FOREIGN KEY(work_order_id, project_id) REFERENCES pm_work_orders(id, project_id),
  UNIQUE(project_id, activity_id, work_date)
);
CREATE INDEX ix_dw_items_project_date ON dw_daily_work_items(project_id, work_date, deleted_at);
CREATE INDEX ix_dw_items_assignee ON dw_daily_work_items(assignee_user_id, work_date);

CREATE TABLE dw_readiness_checks (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  daily_work_id CHAR(32) NOT NULL REFERENCES dw_daily_work_items(id),
  check_type TEXT NOT NULL,
  result TEXT NOT NULL CHECK(result IN ('ready','warning','blocked')),
  note TEXT NOT NULL DEFAULT '',
  checked_by CHAR(32) NOT NULL REFERENCES users(id),
  checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_dw_readiness_item ON dw_readiness_checks(daily_work_id, checked_at);

CREATE TABLE dw_blockers (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  daily_work_id CHAR(32) NOT NULL REFERENCES dw_daily_work_items(id),
  blocker_type TEXT NOT NULL,
  description TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved')),
  resolved_note TEXT NOT NULL DEFAULT '',
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  resolved_at TEXT
);
CREATE INDEX ix_dw_blockers_item ON dw_blockers(daily_work_id, status);

CREATE TABLE dw_participations (
  id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
  daily_work_id CHAR(32) NOT NULL REFERENCES dw_daily_work_items(id),
  employee_id CHAR(32) NOT NULL REFERENCES hr_employees(id),
  participation_type TEXT NOT NULL DEFAULT 'worker',
  minutes INTEGER CHECK(minutes IS NULL OR minutes >= 0),
  notes TEXT NOT NULL DEFAULT '',
  created_by CHAR(32) NOT NULL REFERENCES users(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(daily_work_id, employee_id, participation_type)
);
