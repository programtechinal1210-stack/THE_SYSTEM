-- EMO selects real Inventory records; Inventory remains the sole stock owner.
CREATE TABLE eq_inventory_fuel_mappings (
 id CHAR(32) PRIMARY KEY,
 organization_id CHAR(32) NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
 category_id CHAR(32) NOT NULL,
 energy_type TEXT NOT NULL CHECK(energy_type IN ('diesel','gasoline','electricity','other')),
 item_id CHAR(32) NOT NULL REFERENCES inv_items(id) ON DELETE RESTRICT,
 warehouse_id CHAR(32) NOT NULL REFERENCES inv_warehouses(id) ON DELETE RESTRICT,
 is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
 created_at TEXT NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 updated_at TEXT NOT NULL,
 updated_by CHAR(32) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
 UNIQUE(organization_id,category_id,energy_type),
 FOREIGN KEY(organization_id,category_id) REFERENCES eq_categories(organization_id,id) ON DELETE RESTRICT
);

CREATE TRIGGER trg_eq_inventory_fuel_mapping_scope_insert
BEFORE INSERT ON eq_inventory_fuel_mappings
WHEN NOT EXISTS (
 SELECT 1 FROM inv_items i JOIN inv_warehouses w
  ON w.organization_id=i.organization_id
 WHERE i.id=NEW.item_id AND w.id=NEW.warehouse_id
  AND i.organization_id=NEW.organization_id
  AND i.deleted_at IS NULL AND i.is_active=1
  AND w.deleted_at IS NULL AND w.status='active'
)
BEGIN
 SELECT RAISE(ABORT,'equipment inventory mapping references must be active and same-organization');
END;

CREATE TRIGGER trg_eq_inventory_fuel_mapping_scope_update
BEFORE UPDATE OF organization_id,category_id,energy_type,item_id,warehouse_id,is_active
ON eq_inventory_fuel_mappings
WHEN NOT EXISTS (
 SELECT 1 FROM inv_items i JOIN inv_warehouses w
  ON w.organization_id=i.organization_id
 WHERE i.id=NEW.item_id AND w.id=NEW.warehouse_id
  AND i.organization_id=NEW.organization_id
  AND i.deleted_at IS NULL AND i.is_active=1
  AND w.deleted_at IS NULL AND w.status='active'
)
BEGIN
 SELECT RAISE(ABORT,'equipment inventory mapping references must be active and same-organization');
END;
