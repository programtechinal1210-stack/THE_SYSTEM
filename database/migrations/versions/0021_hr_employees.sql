-- HR-01: organization-scoped employees and dated employment decisions.
CREATE TABLE hr_employees (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 employee_no TEXT NOT NULL,
 full_name TEXT NOT NULL CHECK(length(trim(full_name))>0),
 phone TEXT NOT NULL DEFAULT '',
 home_unit_id CHAR(32) NOT NULL REFERENCES organizations(id),
 position_title TEXT NOT NULL DEFAULT '',
 employment_status TEXT NOT NULL CHECK(employment_status IN ('active','suspended','terminated')),
 hire_date TEXT NOT NULL,
 projection_as_of_date TEXT NOT NULL,
 row_version INTEGER NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(organization_id,employee_no)
);
CREATE INDEX ix_hr_employees_org_unit_status ON hr_employees(organization_id,home_unit_id,employment_status);

CREATE TABLE hr_employment_records (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 employee_id CHAR(32) NOT NULL,
 change_type TEXT NOT NULL CHECK(change_type IN ('hire','transfer','position_change','suspension','termination','reinstatement')),
 from_unit_id CHAR(32) REFERENCES organizations(id),
 to_unit_id CHAR(32) REFERENCES organizations(id),
 from_position_title TEXT NOT NULL DEFAULT '',
 to_position_title TEXT NOT NULL DEFAULT '',
 effective_date TEXT NOT NULL,
 reference_no TEXT NOT NULL DEFAULT '',
 supersedes_record_id CHAR(32),
 is_current INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0,1)),
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','rejected','cancelled')),
 reason TEXT NOT NULL DEFAULT '',
 notes TEXT NOT NULL DEFAULT '',
 approved_by_user_id CHAR(32) REFERENCES users(id),
 approved_at TEXT,
 row_version INTEGER NOT NULL DEFAULT 1 CHECK(row_version>0),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(employee_id,organization_id) REFERENCES hr_employees(id,organization_id),
 FOREIGN KEY(supersedes_record_id) REFERENCES hr_employment_records(id)
);
CREATE UNIQUE INDEX ux_hr_employees_id_org ON hr_employees(id,organization_id);
CREATE UNIQUE INDEX ux_hr_records_current_replacement ON hr_employment_records(supersedes_record_id) WHERE supersedes_record_id IS NOT NULL AND is_current=1;
CREATE INDEX ix_hr_records_employee_effective ON hr_employment_records(organization_id,employee_id,effective_date,status,is_current);