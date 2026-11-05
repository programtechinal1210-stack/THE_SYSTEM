-- Extend PM work orders with explicit manager decisions and partial-close provenance.
ALTER TABLE pm_work_orders ADD COLUMN approved_by CHAR(32) REFERENCES users(id);
ALTER TABLE pm_work_orders ADD COLUMN approved_at TEXT;
ALTER TABLE pm_work_orders ADD COLUMN rejected_by CHAR(32) REFERENCES users(id);
ALTER TABLE pm_work_orders ADD COLUMN rejected_at TEXT;
ALTER TABLE pm_work_orders ADD COLUMN rejection_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE pm_work_orders ADD COLUMN partial_close_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE pm_work_orders ADD COLUMN partial_closed_by CHAR(32) REFERENCES users(id);
ALTER TABLE pm_work_orders ADD COLUMN partial_closed_at TEXT;
