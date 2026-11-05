"""Inventory-backed, append-only equipment part lifecycle operations."""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.access import require
from modules.module_inventory.application.posting_access import warehouse
from .registry_service import EquipmentRegistryService, _hex, _now


class EquipmentPartService:
    def __init__(self, session, request):
        self.session = session
        self.request = request
        self.registry = EquipmentRegistryService(session, request)

    @property
    def actor(self):
        return self.request.state.user_id.hex

    async def _begin_serialized_write(self):
        if self.session.bind.dialect.name != "sqlite":
            raise HTTPException(503, "Part lifecycle serialization requires the configured SQLite Core database")
        await self.session.execute(text("BEGIN IMMEDIATE"))

    async def _asset(self, asset_id, permission):
        row = (await self.session.execute(text(
            "SELECT id,organization_id,meter_normalized_latest,meter_generation,"
            "meter_type_locked,meter_unit_locked,meter_last_at "
            "FROM eq_assets WHERE id=:id AND deleted_at IS NULL"
        ), {"id": _hex(asset_id)})).mappings().first()
        if row is None:
            raise HTTPException(404, "Equipment asset unavailable")
        await self.registry._visible_org(row["organization_id"], permission)
        return dict(row)

    async def _maintenance_order(self, asset, order_id):
        if order_id is None:
            return None
        order = await self.session.scalar(text(
            "SELECT id FROM eq_maintenance_orders WHERE id=:id AND organization_id=:org "
            "AND asset_id=:asset AND status<>'cancelled'"
        ), {"id": _hex(order_id), "org": asset["organization_id"], "asset": asset["id"]})
        if not order:
            raise HTTPException(422, "Maintenance order must belong to this equipment and organization")
        return order

    async def _inventory_document(self, organization_id, document_id, item_id, kind):
        require(self.request, "equipment.inventory.view")
        require(self.request, "inventory.documents.view")
        document = (await self.session.execute(text(
            "SELECT id,organization_id,warehouse_id,document_type,status,document_date "
            "FROM inv_documents WHERE id=:id"
        ), {"id": _hex(document_id)})).mappings().first()
        if (
            document is None or document["organization_id"] != organization_id
            or document["document_type"] != kind or document["status"] not in ("POSTED", "CLOSED")
        ):
            raise HTTPException(409, "A posted, same-organization Inventory document of the required type is required")
        document_column = (
            "installation_inventory_document_id" if kind == "ISSUE_DIRECT"
            else "removal_inventory_document_id"
        )
        already_linked = await self.session.scalar(text(
            f"SELECT 1 FROM eq_part_lifecycles WHERE {document_column}=:document"
        ), {"document": document["id"]})
        if already_linked:
            raise HTTPException(409, "Inventory document is already linked to a part lifecycle")
        await warehouse(
            self.session, self.request, document["warehouse_id"], "inventory.documents.view"
        )
        lines = (await self.session.execute(text(
            "SELECT item_id,base_quantity FROM inv_document_lines WHERE document_id=:id"
        ), {"id": document["id"]})).mappings().all()
        if len(lines) != 1 or lines[0]["item_id"] != _hex(item_id):
            raise HTTPException(409, "Inventory document must contain exactly the linked part item")
        try:
            quantity = Decimal(lines[0]["base_quantity"])
        except (InvalidOperation, TypeError, ValueError):
            raise HTTPException(409, "Inventory part quantity is invalid") from None
        if quantity != Decimal(1):
            raise HTTPException(409, "A physical part lifecycle requires exactly one Inventory unit")
        return dict(document)

    @staticmethod
    def _meter_snapshot(asset, event_at, lower_bound=None):
        if asset["meter_type_locked"] == "none":
            return None, None, None
        if asset["meter_normalized_latest"] is None:
            raise HTTPException(409, "An approved meter baseline is required to measure part life")
        if asset["meter_last_at"] and event_at < asset["meter_last_at"]:
            raise HTTPException(409, "Part lifecycle time cannot precede the latest approved meter reading")
        if lower_bound and event_at < lower_bound:
            raise HTTPException(409, "Part removal cannot precede installation")
        return (
            asset["meter_generation"],
            asset["meter_normalized_latest"],
            asset["meter_unit_locked"],
        )

    @staticmethod
    def _hash(payload):
        return hashlib.sha256(json.dumps(
            payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()

    async def _prepare_install(self, asset, payload, permission):
        item_id = _hex(payload.inventory_item_id)
        item = (await self.session.execute(text(
            "SELECT id FROM inv_items WHERE id=:id AND organization_id=:org "
            "AND is_active=1 AND deleted_at IS NULL"
        ), {"id": item_id, "org": asset["organization_id"]})).first()
        if not item:
            raise HTTPException(422, "Part must reference an active Inventory item in this organization")
        await self._maintenance_order(asset, payload.maintenance_order_id)
        installed_at = payload.installed_at.isoformat(timespec="microseconds").replace("+00:00", "Z")
        key = payload.idempotency_key
        payload_hash = self._hash(payload)
        existing = (await self.session.execute(text(
            "SELECT * FROM eq_part_lifecycles WHERE organization_id=:org AND idempotency_key=:key"
        ), {"org": asset["organization_id"], "key": key})).mappings().first()
        if existing:
            if existing["payload_hash"] != payload_hash:
                raise HTTPException(409, "Part idempotency key was already used for a different installation")
            return dict(existing), True
        document = await self._inventory_document(
            asset["organization_id"], payload.installation_inventory_document_id,
            item_id, "ISSUE_DIRECT",
        )
        generation, value, unit = self._meter_snapshot(asset, installed_at)
        if document["document_date"] > installed_at[:10]:
            raise HTTPException(409, "Inventory issue date cannot follow part installation")
        return {
            "id": uuid4().hex, "organization_id": asset["organization_id"], "asset_id": asset["id"],
            "inventory_item_id": item_id, "mount_position": payload.mount_position,
            "part_serial_number": payload.part_serial_number or None, "lot_number": payload.lot_number or None,
            "lifecycle_status": "installed", "installed_at": installed_at,
            "installed_meter_generation": generation, "installed_meter_value": value,
            "installed_meter_unit": unit, "removed_at": None, "removed_meter_generation": None,
            "removed_meter_value": None, "removed_meter_unit": None, "actual_life_value": None,
            "reason_code": None, "maintenance_order_id": _hex(payload.maintenance_order_id),
            "installation_inventory_document_id": document["id"], "removal_inventory_document_id": None,
            "idempotency_key": key, "payload_hash": payload_hash, "removal_idempotency_key": None,
            "removal_payload_hash": None, "created_at": _now(), "updated_at": _now(),
            "created_by": self.actor, "updated_by": self.actor, "version": 1,
        }, False

    async def _insert_install(self, record):
        await self.session.execute(text(
            "INSERT INTO eq_part_lifecycles(id,organization_id,asset_id,inventory_item_id,mount_position,"
            "part_serial_number,lot_number,lifecycle_status,installed_at,installed_meter_generation,"
            "installed_meter_value,installed_meter_unit,removed_at,removed_meter_generation,removed_meter_value,"
            "removed_meter_unit,actual_life_value,reason_code,maintenance_order_id,installation_inventory_document_id,"
            "removal_inventory_document_id,idempotency_key,payload_hash,removal_idempotency_key,removal_payload_hash,"
            "created_at,updated_at,created_by,updated_by,version) VALUES("
            ":id,:organization_id,:asset_id,:inventory_item_id,:mount_position,:part_serial_number,:lot_number,"
            ":lifecycle_status,:installed_at,:installed_meter_generation,:installed_meter_value,:installed_meter_unit,"
            ":removed_at,:removed_meter_generation,:removed_meter_value,:removed_meter_unit,:actual_life_value,"
            ":reason_code,:maintenance_order_id,:installation_inventory_document_id,:removal_inventory_document_id,"
            ":idempotency_key,:payload_hash,:removal_idempotency_key,:removal_payload_hash,:created_at,:updated_at,"
            ":created_by,:updated_by,:version)"
        ), record)

    async def install(self, asset_id, payload):
        require(self.request, "equipment.parts.install")
        await self._begin_serialized_write()
        asset = await self._asset(asset_id, "equipment.parts.install")
        record, replayed = await self._prepare_install(asset, payload, "equipment.parts.install")
        if not replayed:
            try:
                await self._insert_install(record)
            except IntegrityError as exc:
                if "ux_eq_part_lifecycle_active_mount" in str(exc) or "ux_eq_part_lifecycle_active_serial" in str(exc):
                    raise HTTPException(409, "An active part already occupies this mount or serial number") from None
                if "UNIQUE constraint failed" in str(exc):
                    raise HTTPException(409, "Part lifecycle idempotency key conflicts") from None
                raise
            self._audit(record["id"], None, {"status": "installed", "mount_position": record["mount_position"]})
        return {**record, "idempotent_replay": replayed}

    async def remove(self, lifecycle_id, payload):
        require(self.request, "equipment.parts.remove")
        await self._begin_serialized_write()
        row = (await self.session.execute(text(
            "SELECT * FROM eq_part_lifecycles WHERE id=:id"
        ), {"id": _hex(lifecycle_id)})).mappings().first()
        if row is None:
            raise HTTPException(404, "Part lifecycle unavailable")
        await self.registry._visible_org(row["organization_id"], "equipment.parts.remove")
        payload_hash = self._hash(payload)
        if row["lifecycle_status"] == "removed":
            if row["removal_idempotency_key"] == payload.idempotency_key and row["removal_payload_hash"] == payload_hash:
                return {**dict(row), "idempotent_replay": True}
            raise HTTPException(409, "Only an installed part can be removed")
        asset = await self._asset(row["asset_id"], "equipment.parts.remove")
        document = await self._inventory_document(
            row["organization_id"], payload.removal_inventory_document_id,
            row["inventory_item_id"], "RECEIPT",
        )
        removed_at = payload.removed_at.isoformat(timespec="microseconds").replace("+00:00", "Z")
        if document["document_date"] > removed_at[:10]:
            raise HTTPException(409, "Inventory return date cannot follow part removal")
        generation, value, unit = self._meter_snapshot(asset, removed_at, row["installed_at"])
        life = None
        if row["installed_meter_value"] is not None and value is not None:
            try:
                life = str(Decimal(value) - Decimal(row["installed_meter_value"]))
                if Decimal(life) < 0:
                    raise ValueError
            except (InvalidOperation, ValueError):
                raise HTTPException(409, "Part meter life is invalid") from None
        now = _now()
        try:
            await self.session.execute(text(
                "UPDATE eq_part_lifecycles SET lifecycle_status='removed',removed_at=:removed_at,"
                "removed_meter_generation=:generation,removed_meter_value=:value,removed_meter_unit=:unit,"
                "actual_life_value=:life,reason_code=:reason,removal_inventory_document_id=:document,"
                "removal_idempotency_key=:key,removal_payload_hash=:payload_hash,updated_at=:now,"
                "updated_by=:actor,version=version+1 WHERE id=:id AND lifecycle_status='installed'"
            ), {
                "removed_at": removed_at, "generation": generation, "value": value, "unit": unit,
                "life": life, "reason": payload.reason_code, "document": document["id"],
                "key": payload.idempotency_key, "payload_hash": payload_hash, "now": now,
                "actor": self.actor, "id": row["id"],
            })
        except IntegrityError as exc:
            raise HTTPException(409, "Part lifecycle or Inventory return conflicts with immutable history") from exc
        result = {**dict(row), "lifecycle_status": "removed", "removed_at": removed_at,
            "removed_meter_generation": generation, "removed_meter_value": value,
            "removed_meter_unit": unit, "actual_life_value": life, "reason_code": payload.reason_code,
            "removal_inventory_document_id": document["id"], "removal_idempotency_key": payload.idempotency_key,
            "removal_payload_hash": payload_hash, "updated_at": now, "updated_by": self.actor,
            "version": row["version"] + 1, "idempotent_replay": False}
        self._audit(row["id"], {"status": "installed"}, {"status": "removed", "reason_code": payload.reason_code,
            "actual_life_value": life, "inventory_document_id": document["id"]})
        return result

    async def replace(self, lifecycle_id, payload):
        require(self.request, "equipment.parts.replace")
        await self._begin_serialized_write()
        current = (await self.session.execute(text(
            "SELECT * FROM eq_part_lifecycles WHERE id=:id"
        ), {"id": _hex(lifecycle_id)})).mappings().first()
        if current is None:
            raise HTTPException(404, "Part lifecycle unavailable")
        await self.registry._visible_org(current["organization_id"], "equipment.parts.replace")
        removed_at = payload.removed_at.isoformat(timespec="microseconds").replace("+00:00", "Z")
        removal_payload = {
            "removed_at": removed_at, "reason_code": payload.removal_reason_code,
            "removal_inventory_document_id": _hex(payload.removal_inventory_document_id),
        }
        removal_hash = hashlib.sha256(json.dumps(
            removal_payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        install_hash = self._hash(payload)
        if current["lifecycle_status"] == "removed":
            replacement = (await self.session.execute(text(
                "SELECT * FROM eq_part_lifecycles WHERE organization_id=:org AND idempotency_key=:key"
            ), {
                "org": current["organization_id"], "key": payload.idempotency_key,
            })).mappings().first()
            if (
                current["removal_idempotency_key"] == payload.idempotency_key + ":remove"
                and current["removal_payload_hash"] == removal_hash
                and replacement is not None and replacement["payload_hash"] == install_hash
            ):
                return {
                    "removed": {"id": current["id"], "actual_life_value": current["actual_life_value"],
                                "removal_inventory_document_id": current["removal_inventory_document_id"]},
                    "installed": dict(replacement), "idempotent_replay": True,
                }
            raise HTTPException(409, "Only an installed part can be replaced")
        if current["lifecycle_status"] != "installed":
            raise HTTPException(409, "Only an installed part can be replaced")
        asset = await self._asset(current["asset_id"], "equipment.parts.replace")
        removal_doc = await self._inventory_document(
            current["organization_id"], payload.removal_inventory_document_id,
            current["inventory_item_id"], "RECEIPT",
        )
        if removal_doc["document_date"] > removed_at[:10]:
            raise HTTPException(409, "Inventory return date cannot follow part removal")
        generation, meter_value, meter_unit = self._meter_snapshot(asset, removed_at, current["installed_at"])
        install_record, replayed = await self._prepare_install(asset, payload, "equipment.parts.replace")
        if replayed:
            raise HTTPException(409, "Replacement installation idempotency key is already in use")
        if install_record["mount_position"] != current["mount_position"]:
            raise HTTPException(422, "A replacement must occupy the original mount position")
        try:
            life = (
                str(Decimal(meter_value) - Decimal(current["installed_meter_value"]))
                if meter_value is not None and current["installed_meter_value"] is not None else None
            )
            if life is not None and Decimal(life) < 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            raise HTTPException(409, "Part meter life is invalid") from None
        removal_payload["removal_inventory_document_id"] = removal_doc["id"]
        removal_hash = hashlib.sha256(json.dumps(
            removal_payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        now = _now()
        await self.session.execute(text(
            "UPDATE eq_part_lifecycles SET lifecycle_status='removed',removed_at=:removed_at,"
            "removed_meter_generation=:generation,removed_meter_value=:value,removed_meter_unit=:unit,"
            "actual_life_value=:life,reason_code=:reason,removal_inventory_document_id=:document,"
            "removal_idempotency_key=:key,removal_payload_hash=:hash,updated_at=:now,updated_by=:actor,"
            "version=version+1 WHERE id=:id AND lifecycle_status='installed'"
        ), {
            "removed_at": removed_at, "generation": generation, "value": meter_value, "unit": meter_unit,
            "life": life, "reason": payload.removal_reason_code, "document": removal_doc["id"],
            "key": payload.idempotency_key + ":remove", "hash": removal_hash, "now": now,
            "actor": self.actor, "id": current["id"],
        })
        try:
            await self._insert_install(install_record)
        except IntegrityError as exc:
            raise HTTPException(409, "Replacement conflicts with an active mount, serial, or inventory record") from exc
        self.request.state.audit_details = {
            "entity_type": "equipment.part_lifecycle.replacement",
            "entity_id": current["id"],
            "old": {"status": "installed"},
            "new": {
                "status": "removed", "replacement_id": install_record["id"],
                "actual_life_value": life,
                "removal_inventory_document_id": removal_doc["id"],
                "installation_inventory_document_id": install_record["installation_inventory_document_id"],
            },
        }
        return {"removed": {"id": current["id"], "actual_life_value": life,
                "removal_inventory_document_id": removal_doc["id"]},
            "installed": install_record, "idempotent_replay": False}

    async def list_for_asset(self, asset_id):
        require(self.request, "equipment.parts.view")
        asset = await self._asset(asset_id, "equipment.parts.view")
        rows = (await self.session.execute(text(
            "SELECT p.*,i.code AS inventory_item_code,i.name_ar AS inventory_item_name "
            "FROM eq_part_lifecycles p JOIN inv_items i "
            "ON i.id=p.inventory_item_id AND i.organization_id=p.organization_id "
            "WHERE p.organization_id=:org AND p.asset_id=:asset "
            "ORDER BY p.installed_at DESC,p.id LIMIT 500"
        ), {"org": asset["organization_id"], "asset": asset["id"]})).mappings().all()
        return {"items": [dict(row) for row in rows]}

    def _audit(self, identifier, old, new):
        self.request.state.audit_details = {
            "entity_type": "equipment.part_lifecycle", "entity_id": identifier,
            "old": old, "new": new,
        }
