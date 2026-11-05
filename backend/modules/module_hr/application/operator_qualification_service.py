"""HR-owned evidence, decisions, and eligibility contract for equipment operators."""
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.access import require
from .employee_service import EmployeeService


class OperatorQualificationService:
    def __init__(self, session, request):
        self.session = session
        self.request = request
        self.employees = EmployeeService(session, request)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

    async def _employee(self, employee_id, permission):
        organization_id = self.employees._organization(permission=permission)
        employee = await self.employees._employee(employee_id, organization_id, permission)
        return organization_id, employee

    async def list_for_employee(self, employee_id):
        permission = "hr.operator_qualifications.view"
        require(self.request, permission)
        organization_id, _ = await self._employee(employee_id, permission)
        rows = (await self.session.execute(text(
            "SELECT * FROM hr_operator_qualifications "
            "WHERE organization_id=:org AND employee_id=:employee "
            "ORDER BY created_at DESC,id DESC"
        ), {"org": organization_id, "employee": employee_id})).mappings().all()
        return {"items": [dict(row) for row in rows]}

    async def create(self, employee_id, payload):
        permission = "hr.operator_qualifications.manage"
        require(self.request, permission)
        organization_id, employee = await self._employee(employee_id, permission)
        if employee["employment_status"] != "active":
            raise HTTPException(409, "Only an active HR employee can receive an operator qualification")
        if payload.valid_until and payload.valid_until < payload.valid_from:
            raise HTTPException(422, "valid_until must not precede valid_from")
        record = {
            "organization_id": organization_id,
            "employee_id": employee_id,
            "equipment_class_code": payload.equipment_class_code,
            "qualification_code": payload.qualification_code,
            "credential_reference": payload.credential_reference,
            "issuer_name": payload.issuer_name,
            "evidence_reference": payload.evidence_reference,
            "valid_from": payload.valid_from.isoformat(),
            "valid_until": payload.valid_until.isoformat() if payload.valid_until else None,
            "idempotency_key": payload.idempotency_key,
        }
        existing = (await self.session.execute(text(
            "SELECT * FROM hr_operator_qualifications "
            "WHERE organization_id=:org AND idempotency_key=:key"
        ), {"org": organization_id, "key": payload.idempotency_key})).mappings().first()
        if existing:
            if all(existing[key] == value for key, value in record.items()):
                return {**dict(existing), "idempotent_replay": True}
            raise HTTPException(409, "Qualification idempotency key conflicts with an existing record")
        identifier = uuid4().hex
        now = self._now()
        record.update({
            "id": identifier,
            "status": "pending",
            "created_at": now,
            "created_by": self.request.state.user.id.hex,
        })
        try:
            await self.session.execute(text(
                "INSERT INTO hr_operator_qualifications("
                "id,organization_id,employee_id,equipment_class_code,qualification_code,"
                "credential_reference,issuer_name,evidence_reference,valid_from,valid_until,"
                "status,idempotency_key,created_at,created_by) "
                "VALUES(:id,:organization_id,:employee_id,:equipment_class_code,:qualification_code,"
                ":credential_reference,:issuer_name,:evidence_reference,:valid_from,:valid_until,"
                ":status,:idempotency_key,:created_at,:created_by)"
            ), record)
        except IntegrityError:
            raise HTTPException(409, "Qualification idempotency key conflicts with an existing record") from None
        self.request.state.audit_details = {
            "entity_type": "hr.operator_qualification",
            "entity_id": identifier,
            "new": {
                "employee_id": employee_id,
                "equipment_class_code": payload.equipment_class_code,
                "qualification_code": payload.qualification_code,
                "status": "pending",
            },
            "summary": "Operator qualification evidence submitted for independent review",
        }
        return {**record, "idempotent_replay": False}

    async def decide(self, qualification_id, action, decision_reason="", authority_ref=""):
        require(self.request, "hr.operator_qualifications.approve")
        row = (await self.session.execute(text(
            "SELECT * FROM hr_operator_qualifications WHERE id=:id"
        ), {"id": qualification_id})).mappings().first()
        if row is None:
            raise HTTPException(404, "Operator qualification unavailable")
        await self.employees._employee(
            row["employee_id"], row["organization_id"], "hr.operator_qualifications.approve"
        )
        if row["created_by"] == self.request.state.user.id.hex:
            raise HTTPException(409, "Qualification decision must be made by a different user")
        if action == "approve":
            if row["status"] != "pending":
                raise HTTPException(409, "Only pending qualification evidence can be approved")
            if not authority_ref.strip():
                raise HTTPException(422, "Approval authority reference is required")
            today = date.today().isoformat()
            if row["valid_until"] and row["valid_until"] < today:
                raise HTTPException(422, "Expired qualification evidence cannot be approved")
            target, reason = "approved", None
        elif action == "reject":
            if row["status"] != "pending":
                raise HTTPException(409, "Only pending qualification evidence can be rejected")
            target = "rejected"
            reason = decision_reason.strip()
        elif action in ("suspend", "revoke"):
            allowed = {"suspend": ("approved",), "revoke": ("approved", "suspended")}
            if row["status"] not in allowed[action]:
                raise HTTPException(409, "Qualification cannot make the requested transition")
            target, reason = ("suspended" if action == "suspend" else "revoked"), decision_reason.strip()
        else:
            raise HTTPException(422, "Unsupported qualification decision")
        if target != "approved" and (not reason or not authority_ref.strip()):
            raise HTTPException(422, "A decision reason and authority reference are required")
        now = self._now()
        actor = self.request.state.user.id.hex
        result = await self.session.execute(text(
            "UPDATE hr_operator_qualifications SET status=:status,decided_at=:at,decided_by=:actor,"
            "decision_reason=:reason,decision_authority_ref=:authority "
            "WHERE id=:id AND status=:previous"
        ), {
            "status": target, "at": now, "actor": actor, "reason": reason,
            "authority": authority_ref.strip(), "id": qualification_id, "previous": row["status"],
        })
        if result.rowcount != 1:
            raise HTTPException(409, "Qualification status changed concurrently")
        self.request.state.audit_details = {
            "entity_type": "hr.operator_qualification",
            "entity_id": qualification_id,
            "old": {"status": row["status"]},
            "new": {"status": target, "authority_ref": authority_ref.strip()},
            "summary": "Operator qualification decision recorded",
        }
        return {
            **dict(row), "status": target, "decided_at": now, "decided_by": actor,
            "decision_reason": reason, "decision_authority_ref": authority_ref.strip(),
        }

    @staticmethod
    async def eligibility(session, employee_id, organization_id, equipment_class_code, at_date=None):
        """Trusted in-process HR contract; callers receive no credential details."""
        table_exists = await session.scalar(text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='hr_operator_qualifications'"
        ))
        if not table_exists:
            raise HTTPException(503, "HR operator qualification migration is not installed")
        employee = (await session.execute(text(
            "SELECT employment_status FROM hr_employees WHERE id=:employee AND organization_id=:org"
        ), {"employee": employee_id, "org": organization_id})).mappings().first()
        if employee is None:
            raise HTTPException(404, "HR employee is unavailable within organization")
        if employee["employment_status"] != "active":
            return {"eligible": False, "reason": "HR_EMPLOYEE_NOT_ACTIVE", "qualification_id": None}
        effective_date = (at_date or date.today()).isoformat()
        qualification = (await session.execute(text(
            "SELECT id,valid_from,valid_until FROM hr_operator_qualifications "
            "WHERE employee_id=:employee AND organization_id=:org "
            "AND equipment_class_code=:class_code AND status='approved' "
            "AND valid_from<=:date AND (valid_until IS NULL OR valid_until>=:date) "
            "ORDER BY valid_until IS NULL,valid_until DESC,decided_at DESC,id DESC LIMIT 1"
        ), {
            "employee": employee_id, "org": organization_id,
            "class_code": equipment_class_code, "date": effective_date,
        })).mappings().first()
        if qualification is None:
            return {
                "eligible": False,
                "reason": "APPROVED_CURRENT_OPERATOR_QUALIFICATION_REQUIRED",
                "qualification_id": None,
            }
        return {
            "eligible": True,
            "reason": None,
            "qualification_id": qualification["id"],
            "valid_until": qualification["valid_until"],
        }
