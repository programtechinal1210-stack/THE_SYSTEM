-- Additive, isolated development only. No production legal entities or controls seeded.
CREATE TABLE inv_material_requests (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 request_no TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','SUBMITTED','APPROVED','PARTIAL','FULFILLED','CANCELLED')),
 created_by CHAR(32) NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL,
 UNIQUE(organization_id,request_no)
);
CREATE TABLE inv_request_lines (
 id CHAR(32) PRIMARY KEY,
 request_id CHAR(32) NOT NULL REFERENCES inv_material_requests(id),
 item_id CHAR(32) NOT NULL REFERENCES inv_items(id),
 quantity TEXT NOT NULL,
 approved_quantity TEXT NOT NULL DEFAULT '0',
 fulfilled_quantity TEXT NOT NULL DEFAULT '0'
);
CREATE TABLE inv_financial_controls (
 legal_entity_id CHAR(32) PRIMARY KEY REFERENCES core_legal_entities(id),
 posting_enabled INTEGER NOT NULL DEFAULT 0 CHECK(posting_enabled IN (0,1)),
 closed_through TEXT,
 updated_by CHAR(32) NOT NULL REFERENCES users(id),
 updated_at TEXT NOT NULL
);
CREATE TABLE inv_warehouse_access (
 warehouse_id CHAR(32) NOT NULL REFERENCES inv_warehouses(id),
 user_id CHAR(32) NOT NULL REFERENCES users(id),
 permission TEXT NOT NULL REFERENCES permissions(code),
 granted_by CHAR(32) NOT NULL REFERENCES users(id),
 granted_at TEXT NOT NULL,
 PRIMARY KEY(warehouse_id,user_id,permission)
);
CREATE TABLE inv_documents (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 document_no TEXT NOT NULL,
 document_type TEXT NOT NULL CHECK(document_type IN ('RECEIPT','ISSUE_DIRECT')),
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
 posting_key TEXT,
 UNIQUE(organization_id,document_no),
 UNIQUE(organization_id,posting_key),
 CHECK(approved_by IS NULL OR approved_by<>created_by),
 CHECK(posted_by IS NULL OR posted_by<>created_by),
 CHECK(status<>'POSTED' OR (legal_entity_id IS NOT NULL AND approved_by IS NOT NULL AND posted_by IS NOT NULL AND posted_at IS NOT NULL AND posting_key IS NOT NULL))
);
CREATE TABLE inv_document_lines (
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
 UNIQUE(document_id,line_no)
);
CREATE TABLE inv_stock_ledger (
 ledger_seq INTEGER PRIMARY KEY AUTOINCREMENT,
 id CHAR(32) NOT NULL UNIQUE,
 document_line_id CHAR(32) NOT NULL REFERENCES inv_document_lines(id),
 posting_group_id CHAR(32) NOT NULL REFERENCES inv_documents(id),
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 legal_entity_id CHAR(32) NOT NULL REFERENCES core_legal_entities(id),
 warehouse_id CHAR(32) NOT NULL REFERENCES inv_warehouses(id),
 location_id CHAR(32) REFERENCES inv_locations(id),
 item_id CHAR(32) NOT NULL REFERENCES inv_items(id),
 stock_status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK(stock_status='AVAILABLE'),
 quantity_delta TEXT NOT NULL,
 value_delta_valuation TEXT NOT NULL,
 valuation_currency_id CHAR(32) NOT NULL REFERENCES core_currencies(id),
 prev_qty TEXT NOT NULL,
 new_qty TEXT NOT NULL,
 prev_avg_cost TEXT NOT NULL,
 new_avg_cost TEXT NOT NULL,
 posted_at TEXT NOT NULL,
 UNIQUE(document_line_id)
);
CREATE INDEX ix_inv_ledger_scope ON inv_stock_ledger(organization_id,warehouse_id,item_id,ledger_seq);
CREATE TABLE inv_stock_balances (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 legal_entity_id CHAR(32) NOT NULL REFERENCES core_legal_entities(id),
 warehouse_id CHAR(32) NOT NULL REFERENCES inv_warehouses(id),
 location_id CHAR(32) REFERENCES inv_locations(id),
 item_id CHAR(32) NOT NULL REFERENCES inv_items(id),
 stock_status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK(stock_status='AVAILABLE'),
 quantity_on_hand TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 0 CHECK(version>=0)
);
CREATE UNIQUE INDEX ux_inv_balance_key ON inv_stock_balances(organization_id,legal_entity_id,warehouse_id,COALESCE(location_id,''),item_id,stock_status);
CREATE TABLE inv_valuation_state (
 id CHAR(32) PRIMARY KEY,
 legal_entity_id CHAR(32) NOT NULL REFERENCES core_legal_entities(id),
 item_id CHAR(32) NOT NULL REFERENCES inv_items(id),
 valuation_currency_id CHAR(32) NOT NULL REFERENCES core_currencies(id),
 quantity_total TEXT NOT NULL,
 inventory_value TEXT NOT NULL,
 avg_cost TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 0,
 UNIQUE(legal_entity_id,item_id,valuation_currency_id)
);
CREATE TABLE inv_outbox_events (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 document_id CHAR(32) NOT NULL UNIQUE REFERENCES inv_documents(id),
 event_name TEXT NOT NULL,
 payload TEXT NOT NULL,
 created_at TEXT NOT NULL,
 delivered_at TEXT,
 attempts INTEGER NOT NULL DEFAULT 0
);
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
