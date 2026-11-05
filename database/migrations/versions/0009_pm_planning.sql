-- PM-01 additive planning schema. Decimal values use canonical text. No execution data.

CREATE TABLE pm_projects (
 id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
 name TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 deleted_at TEXT,
 deleted_by CHAR(32) REFERENCES users(id),
 restored_by CHAR(32) REFERENCES users(id),
 project_code TEXT NOT NULL UNIQUE,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 project_manager_user_id CHAR(32) NOT NULL REFERENCES users(id),
 currency TEXT NOT NULL REFERENCES core_currencies(code),
 directive_date TEXT NOT NULL,
 start_date TEXT NOT NULL,
 daily_hours TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'issued'
);

CREATE TABLE pm_phases (
 id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
 name TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 deleted_at TEXT,
 deleted_by CHAR(32) REFERENCES users(id),
 restored_by CHAR(32) REFERENCES users(id),
 project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
 phase_code TEXT NOT NULL,
 
UNIQUE(id,project_id), UNIQUE(project_id,phase_code)
);

CREATE INDEX ix_pm_phases_parent ON pm_phases(project_id,deleted_at);

CREATE TABLE pm_tasks (
 id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
 name TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 deleted_at TEXT,
 deleted_by CHAR(32) REFERENCES users(id),
 restored_by CHAR(32) REFERENCES users(id),
 project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
 task_code TEXT NOT NULL,
 
phase_id CHAR(32) NOT NULL,
 FOREIGN KEY(phase_id,project_id) REFERENCES pm_phases(id,project_id),
UNIQUE(id,project_id), UNIQUE(project_id,task_code)
);

CREATE INDEX ix_pm_tasks_parent ON pm_tasks(phase_id,deleted_at);

CREATE TABLE pm_activities (
 id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
 name TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 deleted_at TEXT,
 deleted_by CHAR(32) REFERENCES users(id),
 restored_by CHAR(32) REFERENCES users(id),
 project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
 activity_code TEXT NOT NULL,
 planned_quantity TEXT NOT NULL, planned_duration TEXT NOT NULL, unit TEXT NOT NULL DEFAULT '', currency TEXT NOT NULL REFERENCES core_currencies(code), rate_date TEXT NOT NULL, exchange_rate_snapshot TEXT NOT NULL,
task_id CHAR(32) NOT NULL,
 FOREIGN KEY(task_id,project_id) REFERENCES pm_tasks(id,project_id),
UNIQUE(id,project_id), UNIQUE(project_id,activity_code)
);

CREATE INDEX ix_pm_activities_parent ON pm_activities(task_id,deleted_at);

CREATE TABLE pm_activity_resource_requirements (
 id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
 name TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 deleted_at TEXT,
 deleted_by CHAR(32) REFERENCES users(id),
 restored_by CHAR(32) REFERENCES users(id),
 project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
 requirement_code TEXT NOT NULL,
 quantity TEXT NOT NULL, unit_price TEXT NOT NULL, resource_type TEXT NOT NULL DEFAULT '', specifications TEXT NOT NULL DEFAULT '', unit TEXT NOT NULL DEFAULT '', currency TEXT NOT NULL REFERENCES core_currencies(code), rate_date TEXT NOT NULL, exchange_rate_snapshot TEXT NOT NULL,
activity_id CHAR(32) NOT NULL,
 FOREIGN KEY(activity_id,project_id) REFERENCES pm_activities(id,project_id),
UNIQUE(id,project_id), UNIQUE(project_id,requirement_code)
);

CREATE INDEX ix_pm_activity_resource_requirements_parent ON pm_activity_resource_requirements(activity_id,deleted_at);

CREATE INDEX ix_pm_projects_scope ON pm_projects(organization_id,project_manager_user_id,deleted_at);
