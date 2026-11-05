-- EMO-03: assignments, inspections, and independent safety blockers.
CREATE TABLE eq_assignments (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 asset_id CHAR(32) NOT NULL,
 beneficiary_entity_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 purpose TEXT NOT NULL,
 planned_start_at TEXT NOT NULL,
 planned_end_at TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'draft'
  CHECK(status IN ('draft','approved','dispatched','active','suspended','completed','cancelled')),
 idempotency_key TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 updated_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,idempotency_key),
 FOREIGN KEY(organization_id,asset_id) REFERENCES eq_assets(organization_id,id) ON DELETE RESTRICT
);
CREATE INDEX ix_eq_assignments_asset_period
 ON eq_assignments(organization_id,asset_id,status,planned_start_at,planned_end_at);

CREATE TABLE eq_maintenance_orders (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 asset_id CHAR(32) NOT NULL,
 order_code TEXT NOT NULL,
 maintenance_type TEXT NOT NULL CHECK(maintenance_type IN ('preventive','corrective','emergency')),
 description TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'open'
  CHECK(status IN ('open','in_progress','technically_completed','verified_closed','cancelled')),
 block_status TEXT NOT NULL DEFAULT 'active' CHECK(block_status IN ('active','released','none')),
 block_reason_code TEXT,
 completion_notes TEXT,
 release_inspection_id CHAR(32),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 updated_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,order_code),
 FOREIGN KEY(organization_id,asset_id) REFERENCES eq_assets(organization_id,id) ON DELETE RESTRICT,
 CHECK((block_status='active' AND block_reason_code IS NOT NULL)
    OR (block_status<>'active' AND block_reason_code IS NULL))
);
CREATE INDEX ix_eq_maintenance_asset_block
 ON eq_maintenance_orders(organization_id,asset_id,block_status,status);

CREATE TABLE eq_inspections (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 asset_id CHAR(32) NOT NULL,
 assignment_id CHAR(32),
 inspection_type TEXT NOT NULL
  CHECK(inspection_type IN ('pre_operation','post_repair','periodic','return')),
 result TEXT NOT NULL CHECK(result IN ('passed','conditional','failed')),
 critical_failure INTEGER NOT NULL DEFAULT 0 CHECK(critical_failure IN (0,1)),
 status TEXT NOT NULL DEFAULT 'submitted' CHECK(status IN ('submitted','verified')),
 block_status TEXT NOT NULL DEFAULT 'none' CHECK(block_status IN ('active','released','none')),
 block_reason_code TEXT,
 checklist_version TEXT NOT NULL,
 findings TEXT NOT NULL,
 meter_reading TEXT,
 inspected_at TEXT NOT NULL,
 verified_at TEXT,
 verified_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 release_inspection_id CHAR(32),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 updated_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
 UNIQUE(organization_id,id),
 FOREIGN KEY(organization_id,asset_id) REFERENCES eq_assets(organization_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(organization_id,assignment_id) REFERENCES eq_assignments(organization_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(organization_id,release_inspection_id) REFERENCES eq_inspections(organization_id,id) ON DELETE RESTRICT,
 CHECK((result='failed' AND critical_failure=1 AND block_status IN ('active','released'))
    OR ((result<>'failed' OR critical_failure=0) AND block_status IN ('none','released'))),
 CHECK((block_status='active' AND block_reason_code IS NOT NULL)
    OR (block_status<>'active' AND block_reason_code IS NULL)),
 CHECK((status='submitted' AND verified_at IS NULL AND verified_by IS NULL)
    OR (status='verified' AND verified_at IS NOT NULL AND verified_by IS NOT NULL))
);
CREATE INDEX ix_eq_inspections_asset_block
 ON eq_inspections(organization_id,asset_id,block_status,status,result);
CREATE INDEX ix_eq_inspections_assignment
 ON eq_inspections(organization_id,assignment_id,inspection_type,status);

CREATE TRIGGER trg_eq_inspection_assignment_asset_insert
BEFORE INSERT ON eq_inspections
WHEN NEW.assignment_id IS NOT NULL
 AND NOT EXISTS (
  SELECT 1 FROM eq_assignments a
  WHERE a.organization_id=NEW.organization_id AND a.id=NEW.assignment_id AND a.asset_id=NEW.asset_id
 )
BEGIN
 SELECT RAISE(ABORT,'inspection assignment asset mismatch');
END;

CREATE TRIGGER trg_eq_inspection_assignment_asset_update
BEFORE UPDATE OF organization_id,asset_id,assignment_id ON eq_inspections
WHEN NEW.assignment_id IS NOT NULL
 AND NOT EXISTS (
  SELECT 1 FROM eq_assignments a
  WHERE a.organization_id=NEW.organization_id AND a.id=NEW.assignment_id AND a.asset_id=NEW.asset_id
 )
BEGIN
 SELECT RAISE(ABORT,'inspection assignment asset mismatch');
END;

CREATE TRIGGER trg_eq_maintenance_release_inspection_insert
BEFORE INSERT ON eq_maintenance_orders
WHEN NEW.release_inspection_id IS NOT NULL
 AND NOT EXISTS (
  SELECT 1 FROM eq_inspections i
  WHERE i.organization_id=NEW.organization_id AND i.id=NEW.release_inspection_id AND i.asset_id=NEW.asset_id
 )
BEGIN
 SELECT RAISE(ABORT,'maintenance release inspection asset mismatch');
END;

CREATE TRIGGER trg_eq_maintenance_release_inspection_update
BEFORE UPDATE OF organization_id,asset_id,release_inspection_id ON eq_maintenance_orders
WHEN NEW.release_inspection_id IS NOT NULL
 AND NOT EXISTS (
  SELECT 1 FROM eq_inspections i
  WHERE i.organization_id=NEW.organization_id AND i.id=NEW.release_inspection_id AND i.asset_id=NEW.asset_id
 )
BEGIN
 SELECT RAISE(ABORT,'maintenance release inspection asset mismatch');
END;
