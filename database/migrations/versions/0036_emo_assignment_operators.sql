-- EMO-11: reference the authoritative HR employee record; never copy HR identity.
ALTER TABLE eq_assignments
 ADD COLUMN operator_employee_id CHAR(32) REFERENCES hr_employees(id) ON DELETE RESTRICT;

CREATE INDEX ix_eq_assignments_operator_period
 ON eq_assignments(organization_id,operator_employee_id,status,planned_start_at,planned_end_at);

CREATE TRIGGER trg_eq_assignment_operator_org_insert
BEFORE INSERT ON eq_assignments
WHEN NEW.operator_employee_id IS NOT NULL
 AND NOT EXISTS (
  SELECT 1 FROM hr_employees e
  WHERE e.id=NEW.operator_employee_id AND e.organization_id=NEW.organization_id
 )
BEGIN
 SELECT RAISE(ABORT,'assignment operator must be an employee in the same organization');
END;

CREATE TRIGGER trg_eq_assignment_operator_org_update
BEFORE UPDATE OF organization_id,operator_employee_id ON eq_assignments
WHEN NEW.operator_employee_id IS NOT NULL
 AND NOT EXISTS (
  SELECT 1 FROM hr_employees e
  WHERE e.id=NEW.operator_employee_id AND e.organization_id=NEW.organization_id
 )
BEGIN
 SELECT RAISE(ABORT,'assignment operator must be an employee in the same organization');
END;
