CREATE TABLE eq_part_lifecycles (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 asset_id CHAR(32) NOT NULL,
 inventory_item_id CHAR(32) NOT NULL REFERENCES inv_items(id) ON DELETE RESTRICT,
 mount_position TEXT NOT NULL CHECK(length(trim(mount_position)) BETWEEN 1 AND 120),
 part_serial_number TEXT,
 lot_number TEXT,
 lifecycle_status TEXT NOT NULL CHECK(lifecycle_status IN ('installed','removed')),
 installed_at TEXT NOT NULL,
 installed_meter_generation INTEGER,
 installed_meter_value TEXT,
 installed_meter_unit TEXT,
 removed_at TEXT,
 removed_meter_generation INTEGER,
 removed_meter_value TEXT,
 removed_meter_unit TEXT,
 actual_life_value TEXT,
 reason_code TEXT,
 maintenance_order_id CHAR(32),
 installation_inventory_document_id CHAR(32) NOT NULL REFERENCES inv_documents(id) ON DELETE RESTRICT,
 removal_inventory_document_id CHAR(32) REFERENCES inv_documents(id) ON DELETE RESTRICT,
 idempotency_key TEXT NOT NULL,
 payload_hash TEXT NOT NULL,
 removal_idempotency_key TEXT,
 removal_payload_hash TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 updated_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 version INTEGER NOT NULL DEFAULT 1 CHECK(version >= 1),
 UNIQUE(organization_id,id),
 UNIQUE(organization_id,idempotency_key),
 FOREIGN KEY(organization_id,asset_id) REFERENCES eq_assets(organization_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(organization_id,maintenance_order_id) REFERENCES eq_maintenance_orders(organization_id,id) ON DELETE RESTRICT,
 CHECK(
  (lifecycle_status='installed' AND removed_at IS NULL AND removed_meter_value IS NULL
   AND actual_life_value IS NULL AND removal_inventory_document_id IS NULL
   AND removal_idempotency_key IS NULL AND removal_payload_hash IS NULL)
  OR
  (lifecycle_status='removed' AND removed_at IS NOT NULL
   AND removal_inventory_document_id IS NOT NULL
   AND removal_idempotency_key IS NOT NULL AND removal_payload_hash IS NOT NULL)
 ),
 CHECK((installed_meter_value IS NULL AND installed_meter_generation IS NULL AND installed_meter_unit IS NULL)
    OR (installed_meter_value IS NOT NULL AND installed_meter_generation IS NOT NULL AND installed_meter_unit IS NOT NULL)),
 CHECK((removed_meter_value IS NULL AND removed_meter_generation IS NULL AND removed_meter_unit IS NULL)
    OR (removed_meter_value IS NOT NULL AND removed_meter_generation IS NOT NULL AND removed_meter_unit IS NOT NULL))
);

CREATE UNIQUE INDEX ux_eq_part_lifecycle_active_mount
 ON eq_part_lifecycles(organization_id,asset_id,mount_position)
 WHERE lifecycle_status='installed';
CREATE UNIQUE INDEX ux_eq_part_lifecycle_active_serial
 ON eq_part_lifecycles(organization_id,part_serial_number)
 WHERE lifecycle_status='installed' AND part_serial_number IS NOT NULL AND part_serial_number<>'';
CREATE UNIQUE INDEX ux_eq_part_lifecycle_removal_key
 ON eq_part_lifecycles(organization_id,removal_idempotency_key)
 WHERE removal_idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX ux_eq_part_lifecycle_install_document
 ON eq_part_lifecycles(installation_inventory_document_id);
CREATE UNIQUE INDEX ux_eq_part_lifecycle_removal_document
 ON eq_part_lifecycles(removal_inventory_document_id)
 WHERE removal_inventory_document_id IS NOT NULL;
CREATE INDEX ix_eq_part_lifecycle_asset
 ON eq_part_lifecycles(organization_id,asset_id,lifecycle_status,installed_at);

CREATE TRIGGER trg_eq_part_install_inventory_insert
BEFORE INSERT ON eq_part_lifecycles
WHEN NOT EXISTS (
 SELECT 1 FROM inv_documents d
 JOIN inv_document_lines l ON l.document_id=d.id
 WHERE d.id=NEW.installation_inventory_document_id
  AND d.organization_id=NEW.organization_id
  AND d.document_type='ISSUE_DIRECT' AND d.status='POSTED'
  AND l.item_id=NEW.inventory_item_id AND CAST(l.base_quantity AS NUMERIC)=1
  AND (SELECT count(*) FROM inv_document_lines WHERE document_id=d.id)=1
)
BEGIN
 SELECT RAISE(ABORT,'part installation requires a posted matching Inventory issue');
END;

CREATE TRIGGER trg_eq_part_lifecycle_update
BEFORE UPDATE ON eq_part_lifecycles
WHEN OLD.lifecycle_status<>'installed'
 OR NEW.id IS NOT OLD.id
 OR NEW.organization_id IS NOT OLD.organization_id
 OR NEW.asset_id IS NOT OLD.asset_id
 OR NEW.inventory_item_id IS NOT OLD.inventory_item_id
 OR NEW.mount_position IS NOT OLD.mount_position
 OR NEW.part_serial_number IS NOT OLD.part_serial_number
 OR NEW.lot_number IS NOT OLD.lot_number
 OR NEW.installed_at IS NOT OLD.installed_at
 OR NEW.installed_meter_generation IS NOT OLD.installed_meter_generation
 OR NEW.installed_meter_value IS NOT OLD.installed_meter_value
 OR NEW.installed_meter_unit IS NOT OLD.installed_meter_unit
 OR NEW.maintenance_order_id IS NOT OLD.maintenance_order_id
 OR NEW.installation_inventory_document_id IS NOT OLD.installation_inventory_document_id
 OR NEW.idempotency_key IS NOT OLD.idempotency_key
 OR NEW.payload_hash IS NOT OLD.payload_hash
 OR NEW.created_at IS NOT OLD.created_at
 OR NEW.created_by IS NOT OLD.created_by
 OR NEW.lifecycle_status<>'removed'
 OR NOT EXISTS (
  SELECT 1 FROM inv_documents d
  JOIN inv_document_lines l ON l.document_id=d.id
  WHERE d.id=NEW.removal_inventory_document_id
   AND d.organization_id=NEW.organization_id
   AND d.document_type='RECEIPT' AND d.status='POSTED'
   AND l.item_id=NEW.inventory_item_id AND CAST(l.base_quantity AS NUMERIC)=1
   AND (SELECT count(*) FROM inv_document_lines WHERE document_id=d.id)=1
 )
BEGIN
 SELECT RAISE(ABORT,'part lifecycle history is immutable or Inventory return is invalid');
END;

CREATE TRIGGER trg_eq_part_lifecycle_no_delete
BEFORE DELETE ON eq_part_lifecycles
BEGIN
 SELECT RAISE(ABORT,'part lifecycle history is immutable');
END;
