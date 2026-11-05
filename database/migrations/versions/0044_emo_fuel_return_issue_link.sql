ALTER TABLE eq_fuel_events
 ADD COLUMN related_issue_event_id CHAR(32) REFERENCES eq_fuel_events(id) ON DELETE RESTRICT;

CREATE INDEX ix_eq_fuel_events_related_issue
 ON eq_fuel_events(organization_id,related_issue_event_id,status,event_type);

CREATE TRIGGER trg_eq_fuel_return_issue_link_insert
BEFORE INSERT ON eq_fuel_events
WHEN NEW.related_issue_event_id IS NOT NULL
 AND (
  NEW.event_type<>'returned'
  OR NOT EXISTS (
   SELECT 1 FROM eq_fuel_events source
   WHERE source.id=NEW.related_issue_event_id
    AND source.organization_id=NEW.organization_id
    AND source.asset_id=NEW.asset_id
    AND source.event_type='issued'
    AND source.energy_type=NEW.energy_type
    AND source.unit=NEW.unit
    AND source.status='posted'
  )
 )
BEGIN
 SELECT RAISE(ABORT,'fuel return issue source must be a matching approved issue event');
END;

CREATE TRIGGER trg_eq_fuel_return_issue_link_immutable
BEFORE UPDATE OF related_issue_event_id ON eq_fuel_events
WHEN NEW.related_issue_event_id IS NOT OLD.related_issue_event_id
BEGIN
 SELECT RAISE(ABORT,'fuel return issue source is immutable');
END;
