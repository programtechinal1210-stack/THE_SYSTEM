from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.access import require
from .registry_service import EquipmentRegistryService, _hex, _now

ENERGY_TYPES = {"diesel", "gasoline", "electricity", "other"}


class EquipmentInventoryMappingService:
    def __init__(self, session, request):
        self.session = session
        self.request = request
        self.registry = EquipmentRegistryService(session, request)

    async def list(self, organization_id=None):
        permission = "equipment.inventory.view"
        require(self.request, permission)
        organization = await self.registry._organization(organization_id, permission)
        rows = (await self.session.execute(text(
            "SELECT m.id,m.organization_id,m.category_id,c.category_code,c.name_ar AS category_name,"
            "m.energy_type,m.item_id,i.code AS item_code,i.name_ar AS item_name,m.warehouse_id,"
            "w.code AS warehouse_code,w.name AS warehouse_name,m.is_active,m.updated_at "
            "FROM eq_inventory_fuel_mappings m "
            "JOIN eq_categories c ON c.organization_id=m.organization_id AND c.id=m.category_id "
            "JOIN inv_items i ON i.id=m.item_id "
            "JOIN inv_warehouses w ON w.id=m.warehouse_id "
            "WHERE m.organization_id=:org ORDER BY c.category_code,m.energy_type"
        ), {"org": organization})).mappings().all()
        return {"items": [dict(row) for row in rows]}

    async def save(self, category_id, energy_type, payload):
        permission = "equipment.inventory.manage"
        require(self.request, permission)
        if energy_type not in ENERGY_TYPES:
            raise HTTPException(422, "Unsupported equipment energy type")
        organization = await self.registry._organization(payload.organization_id, permission, create=True)
        category = (await self.session.execute(text(
            "SELECT fuel_unit FROM eq_categories WHERE id=:id AND organization_id=:org "
            "AND deleted_at IS NULL AND is_active=1"
        ), {"id": _hex(category_id), "org": organization})).mappings().first()
        if category is None:
            raise HTTPException(404, "Equipment category unavailable")
        item = (await self.session.execute(text(
            "SELECT i.organization_id,i.is_active,i.deleted_at,u.code AS unit_code "
            "FROM inv_items i JOIN inv_units u ON u.id=i.base_unit_id WHERE i.id=:id"
        ), {"id": payload.item_id.hex})).mappings().first()
        warehouse = (await self.session.execute(text(
            "SELECT organization_id,status,deleted_at FROM inv_warehouses WHERE id=:id"
        ), {"id": payload.warehouse_id.hex})).mappings().first()
        if (
            item is None or item["organization_id"] != organization or not item["is_active"]
            or item["deleted_at"] is not None or warehouse is None
            or warehouse["organization_id"] != organization or warehouse["status"] != "active"
            or warehouse["deleted_at"] is not None
        ):
            raise HTTPException(422, "Inventory item and warehouse must be active and in the selected organization")
        if not category["fuel_unit"] or item["unit_code"] != category["fuel_unit"]:
            raise HTTPException(422, "Inventory item base unit must match the equipment category fuel unit")

        actor = _hex(self.request.state.user_id)
        now = _now()
        existing_id = await self.session.scalar(text(
            "SELECT id FROM eq_inventory_fuel_mappings "
            "WHERE organization_id=:org AND category_id=:category AND energy_type=:energy"
        ), {"org": organization, "category": _hex(category_id), "energy": energy_type})
        identifier = existing_id or uuid4().hex
        try:
            if existing_id:
                await self.session.execute(text(
                    "UPDATE eq_inventory_fuel_mappings SET item_id=:item,warehouse_id=:warehouse,"
                    "is_active=:active,updated_at=:now,updated_by=:actor WHERE id=:id"
                ), {
                    "item": payload.item_id.hex, "warehouse": payload.warehouse_id.hex,
                    "active": int(payload.is_active), "now": now, "actor": actor, "id": identifier,
                })
            else:
                await self.session.execute(text(
                    "INSERT INTO eq_inventory_fuel_mappings(id,organization_id,category_id,energy_type,"
                    "item_id,warehouse_id,is_active,created_at,created_by,updated_at,updated_by) "
                    "VALUES(:id,:org,:category,:energy,:item,:warehouse,:active,:now,:actor,:now,:actor)"
                ), {
                    "id": identifier, "org": organization, "category": _hex(category_id),
                    "energy": energy_type, "item": payload.item_id.hex,
                    "warehouse": payload.warehouse_id.hex, "active": int(payload.is_active),
                    "now": now, "actor": actor,
                })
        except IntegrityError as exc:
            raise HTTPException(409, "Inventory mapping changed concurrently or violates scope") from exc
        self.request.state.audit_details = {
            "entity_type": "equipment.inventory_fuel_mapping",
            "entity_id": identifier,
            "new": {
                "organization_id": organization, "category_id": _hex(category_id),
                "energy_type": energy_type, "item_id": payload.item_id.hex,
                "warehouse_id": payload.warehouse_id.hex, "is_active": payload.is_active,
            },
        }
        return {"id": identifier, "status": "configured"}
