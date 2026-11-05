-- Administrative lifecycle; economic history stays immutable, CLOSED remains physically posted.

PRAGMA defer_foreign_keys=ON;
DROP VIEW inv_effective_documents;

-- Explicitly preserve the dependent equipment lifecycle, including its immutable history.
CREATE TEMP TABLE inventory_part_lifecycle_preserve (id TEXT,organization_id TEXT,asset_id TEXT,inventory_item_id TEXT,mount_position TEXT,part_serial_number TEXT,lot_number TEXT,lifecycle_status TEXT,installed_at TEXT,installed_meter_generation INTEGER,installed_meter_value TEXT,installed_meter_unit TEXT,removed_at TEXT,removed_meter_generation INTEGER,removed_meter_value TEXT,removed_meter_unit TEXT,actual_life_value TEXT,reason_code TEXT,maintenance_order_id TEXT,installation_inventory_document_id TEXT,removal_inventory_document_id TEXT,idempotency_key TEXT,payload_hash TEXT,removal_idempotency_key TEXT,removal_payload_hash TEXT,created_at TEXT,updated_at TEXT,created_by TEXT,updated_by TEXT,version INTEGER);
INSERT INTO inventory_part_lifecycle_preserve (id,organization_id,asset_id,inventory_item_id,mount_position,part_serial_number,lot_number,lifecycle_status,installed_at,installed_meter_generation,installed_meter_value,installed_meter_unit,removed_at,removed_meter_generation,removed_meter_value,removed_meter_unit,actual_life_value,reason_code,maintenance_order_id,installation_inventory_document_id,removal_inventory_document_id,idempotency_key,payload_hash,removal_idempotency_key,removal_payload_hash,created_at,updated_at,created_by,updated_by,version) SELECT id,organization_id,asset_id,inventory_item_id,mount_position,part_serial_number,lot_number,lifecycle_status,installed_at,installed_meter_generation,installed_meter_value,installed_meter_unit,removed_at,removed_meter_generation,removed_meter_value,removed_meter_unit,actual_life_value,reason_code,maintenance_order_id,installation_inventory_document_id,removal_inventory_document_id,idempotency_key,payload_hash,removal_idempotency_key,removal_payload_hash,created_at,updated_at,created_by,updated_by,version FROM eq_part_lifecycles;
DROP TABLE eq_part_lifecycles;


DROP TRIGGER "inv_posted_document_no_update";

DROP TRIGGER "inv_posted_document_no_delete";

DROP TRIGGER "inv_posted_line_no_update";

DROP TRIGGER "inv_posted_line_no_insert";

DROP TRIGGER "inv_posted_line_no_delete";

DROP INDEX "ux_inv_documents_source_reference";

DROP TRIGGER "trg_inv_document_source_reference_insert";

DROP TRIGGER "trg_inv_document_source_reference_immutable";



CREATE TABLE inv_documents_next (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 document_no TEXT NOT NULL,
 document_type TEXT NOT NULL CHECK(document_type IN ('RECEIPT','ISSUE_DIRECT','TRANSFER_DIRECT','TRANSFER_DISPATCH','TRANSFER_RECEIPT','LOSS_TRANSIT','ISSUE_CUSTODY','CONSUMPTION','RETURN_INTERNAL','STATUS_CHANGE','SCRAP','RETURN_SUPPLIER','ADJUSTMENT','REVERSAL')),
 status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','SUBMITTED','APPROVED','POSTED','CLOSED','REJECTED','CANCELLED')),
 document_date TEXT NOT NULL,
 warehouse_id CHAR(32) NOT NULL REFERENCES inv_warehouses(id),
 legal_entity_id CHAR(32) REFERENCES core_legal_entities(id),
 created_by CHAR(32) NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 submitted_by CHAR(32) REFERENCES users(id),
 submitted_at TEXT,
 approved_by CHAR(32) REFERENCES users(id),
 approved_at TEXT,
 posted_by CHAR(32) REFERENCES users(id),
 posted_at TEXT,
 beneficiary_user_id CHAR(32) REFERENCES users(id),
 custody_due_date TEXT,
 source_stock_status TEXT CHECK(source_stock_status IS NULL OR source_stock_status IN ('AVAILABLE','QUARANTINE','DAMAGED')),
 target_stock_status TEXT CHECK(target_stock_status IS NULL OR target_stock_status IN ('AVAILABLE','QUARANTINE','DAMAGED')),
 counterparty_reference TEXT,
 decision_action TEXT CHECK(decision_action IS NULL OR decision_action IN ('reject','cancel','revise')),
 decision_reason TEXT,
 decision_by CHAR(32) REFERENCES users(id),
 decision_at TEXT,
 closed_by CHAR(32) REFERENCES users(id),
 closed_at TEXT,
 closed_reason TEXT,
 reverses_document_id CHAR(32) REFERENCES inv_documents(id),
 adjustment_kind TEXT CHECK(adjustment_kind IS NULL OR adjustment_kind='VALUE'),
 reason TEXT,
 posting_key TEXT, source_module TEXT, source_type TEXT, source_id CHAR(32),
 destination_warehouse_id CHAR(32) REFERENCES inv_warehouses(id),
 UNIQUE(organization_id,document_no),
 UNIQUE(organization_id,posting_key),
 CHECK(approved_by IS NULL OR approved_by<>created_by),
 CHECK(posted_by IS NULL OR posted_by<>created_by),
 CHECK((status='CLOSED')=(closed_at IS NOT NULL)),
 CHECK(status<>'CLOSED' OR (closed_by IS NOT NULL AND closed_by<>created_by AND closed_reason IS NOT NULL AND length(trim(closed_reason))>=3)),
 CHECK((document_type='REVERSAL')=(reverses_document_id IS NOT NULL)),
 CHECK(reverses_document_id IS NULL OR reverses_document_id<>id),
 CHECK(status NOT IN ('POSTED','CLOSED') OR (legal_entity_id IS NOT NULL AND approved_by IS NOT NULL AND posted_by IS NOT NULL AND posted_at IS NOT NULL AND posting_key IS NOT NULL))
);

INSERT INTO inv_documents_next (id,organization_id,document_no,document_type,status,document_date,warehouse_id,legal_entity_id,created_by,created_at,updated_at,submitted_by,submitted_at,approved_by,approved_at,posted_by,posted_at,beneficiary_user_id,custody_due_date,source_stock_status,target_stock_status,counterparty_reference,adjustment_kind,reverses_document_id,reason,posting_key,source_module,source_type,source_id,destination_warehouse_id) SELECT id,organization_id,document_no,document_type,status,document_date,warehouse_id,legal_entity_id,created_by,created_at,updated_at,submitted_by,submitted_at,approved_by,approved_at,posted_by,posted_at,beneficiary_user_id,custody_due_date,source_stock_status,target_stock_status,counterparty_reference,adjustment_kind,reverses_document_id,reason,posting_key,source_module,source_type,source_id,destination_warehouse_id FROM inv_documents;

DROP TABLE inv_documents;

ALTER TABLE inv_documents_next RENAME TO inv_documents;

CREATE TRIGGER inv_posted_document_no_update BEFORE UPDATE ON inv_documents WHEN OLD.status IN ('POSTED','CLOSED') AND NOT (OLD.status='POSTED' AND NEW.status='CLOSED' AND NEW.closed_by IS NOT NULL AND NEW.closed_at IS NOT NULL AND NEW.closed_reason IS NOT NULL AND length(trim(NEW.closed_reason))>=3 AND NEW.id IS OLD.id AND NEW.organization_id IS OLD.organization_id AND NEW.document_no IS OLD.document_no AND NEW.document_type IS OLD.document_type AND NEW.document_date IS OLD.document_date AND NEW.warehouse_id IS OLD.warehouse_id AND NEW.legal_entity_id IS OLD.legal_entity_id AND NEW.created_by IS OLD.created_by AND NEW.created_at IS OLD.created_at AND NEW.submitted_by IS OLD.submitted_by AND NEW.submitted_at IS OLD.submitted_at AND NEW.approved_by IS OLD.approved_by AND NEW.approved_at IS OLD.approved_at AND NEW.posted_by IS OLD.posted_by AND NEW.posted_at IS OLD.posted_at AND NEW.beneficiary_user_id IS OLD.beneficiary_user_id AND NEW.custody_due_date IS OLD.custody_due_date AND NEW.source_stock_status IS OLD.source_stock_status AND NEW.target_stock_status IS OLD.target_stock_status AND NEW.counterparty_reference IS OLD.counterparty_reference AND NEW.reverses_document_id IS OLD.reverses_document_id AND NEW.adjustment_kind IS OLD.adjustment_kind AND NEW.reason IS OLD.reason AND NEW.posting_key IS OLD.posting_key AND NEW.source_module IS OLD.source_module AND NEW.source_type IS OLD.source_type AND NEW.source_id IS OLD.source_id AND NEW.destination_warehouse_id IS OLD.destination_warehouse_id AND NEW.decision_action IS OLD.decision_action AND NEW.decision_reason IS OLD.decision_reason AND NEW.decision_by IS OLD.decision_by AND NEW.decision_at IS OLD.decision_at)
BEGIN SELECT RAISE(ABORT,'IMMUTABLE_POSTED_DOCUMENT'); END;

CREATE TRIGGER inv_posted_document_no_delete BEFORE DELETE ON inv_documents WHEN OLD.status IN ('POSTED','CLOSED')
BEGIN SELECT RAISE(ABORT,'IMMUTABLE_POSTED_DOCUMENT'); END;

CREATE TRIGGER inv_posted_line_no_update BEFORE UPDATE ON inv_document_lines
WHEN EXISTS(SELECT 1 FROM inv_documents WHERE id=OLD.document_id AND status IN ('POSTED','CLOSED'))
BEGIN SELECT RAISE(ABORT,'IMMUTABLE_POSTED_LINE'); END;

CREATE TRIGGER inv_posted_line_no_insert BEFORE INSERT ON inv_document_lines
WHEN EXISTS(SELECT 1 FROM inv_documents WHERE id=NEW.document_id AND status IN ('POSTED','CLOSED'))
BEGIN SELECT RAISE(ABORT,'IMMUTABLE_POSTED_LINE'); END;

CREATE TRIGGER inv_posted_line_no_delete BEFORE DELETE ON inv_document_lines
WHEN EXISTS(SELECT 1 FROM inv_documents WHERE id=OLD.document_id AND status IN ('POSTED','CLOSED'))
BEGIN SELECT RAISE(ABORT,'IMMUTABLE_POSTED_LINE'); END;

CREATE UNIQUE INDEX ux_inv_documents_source_reference
 ON inv_documents(organization_id,source_module,source_type,source_id)
 WHERE source_module IS NOT NULL;

CREATE TRIGGER trg_inv_document_source_reference_insert
BEFORE INSERT ON inv_documents
WHEN NOT (
 (NEW.source_module IS NULL AND NEW.source_type IS NULL AND NEW.source_id IS NULL)
 OR
 (NEW.source_module='equipment' AND NEW.source_type IN ('fuel_event','fuel_return_event','maintenance_order','part_lifecycle')
  AND NEW.source_id IS NOT NULL)
)
BEGIN
 SELECT RAISE(ABORT,'invalid inventory document source reference');
END;

CREATE TRIGGER trg_inv_document_source_reference_immutable
BEFORE UPDATE OF source_module,source_type,source_id ON inv_documents
WHEN NEW.source_module IS NOT OLD.source_module
 OR NEW.source_type IS NOT OLD.source_type
 OR NEW.source_id IS NOT OLD.source_id
BEGIN
 SELECT RAISE(ABORT,'inventory document source reference is immutable');
END;

CREATE TEMP TABLE inv_value_fk_guard (violations INTEGER CHECK(violations=0));

INSERT INTO inv_value_fk_guard SELECT count(*) FROM pragma_foreign_key_check;

DROP TABLE inv_value_fk_guard;

PRAGMA defer_foreign_keys=OFF;

CREATE UNIQUE INDEX ux_inv_posted_reversal ON inv_documents(reverses_document_id) WHERE status IN ('POSTED','CLOSED') AND reverses_document_id IS NOT NULL;
CREATE VIEW inv_effective_documents AS SELECT d.* FROM inv_documents d WHERE d.document_type<>'REVERSAL' AND NOT EXISTS(SELECT 1 FROM inv_documents r WHERE r.reverses_document_id=d.id AND r.status IN ('POSTED','CLOSED'));

-- Recreate the identical owner schema before restoring every original column.
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


INSERT INTO eq_part_lifecycles (id,organization_id,asset_id,inventory_item_id,mount_position,part_serial_number,lot_number,lifecycle_status,installed_at,installed_meter_generation,installed_meter_value,installed_meter_unit,removed_at,removed_meter_generation,removed_meter_value,removed_meter_unit,actual_life_value,reason_code,maintenance_order_id,installation_inventory_document_id,removal_inventory_document_id,idempotency_key,payload_hash,removal_idempotency_key,removal_payload_hash,created_at,updated_at,created_by,updated_by,version) SELECT id,organization_id,asset_id,inventory_item_id,mount_position,part_serial_number,lot_number,lifecycle_status,installed_at,installed_meter_generation,installed_meter_value,installed_meter_unit,removed_at,removed_meter_generation,removed_meter_value,removed_meter_unit,actual_life_value,reason_code,maintenance_order_id,installation_inventory_document_id,removal_inventory_document_id,idempotency_key,payload_hash,removal_idempotency_key,removal_payload_hash,created_at,updated_at,created_by,updated_by,version FROM inventory_part_lifecycle_preserve;
DROP TABLE inventory_part_lifecycle_preserve;
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
  AND d.document_type='ISSUE_DIRECT' AND d.status IN ('POSTED','CLOSED')
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
   AND d.document_type='RECEIPT' AND d.status IN ('POSTED','CLOSED')
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

CREATE TRIGGER inv_reversal_external_part_guard BEFORE UPDATE OF status ON inv_documents WHEN NEW.status='POSTED' AND NEW.document_type='REVERSAL' AND EXISTS(SELECT 1 FROM eq_part_lifecycles p WHERE p.installation_inventory_document_id=NEW.reverses_document_id OR p.removal_inventory_document_id=NEW.reverses_document_id) BEGIN SELECT RAISE(ABORT,'EXTERNAL_PART_REQUIRES_OWNER_COMPENSATION'); END;
