-- Protect historical facts without rewriting existing migration checksums.
CREATE TABLE pm_weekly_plan_closures (
 id CHAR(32) PRIMARY KEY,
 plan_id CHAR(32) NOT NULL REFERENCES pm_weekly_plans(id),
 project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
 snapshot TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO pm_weekly_plan_closures(id,plan_id,project_id,snapshot)
 SELECT lower(hex(randomblob(16))),id,project_id,closure FROM pm_weekly_plans WHERE closure IS NOT NULL;
CREATE TRIGGER pm_quantity_no_update BEFORE UPDATE ON pm_execution_quantity_events BEGIN SELECT RAISE(ABORT,'Quantity history is immutable'); END;
CREATE TRIGGER pm_quantity_no_delete BEFORE DELETE ON pm_execution_quantity_events BEGIN SELECT RAISE(ABORT,'Quantity history is immutable'); END;
CREATE TRIGGER pm_weekly_baseline_no_update BEFORE UPDATE ON pm_weekly_plan_baselines BEGIN SELECT RAISE(ABORT,'Weekly baseline is immutable'); END;
CREATE TRIGGER pm_weekly_baseline_no_delete BEFORE DELETE ON pm_weekly_plan_baselines BEGIN SELECT RAISE(ABORT,'Weekly baseline is immutable'); END;
CREATE TRIGGER pm_weekly_history_no_update BEFORE UPDATE ON pm_weekly_plan_history BEGIN SELECT RAISE(ABORT,'Weekly history is immutable'); END;
CREATE TRIGGER pm_weekly_history_no_delete BEFORE DELETE ON pm_weekly_plan_history BEGIN SELECT RAISE(ABORT,'Weekly history is immutable'); END;
CREATE TRIGGER pm_weekly_closure_no_update BEFORE UPDATE ON pm_weekly_plan_closures BEGIN SELECT RAISE(ABORT,'Weekly closure is immutable'); END;
CREATE TRIGGER pm_weekly_closure_no_delete BEFORE DELETE ON pm_weekly_plan_closures BEGIN SELECT RAISE(ABORT,'Weekly closure is immutable'); END;
CREATE TRIGGER pm_master_baseline_no_update BEFORE UPDATE ON pm_plan_baselines BEGIN SELECT RAISE(ABORT,'Master baseline is immutable'); END;
CREATE TRIGGER pm_master_baseline_no_delete BEFORE DELETE ON pm_plan_baselines BEGIN SELECT RAISE(ABORT,'Master baseline is immutable'); END;
CREATE TRIGGER pm_master_items_no_update BEFORE UPDATE ON pm_plan_baseline_items BEGIN SELECT RAISE(ABORT,'Master baseline items are immutable'); END;
CREATE TRIGGER pm_master_items_no_delete BEFORE DELETE ON pm_plan_baseline_items BEGIN SELECT RAISE(ABORT,'Master baseline items are immutable'); END;
