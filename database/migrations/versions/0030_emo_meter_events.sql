-- EMO-07: append-only meter readings, replacements, and documented corrections.
CREATE TABLE eq_meter_events (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 asset_id CHAR(32) NOT NULL,
 event_code TEXT NOT NULL,
 event_type TEXT NOT NULL CHECK(event_type IN ('reading','replacement','correction')),
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved')),
 event_at TEXT NOT NULL,
 meter_type_snapshot TEXT NOT NULL CHECK(meter_type_snapshot IN ('hours','distance','cycles','energy')),
 meter_unit_snapshot TEXT NOT NULL,
 generation_before INTEGER NOT NULL CHECK(generation_before >= 1),
 generation_after INTEGER NOT NULL CHECK(generation_after >= generation_before),
 base_meter_latest TEXT,
 base_meter_normalized_latest TEXT,
 reading_value TEXT,
 old_final_reading TEXT,
 new_initial_reading TEXT,
 correction_of_event_id CHAR(32),
 correction_delta TEXT,
 reason_code TEXT,
 evidence_ref TEXT,
 idempotency_key TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 created_at TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 approved_at TEXT,
 approved_by CHAR(32) REFERENCES users(id) ON DELETE RESTRICT,
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,event_code),
 UNIQUE(organization_id,idempotency_key),
 FOREIGN KEY(organization_id,asset_id) REFERENCES eq_assets(organization_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(organization_id,correction_of_event_id)
  REFERENCES eq_meter_events(organization_id,id) ON DELETE RESTRICT,
 CHECK(
  (status='pending' AND approved_at IS NULL AND approved_by IS NULL)
  OR (status='approved' AND approved_at IS NOT NULL AND approved_by IS NOT NULL)
 ),
 CHECK(
  (event_type='reading' AND generation_after=generation_before AND reading_value IS NOT NULL
   AND old_final_reading IS NULL AND new_initial_reading IS NULL
   AND correction_of_event_id IS NULL AND correction_delta IS NULL
   AND reason_code IS NULL AND evidence_ref IS NULL)
  OR
  (event_type='replacement' AND generation_after=generation_before+1 AND reading_value IS NULL
   AND old_final_reading IS NOT NULL AND new_initial_reading IS NOT NULL
   AND correction_of_event_id IS NULL AND correction_delta IS NULL
   AND reason_code IS NOT NULL AND evidence_ref IS NOT NULL)
  OR
  (event_type='correction' AND generation_after=generation_before AND reading_value IS NOT NULL
   AND old_final_reading IS NULL AND new_initial_reading IS NULL
   AND correction_of_event_id IS NOT NULL AND correction_delta IS NOT NULL
   AND reason_code IS NOT NULL AND evidence_ref IS NOT NULL)
 )
);
CREATE INDEX ix_eq_meter_events_asset_timeline
 ON eq_meter_events(organization_id,asset_id,event_at,id);
CREATE INDEX ix_eq_meter_events_pending
 ON eq_meter_events(organization_id,asset_id,status,event_at);
CREATE UNIQUE INDEX ux_eq_meter_event_generation
 ON eq_meter_events(organization_id,asset_id,generation_after)
 WHERE event_type='replacement' AND status='approved';

CREATE TRIGGER trg_eq_meter_event_insert_pending
BEFORE INSERT ON eq_meter_events
WHEN NEW.status<>'pending' OR NEW.approved_at IS NOT NULL OR NEW.approved_by IS NOT NULL
BEGIN
 SELECT RAISE(ABORT,'meter events must be created pending approval');
END;

CREATE TRIGGER trg_eq_meter_event_no_delete
BEFORE DELETE ON eq_meter_events
BEGIN
 SELECT RAISE(ABORT,'meter events are append-only');
END;

CREATE TRIGGER trg_eq_meter_event_no_content_update
BEFORE UPDATE OF id,organization_id,asset_id,event_code,event_type,event_at,
 meter_type_snapshot,meter_unit_snapshot,generation_before,generation_after,
 base_meter_latest,base_meter_normalized_latest,reading_value,old_final_reading,
 new_initial_reading,correction_of_event_id,correction_delta,reason_code,evidence_ref,
 idempotency_key,payload_hash,created_at,created_by
ON eq_meter_events
BEGIN
 SELECT RAISE(ABORT,'meter event content is immutable');
END;

CREATE TRIGGER trg_eq_meter_event_approve_once
BEFORE UPDATE OF status,approved_at,approved_by ON eq_meter_events
WHEN OLD.status<>'pending' OR NEW.status<>'approved'
 OR OLD.approved_at IS NOT NULL OR OLD.approved_by IS NOT NULL
 OR NEW.approved_at IS NULL OR NEW.approved_by IS NULL
BEGIN
 SELECT RAISE(ABORT,'meter event approval is a one-way transition');
END;
