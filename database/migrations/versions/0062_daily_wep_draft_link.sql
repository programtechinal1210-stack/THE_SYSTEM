-- DW-WO-F2: trace a Daily draft item to its approved weekly commitment.
-- No Actual, Work Order, WEP baseline, or Forecast table is changed.
ALTER TABLE dw_daily_work_items ADD COLUMN wep_plan_item_id CHAR(32) REFERENCES pm_weekly_plan_items(id);
ALTER TABLE dw_daily_work_items ADD COLUMN work_origin TEXT CHECK(work_origin IS NULL OR work_origin IN ('planned_wep','additional_existing_activity','new_project_work','independent_project_work'));
ALTER TABLE dw_daily_work_items ADD COLUMN allocation_key TEXT NOT NULL DEFAULT '';
ALTER TABLE dw_daily_work_items ADD COLUMN allocation_reason TEXT NOT NULL DEFAULT '';

DROP INDEX ux_dw_items_source_day;
CREATE UNIQUE INDEX ux_dw_items_wep_allocation_day
  ON dw_daily_work_items(project_id, activity_id, work_date, allocation_key)
  WHERE deleted_at IS NULL AND emergency_flag=0 AND activity_id IS NOT NULL;
CREATE UNIQUE INDEX ux_dw_items_wep_source_allocation
  ON dw_daily_work_items(plan_id, wep_plan_item_id, allocation_key)
  WHERE deleted_at IS NULL AND wep_plan_item_id IS NOT NULL;
CREATE INDEX ix_dw_items_wep_day
  ON dw_daily_work_items(project_id, wep_plan_item_id, work_date, deleted_at);
