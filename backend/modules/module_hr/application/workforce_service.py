from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.access import require, unit_scope
from .unit_scope import require_unit, unit_filter


LIVE_ASSIGNMENT_STATUSES = ("approved", "active")


class WorkforceService:
    def __init__(self, session, request):
        self.session = session
        self.request = request

    def _organization(self, requested=None, permission="hr.workforce.view"):
        actor_org = self.request.state.user.organization_id.hex
        if requested is None:
            return actor_org
        scopes = self.request.state.permission_scopes.get(permission, {"self"})
        if self.request.state.is_admin:
            return requested
        if self.request.state.permission_unit_scopes.get(permission) and requested != actor_org:
            raise HTTPException(403, "Outside assigned data scope")
        if ("institution" in self.request.state.permission_global_scopes.get(permission, set())
                and unit_scope(self.request, permission) is None):
            return requested
        if requested != actor_org:
            raise HTTPException(403, "Outside assigned data scope")
        return actor_org

    async def _unit(self, unit_id, organization_id, permission="hr.workforce.view"):
        exists = bool(await self.session.scalar(text(
            "WITH RECURSIVE units(id,path) AS ("
            "SELECT id,'|'||id||'|' FROM organizations WHERE id=:org AND is_active=1 "
            "UNION ALL SELECT child.id,units.path||child.id||'|' FROM organizations child "
            "JOIN units ON child.parent_id=units.id WHERE child.is_active=1 "
            "AND instr(units.path,'|'||child.id||'|')=0) "
            "SELECT 1 FROM units WHERE id=:unit"
        ), {"unit": unit_id, "org": organization_id}))
        if exists:
            require_unit(self.request, permission, unit_id)
        return exists

    async def _require_active_employee_for_period(self, employee_id, organization_id, business_date, start_at, end_at):
        start_day = date.fromisoformat(business_date)
        if start_at:
            start_day = min(start_day, datetime.fromisoformat(start_at).date())
        last_day = start_day
        if end_at:
            end = datetime.fromisoformat(end_at)
            last_day = max(start_day, (end - timedelta(microseconds=1)).date())
        rows = (await self.session.execute(text(
            "SELECT change_type,effective_date FROM hr_employment_records "
            "WHERE employee_id=:employee AND organization_id=:org AND status='approved' AND is_current=1 "
            "ORDER BY effective_date,id"
        ), {"employee": employee_id, "org": organization_id})).mappings().all()
        events = [(date.fromisoformat(row["effective_date"]), row["change_type"]) for row in rows]
        if not events or not any(kind == "hire" and effective <= start_day for effective, kind in events):
            raise HTTPException(409, "Employee is not employed for the assignment period")

        checkpoints = {start_day}
        checkpoints.update(effective for effective, _ in events if start_day < effective <= last_day)
        for checkpoint in sorted(checkpoints):
            status = None
            for effective, kind in events:
                if effective > checkpoint:
                    break
                if kind in ("hire", "reinstatement"):
                    status = "active"
                elif kind == "suspension":
                    status = "suspended"
                elif kind == "termination":
                    status = "terminated"
            if status != "active":
                raise HTTPException(409, "Employee is not active throughout the assignment period")

    async def _row(self, table, entity_id, organization_id, label, permission="hr.workforce.view"):
        row = (await self.session.execute(text(
            f"SELECT * FROM {table} WHERE id=:id AND organization_id=:org"
        ), {"id": entity_id, "org": organization_id})).mappings().first()
        if row is None:
            raise HTTPException(404, f"{label} unavailable within assigned scope")
        unit_column = {
            "hr_employees": "home_unit_id",
            "hr_field_tasks": "owner_unit_id",
            "hr_workforce_requests": "requesting_unit_id",
            "hr_assignments": "beneficiary_unit_id",
        }.get(table)
        if unit_column:
            require_unit(self.request, permission, row[unit_column], status_code=404)
        if table == "hr_workforce_requests" and row["task_id"]:
            task_unit = await self.session.scalar(text(
                "SELECT owner_unit_id FROM hr_field_tasks WHERE id=:task AND organization_id=:org"
            ), {"task": row["task_id"], "org": organization_id})
            if task_unit:
                require_unit(self.request, permission, task_unit, status_code=404)
        if table == "hr_assignments":
            related_units = (await self.session.execute(text(
                "SELECT e.home_unit_id,t.owner_unit_id,r.requesting_unit_id "
                "FROM hr_employees e "
                "LEFT JOIN hr_field_tasks t ON t.id=:task AND t.organization_id=:org "
                "LEFT JOIN hr_workforce_requests r ON r.id=:request AND r.organization_id=:org "
                "WHERE e.id=:employee AND e.organization_id=:org"
            ), {"employee": row["employee_id"], "task": row["task_id"],
                "request": row["request_id"], "org": organization_id})).first()
            if related_units:
                for related_unit in related_units:
                    if related_unit:
                        require_unit(self.request, permission, related_unit, status_code=404)
        return dict(row)

    @staticmethod
    def _timestamp(value, field):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            raise HTTPException(422, f"Invalid {field}")
        if parsed.tzinfo is None:
            raise HTTPException(422, f"{field} must include a timezone")
        return parsed.astimezone(timezone.utc).isoformat()

    async def create_task(self, payload):
        require(self.request, "hr.task.manage")
        org = self._organization(payload.get("organization_id"), "hr.task.manage")
        if not await self._unit(payload["owner_unit_id"], org, "hr.task.manage"):
            raise HTTPException(422, "Task owner unit is unavailable within organization")
        start, end = payload.get("planned_start_at"), payload.get("planned_end_at")
        if bool(start) != bool(end):
            raise HTTPException(422, "Task planned timestamps must be supplied together")
        if start:
            start, end = self._timestamp(start, "planned_start_at"), self._timestamp(end, "planned_end_at")
            if end <= start:
                raise HTTPException(422, "Task planned end must follow start")
        task_id = uuid4().hex
        try:
            await self.session.execute(text(
                "INSERT INTO hr_field_tasks(id,organization_id,task_no,title,description,owner_unit_id,business_date,planned_start_at,planned_end_at,location_text,status) "
                "VALUES(:id,:org,:no,:title,:description,:unit,:business_date,:start,:end,:location,'draft')"
            ), dict(id=task_id, org=org, no=payload["task_no"].strip(), title=payload["title"].strip(),
                    description=payload.get("description", "").strip(), unit=payload["owner_unit_id"],
                    business_date=payload["business_date"], start=start, end=end,
                    location=payload.get("location_text", "").strip()))
        except IntegrityError as exc:
            if "UNIQUE" in str(exc).upper():
                raise HTTPException(409, "Task number already exists within organization") from None
            raise
        task = await self._row("hr_field_tasks", task_id, org, "Task", "hr.task.manage")
        self._audit("hr.field_tasks", task_id, None, task, "HR field task created")
        return task

    async def transition_task(self, entity_id, data):
        require(self.request, "hr.task.manage")
        org = self._organization(permission="hr.task.manage")
        task = await self._row("hr_field_tasks", entity_id, org, "Task", "hr.task.manage")
        transitions = {
            ("draft", "ready"): "ready",
            ("ready", "start"): "in_progress",
            ("ready", "complete"): "completed",
            ("in_progress", "complete"): "completed",
            ("draft", "cancel"): "cancelled",
            ("ready", "cancel"): "cancelled",
            ("completed", "archive"): "archived",
            ("cancelled", "archive"): "archived",
        }
        target = transitions.get((task["status"], data["action"]))
        if not target:
            raise HTTPException(409, "Task transition is not allowed")
        reason = data.get("reason", "").strip()
        if data["action"] in ("cancel", "archive") and not reason:
            raise HTTPException(422, "A reason is required for cancellation or archival")
        if target == "in_progress" and not task["planned_start_at"]:
            assignments = await self.session.scalar(text(
                "SELECT 1 FROM hr_assignments WHERE organization_id=:org AND task_id=:task "
                "AND status IN ('approved','active') LIMIT 1"
            ), {"org": org, "task": entity_id})
            if not assignments:
                raise HTTPException(409, "Starting a task requires a scheduled period or approved assignment")
        if target in ("completed", "cancelled"):
            active = await self.session.scalar(text(
                "SELECT 1 FROM hr_assignments WHERE organization_id=:org AND task_id=:task "
                "AND status IN ('pending','approved','active') LIMIT 1"
            ), {"org": org, "task": entity_id})
            if active:
                raise HTTPException(409, "Resolve pending or active assignments before completing or cancelling")
        result = await self.session.execute(text(
            "UPDATE hr_field_tasks SET status=:status,state_reason=:reason,row_version=row_version+1,updated_at=:now "
            "WHERE id=:id AND organization_id=:org AND row_version=:version"
        ), dict(status=target, reason=reason, now=datetime.now(timezone.utc).isoformat(),
                id=entity_id, org=org, version=data["row_version"]))
        if result.rowcount != 1:
            raise HTTPException(409, "Task changed; reload before transition")
        updated = await self._row("hr_field_tasks", entity_id, org, "Task", "hr.task.manage")
        self._audit("hr.field_tasks", entity_id, task, updated, "HR task transitioned")
        return updated

    async def create_request(self, payload):
        require(self.request, "hr.workforce.request")
        org = self._organization(payload.get("organization_id"), "hr.workforce.request")
        if not await self._unit(payload["requesting_unit_id"], org, "hr.workforce.request"):
            raise HTTPException(422, "Requesting unit is unavailable within organization")
        start, end = self._timestamp(payload["start_at"], "start_at"), self._timestamp(payload["end_at"], "end_at")
        if end <= start:
            raise HTTPException(422, "Request end must follow start")
        task_id = payload.get("task_id")
        if task_id:
            await self._row("hr_field_tasks", task_id, org, "Task", "hr.workforce.request")
        request_id = uuid4().hex
        await self.session.execute(text(
            "INSERT INTO hr_workforce_requests(id,organization_id,request_no,requesting_unit_id,task_id,requested_position,headcount,start_at,end_at,priority,purpose,status,requested_by_user_id,approved_by_user_id,approved_at) "
            "VALUES(:id,:org,:no,:unit,:task,:position,:headcount,:start,:end,:priority,:purpose,'draft',:user,NULL,NULL)"
        ), dict(id=request_id, org=org, no=payload["request_no"].strip(), unit=payload["requesting_unit_id"], task=task_id,
                position=payload.get("requested_position", "").strip(), headcount=payload["headcount"], start=start, end=end,
                priority=payload.get("priority", "normal"), purpose=payload["purpose"].strip(),
                user=self.request.state.user_id.hex))
        row = await self._row("hr_workforce_requests", request_id, org, "Workforce request", "hr.workforce.request")
        self._audit("hr.workforce_requests", request_id, None, row, "HR workforce request created")
        return await self.request_coverage(request_id, org)

    async def transition_request(self, entity_id, data):
        action = data["action"]
        require(self.request, "hr.workforce.request" if action == "submit" else "hr.workforce.approve")
        org = self._organization(
            permission="hr.workforce.request" if action == "submit" else "hr.workforce.approve"
        )
        row = await self._row(
            "hr_workforce_requests", entity_id, org, "Workforce request",
            "hr.workforce.request" if action == "submit" else "hr.workforce.approve"
        )
        transitions = {
            ("draft", "submit"): "submitted",
            ("submitted", "approve"): "approved",
            ("submitted", "reject"): "rejected",
            ("approved", "close"): "closed",
            ("partially_filled", "close"): "closed",
            ("filled", "close"): "closed",
            ("draft", "cancel"): "cancelled",
            ("submitted", "cancel"): "cancelled",
            ("approved", "cancel"): "cancelled",
            ("partially_filled", "cancel"): "cancelled",
            ("filled", "cancel"): "cancelled",
        }
        target = transitions.get((row["status"], action))
        if not target:
            raise HTTPException(409, "Workforce request transition is not allowed")
        reason = data.get("reason", "").strip()
        if action in ("reject", "close", "cancel") and not reason:
            raise HTTPException(422, "A reason is required for this transition")
        if action == "approve" and row["requested_by_user_id"] == self.request.state.user_id.hex:
            raise HTTPException(403, "Request approval must be performed by a different user")
        if action in ("close", "cancel"):
            active = await self.session.scalar(text(
                "SELECT 1 FROM hr_assignments WHERE organization_id=:org AND request_id=:request "
                "AND status IN ('approved','active') LIMIT 1"
            ), {"org": org, "request": entity_id})
            if active:
                raise HTTPException(409, "Resolve affected assignments before closing or cancelling the request")
        now = datetime.now(timezone.utc).isoformat()
        result = await self.session.execute(text(
            "UPDATE hr_workforce_requests SET status=:status,decision_note=:note,"
            "approved_by_user_id=:approver,approved_at=:approved_at,row_version=row_version+1,updated_at=:now "
            "WHERE id=:id AND organization_id=:org AND row_version=:version"
        ), dict(status=target, note=reason, approver=self.request.state.user_id.hex if action == "approve" else row["approved_by_user_id"],
                approved_at=now if action == "approve" else row["approved_at"], now=now,
                id=entity_id, org=org, version=data["row_version"]))
        if result.rowcount != 1:
            raise HTTPException(409, "Workforce request changed; reload before transition")
        updated = await self._row(
            "hr_workforce_requests", entity_id, org, "Workforce request",
            "hr.workforce.request" if action == "submit" else "hr.workforce.approve"
        )
        self._audit("hr.workforce_requests", entity_id, row, updated, "HR workforce request transitioned")
        return updated

    async def create_assignment(self, payload):
        require(self.request, "hr.assignment.manage")
        await self.session.execute(text("BEGIN IMMEDIATE"))
        org = self._organization(payload.get("organization_id"), "hr.assignment.manage")
        employee = await self._row(
            "hr_employees", payload["employee_id"], org, "Employee", "hr.assignment.manage"
        )
        if not await self._unit(payload["beneficiary_unit_id"], org, "hr.assignment.manage"):
            raise HTTPException(422, "Beneficiary unit is unavailable within organization")
        kind, exclusive = payload["assignment_kind"], payload.get("exclusivity", "exclusive")
        if kind not in ("direct_task", "supervision", "unit_allocation", "historical_import"):
            raise HTTPException(422, "Invalid assignment kind")
        if exclusive not in ("exclusive", "nonexclusive"):
            raise HTTPException(422, "Invalid assignment exclusivity")
        task_id, request_id = payload.get("task_id"), payload.get("request_id")
        if kind == "direct_task" and not task_id:
            raise HTTPException(422, "Direct task assignments require a task")
        if task_id:
            await self._row("hr_field_tasks", task_id, org, "Task", "hr.assignment.manage")
        request = await self._row(
            "hr_workforce_requests", request_id, org, "Workforce request", "hr.assignment.manage"
        ) if request_id else None
        if request and request["status"] not in ("approved", "partially_filled", "filled"):
            raise HTTPException(409, "Workforce request must be approved before assignment")
        start, end = payload.get("start_at"), payload.get("end_at")
        if kind == "historical_import":
            if start or end:
                raise HTTPException(422, "Historical import assignment must not have timestamps")
        else:
            start, end = self._timestamp(start, "start_at"), self._timestamp(end, "end_at")
            if end <= start:
                raise HTTPException(422, "Assignment end must follow start")
        await self._require_active_employee_for_period(
            payload["employee_id"], org, payload["business_date"], start, end
        )
        if request:
            if payload["beneficiary_unit_id"] != request["requesting_unit_id"]:
                raise HTTPException(422, "Assignment beneficiary must match workforce request unit")
            if request["task_id"] and task_id != request["task_id"]:
                raise HTTPException(422, "Assignment task must match workforce request task")
            if not (start < request["end_at"] and end > request["start_at"]):
                raise HTTPException(422, "Assignment must overlap workforce request period")
        assignment_id = uuid4().hex
        status = payload.get("status", "pending")
        if status not in ("approved", "draft", "pending"):
            raise HTTPException(422, "Assignments must be created as draft or pending")
        if status == "approved":
            raise HTTPException(422, "Assignments require a separate approval transition")
        await self.session.execute(text(
            "INSERT INTO hr_assignments(id,organization_id,employee_id,task_id,request_id,beneficiary_unit_id,assignment_kind,exclusivity,business_date,start_at,end_at,status,approved_by_user_id,approved_at,notes) "
            "VALUES(:id,:org,:employee,:task,:request,:unit,:kind,:exclusive,:business_date,:start,:end,:status,:approver,:approved_at,:notes)"
        ), dict(id=assignment_id, org=org, employee=payload["employee_id"], task=task_id, request=request_id,
                unit=payload["beneficiary_unit_id"], kind=kind, exclusive=exclusive, business_date=payload["business_date"],
                start=start, end=end, status=status,
                approver=None, approved_at=None,
                notes=payload.get("notes", "").strip()))
        assignment = await self._row("hr_assignments", assignment_id, org, "Assignment", "hr.assignment.manage")
        self._audit("hr.assignments", assignment_id, None, assignment, "HR assignment submitted")
        return assignment

    async def transition_assignment(self, entity_id, data):
        action = data["action"]
        require(self.request, "hr.assignment.approve" if action == "approve" else "hr.assignment.manage")
        await self.session.execute(text("BEGIN IMMEDIATE"))
        org = self._organization(
            permission="hr.assignment.approve" if action == "approve" else "hr.assignment.manage"
        )
        row = await self._row(
            "hr_assignments", entity_id, org, "Assignment",
            "hr.assignment.approve" if action == "approve" else "hr.assignment.manage"
        )
        reason = data.get("reason", "").strip()
        now = datetime.now(timezone.utc).isoformat()
        if action == "approve":
            if row["status"] != "pending":
                raise HTTPException(409, "Only pending assignments can be approved")
            employee = await self._row("hr_employees", row["employee_id"], org, "Employee", "hr.assignment.approve")
            await self._require_active_employee_for_period(
                row["employee_id"], org, row["business_date"], row["start_at"], row["end_at"]
            )
            task = await self._row(
                "hr_field_tasks", row["task_id"], org, "Task", "hr.assignment.approve"
            ) if row["task_id"] else None
            if task and task["status"] not in ("ready", "in_progress"):
                raise HTTPException(409, "Task must be ready or in progress before assignment approval")
            request = await self._row(
                "hr_workforce_requests", row["request_id"], org, "Workforce request", "hr.assignment.approve"
            ) if row["request_id"] else None
            if request and request["status"] not in ("approved", "partially_filled", "filled"):
                raise HTTPException(409, "Workforce request must be approved before assignment approval")
            if row["exclusivity"] == "exclusive" and row["start_at"]:
                overlap = await self.session.scalar(text(
                    "SELECT 1 FROM hr_assignments WHERE organization_id=:org AND employee_id=:employee "
                    "AND id<>:id AND exclusivity='exclusive' AND status IN ('approved','active') "
                    "AND start_at<:end AND end_at>:start LIMIT 1"
                ), dict(org=org, employee=row["employee_id"], id=entity_id,
                        start=row["start_at"], end=row["end_at"]))
                if overlap:
                    raise HTTPException(409, "Employee already has an overlapping exclusive assignment")
            result = await self.session.execute(text(
                "UPDATE hr_assignments SET status='approved',approved_by_user_id=:actor,approved_at=:now,"
                "row_version=row_version+1,updated_at=:now WHERE id=:id AND organization_id=:org "
                "AND status='pending' AND row_version=:version"
            ), dict(actor=self.request.state.user_id.hex, now=now, id=entity_id, org=org, version=data["row_version"]))
            if result.rowcount != 1:
                raise HTTPException(409, "Assignment changed; reload before approval")
            if request:
                coverage = await self._coverage(request)
                if any(item["covered_count"] > request["headcount"] for item in coverage["slices"]):
                    raise HTTPException(409, "Assignment would exceed workforce request headcount")
                await self.session.execute(text(
                    "UPDATE hr_workforce_requests SET status=:status,row_version=row_version+1,updated_at=:now "
                    "WHERE id=:id AND organization_id=:org AND status IN ('approved','partially_filled','filled')"
                ), dict(status=coverage["status"], now=now, id=request["id"], org=org))
            summary = "HR assignment approved"
        elif action == "submit":
            if row["status"] != "draft":
                raise HTTPException(409, "Only draft assignments can be submitted")
            result = await self.session.execute(text(
                "UPDATE hr_assignments SET status='pending',row_version=row_version+1,updated_at=:now "
                "WHERE id=:id AND organization_id=:org AND row_version=:version"
            ), dict(now=now, id=entity_id, org=org, version=data["row_version"]))
            if result.rowcount != 1:
                raise HTTPException(409, "Assignment changed; reload before submission")
            summary = "HR assignment submitted"
        elif action == "cancel":
            if not reason:
                raise HTTPException(422, "A reason is required to cancel an assignment")
            if row["status"] not in ("draft", "pending", "approved"):
                raise HTTPException(409, "Assignment cannot be cancelled in its current state")
            if row["status"] == "approved":
                attendance = await self.session.scalar(text(
                    "SELECT 1 FROM hr_attendance WHERE organization_id=:org AND assignment_id=:id "
                    "AND approval_status='approved' AND is_current=1 LIMIT 1"
                ), {"org": org, "id": entity_id})
                if attendance:
                    raise HTTPException(409, "Assignment with approved attendance requires a documented settlement")
            result = await self.session.execute(text(
                "UPDATE hr_assignments SET status='cancelled',approval_note=:reason,row_version=row_version+1,updated_at=:now "
                "WHERE id=:id AND organization_id=:org AND row_version=:version"
            ), dict(reason=reason, now=now, id=entity_id, org=org, version=data["row_version"]))
            if result.rowcount != 1:
                raise HTTPException(409, "Assignment changed; reload before cancellation")
            if row["request_id"]:
                request = await self._row(
                    "hr_workforce_requests", row["request_id"], org, "Workforce request",
                    "hr.assignment.manage"
                )
                if request["status"] in ("approved", "partially_filled", "filled"):
                    coverage = await self._coverage(request)
                    await self.session.execute(text(
                        "UPDATE hr_workforce_requests SET status=:status,row_version=row_version+1,updated_at=:now "
                        "WHERE id=:id AND organization_id=:org"
                    ), dict(status=coverage["status"], now=now, id=request["id"], org=org))
            summary = "HR assignment cancelled"
        else:
            raise HTTPException(422, "Unsupported assignment transition")
        updated = await self._row(
            "hr_assignments", entity_id, org, "Assignment",
            "hr.assignment.approve" if action == "approve" else "hr.assignment.manage"
        )
        self._audit("hr.assignments", entity_id, row, updated, summary)
        return updated

    async def _coverage(self, request, extra=None):
        rows = (await self.session.execute(text(
            "SELECT employee_id,start_at,end_at FROM hr_assignments WHERE organization_id=:org AND request_id=:request "
            "AND beneficiary_unit_id=:unit AND status IN ('approved','active') AND assignment_kind IN ('direct_task','supervision') "
            "AND start_at<:end AND end_at>:start"
        ), dict(org=request["organization_id"], request=request["id"], unit=request["requesting_unit_id"],
                start=request["start_at"], end=request["end_at"]))).mappings().all()
        intervals = [dict(row) for row in rows]
        if extra:
            intervals.append(extra)
        points = {request["start_at"], request["end_at"]}
        for row in intervals:
            points.add(max(row["start_at"], request["start_at"]))
            points.add(min(row["end_at"], request["end_at"]))
        ordered = sorted(points)
        slices = []
        for left, right in zip(ordered, ordered[1:]):
            employees = sorted({r["employee_id"] for r in intervals if r["start_at"] < right and r["end_at"] > left})
            slices.append({"start_at": left, "end_at": right, "covered_count": len(employees), "employee_ids": employees,
                           "uncovered": max(request["headcount"] - len(employees), 0)})
        counts = [part["covered_count"] for part in slices]
        status = "filled" if slices and all(count >= request["headcount"] for count in counts) else "partially_filled" if any(counts) else "approved"
        return {"headcount": request["headcount"], "status": status, "slices": slices}

    async def request_coverage(self, request_id, organization_id=None):
        require(self.request, "hr.workforce.view")
        org = organization_id or self._organization()
        request = await self._row("hr_workforce_requests", request_id, org, "Workforce request", "hr.workforce.view")
        coverage = await self._coverage(request)
        allowed_units = unit_scope(self.request, "hr.workforce.view")
        if allowed_units is not None:
            employee_ids = {
                employee_id
                for part in coverage["slices"]
                for employee_id in part["employee_ids"]
            }
            if employee_ids:
                params = {f"employee_{index}": value for index, value in enumerate(sorted(employee_ids))}
                params["org"] = org
                params.update({f"unit_{index}": value for index, value in enumerate(sorted(allowed_units))})
                employee_placeholders = ",".join(
                    f":employee_{index}" for index in range(len(employee_ids))
                )
                unit_placeholders = ",".join(
                    f":unit_{index}" for index in range(len(allowed_units))
                )
                visible = set((await self.session.execute(text(
                    "SELECT id FROM hr_employees WHERE organization_id=:org "
                    f"AND id IN ({employee_placeholders}) AND home_unit_id IN ({unit_placeholders})"
                ), params)).scalars())
            else:
                visible = set()
            for part in coverage["slices"]:
                part["employee_ids"] = [
                    employee_id for employee_id in part["employee_ids"] if employee_id in visible
                ]
        return {"request": request, "coverage": coverage}

    async def list_coverage(self):
        require(self.request, "hr.workforce.view")
        org = self._organization()
        request_params = {"org": org}
        request_scope = unit_filter(
            self.request, "hr.workforce.view", "requesting_unit_id", request_params
        )
        requests = (await self.session.execute(text(
            "SELECT * FROM hr_workforce_requests WHERE organization_id=:org" + request_scope
            + " ORDER BY created_at DESC"
        ), request_params)).mappings().all()
        assignment_params = {"org": org}
        assignment_scope = unit_filter(
            self.request, "hr.workforce.view", "a.beneficiary_unit_id", assignment_params
        )
        employee_scope = unit_filter(
            self.request, "hr.workforce.view", "e.home_unit_id", assignment_params,
            prefix="employee_unit"
        )
        assignments = (await self.session.execute(text(
            "SELECT a.request_id,a.beneficiary_unit_id,a.employee_id,a.start_at,a.end_at "
            "FROM hr_assignments a JOIN hr_employees e ON e.id=a.employee_id "
            "WHERE a.organization_id=:org AND a.status IN ('approved','active') "
            "AND a.assignment_kind IN ('direct_task','supervision')" + assignment_scope + employee_scope
        ), assignment_params)).mappings().all()
        results = []
        for request in requests:
            intervals = [
                dict(row) for row in assignments
                if row["request_id"] == request["id"]
                and row["beneficiary_unit_id"] == request["requesting_unit_id"]
                and row["start_at"] < request["end_at"]
                and row["end_at"] > request["start_at"]
            ]
            points = {request["start_at"], request["end_at"]}
            for row in intervals:
                points.add(max(row["start_at"], request["start_at"]))
                points.add(min(row["end_at"], request["end_at"]))
            slices = []
            ordered = sorted(points)
            for left, right in zip(ordered, ordered[1:]):
                employees = sorted({
                    row["employee_id"] for row in intervals
                    if row["start_at"] < right and row["end_at"] > left
                })
                slices.append({
                    "start_at": left,
                    "end_at": right,
                    "covered_count": len(employees),
                    "employee_ids": employees,
                    "uncovered": max(request["headcount"] - len(employees), 0),
                })
            counts = [item["covered_count"] for item in slices]
            status = (
                "filled" if slices and all(count >= request["headcount"] for count in counts)
                else "partially_filled" if any(counts) else "approved"
            )
            results.append({
                "request_id": request["id"],
                "coverage": {"headcount": request["headcount"], "status": status, "slices": slices},
            })
        return {"items": results}

    async def list_rows(self, table, employee_id=None, filters=None):
        permission = "hr.task.view" if table == "hr_field_tasks" else "hr.workforce.view"
        require(self.request, permission)
        if table not in {"hr_field_tasks", "hr_workforce_requests", "hr_assignments"}:
            raise ValueError("Unsupported HR list")
        org = self._organization(permission=permission)
        params = {"org": org}
        if table == "hr_assignments":
            beneficiary_scope = unit_filter(
                self.request, permission, "a.beneficiary_unit_id", params
            )
            employee_scope = unit_filter(
                self.request, permission, "e.home_unit_id", params, "employee_unit"
            )
            task_scope = self._optional_unit_filter(
                self.request, permission, "t.owner_unit_id", params, "task_unit"
            )
            request_scope = self._optional_unit_filter(
                self.request, permission, "r.requesting_unit_id", params, "request_unit"
            )
            query = (
                "SELECT a.* FROM hr_assignments a "
                "JOIN hr_employees e ON e.id=a.employee_id "
                "LEFT JOIN hr_field_tasks t ON t.id=a.task_id "
                "LEFT JOIN hr_workforce_requests r ON r.id=a.request_id "
                "WHERE a.organization_id=:org" + beneficiary_scope + employee_scope
                + task_scope + request_scope + (" AND a.employee_id=:employee" if employee_id else "")
                + " ORDER BY a.created_at DESC"
            )
        else:
            unit_column = (
                "owner_unit_id" if table == "hr_field_tasks" else "requesting_unit_id"
            )
            scoped = unit_filter(self.request, permission, unit_column, params)
            query = f"SELECT * FROM {table} WHERE organization_id=:org" + scoped
            if employee_id and table == "hr_assignments":
                query += " AND employee_id=:employee"
            if table == "hr_field_tasks" and filters:
                if filters.get("q"):
                    query += " AND (task_no LIKE :task_q OR title LIKE :task_q OR location_text LIKE :task_q)"
                    params["task_q"] = f"%{filters['q']}%"
                if filters.get("status"):
                    query += " AND status=:task_status"
                    params["task_status"] = filters["status"]
                if filters.get("business_date_from"):
                    query += " AND business_date>=:task_date_from"
                    params["task_date_from"] = filters["business_date_from"]
                if filters.get("business_date_to"):
                    query += " AND business_date<=:task_date_to"
                    params["task_date_to"] = filters["business_date_to"]
                if filters.get("unit_id"):
                    query += " AND owner_unit_id=:task_unit"
                    params["task_unit"] = filters["unit_id"]
            if table == "hr_workforce_requests" and filters:
                if filters.get("q"):
                    query += " AND (request_no LIKE :request_q OR requested_position LIKE :request_q OR purpose LIKE :request_q)"
                    params["request_q"] = f"%{filters['q']}%"
                if filters.get("status"):
                    query += " AND status=:request_status"
                    params["request_status"] = filters["status"]
                if filters.get("business_date_from"):
                    query += " AND substr(start_at,1,10)>=:request_date_from"
                    params["request_date_from"] = filters["business_date_from"]
                if filters.get("business_date_to"):
                    query += " AND substr(end_at,1,10)<=:request_date_to"
                    params["request_date_to"] = filters["business_date_to"]
                if filters.get("unit_id"):
                    query += " AND requesting_unit_id=:request_unit"
                    params["request_unit"] = filters["unit_id"]
            query += " ORDER BY created_at DESC"
        if employee_id:
            params["employee"] = employee_id
        if table != "hr_field_tasks" or not filters:
            rows = (await self.session.execute(text(query), params)).mappings().all()
            return {"items": [dict(row) for row in rows]}
        page = max(int(filters.get("page") or 1), 1)
        page_size = min(max(int(filters.get("page_size") or 10), 1), 100)
        count_query = query.replace("SELECT *", "SELECT COUNT(*)", 1).replace(" ORDER BY created_at DESC", "")
        total = int((await self.session.execute(text(count_query), params)).scalar_one())
        query += " LIMIT :task_limit OFFSET :task_offset"
        params.update({"task_limit": page_size, "task_offset": (page - 1) * page_size})
        rows = (await self.session.execute(text(query), params)).mappings().all()
        return {"items": [dict(row) for row in rows], "total": total, "page": page, "page_size": page_size}

    def _optional_unit_filter(self, request, permission, column, params, prefix):
        scopes = unit_scope(request, permission)
        if scopes is None:
            return ""
        if not scopes:
            raise HTTPException(403, "Permission has no assigned organizational units")
        placeholders = []
        for index, unit_id in enumerate(sorted(scopes)):
            key = f"{prefix}_{index}"
            placeholders.append(f":{key}")
            params[key] = unit_id
        return f" AND ({column} IS NULL OR {column} IN ({','.join(placeholders)}))"

    def _audit(self, entity_type, entity_id, old, new, summary):
        self.request.state.audit_details = {"entity_type": entity_type, "entity_id": entity_id,
                                            "old": old, "new": new, "summary": summary}
