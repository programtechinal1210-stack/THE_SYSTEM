-- EMO-08: operational fuel/energy balance, distinct from Inventory stock and accounting.
CREATE TABLE eq_fuel_events (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 asset_id CHAR(32) NOT NULL,
 fuel_event_code TEXT NOT NULL,
 event_type TEXT NOT NULL CHECK(event_type IN (
  'opening','issued','consumed','returned','adjustment_in','adjustment_out'
 )),
 energy_type TEXT NOT NULL CHECK(energy_type IN ('diesel','gasoline','electricity','other')),
 quantity TEXT NOT NULL,
 unit TEXT NOT NULL,
 event_at TEXT NOT NULL,
 unit_cost TEXT,
 cost_amount TEXT,
 currency_id CHAR(32) REFERENCES core_currencies(id) ON DELETE RESTRICT,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','posted','rejected')),
 reason_code TEXT,
 notes TEXT NOT NULL DEFAULT '',
 idempotency_key TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 reviewed_at TEXT,
 reviewed_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 rejection_reason TEXT,
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,fuel_event_code),
 UNIQUE(organization_id,idempotency_key),
 FOREIGN KEY(organization_id,asset_id) REFERENCES eq_assets(organization_id,id) ON DELETE RESTRICT,
 CHECK((unit_cost IS NULL AND cost_amount IS NULL AND currency_id IS NULL)
    OR (unit_cost IS NOT NULL AND cost_amount IS NOT NULL AND currency_id IS NOT NULL)),
 CHECK((event_type IN ('adjustment_in','adjustment_out') AND reason_code IS NOT NULL)
    OR event_type NOT IN ('adjustment_in','adjustment_out')),
 CHECK(
  (status='draft' AND reviewed_at IS NULL AND reviewed_by IS NULL AND rejection_reason IS NULL)
  OR (status='posted' AND reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL AND rejection_reason IS NULL)
  OR (status='rejected' AND reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL
      AND rejection_reason IS NOT NULL AND length(trim(rejection_reason))>0)
 )
);
CREATE INDEX ix_eq_fuel_events_ledger
 ON eq_fuel_events(organization_id,asset_id,energy_type,unit,status,event_at,id);
CREATE UNIQUE INDEX ux_eq_fuel_events_opening
 ON eq_fuel_events(organization_id,asset_id,energy_type,unit)
 WHERE event_type='opening' AND status IN ('draft','posted');

CREATE TRIGGER trg_eq_fuel_event_insert_draft
BEFORE INSERT ON eq_fuel_events
WHEN NEW.status<>'draft' OR NEW.reviewed_at IS NOT NULL OR NEW.reviewed_by IS NOT NULL
 OR NEW.rejection_reason IS NOT NULL
BEGIN
 SELECT RAISE(ABORT,'fuel events must be created as drafts');
END;

CREATE TRIGGER trg_eq_fuel_event_no_delete
BEFORE DELETE ON eq_fuel_events
BEGIN
 SELECT RAISE(ABORT,'fuel events are append-only');
END;

CREATE TRIGGER trg_eq_fuel_event_no_content_update
BEFORE UPDATE OF id,organization_id,asset_id,fuel_event_code,event_type,energy_type,quantity,unit,
 event_at,unit_cost,cost_amount,currency_id,reason_code,notes,idempotency_key,payload_hash,created_at,created_by
ON eq_fuel_events
BEGIN
 SELECT RAISE(ABORT,'fuel event content is immutable');
END;

CREATE TRIGGER trg_eq_fuel_event_review_once
BEFORE UPDATE OF status,reviewed_at,reviewed_by,rejection_reason ON eq_fuel_events
WHEN OLD.status<>'draft'
 OR NEW.status NOT IN ('posted','rejected')
 OR NEW.reviewed_at IS NULL
 OR NEW.reviewed_by IS NULL
 OR (NEW.status='posted' AND NEW.rejection_reason IS NOT NULL)
 OR (NEW.status='rejected' AND (NEW.rejection_reason IS NULL OR length(trim(NEW.rejection_reason))=0))
BEGIN
 SELECT RAISE(ABORT,'fuel event review is a one-way transition');
END;
