-- Isolated-only supplier return; immutable history and references preserved.

PRAGMA defer_foreign_keys=ON;

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
 document_type TEXT NOT NULL CHECK(document_type IN ('RECEIPT','ISSUE_DIRECT','TRANSFER_DIRECT','TRANSFER_DISPATCH','TRANSFER_RECEIPT','LOSS_TRANSIT','ISSUE_CUSTODY','CONSUMPTION','RETURN_INTERNAL','STATUS_CHANGE','SCRAP','RETURN_SUPPLIER')),
 status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','SUBMITTED','APPROVED','POSTED','CANCELLED')),
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
 reason TEXT,
 posting_key TEXT, source_module TEXT, source_type TEXT, source_id CHAR(32),
 destination_warehouse_id CHAR(32) REFERENCES inv_warehouses(id),
 UNIQUE(organization_id,document_no),
 UNIQUE(organization_id,posting_key),
 CHECK(approved_by IS NULL OR approved_by<>created_by),
 CHECK(posted_by IS NULL OR posted_by<>created_by),
 CHECK(status<>'POSTED' OR (legal_entity_id IS NOT NULL AND approved_by IS NOT NULL AND posted_by IS NOT NULL AND posted_at IS NOT NULL AND posting_key IS NOT NULL))
);

INSERT INTO inv_documents_next (id,organization_id,document_no,document_type,status,document_date,warehouse_id,legal_entity_id,created_by,created_at,updated_at,submitted_by,submitted_at,approved_by,approved_at,posted_by,posted_at,beneficiary_user_id,custody_due_date,source_stock_status,target_stock_status,reason,posting_key,source_module,source_type,source_id,destination_warehouse_id) SELECT id,organization_id,document_no,document_type,status,document_date,warehouse_id,legal_entity_id,created_by,created_at,updated_at,submitted_by,submitted_at,approved_by,approved_at,posted_by,posted_at,beneficiary_user_id,custody_due_date,source_stock_status,target_stock_status,reason,posting_key,source_module,source_type,source_id,destination_warehouse_id FROM inv_documents;

DROP TABLE inv_documents;

ALTER TABLE inv_documents_next RENAME TO inv_documents;

CREATE TRIGGER inv_posted_document_no_update BEFORE UPDATE ON inv_documents WHEN OLD.status='POSTED'
BEGIN SELECT RAISE(ABORT,'IMMUTABLE_POSTED_DOCUMENT'); END;

CREATE TRIGGER inv_posted_document_no_delete BEFORE DELETE ON inv_documents WHEN OLD.status='POSTED'
BEGIN SELECT RAISE(ABORT,'IMMUTABLE_POSTED_DOCUMENT'); END;

CREATE TRIGGER inv_posted_line_no_update BEFORE UPDATE ON inv_document_lines
WHEN EXISTS(SELECT 1 FROM inv_documents WHERE id=OLD.document_id AND status='POSTED')
BEGIN SELECT RAISE(ABORT,'IMMUTABLE_POSTED_LINE'); END;

CREATE TRIGGER inv_posted_line_no_insert BEFORE INSERT ON inv_document_lines
WHEN EXISTS(SELECT 1 FROM inv_documents WHERE id=NEW.document_id AND status='POSTED')
BEGIN SELECT RAISE(ABORT,'IMMUTABLE_POSTED_LINE'); END;

CREATE TRIGGER inv_posted_line_no_delete BEFORE DELETE ON inv_document_lines
WHEN EXISTS(SELECT 1 FROM inv_documents WHERE id=OLD.document_id AND status='POSTED')
BEGIN SELECT RAISE(ABORT,'IMMUTABLE_POSTED_LINE'); END;

CREATE UNIQUE INDEX ux_inv_documents_source_reference
 ON inv_documents(organization_id,source_module,source_type,source_id)
 WHERE source_module IS NOT NULL;

CREATE TRIGGER trg_inv_document_source_reference_insert
BEFORE INSERT ON inv_documents
WHEN NOT (
 (NEW.source_module IS NULL AND NEW.source_type IS NULL AND NEW.source_id IS NULL)
 OR
 (NEW.source_module='equipment' AND NEW.source_type IN ('fuel_event','maintenance_order','part_lifecycle')
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

CREATE TEMP TABLE inv_supplier_fk_guard (violations INTEGER CHECK(violations=0));

INSERT INTO inv_supplier_fk_guard SELECT count(*) FROM pragma_foreign_key_check;

DROP TABLE inv_supplier_fk_guard;

PRAGMA defer_foreign_keys=OFF;
