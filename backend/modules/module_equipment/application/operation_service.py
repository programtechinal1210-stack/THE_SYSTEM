import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.access import require
from core.config import settings
from modules.module_hr.application.operator_qualification_service import OperatorQualificationService
from .registry_service import EquipmentRegistryService, _hex, _now


def _timestamp(value):
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hash(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")).hexdigest()


class EquipmentOperationService:
    def __init__(self, session, request):
        self.session = session
        self.request = request
        self.registry = EquipmentRegistryService(session, request)

    @property
    def actor(self):
        return self.request.state.user_id.hex

    async def _serialize(self):
        if self.session.bind.dialect.name != "sqlite":
            raise HTTPException(503, "Equipment operation serialization requires the configured SQLite Core database")
        await self.session.execute(text("BEGIN IMMEDIATE"))

    @staticmethod
    def _isolated_test_environment():
        path = urlparse(settings.DATABASE_URL).path.replace("\\", "/").lower()
        return (
            settings.APP_ENV.lower() in {"test", "testing"}
            and "/.work/test-" in path
            and not settings.APP_ENV.lower() == "production"
        )

    async def list_policies(self, organization_id=None):
        permission = "equipment.safety_policy.view"
        require(self.request, permission)
        organization = await self.registry._organization(organization_id, permission)
        rows = (await self.session.execute(text(
            "SELECT id,organization_id,policy_version,policy_mode,policy_reference,policy_document_ref,"
            "issuing_authority,authorized_role_code,inspection_validity_minutes,effective_from,"
            "effective_until,status,created_at,created_by,reviewed_at,reviewed_by,decision_authority_ref "
            "FROM eq_safety_policies WHERE organization_id=:org ORDER BY policy_mode,policy_version DESC"
        ), {"org": organization})).mappings().all()
        return {"items": [dict(row) for row in rows]}

    async def create_policy(self, payload):
        require(self.request, "equipment.safety_policy.manage")
        organization = await self.registry._organization(
            payload.organization_id, "equipment.safety_policy.manage", create=True
        )
        if payload.policy_mode == "test" and not self._isolated_test_environment():
            raise HTTPException(403, "Test safety policies are allowed only on an isolated test database")
        role_exists = await self.session.scalar(
            text("SELECT 1 FROM roles WHERE name=:name"), {"name": payload.authorized_role_code}
        )
        if not role_exists:
            raise HTTPException(422, "Authorized policy role does not exist")
        if payload.effective_until and payload.effective_until <= payload.effective_from:
            raise HTTPException(422, "Policy effective interval is invalid")
        identifier, now = uuid4().hex, _now()
        record = {
            "id": identifier, "organization_id": organization,
            "policy_version": payload.policy_version, "policy_mode": payload.policy_mode,
            "policy_reference": payload.policy_reference, "policy_document_ref": payload.policy_document_ref,
            "issuing_authority": payload.issuing_authority,
            "authorized_role_code": payload.authorized_role_code,
            "inspection_validity_minutes": payload.inspection_validity_minutes,
            "effective_from": _timestamp(payload.effective_from.astimezone(timezone.utc)),
            "effective_until": _timestamp(payload.effective_until.astimezone(timezone.utc))
                if payload.effective_until else None,
            "status": "draft", "created_at": now, "created_by": self.actor,
        }
        try:
            await self.session.execute(text(
                "INSERT INTO eq_safety_policies(id,organization_id,policy_version,policy_mode,policy_reference,"
                "policy_document_ref,issuing_authority,authorized_role_code,inspection_validity_minutes,"
                "effective_from,effective_until,status,created_at,created_by) "
                "VALUES(:id,:organization_id,:policy_version,:policy_mode,:policy_reference,:policy_document_ref,"
                ":issuing_authority,:authorized_role_code,:inspection_validity_minutes,:effective_from,"
                ":effective_until,:status,:created_at,:created_by)"
            ), record)
        except IntegrityError as exc:
            raise HTTPException(409, "Policy version already exists or policy scope conflicts") from exc
        self.request.state.audit_details = {
            "entity_type": "equipment.safety_policy", "entity_id": identifier,
            "new": {
                "policy_mode": payload.policy_mode, "policy_version": payload.policy_version,
                "policy_reference": payload.policy_reference,
                "authorized_role_code": payload.authorized_role_code, "status": "draft",
            },
        }
        return record

    async def decide_policy(self, policy_id, approve, authority_ref):
        permission = "equipment.safety_policy.approve"
        require(self.request, permission)
        await self._serialize()
        row = (await self.session.execute(text(
            "SELECT * FROM eq_safety_policies WHERE id=:id"
        ), {"id": _hex(policy_id)})).mappings().first()
        if row is None:
            raise HTTPException(404, "Safety policy unavailable")
        await self.registry._visible_org(row["organization_id"], permission)
        if row["status"] != "draft":
            raise HTTPException(409, "Only a draft safety policy can be decided")
        if row["created_by"] == self.actor:
            raise HTTPException(409, "Safety policy approval must be performed by a different user")
        approver_organization = getattr(self.request.state.user, "organization_id", None)
        role_member = await self.session.scalar(text(
            "SELECT 1 FROM roles r JOIN user_roles ur ON ur.role_id=r.id "
            "WHERE r.name=:role AND ur.user_id=:actor AND "
            "(ur.scope='institution' OR "
            "(ur.scope='organization' AND :approver_org=:policy_org))"
        ), {
            "role": row["authorized_role_code"], "actor": self.actor,
            "approver_org": _hex(approver_organization) if approver_organization else None,
            "policy_org": row["organization_id"],
        })
        if not role_member:
            raise HTTPException(403, "Policy approver must hold the policy's authorized role")
        if row["policy_mode"] == "test" and not self._isolated_test_environment():
            raise HTTPException(403, "Test safety policies are allowed only on an isolated test database")
        if not authority_ref.strip():
            raise HTTPException(422, "Decision authority reference is required")
        if approve:
            status = "approved"
            effective_now = _now()
            if row["effective_from"] > effective_now or (
                row["effective_until"] and row["effective_until"] <= effective_now
            ):
                raise HTTPException(409, "Safety policy is not currently effective")
        else:
            status = "withdrawn"
        now = _now()
        result = await self.session.execute(text(
            "UPDATE eq_safety_policies SET status=:status,reviewed_at=:now,reviewed_by=:actor,"
            "decision_authority_ref=:authority WHERE id=:id AND status='draft'"
        ), {
            "status": status, "now": now, "actor": self.actor,
            "authority": authority_ref.strip(), "id": row["id"],
        })
        if result.rowcount != 1:
            raise HTTPException(409, "Safety policy decision conflicted")
        self.request.state.audit_details = {
            "entity_type": "equipment.safety_policy", "entity_id": row["id"],
            "old": {"status": "draft"},
            "new": {"status": status, "authority_ref": authority_ref.strip()},
        }
        return {"id": row["id"], "status": status, "reviewed_at": now, "reviewed_by": self.actor}

    async def _policy(self, policy_id, organization_id, at):
        row = (await self.session.execute(text(
            "SELECT * FROM eq_safety_policies WHERE id=:id AND organization_id=:org "
            "AND status='approved' AND effective_from<=:at AND (effective_until IS NULL OR effective_until>:at)"
        ), {"id": policy_id, "org": organization_id, "at": at})).mappings().first()
        if row is None:
            raise HTTPException(409, "APPROVED_EFFECTIVE_SAFETY_POLICY_REQUIRED")
        if row["policy_mode"] == "test" and not self._isolated_test_environment():
            raise HTTPException(403, "Test safety policy cannot authorize this environment")
        if settings.APP_ENV.lower() == "production" and row["policy_mode"] != "production":
            raise HTTPException(409, "PRODUCTION_SAFETY_POLICY_REQUIRED")
        if self._isolated_test_environment() and row["policy_mode"] != "test":
            raise HTTPException(409, "ISOLATED_TEST_SAFETY_POLICY_REQUIRED")
        return row

    async def start(self, payload):
        permission = "equipment.operations.start"
        require(self.request, permission)
        await self._serialize()
        if settings.APP_ENV.lower() == "production":
            pass
        elif not self._isolated_test_environment():
            raise HTTPException(503, "Equipment operation start is disabled outside production and isolated tests")
        at = _now()
        digest = _hash(payload.model_dump(mode="json"))
        assignment = (await self.session.execute(text(
            "SELECT a.*,e.category_id,e.lifecycle_status,e.technical_status,e.meter_type_locked,"
            "e.meter_unit_locked,e.meter_generation,e.meter_normalized_latest,e.meter_latest,"
            "c.category_code,c.output_unit,c.fuel_unit "
            "FROM eq_assignments a JOIN eq_assets e ON e.id=a.asset_id AND e.organization_id=a.organization_id "
            "JOIN eq_categories c ON c.id=e.category_id AND c.organization_id=e.organization_id "
            "WHERE a.id=:id"
        ), {"id": _hex(payload.assignment_id)})).mappings().first()
        if assignment is None:
            raise HTTPException(404, "Equipment assignment unavailable")
        await self.registry._visible_org(assignment["organization_id"], permission)
        existing = (await self.session.execute(text(
            "SELECT * FROM eq_operation_logs WHERE organization_id=:org AND idempotency_key=:key"
        ), {
            "org": assignment["organization_id"], "key": payload.idempotency_key,
        })).mappings().first()
        if existing:
            if existing["start_payload_hash"] != digest:
                raise HTTPException(409, "Operation idempotency key was used with a different request")
            return {**dict(existing), "idempotent_replay": True}
        pending_meter_event = await self.session.scalar(text(
            "SELECT 1 FROM eq_meter_events WHERE organization_id=:org AND asset_id=:asset "
            "AND status='pending' LIMIT 1"
        ), {"org": assignment["organization_id"], "asset": assignment["asset_id"]})
        if pending_meter_event:
            raise HTTPException(409, "Pending meter events must be approved before operation start")
        if assignment["status"] not in ("approved", "active"):
            raise HTTPException(409, "APPROVED_ASSIGNMENT_REQUIRED")
        if assignment["lifecycle_status"] != "in_service" or assignment["technical_status"] in {
            "unsafe", "maintenance", "out_of_service",
        }:
            raise HTTPException(422, "SAFETY_BLOCK")
        if not assignment["operator_employee_id"]:
            raise HTTPException(422, "QUALIFIED_OPERATOR_REQUIRED")
        if assignment["planned_start_at"] > at or assignment["planned_end_at"] <= at:
            raise HTTPException(409, "ASSIGNMENT_NOT_ACTIVE_AT_START")
        policy = await self._policy(_hex(payload.policy_id), assignment["organization_id"], at)
        if policy["policy_mode"] == "test" and not self._isolated_test_environment():
            raise HTTPException(403, "Test-only policy cannot be used outside test environment")

        blockers = await self.session.execute(text(
            "SELECT id,'inspection' AS source,block_reason_code AS reason FROM eq_inspections "
            "WHERE organization_id=:org AND asset_id=:asset AND block_status='active' "
            "UNION ALL SELECT id,'maintenance' AS source,block_reason_code AS reason "
            "FROM eq_maintenance_orders WHERE organization_id=:org AND asset_id=:asset AND block_status='active'"
        ), {"org": assignment["organization_id"], "asset": assignment["asset_id"]})
        if blockers.mappings().first():
            raise HTTPException(422, "SAFETY_BLOCK")

        eligibility = await OperatorQualificationService.eligibility(
            self.session, assignment["operator_employee_id"], assignment["organization_id"],
            assignment["category_code"], at_date=datetime.fromisoformat(at.replace("Z", "+00:00")).date(),
        )
        if not eligibility["eligible"]:
            raise HTTPException(422, eligibility["reason"])

        roster = (await self.session.execute(text(
            "SELECT id,start_at,end_at FROM hr_shift_roster WHERE id=:id AND organization_id=:org "
            "AND employee_id=:employee AND status='confirmed' AND start_at<=:at AND end_at>:at"
        ), {
            "id": _hex(payload.shift_roster_id), "org": assignment["organization_id"],
            "employee": assignment["operator_employee_id"], "at": at,
        })).mappings().first()
        if roster is None:
            raise HTTPException(422, "CONFIRMED_OPERATOR_SHIFT_REQUIRED")
        attendance = await self.session.scalar(text(
            "SELECT 1 FROM hr_attendance WHERE organization_id=:org AND employee_id=:employee "
            "AND shift_roster_id=:roster AND attendance_kind='base_shift' AND is_current=1 "
            "AND approval_status='approved' AND status IN ('present','partial','late')"
        ), {
            "org": assignment["organization_id"], "employee": assignment["operator_employee_id"],
            "roster": roster["id"],
        })
        if not attendance:
            raise HTTPException(422, "APPROVED_OPERATOR_ATTENDANCE_REQUIRED")
        recent_inspection = await self.session.scalar(text(
            "SELECT 1 FROM eq_inspections WHERE organization_id=:org AND asset_id=:asset "
            "AND assignment_id=:assignment AND inspection_type='pre_operation' "
            "AND result='passed' AND status='verified' "
            "AND inspected_at>=:fresh_after AND inspected_at<=:at"
        ), {
            "org": assignment["organization_id"], "asset": assignment["asset_id"],
            "assignment": assignment["id"],
            "fresh_after": _timestamp(
                datetime.fromisoformat(at.replace("Z", "+00:00"))
                - timedelta(minutes=policy["inspection_validity_minutes"])
            ),
            "at": at,
        })
        if not recent_inspection:
            raise HTTPException(422, "VERIFIED_CURRENT_PRE_OPERATION_INSPECTION_REQUIRED")

        running_operator = await self.session.scalar(text(
            "SELECT 1 FROM eq_operation_logs WHERE organization_id=:org "
            "AND operator_employee_id=:operator AND status='running'"
        ), {"org": assignment["organization_id"], "operator": assignment["operator_employee_id"]})
        if running_operator:
            raise HTTPException(409, "OPERATOR_ALREADY_IN_OPERATION")

        meter_start = (
            assignment["meter_latest"]
        )
        meter_normalized_start = (
            assignment["meter_normalized_latest"]
            if assignment["meter_normalized_latest"] is not None
            else assignment["meter_latest"]
        )
        meter_type = assignment["meter_type_locked"] or "none"
        meter_unit = assignment["meter_unit_locked"] or "none"
        generation = assignment["meter_generation"] or 1
        identifier = uuid4().hex
        record = {
            "id": identifier, "organization_id": assignment["organization_id"],
            "asset_id": assignment["asset_id"], "assignment_id": assignment["id"],
            "operator_employee_id": assignment["operator_employee_id"], "shift_roster_id": roster["id"],
            "safety_policy_id": policy["id"], "policy_mode": policy["policy_mode"],
            "operation_code": "EMO-O-" + identifier[:12].upper(),
            "started_at": at, "meter_type_snapshot": meter_type, "meter_unit_snapshot": meter_unit,
            "meter_generation_snapshot": generation, "meter_start": meter_start,
            "meter_normalized_start": meter_normalized_start,
            "status": "running", "idempotency_key": payload.idempotency_key,
            "start_payload_hash": digest, "notes": payload.notes,
            "created_at": at, "created_by": self.actor,
        }
        try:
            await self.session.execute(text(
                "INSERT INTO eq_operation_logs(id,organization_id,asset_id,assignment_id,operator_employee_id,"
                "shift_roster_id,safety_policy_id,policy_mode,operation_code,started_at,meter_type_snapshot,"
                "meter_unit_snapshot,meter_generation_snapshot,meter_start,meter_normalized_start,status,idempotency_key,"
                "start_payload_hash,notes,created_at,created_by) VALUES(:id,:organization_id,:asset_id,:assignment_id,"
                ":operator_employee_id,:shift_roster_id,:safety_policy_id,:policy_mode,:operation_code,"
                ":started_at,:meter_type_snapshot,:meter_unit_snapshot,:meter_generation_snapshot,:meter_start,"
                ":meter_normalized_start,"
                ":status,:idempotency_key,:start_payload_hash,:notes,:created_at,:created_by)"
            ), record)
        except IntegrityError as exc:
            raise HTTPException(409, "Asset or operator already has an active operation") from exc
        if assignment["status"] == "approved":
            await self.session.execute(text(
                "UPDATE eq_assignments SET status='active',updated_at=:at,updated_by=:actor,version=version+1 "
                "WHERE id=:id AND status='approved'"
            ), {"at": at, "actor": self.actor, "id": assignment["id"]})
        self.request.state.audit_details = {
            "entity_type": "equipment.operation", "entity_id": identifier,
            "new": {
                "asset_id": assignment["asset_id"], "assignment_id": assignment["id"],
                "operator_employee_id": assignment["operator_employee_id"],
                "safety_policy_id": policy["id"], "policy_mode": policy["policy_mode"],
                "status": "running",
            },
        }
        return {**record, "idempotent_replay": False}

    async def finish(self, operation_id, payload):
        permission = "equipment.operations.record"
        require(self.request, permission)
        await self._serialize()
        row = (await self.session.execute(text(
            "SELECT * FROM eq_operation_logs WHERE id=:id"
        ), {"id": _hex(operation_id)})).mappings().first()
        if row is None:
            raise HTTPException(404, "Equipment operation unavailable")
        await self.registry._visible_org(row["organization_id"], permission)
        digest = _hash(payload.model_dump(mode="json"))
        if row["status"] == "submitted":
            if row["finish_payload_hash"] == digest:
                meter_event_id = await self.session.scalar(text(
                    "SELECT id FROM eq_meter_events WHERE operation_log_id=:operation"
                ), {"operation": row["id"]})
                fuel_event_id = await self.session.scalar(text(
                    "SELECT id FROM eq_fuel_events WHERE operation_log_id=:operation "
                    "AND event_type='consumed'"
                ), {"operation": row["id"]})
                return {
                    **dict(row), "meter_end_event_id": meter_event_id,
                    "fuel_event_id": fuel_event_id, "idempotent_replay": True,
                }
            raise HTTPException(409, "Operation was already submitted with different closing values")
        if row["status"] != "running":
            raise HTTPException(409, "Only a running operation can be ended")
        if row["created_by"] != self.actor:
            raise HTTPException(403, "Only the assigned operation recorder can submit its closing values")
        now = _now()
        duration = int(
            (datetime.fromisoformat(now.replace("Z", "+00:00"))
             - datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))).total_seconds() // 60
        )
        if payload.working_minutes + payload.idle_minutes + payload.downtime_minutes > duration + 2:
            raise HTTPException(422, "Recorded working, idle and downtime minutes exceed operation duration")
        meter_event_id = None
        meter_normalized_end = None
        meter_asset = None
        if payload.meter_end is not None:
            meter_asset = (await self.session.execute(text(
                "SELECT meter_latest,meter_normalized_latest,meter_generation,meter_type_locked,"
                "meter_unit_locked,meter_last_at FROM eq_assets "
                "WHERE id=:asset AND organization_id=:org AND deleted_at IS NULL"
            ), {"asset": row["asset_id"], "org": row["organization_id"]})).mappings().first()
            if (
                row["meter_type_snapshot"] == "none"
                or row["meter_start"] is None
                or meter_asset is None
                or meter_asset["meter_generation"] != row["meter_generation_snapshot"]
                or meter_asset["meter_type_locked"] != row["meter_type_snapshot"]
                or meter_asset["meter_unit_locked"] != row["meter_unit_snapshot"]
                or meter_asset["meter_latest"] != row["meter_start"]
            ):
                raise HTTPException(409, "Operation meter snapshot is stale or unavailable")
            if Decimal(str(payload.meter_end)) < Decimal(str(row["meter_start"])):
                raise HTTPException(422, "Operation meter cannot decrease within one generation")
            if meter_asset["meter_last_at"] and now <= meter_asset["meter_last_at"]:
                raise HTTPException(409, "Operation meter event time must follow the last approved reading")
            pending_meter_event = await self.session.scalar(text(
                "SELECT 1 FROM eq_meter_events WHERE organization_id=:org AND asset_id=:asset "
                "AND status='pending' LIMIT 1"
            ), {"org": row["organization_id"], "asset": row["asset_id"]})
            if pending_meter_event:
                raise HTTPException(409, "Pending meter events must be resolved before operation close")
            current_normalized = (
                Decimal(str(meter_asset["meter_normalized_latest"]))
                if meter_asset["meter_normalized_latest"] is not None
                else Decimal(str(meter_asset["meter_latest"]))
            )
            offset = current_normalized - Decimal(str(meter_asset["meter_latest"]))
            meter_normalized_end = format(
                (Decimal(str(payload.meter_end)) + offset).normalize(), "f"
            )
            meter_event_id = uuid4().hex
        category = (await self.session.execute(text(
            "SELECT c.fuel_unit FROM eq_assets a JOIN eq_categories c "
            "ON c.id=a.category_id AND c.organization_id=a.organization_id "
            "WHERE a.id=:asset AND a.organization_id=:org"
        ), {"asset": row["asset_id"], "org": row["organization_id"]})).mappings().first()
        fuel_event_id = None
        if payload.fuel_consumed is not None:
            if category is None or category["fuel_unit"] != payload.fuel_unit:
                raise HTTPException(422, "Operation fuel unit must match the equipment category")
            fuel_event_id = uuid4().hex
        result = await self.session.execute(text(
            "UPDATE eq_operation_logs SET ended_at=:ended_at,meter_end=:meter_end,"
            "meter_normalized_end=:meter_normalized_end,working_minutes=:working,"
            "idle_minutes=:idle,downtime_minutes=:downtime,produced_quantity=:produced,production_unit=:unit,"
            "fuel_consumed=:fuel,downtime_reason_code=:downtime_reason,downtime_notes=:downtime_notes,"
            "status='submitted',finish_payload_hash=:hash WHERE id=:id AND status='running'"
        ), {
            "ended_at": now, "meter_end": str(payload.meter_end) if payload.meter_end is not None else None,
            "meter_normalized_end": meter_normalized_end,
            "working": payload.working_minutes, "idle": payload.idle_minutes,
            "downtime": payload.downtime_minutes,
            "produced": str(payload.produced_quantity) if payload.produced_quantity is not None else None,
            "unit": payload.production_unit,
            "fuel": str(payload.fuel_consumed) if payload.fuel_consumed is not None else None,
            "downtime_reason": payload.downtime_reason_code,
            "downtime_notes": payload.downtime_notes, "hash": digest, "id": row["id"],
        })
        if result.rowcount != 1:
            raise HTTPException(409, "Operation was closed concurrently")
        if meter_event_id:
            event_hash = _hash({
                "operation_id": row["id"], "event_type": "reading",
                "event_at": now, "meter_type": row["meter_type_snapshot"],
                "meter_unit": row["meter_unit_snapshot"],
                "generation": row["meter_generation_snapshot"],
                "reading_value": str(payload.meter_end),
            })
            try:
                await self.session.execute(text(
                    "INSERT INTO eq_meter_events(id,organization_id,asset_id,event_code,event_type,status,event_at,"
                    "meter_type_snapshot,meter_unit_snapshot,generation_before,generation_after,base_meter_latest,"
                    "base_meter_normalized_latest,reading_value,idempotency_key,payload_hash,created_at,created_by,"
                    "operation_log_id) VALUES(:id,:org,:asset,:code,'reading','pending',:at,:meter_type,:meter_unit,"
                    ":generation,:generation,:base_latest,:base_normalized,:reading,:key,:hash,:at,:actor,:operation)"
                ), {
                    "id": meter_event_id, "org": row["organization_id"], "asset": row["asset_id"],
                    "code": "EMO-ME-" + meter_event_id[:12].upper(), "at": now,
                    "meter_type": row["meter_type_snapshot"], "meter_unit": row["meter_unit_snapshot"],
                    "generation": row["meter_generation_snapshot"],
                    "base_latest": meter_asset["meter_latest"],
                    "base_normalized": meter_asset["meter_normalized_latest"],
                    "reading": str(payload.meter_end),
                    "key": "operation:" + row["id"] + ":meter-end",
                    "hash": event_hash, "actor": self.actor, "operation": row["id"],
                })
            except IntegrityError as exc:
                raise HTTPException(409, "Operation meter event could not be recorded uniquely") from exc
        if fuel_event_id:
            category_energy = payload.fuel_energy_type
            await self.session.execute(text(
                "INSERT INTO eq_fuel_events(id,organization_id,asset_id,fuel_event_code,event_type,energy_type,"
                "quantity,unit,event_at,status,reason_code,notes,idempotency_key,payload_hash,created_at,created_by,"
                "operation_log_id) VALUES(:id,:org,:asset,:code,'consumed',:energy,:quantity,:unit,:at,'draft',"
                "NULL,'Operation consumption pending independent fuel review',:key,:hash,:at,:actor,:operation)"
            ), {
                "id": fuel_event_id, "org": row["organization_id"], "asset": row["asset_id"],
                "code": "EMO-F-" + fuel_event_id[:12].upper(), "energy": category_energy,
                "quantity": str(payload.fuel_consumed), "unit": payload.fuel_unit, "at": now,
                "key": "operation:" + row["id"] + ":consumption",
                "hash": hashlib.sha256(
                    f"{row['id']}:{category_energy}:{payload.fuel_consumed}:{payload.fuel_unit}".encode()
                ).hexdigest(),
                "actor": self.actor, "operation": row["id"],
            })
        self.request.state.audit_details = {
            "entity_type": "equipment.operation", "entity_id": row["id"],
            "old": {"status": "running"},
            "new": {
                "status": "submitted", "ended_at": now,
                "meter_end_event_id": meter_event_id, "fuel_event_id": fuel_event_id,
            },
        }
        return {
            "id": row["id"], "status": "submitted", "ended_at": now,
            "meter_end_event_id": meter_event_id, "fuel_event_id": fuel_event_id,
            "idempotent_replay": False,
        }

    async def verify(self, operation_id):
        permission = "equipment.operations.verify"
        require(self.request, permission)
        await self._serialize()
        row = (await self.session.execute(text(
            "SELECT * FROM eq_operation_logs WHERE id=:id"
        ), {"id": _hex(operation_id)})).mappings().first()
        if row is None:
            raise HTTPException(404, "Equipment operation unavailable")
        await self.registry._visible_org(row["organization_id"], permission)
        if row["status"] != "submitted":
            raise HTTPException(409, "Only submitted operation logs can be verified")
        if row["created_by"] == self.actor:
            raise HTTPException(409, "Operation verification must be performed by a different user")
        meter_event = (await self.session.execute(text(
            "SELECT id,status FROM eq_meter_events WHERE operation_log_id=:operation"
        ), {"operation": row["id"]})).mappings().first()
        if row["meter_end"] is not None and meter_event is None:
            raise HTTPException(409, "Operation closing meter event is missing")
        if meter_event and meter_event["status"] != "approved":
            raise HTTPException(409, "Operation closing meter event requires independent approval")
        now = _now()
        result = await self.session.execute(text(
            "UPDATE eq_operation_logs SET status='verified',verified_at=:now,verified_by=:actor "
            "WHERE id=:id AND status='submitted'"
        ), {"now": now, "actor": self.actor, "id": row["id"]})
        if result.rowcount != 1:
            raise HTTPException(409, "Operation verification conflicted")
        self.request.state.audit_details = {
            "entity_type": "equipment.operation", "entity_id": row["id"],
            "old": {"status": "submitted"}, "new": {"status": "verified"},
        }
        return {"id": row["id"], "status": "verified", "verified_at": now, "verified_by": self.actor}

    async def list_operations(self, organization_id=None, asset_id=None):
        permission = "equipment.operations.view"
        require(self.request, permission)
        if asset_id:
            asset = (await self.session.execute(text(
                "SELECT id,organization_id FROM eq_assets WHERE id=:asset"
            ), {"asset": _hex(asset_id)})).mappings().first()
            if asset is None:
                raise HTTPException(404, "Equipment asset unavailable")
            organization = asset["organization_id"]
            await self.registry._visible_org(organization, permission)
        else:
            organization = await self.registry._organization(organization_id, permission)
        rows = (await self.session.execute(text(
            "SELECT id,organization_id,asset_id,assignment_id,operator_employee_id,shift_roster_id,"
            "safety_policy_id,policy_mode,operation_code,started_at,ended_at,meter_type_snapshot,"
            "meter_unit_snapshot,meter_generation_snapshot,meter_start,meter_end,"
            "meter_normalized_start,meter_normalized_end,working_minutes,"
            "idle_minutes,downtime_minutes,produced_quantity,production_unit,fuel_consumed,"
            "downtime_reason_code,downtime_notes,notes,status,created_by,verified_at,verified_by,"
            "(SELECT id FROM eq_meter_events me WHERE me.operation_log_id=eq_operation_logs.id) "
            "AS meter_end_event_id,(SELECT status FROM eq_meter_events me "
            "WHERE me.operation_log_id=eq_operation_logs.id) AS meter_end_event_status "
            "FROM eq_operation_logs WHERE organization_id=:org "
            "AND (:asset IS NULL OR asset_id=:asset) ORDER BY started_at DESC,id DESC LIMIT 500"
        ), {"org": organization, "asset": _hex(asset_id)})).mappings().all()
        return {"items": [dict(row) for row in rows]}
