-- EMO-16: keep raw and normalized operation readings and link the closing reading
-- to the append-only meter-event approval workflow.
ALTER TABLE eq_operation_logs ADD COLUMN meter_normalized_start TEXT;
ALTER TABLE eq_operation_logs ADD COLUMN meter_normalized_end TEXT;
ALTER TABLE eq_meter_events ADD COLUMN operation_log_id CHAR(32)
 REFERENCES eq_operation_logs(id) ON DELETE RESTRICT;

CREATE UNIQUE INDEX ux_eq_meter_event_operation
 ON eq_meter_events(operation_log_id) WHERE operation_log_id IS NOT NULL;

CREATE TRIGGER trg_eq_meter_operation_event_scope
BEFORE INSERT ON eq_meter_events
WHEN NEW.operation_log_id IS NOT NULL AND NOT EXISTS (
 SELECT 1 FROM eq_operation_logs o
 WHERE o.id=NEW.operation_log_id
  AND o.organization_id=NEW.organization_id
  AND o.asset_id=NEW.asset_id
  AND o.status='submitted'
  AND o.ended_at=NEW.event_at
  AND o.meter_type_snapshot=NEW.meter_type_snapshot
  AND o.meter_unit_snapshot=NEW.meter_unit_snapshot
  AND o.meter_generation_snapshot=NEW.generation_before
  AND o.meter_end=NEW.reading_value
  AND o.meter_normalized_end IS NOT NULL
  AND NEW.event_type='reading'
  AND NEW.status='pending'
)
BEGIN
 SELECT RAISE(ABORT,'operation meter event must match a submitted operation');
END;

CREATE TRIGGER trg_eq_meter_operation_link_immutable
BEFORE UPDATE OF operation_log_id ON eq_meter_events
WHEN NEW.operation_log_id IS NOT OLD.operation_log_id
BEGIN
 SELECT RAISE(ABORT,'operation meter event link is immutable');
END;

CREATE TRIGGER trg_eq_operation_meter_normalized_start_immutable
BEFORE UPDATE OF meter_normalized_start ON eq_operation_logs
WHEN NEW.meter_normalized_start IS NOT OLD.meter_normalized_start
BEGIN
 SELECT RAISE(ABORT,'operation normalized meter start is immutable');
END;

CREATE TRIGGER trg_eq_operation_meter_normalized_end_transition
BEFORE UPDATE OF meter_normalized_end ON eq_operation_logs
WHEN NOT (
 OLD.status='running'
 AND NEW.status='submitted'
 AND OLD.meter_normalized_end IS NULL
 AND (
  (NEW.meter_end IS NULL AND NEW.meter_normalized_end IS NULL)
  OR (NEW.meter_end IS NOT NULL AND NEW.meter_normalized_end IS NOT NULL)
 )
)
BEGIN
 SELECT RAISE(ABORT,'operation normalized meter end transition is invalid');
END;
