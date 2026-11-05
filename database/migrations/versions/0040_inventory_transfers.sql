-- Inventory transfer legs: isolated deployment only; explicit historical column mapping.

PRAGMA defer_foreign_keys=ON;

DROP INDEX "ix_inv_ledger_scope";

DROP INDEX "ux_inv_balance_key";

DROP TRIGGER "inv_ledger_no_update";

DROP TRIGGER "inv_ledger_no_delete";

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
 document_type TEXT NOT NULL CHECK(document_type IN ('RECEIPT','ISSUE_DIRECT','TRANSFER_DIRECT','TRANSFER_DISPATCH','TRANSFER_RECEIPT')),
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
 posting_key TEXT, source_module TEXT, source_type TEXT, source_id CHAR(32),
 destination_warehouse_id CHAR(32) REFERENCES inv_warehouses(id),
 UNIQUE(organization_id,document_no),
 UNIQUE(organization_id,posting_key),
 CHECK(approved_by IS NULL OR approved_by<>created_by),
 CHECK(posted_by IS NULL OR posted_by<>created_by),
 CHECK(status<>'POSTED' OR (legal_entity_id IS NOT NULL AND approved_by IS NOT NULL AND posted_by IS NOT NULL AND posted_at IS NOT NULL AND posting_key IS NOT NULL))
);

INSERT INTO inv_documents_next (id,organization_id,document_no,document_type,status,document_date,warehouse_id,legal_entity_id,created_by,created_at,updated_at,submitted_by,submitted_at,approved_by,approved_at,posted_by,posted_at,posting_key,source_module,source_type,source_id) SELECT id,organization_id,document_no,document_type,status,document_date,warehouse_id,legal_entity_id,created_by,created_at,updated_at,submitted_by,submitted_at,approved_by,approved_at,posted_by,posted_at,posting_key,source_module,source_type,source_id FROM inv_documents;

DROP TABLE inv_documents;

ALTER TABLE inv_documents_next RENAME TO inv_documents;

CREATE TABLE inv_document_lines_next (
 id CHAR(32) PRIMARY KEY,
 document_id CHAR(32) NOT NULL REFERENCES inv_documents(id),
 line_no INTEGER NOT NULL CHECK(line_no>0),
 item_id CHAR(32) NOT NULL REFERENCES inv_items(id),
 unit_id CHAR(32) NOT NULL REFERENCES inv_units(id),
 location_id CHAR(32) REFERENCES inv_locations(id),
 quantity TEXT NOT NULL,
 base_quantity TEXT NOT NULL,
 request_line_id CHAR(32) REFERENCES inv_request_lines(id),
 transaction_currency_id CHAR(32) REFERENCES core_currencies(id),
 original_unit_price TEXT,
 original_amount TEXT,
 valuation_currency_id CHAR(32) REFERENCES core_currencies(id),
 fx_rate TEXT,
 fx_effective_at TEXT,
 fx_source_ref TEXT,
 unit_cost_valuation TEXT,
 amount_valuation TEXT,
 destination_location_id CHAR(32) REFERENCES inv_locations(id),
 dispatch_line_id CHAR(32) REFERENCES inv_document_lines(id),
 UNIQUE(document_id,line_no)
);

INSERT INTO inv_document_lines_next (id,document_id,line_no,item_id,unit_id,location_id,quantity,base_quantity,request_line_id,transaction_currency_id,original_unit_price,original_amount,valuation_currency_id,fx_rate,fx_effective_at,fx_source_ref,unit_cost_valuation,amount_valuation) SELECT id,document_id,line_no,item_id,unit_id,location_id,quantity,base_quantity,request_line_id,transaction_currency_id,original_unit_price,original_amount,valuation_currency_id,fx_rate,fx_effective_at,fx_source_ref,unit_cost_valuation,amount_valuation FROM inv_document_lines;

DROP TABLE inv_document_lines;

ALTER TABLE inv_document_lines_next RENAME TO inv_document_lines;

CREATE TABLE inv_stock_ledger_next (
 ledger_seq INTEGER PRIMARY KEY AUTOINCREMENT,
 id CHAR(32) NOT NULL UNIQUE,
 document_line_id CHAR(32) NOT NULL REFERENCES inv_document_lines(id),
 posting_group_id CHAR(32) NOT NULL REFERENCES inv_documents(id),
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 legal_entity_id CHAR(32) NOT NULL REFERENCES core_legal_entities(id),
 warehouse_id CHAR(32) NOT NULL REFERENCES inv_warehouses(id),
 location_id CHAR(32) REFERENCES inv_locations(id),
 item_id CHAR(32) NOT NULL REFERENCES inv_items(id),
 stock_status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK(stock_status IN ('AVAILABLE','IN_TRANSIT')),
 quantity_delta TEXT NOT NULL,
 value_delta_valuation TEXT NOT NULL,
 valuation_currency_id CHAR(32) NOT NULL REFERENCES core_currencies(id),
 prev_qty TEXT NOT NULL,
 new_qty TEXT NOT NULL,
 prev_avg_cost TEXT NOT NULL,
 new_avg_cost TEXT NOT NULL,
 posted_at TEXT NOT NULL,
 posting_leg_key TEXT NOT NULL DEFAULT 'PRIMARY', UNIQUE(document_line_id,posting_leg_key)
);

INSERT INTO inv_stock_ledger_next (ledger_seq,id,document_line_id,posting_group_id,organization_id,legal_entity_id,warehouse_id,location_id,item_id,stock_status,quantity_delta,value_delta_valuation,valuation_currency_id,prev_qty,new_qty,prev_avg_cost,new_avg_cost,posted_at) SELECT ledger_seq,id,document_line_id,posting_group_id,organization_id,legal_entity_id,warehouse_id,location_id,item_id,stock_status,quantity_delta,value_delta_valuation,valuation_currency_id,prev_qty,new_qty,prev_avg_cost,new_avg_cost,posted_at FROM inv_stock_ledger;

DROP TABLE inv_stock_ledger;

ALTER TABLE inv_stock_ledger_next RENAME TO inv_stock_ledger;

CREATE TABLE inv_stock_balances_next (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 legal_entity_id CHAR(32) NOT NULL REFERENCES core_legal_entities(id),
 warehouse_id CHAR(32) NOT NULL REFERENCES inv_warehouses(id),
 location_id CHAR(32) REFERENCES inv_locations(id),
 item_id CHAR(32) NOT NULL REFERENCES inv_items(id),
 stock_status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK(stock_status IN ('AVAILABLE','IN_TRANSIT')),
 quantity_on_hand TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 0 CHECK(version>=0)
);

INSERT INTO inv_stock_balances_next (id,organization_id,legal_entity_id,warehouse_id,location_id,item_id,stock_status,quantity_on_hand,version) SELECT id,organization_id,legal_entity_id,warehouse_id,location_id,item_id,stock_status,quantity_on_hand,version FROM inv_stock_balances;

DROP TABLE inv_stock_balances;

ALTER TABLE inv_stock_balances_next RENAME TO inv_stock_balances;

CREATE INDEX ix_inv_ledger_scope ON inv_stock_ledger(organization_id,warehouse_id,item_id,ledger_seq);

CREATE UNIQUE INDEX ux_inv_balance_key ON inv_stock_balances(organization_id,legal_entity_id,warehouse_id,COALESCE(location_id,''),item_id,stock_status);

CREATE TRIGGER inv_ledger_no_update BEFORE UPDATE ON inv_stock_ledger
BEGIN SELECT RAISE(ABORT,'IMMUTABLE_INVENTORY_LEDGER'); END;

CREATE TRIGGER inv_ledger_no_delete BEFORE DELETE ON inv_stock_ledger
BEGIN SELECT RAISE(ABORT,'IMMUTABLE_INVENTORY_LEDGER'); END;

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

CREATE INDEX ix_inv_dispatch_reference ON inv_document_lines(dispatch_line_id);

CREATE TEMP TABLE inv_transfer_fk_guard (violations INTEGER CHECK(violations=0));

INSERT INTO inv_transfer_fk_guard SELECT count(*) FROM pragma_foreign_key_check;

DROP TABLE inv_transfer_fk_guard;

PRAGMA defer_foreign_keys=OFF;
