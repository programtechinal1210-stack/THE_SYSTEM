-- EMO-05: controlled equipment movement and receipt records.
CREATE TABLE eq_movements (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 asset_id CHAR(32) NOT NULL,
 movement_code TEXT NOT NULL,
 from_entity_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 to_entity_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 from_location TEXT NOT NULL DEFAULT '',
 to_location TEXT NOT NULL,
 movement_reason TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','dispatched','received','cancelled')),
 idempotency_key TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 dispatched_at TEXT,
 handed_over_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 received_at TEXT,
 received_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 condition_at_receipt TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 updated_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,movement_code),
 UNIQUE(organization_id,idempotency_key),
 FOREIGN KEY(organization_id,asset_id) REFERENCES eq_assets(organization_id,id) ON DELETE RESTRICT,
 CHECK(
  (status='draft' AND dispatched_at IS NULL AND handed_over_by IS NULL
   AND received_at IS NULL AND received_by IS NULL)
  OR (status='dispatched' AND dispatched_at IS NOT NULL AND handed_over_by IS NOT NULL
      AND received_at IS NULL AND received_by IS NULL)
  OR (status='received' AND dispatched_at IS NOT NULL AND handed_over_by IS NOT NULL
      AND received_at IS NOT NULL AND received_by IS NOT NULL AND condition_at_receipt IS NOT NULL)
  OR (status='cancelled')
 ),
 CHECK(status<>'received' OR received_by<>handed_over_by)
);
CREATE INDEX ix_eq_movements_asset_status
 ON eq_movements(organization_id,asset_id,status,created_at);
CREATE UNIQUE INDEX ux_eq_movements_asset_open
 ON eq_movements(organization_id,asset_id) WHERE status IN ('draft','dispatched');
