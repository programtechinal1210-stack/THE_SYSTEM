-- HR-03/04/05. The remaining six HR tables; total HR base tables remain nine.
CREATE TABLE hr_shift_templates (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 code TEXT NOT NULL,
 name_ar TEXT NOT NULL,
 start_local_time TEXT NOT NULL,
 end_local_time TEXT NOT NULL,
 end_day_offset INTEGER NOT NULL CHECK(end_day_offset IN (0,1)),
 break_minutes INTEGER NOT NULL DEFAULT 0 CHECK(break_minutes>=0),
 timezone_name TEXT NOT NULL DEFAULT 'UTC',
 is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
 row_version INTEGER NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(organization_id,code)
);
CREATE UNIQUE INDEX ux_hr_shift_templates_id_org ON hr_shift_templates(id,organization_id);

CREATE TABLE hr_shift_roster (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 employee_id CHAR(32) NOT NULL,
 shift_template_id CHAR(32),
 owner_unit_id CHAR(32) NOT NULL REFERENCES organizations(id),
 work_unit_id CHAR(32) NOT NULL REFERENCES organizations(id),
 business_date TEXT NOT NULL,
 start_at TEXT NOT NULL,
 end_at TEXT NOT NULL,
 planned_break_minutes INTEGER NOT NULL DEFAULT 0 CHECK(planned_break_minutes>=0),
 location_text TEXT NOT NULL DEFAULT '',
 shift_name_snapshot TEXT NOT NULL DEFAULT '',
 timezone_name_snapshot TEXT NOT NULL DEFAULT 'UTC',
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','confirmed','completed','cancelled')),
 confirmed_by_user_id CHAR(32) REFERENCES users(id),
 confirmed_at TEXT,
 notes TEXT NOT NULL DEFAULT '',
 row_version INTEGER NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK(end_at>start_at),
 FOREIGN KEY(employee_id,organization_id) REFERENCES hr_employees(id,organization_id),
 FOREIGN KEY(shift_template_id,organization_id) REFERENCES hr_shift_templates(id,organization_id)
);
CREATE UNIQUE INDEX ux_hr_shift_roster_id_org ON hr_shift_roster(id,organization_id);
CREATE INDEX ix_hr_shift_roster_employee_time ON hr_shift_roster(organization_id,employee_id,start_at,end_at,status);

CREATE TABLE hr_attendance (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 employee_id CHAR(32) NOT NULL,
 attendance_kind TEXT NOT NULL CHECK(attendance_kind IN ('base_shift','base_unscheduled','task_participation')),
 shift_roster_id CHAR(32),
 assignment_id CHAR(32),
 task_id CHAR(32),
 business_date TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','present','absent','partial','late','excused','participated','not_participated','unknown')),
 approval_status TEXT NOT NULL DEFAULT 'draft' CHECK(approval_status IN ('draft','submitted','approved','rejected')),
 source TEXT NOT NULL DEFAULT 'manual' CHECK(source IN ('manual','device','import')),
 source_system TEXT,
 source_record_id TEXT,
 check_in_at TEXT,
 check_out_at TEXT,
 root_attendance_id CHAR(32),
 supersedes_attendance_id CHAR(32),
 supersedes_row_version INTEGER,
 is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0,1)),
 notes TEXT NOT NULL DEFAULT '',
 approved_by_user_id CHAR(32) REFERENCES users(id),
 approved_at TEXT,
 row_version INTEGER NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CHECK((check_in_at IS NULL AND check_out_at IS NULL) OR (check_in_at IS NOT NULL AND check_out_at IS NOT NULL AND check_out_at>=check_in_at)),
 CHECK((attendance_kind='task_participation' AND assignment_id IS NOT NULL AND root_attendance_id IS NOT NULL) OR attendance_kind<>'task_participation'),
 FOREIGN KEY(employee_id,organization_id) REFERENCES hr_employees(id,organization_id),
 FOREIGN KEY(shift_roster_id,organization_id) REFERENCES hr_shift_roster(id,organization_id),
 FOREIGN KEY(assignment_id,organization_id) REFERENCES hr_assignments(id,organization_id),
 FOREIGN KEY(task_id,organization_id) REFERENCES hr_field_tasks(id,organization_id),
 FOREIGN KEY(root_attendance_id) REFERENCES hr_attendance(id),
 FOREIGN KEY(supersedes_attendance_id) REFERENCES hr_attendance(id)
);
CREATE UNIQUE INDEX ux_hr_attendance_id_org ON hr_attendance(id,organization_id);
CREATE UNIQUE INDEX ux_hr_attendance_base_current ON hr_attendance(organization_id,employee_id,shift_roster_id) WHERE attendance_kind='base_shift' AND is_current=1;
CREATE UNIQUE INDEX ux_hr_attendance_unscheduled_current ON hr_attendance(organization_id,employee_id,business_date) WHERE attendance_kind='base_unscheduled' AND is_current=1;
CREATE UNIQUE INDEX ux_hr_attendance_replacement ON hr_attendance(supersedes_attendance_id) WHERE supersedes_attendance_id IS NOT NULL AND is_current=1;
CREATE UNIQUE INDEX ux_hr_attendance_task_current ON hr_attendance(organization_id,root_attendance_id,assignment_id) WHERE attendance_kind='task_participation' AND is_current=1 AND root_attendance_id IS NOT NULL AND assignment_id IS NOT NULL;
CREATE UNIQUE INDEX ux_hr_attendance_source_record ON hr_attendance(organization_id,source_system,source_record_id) WHERE source_system IS NOT NULL AND source_record_id IS NOT NULL;
CREATE INDEX ix_hr_attendance_org_date ON hr_attendance(organization_id,business_date,employee_id,attendance_kind,status,is_current);

CREATE TABLE hr_attendance_issues (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 employee_id CHAR(32),
 attendance_id CHAR(32),
 task_id CHAR(32),
 issue_type TEXT NOT NULL CHECK(issue_type IN ('absence','late','early_exit','missing_coverage','field_problem','other')),
 business_date TEXT NOT NULL,
 priority TEXT NOT NULL DEFAULT 'normal' CHECK(priority IN ('low','normal','high','urgent')),
 solution_status TEXT NOT NULL DEFAULT 'not_started' CHECK(solution_status IN ('not_started','in_progress','resolved','closed','cancelled')),
 excuse_decision TEXT NOT NULL DEFAULT 'not_applicable' CHECK(excuse_decision IN ('not_applicable','pending','accepted','rejected')),
 reason TEXT NOT NULL DEFAULT '',
 proposed_solution TEXT NOT NULL DEFAULT '',
 responsible_unit_id CHAR(32) REFERENCES organizations(id),
 responsible_employee_id CHAR(32),
 responsible_user_id CHAR(32) REFERENCES users(id),
 resolution_notes TEXT NOT NULL DEFAULT '',
 resolved_at TEXT,
 closed_at TEXT,
 row_version INTEGER NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(employee_id,organization_id) REFERENCES hr_employees(id,organization_id),
 FOREIGN KEY(attendance_id,organization_id) REFERENCES hr_attendance(id,organization_id),
 FOREIGN KEY(task_id,organization_id) REFERENCES hr_field_tasks(id,organization_id),
 FOREIGN KEY(responsible_employee_id,organization_id) REFERENCES hr_employees(id,organization_id)
);
CREATE INDEX ix_hr_attendance_issues_org_status ON hr_attendance_issues(organization_id,solution_status,created_at);