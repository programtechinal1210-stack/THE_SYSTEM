-- EMO-04: equipment requests and links to one-asset assignments.
CREATE TABLE eq_requests (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 request_code TEXT NOT NULL,
 requested_entity_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 category_id CHAR(32) NOT NULL,
 required_quantity INTEGER NOT NULL CHECK(required_quantity > 0),
 required_start TEXT NOT NULL,
 required_end TEXT NOT NULL,
 required_specs TEXT NOT NULL DEFAULT '{}',
 target_location TEXT NOT NULL DEFAULT '',
 purpose TEXT NOT NULL,
 priority TEXT NOT NULL CHECK(priority IN ('low','normal','high','critical')),
 status TEXT NOT NULL DEFAULT 'submitted'
  CHECK(status IN ('submitted','approved','partially_fulfilled','fulfilled','rejected','cancelled')),
 requested_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 approved_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 decided_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 decision_at TEXT,
 decision_reason TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 updated_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,request_code),
 FOREIGN KEY(organization_id,category_id) REFERENCES eq_categories(organization_id,id) ON DELETE RESTRICT,
 CHECK(required_start < required_end),
 CHECK(
  (status='submitted' AND approved_by IS NULL AND decided_by IS NULL AND decision_at IS NULL)
  OR (status IN ('approved','partially_fulfilled','fulfilled')
      AND approved_by IS NOT NULL AND decided_by IS NOT NULL AND decision_at IS NOT NULL)
  OR (status IN ('rejected','cancelled')
      AND approved_by IS NULL AND decided_by IS NOT NULL AND decision_at IS NOT NULL)
 )
);
CREATE INDEX ix_eq_requests_scope_status
 ON eq_requests(organization_id,requested_entity_id,status,required_start,required_end);

ALTER TABLE eq_assignments ADD COLUMN request_id CHAR(32)
 REFERENCES eq_requests(id) ON DELETE RESTRICT;
CREATE INDEX ix_eq_assignments_request_status
 ON eq_assignments(organization_id,request_id,status);

CREATE TRIGGER trg_eq_assignment_request_insert
BEFORE INSERT ON eq_assignments
WHEN NEW.request_id IS NOT NULL
 AND NOT EXISTS (
  SELECT 1 FROM eq_requests r
  JOIN eq_assets a ON a.id=NEW.asset_id AND a.organization_id=NEW.organization_id
  WHERE r.id=NEW.request_id AND r.organization_id=NEW.organization_id
    AND r.category_id=a.category_id AND r.status IN ('approved','partially_fulfilled')
    AND NEW.planned_start_at>=r.required_start AND NEW.planned_end_at<=r.required_end
    AND r.requested_entity_id=NEW.beneficiary_entity_id
 )
BEGIN
 SELECT RAISE(ABORT,'assignment does not fulfill its request');
END;

CREATE TRIGGER trg_eq_assignment_request_update
BEFORE UPDATE OF organization_id,asset_id,request_id,beneficiary_entity_id,planned_start_at,planned_end_at
ON eq_assignments
WHEN NEW.request_id IS NOT NULL
 AND NOT EXISTS (
  SELECT 1 FROM eq_requests r
  JOIN eq_assets a ON a.id=NEW.asset_id AND a.organization_id=NEW.organization_id
  WHERE r.id=NEW.request_id AND r.organization_id=NEW.organization_id
    AND r.category_id=a.category_id AND r.status IN ('approved','partially_fulfilled','fulfilled')
    AND NEW.planned_start_at>=r.required_start AND NEW.planned_end_at<=r.required_end
    AND r.requested_entity_id=NEW.beneficiary_entity_id
 )
BEGIN
 SELECT RAISE(ABORT,'assignment does not fulfill its request');
END;
