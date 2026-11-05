-- HR-02: independent field tasks, workforce demand and dated assignments.
CREATE TABLE hr_field_tasks (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 task_no TEXT NOT NULL,
 title TEXT NOT NULL CHECK(length(trim(title))>0),
 description TEXT NOT NULL DEFAULT '',
 owner_unit_id CHAR(32) NOT NULL REFERENCES organizations(id),
 business_date TEXT NOT NULL,
 planned_start_at TEXT,
 planned_end_at TEXT,
 location_text TEXT NOT NULL DEFAULT '',
 location_ref_id TEXT,
 supervisor_employee_id CHAR(32),
 project_ref_id TEXT,
 work_order_ref_id TEXT,
 equipment_ref_id TEXT,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','ready','in_progress','completed','cancelled','archived')),
 row_version INTEGER NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK((planned_start_at IS NULL AND planned_end_at IS NULL) OR (planned_start_at IS NOT NULL AND planned_end_at IS NOT NULL AND planned_end_at>planned_start_at)),
 UNIQUE(organization_id,task_no),
 FOREIGN KEY(supervisor_employee_id,organization_id) REFERENCES hr_employees(id,organization_id)
);
CREATE INDEX ix_hr_field_tasks_org_date_status ON hr_field_tasks(organization_id,business_date,status);

CREATE TABLE hr_workforce_requests (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 request_no TEXT NOT NULL,
 requesting_unit_id CHAR(32) NOT NULL REFERENCES organizations(id),
 task_id CHAR(32),
 requested_position TEXT NOT NULL DEFAULT '',
 headcount INTEGER NOT NULL CHECK(headcount>0),
 start_at TEXT NOT NULL,
 end_at TEXT NOT NULL,
 priority TEXT NOT NULL DEFAULT 'normal' CHECK(priority IN ('low','normal','high','urgent')),
 purpose TEXT NOT NULL CHECK(length(trim(purpose))>0),
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','submitted','approved','partially_filled','filled','rejected','closed','cancelled')),
 requested_by_user_id CHAR(32) REFERENCES users(id),
 approved_by_user_id CHAR(32) REFERENCES users(id),
 approved_at TEXT,
 row_version INTEGER NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(end_at>start_at),
 UNIQUE(organization_id,request_no),
 FOREIGN KEY(task_id,organization_id) REFERENCES hr_field_tasks(id,organization_id)
);
CREATE UNIQUE INDEX ux_hr_field_tasks_id_org ON hr_field_tasks(id,organization_id);
CREATE UNIQUE INDEX ux_hr_workforce_requests_id_org ON hr_workforce_requests(id,organization_id);
CREATE INDEX ix_hr_workforce_requests_org_period ON hr_workforce_requests(organization_id,requesting_unit_id,start_at,end_at,status);

CREATE TABLE hr_assignments (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 employee_id CHAR(32) NOT NULL,
 task_id CHAR(32),
 request_id CHAR(32),
 beneficiary_unit_id CHAR(32) NOT NULL REFERENCES organizations(id),
 assignment_kind TEXT NOT NULL CHECK(assignment_kind IN ('direct_task','supervision','unit_allocation','historical_import')),
 exclusivity TEXT NOT NULL CHECK(exclusivity IN ('exclusive','nonexclusive')),
 business_date TEXT NOT NULL,
 start_at TEXT,
 end_at TEXT,
 supervisor_employee_id CHAR(32),
 shift_roster_id CHAR(32),
 allocation_percent INTEGER CHECK(allocation_percent BETWEEN 1 AND 100),
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','pending','approved','active','completed','cancelled')),
 approval_note TEXT NOT NULL DEFAULT '',
 notes TEXT NOT NULL DEFAULT '',
 approved_by_user_id CHAR(32) REFERENCES users(id),
 approved_at TEXT,
 row_version INTEGER NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK((assignment_kind='historical_import' AND start_at IS NULL AND end_at IS NULL) OR (assignment_kind<>'historical_import' AND start_at IS NOT NULL AND end_at IS NOT NULL AND end_at>start_at)),
 CHECK(assignment_kind<>'direct_task' OR task_id IS NOT NULL),
 FOREIGN KEY(employee_id,organization_id) REFERENCES hr_employees(id,organization_id),
 FOREIGN KEY(task_id,organization_id) REFERENCES hr_field_tasks(id,organization_id),
 FOREIGN KEY(request_id,organization_id) REFERENCES hr_workforce_requests(id,organization_id),
 FOREIGN KEY(supervisor_employee_id,organization_id) REFERENCES hr_employees(id,organization_id)
);
CREATE INDEX ix_hr_assignments_employee_time ON hr_assignments(organization_id,employee_id,start_at,end_at,status);
CREATE INDEX ix_hr_assignments_request_time ON hr_assignments(organization_id,request_id,start_at,end_at,status);
CREATE UNIQUE INDEX ux_hr_assignments_id_org ON hr_assignments(id,organization_id);