CREATE TABLE eq_safety_policies (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 policy_version INTEGER NOT NULL CHECK(policy_version>0),
 policy_mode TEXT NOT NULL CHECK(policy_mode IN ('test','production')),
 policy_reference TEXT NOT NULL CHECK(length(trim(policy_reference)) BETWEEN 1 AND 120),
 policy_document_ref TEXT NOT NULL CHECK(length(trim(policy_document_ref)) BETWEEN 1 AND 500),
 issuing_authority TEXT NOT NULL CHECK(length(trim(issuing_authority)) BETWEEN 1 AND 200),
 authorized_role_code TEXT NOT NULL CHECK(length(trim(authorized_role_code)) BETWEEN 1 AND 120),
 inspection_validity_minutes INTEGER NOT NULL CHECK(inspection_validity_minutes BETWEEN 1 AND 1440),
 effective_from TEXT NOT NULL,
 effective_until TEXT,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved','withdrawn')),
 created_at TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 reviewed_at TEXT,
 reviewed_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 decision_authority_ref TEXT,
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,policy_mode,policy_version),
 CHECK(effective_until IS NULL OR effective_until>=effective_from),
 CHECK(
  (status='draft' AND reviewed_at IS NULL AND reviewed_by IS NULL AND decision_authority_ref IS NULL)
  OR
  (status='approved' AND reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL
   AND reviewed_by<>created_by AND decision_authority_ref IS NOT NULL
   AND length(trim(decision_authority_ref))>0)
  OR
  (status='withdrawn' AND reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL
   AND decision_authority_ref IS NOT NULL AND length(trim(decision_authority_ref))>0)
 )
);
CREATE UNIQUE INDEX ux_eq_safety_policy_current
 ON eq_safety_policies(organization_id,policy_mode)
 WHERE status='approved';

CREATE TRIGGER trg_eq_safety_policy_no_delete
BEFORE DELETE ON eq_safety_policies
BEGIN
 SELECT RAISE(ABORT,'safety policy history is append-only');
END;

CREATE TRIGGER trg_eq_safety_policy_content_immutable
BEFORE UPDATE OF id,organization_id,policy_version,policy_mode,policy_reference,
 policy_document_ref,issuing_authority,authorized_role_code,effective_from,effective_until,
 created_at,created_by
ON eq_safety_policies
BEGIN
 SELECT RAISE(ABORT,'safety policy content is immutable');
END;

CREATE TRIGGER trg_eq_safety_policy_decision_once
BEFORE UPDATE OF status,reviewed_at,reviewed_by,decision_authority_ref
ON eq_safety_policies
WHEN OLD.status<>'draft' OR NEW.status NOT IN ('approved','withdrawn')
 OR NEW.reviewed_at IS NULL OR NEW.reviewed_by IS NULL
 OR NEW.reviewed_by=OLD.created_by OR NEW.decision_authority_ref IS NULL
 OR length(trim(NEW.decision_authority_ref))=0
BEGIN
 SELECT RAISE(ABORT,'safety policy decision is invalid or terminal');
END;

CREATE TABLE eq_operation_logs (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 asset_id CHAR(32) NOT NULL,
 assignment_id CHAR(32) NOT NULL,
 operator_employee_id CHAR(32) NOT NULL,
 shift_roster_id CHAR(32) NOT NULL,
 safety_policy_id CHAR(32) NOT NULL,
 policy_mode TEXT NOT NULL CHECK(policy_mode IN ('test','production')),
 operation_code TEXT NOT NULL,
 started_at TEXT NOT NULL,
 ended_at TEXT,
 meter_type_snapshot TEXT NOT NULL,
 meter_unit_snapshot TEXT NOT NULL,
 meter_generation_snapshot INTEGER NOT NULL CHECK(meter_generation_snapshot>=1),
 meter_start TEXT,
 meter_end TEXT,
 working_minutes INTEGER CHECK(working_minutes IS NULL OR working_minutes>=0),
 idle_minutes INTEGER CHECK(idle_minutes IS NULL OR idle_minutes>=0),
 downtime_minutes INTEGER CHECK(downtime_minutes IS NULL OR downtime_minutes>=0),
 produced_quantity TEXT,
 production_unit TEXT,
 fuel_consumed TEXT,
 downtime_reason_code TEXT,
 downtime_notes TEXT NOT NULL DEFAULT '',
 notes TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'running' CHECK(status IN ('running','submitted','verified','corrected','voided')),
 idempotency_key TEXT NOT NULL,
 start_payload_hash TEXT NOT NULL,
 finish_payload_hash TEXT,
 created_at TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 verified_at TEXT,
 verified_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 supersedes_log_id CHAR(32),
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,operation_code),
 UNIQUE(organization_id,idempotency_key),
 FOREIGN KEY(organization_id,asset_id) REFERENCES eq_assets(organization_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(organization_id,assignment_id) REFERENCES eq_assignments(organization_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(operator_employee_id,organization_id) REFERENCES hr_employees(id,organization_id) ON DELETE RESTRICT,
 FOREIGN KEY(shift_roster_id,organization_id) REFERENCES hr_shift_roster(id,organization_id) ON DELETE RESTRICT,
 FOREIGN KEY(organization_id,safety_policy_id) REFERENCES eq_safety_policies(organization_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(organization_id,supersedes_log_id) REFERENCES eq_operation_logs(organization_id,id) ON DELETE RESTRICT,
 CHECK(ended_at IS NULL OR ended_at>started_at),
 CHECK((meter_start IS NULL AND meter_end IS NULL) OR meter_start IS NOT NULL),
 CHECK((produced_quantity IS NULL AND production_unit IS NULL)
    OR (produced_quantity IS NOT NULL AND production_unit IS NOT NULL)),
 CHECK((status IN ('running','submitted') AND verified_at IS NULL AND verified_by IS NULL)
    OR (status IN ('verified','corrected','voided') AND verified_at IS NOT NULL AND verified_by IS NOT NULL)),
 CHECK(
  (status='running' AND ended_at IS NULL AND working_minutes IS NULL
   AND idle_minutes IS NULL AND downtime_minutes IS NULL)
  OR
  (status<>'running' AND ended_at IS NOT NULL AND working_minutes IS NOT NULL
   AND idle_minutes IS NOT NULL AND downtime_minutes IS NOT NULL)
 )
);
CREATE INDEX ix_eq_operation_logs_asset_period
 ON eq_operation_logs(organization_id,asset_id,started_at,status);
CREATE INDEX ix_eq_operation_logs_operator_period
 ON eq_operation_logs(organization_id,operator_employee_id,started_at,status);
CREATE UNIQUE INDEX ux_eq_operation_logs_running_asset
 ON eq_operation_logs(organization_id,asset_id) WHERE status='running';

CREATE TRIGGER trg_eq_operation_log_no_delete
BEFORE DELETE ON eq_operation_logs
BEGIN
 SELECT RAISE(ABORT,'operation history is append-only');
END;

CREATE TRIGGER trg_eq_operation_log_transition
BEFORE UPDATE ON eq_operation_logs
WHEN NOT (
 (OLD.status='running' AND NEW.status='submitted'
  AND NEW.id=OLD.id AND NEW.organization_id=OLD.organization_id
  AND NEW.asset_id=OLD.asset_id AND NEW.assignment_id=OLD.assignment_id
  AND NEW.operator_employee_id=OLD.operator_employee_id AND NEW.shift_roster_id=OLD.shift_roster_id
  AND NEW.safety_policy_id=OLD.safety_policy_id AND NEW.policy_mode=OLD.policy_mode
  AND NEW.operation_code=OLD.operation_code AND NEW.started_at=OLD.started_at
  AND NEW.meter_type_snapshot=OLD.meter_type_snapshot AND NEW.meter_unit_snapshot=OLD.meter_unit_snapshot
  AND NEW.meter_generation_snapshot=OLD.meter_generation_snapshot AND NEW.meter_start=OLD.meter_start
  AND NEW.idempotency_key=OLD.idempotency_key AND NEW.start_payload_hash=OLD.start_payload_hash
  AND NEW.created_at=OLD.created_at AND NEW.created_by=OLD.created_by
  AND NEW.verified_at IS NULL AND NEW.verified_by IS NULL
  AND NEW.finish_payload_hash IS NOT NULL)
 OR
 (OLD.status='submitted' AND NEW.status='verified'
  AND NEW.verified_at IS NOT NULL AND NEW.verified_by IS NOT NULL
  AND NEW.verified_by<>OLD.created_by
  AND NEW.id=OLD.id AND NEW.organization_id=OLD.organization_id
  AND NEW.asset_id=OLD.asset_id AND NEW.assignment_id=OLD.assignment_id
  AND NEW.operator_employee_id=OLD.operator_employee_id AND NEW.shift_roster_id=OLD.shift_roster_id
  AND NEW.safety_policy_id=OLD.safety_policy_id AND NEW.policy_mode=OLD.policy_mode
  AND NEW.operation_code=OLD.operation_code AND NEW.started_at=OLD.started_at
  AND NEW.ended_at=OLD.ended_at AND NEW.meter_type_snapshot=OLD.meter_type_snapshot
  AND NEW.meter_unit_snapshot=OLD.meter_unit_snapshot
  AND NEW.meter_generation_snapshot=OLD.meter_generation_snapshot
  AND NEW.meter_start IS OLD.meter_start AND NEW.meter_end IS OLD.meter_end
  AND NEW.working_minutes=OLD.working_minutes AND NEW.idle_minutes=OLD.idle_minutes
  AND NEW.downtime_minutes=OLD.downtime_minutes
  AND NEW.produced_quantity IS OLD.produced_quantity AND NEW.production_unit IS OLD.production_unit
  AND NEW.fuel_consumed IS OLD.fuel_consumed
  AND NEW.downtime_reason_code IS OLD.downtime_reason_code
  AND NEW.downtime_notes=OLD.downtime_notes AND NEW.notes=OLD.notes
  AND NEW.idempotency_key=OLD.idempotency_key
  AND NEW.start_payload_hash=OLD.start_payload_hash
  AND NEW.finish_payload_hash=OLD.finish_payload_hash
  AND NEW.created_at=OLD.created_at AND NEW.created_by=OLD.created_by
  AND NEW.supersedes_log_id IS OLD.supersedes_log_id)
)
BEGIN
 SELECT RAISE(ABORT,'operation log transition or immutable history violation');
END;

ALTER TABLE eq_fuel_events ADD COLUMN operation_log_id CHAR(32);
CREATE INDEX ix_eq_fuel_events_operation ON eq_fuel_events(organization_id,operation_log_id);
CREATE TRIGGER trg_eq_fuel_operation_scope
BEFORE INSERT ON eq_fuel_events
WHEN NEW.operation_log_id IS NOT NULL AND NOT EXISTS (
 SELECT 1 FROM eq_operation_logs o
 WHERE o.organization_id=NEW.organization_id AND o.id=NEW.operation_log_id
  AND o.asset_id=NEW.asset_id
)
BEGIN
 SELECT RAISE(ABORT,'fuel operation link must use same organization and asset');
END;

CREATE TRIGGER trg_eq_fuel_operation_link_immutable
BEFORE UPDATE OF operation_log_id ON eq_fuel_events
WHEN NEW.operation_log_id IS NOT OLD.operation_log_id
BEGIN
 SELECT RAISE(ABORT,'fuel operation link is immutable');
END;
