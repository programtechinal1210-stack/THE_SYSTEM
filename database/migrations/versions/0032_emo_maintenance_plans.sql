-- EMO-09: organization-scoped preventive plans and plan-linked order snapshots.
CREATE TABLE eq_maintenance_plans (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 asset_id CHAR(32) NOT NULL,
 plan_code TEXT NOT NULL,
 description TEXT NOT NULL,
 interval_days INTEGER,
 interval_meter TEXT,
 meter_type_snapshot TEXT,
 meter_unit_snapshot TEXT,
 meter_generation_snapshot INTEGER,
 next_due_at TEXT,
 next_due_meter TEXT,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused')),
 idempotency_key TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 updated_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,plan_code),
 UNIQUE(organization_id,idempotency_key),
 FOREIGN KEY(organization_id,asset_id) REFERENCES eq_assets(organization_id,id) ON DELETE RESTRICT,
 CHECK(interval_days IS NOT NULL OR interval_meter IS NOT NULL),
 CHECK((interval_days IS NULL AND next_due_at IS NULL)
    OR (interval_days IS NOT NULL AND interval_days > 0 AND next_due_at IS NOT NULL)),
 CHECK((interval_meter IS NULL AND next_due_meter IS NULL
       AND meter_type_snapshot IS NULL AND meter_unit_snapshot IS NULL
       AND meter_generation_snapshot IS NULL)
    OR (interval_meter IS NOT NULL AND CAST(interval_meter AS REAL) > 0
       AND next_due_meter IS NOT NULL AND CAST(next_due_meter AS REAL) >= 0
       AND meter_type_snapshot IS NOT NULL AND meter_unit_snapshot IS NOT NULL
       AND meter_generation_snapshot IS NOT NULL AND meter_generation_snapshot >= 1))
);
CREATE INDEX ix_eq_maintenance_plans_due
 ON eq_maintenance_plans(organization_id,status,next_due_at,asset_id);
CREATE INDEX ix_eq_maintenance_plans_meter_due
 ON eq_maintenance_plans(organization_id,status,asset_id);

ALTER TABLE eq_maintenance_orders ADD COLUMN plan_id CHAR(32)
 REFERENCES eq_maintenance_plans(id) ON DELETE RESTRICT;
ALTER TABLE eq_maintenance_orders ADD COLUMN plan_due_at TEXT;
ALTER TABLE eq_maintenance_orders ADD COLUMN plan_due_meter TEXT;
ALTER TABLE eq_maintenance_orders ADD COLUMN plan_cycle_key TEXT;
CREATE UNIQUE INDEX ux_eq_maintenance_plan_cycle
 ON eq_maintenance_orders(organization_id,plan_id,plan_cycle_key);

CREATE TRIGGER trg_eq_maintenance_plan_order_insert
BEFORE INSERT ON eq_maintenance_orders
WHEN NEW.plan_id IS NOT NULL AND NOT EXISTS (
 SELECT 1 FROM eq_maintenance_plans p
 WHERE p.id=NEW.plan_id AND p.organization_id=NEW.organization_id
   AND p.asset_id=NEW.asset_id AND NEW.maintenance_type='preventive'
   AND NEW.plan_cycle_key IS NOT NULL
)
BEGIN
 SELECT RAISE(ABORT,'maintenance plan order reference mismatch');
END;

CREATE TRIGGER trg_eq_maintenance_plan_order_update
BEFORE UPDATE OF plan_id,plan_cycle_key,organization_id,asset_id,maintenance_type
ON eq_maintenance_orders
WHEN NEW.plan_id IS NOT NULL AND NOT EXISTS (
 SELECT 1 FROM eq_maintenance_plans p
 WHERE p.id=NEW.plan_id AND p.organization_id=NEW.organization_id
   AND p.asset_id=NEW.asset_id AND NEW.maintenance_type='preventive'
   AND NEW.plan_cycle_key IS NOT NULL
)
BEGIN
 SELECT RAISE(ABORT,'maintenance plan order reference mismatch');
END;
