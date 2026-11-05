"""Assignment, inspection, maintenance-block, and readiness operations."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.access import require
from modules.module_hr.application.operator_qualification_service import OperatorQualificationService
from .registry_service import EquipmentRegistryService, _hex, _now


class EquipmentSafetyService:
    def __init__(self, session, request):
        self.session = session
        self.request = request
        self.registry = EquipmentRegistryService(session, request)

    @property
    def actor(self):
        return self.request.state.user_id.hex

    async def _begin_serialized_write(self):
        if self.session.bind.dialect.name != "sqlite":
            raise HTTPException(503, "EMO serialized workflow is supported only on the configured SQLite Core database")
        await self.session.execute(text("BEGIN IMMEDIATE"))

    async def _asset(self, asset_id, permission):
        row = (await self.session.execute(
            text(
                "SELECT id,organization_id,category_id,lifecycle_status,technical_status,current_location "
                "FROM eq_assets WHERE id=:id AND deleted_at IS NULL"
            ),
            {"id": _hex(asset_id)},
        )).mappings().first()
        if not row:
            raise HTTPException(404, "Equipment asset unavailable")
        await self.registry._visible_org(row["organization_id"], permission)
        return row

    async def _entity(self, entity_id, organization_id):
        found = await self.session.scalar(
            text(
                "WITH RECURSIVE allowed_units(id) AS ("
                " SELECT id FROM organizations WHERE id=:org AND is_active=1"
                " UNION SELECT child.id FROM organizations child"
                " JOIN allowed_units parent ON child.parent_id=parent.id WHERE child.is_active=1"
                ") SELECT 1 FROM allowed_units WHERE id=:entity"
            ),
            {"org": organization_id, "entity": _hex(entity_id)},
        )
        if not found:
            raise HTTPException(422, "beneficiary_entity_id must be an active descendant of the equipment organization")

    async def _require_operator_qualified(self, employee_id, organization_id, category_id, start_at, end_at):
        category_code = await self.session.scalar(text(
            "SELECT category_code FROM eq_categories "
            "WHERE id=:category AND organization_id=:org AND is_active=1 AND deleted_at IS NULL"
        ), {"category": category_id, "org": organization_id})
        if not category_code:
            raise HTTPException(422, "Equipment category is unavailable for operator qualification")
        checks = (
            start_at.date(),
            (end_at - timedelta(microseconds=1)).date(),
        )
        for effective_date in checks:
            result = await OperatorQualificationService.eligibility(
                self.session, employee_id, organization_id, category_code, effective_date
            )
            if not result["eligible"]:
                raise HTTPException(422, result["reason"])

    async def create_request(self, payload, organization_id=None):
        require(self.request, "equipment.requests.create")
        org = await self.registry._organization(
            organization_id, "equipment.requests.create", create=True
        )
        await self._entity(payload.requested_entity_id, org)
        category = await self.session.scalar(
            text(
                "SELECT 1 FROM eq_categories WHERE id=:category AND organization_id=:org "
                "AND is_active=1 AND deleted_at IS NULL"
            ),
            {"category": _hex(payload.category_id), "org": org},
        )
        if not category:
            raise HTTPException(422, "category_id must reference an active category in this organization")
        values = payload.model_dump(mode="json")
        identifier, now = uuid4().hex, _now()
        record = {
            "id": identifier, "organization_id": org,
            "request_code": "EMO-R-" + identifier[:12].upper(),
            "requested_entity_id": _hex(payload.requested_entity_id),
            "category_id": _hex(payload.category_id), "required_quantity": payload.required_quantity,
            "required_start": payload.required_start.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "required_end": payload.required_end.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "required_specs": json.dumps(values["required_specs"], ensure_ascii=False, separators=(",", ":")),
            "target_location": payload.target_location, "purpose": payload.purpose,
            "priority": payload.priority, "status": "submitted",
            "requested_by": self.actor, "approved_by": None, "decision_at": None,
            "decided_by": None, "decision_reason": None, "created_at": now, "updated_at": now,
            "updated_by": self.actor, "version": 1,
        }
        await self.session.execute(
            text(
                "INSERT INTO eq_requests(id,organization_id,request_code,requested_entity_id,category_id,"
                "required_quantity,required_start,required_end,required_specs,target_location,purpose,priority,"
                "status,requested_by,approved_by,decided_by,decision_at,decision_reason,created_at,updated_at,updated_by,"
                "version) VALUES(:id,:organization_id,:request_code,:requested_entity_id,:category_id,"
                ":required_quantity,:required_start,:required_end,:required_specs,:target_location,:purpose,"
                ":priority,:status,:requested_by,:approved_by,:decided_by,:decision_at,:decision_reason,:created_at,"
                ":updated_at,:updated_by,:version)"
            ),
            record,
        )
        self._audit("equipment.request", identifier, {"status": "submitted", "request_code": record["request_code"]})
        return {**record, "required_specs": values["required_specs"]}

    async def list_requests(self, organization_id=None, status=None):
        require(self.request, "equipment.requests.view")
        org = await self.registry._organization(organization_id, "equipment.requests.view")
        query = "SELECT * FROM eq_requests WHERE organization_id=:org"
        params = {"org": org}
        if status:
            if status not in ("submitted", "approved", "partially_fulfilled", "fulfilled", "rejected", "cancelled"):
                raise HTTPException(422, "Invalid request status filter")
            query += " AND status=:status"
            params["status"] = status
        query += " ORDER BY created_at DESC,request_code LIMIT 200"
        rows = (await self.session.execute(text(query), params)).mappings().all()
        return {
            "items": [
                {**dict(row), "required_specs": json.loads(row["required_specs"])}
                for row in rows
            ]
        }

    async def decide_request(self, request_id, decision, reason=""):
        permission = f"equipment.requests.{decision}"
        require(self.request, permission)
        await self._begin_serialized_write()
        row = (await self.session.execute(
            text("SELECT * FROM eq_requests WHERE id=:id"),
            {"id": _hex(request_id)},
        )).mappings().first()
        if not row:
            raise HTTPException(404, "Equipment request unavailable")
        await self.registry._visible_org(row["organization_id"], "equipment.requests.view")
        if row["status"] != "submitted":
            raise HTTPException(409, "Only a submitted request can be decided")
        if decision == "reject" and not reason.strip():
            raise HTTPException(422, "A reason is required to reject an equipment request")
        now = _now()
        status = "approved" if decision == "approve" else "rejected"
        await self.session.execute(
            text(
                "UPDATE eq_requests SET status=:status,approved_by=:approved_by,decided_by=:actor,decision_at=:now,"
                "decision_reason=:reason,updated_at=:now,updated_by=:actor,version=version+1 "
                "WHERE id=:id AND organization_id=:org AND status='submitted'"
            ),
            {
                "status": status, "actor": self.actor,
                "approved_by": self.actor if decision == "approve" else None, "now": now,
                "reason": reason.strip() or None, "id": row["id"], "org": row["organization_id"],
            },
        )
        self._audit("equipment.request", row["id"], {"status": status})
        return {
            **dict(row), "status": status,
            "approved_by": self.actor if decision == "approve" else None,
            "decided_by": self.actor, "decision_at": now,
            "decision_reason": reason.strip() or None, "updated_at": now, "updated_by": self.actor,
            "version": row["version"] + 1,
        }

    async def create_assignment(self, payload):
        require(self.request, "equipment.assignments.create")
        await self._begin_serialized_write()
        asset = await self._asset(payload.asset_id, "equipment.assignments.view")
        if asset["lifecycle_status"] != "in_service":
            raise HTTPException(409, "Asset lifecycle does not allow assignment")
        await self._entity(payload.beneficiary_entity_id, asset["organization_id"])
        operator_id = _hex(payload.operator_employee_id)
        if operator_id:
            await self._require_operator_qualified(
                operator_id, asset["organization_id"], asset["category_id"],
                payload.planned_start_at, payload.planned_end_at,
            )

        values = payload.model_dump(mode="json")
        digest = hashlib.sha256(
            json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        existing = (await self.session.execute(
            text(
                "SELECT * FROM eq_assignments WHERE organization_id=:org AND idempotency_key=:key"
            ),
            {"org": asset["organization_id"], "key": payload.idempotency_key},
        )).mappings().first()
        if existing:
            if existing["payload_hash"] != digest:
                raise HTTPException(409, "Idempotency key was already used for a different assignment")
            return {**dict(existing), "idempotent_replay": True}

        request = None
        request_id = _hex(payload.request_id)
        if request_id:
            request = (await self.session.execute(
                text(
                    "SELECT * FROM eq_requests WHERE id=:id AND organization_id=:org"
                ),
                {"id": request_id, "org": asset["organization_id"]},
            )).mappings().first()
            if not request or request["status"] not in ("approved", "partially_fulfilled"):
                raise HTTPException(409, "Assignment requires an approved request in this organization")
            if request["category_id"] != asset["category_id"]:
                raise HTTPException(422, "Asset category does not fulfill this request")
            if request["requested_entity_id"] != _hex(payload.beneficiary_entity_id):
                raise HTTPException(422, "Assignment beneficiary must match the request")
            if (
                values["planned_start_at"] < request["required_start"]
                or values["planned_end_at"] > request["required_end"]
            ):
                raise HTTPException(422, "Assignment period must be within the approved request period")

        identifier, now = uuid4().hex, _now()
        record = {
            "id": identifier, "organization_id": asset["organization_id"], "asset_id": _hex(payload.asset_id),
            "request_id": request_id,
            "operator_employee_id": operator_id,
            "beneficiary_entity_id": _hex(payload.beneficiary_entity_id), "purpose": payload.purpose,
            "planned_start_at": payload.planned_start_at.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "planned_end_at": payload.planned_end_at.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "status": "draft", "idempotency_key": payload.idempotency_key, "payload_hash": digest,
            "created_at": now, "updated_at": now, "created_by": self.actor, "updated_by": self.actor, "version": 1,
        }
        try:
            await self.session.execute(
                text(
                    "INSERT INTO eq_assignments(id,organization_id,asset_id,request_id,operator_employee_id,"
                    "beneficiary_entity_id,purpose,"
                    "planned_start_at,planned_end_at,status,idempotency_key,payload_hash,created_at,updated_at,"
                    "created_by,updated_by,version) VALUES(:id,:organization_id,:asset_id,:request_id,"
                    ":operator_employee_id,:beneficiary_entity_id,"
                    ":purpose,:planned_start_at,:planned_end_at,:status,:idempotency_key,:payload_hash,"
                    ":created_at,:updated_at,:created_by,:updated_by,:version)"
                ),
                record,
            )
        except IntegrityError:
            raise HTTPException(409, "Assignment could not be created due to a duplicate or invalid reference") from None
        self._audit("equipment.assignment", identifier, {"status": "draft"})
        return {**record, "idempotent_replay": False}

    async def approve_assignment(self, assignment_id):
        require(self.request, "equipment.assignments.approve")
        await self._begin_serialized_write()
        row = (await self.session.execute(
            text("SELECT * FROM eq_assignments WHERE id=:id"),
            {"id": _hex(assignment_id)},
        )).mappings().first()
        if not row:
            raise HTTPException(404, "Equipment assignment unavailable")
        await self.registry._visible_org(row["organization_id"], "equipment.assignments.view")
        if row["status"] != "draft":
            raise HTTPException(409, "Only a draft assignment can be approved")
        asset = (await self.session.execute(
            text(
                "SELECT lifecycle_status,technical_status FROM eq_assets WHERE id=:id AND organization_id=:org "
                "AND deleted_at IS NULL"
            ),
            {"id": row["asset_id"], "org": row["organization_id"]},
        )).mappings().first()
        if (
            not asset or asset["lifecycle_status"] != "in_service"
            or asset["technical_status"] in ("unsafe", "maintenance", "out_of_service")
        ):
            raise HTTPException(409, "Asset lifecycle does not allow assignment approval")
        if row["operator_employee_id"]:
            start_at = datetime.fromisoformat(row["planned_start_at"].replace("Z", "+00:00"))
            end_at = datetime.fromisoformat(row["planned_end_at"].replace("Z", "+00:00"))
            category_id = await self.session.scalar(text(
                "SELECT category_id FROM eq_assets WHERE id=:asset AND organization_id=:org"
            ), {"asset": row["asset_id"], "org": row["organization_id"]})
            await self._require_operator_qualified(
                row["operator_employee_id"], row["organization_id"], category_id, start_at, end_at
            )
        blockers = await self._active_blockers(row["organization_id"], row["asset_id"])
        if blockers:
            raise HTTPException(409, "Active safety blockers prevent assignment approval")
        moving = await self.session.scalar(
            text(
                "SELECT 1 FROM eq_movements WHERE organization_id=:org AND asset_id=:asset "
                "AND status='dispatched' LIMIT 1"
            ),
            {"org": row["organization_id"], "asset": row["asset_id"]},
        )
        if moving:
            raise HTTPException(409, "A dispatched movement prevents assignment approval")
        outstanding = await self.session.scalar(
            text(
                "SELECT 1 FROM eq_assignments WHERE organization_id=:org AND asset_id=:asset "
                "AND id<>:id AND status IN ('dispatched','active','suspended') LIMIT 1"
            ),
            {"org": row["organization_id"], "asset": row["asset_id"], "id": row["id"]},
        )
        overlap = await self.session.scalar(
            text(
                "SELECT 1 FROM eq_assignments WHERE organization_id=:org AND asset_id=:asset AND id<>:id "
                "AND status IN ('approved','dispatched','active','suspended') "
                "AND planned_start_at<:end_at AND :start_at<planned_end_at LIMIT 1"
            ),
            {
                "org": row["organization_id"], "asset": row["asset_id"], "id": row["id"],
                "start_at": row["planned_start_at"], "end_at": row["planned_end_at"],
            },
        )
        if outstanding or overlap:
            raise HTTPException(409, "Assignment period conflicts with an existing allocation")
        operator_overlap = None
        if row["operator_employee_id"]:
            operator_overlap = await self.session.scalar(text(
                "SELECT 1 FROM eq_assignments WHERE organization_id=:org "
                "AND operator_employee_id=:operator AND id<>:id "
                "AND status IN ('approved','dispatched','active','suspended') "
                "AND planned_start_at<:end_at AND :start_at<planned_end_at LIMIT 1"
            ), {
                "org": row["organization_id"], "operator": row["operator_employee_id"],
                "id": row["id"], "start_at": row["planned_start_at"], "end_at": row["planned_end_at"],
            })
        if operator_overlap:
            raise HTTPException(409, "Operator assignment period conflicts with an existing allocation")
        request = None
        fulfilling_count = 0
        if row["request_id"]:
            request = (await self.session.execute(
                text(
                    "SELECT * FROM eq_requests WHERE id=:id AND organization_id=:org"
                ),
                {"id": row["request_id"], "org": row["organization_id"]},
            )).mappings().first()
            if not request or request["status"] not in ("approved", "partially_fulfilled"):
                raise HTTPException(409, "Linked request is no longer open for allocation")
            fulfilling_count = await self.session.scalar(
                text(
                    "SELECT COUNT(*) FROM eq_assignments WHERE organization_id=:org AND request_id=:request "
                    "AND status IN ('approved','dispatched','active','suspended','completed')"
                ),
                {"org": row["organization_id"], "request": row["request_id"]},
            )
            if fulfilling_count >= request["required_quantity"]:
                raise HTTPException(409, "Request quantity is already fulfilled")
        now = _now()
        await self.session.execute(
            text(
                "UPDATE eq_assignments SET status='approved',updated_at=:now,updated_by=:actor,version=version+1 "
                "WHERE id=:id AND organization_id=:org AND status='draft'"
            ),
            {"now": now, "actor": self.actor, "id": row["id"], "org": row["organization_id"]},
        )
        if request:
            next_request_status = (
                "fulfilled" if fulfilling_count + 1 >= request["required_quantity"] else "partially_fulfilled"
            )
            await self.session.execute(
                text(
                    "UPDATE eq_requests SET status=:status,updated_at=:now,updated_by=:actor,"
                    "version=version+1 WHERE id=:id AND organization_id=:org"
                ),
                {
                    "status": next_request_status, "now": now, "actor": self.actor,
                    "id": request["id"], "org": row["organization_id"],
                },
            )
        self._audit("equipment.assignment", row["id"], {"status": "approved"})
        return {**dict(row), "status": "approved", "updated_at": now, "updated_by": self.actor,
                "version": row["version"] + 1}

    async def list_assignments(self, asset_id):
        require(self.request, "equipment.assignments.view")
        asset = await self._asset(asset_id, "equipment.assignments.view")
        rows = (await self.session.execute(
            text(
                "SELECT * FROM eq_assignments WHERE organization_id=:org AND asset_id=:asset "
                "ORDER BY planned_start_at DESC,id"
            ),
            {"org": asset["organization_id"], "asset": _hex(asset_id)},
        )).mappings().all()
        return {"items": [dict(row) for row in rows]}

    async def list_all_assignments(self, organization_id=None):
        permission = "equipment.assignments.view"
        require(self.request, permission)
        organization = await self.registry._organization(organization_id, permission)
        rows = (await self.session.execute(text(
            "SELECT a.*,e.asset_code,e.asset_name FROM eq_assignments a "
            "JOIN eq_assets e ON e.id=a.asset_id AND e.organization_id=a.organization_id "
            "WHERE a.organization_id=:org ORDER BY a.planned_start_at DESC,a.id LIMIT 500"
        ), {"org": organization})).mappings().all()
        return {"items": [dict(row) for row in rows]}

    async def create_movement(self, payload):
        require(self.request, "equipment.movements.create")
        await self._begin_serialized_write()
        asset = await self._asset(payload.asset_id, "equipment.movements.view")
        if asset["lifecycle_status"] in ("retired", "disposed"):
            raise HTTPException(409, "Retired or disposed equipment cannot be moved")
        await self._entity(payload.from_entity_id, asset["organization_id"])
        await self._entity(payload.to_entity_id, asset["organization_id"])
        await self._ensure_not_assigned(asset["organization_id"], asset["id"])
        values = payload.model_dump(mode="json")
        digest = hashlib.sha256(
            json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        existing = (await self.session.execute(
            text(
                "SELECT * FROM eq_movements WHERE organization_id=:org AND idempotency_key=:key"
            ),
            {"org": asset["organization_id"], "key": payload.idempotency_key},
        )).mappings().first()
        if existing:
            if existing["payload_hash"] != digest:
                raise HTTPException(409, "Idempotency key was already used for a different movement")
            return {**dict(existing), "idempotent_replay": True}
        if asset["current_location"] and payload.from_location and payload.from_location != asset["current_location"]:
            raise HTTPException(409, "Movement source location does not match the current asset location")
        active_movement = await self.session.scalar(
            text(
                "SELECT 1 FROM eq_movements WHERE organization_id=:org AND asset_id=:asset "
                "AND status IN ('draft','dispatched') LIMIT 1"
            ),
            {"org": asset["organization_id"], "asset": asset["id"]},
        )
        if active_movement:
            raise HTTPException(409, "An unfinished movement already exists for this asset")
        identifier, now = uuid4().hex, _now()
        record = {
            "id": identifier, "organization_id": asset["organization_id"], "asset_id": asset["id"],
            "movement_code": "EMO-MV-" + identifier[:12].upper(),
            "from_entity_id": _hex(payload.from_entity_id), "to_entity_id": _hex(payload.to_entity_id),
            "from_location": payload.from_location or asset["current_location"] or "",
            "to_location": payload.to_location,
            "movement_reason": payload.movement_reason, "status": "draft",
            "idempotency_key": payload.idempotency_key, "payload_hash": digest,
            "dispatched_at": None, "handed_over_by": None, "received_at": None, "received_by": None,
            "condition_at_receipt": None, "created_at": now, "updated_at": now,
            "created_by": self.actor, "updated_by": self.actor, "version": 1,
        }
        try:
            await self.session.execute(
                text(
                    "INSERT INTO eq_movements(id,organization_id,asset_id,movement_code,from_entity_id,to_entity_id,"
                    "from_location,to_location,movement_reason,status,idempotency_key,payload_hash,dispatched_at,"
                    "handed_over_by,received_at,received_by,condition_at_receipt,created_at,updated_at,created_by,"
                    "updated_by,version) VALUES(:id,:organization_id,:asset_id,:movement_code,:from_entity_id,"
                    ":to_entity_id,:from_location,:to_location,:movement_reason,:status,:idempotency_key,"
                    ":payload_hash,:dispatched_at,:handed_over_by,:received_at,:received_by,:condition_at_receipt,"
                    ":created_at,:updated_at,:created_by,:updated_by,:version)"
                ),
                record,
            )
        except IntegrityError:
            raise HTTPException(409, "An unfinished movement or duplicate movement key exists") from None
        self._audit("equipment.movement", identifier, {"status": "draft"})
        return {**record, "idempotent_replay": False}

    async def dispatch_movement(self, movement_id):
        require(self.request, "equipment.movements.dispatch")
        await self._begin_serialized_write()
        row = await self._movement(movement_id)
        if row["status"] != "draft":
            raise HTTPException(409, "Only a draft movement can be dispatched")
        await self._ensure_not_assigned(row["organization_id"], row["asset_id"])
        asset = (await self.session.execute(
            text(
                "SELECT lifecycle_status,current_location FROM eq_assets WHERE id=:id AND organization_id=:org "
                "AND deleted_at IS NULL"
            ),
            {"id": row["asset_id"], "org": row["organization_id"]},
        )).mappings().first()
        if not asset or asset["lifecycle_status"] in ("retired", "disposed"):
            raise HTTPException(409, "Asset lifecycle does not allow movement")
        if (asset["current_location"] or "") != row["from_location"]:
            raise HTTPException(409, "Asset location changed after the movement was created")
        now = _now()
        await self.session.execute(
            text(
                "UPDATE eq_movements SET status='dispatched',dispatched_at=:now,handed_over_by=:actor,"
                "updated_at=:now,updated_by=:actor,version=version+1 WHERE id=:id AND status='draft'"
            ),
            {"now": now, "actor": self.actor, "id": row["id"]},
        )
        self._audit("equipment.movement", row["id"], {"status": "dispatched"})
        return {**dict(row), "status": "dispatched", "dispatched_at": now, "handed_over_by": self.actor,
                "updated_at": now, "updated_by": self.actor, "version": row["version"] + 1}

    async def receive_movement(self, movement_id, payload):
        require(self.request, "equipment.movements.receive")
        await self._begin_serialized_write()
        row = await self._movement(movement_id)
        if row["status"] != "dispatched":
            raise HTTPException(409, "Only a dispatched movement can be received")
        if row["handed_over_by"] == self.actor:
            raise HTTPException(409, "Receipt must be confirmed by a different user than handover")
        now = _now()
        await self.session.execute(
            text(
                "UPDATE eq_movements SET status='received',received_at=:now,received_by=:actor,"
                "condition_at_receipt=:condition,updated_at=:now,updated_by=:actor,version=version+1 "
                "WHERE id=:id AND status='dispatched'"
            ),
            {
                "now": now, "actor": self.actor, "condition": payload.condition_at_receipt,
                "id": row["id"],
            },
        )
        await self.session.execute(
            text(
                "UPDATE eq_assets SET current_location=:location,updated_at=:now,updated_by=:actor,"
                "version=version+1 WHERE id=:asset AND organization_id=:org AND deleted_at IS NULL"
            ),
            {
                "location": row["to_location"], "now": now, "actor": self.actor,
                "asset": row["asset_id"], "org": row["organization_id"],
            },
        )
        self._audit("equipment.movement", row["id"], {
            "status": "received", "asset_id": row["asset_id"], "current_location": row["to_location"],
        })
        return {
            **dict(row), "status": "received", "received_at": now, "received_by": self.actor,
            "condition_at_receipt": payload.condition_at_receipt, "updated_at": now,
            "updated_by": self.actor, "version": row["version"] + 1,
        }

    async def cancel_movement(self, movement_id):
        require(self.request, "equipment.movements.cancel")
        await self._begin_serialized_write()
        row = await self._movement(movement_id)
        if row["status"] != "draft":
            raise HTTPException(409, "Only a draft movement can be cancelled")
        now = _now()
        await self.session.execute(
            text(
                "UPDATE eq_movements SET status='cancelled',updated_at=:now,updated_by=:actor,"
                "version=version+1 WHERE id=:id AND status='draft'"
            ),
            {"now": now, "actor": self.actor, "id": row["id"]},
        )
        self._audit("equipment.movement", row["id"], {"status": "cancelled"})
        return {**dict(row), "status": "cancelled", "updated_at": now, "updated_by": self.actor,
                "version": row["version"] + 1}

    async def list_movements(self, asset_id=None, organization_id=None, status=None):
        require(self.request, "equipment.movements.view")
        if asset_id:
            asset = await self._asset(asset_id, "equipment.movements.view")
            org = asset["organization_id"]
        else:
            org = await self.registry._organization(organization_id, "equipment.movements.view")
        query = "SELECT * FROM eq_movements WHERE organization_id=:org"
        params = {"org": org}
        if asset_id:
            query += " AND asset_id=:asset"
            params["asset"] = _hex(asset_id)
        if status:
            if status not in ("draft", "dispatched", "received", "cancelled"):
                raise HTTPException(422, "Invalid movement status filter")
            query += " AND status=:status"
            params["status"] = status
        query += " ORDER BY created_at DESC,movement_code LIMIT 200"
        rows = (await self.session.execute(text(query), params)).mappings().all()
        return {"items": [dict(row) for row in rows]}

    async def _movement(self, movement_id):
        row = (await self.session.execute(
            text("SELECT * FROM eq_movements WHERE id=:id"),
            {"id": _hex(movement_id)},
        )).mappings().first()
        if not row:
            raise HTTPException(404, "Equipment movement unavailable")
        await self.registry._visible_org(row["organization_id"], "equipment.movements.view")
        return row

    async def _ensure_not_assigned(self, organization_id, asset_id):
        active = await self.session.scalar(
            text(
                "SELECT 1 FROM eq_assignments WHERE organization_id=:org AND asset_id=:asset "
                "AND status IN ('approved','dispatched','active','suspended') LIMIT 1"
            ),
            {"org": organization_id, "asset": asset_id},
        )
        if active:
            raise HTTPException(409, "An approved or active assignment prevents equipment movement")

    async def create_inspection(self, payload):
        require(self.request, "equipment.inspections.record")
        asset = await self._asset(payload.asset_id, "equipment.inspections.view")
        if payload.assignment_id:
            assignment = (await self.session.execute(
                text(
                    "SELECT id,status,operator_employee_id FROM eq_assignments "
                    "WHERE id=:id AND organization_id=:org AND asset_id=:asset"
                ),
                {"id": _hex(payload.assignment_id), "org": asset["organization_id"], "asset": _hex(payload.asset_id)},
            )).mappings().first()
            if not assignment:
                raise HTTPException(422, "Inspection assignment must belong to this asset and organization")
            if payload.inspection_type == "pre_operation" and assignment["status"] != "approved":
                raise HTTPException(409, "Pre-operation inspection requires an approved assignment")
        elif payload.inspection_type == "pre_operation":
            raise HTTPException(422, "Pre-operation inspection requires an assignment")
        if len(json.dumps(payload.findings, ensure_ascii=False)) > 16000:
            raise HTTPException(422, "findings exceeds 16000 characters")

        identifier, now = uuid4().hex, _now()
        block_status = "active" if payload.result == "failed" and payload.critical_failure else "none"
        record = {
            "id": identifier, "organization_id": asset["organization_id"], "asset_id": _hex(payload.asset_id),
            "assignment_id": _hex(payload.assignment_id), "inspection_type": payload.inspection_type,
            "result": payload.result, "critical_failure": int(payload.critical_failure), "status": "submitted",
            "block_status": block_status,
            "block_reason_code": "CRITICAL_INSPECTION_FAILURE" if block_status == "active" else None,
            "checklist_version": payload.checklist_version,
            "findings": json.dumps(payload.findings, ensure_ascii=False, separators=(",", ":")),
            "meter_reading": str(payload.meter_reading) if payload.meter_reading is not None else None,
            "inspected_at": (payload.inspected_at or datetime.now(timezone.utc)).isoformat(
                timespec="microseconds"
            ).replace("+00:00", "Z"),
            "created_at": now, "updated_at": now, "created_by": self.actor, "updated_by": self.actor,
        }
        await self.session.execute(
            text(
                "INSERT INTO eq_inspections(id,organization_id,asset_id,assignment_id,inspection_type,result,"
                "critical_failure,status,block_status,block_reason_code,checklist_version,findings,meter_reading,"
                "inspected_at,created_at,updated_at,created_by,updated_by) VALUES(:id,:organization_id,:asset_id,"
                ":assignment_id,:inspection_type,:result,:critical_failure,:status,:block_status,"
                ":block_reason_code,:checklist_version,:findings,:meter_reading,:inspected_at,:created_at,"
                ":updated_at,:created_by,:updated_by)"
            ),
            record,
        )
        self._audit("equipment.inspection", identifier, {"result": payload.result, "block_status": block_status})
        return {**record, "findings": payload.findings, "verified_at": None, "verified_by": None, "version": 1}

    async def list_inspections(self, organization_id=None, asset_id=None, status=None):
        require(self.request, "equipment.inspections.view")
        if asset_id:
            asset = await self._asset(asset_id, "equipment.inspections.view")
            org = asset["organization_id"]
        else:
            org = await self.registry._organization(organization_id, "equipment.inspections.view")
        query = "SELECT * FROM eq_inspections WHERE organization_id=:org"
        params = {"org": org}
        if asset_id:
            query += " AND asset_id=:asset"
            params["asset"] = _hex(asset_id)
        if status:
            if status not in ("submitted", "verified"):
                raise HTTPException(422, "Invalid inspection status filter")
            query += " AND status=:status"
            params["status"] = status
        query += " ORDER BY inspected_at DESC,id LIMIT 200"
        rows = (await self.session.execute(text(query), params)).mappings().all()
        return {"items": [{**dict(row), "findings": json.loads(row["findings"])} for row in rows]}

    async def verify_inspection(self, inspection_id):
        require(self.request, "equipment.inspections.verify")
        row = (await self.session.execute(
            text("SELECT * FROM eq_inspections WHERE id=:id"),
            {"id": _hex(inspection_id)},
        )).mappings().first()
        if not row:
            raise HTTPException(404, "Equipment inspection unavailable")
        await self.registry._visible_org(row["organization_id"], "equipment.inspections.view")
        if row["status"] != "submitted":
            raise HTTPException(409, "Only a submitted inspection can be verified")
        if row["created_by"] == self.actor:
            raise HTTPException(409, "Inspection verification must be performed by a different user")
        now = _now()
        await self.session.execute(
            text(
                "UPDATE eq_inspections SET status='verified',verified_at=:now,verified_by=:actor,"
                "updated_at=:now,updated_by=:actor,version=version+1 WHERE id=:id AND status='submitted'"
            ),
            {"now": now, "actor": self.actor, "id": row["id"]},
        )
        self._audit("equipment.inspection", row["id"], {"status": "verified"})
        return {**dict(row), "status": "verified", "verified_at": now, "verified_by": self.actor,
                "updated_at": now, "updated_by": self.actor, "version": row["version"] + 1}

    async def create_maintenance_order(self, payload):
        require(self.request, "equipment.maintenance.create")
        asset = await self._asset(payload.asset_id, "equipment.maintenance.view")
        identifier, now = uuid4().hex, _now()
        record = {
            "id": identifier, "organization_id": asset["organization_id"], "asset_id": _hex(payload.asset_id),
            "order_code": "EMO-M-" + identifier[:12].upper(), "maintenance_type": payload.maintenance_type,
            "description": payload.description, "status": "open", "block_status": "active",
            "block_reason_code": "MAINTENANCE_ORDER_OPEN", "created_at": now, "updated_at": now,
            "created_by": self.actor, "updated_by": self.actor, "version": 1,
        }
        await self.session.execute(
            text(
                "INSERT INTO eq_maintenance_orders(id,organization_id,asset_id,order_code,maintenance_type,"
                "description,status,block_status,block_reason_code,created_at,updated_at,created_by,updated_by,"
                "version) VALUES(:id,:organization_id,:asset_id,:order_code,:maintenance_type,:description,"
                ":status,:block_status,:block_reason_code,:created_at,:updated_at,:created_by,:updated_by,:version)"
            ),
            record,
        )
        self._audit("equipment.maintenance_order", identifier, {"block_status": "active"})
        return record

    async def list_maintenance_orders(self, organization_id=None, asset_id=None, status=None):
        require(self.request, "equipment.maintenance.view")
        if asset_id:
            asset = await self._asset(asset_id, "equipment.maintenance.view")
            org = asset["organization_id"]
        else:
            org = await self.registry._organization(organization_id, "equipment.maintenance.view")
        query = "SELECT * FROM eq_maintenance_orders WHERE organization_id=:org"
        params = {"org": org}
        if asset_id:
            query += " AND asset_id=:asset"
            params["asset"] = _hex(asset_id)
        if status:
            if status not in ("open", "in_progress", "technically_completed", "verified_closed", "cancelled"):
                raise HTTPException(422, "Invalid maintenance status filter")
            query += " AND status=:status"
            params["status"] = status
        query += " ORDER BY created_at DESC,order_code LIMIT 200"
        rows = (await self.session.execute(text(query), params)).mappings().all()
        return {"items": [dict(row) for row in rows]}

    async def complete_maintenance(self, order_id, payload):
        require(self.request, "equipment.maintenance.execute")
        row = (await self.session.execute(
            text("SELECT * FROM eq_maintenance_orders WHERE id=:id"),
            {"id": _hex(order_id)},
        )).mappings().first()
        if not row:
            raise HTTPException(404, "Equipment maintenance order unavailable")
        await self.registry._visible_org(row["organization_id"], "equipment.maintenance.view")
        if row["status"] != "open" and row["status"] != "in_progress":
            raise HTTPException(409, "Only open or in-progress maintenance can be completed")
        now = _now()
        next_due_at = next_due_meter = None
        plan = None
        if row["plan_id"]:
            plan = (await self.session.execute(
                text("SELECT * FROM eq_maintenance_plans WHERE id=:id"),
                {"id": row["plan_id"]},
            )).mappings().first()
            if not plan:
                raise HTTPException(409, "Preventive maintenance plan is unavailable")
            next_due_at = row["plan_due_at"]
            if next_due_at and plan["interval_days"] is not None:
                due_at = datetime.fromisoformat(next_due_at.replace("Z", "+00:00"))
                next_due_at = (
                    due_at + timedelta(days=plan["interval_days"])
                ).isoformat(timespec="microseconds").replace("+00:00", "Z")
            next_due_meter = row["plan_due_meter"]
            if next_due_meter is not None and plan["interval_meter"] is not None:
                next_due_meter = format(
                    Decimal(next_due_meter) + Decimal(plan["interval_meter"]), "f"
                )
            await self.session.execute(
                text(
                    "UPDATE eq_maintenance_plans SET next_due_at=:next_due_at,"
                    "next_due_meter=:next_due_meter,updated_at=:now,updated_by=:actor,"
                    "version=version+1 WHERE id=:id"
                ),
                {
                    "next_due_at": next_due_at, "next_due_meter": next_due_meter,
                    "now": now, "actor": self.actor, "id": plan["id"],
                },
            )
        await self.session.execute(
            text(
                "UPDATE eq_maintenance_orders SET status='technically_completed',completion_notes=:notes,"
                "updated_at=:now,updated_by=:actor,version=version+1 WHERE id=:id"
            ),
            {"notes": payload.completion_notes, "now": now, "actor": self.actor, "id": row["id"]},
        )
        self._audit(
            "equipment.maintenance_order",
            row["id"],
            {
                "status": "technically_completed",
                "plan_id": row["plan_id"],
                "next_due_at": next_due_at,
                "next_due_meter": next_due_meter,
            },
        )
        return {**dict(row), "status": "technically_completed", "completion_notes": payload.completion_notes,
                "updated_at": now, "updated_by": self.actor, "version": row["version"] + 1}

    async def create_maintenance_plan(self, payload):
        require(self.request, "equipment.maintenance.create")
        await self._begin_serialized_write()
        asset = await self._asset(payload.asset_id, "equipment.maintenance.view")
        values = payload.model_dump(mode="json")
        payload_hash = hashlib.sha256(
            json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        existing = (await self.session.execute(
            text(
                "SELECT * FROM eq_maintenance_plans "
                "WHERE organization_id=:org AND idempotency_key=:key"
            ),
            {"org": asset["organization_id"], "key": payload.idempotency_key},
        )).mappings().first()
        if existing:
            if existing["payload_hash"] != payload_hash:
                raise HTTPException(409, "Maintenance plan idempotency key was used with a different payload")
            return {**dict(existing), "idempotent_replay": True}
        meter_type = meter_unit = None
        meter_generation = None
        if payload.interval_meter is not None:
            meter = (await self.session.execute(
                text(
                    "SELECT meter_type_locked,meter_unit_locked,meter_generation "
                    "FROM eq_assets WHERE id=:id AND organization_id=:org AND deleted_at IS NULL"
                ),
                {"id": _hex(payload.asset_id), "org": asset["organization_id"]},
            )).mappings().first()
            if not meter or meter["meter_type_locked"] in (None, "none"):
                raise HTTPException(422, "Meter-based maintenance requires a configured asset meter")
            meter_type = meter["meter_type_locked"]
            meter_unit = meter["meter_unit_locked"]
            meter_generation = meter["meter_generation"]
        identifier, now = uuid4().hex, _now()
        record = {
            "id": identifier,
            "organization_id": asset["organization_id"],
            "asset_id": _hex(payload.asset_id),
            "plan_code": "EMO-MP-" + identifier[:12].upper(),
            "description": payload.description,
            "interval_days": payload.interval_days,
            "interval_meter": str(payload.interval_meter) if payload.interval_meter is not None else None,
            "meter_type_snapshot": meter_type,
            "meter_unit_snapshot": meter_unit,
            "meter_generation_snapshot": meter_generation,
            "next_due_at": (
                payload.first_due_at.isoformat(timespec="microseconds").replace("+00:00", "Z")
                if payload.first_due_at else None
            ),
            "next_due_meter": str(payload.first_due_meter) if payload.first_due_meter is not None else None,
            "status": "active",
            "idempotency_key": payload.idempotency_key,
            "payload_hash": payload_hash,
            "created_at": now,
            "updated_at": now,
            "created_by": self.actor,
            "updated_by": self.actor,
            "version": 1,
        }
        await self.session.execute(
            text(
                "INSERT INTO eq_maintenance_plans(id,organization_id,asset_id,plan_code,description,"
                "interval_days,interval_meter,meter_type_snapshot,meter_unit_snapshot,"
                "meter_generation_snapshot,next_due_at,next_due_meter,status,idempotency_key,"
                "payload_hash,created_at,updated_at,created_by,updated_by,version) "
                "VALUES(:id,:organization_id,:asset_id,:plan_code,:description,:interval_days,"
                ":interval_meter,:meter_type_snapshot,:meter_unit_snapshot,:meter_generation_snapshot,"
                ":next_due_at,:next_due_meter,:status,:idempotency_key,:payload_hash,:created_at,"
                ":updated_at,:created_by,:updated_by,:version)"
            ),
            record,
        )
        self._audit("equipment.maintenance_plan", identifier, {"status": "active"})
        return record

    async def list_maintenance_plans(self, organization_id=None, asset_id=None, status=None):
        require(self.request, "equipment.maintenance.view")
        if asset_id:
            asset = await self._asset(asset_id, "equipment.maintenance.view")
            org = asset["organization_id"]
        else:
            org = await self.registry._organization(organization_id, "equipment.maintenance.view")
        query = "SELECT * FROM eq_maintenance_plans WHERE organization_id=:org"
        params = {"org": org}
        if asset_id:
            query += " AND asset_id=:asset"
            params["asset"] = _hex(asset_id)
        if status:
            if status not in ("active", "paused"):
                raise HTTPException(422, "Invalid maintenance plan status filter")
            query += " AND status=:status"
            params["status"] = status
        query += " ORDER BY plan_code LIMIT 200"
        rows = (await self.session.execute(text(query), params)).mappings().all()
        return {"items": [dict(row) for row in rows]}

    async def list_due_maintenance_plans(self, organization_id=None, asset_id=None):
        require(self.request, "equipment.maintenance.view")
        if asset_id:
            asset = await self._asset(asset_id, "equipment.maintenance.view")
            org = asset["organization_id"]
        else:
            org = await self.registry._organization(organization_id, "equipment.maintenance.view")
        query = (
            "SELECT p.*,a.meter_normalized_latest,a.meter_type_locked,a.meter_unit_locked "
            "FROM eq_maintenance_plans p JOIN eq_assets a "
            "ON a.organization_id=p.organization_id AND a.id=p.asset_id "
            "WHERE p.organization_id=:org AND p.status='active' AND a.deleted_at IS NULL"
        )
        params = {"org": org}
        if asset_id:
            query += " AND p.asset_id=:asset"
            params["asset"] = _hex(asset_id)
        rows = (await self.session.execute(text(query), params)).mappings().all()
        now = _now()
        due_items, blocked_items = [], []
        for row in rows:
            reasons, blocked_reasons = [], []
            if row["next_due_at"] and row["next_due_at"] <= now:
                reasons.append("calendar")
            if row["next_due_meter"] is not None:
                if (
                    row["meter_unit_locked"] != row["meter_unit_snapshot"]
                    or row["meter_type_locked"] != row["meter_type_snapshot"]
                ):
                    blocked_reasons.append("meter_contract_changed")
                elif (
                    row["meter_normalized_latest"] is not None
                    and Decimal(row["meter_normalized_latest"]) >= Decimal(row["next_due_meter"])
                ):
                    reasons.append("meter")
            if reasons:
                due_items.append(
                    {**dict(row), "due_reasons": reasons, "blocked_reasons": blocked_reasons}
                )
            elif blocked_reasons:
                blocked_items.append(
                    {**dict(row), "blocked_reasons": blocked_reasons}
                )
        return {"items": due_items, "blocked_items": blocked_items}

    async def generate_due_maintenance_order(self, plan_id):
        require(self.request, "equipment.maintenance.create")
        await self._begin_serialized_write()
        plan = (await self.session.execute(
            text("SELECT * FROM eq_maintenance_plans WHERE id=:id"),
            {"id": _hex(plan_id)},
        )).mappings().first()
        if not plan:
            raise HTTPException(404, "Preventive maintenance plan unavailable")
        await self.registry._visible_org(plan["organization_id"], "equipment.maintenance.view")
        if plan["status"] != "active":
            raise HTTPException(409, "Paused maintenance plans cannot generate orders")
        due = await self.list_due_maintenance_plans(asset_id=plan["asset_id"])
        due_plan = next((item for item in due["items"] if item["id"] == plan["id"]), None)
        if not due_plan:
            blocked_plan = next(
                (item for item in due["blocked_items"] if item["id"] == plan["id"]), None
            )
            if blocked_plan:
                raise HTTPException(409, "Preventive maintenance meter contract requires review")
            raise HTTPException(409, "Preventive maintenance plan is not due")
        cycle_key = f"date:{plan['next_due_at'] or '-'}|meter:{plan['next_due_meter'] or '-'}"
        existing = (await self.session.execute(
            text(
                "SELECT * FROM eq_maintenance_orders "
                "WHERE organization_id=:org AND plan_id=:plan AND plan_cycle_key=:cycle"
            ),
            {"org": plan["organization_id"], "plan": plan["id"], "cycle": cycle_key},
        )).mappings().first()
        if existing:
            return {**dict(existing), "idempotent_replay": True}
        identifier, now = uuid4().hex, _now()
        record = {
            "id": identifier,
            "organization_id": plan["organization_id"],
            "asset_id": plan["asset_id"],
            "order_code": "EMO-M-" + identifier[:12].upper(),
            "maintenance_type": "preventive",
            "description": plan["description"],
            "status": "open",
            "block_status": "active",
            "block_reason_code": "MAINTENANCE_ORDER_OPEN",
            "created_at": now,
            "updated_at": now,
            "created_by": self.actor,
            "updated_by": self.actor,
            "version": 1,
            "plan_id": plan["id"],
            "plan_due_at": plan["next_due_at"],
            "plan_due_meter": plan["next_due_meter"],
            "plan_cycle_key": cycle_key,
        }
        await self.session.execute(
            text(
                "INSERT INTO eq_maintenance_orders(id,organization_id,asset_id,order_code,"
                "maintenance_type,description,status,block_status,block_reason_code,created_at,"
                "updated_at,created_by,updated_by,version,plan_id,plan_due_at,plan_due_meter,"
                "plan_cycle_key) VALUES(:id,:organization_id,:asset_id,:order_code,"
                ":maintenance_type,:description,:status,:block_status,:block_reason_code,:created_at,"
                ":updated_at,:created_by,:updated_by,:version,:plan_id,:plan_due_at,:plan_due_meter,"
                ":plan_cycle_key)"
            ),
            record,
        )
        self._audit(
            "equipment.maintenance_order",
            identifier,
            {"status": "open", "plan_id": plan["id"], "plan_cycle_key": cycle_key},
        )
        return record

    async def set_maintenance_plan_status(self, plan_id, status):
        require(self.request, "equipment.maintenance.create")
        if status not in ("active", "paused"):
            raise HTTPException(422, "Invalid maintenance plan status")
        await self._begin_serialized_write()
        plan = (await self.session.execute(
            text("SELECT * FROM eq_maintenance_plans WHERE id=:id"),
            {"id": _hex(plan_id)},
        )).mappings().first()
        if not plan:
            raise HTTPException(404, "Preventive maintenance plan unavailable")
        await self.registry._visible_org(plan["organization_id"], "equipment.maintenance.view")
        if plan["status"] != status:
            now = _now()
            await self.session.execute(
                text(
                    "UPDATE eq_maintenance_plans SET status=:status,updated_at=:now,"
                    "updated_by=:actor,version=version+1 WHERE id=:id"
                ),
                {"status": status, "now": now, "actor": self.actor, "id": plan["id"]},
            )
            self._audit("equipment.maintenance_plan", plan["id"], {"status": status})
            return {**dict(plan), "status": status, "updated_at": now,
                    "updated_by": self.actor, "version": plan["version"] + 1}
        return dict(plan)

    async def release_inspection_block(self, inspection_id, payload):
        require(self.request, "equipment.safety.release")
        original = (await self.session.execute(
            text("SELECT * FROM eq_inspections WHERE id=:id"),
            {"id": _hex(inspection_id)},
        )).mappings().first()
        if not original:
            raise HTTPException(404, "Equipment inspection unavailable")
        await self.registry._visible_org(original["organization_id"], "equipment.inspections.view")
        if original["block_status"] != "active":
            raise HTTPException(409, "Inspection has no active safety blocker")
        if original["created_by"] == self.actor:
            raise HTTPException(409, "Safety release must be performed by a different user")
        followup = await self._verified_post_repair(payload.inspection_id, original)
        if followup["created_by"] == self.actor or followup["verified_by"] == self.actor:
            raise HTTPException(409, "Safety release must be independent of the follow-up inspection")
        await self.session.execute(
            text(
                "UPDATE eq_inspections SET block_status='released',block_reason_code=NULL,"
                "release_inspection_id=:followup,updated_at=:now,updated_by=:actor,version=version+1 "
                "WHERE id=:id AND block_status='active'"
            ),
            {"followup": followup["id"], "now": _now(), "actor": self.actor, "id": original["id"]},
        )
        self._audit("equipment.inspection", original["id"], {"block_status": "released"})
        return {"id": original["id"], "block_status": "released", "release_inspection_id": followup["id"]}

    async def release_maintenance_block(self, order_id, payload):
        require(self.request, "equipment.safety.release")
        order = (await self.session.execute(
            text("SELECT * FROM eq_maintenance_orders WHERE id=:id"),
            {"id": _hex(order_id)},
        )).mappings().first()
        if not order:
            raise HTTPException(404, "Equipment maintenance order unavailable")
        await self.registry._visible_org(order["organization_id"], "equipment.maintenance.view")
        if order["block_status"] != "active" or order["status"] != "technically_completed":
            raise HTTPException(409, "Maintenance must be technically completed with an active blocker")
        if order["created_by"] == self.actor or order["updated_by"] == self.actor:
            raise HTTPException(409, "Safety release must be independent of maintenance request and completion")
        followup = await self._verified_post_repair(payload.inspection_id, order)
        if followup["created_by"] == self.actor or followup["verified_by"] == self.actor:
            raise HTTPException(409, "Safety release must be independent of the follow-up inspection")
        now = _now()
        await self.session.execute(
            text(
                "UPDATE eq_maintenance_orders SET status='verified_closed',block_status='released',"
                "block_reason_code=NULL,release_inspection_id=:inspection,updated_at=:now,updated_by=:actor,"
                "version=version+1 WHERE id=:id AND block_status='active'"
            ),
            {"inspection": followup["id"], "now": now, "actor": self.actor, "id": order["id"]},
        )
        self._audit("equipment.maintenance_order", order["id"], {"status": "verified_closed"})
        return {"id": order["id"], "status": "verified_closed", "block_status": "released",
                "release_inspection_id": followup["id"]}

    async def _verified_post_repair(self, inspection_id, source):
        followup = (await self.session.execute(
            text(
                "SELECT * FROM eq_inspections WHERE id=:id AND organization_id=:org AND asset_id=:asset"
            ),
            {"id": _hex(inspection_id), "org": source["organization_id"], "asset": source["asset_id"]},
        )).mappings().first()
        if not followup or (
            followup["inspection_type"] != "post_repair" or followup["result"] != "passed"
            or followup["status"] != "verified" or followup["verified_by"] is None
            or followup["created_by"] == source["created_by"]
        ):
            raise HTTPException(422, "A separately performed and verified passing post-repair inspection is required")
        if followup["inspected_at"] <= source["updated_at"]:
            raise HTTPException(422, "Post-repair inspection must follow the safety-blocking event")
        return followup

    async def readiness(self, asset_id, assignment_id=None):
        require(self.request, "equipment.assets.view")
        asset = await self._asset(asset_id, "equipment.assets.view")
        blockers = await self._active_blockers(asset["organization_id"], _hex(asset_id))
        reasons = [blocker["reason_code"] for blocker in blockers]
        if asset["lifecycle_status"] != "in_service":
            reasons.append("ASSET_NOT_IN_SERVICE")
        if asset["technical_status"] in ("unsafe", "maintenance", "out_of_service"):
            reasons.append("TECHNICAL_STATUS_BLOCKED")

        assignment = None
        if assignment_id is None:
            reasons.append("APPROVED_ASSIGNMENT_REQUIRED")
        else:
            assignment = (await self.session.execute(
                text(
                    "SELECT id,status,operator_employee_id FROM eq_assignments "
                    "WHERE id=:id AND organization_id=:org AND asset_id=:asset"
                ),
                {"id": _hex(assignment_id), "org": asset["organization_id"], "asset": _hex(asset_id)},
            )).mappings().first()
            if not assignment or assignment["status"] != "approved":
                reasons.append("APPROVED_ASSIGNMENT_REQUIRED")
            else:
                passed = await self.session.scalar(
                    text(
                        "SELECT 1 FROM eq_inspections WHERE organization_id=:org AND asset_id=:asset "
                        "AND assignment_id=:assignment AND inspection_type='pre_operation' "
                        "AND result='passed' AND status='verified' ORDER BY inspected_at DESC LIMIT 1"
                    ),
                    {"org": asset["organization_id"], "asset": _hex(asset_id), "assignment": assignment["id"]},
                )
                if not passed:
                    reasons.append("VERIFIED_PRE_OPERATION_INSPECTION_REQUIRED")
        safety_ready = not reasons
        if assignment and assignment["status"] == "approved":
            operator_id = assignment["operator_employee_id"]
            if not operator_id:
                reasons.append("OPERATOR_ASSIGNMENT_REQUIRED")
            else:
                category_code = await self.session.scalar(text(
                    "SELECT c.category_code FROM eq_assets a JOIN eq_categories c "
                    "ON c.id=a.category_id AND c.organization_id=a.organization_id "
                    "WHERE a.id=:asset AND a.organization_id=:org"
                ), {"asset": _hex(asset_id), "org": asset["organization_id"]})
                eligibility = await OperatorQualificationService.eligibility(
                    self.session, operator_id, asset["organization_id"], category_code
                )
                if not eligibility["eligible"]:
                    reasons.append(eligibility["reason"])
        reasons.append("SAFETY_POLICY_APPROVAL_REQUIRED")
        return {
            "asset_id": _hex(asset_id), "assignment_id": assignment["id"] if assignment else None,
            "safety_ready": safety_ready, "eligible_to_start": False, "evaluated_at": _now(),
            "active_blockers": blockers, "reasons": reasons,
            "note": "Operation start remains disabled until an authorized safety policy is approved and implemented.",
        }

    async def _active_blockers(self, organization_id, asset_id):
        inspections = (await self.session.execute(
            text(
                "SELECT id,'inspection' AS source,block_reason_code AS reason_code "
                "FROM eq_inspections WHERE organization_id=:org AND asset_id=:asset AND block_status='active'"
            ),
            {"org": organization_id, "asset": asset_id},
        )).mappings().all()
        maintenance = (await self.session.execute(
            text(
                "SELECT id,'maintenance' AS source,block_reason_code AS reason_code "
                "FROM eq_maintenance_orders WHERE organization_id=:org AND asset_id=:asset AND block_status='active'"
            ),
            {"org": organization_id, "asset": asset_id},
        )).mappings().all()
        return [dict(row) for row in (*inspections, *maintenance)]

    def _audit(self, entity_type, identifier, new):
        self.request.state.audit_details = {
            "entity_type": entity_type, "entity_id": identifier, "new": new,
            "summary": f"{entity_type} safety workflow change",
        }
