-- INV-01 foundation: catalog + warehouses (org-scoped, soft-delete ready).
-- Follows PM migration conventions: CHAR(32) UUID hex, TEXT timestamps, Decimal as TEXT.
CREATE TABLE inv_units (
 id CHAR(32) PRIMARY KEY,
 code TEXT NOT NULL,
 name TEXT NOT NULL,
 dimension TEXT NOT NULL DEFAULT '',
 precision INTEGER NOT NULL DEFAULT 3 CHECK(precision>=0 AND precision<=6),
 is_active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 deleted_at TEXT,
 deleted_by CHAR(32) REFERENCES users(id)
);
CREATE UNIQUE INDEX ux_inv_units_code ON inv_units(code);
CREATE TABLE inv_categories (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 parent_id CHAR(32) REFERENCES inv_categories(id),
 code TEXT NOT NULL,
 name_ar TEXT NOT NULL,
 name_en TEXT NOT NULL DEFAULT '',
 is_active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 deleted_at TEXT,
 deleted_by CHAR(32) REFERENCES users(id)
);
CREATE UNIQUE INDEX ux_inv_categories_org_code ON inv_categories(organization_id,code);
CREATE INDEX ix_inv_categories_parent ON inv_categories(parent_id);
CREATE TABLE inv_items (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 category_id CHAR(32) REFERENCES inv_categories(id),
 code TEXT NOT NULL,
 name_ar TEXT NOT NULL,
 name_en TEXT NOT NULL DEFAULT '',
 base_unit_id CHAR(32) REFERENCES inv_units(id),
 tracking_policy TEXT NOT NULL DEFAULT 'none' CHECK(tracking_policy IN ('none','lot','serial','lot_serial')),
 attributes_json TEXT NOT NULL DEFAULT '{}',
 is_active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 deleted_at TEXT,
 deleted_by CHAR(32) REFERENCES users(id)
);
CREATE UNIQUE INDEX ux_inv_items_org_code ON inv_items(organization_id,code);
CREATE INDEX ix_inv_items_category ON inv_items(category_id);
CREATE TABLE inv_item_units (
 id CHAR(32) PRIMARY KEY,
 item_id CHAR(32) NOT NULL REFERENCES inv_items(id) ON DELETE CASCADE,
 unit_id CHAR(32) NOT NULL REFERENCES inv_units(id),
 factor_num TEXT NOT NULL DEFAULT '1',
 factor_den TEXT NOT NULL DEFAULT '1',
 is_purchase INTEGER NOT NULL DEFAULT 0,
 is_issue INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_inv_item_units ON inv_item_units(item_id,unit_id);
CREATE TABLE inv_warehouses (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id),
 operating_department_id CHAR(32) REFERENCES organizations(id),
 code TEXT NOT NULL,
 name TEXT NOT NULL,
 warehouse_type TEXT NOT NULL DEFAULT 'central' CHECK(warehouse_type IN ('central','branch','independent')),
 parent_id CHAR(32) REFERENCES inv_warehouses(id),
 manager_user_id CHAR(32) REFERENCES users(id),
 operation_mode TEXT NOT NULL DEFAULT 'centralized' CHECK(operation_mode IN ('centralized','hybrid','decentralized','independent')),
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended','closed')),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 deleted_at TEXT,
 deleted_by CHAR(32) REFERENCES users(id)
);
CREATE UNIQUE INDEX ux_inv_warehouses_org_code ON inv_warehouses(organization_id,code);
CREATE INDEX ix_inv_warehouses_parent ON inv_warehouses(parent_id);
CREATE TABLE inv_locations (
 id CHAR(32) PRIMARY KEY,
 warehouse_id CHAR(32) NOT NULL REFERENCES inv_warehouses(id) ON DELETE CASCADE,
 parent_id CHAR(32) REFERENCES inv_locations(id),
 code TEXT NOT NULL,
 name TEXT NOT NULL,
 location_type TEXT NOT NULL DEFAULT 'shelf' CHECK(location_type IN ('zone','aisle','shelf','bin','yard','cold')),
 is_active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL,
 deleted_at TEXT
);
CREATE UNIQUE INDEX ux_inv_locations_wh_code ON inv_locations(warehouse_id,code);
