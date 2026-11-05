"""Append-only equipment meter event workflows."""
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.access import require
from .registry_service import EquipmentRegistryService, _hex, _now


def _decimal_text(value):
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    return format(number.normalize(), "f") if number else "0"


def _decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(409, "Stored meter value is invalid") from None


def _event_time(value):
    if value is None:
        return _now()
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class EquipmentMeterService:
    def __init__(self, session, request):
        self.session = session
        self.request = request
        self.registry = EquipmentRegistryService(session, request)

    @property
    def actor(self):
        return self.request.state.user_id.hex

    async def _begin_serialized_write(self):
        if self.session.bind.dialect.name != "sqlite":
            raise HTTPException(503, "Meter event serialization requires the configured SQLite Core database")
        await self.session.execute(text("BEGIN IMMEDIATE"))

    async def _asset(self, asset_id, permission):
        row = (await self.session.execute(text(
            "SELECT id,organization_id,meter_latest,meter_normalized_latest,meter_generation,"
            "meter_type_locked,meter_unit_locked,meter_last_at,deleted_at "
            "FROM eq_assets WHERE id=:id AND deleted_at IS NULL"
        ), {"id": _hex(asset_id)})).mappings().first()
        if row is None:
            raise HTTPException(404, "Equipment asset unavailable")
        await self.registry._visible_org(row["organization_id"], permission)
        return dict(row)

    @staticmethod
    def _base_offset(asset):
        if asset["meter_latest"] is None or asset["meter_normalized_latest"] is None:
            return Decimal(0)
        return _decimal(asset["meter_normalized_latest"]) - _decimal(asset["meter_latest"])

    @staticmethod
    def _validate_meter_type(asset, payload):
        if (
            asset["meter_type_locked"] == "none"
            or payload.meter_type != asset["meter_type_locked"]
            or payload.meter_unit != asset["meter_unit_locked"]
        ):
            raise HTTPException(422, "Meter type and unit must match the asset's locked category")

    @staticmethod
    def _validate_event_time(asset, event_at):
        if asset["meter_last_at"] and event_at <= asset["meter_last_at"]:
            raise HTTPException(409, "Meter event time must follow the latest approved meter event")

    @staticmethod
    def _payload_hash(event_type, payload):
        data = payload.model_dump(mode="json")
        data["event_at"] = (
            payload.event_at.isoformat() if payload.event_at is not None else None
        )
        encoded = json.dumps(
            {"event_type": event_type, **data},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    async def _create_event(self, asset_id, payload, event_type):
        require(self.request, "equipment.meters.record")
        await self._begin_serialized_write()
        asset = await self._asset(asset_id, "equipment.meters.record")
        self._validate_meter_type(asset, payload)
        payload_hash = self._payload_hash(event_type, payload)
        existing = (await self.session.execute(text(
            "SELECT * FROM eq_meter_events WHERE organization_id=:org AND idempotency_key=:key"
        ), {"org": asset["organization_id"], "key": payload.idempotency_key})).mappings().first()
        if existing:
            if existing["payload_hash"] != payload_hash:
                raise HTTPException(409, "Meter idempotency key was already used for a different event")
            return {**dict(existing), "idempotent_replay": True}
        operation_lock = await self.session.scalar(text(
            "SELECT 1 FROM eq_operation_logs WHERE organization_id=:org AND asset_id=:asset "
            "AND status='running' "
            "UNION ALL SELECT 1 FROM eq_meter_events WHERE organization_id=:org AND asset_id=:asset "
            "AND status='pending' AND operation_log_id IS NOT NULL LIMIT 1"
        ), {"org": asset["organization_id"], "asset": asset["id"]})
        if operation_lock:
            raise HTTPException(409, "Meter events are locked by an active or unapproved operation")
        event_at = _event_time(payload.event_at)
        self._validate_event_time(asset, event_at)

        base_latest = asset["meter_latest"]
        base_normalized = asset["meter_normalized_latest"]
        current_offset = self._base_offset(asset)
        generation = asset["meter_generation"]
        identifier, now = uuid4().hex, _now()
        record = {
            "id": identifier,
            "organization_id": asset["organization_id"],
            "asset_id": asset["id"],
            "event_code": "EMO-ME-" + identifier[:12].upper(),
            "event_type": event_type,
            "status": "pending",
            "event_at": event_at,
            "meter_type_snapshot": asset["meter_type_locked"],
            "meter_unit_snapshot": asset["meter_unit_locked"],
            "generation_before": generation,
            "generation_after": generation,
            "base_meter_latest": base_latest,
            "base_meter_normalized_latest": base_normalized,
            "reading_value": None,
            "old_final_reading": None,
            "new_initial_reading": None,
            "correction_of_event_id": None,
            "correction_delta": None,
            "reason_code": None,
            "evidence_ref": None,
            "idempotency_key": payload.idempotency_key,
            "payload_hash": payload_hash,
            "created_at": now,
            "created_by": self.actor,
        }

        if event_type == "reading":
            value = payload.reading_value
            if base_latest is not None and value < _decimal(base_latest):
                raise HTTPException(409, "Meter reading cannot decrease; record a documented correction or replacement")
            record["reading_value"] = _decimal_text(value)
        elif event_type == "replacement":
            if base_latest is None or base_normalized is None:
                raise HTTPException(409, "A meter without a baseline cannot be replaced")
            old_final = payload.old_final_reading
            new_initial = payload.new_initial_reading
            if old_final < _decimal(base_latest):
                raise HTTPException(409, "Old meter final reading cannot be below the latest approved reading")
            record.update({
                "generation_after": generation + 1,
                "old_final_reading": _decimal_text(old_final),
                "new_initial_reading": _decimal_text(new_initial),
                "reason_code": payload.reason_code,
                "evidence_ref": payload.evidence_ref,
            })
        else:
            target = (await self.session.execute(text(
                "SELECT * FROM eq_meter_events WHERE id=:id AND organization_id=:org "
                "AND asset_id=:asset AND event_type='reading' AND status='approved'"
            ), {
                "id": _hex(payload.correction_of_event_id),
                "org": asset["organization_id"],
                "asset": asset["id"],
            })).mappings().first()
            if not target:
                raise HTTPException(422, "Correction must reference an approved reading for this asset")
            previous_correction = await self.session.scalar(text(
                "SELECT reading_value FROM eq_meter_events WHERE correction_of_event_id=:target "
                "AND status='approved' ORDER BY approved_at DESC,id DESC LIMIT 1"
            ), {"target": target["id"]})
            previous_value = _decimal(
                previous_correction if previous_correction is not None else target["reading_value"]
            )
            generation = target["generation_before"]
            prior = (await self.session.execute(text(
                "SELECT e.event_at,CASE WHEN e.event_type='reading' THEN COALESCE(("
                "SELECT c.reading_value FROM eq_meter_events c WHERE c.correction_of_event_id=e.id "
                "AND c.status='approved' ORDER BY c.approved_at DESC,c.id DESC LIMIT 1),e.reading_value) "
                "ELSE e.new_initial_reading END AS reading_value "
                "FROM eq_meter_events e WHERE e.organization_id=:org AND e.asset_id=:asset "
                "AND e.status='approved' AND e.event_at<:event_at AND "
                "((e.event_type='reading' AND e.generation_before=:generation) OR "
                "(e.event_type='replacement' AND e.generation_after=:generation)) "
                "ORDER BY e.event_at DESC,e.id DESC LIMIT 1"
            ), {
                "org": asset["organization_id"], "asset": asset["id"],
                "event_at": target["event_at"], "generation": generation,
            })).mappings().first()
            following = (await self.session.execute(text(
                "SELECT e.event_at,CASE WHEN e.event_type='reading' THEN COALESCE(("
                "SELECT c.reading_value FROM eq_meter_events c WHERE c.correction_of_event_id=e.id "
                "AND c.status='approved' ORDER BY c.approved_at DESC,c.id DESC LIMIT 1),e.reading_value) "
                "ELSE e.old_final_reading END AS reading_value "
                "FROM eq_meter_events e WHERE e.organization_id=:org AND e.asset_id=:asset "
                "AND e.status='approved' AND e.event_at>:event_at AND "
                "((e.event_type='reading' AND e.generation_before=:generation) OR "
                "(e.event_type='replacement' AND e.generation_before=:generation)) "
                "ORDER BY e.event_at,e.id LIMIT 1"
            ), {
                "org": asset["organization_id"], "asset": asset["id"],
                "event_at": target["event_at"], "generation": generation,
            })).mappings().first()
            if prior and payload.corrected_reading < _decimal(prior["reading_value"]):
                raise HTTPException(409, "Corrected reading is below the previous generation reading")
            if following and payload.corrected_reading > _decimal(following["reading_value"]):
                raise HTTPException(409, "Corrected reading exceeds the following generation reading")
            delta = payload.corrected_reading - previous_value
            adjusted_latest = _decimal(base_normalized or base_latest or "0") + delta
            if adjusted_latest < 0 or (base_latest is not None and adjusted_latest < _decimal(base_latest)):
                raise HTTPException(409, "Correction would produce an invalid cumulative meter value")
            record.update({
                "reading_value": _decimal_text(payload.corrected_reading),
                "correction_of_event_id": _hex(payload.correction_of_event_id),
                "correction_delta": _decimal_text(delta),
                "reason_code": payload.reason_code,
                "evidence_ref": payload.evidence_ref,
            })

        record.update({
            "base_meter_latest": base_latest,
            "base_meter_normalized_latest": base_normalized,
        })
        try:
            await self.session.execute(text(
                "INSERT INTO eq_meter_events(id,organization_id,asset_id,event_code,event_type,status,event_at,"
                "meter_type_snapshot,meter_unit_snapshot,generation_before,generation_after,base_meter_latest,"
                "base_meter_normalized_latest,reading_value,old_final_reading,new_initial_reading,"
                "correction_of_event_id,correction_delta,reason_code,evidence_ref,idempotency_key,payload_hash,"
                "created_at,created_by) VALUES(:id,:organization_id,:asset_id,:event_code,:event_type,:status,"
                ":event_at,:meter_type_snapshot,:meter_unit_snapshot,:generation_before,:generation_after,"
                ":base_meter_latest,:base_meter_normalized_latest,:reading_value,:old_final_reading,"
                ":new_initial_reading,:correction_of_event_id,:correction_delta,:reason_code,:evidence_ref,"
                ":idempotency_key,:payload_hash,:created_at,:created_by)"
            ), record)
        except IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise HTTPException(409, "Meter event key or generation already exists") from None
            raise
        self.request.state.audit_details = {
            "entity_type": "equipment.meter_event",
            "entity_id": identifier,
            "new": {
                "event_type": event_type,
                "event_at": event_at,
                "meter_type": record["meter_type_snapshot"],
                "meter_unit": record["meter_unit_snapshot"],
                "generation": generation,
                "status": "pending",
            },
            "summary": "Equipment meter event submitted for independent approval",
        }
        return {**record, "idempotent_replay": False}

    async def record_reading(self, asset_id, payload):
        return await self._create_event(asset_id, payload, "reading")

    async def record_replacement(self, asset_id, payload):
        return await self._create_event(asset_id, payload, "replacement")

    async def record_correction(self, asset_id, payload):
        return await self._create_event(asset_id, payload, "correction")

    async def list_events(self, asset_id):
        require(self.request, "equipment.meters.view")
        asset = await self._asset(asset_id, "equipment.meters.view")
        rows = (await self.session.execute(text(
            "SELECT * FROM eq_meter_events WHERE organization_id=:org AND asset_id=:asset "
            "ORDER BY event_at,id LIMIT 500"
        ), {"org": asset["organization_id"], "asset": asset["id"]})).mappings().all()
        return {"items": [dict(row) for row in rows]}

    async def approve_event(self, event_id):
        require(self.request, "equipment.meters.approve")
        await self._begin_serialized_write()
        event = (await self.session.execute(text(
            "SELECT * FROM eq_meter_events WHERE id=:id"
        ), {"id": _hex(event_id)})).mappings().first()
        if event is None:
            raise HTTPException(404, "Meter event unavailable")
        await self.registry._visible_org(event["organization_id"], "equipment.meters.approve")
        if event["status"] != "pending":
            raise HTTPException(409, "Only a pending meter event can be approved")
        if event["created_by"] == self.actor:
            raise HTTPException(409, "Meter event approval must be performed by a different user")
        asset = await self._asset(UUID(event["asset_id"]), "equipment.meters.approve")
        if (
            asset["meter_generation"] != event["generation_before"]
            or asset["meter_latest"] != event["base_meter_latest"]
            or asset["meter_normalized_latest"] != event["base_meter_normalized_latest"]
            or asset["meter_type_locked"] != event["meter_type_snapshot"]
            or asset["meter_unit_locked"] != event["meter_unit_snapshot"]
        ):
            raise HTTPException(409, "Meter event is stale; submit a new event against the current meter state")
        current_latest = _decimal(asset["meter_latest"]) if asset["meter_latest"] is not None else None
        current_normalized = (
            _decimal(asset["meter_normalized_latest"])
            if asset["meter_normalized_latest"] is not None else current_latest
        )
        offset = self._base_offset(asset)
        update = {
            "generation": asset["meter_generation"],
            "latest": asset["meter_latest"],
            "normalized": asset["meter_normalized_latest"],
        }
        if event["event_type"] == "reading":
            reading = _decimal(event["reading_value"])
            if current_latest is not None and reading < current_latest:
                raise HTTPException(409, "Meter reading cannot decrease")
            update.update({
                "latest": _decimal_text(reading),
                "normalized": _decimal_text(reading + offset),
            })
        elif event["event_type"] == "replacement":
            old_final = _decimal(event["old_final_reading"])
            new_initial = _decimal(event["new_initial_reading"])
            if current_latest is None or current_normalized is None or old_final < current_latest:
                raise HTTPException(409, "Replacement no longer matches the current approved meter")
            normalized_final = old_final + offset
            update.update({
                "generation": event["generation_after"],
                "latest": _decimal_text(new_initial),
                "normalized": _decimal_text(normalized_final),
            })
        else:
            delta = _decimal(event["correction_delta"])
            corrected_total = (current_normalized or Decimal(0)) + delta
            if corrected_total < 0 or (current_latest is not None and corrected_total < current_latest):
                raise HTTPException(409, "Correction would produce an invalid cumulative meter value")
            update["normalized"] = _decimal_text(corrected_total)

        now = _now()
        await self.session.execute(text(
            "UPDATE eq_assets SET meter_latest=:latest,meter_normalized_latest=:normalized,"
            "meter_generation=:generation,meter_last_at=:event_at,updated_at=:now,updated_by=:actor,"
            "version=version+1 WHERE id=:asset AND organization_id=:org"
        ), {
            **update,
            "event_at": event["event_at"],
            "now": now,
            "actor": self.actor,
            "asset": asset["id"],
            "org": asset["organization_id"],
        })
        await self.session.execute(text(
            "UPDATE eq_meter_events SET status='approved',approved_at=:now,approved_by=:actor "
            "WHERE id=:id AND status='pending'"
        ), {"now": now, "actor": self.actor, "id": event["id"]})
        self.request.state.audit_details = {
            "entity_type": "equipment.meter_event",
            "entity_id": event["id"],
            "old": {"status": "pending", "meter_latest": current_latest,
                    "meter_normalized_latest": current_normalized,
                    "meter_generation": asset["meter_generation"]},
            "new": {"status": "approved", "meter_latest": update["latest"],
                    "meter_normalized_latest": update["normalized"],
                    "meter_generation": update["generation"]},
            "reference": {"event_code": event["event_code"], "event_type": event["event_type"]},
            "summary": "Equipment meter event independently approved and applied",
        }
        return {"id": event["id"], "status": "approved", **update, "approved_at": now,
                "approved_by": self.actor}
