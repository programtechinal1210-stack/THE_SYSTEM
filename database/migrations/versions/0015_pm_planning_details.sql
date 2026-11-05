-- Additive planning details. Existing quantities, costs, FX and history stay unchanged.
ALTER TABLE pm_phases ADD COLUMN owner_user_id CHAR(32) REFERENCES users(id);
ALTER TABLE pm_tasks ADD COLUMN owner_user_id CHAR(32) REFERENCES users(id);
ALTER TABLE pm_activities ADD COLUMN description TEXT NOT NULL DEFAULT '';
ALTER TABLE pm_activities ADD COLUMN notes TEXT NOT NULL DEFAULT '';
ALTER TABLE pm_activities ADD COLUMN attachment_url TEXT NOT NULL DEFAULT '';
ALTER TABLE pm_activities ADD COLUMN planned_start_date TEXT;
ALTER TABLE pm_activities ADD COLUMN planned_end_date TEXT;
ALTER TABLE pm_activity_resource_requirements ADD COLUMN productivity TEXT NOT NULL DEFAULT '0';
ALTER TABLE pm_activity_resource_requirements ADD COLUMN source TEXT NOT NULL DEFAULT '';
ALTER TABLE pm_activity_resource_requirements ADD COLUMN item_category TEXT NOT NULL DEFAULT '';
ALTER TABLE pm_activity_resource_requirements ADD COLUMN notes TEXT NOT NULL DEFAULT '';
