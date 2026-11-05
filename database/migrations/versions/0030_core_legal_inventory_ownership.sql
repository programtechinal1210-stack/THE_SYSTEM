-- G2-DEV additive reference model. No production organizations are seeded or changed.
CREATE TABLE core_legal_entities (
 id CHAR(32) PRIMARY KEY,
 code TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL,
 valuation_currency_id CHAR(32) REFERENCES core_currencies(id),
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','approved')),
 valuation_locked INTEGER NOT NULL DEFAULT 0 CHECK(valuation_locked IN (0,1)),
 created_by CHAR(32) NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL,
 approved_by CHAR(32) REFERENCES users(id),
 approved_at TEXT,
 CHECK(status='draft' OR (valuation_currency_id IS NOT NULL AND approved_by IS NOT NULL AND approved_at IS NOT NULL))
);
CREATE TABLE core_legal_organization_links (
 legal_entity_id CHAR(32) NOT NULL REFERENCES core_legal_entities(id),
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 approved_by CHAR(32) NOT NULL REFERENCES users(id),
 approved_at TEXT NOT NULL,
 PRIMARY KEY(legal_entity_id,organization_id)
);
CREATE TABLE inv_warehouse_owners (
 warehouse_id CHAR(32) PRIMARY KEY REFERENCES inv_warehouses(id),
 legal_entity_id CHAR(32) NOT NULL,
 organization_id CHAR(32) NOT NULL,
 approved_by CHAR(32) NOT NULL REFERENCES users(id),
 approved_at TEXT NOT NULL,
 FOREIGN KEY(legal_entity_id,organization_id) REFERENCES core_legal_organization_links(legal_entity_id,organization_id)
);
CREATE TRIGGER core_legal_currency_lock BEFORE UPDATE ON core_legal_entities
WHEN OLD.valuation_locked=1 AND (NEW.valuation_locked<>1 OR NEW.valuation_currency_id IS NOT OLD.valuation_currency_id OR NEW.status<>'approved')
BEGIN SELECT RAISE(ABORT,'LEGAL_VALUATION_LOCKED'); END;
CREATE TRIGGER core_legal_locked_delete BEFORE DELETE ON core_legal_entities
WHEN OLD.valuation_locked=1
BEGIN SELECT RAISE(ABORT,'LEGAL_VALUATION_LOCKED'); END;
CREATE TRIGGER inv_owner_org_insert BEFORE INSERT ON inv_warehouse_owners
WHEN NOT EXISTS(SELECT 1 FROM inv_warehouses WHERE id=NEW.warehouse_id AND organization_id=NEW.organization_id)
BEGIN SELECT RAISE(ABORT,'WAREHOUSE_ORGANIZATION_MISMATCH'); END;
CREATE TRIGGER inv_owner_org_update BEFORE UPDATE ON inv_warehouse_owners
WHEN NOT EXISTS(SELECT 1 FROM inv_warehouses WHERE id=NEW.warehouse_id AND organization_id=NEW.organization_id)
BEGIN SELECT RAISE(ABORT,'WAREHOUSE_ORGANIZATION_MISMATCH'); END;
INSERT OR IGNORE INTO permissions(code,name,system,resource,action) VALUES
 ('core.legal_entities.view','عرض الكيانات القانونية','core','legal_entities','view'),
 ('core.legal_entities.manage','إدارة واعتماد الكيانات القانونية','core','legal_entities','manage');
