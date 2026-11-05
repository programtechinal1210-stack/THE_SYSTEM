from datetime import date, datetime, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.access import require, unit_scope
from .unit_scope import require_unit, unit_filter


class HROperationsService:
    def __init__(self, session, request):
        self.session = session
        self.request = request

    def _organization(self, permission, requested=None):
        actor_org = self.request.state.user.organization_id.hex
        if requested is None:
            return actor_org
        if self.request.state.is_admin:
            return requested
        if ("institution" in self.request.state.permission_global_scopes.get(permission, set())
                and unit_scope(self.request, permission) is None):
            return requested
        if requested != actor_org:
            raise HTTPException(403, "Outside assigned data scope")
        return actor_org

    async def _row(self, table, entity_id, org, label, permission="hr.attendance.view"):
        allowed = {
            "hr_employees", "hr_shift_templates", "hr_shift_roster", "hr_attendance",
            "hr_attendance_issues", "hr_assignments", "hr_field_tasks",
        }
        if table not in allowed:
            raise ValueError("Unsupported HR entity")
        row = (await self.session.execute(text(
            f"SELECT * FROM {table} WHERE id=:id AND organization_id=:org"
        ), {"id": entity_id, "org": org})).mappings().first()
        if row is None:
            raise HTTPException(404, f"{label} unavailable within assigned scope")
        units = []
        if table == "hr_employees":
            units.append(row["home_unit_id"])
        elif table == "hr_shift_roster":
            units.extend((row["owner_unit_id"], row["work_unit_id"]))
            employee_unit = await self.session.scalar(text(
                "SELECT home_unit_id FROM hr_employees WHERE id=:id AND organization_id=:org"
            ), {"id": row["employee_id"], "org": org})
            units.append(employee_unit)
        elif table == "hr_assignments":
            units.append(row["beneficiary_unit_id"])
        elif table == "hr_field_tasks":
            units.append(row["owner_unit_id"])
        elif table == "hr_attendance":
            employee_unit = await self.session.scalar(text(
                "SELECT home_unit_id FROM hr_employees WHERE id=:id AND organization_id=:org"
            ), {"id": row["employee_id"], "org": org})
            units.append(employee_unit)
            if row["shift_roster_id"]:
                roster_units = (await self.session.execute(text(
                    "SELECT owner_unit_id,work_unit_id FROM hr_shift_roster "
                    "WHERE id=:id AND organization_id=:org"
                ), {"id": row["shift_roster_id"], "org": org})).first()
                if roster_units:
                    units.extend(roster_units)
            if row["assignment_id"]:
                assignment_unit = await self.session.scalar(text(
                    "SELECT beneficiary_unit_id FROM hr_assignments WHERE id=:id AND organization_id=:org"
                ), {"id": row["assignment_id"], "org": org})
                units.append(assignment_unit)
        elif table == "hr_attendance_issues":
            units.append(row["responsible_unit_id"])
            for employee_id in (row["employee_id"], row["responsible_employee_id"]):
                if employee_id:
                    units.append(await self.session.scalar(text(
                        "SELECT home_unit_id FROM hr_employees WHERE id=:id AND organization_id=:org"
                    ), {"id": employee_id, "org": org}))
            if row["attendance_id"]:
                attendance_unit = await self.session.scalar(text(
                    "SELECT e.home_unit_id FROM hr_attendance a JOIN hr_employees e ON e.id=a.employee_id "
                    "WHERE a.id=:id AND a.organization_id=:org"
                ), {"id": row["attendance_id"], "org": org})
                units.append(attendance_unit)
            if row["task_id"]:
                task_unit = await self.session.scalar(text(
                    "SELECT owner_unit_id FROM hr_field_tasks WHERE id=:id AND organization_id=:org"
                ), {"id": row["task_id"], "org": org})
                units.append(task_unit)
        for unit_id in filter(None, units):
            require_unit(self.request, permission, unit_id, status_code=404)
        return dict(row)

    async def _unit(self, unit_id, org, permission):
        exists = bool(await self.session.scalar(text(
            "WITH RECURSIVE units(id,path) AS ("
            "SELECT id,'|'||id||'|' FROM organizations WHERE id=:org AND is_active=1 "
            "UNION ALL SELECT child.id,units.path||child.id||'|' FROM organizations child "
            "JOIN units ON child.parent_id=units.id WHERE child.is_active=1 "
            "AND instr(units.path,'|'||child.id||'|')=0) "
            "SELECT 1 FROM units WHERE id=:id"
        ), {"id": unit_id, "org": org}))
        if exists:
            require_unit(self.request, permission, unit_id)
        return exists

    def _optional_unit_filter(self, permission, column, params, prefix):
        scopes = unit_scope(self.request, permission)
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
        self.request.state.audit_details = {
            "entity_type": entity_type, "entity_id": entity_id,
            "old": old, "new": new, "summary": summary,
        }

    @staticmethod
    def _zone(name):
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, TypeError):
            raise HTTPException(422, "Unknown timezone")

    @staticmethod
    def _local_instant(day, clock, zone, fold=None):
        naive = datetime.combine(date.fromisoformat(day), time.fromisoformat(clock))
        candidates = [naive.replace(tzinfo=zone, fold=part) for part in (0, 1)]
        valid = [
            candidate.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == naive
            for candidate in candidates
        ]
        if not any(valid):
            raise HTTPException(422, "Local time does not exist in the selected timezone")
        ambiguous = valid[0] and valid[1] and candidates[0].utcoffset() != candidates[1].utcoffset()
        if ambiguous and fold is None:
            raise HTTPException(422, "Ambiguous local time requires an explicit fold")
        local = candidates[fold or 0]
        return local.astimezone(timezone.utc)

    @staticmethod
    def _timestamp(value, name):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (AttributeError, ValueError):
            raise HTTPException(422, f"Invalid {name}")
        if parsed.tzinfo is None:
            raise HTTPException(422, f"{name} must include timezone")
        return parsed.astimezone(timezone.utc).isoformat()

    async def create_template(self, data):
        require(self.request, "hr.shift.manage")
        org = self._organization("hr.shift.manage", data.get("organization_id"))
        if unit_scope(self.request, "hr.shift.manage") is not None:
            raise HTTPException(403, "Shift templates are organization-wide and cannot be managed by a unit-scoped role")
        zone = self._zone(data["timezone_name"])
        try:
            start = time.fromisoformat(data["start_local_time"])
            end = time.fromisoformat(data["end_local_time"])
        except ValueError:
            raise HTTPException(422, "Invalid local shift time")
        duration = (datetime.combine(date(2000, 1, 2 if data["end_day_offset"] else 1), end)
                    - datetime.combine(date(2000, 1, 1), start)).total_seconds() / 60
        if duration <= 0 or data["break_minutes"] >= duration:
            raise HTTPException(422, "Shift duration must exceed its break")
        if not zone:
            raise HTTPException(422, "Timezone is required")
        entity_id = uuid4().hex
        await self.session.execute(text(
            "INSERT INTO hr_shift_templates(id,organization_id,code,name_ar,start_local_time,end_local_time,end_day_offset,break_minutes,timezone_name) "
            "VALUES(:id,:org,:code,:name,:start,:end,:offset,:break,:zone)"
        ), {"id": entity_id, "org": org, "code": data["code"].strip(), "name": data["name_ar"].strip(),
            "start": start.isoformat(), "end": end.isoformat(), "offset": data["end_day_offset"],
            "break": data["break_minutes"], "zone": data["timezone_name"]})
        row = await self._row("hr_shift_templates", entity_id, org, "Shift template", "hr.shift.manage")
        self._audit("hr.shift_templates", entity_id, None, row, "HR shift template created")
        return row

    async def list_templates(self):
        require(self.request, "hr.shift.view")
        org = self._organization("hr.shift.view")
        rows = (await self.session.execute(text(
            "SELECT * FROM hr_shift_templates WHERE organization_id=:org ORDER BY code"
        ), {"org": org})).mappings().all()
        return {"items": [dict(row) for row in rows]}

    def _can_view_sensitive_issues(self, unit_id=None):
        if self.request.state.is_admin:
            return True
        if "hr.issue.sensitive.view" not in self.request.state.permissions:
            return False
        scopes = unit_scope(self.request, "hr.issue.sensitive.view")
        return scopes is None or (unit_id is not None and str(unit_id) in scopes)

    def _present_issue(self, row):
        if self._can_view_sensitive_issues(row.get("responsible_unit_id")):
            return row
        for field in ("reason", "proposed_solution", "resolution_notes"):
            row.pop(field, None)
        return row

    async def create_roster(self, data):
        require(self.request, "hr.shift.manage")
        org = self._organization("hr.shift.manage", data.get("organization_id"))
        employee = await self._row("hr_employees", data["employee_id"], org, "Employee", "hr.shift.manage")
        if employee["employment_status"] != "active":
            raise HTTPException(409, "Only active employees may be scheduled")
        if not await self._unit(data["owner_unit_id"], org, "hr.shift.manage") or not await self._unit(data["work_unit_id"], org, "hr.shift.manage"):
            raise HTTPException(422, "Roster units must belong to the organization")
        template = None
        if data.get("shift_template_id"):
            if unit_scope(self.request, "hr.shift.manage") is not None:
                raise HTTPException(403, "Unit-scoped roles cannot assign organization-wide shift templates")
            template = await self._row("hr_shift_templates", data["shift_template_id"], org, "Shift template", "hr.shift.manage")
            if not template["is_active"]:
                raise HTTPException(409, "Inactive shift template")
            zone_name = template["timezone_name"]
            zone = self._zone(zone_name)
            local_start = self._local_instant(data["business_date"], template["start_local_time"], zone, data.get("start_fold"))
            end_day = date.fromisoformat(data["business_date"]).toordinal() + template["end_day_offset"]
            end_date = date.fromordinal(end_day).isoformat()
            local_end = self._local_instant(end_date, template["end_local_time"], zone, data.get("end_fold"))
            start, end = local_start.isoformat(), local_end.isoformat()
            break_minutes = template["break_minutes"]
            name_snapshot = template["name_ar"]
        else:
            start = self._timestamp(data["start_at"], "start_at")
            end = self._timestamp(data["end_at"], "end_at")
            break_minutes = data["planned_break_minutes"]
            zone_name = data["timezone_name"]
            self._zone(zone_name)
            name_snapshot = data.get("shift_name_snapshot", "وردية استثنائية")
        if end <= start or break_minutes < 0:
            raise HTTPException(422, "Roster interval or break is invalid")
        if not await self._unit(data["owner_unit_id"], org, "hr.shift.manage"):
            raise HTTPException(422, "Owner unit is outside organization")
        entity_id = uuid4().hex
        await self.session.execute(text(
            "INSERT INTO hr_shift_roster(id,organization_id,employee_id,shift_template_id,owner_unit_id,work_unit_id,business_date,start_at,end_at,planned_break_minutes,location_text,shift_name_snapshot,timezone_name_snapshot,notes) "
            "VALUES(:id,:org,:employee,:template,:owner,:work,:day,:start,:end,:break,:location,:name,:zone,:notes)"
        ), dict(id=entity_id, org=org, employee=data["employee_id"], template=data.get("shift_template_id"),
                owner=data["owner_unit_id"], work=data["work_unit_id"], day=data["business_date"],
                start=start, end=end, **{"break": break_minutes}, location=data.get("location_text", ""),
                name=name_snapshot, zone=zone_name, notes=data.get("notes", "")))
        row = await self._row("hr_shift_roster", entity_id, org, "Shift roster", "hr.shift.manage")
        self._audit("hr.shift_roster", entity_id, None, row, "HR shift roster drafted")
        return row

    async def list_roster(self, employee_id=None):
        require(self.request, "hr.shift.view")
        org = self._organization("hr.shift.view")
        params = {"org": org}
        owner_scope = unit_filter(self.request, "hr.shift.view", "r.owner_unit_id", params)
        work_scope = unit_filter(self.request, "hr.shift.view", "r.work_unit_id", params, "work_unit")
        employee_scope = unit_filter(self.request, "hr.shift.view", "e.home_unit_id", params, "employee_unit")
        if employee_id:
            params["employee"] = employee_id
        rows = (await self.session.execute(text(
            "SELECT r.* FROM hr_shift_roster r JOIN hr_employees e ON e.id=r.employee_id "
            "WHERE r.organization_id=:org" + owner_scope + work_scope + employee_scope
            + (" AND r.employee_id=:employee" if employee_id else "") + " ORDER BY r.start_at"
        ), params)).mappings().all()
        return {"items": [dict(row) for row in rows]}

    async def confirm_roster(self, entity_id):
        require(self.request, "hr.shift.confirm")
        await self.session.execute(text("BEGIN IMMEDIATE"))
        org = self._organization("hr.shift.confirm")
        row = await self._row("hr_shift_roster", entity_id, org, "Shift roster", "hr.shift.confirm")
        if row["status"] != "draft":
            raise HTTPException(409, "Only draft shifts can be confirmed")
        overlap = await self.session.scalar(text(
            "SELECT 1 FROM hr_shift_roster WHERE organization_id=:org AND employee_id=:employee "
            "AND status='confirmed' AND start_at<:end AND end_at>:start LIMIT 1"
        ), dict(org=org, employee=row["employee_id"], start=row["start_at"], end=row["end_at"]))
        if overlap:
            raise HTTPException(409, "Employee already has an overlapping confirmed shift")
        now = datetime.now(timezone.utc).isoformat()
        result = await self.session.execute(text(
            "UPDATE hr_shift_roster SET status='confirmed',confirmed_by_user_id=:actor,confirmed_at=:now,"
            "row_version=row_version+1,updated_at=:now WHERE id=:id AND organization_id=:org AND row_version=:version AND status='draft'"
        ), dict(actor=self.request.state.user_id.hex, now=now, id=entity_id, org=org, version=row["row_version"]))
        if result.rowcount != 1:
            raise HTTPException(409, "Shift changed; reload before confirming")
        updated = await self._row("hr_shift_roster", entity_id, org, "Shift roster", "hr.shift.confirm")
        self._audit("hr.shift_roster", entity_id, row, updated, "HR shift roster confirmed")
        return updated

    async def create_attendance(self, data):
        require(self.request, "hr.attendance.record")
        await self.session.execute(text("BEGIN IMMEDIATE"))
        org = self._organization("hr.attendance.record", data.get("organization_id"))
        employee = await self._row(
        "hr_employees", data["employee_id"], org, "Employee", "hr.attendance.record"
        )
        kind = data["attendance_kind"]
        roster_id, assignment_id, task_id, root_id = (
            data.get("shift_roster_id"), data.get("assignment_id"),
            data.get("task_id"), data.get("root_attendance_id"))
        if kind == "base_shift":
            if not roster_id:
                raise HTTPException(422, "Shift-based attendance requires a roster")
            roster = await self._row("hr_shift_roster", roster_id, org, "Shift roster", "hr.attendance.record")
            if roster["employee_id"] != data["employee_id"] or roster["business_date"] != data["business_date"]:
                raise HTTPException(422, "Attendance must match roster employee and business date")
            if roster["status"] not in ("confirmed", "completed"):
                raise HTTPException(409, "Attendance requires a confirmed or completed shift")
        elif kind == "base_unscheduled":
            if roster_id or assignment_id or root_id:
                raise HTTPException(422, "Unscheduled base attendance cannot reference a shift or task")
            confirmed_roster = await self.session.scalar(text(
                "SELECT 1 FROM hr_shift_roster WHERE organization_id=:org AND employee_id=:employee "
                "AND business_date=:day AND status IN ('confirmed','completed') LIMIT 1"
            ), {"org": org, "employee": data["employee_id"], "day": data["business_date"]})
            if confirmed_roster:
                raise HTTPException(409, "Unscheduled base attendance conflicts with a confirmed shift")
        else:
            if not assignment_id or not root_id:
                raise HTTPException(422, "Task participation requires assignment and base attendance root")
            assignment = await self._row("hr_assignments", assignment_id, org, "Assignment", "hr.attendance.record")
            root = await self._row("hr_attendance", root_id, org, "Base attendance", "hr.attendance.record")
            if assignment["employee_id"] != data["employee_id"] or root["employee_id"] != data["employee_id"]:
                raise HTTPException(422, "Task participation references must match employee")
            if assignment["status"] not in ("approved", "active", "completed"):
                raise HTTPException(409, "Task participation requires an approved assignment")
            if assignment["business_date"] != data["business_date"]:
                raise HTTPException(422, "Task participation date must match the assignment")
            if root["attendance_kind"] == "task_participation":
                raise HTTPException(422, "Task participation must reference a base attendance root")
            root_id = root["root_attendance_id"] or root["id"]
            current_root = (await self.session.execute(text(
                "SELECT * FROM hr_attendance WHERE organization_id=:org AND root_attendance_id=:root "
                "AND attendance_kind<>'task_participation' AND is_current=1"
            ), {"org": org, "root": root_id})).mappings().first()
            if (current_root is None or current_root["approval_status"] != "approved"
                    or current_root["status"] not in ("present", "partial", "late")
                    or current_root["business_date"] != data["business_date"]):
                raise HTTPException(409, "Task participation requires current approved base attendance")
            if task_id and task_id != assignment["task_id"]:
                raise HTTPException(422, "Task does not match assignment")
            task_id = assignment["task_id"]
            if not task_id:
                raise HTTPException(422, "Assignment has no field task")
        status = data["status"]
        valid = ({"pending", "present", "absent", "partial", "late", "excused", "unknown"}
                 if kind != "task_participation" else {"pending", "participated", "not_participated", "unknown"})
        if status not in valid:
            raise HTTPException(422, "Attendance status does not match record kind")
        approval_status = data.get("approval_status", "draft")
        if approval_status not in ("draft", "submitted"):
            raise HTTPException(422, "Attendance must be submitted separately for approval")
        source = data.get("source", "manual")
        if source not in ("manual", "device", "import"):
            raise HTTPException(422, "Invalid attendance source")
        check_in, check_out = data.get("check_in_at"), data.get("check_out_at")
        if bool(check_in) != bool(check_out):
            raise HTTPException(422, "Check-in and check-out must be supplied together")
        if check_in:
            check_in = self._timestamp(check_in, "check_in_at")
            check_out = self._timestamp(check_out, "check_out_at")
            if check_out < check_in:
                raise HTTPException(422, "Check-out must not precede check-in")
        if bool(data.get("source_system")) != bool(data.get("source_record_id")):
            raise HTTPException(422, "Source system and source record ID must be supplied together")
        entity_id = uuid4().hex
        if kind != "task_participation":
            root_id = entity_id
        try:
            await self.session.execute(text(
                "INSERT INTO hr_attendance(id,organization_id,employee_id,attendance_kind,shift_roster_id,assignment_id,task_id,business_date,status,approval_status,source,source_system,source_record_id,root_attendance_id,is_current,notes,check_in_at,check_out_at,recorded_by_user_id) "
                "VALUES(:id,:org,:employee,:kind,:roster,:assignment,:task,:day,:status,:approval,:source,:source_system,:source_record,:root,1,:notes,:check_in,:check_out,:actor)"
            ), dict(id=entity_id, org=org, employee=data["employee_id"], kind=kind, roster=roster_id,
                    assignment=assignment_id, task=task_id, day=data["business_date"], status=status,
                    approval=approval_status, source=source, source_system=data.get("source_system"),
                    source_record=data.get("source_record_id"), root=root_id, notes=data.get("notes", ""),
                    check_in=check_in, check_out=check_out, actor=self.request.state.user_id.hex))
        except IntegrityError as exc:
            raise HTTPException(409, "Attendance already exists or conflicts with an existing record") from exc
        row = await self._row("hr_attendance", entity_id, org, "Attendance", "hr.attendance.record")
        self._audit("hr.attendance", entity_id, None, row, "HR attendance recorded")
        return row

    async def list_attendance(self, business_date=None, employee_id=None):
        require(self.request, "hr.attendance.view")
        org = self._organization("hr.attendance.view")
        params = {"org": org}
        scoped = unit_filter(self.request, "hr.attendance.view", "e.home_unit_id", params)
        scoped += self._optional_unit_filter(
            "hr.attendance.view", "r.owner_unit_id", params, "roster_owner"
        )
        scoped += self._optional_unit_filter(
            "hr.attendance.view", "r.work_unit_id", params, "roster_work"
        )
        scoped += self._optional_unit_filter(
            "hr.attendance.view", "a2.beneficiary_unit_id", params, "assignment_unit"
        )
        scoped += self._optional_unit_filter(
            "hr.attendance.view", "t.owner_unit_id", params, "task_unit"
        )
        sql = (
            "SELECT a.* FROM hr_attendance a JOIN hr_employees e ON e.id=a.employee_id "
            "LEFT JOIN hr_shift_roster r ON r.id=a.shift_roster_id "
            "LEFT JOIN hr_assignments a2 ON a2.id=a.assignment_id "
            "LEFT JOIN hr_field_tasks t ON t.id=a.task_id "
            "WHERE a.organization_id=:org" + scoped
        )
        if business_date:
            sql += " AND a.business_date=:day"
            params["day"] = business_date
        if employee_id:
            sql += " AND a.employee_id=:employee"
            params["employee"] = employee_id
        rows = (await self.session.execute(text(sql + " ORDER BY a.business_date,a.created_at"), params)).mappings().all()
        return {"items": [dict(row) for row in rows]}

    async def submit_attendance(self, entity_id, expected_version):
        require(self.request, "hr.attendance.record")
        org = self._organization("hr.attendance.record")
        row = await self._row("hr_attendance", entity_id, org, "Attendance", "hr.attendance.record")
        if row["approval_status"] != "draft":
            raise HTTPException(409, "Only draft attendance can be submitted")
        if row["supersedes_attendance_id"]:
            original = await self._row(
                "hr_attendance", row["supersedes_attendance_id"], org, "Original attendance",
                "hr.attendance.record"
            )
            if (not original["is_current"] or original["row_version"] != row["supersedes_row_version"]
                    or original["approval_status"] != "approved"):
                raise HTTPException(409, "Original attendance changed; recreate the correction")
        result = await self.session.execute(text(
            "UPDATE hr_attendance SET approval_status='submitted',row_version=row_version+1,updated_at=:now "
            "WHERE id=:id AND organization_id=:org AND row_version=:version AND approval_status='draft'"
        ), dict(now=datetime.now(timezone.utc).isoformat(), id=entity_id, org=org, version=expected_version))
        if result.rowcount != 1:
            raise HTTPException(409, "Attendance changed; reload before submission")
        updated = await self._row("hr_attendance", entity_id, org, "Attendance", "hr.attendance.record")
        self._audit("hr.attendance", entity_id, row, updated, "HR attendance submitted")
        return updated

    async def reject_attendance(self, entity_id, expected_version, reason):
        require(self.request, "hr.attendance.approve")
        await self.session.execute(text("BEGIN IMMEDIATE"))
        org = self._organization("hr.attendance.approve")
        row = await self._row("hr_attendance", entity_id, org, "Attendance", "hr.attendance.approve")
        if row["approval_status"] != "submitted":
            raise HTTPException(409, "Only submitted attendance can be rejected")
        if row["recorded_by_user_id"] == self.request.state.user_id.hex:
            raise HTTPException(403, "Attendance approval must be performed by a different user")
        result = await self.session.execute(text(
            "UPDATE hr_attendance SET approval_status='rejected',is_current=0,decision_note=:reason,"
            "row_version=row_version+1,updated_at=:now WHERE id=:id AND organization_id=:org "
            "AND row_version=:version AND approval_status='submitted'"
        ), dict(reason=reason.strip(), now=datetime.now(timezone.utc).isoformat(),
                id=entity_id, org=org, version=expected_version))
        if result.rowcount != 1:
            raise HTTPException(409, "Attendance changed; reload before rejection")
        updated = await self._row("hr_attendance", entity_id, org, "Attendance", "hr.attendance.approve")
        self._audit("hr.attendance", entity_id, row, updated, "HR attendance rejected")
        return updated

    async def approve_attendance(self, entity_id, expected_version):
        require(self.request, "hr.attendance.approve")
        await self.session.execute(text("BEGIN IMMEDIATE"))
        org = self._organization("hr.attendance.approve")
        row = await self._row("hr_attendance", entity_id, org, "Attendance", "hr.attendance.approve")
        if row["approval_status"] != "submitted":
            raise HTTPException(409, "Attendance is not awaiting approval")
        if row["recorded_by_user_id"] == self.request.state.user_id.hex:
            raise HTTPException(403, "Attendance approval must be performed by a different user")
        if row["attendance_kind"] == "task_participation":
            parent = await self.session.execute(text(
                "SELECT * FROM hr_attendance WHERE organization_id=:org AND is_current=1 "
                "AND (id=:root OR root_attendance_id=:root) AND attendance_kind<>'task_participation'"
            ), {"org": org, "root": row["root_attendance_id"]})
            parent = parent.mappings().first()
            if parent is None:
                raise HTTPException(409, "Current base attendance for task participation is unavailable")
            await self._row("hr_attendance", parent["id"], org, "Base attendance", "hr.attendance.approve")
            if parent["status"] == "absent" and parent["approval_status"] == "approved":
                raise HTTPException(409, "Cannot approve task participation while base attendance is absent")
        if row["supersedes_attendance_id"]:
            original = await self._row("hr_attendance", row["supersedes_attendance_id"], org, "Original attendance", "hr.attendance.approve")
            if (not original["is_current"] or original["row_version"] != row["supersedes_row_version"]
                    or original["approval_status"] != "approved"):
                raise HTTPException(409, "Original attendance changed; recreate the correction")
            if original["attendance_kind"] != "task_participation" and row["status"] == "absent":
                child = await self.session.scalar(text(
                    "SELECT 1 FROM hr_attendance WHERE organization_id=:org AND root_attendance_id=:root "
                    "AND attendance_kind='task_participation' AND status='participated' "
                    "AND approval_status='approved' AND is_current=1"
                ), {"org": org, "root": original["root_attendance_id"] or original["id"]})
                if child:
                    raise HTTPException(409, "Resolve approved task participation before approving absence correction")
            original_update = await self.session.execute(text(
                "UPDATE hr_attendance SET is_current=0,row_version=row_version+1,updated_at=:now "
                "WHERE id=:id AND organization_id=:org AND is_current=1 AND row_version=:version"
            ), dict(now=datetime.now(timezone.utc).isoformat(), id=original["id"], org=org,
                    version=row["supersedes_row_version"]))
            if original_update.rowcount != 1:
                raise HTTPException(409, "Original attendance changed; reload before correction approval")
        result = await self.session.execute(text(
            "UPDATE hr_attendance SET approval_status='approved',approved_by_user_id=:actor,approved_at=:now,"
            "is_current=1,row_version=row_version+1,updated_at=:now WHERE id=:id AND organization_id=:org AND row_version=:version"
        ), dict(actor=self.request.state.user_id.hex, now=datetime.now(timezone.utc).isoformat(),
                id=entity_id, org=org, version=expected_version))
        if result.rowcount != 1:
            raise HTTPException(409, "Attendance changed; reload before approval")
        updated = await self._row("hr_attendance", entity_id, org, "Attendance", "hr.attendance.approve")
        self._audit("hr.attendance", entity_id, row, updated, "HR attendance approved")
        return updated

    async def correct_attendance(self, entity_id, data):
        require(self.request, "hr.attendance.correct")
        await self.session.execute(text("BEGIN IMMEDIATE"))
        org = self._organization("hr.attendance.correct")
        old = await self._row("hr_attendance", entity_id, org, "Attendance", "hr.attendance.correct")
        if old["approval_status"] != "approved" or not old["is_current"]:
            raise HTTPException(409, "Only current approved attendance can be corrected")
        new_status = data["status"]
        if old["attendance_kind"] == "task_participation" and new_status not in ("pending", "participated", "not_participated", "unknown"):
            raise HTTPException(422, "Task participation correction has invalid status")
        if old["attendance_kind"] != "task_participation" and new_status not in ("pending", "present", "absent", "partial", "late", "excused", "unknown"):
            raise HTTPException(422, "Base attendance correction has invalid status")
        if old["row_version"] != data["row_version"]:
            raise HTTPException(409, "Attendance changed; reload before correction")
        pending_correction = await self.session.scalar(text(
            "SELECT 1 FROM hr_attendance WHERE organization_id=:org AND supersedes_attendance_id=:id "
            "AND approval_status IN ('draft','submitted') LIMIT 1"
        ), {"org": org, "id": entity_id})
        if pending_correction:
            raise HTTPException(409, "Attendance already has a pending correction")
        root = old["root_attendance_id"] or old["id"]
        if old["attendance_kind"] != "task_participation" and new_status == "absent":
            child = await self.session.scalar(text(
                "SELECT 1 FROM hr_attendance WHERE organization_id=:org AND root_attendance_id=:root "
                "AND attendance_kind='task_participation' AND status='participated' AND approval_status='approved' AND is_current=1"
            ), {"org": org, "root": root})
            if child:
                raise HTTPException(409, "Resolve approved task participation before correcting base attendance to absent")
        new_id = uuid4().hex
        await self.session.execute(text(
            "INSERT INTO hr_attendance(id,organization_id,employee_id,attendance_kind,shift_roster_id,assignment_id,task_id,business_date,status,approval_status,source,root_attendance_id,supersedes_attendance_id,supersedes_row_version,is_current,notes,check_in_at,check_out_at,recorded_by_user_id) "
            "VALUES(:id,:org,:employee,:kind,:roster,:assignment,:task,:day,:status,'draft',:source,:root,:old,:version,0,:notes,:check_in,:check_out,:actor)"
        ), dict(id=new_id, org=org, employee=old["employee_id"], kind=old["attendance_kind"],
                roster=old["shift_roster_id"], assignment=old["assignment_id"], task=old["task_id"],
                day=old["business_date"], status=new_status, source=old["source"], root=root, old=entity_id,
                version=data["row_version"],
                notes=data["reason"], check_in=old["check_in_at"], check_out=old["check_out_at"],
                actor=self.request.state.user_id.hex))
        pending = await self._row("hr_attendance", new_id, org, "Corrected attendance", "hr.attendance.correct")
        self._audit("hr.attendance", new_id, old, pending, "HR attendance correction submitted")
        return pending

    async def create_issue(self, data):
        require(self.request, "hr.issue.manage")
        org = self._organization("hr.issue.manage", data.get("organization_id"))
        employee_id, attendance_id, task_id = data.get("employee_id"), data.get("attendance_id"), data.get("task_id")
        if employee_id:
            await self._row("hr_employees", employee_id, org, "Employee", "hr.issue.manage")
        if attendance_id:
            await self._row("hr_attendance", attendance_id, org, "Attendance", "hr.issue.manage")
        if task_id:
            await self._row("hr_field_tasks", task_id, org, "Task", "hr.issue.manage")
        if data["issue_type"] == "absence" and not employee_id:
            raise HTTPException(422, "Absence issue requires an employee")
        responsible_employee = data.get("responsible_employee_id")
        if responsible_employee:
            await self._row(
                "hr_employees", responsible_employee, org, "Responsible employee", "hr.issue.manage"
            )
        responsible_unit = data.get("responsible_unit_id")
        if responsible_unit and not await self._unit(responsible_unit, org, "hr.issue.manage"):
            raise HTTPException(422, "Responsible unit is outside organization")
        entity_id = uuid4().hex
        await self.session.execute(text(
            "INSERT INTO hr_attendance_issues(id,organization_id,employee_id,attendance_id,task_id,issue_type,business_date,priority,solution_status,excuse_decision,reason,proposed_solution,responsible_unit_id,responsible_employee_id,responsible_user_id) "
            "VALUES(:id,:org,:employee,:attendance,:task,:type,:day,:priority,'not_started',:excuse,:reason,:solution,:unit,:responsible,:user)"
        ), dict(id=entity_id, org=org, employee=employee_id, attendance=attendance_id, task=task_id,
                type=data["issue_type"], day=data["business_date"], priority=data["priority"],
                excuse=data.get("excuse_decision", "not_applicable"), reason=data["reason"].strip(),
                solution=data.get("proposed_solution", "").strip(), unit=responsible_unit,
                responsible=responsible_employee, user=self.request.state.user_id.hex))
        row = await self._row("hr_attendance_issues", entity_id, org, "Issue", "hr.issue.manage")
        self._audit("hr.attendance_issues", entity_id, None, row, "HR issue created")
        return self._present_issue(row)

    async def list_issues(self, employee_id=None):
        require(self.request, "hr.issue.view")
        org = self._organization("hr.issue.view")
        params = {"org": org}
        scope_sql = ""
        if unit_scope(self.request, "hr.issue.view") is not None:
            scope_sql += unit_filter(
                self.request, "hr.issue.view", "e.home_unit_id", params, "issue_employee"
            )
            scope_sql += self._optional_unit_filter(
                "hr.issue.view", "i.responsible_unit_id", params, "issue_unit"
            )
            scope_sql += self._optional_unit_filter(
                "hr.issue.view", "re.home_unit_id", params, "responsible_employee"
            )
            scope_sql += self._optional_unit_filter(
                "hr.issue.view", "ae.home_unit_id", params, "attendance_employee"
            )
            scope_sql += self._optional_unit_filter(
                "hr.issue.view", "t.owner_unit_id", params, "issue_task"
            )
        if employee_id:
            scope_sql += " AND i.employee_id=:employee"
            params["employee"] = employee_id
        rows = (await self.session.execute(text(
            "SELECT i.*, e.full_name AS employee_name, e.employee_no AS employee_no, "
            "re.full_name AS responsible_employee_name, ru.name AS responsible_unit_name "
            "FROM hr_attendance_issues i "
            "LEFT JOIN hr_employees e ON e.id=i.employee_id "
            "LEFT JOIN hr_employees re ON re.id=i.responsible_employee_id "
            "LEFT JOIN organizations ru ON ru.id=i.responsible_unit_id "
            "LEFT JOIN hr_attendance a ON a.id=i.attendance_id "
            "LEFT JOIN hr_employees ae ON ae.id=a.employee_id "
            "LEFT JOIN hr_field_tasks t ON t.id=i.task_id "
            "WHERE i.organization_id=:org" + scope_sql + " ORDER BY i.created_at DESC"
        ), params)).mappings().all()
        return {"items": [self._present_issue(dict(row)) for row in rows]}

    async def transition_issue(self, entity_id, data):
        require(self.request, "hr.issue.manage")
        org = self._organization("hr.issue.manage")
        row = await self._row("hr_attendance_issues", entity_id, org, "Issue", "hr.issue.manage")
        action = data["action"]
        if action in ("accept_excuse", "reject_excuse"):
            require(self.request, "hr.excuse.decide")
            await self._row("hr_attendance_issues", entity_id, org, "Issue", "hr.excuse.decide")
            if row["excuse_decision"] != "pending":
                raise HTTPException(409, "Issue has no pending excuse decision")
            next_excuse = "accepted" if action == "accept_excuse" else "rejected"
            result = await self.session.execute(text(
                "UPDATE hr_attendance_issues SET excuse_decision=:excuse,row_version=row_version+1,updated_at=:now "
                "WHERE id=:id AND organization_id=:org AND row_version=:version"
            ), dict(excuse=next_excuse, now=datetime.now(timezone.utc).isoformat(),
                    id=entity_id, org=org, version=data["row_version"]))
            if result.rowcount != 1:
                raise HTTPException(409, "Issue changed; reload before deciding")
            updated = await self._row(
                "hr_attendance_issues", entity_id, org, "Issue", "hr.excuse.decide"
            )
            self._audit("hr.attendance_issues", entity_id, row, updated, "HR excuse decision recorded")
            return self._present_issue(updated)
        next_status = {
            ("not_started", "start"): "in_progress",
            ("in_progress", "resolve"): "resolved",
            ("resolved", "close"): "closed",
            ("not_started", "cancel"): "cancelled",
            ("in_progress", "cancel"): "cancelled",
        }.get((row["solution_status"], action))
        if not next_status:
            raise HTTPException(409, "Issue transition is not allowed")
        if next_status == "resolved" and not data.get("resolution_notes", "").strip():
            raise HTTPException(422, "Resolution result is required")
        if next_status == "closed":
            require(self.request, "hr.issue.close")
            await self._row("hr_attendance_issues", entity_id, org, "Issue", "hr.issue.close")
            if not row["resolution_notes"]:
                raise HTTPException(409, "Issue must be resolved before closing")
        require(self.request, "hr.issue.close" if action == "close" else "hr.issue.manage")
        now = datetime.now(timezone.utc).isoformat()
        resolved_at = now if next_status == "resolved" else row["resolved_at"]
        closed_at = now if next_status in ("closed", "cancelled") else row["closed_at"]
        result = await self.session.execute(text(
            "UPDATE hr_attendance_issues SET solution_status=:status,resolution_notes=:notes,resolved_at=:resolved,closed_at=:closed,"
            "row_version=row_version+1,updated_at=:now WHERE id=:id AND organization_id=:org AND row_version=:version"
        ), dict(status=next_status, notes=data.get("resolution_notes") or row["resolution_notes"],
                resolved=resolved_at, closed=closed_at, now=now, id=entity_id, org=org, version=data["row_version"]))
        if result.rowcount != 1:
            raise HTTPException(409, "Issue changed; reload before transition")
        updated = await self._row(
            "hr_attendance_issues", entity_id, org, "Issue",
            "hr.issue.close" if action == "close" else "hr.issue.manage"
        )
        self._audit("hr.attendance_issues", entity_id, row, updated, "HR issue transitioned")
        return self._present_issue(updated)

    async def report(self, report_code, start_date, end_date, extra_permission=None):
        require(self.request, "hr.report.view")
        org = self._organization("hr.report.view")
        if start_date and end_date and start_date > end_date:
            raise HTTPException(422, "Report start date must not follow end date")

        def attendance_scope(permission, prefix, params):
            scope = unit_filter(
                self.request, permission, "e.home_unit_id", params, prefix + "_employee"
            )
            scope += self._optional_unit_filter(
                permission, "r.owner_unit_id", params, prefix + "_roster_owner"
            )
            scope += self._optional_unit_filter(
                permission, "r.work_unit_id", params, prefix + "_roster_work"
            )
            scope += self._optional_unit_filter(
                permission, "a2.beneficiary_unit_id", params, prefix + "_assignment"
            )
            scope += self._optional_unit_filter(
                permission, "t.owner_unit_id", params, prefix + "_task"
            )
            return scope

        if report_code == "attendance":
            params = {"org": org, "start": start_date, "end": end_date}
            scope = attendance_scope("hr.report.view", "report", params)
            if extra_permission:
                scope += attendance_scope(extra_permission, "export", params)
            rows = (await self.session.execute(text(
                "SELECT a.business_date,a.attendance_kind,a.status,COUNT(*) AS total "
                "FROM hr_attendance a JOIN hr_employees e ON e.id=a.employee_id "
                "LEFT JOIN hr_shift_roster r ON r.id=a.shift_roster_id "
                "LEFT JOIN hr_assignments a2 ON a2.id=a.assignment_id "
                "LEFT JOIN hr_field_tasks t ON t.id=a.task_id "
                "WHERE a.organization_id=:org" + scope + " AND a.attendance_kind IN ('base_shift','base_unscheduled') "
                "AND approval_status='approved' AND is_current=1 "
                "AND (:start IS NULL OR a.business_date>=:start) AND (:end IS NULL OR a.business_date<=:end) "
                "GROUP BY a.business_date,a.attendance_kind,a.status ORDER BY a.business_date"
            ), params)).mappings().all()
            participation_scope = attendance_scope("hr.report.view", "participation", params)
            if extra_permission:
                participation_scope += attendance_scope(extra_permission, "participation_export", params)
            participation = (await self.session.execute(text(
                "SELECT a.business_date,a.status,COUNT(*) AS total "
                "FROM hr_attendance a JOIN hr_employees e ON e.id=a.employee_id "
                "LEFT JOIN hr_shift_roster r ON r.id=a.shift_roster_id "
                "LEFT JOIN hr_assignments a2 ON a2.id=a.assignment_id "
                "LEFT JOIN hr_field_tasks t ON t.id=a.task_id "
                "WHERE a.organization_id=:org" + participation_scope + " AND a.attendance_kind='task_participation' "
                "AND approval_status='approved' AND is_current=1 "
                "AND (:start IS NULL OR a.business_date>=:start) AND (:end IS NULL OR a.business_date<=:end) "
                "GROUP BY a.business_date,a.status ORDER BY a.business_date"
            ), params)).mappings().all()
            return {"report": report_code, "items": [dict(row) for row in rows],
                    "task_participation": [dict(row) for row in participation]}
        if report_code == "issues":
            params = {"org": org, "start": start_date, "end": end_date}
            scope = unit_filter(self.request, "hr.report.view", "e.home_unit_id", params)
            if extra_permission:
                scope += unit_filter(
                    self.request, extra_permission, "e.home_unit_id", params, "export_unit"
                )
            rows = (await self.session.execute(text(
                "SELECT i.solution_status,i.issue_type,COUNT(*) AS total "
                "FROM hr_attendance_issues i JOIN hr_employees e ON e.id=i.employee_id "
                "WHERE i.organization_id=:org" + scope + " AND (:start IS NULL OR i.business_date>=:start) "
                "AND (:end IS NULL OR i.business_date<=:end) GROUP BY i.solution_status,i.issue_type"
            ), params)).mappings().all()
            return {"report": report_code, "items": [dict(row) for row in rows]}
        if report_code == "employees":
            params = {"org": org}
            scope = unit_filter(self.request, "hr.report.view", "home_unit_id", params)
            if extra_permission:
                scope += unit_filter(
                    self.request, extra_permission, "home_unit_id", params, "export_unit"
                )
            rows = (await self.session.execute(text(
                "SELECT employment_status,COUNT(*) AS total FROM hr_employees "
                "WHERE organization_id=:org" + scope + " GROUP BY employment_status"
            ), params)).mappings().all()
            return {"report": report_code, "items": [dict(row) for row in rows]}
        raise HTTPException(404, "Unknown HR report")
