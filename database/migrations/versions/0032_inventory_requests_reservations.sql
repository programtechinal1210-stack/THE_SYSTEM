-- Isolated development; explicit header mapping, never modify 0031.
-- Deferral keeps foreign keys enabled; migrate_core validates them before commit.
PRAGMA defer_foreign_keys=ON;
CREATE TABLE inv_material_requests_next (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 request_no TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','SUBMITTED','APPROVED','PARTIAL','FULFILLED','CANCELLED','REJECTED','CLOSED')),
 created_by CHAR(32) NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 department_id CHAR(32) REFERENCES organizations(id),
 submitted_by CHAR(32) REFERENCES users(id), submitted_at TEXT,
 approved_by CHAR(32) REFERENCES users(id), approved_at TEXT,
 closed_by CHAR(32) REFERENCES users(id), closed_at TEXT,
 decision_reason TEXT,
 UNIQUE(organization_id,request_no),
 CHECK(approved_by IS NULL OR approved_by<>created_by),
 CHECK(status NOT IN ('APPROVED','PARTIAL','FULFILLED') OR approved_by IS NOT NULL)
);
INSERT INTO inv_material_requests_next(id,organization_id,request_no,status,created_by,created_at,updated_at)
 SELECT id,organization_id,request_no,status,created_by,created_at,created_at FROM inv_material_requests;
DROP TABLE inv_material_requests;
ALTER TABLE inv_material_requests_next RENAME TO inv_material_requests;
CREATE INDEX ix_inv_requests_scope ON inv_material_requests(organization_id,status,created_at);
CREATE INDEX ix_inv_request_lines_request ON inv_request_lines(request_id);
CREATE TABLE inv_reservations (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 legal_entity_id CHAR(32) NOT NULL REFERENCES core_legal_entities(id),
 request_line_id CHAR(32) NOT NULL REFERENCES inv_request_lines(id),
 warehouse_id CHAR(32) NOT NULL REFERENCES inv_warehouses(id),
 location_id CHAR(32) REFERENCES inv_locations(id),
 item_id CHAR(32) NOT NULL REFERENCES inv_items(id),
 reservation_key TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 quantity TEXT NOT NULL,
 fulfilled_qty TEXT NOT NULL DEFAULT '0',
 status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','FULFILLED','RELEASED','EXPIRED')),
 expires_at TEXT,
 created_by CHAR(32) NOT NULL REFERENCES users(id), created_at TEXT NOT NULL,
 updated_by CHAR(32) NOT NULL REFERENCES users(id), updated_at TEXT NOT NULL,
 UNIQUE(organization_id,reservation_key)
);
CREATE INDEX ix_inv_reservation_request ON inv_reservations(request_line_id,status);
CREATE INDEX ix_inv_reservation_balance ON inv_reservations(warehouse_id,item_id,location_id,status,expires_at);
