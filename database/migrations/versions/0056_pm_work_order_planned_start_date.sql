-- PM execution: planned scheduling date is distinct from the actual start_date.
ALTER TABLE pm_work_orders ADD COLUMN planned_start_date TEXT;
