"""Operational fuel/energy ledger; it never reads or mutates Inventory stock."""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.access import require
from .registry_service import EquipmentRegistryService, _hex, _now

POSITIVE_EVENTS = {"opening", "issued", "adjustment_in"}
NEGATIVE_EVENTS = {"consumed", "returned", "adjustment_out"}


def _decimal_text(value):
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    return format(number.normalize(), "f") if number else "0"


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(409, "Stored fuel quantity or cost is invalid") from None


def _event_time(value):
    if value is None:
        return _now()
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


class EquipmentFuelService:
    def __init__(self, session, request):
        self.session = session
        self.request = request
        self.registry = EquipmentRegistryService(session, request)

    @property
    def actor(self):
        return self.request.state.user_id.hex

    async def _begin_serialized_write(self):
        if self.session.bind.dialect.name != "sqlite":
            raise HTTPException(503, "Fuel ledger serialization requires the configured SQLite Core database")
        await self.session.execute(text("BEGIN IMMEDIATE"))

    async def _asset(self, asset_id, permission):
        row = (await self.session.execute(text(
            "SELECT id,organization_id,category_id FROM eq_assets "
            "WHERE id=:id AND deleted_at IS NULL"
        ), {"id": _hex(asset_id)})).mappings().first()
        if row is None:
            raise HTTPException(404, "Equipment asset unavailable")
        await self.registry._visible_org(row["organization_id"], permission)
        category = (await self.session.execute(text(
            "SELECT fuel_unit FROM eq_categories WHERE id=:id AND organization_id=:org "
            "AND deleted_at IS NULL"
        ), {"id": row["category_id"], "org": row["organization_id"]})).mappings().first()
        return {**dict(row), "fuel_unit": category["fuel_unit"] if category else None}

    @staticmethod
    def _validate_unit(payload, asset):
        required_unit = {"diesel": "L", "gasoline": "L", "electricity": "kWh"}.get(payload.energy_type)
        if required_unit and payload.unit != required_unit:
            raise HTTPException(422, f"{payload.energy_type} requires unit {required_unit}")
        if asset["fuel_unit"] and payload.unit != asset["fuel_unit"]:
            raise HTTPException(422, "Fuel unit must match the equipment category's configured fuel unit")

    @staticmethod
    def _payload_hash(payload):
        values = payload.model_dump(mode="json")
        values["event_at"] = payload.event_at.isoformat() if payload.event_at is not None else None
        return hashlib.sha256(json.dumps(
            values, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")).hexdigest()

    async def _validate_return_source(self, organization_id, asset_id, payload, exclude_event_id=None):
        source_id = _hex(payload.related_issue_event_id)
        if source_id is None:
            return
        source = (await self.session.execute(text(
            "SELECT id,organization_id,asset_id,event_type,energy_type,quantity,unit,status "
            "FROM eq_fuel_events WHERE id=:id"
        ), {"id": source_id})).mappings().first()
        if (
            source is None or source["organization_id"] != organization_id
            or source["asset_id"] != asset_id or source["event_type"] != "issued"
            or source["energy_type"] != payload.energy_type or source["unit"] != payload.unit
            or source["status"] != "posted"
        ):
            raise HTTPException(409, "RETURN_REQUIRES_MATCHING_APPROVED_ISSUE_EVENT")
        parameters = {"source": source_id}
        exclusion = ""
        if exclude_event_id:
            exclusion = " AND id<>:exclude"
            parameters["exclude"] = exclude_event_id
        linked = (await self.session.execute(text(
            "SELECT quantity FROM eq_fuel_events WHERE related_issue_event_id=:source "
            "AND event_type='returned' AND status IN ('draft','posted')" + exclusion
        ), parameters)).mappings().all()
        reserved_quantity = sum((_decimal(row["quantity"]) for row in linked), Decimal(0))
        if reserved_quantity + payload.quantity > _decimal(source["quantity"]):
            raise HTTPException(409, "RETURN_EXCEEDS_ISSUED_EVENT_QUANTITY")

    async def create_event(self, asset_id, payload):
        require(self.request, "equipment.fuel.record")
        await self._begin_serialized_write()
        asset = await self._asset(asset_id, "equipment.fuel.record")
        self._validate_unit(payload, asset)
        event_at = _event_time(payload.event_at)
        payload_hash = self._payload_hash(payload)
        existing = (await self.session.execute(text(
            "SELECT * FROM eq_fuel_events WHERE organization_id=:org AND idempotency_key=:key"
        ), {"org": asset["organization_id"], "key": payload.idempotency_key})).mappings().first()
        if existing:
            if existing["payload_hash"] != payload_hash:
                raise HTTPException(409, "Fuel idempotency key was already used for a different event")
            return {**dict(existing), "idempotent_replay": True}
        if payload.event_type == "returned":
            await self._validate_return_source(
                asset["organization_id"], asset["id"], payload
            )

        latest = await self.session.scalar(text(
            "SELECT MAX(event_at) FROM eq_fuel_events WHERE organization_id=:org AND asset_id=:asset "
            "AND energy_type=:energy AND unit=:unit AND status='posted'"
        ), {
            "org": asset["organization_id"], "asset": asset["id"],
            "energy": payload.energy_type, "unit": payload.unit,
        })
        if latest and event_at <= latest:
            raise HTTPException(409, "Fuel event time must follow the latest posted event in this ledger")
        currency_id = _hex(payload.currency_id)
        if currency_id:
            active_currency = await self.session.scalar(text(
                "SELECT 1 FROM core_currencies WHERE id=:id AND is_active=1"
            ), {"id": currency_id})
            if not active_currency:
                raise HTTPException(422, "Fuel event currency is unavailable or inactive")
        identifier, now = uuid4().hex, _now()
        record = {
            "id": identifier,
            "organization_id": asset["organization_id"],
            "asset_id": asset["id"],
            "fuel_event_code": "EMO-F-" + identifier[:12].upper(),
            "event_type": payload.event_type,
            "energy_type": payload.energy_type,
            "quantity": _decimal_text(payload.quantity),
            "related_issue_event_id": _hex(payload.related_issue_event_id),
            "unit": payload.unit,
            "event_at": event_at,
            "unit_cost": _decimal_text(payload.unit_cost) if payload.unit_cost is not None else None,
            "cost_amount": (
                _decimal_text(payload.quantity * payload.unit_cost)
                if payload.unit_cost is not None else None
            ),
            "currency_id": currency_id,
            "status": "draft",
            "reason_code": payload.reason_code,
            "notes": payload.notes,
            "idempotency_key": payload.idempotency_key,
            "payload_hash": payload_hash,
            "created_at": now,
            "created_by": self.actor,
        }
        try:
            await self.session.execute(text(
                "INSERT INTO eq_fuel_events(id,organization_id,asset_id,fuel_event_code,event_type,energy_type,"
                "quantity,related_issue_event_id,unit,event_at,unit_cost,cost_amount,currency_id,status,reason_code,notes,idempotency_key,payload_hash,"
                "created_at,created_by) VALUES(:id,:organization_id,:asset_id,:fuel_event_code,:event_type,"
                ":energy_type,:quantity,:related_issue_event_id,:unit,:event_at,:unit_cost,:cost_amount,:currency_id,:status,:reason_code,:notes,"
                ":idempotency_key,:payload_hash,:created_at,:created_by)"
            ), record)
        except IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise HTTPException(409, "Fuel opening or idempotency key already exists") from None
            raise
        self.request.state.audit_details = {
            "entity_type": "equipment.fuel_event",
            "entity_id": identifier,
            "new": {
                "event_type": payload.event_type,
                "energy_type": payload.energy_type,
                "quantity": record["quantity"],
                "unit": payload.unit,
                "status": "draft",
            },
            "summary": "Operational fuel/energy event submitted; no Inventory stock was changed",
        }
        return {**record, "idempotent_replay": False}

    async def decide_event(self, event_id, approve, decision_reason=""):
        permission = "equipment.fuel.approve"
        require(self.request, permission)
        await self._begin_serialized_write()
        event = (await self.session.execute(text(
            "SELECT * FROM eq_fuel_events WHERE id=:id"
        ), {"id": _hex(event_id)})).mappings().first()
        if not event:
            raise HTTPException(404, "Fuel event unavailable")
        await self.registry._visible_org(event["organization_id"], permission)
        if event["status"] != "draft":
            raise HTTPException(409, "Only a draft fuel event can be reviewed")
        if event["created_by"] == self.actor:
            raise HTTPException(409, "Fuel event review must be performed by a different user")
        if approve and event["event_type"] == "returned" and event["related_issue_event_id"]:
            from ..domain.fuel import FuelEventInput
            return_payload = FuelEventInput(
                event_type="returned",
                energy_type=event["energy_type"],
                quantity=event["quantity"],
                unit=event["unit"],
                related_issue_event_id=event["related_issue_event_id"],
                idempotency_key=event["idempotency_key"],
            )
            await self._validate_return_source(
                event["organization_id"], event["asset_id"], return_payload,
                exclude_event_id=event["id"],
            )

        balance = await self._balance(
            event["organization_id"], event["asset_id"], event["energy_type"], event["unit"]
        )
        latest = await self.session.scalar(text(
            "SELECT MAX(event_at) FROM eq_fuel_events WHERE organization_id=:org AND asset_id=:asset "
            "AND energy_type=:energy AND unit=:unit AND status='posted'"
        ), {
            "org": event["organization_id"], "asset": event["asset_id"],
            "energy": event["energy_type"], "unit": event["unit"],
        })
        if approve and latest and event["event_at"] <= latest:
            raise HTTPException(409, "Fuel draft is stale; submit it again after the latest posted event")
        quantity = _decimal(event["quantity"])
        next_balance = balance
        if approve:
            if event["event_type"] in POSITIVE_EVENTS:
                if event["event_type"] == "opening" and balance != 0:
                    raise HTTPException(409, "Opening balance must be the first posted event for this ledger")
                next_balance += quantity
            else:
                if quantity > balance:
                    raise HTTPException(409, "Fuel consumption/return exceeds the available operational balance")
                next_balance -= quantity
            now = _now()
            await self.session.execute(text(
                "UPDATE eq_fuel_events SET status='posted',reviewed_at=:now,reviewed_by=:actor "
                "WHERE id=:id AND status='draft'"
            ), {"now": now, "actor": self.actor, "id": event["id"]})
            status = "posted"
        else:
            if not decision_reason.strip():
                raise HTTPException(422, "A reason is required to reject a fuel event")
            now = _now()
            await self.session.execute(text(
                "UPDATE eq_fuel_events SET status='rejected',reviewed_at=:now,reviewed_by=:actor,"
                "rejection_reason=:reason WHERE id=:id AND status='draft'"
            ), {
                "now": now, "actor": self.actor, "reason": decision_reason.strip(),
                "id": event["id"],
            })
            status = "rejected"

        self.request.state.audit_details = {
            "entity_type": "equipment.fuel_event",
            "entity_id": event["id"],
            "old": {"status": "draft", "operational_balance": _decimal_text(balance)},
            "new": {
                "status": status,
                "operational_balance": _decimal_text(next_balance),
                "review_reason": decision_reason.strip() or None,
            },
            "summary": "Operational fuel/energy event reviewed without posting to Inventory",
        }
        return {
            "id": event["id"], "status": status, "balance": _decimal_text(next_balance),
            "unit": event["unit"], "reviewed_at": now, "reviewed_by": self.actor,
        }

    async def _balance(self, organization_id, asset_id, energy_type, unit):
        rows = (await self.session.execute(text(
            "SELECT event_type,quantity FROM eq_fuel_events WHERE organization_id=:org "
            "AND asset_id=:asset AND energy_type=:energy AND unit=:unit AND status='posted'"
        ), {
            "org": organization_id, "asset": asset_id,
            "energy": energy_type, "unit": unit,
        })).mappings().all()
        balance = Decimal(0)
        for row in rows:
            quantity = _decimal(row["quantity"])
            balance += quantity if row["event_type"] in POSITIVE_EVENTS else -quantity
        return balance

    async def list_events(self, asset_id):
        require(self.request, "equipment.fuel.view")
        asset = await self._asset(asset_id, "equipment.fuel.view")
        rows = (await self.session.execute(text(
            "SELECT * FROM eq_fuel_events WHERE organization_id=:org AND asset_id=:asset "
            "ORDER BY event_at,id LIMIT 500"
        ), {"org": asset["organization_id"], "asset": asset["id"]})).mappings().all()
        return {"items": [dict(row) for row in rows]}

    async def balances(self, asset_id):
        require(self.request, "equipment.fuel.view")
        asset = await self._asset(asset_id, "equipment.fuel.view")
        rows = (await self.session.execute(text(
            "SELECT energy_type,unit,event_type,quantity,status FROM eq_fuel_events "
            "WHERE organization_id=:org AND asset_id=:asset AND status='posted' "
            "ORDER BY energy_type,unit,event_at,id"
        ), {"org": asset["organization_id"], "asset": asset["id"]})).mappings().all()
        ledgers = {}
        for row in rows:
            key = (row["energy_type"], row["unit"])
            ledger = ledgers.setdefault(key, {
                "energy_type": key[0], "unit": key[1],
                "opening": Decimal(0), "issued": Decimal(0), "consumed": Decimal(0),
                "returned": Decimal(0), "adjustment_in": Decimal(0), "adjustment_out": Decimal(0),
                "balance": Decimal(0),
            })
            quantity = _decimal(row["quantity"])
            ledger[row["event_type"]] += quantity
            ledger["balance"] += quantity if row["event_type"] in POSITIVE_EVENTS else -quantity
        return {"items": [
            {key: _decimal_text(value) if isinstance(value, Decimal) else value for key, value in row.items()}
            for row in ledgers.values()
        ]}
