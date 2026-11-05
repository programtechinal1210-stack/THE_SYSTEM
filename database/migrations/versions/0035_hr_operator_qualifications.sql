-- HR owns operator qualification evidence and approval decisions.
CREATE TABLE hr_operator_qualifications (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 employee_id CHAR(32) NOT NULL,
 equipment_class_code TEXT NOT NULL CHECK(length(trim(equipment_class_code)) BETWEEN 1 AND 50),
 qualification_code TEXT NOT NULL CHECK(length(trim(qualification_code)) BETWEEN 1 AND 80),
 credential_reference TEXT NOT NULL CHECK(length(trim(credential_reference)) BETWEEN 1 AND 120),
 issuer_name TEXT NOT NULL CHECK(length(trim(issuer_name)) BETWEEN 1 AND 200),
 evidence_reference TEXT NOT NULL CHECK(length(trim(evidence_reference)) BETWEEN 1 AND 500),
 valid_from TEXT NOT NULL,
 valid_until TEXT,
 status TEXT NOT NULL DEFAULT 'pending'
  CHECK(status IN ('pending','approved','rejected','suspended','revoked')),
 idempotency_key TEXT NOT NULL,
 created_at TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 decided_at TEXT,
 decided_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 decision_reason TEXT,
 decision_authority_ref TEXT,
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,idempotency_key),
 FOREIGN KEY(employee_id,organization_id) REFERENCES hr_employees(id,organization_id) ON DELETE RESTRICT,
 CHECK(valid_until IS NULL OR valid_until>=valid_from),
 CHECK(
  (status='pending' AND decided_at IS NULL AND decided_by IS NULL
   AND decision_reason IS NULL AND decision_authority_ref IS NULL)
  OR
  (status='approved' AND decided_at IS NOT NULL AND decided_by IS NOT NULL
   AND decided_by<>created_by AND decision_authority_ref IS NOT NULL
   AND length(trim(decision_authority_ref))>0 AND decision_reason IS NULL)
  OR
  (status IN ('rejected','suspended','revoked') AND decided_at IS NOT NULL
   AND decided_by IS NOT NULL AND decided_by<>created_by
   AND decision_reason IS NOT NULL AND length(trim(decision_reason))>0
   AND decision_authority_ref IS NOT NULL AND length(trim(decision_authority_ref))>0)
 )
);
CREATE INDEX ix_hr_operator_qualifications_employee
 ON hr_operator_qualifications(organization_id,employee_id,equipment_class_code,status,valid_from,valid_until);

CREATE TRIGGER trg_hr_operator_qualification_insert_pending
BEFORE INSERT ON hr_operator_qualifications
WHEN NEW.status<>'pending' OR NEW.decided_at IS NOT NULL OR NEW.decided_by IS NOT NULL
 OR NEW.decision_reason IS NOT NULL OR NEW.decision_authority_ref IS NOT NULL
BEGIN
 SELECT RAISE(ABORT,'operator qualification must be submitted as pending');
END;

CREATE TRIGGER trg_hr_operator_qualification_no_delete
BEFORE DELETE ON hr_operator_qualifications
BEGIN
 SELECT RAISE(ABORT,'operator qualification history is append-only');
END;

CREATE TRIGGER trg_hr_operator_qualification_content_immutable
BEFORE UPDATE OF id,organization_id,employee_id,equipment_class_code,qualification_code,
 credential_reference,issuer_name,evidence_reference,valid_from,valid_until,idempotency_key,
 created_at,created_by
ON hr_operator_qualifications
BEGIN
 SELECT RAISE(ABORT,'operator qualification evidence is immutable');
END;

CREATE TRIGGER trg_hr_operator_qualification_decision_once
BEFORE UPDATE OF status,decided_at,decided_by,decision_reason,decision_authority_ref
ON hr_operator_qualifications
WHEN NOT (
 (OLD.status='pending' AND NEW.status IN ('approved','rejected'))
 OR (OLD.status='approved' AND NEW.status IN ('suspended','revoked'))
 OR (OLD.status='suspended' AND NEW.status='revoked')
)
 OR NEW.decided_at IS NULL OR NEW.decided_by IS NULL OR NEW.decided_by=OLD.created_by
 OR (NEW.status='approved' AND (
     NEW.decision_reason IS NOT NULL OR NEW.decision_authority_ref IS NULL
     OR length(trim(NEW.decision_authority_ref))=0
 ))
 OR (NEW.status IN ('rejected','suspended','revoked') AND (
     NEW.decision_reason IS NULL OR length(trim(NEW.decision_reason))=0
     OR NEW.decision_authority_ref IS NULL OR length(trim(NEW.decision_authority_ref))=0
 ))
BEGIN
 SELECT RAISE(ABORT,'operator qualification decision is invalid or terminal');
END;
