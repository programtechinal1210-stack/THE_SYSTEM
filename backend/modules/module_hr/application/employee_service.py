from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.access import require, unit_scope
from .unit_scope import require_unit, unit_filter


STATUS_BY_CHANGE = {
    "hire": "active",
    "suspension": "suspended",
    "termination": "terminated",
    "reinstatement": "active",
}


class EmployeeService:
    def __init__(self, session, request):
        self.session = session
        self.request = request

    def _scopes(self, permission):
        return self.request.state.permission_scopes.get(permission, {"self"})

    def _organization(self, requested=None, permission="hr.employees.view"):
        actor_org = self.request.state.user.organization_id.hex
        if requested is None:
            return actor_org
        if self.request.state.is_admin:
            return requested
        if self.request.state.permission_unit_scopes.get(permission):
            if requested != actor_org:
                raise HTTPException(403, "Outside assigned data scope")
        elif "institution" in self.request.state.permission_global_scopes.get(permission, set()):
            return requested
        if requested != actor_org:
            raise HTTPException(403, "Outside assigned data scope")
        return actor_org

    async def _unit_in_organization(self, unit_id, organization_id, permission="hr.employees.view"):
        if not unit_id:
            return False
        row = await self.session.scalar(text(
            "WITH RECURSIVE units(id,path) AS ("
            "SELECT id,'|'||id||'|' FROM organizations WHERE id=:org AND is_active=1 "
            "UNION ALL SELECT child.id,units.path||child.id||'|' FROM organizations child "
            "JOIN units ON child.parent_id=units.id WHERE child.is_active=1 "
            "AND instr(units.path,'|'||child.id||'|')=0) "
            "SELECT 1 FROM units WHERE id=:unit"
        ), {"unit": unit_id, "org": organization_id})
        if row:
            require_unit(self.request, permission, unit_id)
        return bool(row)

    async def _organization_exists(self, organization_id):
        return bool(await self.session.scalar(text(
            "SELECT 1 FROM organizations WHERE id=:org AND is_active=1"
        ), {"org": organization_id}))

    async def _employee(self, employee_id, organization_id, permission="hr.employees.view"):
        row = (await self.session.execute(text(
            "SELECT * FROM hr_employees WHERE id=:id AND organization_id=:org"
        ), {"id": employee_id, "org": organization_id})).mappings().first()
        if row is None:
            raise HTTPException(404, "Employee unavailable within assigned scope")
        require_unit(self.request, permission, row["home_unit_id"], status_code=404)
        return dict(row)

    @staticmethod
    def _present_employee(row, include_sensitive=False):
        employee = {
            "id": row["id"], "organization_id": row["organization_id"], "employee_no": row["employee_no"],
            "full_name": row["full_name"], "home_unit_id": row["home_unit_id"],
            "position_title": row["position_title"], "employment_status": row["employment_status"],
            "hire_date": row["hire_date"], "projection_as_of_date": row["projection_as_of_date"],
            "row_version": row["row_version"],
        }
        if include_sensitive:
            employee["phone"] = row["phone"]
        if row.get("home_unit_name") is not None:
            employee["home_unit_name"] = row["home_unit_name"]
        return employee

    def _can_view_sensitive(self, unit_id):
        if self.request.state.is_admin:
            return True
        if "hr.employees.sensitive.view" not in self.request.state.permissions:
            return False
        allowed_units = unit_scope(self.request, "hr.employees.sensitive.view")
        return allowed_units is None or str(unit_id) in allowed_units

    async def create_employee(self, payload):
        require(self.request, "hr.employees.create")
        organization_id = self._organization(payload.get("organization_id"), "hr.employees.create")
        home_unit_id = payload["home_unit_id"]
        if not await self._unit_in_organization(home_unit_id, organization_id, "hr.employees.create"):
            raise HTTPException(422, "Home unit is unavailable within organization")
        effective_date = payload.get("hire_date") or date.today().isoformat()
        try:
            date.fromisoformat(effective_date)
        except ValueError:
            raise HTTPException(422, "Invalid hire date")
        employee_id, record_id = uuid4().hex, uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        values = dict(
            id=employee_id, org=organization_id, no=payload["employee_no"].strip(), name=payload["full_name"].strip(),
            phone=payload.get("phone", "").strip(), unit=home_unit_id, title=payload.get("position_title", "").strip(),
            hire=effective_date, projection=effective_date if effective_date <= date.today().isoformat() else date.today().isoformat(),
            record=record_id, actor=self.request.state.user.id.hex, now=now,
        )
        if not values["no"] or not values["name"]:
            raise HTTPException(422, "Employee number and name are required")
        try:
            await self.session.execute(text(
                "INSERT INTO hr_employees(id,organization_id,employee_no,full_name,phone,home_unit_id,position_title,employment_status,hire_date,projection_as_of_date,created_at,updated_at) "
                "VALUES(:id,:org,:no,:name,:phone,:unit,:title,'active',:hire,:projection,:now,:now)"
            ), values)
            await self.session.execute(text(
                "INSERT INTO hr_employment_records(id,organization_id,employee_id,change_type,to_unit_id,to_position_title,effective_date,status,reason,approved_by_user_id,approved_at,created_at,updated_at) "
                "VALUES(:record,:org,:id,'hire',:unit,:title,:hire,'approved','Initial employment',:actor,:now,:now,:now)"
            ), values)
            await self.session.flush()
        except IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise HTTPException(409, "Employee number already exists within organization") from None
            raise
        created = await self._employee(employee_id, organization_id, "hr.employees.create")
        self.request.state.audit_details = {
            "entity_type": "hr.employees",
            "entity_id": employee_id,
            "old": None,
            "new": {"employee_no": created["employee_no"], "full_name": created["full_name"],
                    "home_unit_id": created["home_unit_id"], "employment_status": created["employment_status"]},
            "reference": {"employment_record_id": record_id, "event": "hr.employee.created"},
            "summary": "HR employee created with approved hire decision",
        }
        return self._present_employee(created, self._can_view_sensitive(created["home_unit_id"]))

    async def get_employee(self, employee_id):
        require(self.request, "hr.employees.view")
        organization_id = self._organization()
        row = await self._employee(employee_id, organization_id, "hr.employees.view")
        row["home_unit_name"] = await self.session.scalar(
            text("SELECT name FROM organizations WHERE id=:unit AND is_active=1"),
            {"unit": row["home_unit_id"]},
        )
        return self._present_employee(row, self._can_view_sensitive(row["home_unit_id"]))

    async def list_employees(self, q=None, unit_id=None, position_title=None,
                             employment_status=None, page=1, page_size=20):
        require(self.request, "hr.employees.view")
        organization_id = self._organization()
        params = {"org": organization_id}
        scoped = unit_filter(self.request, "hr.employees.view", "home_unit_id", params)
        filters = []
        if q:
            filters.append("(employee_no LIKE :q OR full_name LIKE :q)")
            params["q"] = f"%{q.strip()}%"
        if unit_id:
            filters.append("home_unit_id=:unit_id")
            params["unit_id"] = unit_id
        if position_title:
            filters.append("position_title=:position_title")
            params["position_title"] = position_title
        if employment_status:
            filters.append("employment_status=:employment_status")
            params["employment_status"] = employment_status
        where = " WHERE organization_id=:org" + scoped
        if filters:
            where += " AND " + " AND ".join(filters)
        total = await self.session.scalar(text("SELECT COUNT(*) FROM hr_employees" + where), params)
        active = await self.session.scalar(text("SELECT COUNT(*) FROM hr_employees" + where + " AND employment_status='active'"), params)
        suspended = await self.session.scalar(text("SELECT COUNT(*) FROM hr_employees" + where + " AND employment_status='suspended'"), params)
        future_params = dict(params)
        future_scoped = unit_filter(self.request, "hr.employees.view", "e.home_unit_id", future_params, prefix="future_scope_unit")
        future_filters = [item.replace("employee_no", "e.employee_no").replace("full_name", "e.full_name")
                          .replace("home_unit_id", "e.home_unit_id").replace("position_title", "e.position_title")
                          .replace("employment_status", "e.employment_status") for item in filters]
        future_decisions = await self.session.scalar(text(
            "SELECT COUNT(*) FROM hr_employment_records r JOIN hr_employees e ON e.id=r.employee_id "
            "WHERE e.organization_id=:org" + future_scoped + " AND r.status='approved' AND r.is_current=1 "
            "AND r.effective_date>:today" + (" AND " + " AND ".join(future_filters) if future_filters else "")
        ), {**future_params, "today": date.today().isoformat()})
        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size
        rows = (await self.session.execute(text(
            "SELECT e.*, o.name AS home_unit_name FROM hr_employees e "
            "LEFT JOIN organizations o ON o.id=e.home_unit_id" + where.replace("home_unit_id", "e.home_unit_id") +
            " ORDER BY e.employee_no LIMIT :limit OFFSET :offset"
        ), params)).mappings().all()
        return {"items": [
            self._present_employee(dict(row), self._can_view_sensitive(row["home_unit_id"]))
            | {"home_unit_name": row.get("home_unit_name") or "غير متاح"}
            for row in rows
        ], "total": int(total or 0), "page": page, "page_size": page_size,
                "summary": {"total": int(total or 0), "active": int(active or 0),
                            "suspended": int(suspended or 0), "future_decisions": int(future_decisions or 0)}}

    async def create_decision(self, employee_id, payload):
        require(self.request, "hr.employment_records.manage")
        organization_id = self._organization()
        employee = await self._employee(employee_id, organization_id, "hr.employment_records.manage")
        change_type, effective_date = payload["change_type"], payload["effective_date"]
        try:
            date.fromisoformat(effective_date)
        except ValueError:
            raise HTTPException(422, "Invalid effective date")
        if change_type == "hire":
            raise HTTPException(422, "Hire is created only with employee creation")
        to_unit_id = payload.get("to_unit_id") or employee["home_unit_id"]
        if change_type == "transfer" and not await self._unit_in_organization(
            to_unit_id, organization_id, "hr.employment_records.manage"
        ):
            raise HTTPException(422, "Target unit is unavailable within organization")
        supersedes = payload.get("supersedes_record_id")
        same_day = await self.session.scalar(text(
            "SELECT 1 FROM hr_employment_records WHERE employee_id=:employee AND organization_id=:org "
            "AND effective_date=:date AND status='approved' AND is_current=1 AND change_type IN ('transfer','position_change','suspension','termination','reinstatement')"
            + (" AND id<>:supersedes" if supersedes else "")
        ), dict(employee=employee_id, org=organization_id, date=effective_date, supersedes=supersedes))
        if same_day:
            raise HTTPException(409, "Conflicting approved decision on the same effective date")
        if supersedes:
            original = await self.session.scalar(text(
                "SELECT 1 FROM hr_employment_records WHERE id=:id AND employee_id=:employee AND organization_id=:org AND status='approved' AND is_current=1"
            ), {"id": supersedes, "employee": employee_id, "org": organization_id})
            if not original:
                raise HTTPException(409, "Original decision is unavailable for correction")
            current_replacement = await self.session.scalar(text(
                "SELECT 1 FROM hr_employment_records WHERE supersedes_record_id=:id AND is_current=1"
            ), {"id": supersedes})
            if current_replacement:
                raise HTTPException(409, "Decision already has an active correction")
            result = await self.session.execute(text(
                "UPDATE hr_employment_records SET is_current=0,row_version=row_version+1,updated_at=:now WHERE id=:id AND row_version=:version"
            ), {"id": supersedes, "version": payload.get("supersedes_row_version"), "now": datetime.now(timezone.utc).isoformat()})
            if result.rowcount != 1:
                raise HTTPException(409, "Employment decision changed; reload before correcting")
        record_id, now = uuid4().hex, datetime.now(timezone.utc).isoformat()
        await self.session.execute(text(
            "INSERT INTO hr_employment_records(id,organization_id,employee_id,change_type,from_unit_id,to_unit_id,from_position_title,to_position_title,effective_date,reference_no,supersedes_record_id,status,reason,notes,approved_by_user_id,approved_at,created_at,updated_at) "
            "VALUES(:id,:org,:employee,:kind,:from_unit,:to_unit,:from_title,:to_title,:date,:reference,:supersedes,'approved',:reason,:notes,:actor,:now,:now,:now)"
        ), dict(id=record_id, org=organization_id, employee=employee_id, kind=change_type,
                 from_unit=employee["home_unit_id"], to_unit=to_unit_id,
                 from_title=employee["position_title"], to_title=payload.get("to_position_title", employee["position_title"]),
                 date=effective_date, reference=payload.get("reference_no", ""), supersedes=supersedes,
                 reason=payload.get("reason", ""), notes=payload.get("notes", ""), actor=self.request.state.user.id.hex, now=now))
        if effective_date <= date.today().isoformat():
            await self._rebuild_projection(employee_id, organization_id)
        await self.session.flush()
        decision = await self.decision(record_id)
        self.request.state.audit_details = {
            "entity_type": "hr.employment_records",
            "entity_id": record_id,
            "old": {"supersedes_record_id": supersedes} if supersedes else None,
            "new": {"employee_id": employee_id, "change_type": change_type,
                    "effective_date": effective_date, "to_unit_id": to_unit_id,
                    "to_position_title": decision["to_position_title"], "status": "approved"},
            "reference": {"event": "hr.employment.approved", "correction": bool(supersedes)},
            "summary": "HR employment decision approved" + (" as correction" if supersedes else ""),
        }
        return decision

    async def _rebuild_projection(self, employee_id, organization_id):
        today = date.today().isoformat()
        rows = (await self.session.execute(text(
            "SELECT * FROM hr_employment_records WHERE employee_id=:employee AND organization_id=:org "
            "AND status='approved' AND is_current=1 AND effective_date<=:today ORDER BY effective_date,id"
        ), {"employee": employee_id, "org": organization_id, "today": today})).mappings().all()
        hire = next((row for row in rows if row["change_type"] == "hire"), None)
        if hire is None:
            raise HTTPException(409, "Approved hire decision is required to rebuild employee projection")
        unit, title, status = hire["to_unit_id"], hire["to_position_title"], "active"
        for row in rows:
            if row["id"] == hire["id"]:
                continue
            if row["change_type"] == "transfer": unit = row["to_unit_id"]
            if row["change_type"] in ("hire", "position_change"): title = row["to_position_title"]
            status = STATUS_BY_CHANGE.get(row["change_type"], status)
        await self.session.execute(text(
            "UPDATE hr_employees SET home_unit_id=:unit,position_title=:title,employment_status=:status,projection_as_of_date=:today,row_version=row_version+1,updated_at=:now WHERE id=:employee AND organization_id=:org"
        ), dict(unit=unit, title=title, status=status, today=today, now=datetime.now(timezone.utc).isoformat(), employee=employee_id, org=organization_id))

    async def decision(self, record_id):
        require(self.request, "hr.employment_records.view")
        organization_id = self._organization()
        row = (await self.session.execute(text(
            "SELECT * FROM hr_employment_records WHERE id=:id AND organization_id=:org"
        ), {"id": record_id, "org": organization_id})).mappings().first()
        if row is None:
            raise HTTPException(404, "Employment decision unavailable within assigned scope")
        require_unit(self.request, "hr.employment_records.view", row["to_unit_id"], status_code=404)
        return dict(row)

    async def list_decisions(self, q=None, change_type=None, status=None, unit_id=None,
                             effective_from=None, effective_to=None, page=1, page_size=20):
        require(self.request, "hr.employment_records.view")
        organization_id = self._organization()
        params = {"org": organization_id}
        scoped = unit_filter(self.request, "hr.employment_records.view", "e.home_unit_id", params)
        filters = []
        if q:
            filters.append("(e.employee_no LIKE :q OR e.full_name LIKE :q OR r.reference_no LIKE :q)")
            params["q"] = f"%{q.strip()}%"
        if change_type:
            filters.append("r.change_type=:change_type")
            params["change_type"] = change_type
        if status:
            filters.append("r.status=:status")
            params["status"] = status
        if unit_id:
            filters.append("e.home_unit_id=:unit_id")
            params["unit_id"] = unit_id
        if effective_from:
            filters.append("r.effective_date>=:effective_from")
            params["effective_from"] = effective_from
        if effective_to:
            filters.append("r.effective_date<=:effective_to")
            params["effective_to"] = effective_to
        where = " WHERE r.organization_id=:org" + scoped
        if filters:
            where += " AND " + " AND ".join(filters)
        base = " FROM hr_employment_records r JOIN hr_employees e ON e.id=r.employee_id "
        total = await self.session.scalar(text("SELECT COUNT(*)" + base + where), params)
        approved = await self.session.scalar(text("SELECT COUNT(*)" + base + where + " AND r.status='approved'"), params)
        future_params = dict(params)
        future_where = where + " AND r.status='approved' AND r.effective_date>:today"
        future_params["today"] = date.today().isoformat()
        future = await self.session.scalar(text("SELECT COUNT(*)" + base + future_where), future_params)
        review = await self.session.scalar(text("SELECT COUNT(*)" + base + where + " AND r.status NOT IN ('approved','rejected','cancelled')"), params)
        offset = (page - 1) * page_size
        rows = (await self.session.execute(text(
            "SELECT r.*, e.employee_no, e.full_name, e.position_title, e.home_unit_id, "
            "u.name AS home_unit_name FROM hr_employment_records r "
            "JOIN hr_employees e ON e.id=r.employee_id LEFT JOIN organizations u ON u.id=e.home_unit_id" + where +
            " ORDER BY r.effective_date DESC, r.created_at DESC LIMIT :limit OFFSET :offset"
        ), {**params, "limit": page_size, "offset": offset})).mappings().all()
        units = (await self.session.execute(text(
            "SELECT DISTINCT e.home_unit_id, u.name FROM hr_employment_records r "
            "JOIN hr_employees e ON e.id=r.employee_id LEFT JOIN organizations u ON u.id=e.home_unit_id "
            "WHERE r.organization_id=:org" + scoped + " ORDER BY u.name"
        ), params)).all()
        pages = max(1, (int(total or 0) + page_size - 1) // page_size)
        return {
            "items": [dict(row) for row in rows], "total": int(total or 0),
            "page": page, "page_size": page_size, "pages": pages,
            "summary": {"total": int(total or 0), "approved": int(approved or 0),
                         "future": int(future or 0), "review": int(review or 0)},
            "units": [{"id": row[0], "name": row[1]} for row in units if row[0]],
        }

    async def history(self, employee_id, as_of=None):
        require(self.request, "hr.employment_records.view")
        organization_id = self._organization()
        await self._employee(employee_id, organization_id, "hr.employment_records.view")
        params = {"employee": employee_id, "org": organization_id}
        clause = ""
        if as_of:
            try: date.fromisoformat(as_of)
            except ValueError: raise HTTPException(422, "Invalid as_of date")
            clause = " AND effective_date<=:as_of"
            params["as_of"] = as_of
        rows = (await self.session.execute(text(
            "SELECT * FROM hr_employment_records WHERE employee_id=:employee AND organization_id=:org "
            "AND status='approved' AND is_current=1" + clause + " ORDER BY effective_date,id"
        ), params)).mappings().all()
        return {"items": [dict(row) for row in rows]}
