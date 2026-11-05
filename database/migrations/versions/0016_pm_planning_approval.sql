ALTER TABLE pm_activities ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'pending' CHECK(approval_status IN ('pending','approved','rejected'));
ALTER TABLE pm_activities ADD COLUMN approval_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE pm_activities ADD COLUMN approved_by CHAR(32) REFERENCES users(id);
ALTER TABLE pm_activities ADD COLUMN approved_at TEXT;
