-- DW-WO-F3-A: flexible Daily Work draft provenance and retry safety.
-- Planning metadata only. No Actual, WO, WEP, Baseline, or Forecast data is changed.
ALTER TABLE dw_daily_work_items ADD COLUMN reason_code TEXT NOT NULL DEFAULT '';
ALTER TABLE dw_daily_work_items ADD COLUMN reason_note TEXT NOT NULL DEFAULT '';
ALTER TABLE dw_daily_work_items ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'
  CHECK(priority IN ('low','normal','high','urgent'));
ALTER TABLE dw_daily_work_items ADD COLUMN idempotency_key TEXT;

CREATE UNIQUE INDEX ux_dw_items_project_idempotency
  ON dw_daily_work_items(project_id, idempotency_key)
  WHERE idempotency_key IS NOT NULL AND idempotency_key<>'';

ALTER TABLE dw_work_item_estimates ADD COLUMN fx_source TEXT NOT NULL DEFAULT '';
