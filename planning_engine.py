"""DW-02 planning and controlled Daily Work operations.

External execution remains owned by PM/HR/EMO/Inventory. Only items explicitly
marked independent may receive DW-owned actual events.
"""
import json
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import text

from core.access import require
from modules.module_pm.application.execution_service import ExecutionService
from modules.module_pm.application.planning_service import PlanningService

ZERO = Decimal("0")


def now():
    return datetime.now(timezone.utc).isoformat()


def decimal(value, *, name, non_negative=True):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(422, f"Invalid decimal: {name}") from None
    if not result.is_finite() or (non_negative and result < ZERO):
        raise HTTPException(422, f"Invalid value: {name}")
    return result


def money(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class DailyPlanningEngine(PlanningService):
    async def plans(self, project_id, plan_date=None):
        await self.project(project_id, "daily_work.view")
        params = {"p": project_id}
        date_clause = ""
        if plan_date:
            date_clause = " AND plan_date=:d"
            params["d"] = plan_date
        rows = (await self.session.execute(text(
            "SELECT p.*, COUNT(i.id) AS item_count, "
            "COALESCE(SUM(CAST(i.target_quantity AS NUMERIC)), 0) AS planned_quantity "
            "FROM dw_work_plans p LEFT JOIN dw_daily_work_items i "
            "ON i.plan_id=p.id AND i.deleted_at IS NULL "
            "WHERE p.project_id=:p AND p.deleted_at IS NULL" + date_clause +
            " GROUP BY p.id ORDER BY p.plan_date DESC, p.version DESC"
        ), params)).mappings().all()
        return {"plans": [dict(row) for row in rows]}

    async def project_plan(self, project_id, plan_id, permission="daily_work.view"):
        await self.project(project_id, permission)
        row = (await self.session.execute(text(
            "SELECT * FROM dw_work_plans WHERE id=:id AND project_id=:p AND deleted_at IS NULL"
        ), {"id": plan_id, "p": project_id})).mappings().first()
        if not row:
            raise HTTPException(404, "Daily plan unavailable")
        return dict(row)

    async def plan(self, project_id, plan_id):
        return await self.project_plan(project_id, plan_id, "daily_work.view")

    async def create_plan(self, project_id, payload):
        project = await self.project(project_id, "daily_work.manage")
        if payload.period_end < payload.period_start:
            raise HTTPException(422, "Plan period must be ordered")
        plan_id = uuid4().hex
        values = {
            "id": plan_id, "organization_id": project["organization_id"], "scope_type": "project",
            "scope_id": project_id, "project_id": project_id, "plan_date": payload.plan_date.isoformat(),
            "period_start": payload.period_start.isoformat(), "period_end": payload.period_end.isoformat(),
            "owner_user_id": payload.owner_user_id.hex if payload.owner_user_id else self.request.state.user_id.hex,
            "created_by": self.request.state.user_id.hex, "updated_at": now(),
        }
        owner = await self.session.scalar(text(
            "SELECT 1 FROM users WHERE id=:id AND organization_id=:org AND is_active=1"
        ), {"id": values["owner_user_id"], "org": project["organization_id"]})
        if not owner:
            raise HTTPException(422, "Plan owner must be active in the project organization")
        await self.session.execute(text(
            "INSERT INTO dw_work_plans (" + ",".join(values) + ") VALUES (" + ",".join(":" + k for k in values) + ")"
        ), values)
        self.audit("create", plan_id, None, values)
        return await self.plan(project_id, plan_id)

    async def add_item(self, project_id, plan_id, payload):
        await self.project(project_id, "daily_work.manage")
        plan = await self.plan(project_id, plan_id)
        if plan["status"] != "draft":
            raise HTTPException(409, "Only draft plans can be edited")
        if not (plan["period_start"] <= payload.work_date.isoformat() <= plan["period_end"]):
            raise HTTPException(422, "Work date must be inside the plan period")
        activity = None
        if payload.source_type != "independent":
            if not payload.activity_id:
                raise HTTPException(422, "An external Daily Work item requires an activity")
            activity = (await self.session.execute(text(
                "SELECT * FROM pm_activities WHERE id=:a AND project_id=:p AND deleted_at IS NULL"
            ), {"a": payload.activity_id.hex, "p": project_id})).mappings().first()
            if not activity:
                raise HTTPException(422, "Activity must belong to the project")
        elif payload.activity_id or payload.work_order_id or not payload.assignee_user_id:
            raise HTTPException(422, "Independent work requires an owner and no external source")
        if payload.emergency_flag and not payload.emergency_reason.strip():
            raise HTTPException(422, "Emergency work requires a reason")
        target = decimal(payload.target_quantity, name="target_quantity")
        minutes = decimal(payload.planned_minutes, name="planned_minutes")
        if activity and payload.unit and activity["unit"] and payload.unit != activity["unit"]:
            raise HTTPException(422, "Daily unit must match the PM activity unit")
        activity_id = payload.activity_id.hex if payload.activity_id else None
        work_order_id = payload.work_order_id.hex if payload.work_order_id else None
        duplicate = await self.session.scalar(text(
            "SELECT 1 FROM dw_daily_work_items WHERE plan_id=:p AND work_date=:d AND deleted_at IS NULL "
            "AND emergency_flag=0 AND ((:source='independent' AND source_type='independent' AND title=:title) "
            "OR (:source<>'independent' AND activity_id=:a AND COALESCE(work_order_id,'')=COALESCE(:w,'')))"
        ), {"p": plan_id, "d": payload.work_date.isoformat(), "source": payload.source_type,
            "title": payload.title, "a": activity_id, "w": work_order_id})
        if duplicate and not payload.emergency_flag:
            raise HTTPException(409, "The item is already present in this plan for the work date")
        owner_id = payload.assignee_user_id.hex if payload.assignee_user_id else None
        if payload.source_type == "independent":
            owner = await self.session.scalar(text(
                "SELECT 1 FROM users WHERE id=:id AND organization_id=:org AND is_active=1"
            ), {"id": owner_id, "org": plan["organization_id"]})
            if not owner:
                raise HTTPException(422, "Independent work owner must be active in the plan organization")
        source_type = "independent" if payload.source_type == "independent" else ("pm_work_order" if work_order_id else "pm_activity")
        if work_order_id:
            matching = await self.session.scalar(text(
                "SELECT 1 FROM pm_work_orders WHERE id=:w AND project_id=:p AND activity_id=:a AND deleted_at IS NULL"
            ), {"w": work_order_id, "p": project_id, "a": activity_id})
            if not matching:
                raise HTTPException(422, "Work order must match the activity and project")
        item_id = uuid4().hex
        values = {
            "id": item_id, "plan_id": plan_id, "project_id": project_id, "activity_id": activity_id,
            "work_order_id": work_order_id, "work_date": payload.work_date.isoformat(), "title": payload.title,
            "target_quantity": str(target), "unit": payload.unit or (activity["unit"] if activity else ""),
            "assignee_user_id": owner_id, "organization_id": plan["organization_id"],
            "source_id": None if source_type == "independent" else activity_id, "source_type": source_type,
            "team_name": payload.team_name, "shift": payload.shift, "location": payload.location,
            "emergency_flag": 1 if payload.emergency_flag else 0, "emergency_reason": payload.emergency_reason,
            "planned_minutes": str(minutes), "notes": payload.notes,
            "created_by": self.request.state.user_id.hex, "updated_at": now(),
        }
        await self.session.execute(text(
            "INSERT INTO dw_daily_work_items (" + ",".join(values) + ") VALUES (" + ",".join(":" + k for k in values) + ")"
        ), values)
        return await self.metrics(project_id, item_id)

    async def add_estimate(self, project_id, item_id, payload):
        item = await self.item(project_id, item_id, "daily_work.manage")
        if item["commitment_status"] == "committed":
            raise HTTPException(409, "Committed item estimates are immutable")
        if payload.estimate_kind not in {"labor", "equipment", "material", "expense"}:
            raise HTTPException(422, "Unsupported estimate kind")
        if payload.confidence not in {"high", "medium", "low"}:
            raise HTTPException(422, "Unsupported estimate confidence")
        currency = await self.session.scalar(text(
            "SELECT 1 FROM core_currencies WHERE code=:code AND is_active=1"
        ), {"code": payload.currency_id})
        if not currency:
            raise HTTPException(422, "Unknown active currency")
        quantity, rate = decimal(payload.quantity, name="quantity"), decimal(payload.unit_rate, name="unit_rate")
        fx = decimal(payload.fx_rate, name="fx_rate", non_negative=False)
        if fx <= ZERO:
            raise HTTPException(422, "fx_rate must be positive")
        estimate_id = uuid4().hex
        await self.session.execute(text(
            "UPDATE dw_work_item_estimates SET is_current=0 WHERE daily_work_id=:i AND estimate_kind=:k AND is_current=1"
        ), {"i": item_id, "k": payload.estimate_kind})
        await self.session.execute(text(
            "INSERT INTO dw_work_item_estimates (id,daily_work_id,estimate_kind,quantity,unit,unit_rate,currency_id,fx_rate,fx_as_of,confidence,created_by) "
            "VALUES(:id,:i,:k,:q,:u,:r,:c,:fx,:asof,:confidence,:by)"
        ), {"id": estimate_id, "i": item_id, "k": payload.estimate_kind, "q": str(quantity), "u": payload.unit,
            "r": str(rate), "c": payload.currency_id, "fx": str(fx), "asof": payload.fx_as_of.isoformat(),
            "confidence": payload.confidence, "by": self.request.state.user_id.hex})
        rows = (await self.session.execute(text(
            "SELECT quantity,unit_rate,fx_rate FROM dw_work_item_estimates WHERE daily_work_id=:i AND is_current=1"
        ), {"i": item_id})).mappings()
        total = money(sum((decimal(r["quantity"], name="quantity") * decimal(r["unit_rate"], name="unit_rate") * decimal(r["fx_rate"], name="fx_rate", non_negative=False) for r in rows), ZERO))
        await self.session.execute(text(
            "UPDATE dw_daily_work_items SET estimate_total=:total,estimated_cost_status='available',currency_id=:currency,updated_at=:at WHERE id=:id"
        ), {"total": str(total), "currency": payload.currency_id, "at": now(), "id": item_id})
        return {"id": estimate_id, "estimate_total": str(total), "line_total": str(money(quantity * rate * fx))}

    async def record_actual(self, project_id, item_id, payload):
        item = await self.item(project_id, item_id, "daily_work.manage")
        if item["source_type"] != "independent":
            raise HTTPException(409, "EXTERNAL_ACTUAL_OWNER")
        existing = await self.session.scalar(text("SELECT id FROM dw_work_item_updates WHERE idempotency_key=:key"), {"key": payload.idempotency_key})
        if existing:
            return await self.metrics(project_id, item_id)
        value = decimal(payload.value, name="actual_value")
        if payload.event_type == "quantity" and payload.unit and payload.unit != item["unit"]:
            raise HTTPException(422, "Actual unit must match the independent item unit")
        if payload.event_type == "time" and value != value.to_integral_value():
            raise HTTPException(422, "Actual minutes must be an integer")
        if payload.event_type == "cost":
            if not payload.currency_id:
                raise HTTPException(422, "Actual cost requires a currency")
            active = await self.session.scalar(text("SELECT 1 FROM core_currencies WHERE code=:code AND is_active=1"), {"code": payload.currency_id})
            if not active:
                raise HTTPException(422, "Unknown active currency")
        occurred = payload.occurred_at or now()
        await self.session.execute(text(
            "INSERT INTO dw_work_item_updates(id,daily_work_id,event_type,quantity_delta,minutes_delta,cost_delta,unit,currency_id,fx_rate,fx_as_of,idempotency_key,occurred_at,business_date,actor_user_id,note,source_type) "
            "VALUES(:id,:item,:kind,:quantity,:minutes,:cost,:unit,:currency,:fx,:asof,:key,:occurred,:date,:actor,:note,'independent')"
        ), {"id": uuid4().hex, "item": item_id, "kind": payload.event_type,
            "quantity": str(value) if payload.event_type == "quantity" else None,
            "minutes": int(value) if payload.event_type == "time" else None,
            "cost": str(money(value * payload.fx_rate)) if payload.event_type == "cost" else None,
            "unit": payload.unit, "currency": payload.currency_id, "fx": str(payload.fx_rate),
            "asof": occurred[:10], "key": payload.idempotency_key, "occurred": occurred,
            "date": occurred[:10], "actor": self.request.state.user_id.hex, "note": payload.note})
        return await self.metrics(project_id, item_id)

    async def commit(self, project_id, plan_id):
        await self.project(project_id, "daily_work.manage")
        plan = await self.plan(project_id, plan_id)
        if plan["status"] != "draft":
            raise HTTPException(409, "Only draft plans can be committed")
        items = (await self.session.execute(text("SELECT * FROM dw_daily_work_items WHERE plan_id=:p AND deleted_at IS NULL"), {"p": plan_id})).mappings().all()
        if not items:
            raise HTTPException(409, "Cannot commit an empty plan")
        at = now()
        for item in items:
            await self.session.execute(text("UPDATE dw_daily_work_items SET committed_quantity=target_quantity,committed_minutes=planned_minutes,commitment_status='committed',status=CASE WHEN status='planned' THEN 'ready' ELSE status END,updated_at=:at WHERE id=:id"), {"at": at, "id": item["id"]})
        await self.session.execute(text("UPDATE dw_work_plans SET status='committed',committed_at=:at,updated_at=:at WHERE id=:id"), {"at": at, "id": plan_id})
        self.audit("commit", plan_id, dict(plan), {"status": "committed", "item_count": len(items)})
        return await self.plan(project_id, plan_id)

    async def close(self, project_id, plan_id, payload):
        plan = await self.project_plan(project_id, plan_id, "daily_work.review")
        if plan["status"] not in ("committed", "in_progress"):
            raise HTTPException(409, "Only committed or in-progress plans can be closed")
        if await self.session.scalar(text("SELECT id FROM dw_plan_closures WHERE plan_id=:id AND closure_version=:v"), {"id": plan_id, "v": plan["version"]}):
            raise HTTPException(409, "Plan version already has a closure")
        items = (await self.session.execute(text("SELECT * FROM dw_daily_work_items WHERE plan_id=:id AND deleted_at IS NULL"), {"id": plan_id})).mappings().all()
        independent = [i for i in items if i["source_type"] == "independent"]
        external = [i for i in items if i["source_type"] != "independent"]
        aq, at, ac = await self.actual_totals([i["id"] for i in independent])
        coverage = {"independent_items": len(independent), "external_items": len(external), "actual_external": "unavailable" if external else "not_applicable"}
        closure_id = uuid4().hex
        await self.session.execute(text("INSERT INTO dw_plan_closures(id,plan_id,closure_version,planned_count,committed_count,completed_count,blocked_count,carryover_count,planned_quantity_snapshot,actual_quantity_snapshot,planned_minutes_snapshot,actual_minutes_snapshot,planned_cost_snapshot,actual_cost_snapshot,coverage_json,closed_by,summary) VALUES(:id,:plan,:v,:planned,:committed,:completed,:blocked,0,:pq,:aq,:pm,:at,:pc,:ac,:coverage,:by,:summary)"), {
            "id": closure_id, "plan": plan_id, "v": plan["version"], "planned": len(items), "committed": sum(i["commitment_status"] == "committed" for i in items), "completed": sum(i["status"] == "completed" for i in items), "blocked": sum(i["status"] == "blocked" for i in items), "pq": str(sum((decimal(i["target_quantity"], name="target_quantity") for i in items), ZERO)), "aq": str(aq) if not external else None, "pm": str(sum((decimal(i["planned_minutes"], name="planned_minutes") for i in items), ZERO)), "at": int(at) if not external else None, "pc": str(sum((decimal(i["estimate_total"], name="estimate_total") for i in items), ZERO)), "ac": str(ac) if independent and not external else None, "coverage": json.dumps(coverage), "by": self.request.state.user_id.hex, "summary": payload.summary})
        await self.session.execute(text("UPDATE dw_work_plans SET status='closed',closed_at=:at,updated_at=:at WHERE id=:id"), {"at": now(), "id": plan_id})
        self.audit("close", plan_id, dict(plan), {"closure_id": closure_id})
        return {"plan": await self.plan(project_id, plan_id), "closure_id": closure_id, "coverage": coverage}

    async def reopen(self, project_id, plan_id, payload):
        old = await self.project_plan(project_id, plan_id, "daily_work.review")
        if old["status"] != "closed":
            raise HTTPException(409, "Only closed plans can be reopened")
        new_id, version = uuid4().hex, int(old["version"]) + 1
        values = {"id": new_id, "organization_id": old["organization_id"], "scope_type": old["scope_type"], "scope_id": old["scope_id"], "project_id": project_id, "plan_date": old["plan_date"], "period_start": old["period_start"], "period_end": old["period_end"], "timezone_name_snapshot": old["timezone_name_snapshot"], "status": "draft", "version": version, "owner_user_id": old["owner_user_id"], "created_by": self.request.state.user_id.hex, "reopened_from_plan_id": plan_id, "reopen_reason": payload.reason, "updated_at": now()}
        await self.session.execute(text("INSERT INTO dw_work_plans (" + ",".join(values) + ") VALUES (" + ",".join(":" + k for k in values) + ")"), values)
        old_items = (await self.session.execute(text("SELECT * FROM dw_daily_work_items WHERE plan_id=:id AND deleted_at IS NULL AND source_type='independent'"), {"id": plan_id})).mappings().all()
        for item in old_items:
            aq, _, _ = await self.actual_totals([item["id"]])
            remaining = max(decimal(item["committed_quantity"], name="committed_quantity") - aq, ZERO)
            if remaining <= ZERO:
                continue
            clone = dict(item)
            clone.update({"id": uuid4().hex, "plan_id": new_id, "target_quantity": str(remaining), "committed_quantity": "0", "committed_minutes": "0", "commitment_status": "proposed", "status": "planned", "outcome_status": "carried_over", "carryover_of_id": item["id"], "created_by": self.request.state.user_id.hex, "created_at": now(), "updated_at": now(), "emergency_flag": 0, "emergency_reason": ""})
            cols = [k for k in clone if k != "id"]
            await self.session.execute(text("INSERT INTO dw_daily_work_items (id," + ",".join(cols) + ") VALUES (:id," + ",".join(":" + k for k in cols) + ")"), clone)
        self.audit("reopen", new_id, None, {"reopened_from_plan_id": plan_id, "version": version})
        return await self.plan(project_id, new_id)

    async def add_evidence(self, project_id, item_id, payload):
        item = await self.item(project_id, item_id, "daily_work.manage")
        key = payload.local_storage_key.replace("\\", "/")
        if ":" in key or "://" in key or key.startswith("/") or any(part == ".." for part in key.split("/")):
            raise HTTPException(422, "Evidence must use a relative local storage key")
        if await self.session.scalar(text("SELECT id FROM dw_work_item_evidence WHERE daily_work_id=:item AND sha256=:hash"), {"item": item["id"], "hash": payload.sha256.lower()}):
            raise HTTPException(409, "Evidence hash already exists for this item")
        evidence_id = uuid4().hex
        await self.session.execute(text("INSERT INTO dw_work_item_evidence(id,daily_work_id,evidence_type,local_storage_key,sha256,content_type,size_bytes,captured_at,captured_by) VALUES(:id,:item,:type,:key,:hash,:content,:size,:at,:by)"), {"id": evidence_id, "item": item["id"], "type": payload.evidence_type, "key": key, "hash": payload.sha256.lower(), "content": payload.content_type, "size": payload.size_bytes, "at": payload.captured_at or now(), "by": self.request.state.user_id.hex})
        return dict((await self.session.execute(text("SELECT * FROM dw_work_item_evidence WHERE id=:id"), {"id": evidence_id})).mappings().first())

    async def actual_totals(self, item_ids):
        if not item_ids:
            return ZERO, ZERO, ZERO
        params = {f"i{n}": value for n, value in enumerate(item_ids)}
        bind = ",".join(f":i{n}" for n in range(len(item_ids)))
        rows = (await self.session.execute(text(f"SELECT event_type,quantity_delta,minutes_delta,cost_delta FROM dw_work_item_updates WHERE daily_work_id IN ({bind}) AND source_type='independent'"), params)).mappings().all()
        q = sum((decimal(r["quantity_delta"] or 0, name="actual_quantity") for r in rows if r["event_type"] == "quantity"), ZERO)
        t = sum((Decimal(r["minutes_delta"] or 0) for r in rows if r["event_type"] == "time"), ZERO)
        c = sum((decimal(r["cost_delta"] or 0, name="actual_cost") for r in rows if r["event_type"] == "cost"), ZERO)
        return q, t, c

    async def assignments(self, project_id, item_id):
        item = await self.item(project_id, item_id, "daily_work.view")
        rows = (await self.session.execute(text(
            "SELECT * FROM dw_work_item_assignments WHERE daily_work_id=:id "
            "AND status<>'released' ORDER BY is_lead DESC, created_at"
        ), {"id": item["id"]})).mappings().all()
        return {"item_id": item["id"], "assignments": [dict(row) for row in rows]}

    async def add_assignment(self, project_id, item_id, payload):
        item = await self.item(project_id, item_id, "daily_work.manage")
        if item["commitment_status"] == "committed":
            raise HTTPException(409, "Committed item assignments are immutable")
        if payload.subject_type == "user":
            active = await self.session.scalar(text(
                "SELECT 1 FROM users WHERE id=:id AND organization_id=:org AND is_active=1"
            ), {"id": payload.subject_id.replace("-", ""), "org": item["organization_id"]})
            if not active:
                raise HTTPException(422, "Assigned user must be active in the item organization")
        duplicate = await self.session.scalar(text(
            "SELECT id FROM dw_work_item_assignments WHERE daily_work_id=:item "
            "AND subject_type=:type AND subject_id=:subject AND status<>'released'"
        ), {"item": item_id, "type": payload.subject_type, "subject": payload.subject_id})
        if duplicate:
            raise HTTPException(409, "Assignment already exists for this item")
        assignment_id = uuid4().hex
        await self.session.execute(text(
            "INSERT INTO dw_work_item_assignments "
            "(id,daily_work_id,subject_type,subject_id,role,is_lead,planned_minutes,created_by) "
            "VALUES(:id,:item,:type,:subject,:role,:lead,:minutes,:by)"
        ), {"id": assignment_id, "item": item_id, "type": payload.subject_type,
            "subject": payload.subject_id, "role": payload.role, "lead": 1 if payload.is_lead else 0,
            "minutes": str(payload.planned_minutes), "by": self.request.state.user_id.hex})
        self.audit("assign", assignment_id, None, {"daily_work_id": item_id, "subject_type": payload.subject_type, "subject_id": payload.subject_id})
        return dict((await self.session.execute(text(
            "SELECT * FROM dw_work_item_assignments WHERE id=:id"), {"id": assignment_id})).mappings().first())

    async def item(self, project_id, item_id, permission):
        require(self.request, permission)
        row = (await self.session.execute(text("SELECT * FROM dw_daily_work_items WHERE id=:id AND project_id=:p AND deleted_at IS NULL"), {"id": item_id, "p": project_id})).mappings().first()
        if not row:
            raise HTTPException(404, "Daily work item unavailable")
        await self.project(project_id, permission)
        return dict(row)

    async def metrics(self, project_id, item_id):
        item = await self.item(project_id, item_id, "daily_work.view")
        estimates = (await self.session.execute(text("SELECT * FROM dw_work_item_estimates WHERE daily_work_id=:i AND is_current=1 ORDER BY estimate_kind"), {"i": item_id})).mappings().all()
        events = (await self.session.execute(text(
            "SELECT event_type,quantity_delta,minutes_delta,cost_delta FROM dw_work_item_updates "
            "WHERE daily_work_id=:i AND source_type='independent'"
        ), {"i": item_id})).mappings().all()
        has_quantity = any(row["event_type"] == "quantity" for row in events)
        has_time = any(row["event_type"] == "time" for row in events)
        has_cost = any(row["event_type"] == "cost" for row in events)
        if item["source_type"] == "independent":
            actual_q, actual_t, actual_c = await self.actual_totals([item_id])
            volume = {"planned": item["target_quantity"], "committed": item["committed_quantity"], "actual": str(actual_q), "unit": item["unit"], "coverage": "complete" if has_quantity else "planned_only"}
            time = {"planned_minutes": item["planned_minutes"], "committed_minutes": item["committed_minutes"], "actual_minutes": int(actual_t) if has_time else None, "coverage": "complete" if has_time else "unavailable"}
            cost = {"estimated": item["estimate_total"], "committed": item["estimate_total"] if item["commitment_status"] == "committed" else None, "actual": str(money(actual_c)) if has_cost else None, "coverage": "complete" if has_cost else "unavailable"}
        else:
            external_actual = None
            external_coverage = "unavailable"
            if item["work_order_id"]:
                work_order = await ExecutionService(self.session, self.request)._work_order(item["work_order_id"], project_id)
                external_actual = str(work_order["actual_quantity_snapshot"])
                external_coverage = "external_source"
            volume = {"planned": item["target_quantity"], "committed": item["committed_quantity"], "actual": external_actual, "unit": item["unit"], "coverage": external_coverage}
            time = {"planned_minutes": item["planned_minutes"], "committed_minutes": item["committed_minutes"], "actual_minutes": None, "coverage": external_coverage}
            cost = {"estimated": item["estimate_total"], "committed": item["estimate_total"] if item["commitment_status"] == "committed" else None, "actual": None, "coverage": "unavailable"}
        target = decimal(volume["planned"], name="target_quantity")
        actual = decimal(volume["actual"], name="actual_quantity") if volume["actual"] is not None else None
        planned_minutes = decimal(time["planned_minutes"], name="planned_minutes")
        actual_minutes = Decimal(str(time["actual_minutes"])) if time["actual_minutes"] is not None else None
        estimated = decimal(cost["estimated"], name="estimate_total") if cost["estimated"] is not None else None
        actual_cost = decimal(cost["actual"], name="actual_cost") if cost["actual"] is not None else None
        completion = (actual / target * Decimal("100")) if actual is not None and target > ZERO else None
        remaining = max(target - actual, ZERO) if actual is not None else None
        expected = self._expected_by_now(item, target)
        cost_forecast = None
        if actual_cost is not None and actual is not None and actual > ZERO and target > ZERO:
            cost_forecast = money(actual_cost / actual * target)
        work_duration = self._calendar_duration(item)
        control = {
            "completion_percent": str(completion.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) if completion is not None else None,
            "remaining_quantity": str(remaining) if remaining is not None else None,
            "expected_quantity_by_now": str(expected) if expected is not None else None,
            "volume_variance": str(actual - expected) if actual is not None and expected is not None else None,
            "resource_minutes_variance": str(actual_minutes - planned_minutes) if actual_minutes is not None else None,
            "planned_work_duration_minutes": work_duration,
            "resource_productivity_actual": str((actual / actual_minutes).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) if actual is not None and actual_minutes and actual_minutes > ZERO else None,
            "resource_productivity_planned": str((target / planned_minutes).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) if target > ZERO and planned_minutes > ZERO else None,
            "cost_variance": str(money(actual_cost - estimated)) if actual_cost is not None and estimated is not None else None,
            "cost_forecast_at_completion": str(cost_forecast) if cost_forecast is not None else None,
            "alerts": self._alerts(volume, time, cost, expected),
        }
        return {"item": item, "volume": volume, "time": time, "cost": cost, "control": control, "estimates": [dict(row) for row in estimates], "is_comparable": True}

    @staticmethod
    def _calendar_duration(item):
        start, end = item.get("planned_start_at"), item.get("planned_end_at")
        if not start or not end:
            return None
        try:
            return max(0, int((datetime.fromisoformat(str(end).replace("Z", "+00:00")) - datetime.fromisoformat(str(start).replace("Z", "+00:00"))).total_seconds() // 60))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _expected_by_now(item, target):
        if item.get("source_type") != "independent":
            return None
        today = date.today().isoformat()
        work_date = str(item.get("work_date") or "")
        if not work_date:
            return None
        if work_date < today:
            return target
        if work_date > today:
            return ZERO
        # A date-only daily plan has no authoritative work window. Use elapsed
        # civil day as a transparent expectation, never as an actual value.
        ratio = Decimal(datetime.now().hour * 60 + datetime.now().minute) / Decimal("1440")
        return (target * ratio).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _alerts(volume, time, cost, expected):
        alerts = []
        if volume["actual"] is not None and expected is not None and decimal(volume["actual"], name="actual") < expected:
            alerts.append({"code": "volume_behind", "severity": "warning"})
        if time["actual_minutes"] is not None and decimal(time["actual_minutes"], name="actual_minutes") > decimal(time["planned_minutes"], name="planned_minutes"):
            alerts.append({"code": "resource_time_overrun", "severity": "warning"})
        if cost["actual"] is not None and decimal(cost["estimated"], name="estimated") < decimal(cost["actual"], name="actual_cost"):
            alerts.append({"code": "cost_overrun", "severity": "critical"})
        if cost["coverage"] == "unavailable":
            alerts.append({"code": "cost_coverage_unavailable", "severity": "info"})
        return alerts

    async def plan_control(self, project_id, plan_id):
        plan = await self.project_plan(project_id, plan_id, "daily_work.view")
        rows = (await self.session.execute(text(
            "SELECT id FROM dw_daily_work_items WHERE plan_id=:p AND deleted_at IS NULL ORDER BY created_at"
        ), {"p": plan_id})).mappings().all()
        item_metrics = [await self.metrics(project_id, row["id"]) for row in rows]
        def dec(path, obj):
            value = obj
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            return decimal(value, name="control") if value is not None else None
        target = sum((dec(("volume", "planned"), m) or ZERO for m in item_metrics), ZERO)
        actual_values = [dec(("volume", "actual"), m) for m in item_metrics]
        actual = sum((x or ZERO for x in actual_values), ZERO) if all(x is not None for x in actual_values) else None
        estimated = sum((dec(("cost", "estimated"), m) or ZERO for m in item_metrics), ZERO)
        cost_values = [dec(("cost", "actual"), m) for m in item_metrics]
        actual_cost = sum(cost_values, ZERO) if all(x is not None for x in cost_values) and cost_values else None
        alerts = [dict(alert, item_id=m["item"]["id"]) for m in item_metrics for alert in m["control"]["alerts"]]
        return {"plan": plan, "items": item_metrics, "summary": {
            "item_count": len(item_metrics), "planned_quantity": str(target),
            "actual_quantity": str(actual) if actual is not None else None,
            "estimated_cost": str(money(estimated)), "actual_cost": str(money(actual_cost)) if actual_cost is not None else None,
            "cost_coverage": "complete" if actual_cost is not None else "partial_or_unavailable",
            "alerts_count": len(alerts),
        }, "alerts": alerts}

    def audit(self, action, entity_id, old, new):
        if self.request is not None:
            self.request.state.audit_details = {"entity_type": "daily_work." + action, "entity_id": str(UUID(entity_id)), "old": old, "new": new, "summary": "DW planning " + action}
