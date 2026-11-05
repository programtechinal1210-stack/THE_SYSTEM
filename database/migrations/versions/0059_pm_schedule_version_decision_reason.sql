-- S-02: immutable approval context, distinct from the calculation request reason.
ALTER TABLE pm_schedule_versions ADD COLUMN approval_reason TEXT;
