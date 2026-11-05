-- Additive display/edit fields requested by workspace design; no historical repricing.
ALTER TABLE pm_projects ADD COLUMN client_name TEXT NOT NULL DEFAULT '';
ALTER TABLE pm_activities ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'
    CHECK (priority IN ('low','normal','high','urgent'));
