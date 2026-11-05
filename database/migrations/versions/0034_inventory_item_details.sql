ALTER TABLE inv_items ADD COLUMN aliases_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE inv_items ADD COLUMN barcode TEXT;
ALTER TABLE inv_items ADD COLUMN item_type TEXT NOT NULL DEFAULT 'MATERIAL'
 CHECK(item_type IN ('MATERIAL','SPARE_PART','CONSUMABLE','TOOL','OTHER'));
ALTER TABLE inv_items ADD COLUMN notes TEXT NOT NULL DEFAULT '';
CREATE UNIQUE INDEX ux_inv_item_barcode ON inv_items(organization_id,barcode) WHERE barcode IS NOT NULL AND barcode<>'';
