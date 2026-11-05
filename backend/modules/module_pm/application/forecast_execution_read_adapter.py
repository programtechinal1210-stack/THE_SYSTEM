"""Read-only S-04.4 projection of a proposed forecast against execution commitments."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import text

from .actual_read_adapter import ActualReadAdapter
from .planning_service import PlanningService


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _day(value):
    return datetime.fromisoformat(value).date() if value else None


class ForecastExecutionReadAdapter(PlanningService):
    """Compare facts without changing WEP, WO, Daily Work, or a schedule version."""

    async def read(self, project_id: str, forecast_version_id: str):
        # Each source retains its own permission and the project scope is checked for each.
        project = await self.project(project_id, "pm.schedule.view")
        await self.project(project_id, "pm.wep.view")
        await self.project(project_id, "pm.execution.view")
        await self.project(project_id, "daily_work.view")
        forecast = (await self.session.execute(text(
            "SELECT * FROM pm_schedule_versions WHERE id=:id AND project_id=:p"
        ), {"id": forecast_version_id, "p": project_id})).mappings().first()
        if not forecast:
            raise HTTPException(404, "Schedule version not found")
        if forecast["status"] not in ("draft", "proposed"):
            raise HTTPException(422, "Execution impact is available only for a draft or proposed forecast")
        if not forecast["actual_as_of"]:
            raise HTTPException(422, "Forecast has no Actual measurement timestamp")

        actual = await ActualReadAdapter(self.session, self.request).read(
            project_id, datetime.fromisoformat(forecast["actual_as_of"]))
        actual_by_activity = {item["activity_id"]: item for item in actual["items"]}
        proposed = (await self.session.execute(text(
            "SELECT i.*,a.activity_code,a.name FROM pm_schedule_items i "
            "JOIN pm_activities a ON a.id=i.activity_id AND a.project_id=i.project_id "
            "WHERE i.schedule_version_id=:v AND i.project_id=:p AND a.deleted_at IS NULL ORDER BY a.activity_code,i.id"
        ), {"v": forecast_version_id, "p": project_id})).mappings().all()
        approved = (await self.session.execute(text(
            "SELECT id,version_no FROM pm_schedule_versions WHERE project_id=:p AND status='approved' "
            "ORDER BY version_no DESC,id DESC LIMIT 1"
        ), {"p": project_id})).mappings().first()
        approved_items = {}
        if approved:
            approved_items = {row["activity_id"]: dict(row) for row in (await self.session.execute(text(
                "SELECT activity_id,early_start,early_finish FROM pm_schedule_items WHERE schedule_version_id=:v AND project_id=:p"
            ), {"v": approved["id"], "p": project_id})).mappings().all()}

        weekly_rows = (await self.session.execute(text(
            "SELECT wi.activity_id,wi.id AS weekly_item_id,wi.weekly_target,wi.status AS item_status,"
            "w.id AS weekly_plan_id,w.week_code,w.start_date,w.end_date,w.status AS plan_status "
            "FROM pm_weekly_plan_items wi JOIN pm_weekly_plans w ON w.id=wi.plan_id AND w.project_id=wi.project_id "
            "WHERE wi.project_id=:p AND wi.deleted_at IS NULL AND w.deleted_at IS NULL "
            "AND w.status IN ('approved','in_progress','closed') ORDER BY w.start_date,w.id,wi.id"
        ), {"p": project_id})).mappings().all()
        weekly_by_activity = {}
        for row in weekly_rows:
            weekly_by_activity.setdefault(row["activity_id"], []).append(dict(row))
        work_orders = (await self.session.execute(text(
            "SELECT id,activity_id,work_order_code,status,actual_quantity_snapshot FROM pm_work_orders "
            "WHERE project_id=:p AND deleted_at IS NULL ORDER BY work_order_code,id"
        ), {"p": project_id})).mappings().all()
        orders_by_activity = {}
        for row in work_orders:
            orders_by_activity.setdefault(row["activity_id"], []).append(dict(row))
        daily_rows = (await self.session.execute(text(
            "SELECT id,activity_id,work_order_id,work_date,status,readiness_status,source_type,source_id,"
            "assignee_user_id,team_name,blocker_summary FROM dw_daily_work_items "
            "WHERE project_id=:p AND deleted_at IS NULL AND activity_id IS NOT NULL "
            "ORDER BY work_date,id"
        ), {"p": project_id})).mappings().all()
        daily_by_activity = {}
        daily_ids = []
        for row in daily_rows:
            daily_by_activity.setdefault(row["activity_id"], []).append(dict(row))
            daily_ids.append(row["id"])
        blockers_by_daily, assignments_by_daily = {}, {}
        if daily_ids:
            params = {"p": project_id, **{f"d{i}": value for i, value in enumerate(daily_ids)}}
            placeholders = ",".join(f":d{i}" for i in range(len(daily_ids)))
            blockers = (await self.session.execute(text(
                "SELECT b.daily_work_id,b.id,b.blocker_type,b.description,b.status FROM dw_blockers b "
                f"JOIN dw_daily_work_items d ON d.id=b.daily_work_id WHERE d.project_id=:p AND b.status='open' AND b.daily_work_id IN ({placeholders}) "
                "ORDER BY b.created_at,b.id"
            ), params)).mappings().all()
            assignments = (await self.session.execute(text(
                "SELECT a.daily_work_id,a.id,a.subject_type,a.subject_id,a.role,a.is_lead,a.status FROM dw_work_item_assignments a "
                f"JOIN dw_daily_work_items d ON d.id=a.daily_work_id WHERE d.project_id=:p AND a.daily_work_id IN ({placeholders}) "
                "ORDER BY a.created_at,a.id"
            ), params)).mappings().all()
            for row in blockers:
                blockers_by_daily.setdefault(row["daily_work_id"], []).append(dict(row))
            for row in assignments:
                assignments_by_daily.setdefault(row["daily_work_id"], []).append(dict(row))

        items = []
        for row in proposed:
            item = dict(row)
            start, finish = _day(item["early_start"]), _day(item["early_finish"])
            weekly = weekly_by_activity.get(item["activity_id"], [])
            daily = daily_by_activity.get(item["activity_id"], [])
            for entry in daily:
                entry["open_blockers"] = blockers_by_daily.get(entry["id"], [])
                entry["assignments"] = assignments_by_daily.get(entry["id"], [])
            inside_week = [entry for entry in weekly if start and finish and _day(entry["start_date"]) <= start and finish <= _day(entry["end_date"])]
            past_week = bool(finish and any(finish > _day(entry["end_date"]) for entry in weekly))
            prior = approved_items.get(item["activity_id"])
            slipped = bool(finish and prior and prior["early_finish"] and finish > _day(prior["early_finish"]))
            has_blocker = any(entry["open_blockers"] for entry in daily)
            unready = any(entry["readiness_status"] == "not_ready" for entry in daily)
            if item["scheduling_state"].startswith("blocked_") or not start or not finish:
                classification, reasons = "unavailable", ["forecast_dates_unavailable"]
            elif slipped or past_week:
                classification, reasons = "delayed", (["later_than_approved_forecast"] if slipped else []) + (["outside_weekly_commitment"] if past_week else [])
            elif not weekly:
                classification, reasons = "unavailable", ["weekly_commitment_unavailable"]
            elif not inside_week:
                classification, reasons = "needs_review", ["forecast_outside_committed_week"]
            elif has_blocker or unready:
                classification, reasons = "needs_review", (["open_daily_blocker"] if has_blocker else []) + (["daily_work_not_ready"] if unready else [])
            else:
                classification, reasons = "aligned", []
            actual_item = actual_by_activity.get(item["activity_id"], {})
            items.append({
                "activity_id": item["activity_id"], "activity_code": item["activity_code"], "name": item["name"],
                "forecast": {key: item[key] for key in ("scheduling_state", "early_start", "early_finish", "remaining_work_minutes", "planned_quantity", "actual_quantity_at_measurement", "remaining_quantity")},
                "approved_forecast": approved_items.get(item["activity_id"]), "weekly_commitments": weekly,
                "work_orders": orders_by_activity.get(item["activity_id"], []), "daily_work": daily,
                "actual": actual_item, "actual_source": "pm_execution_quantity_events", "classification": classification,
                "reasons": reasons,
            })
        core = {"project_id": project_id, "organization_id": project["organization_id"], "forecast_version_id": forecast_version_id,
                "forecast_status": forecast["status"], "baseline_id": forecast["baseline_id"], "actual_as_of": forecast["actual_as_of"],
                "approved_version": dict(approved) if approved else None, "actual_input_hash": forecast["actual_input_hash"],
                "actual_output_hash": actual["output_hash"], "items": items}
        result = dict(core, output_hash=_digest(core))
        self.request.state.audit_export = True
        self.request.state.audit_details = {"entity_type": "pm.forecast_execution_impact", "entity_id": forecast_version_id,
            "new": {"project_id": project_id, "organization_id": project["organization_id"], "baseline_id": forecast["baseline_id"],
                    "actual_as_of": forecast["actual_as_of"], "actual_input_hash": forecast["actual_input_hash"], "output_hash": result["output_hash"],
                    "source_event_ids": json.loads(forecast["actual_source_event_ids_json"] or "[]")}, "summary": "PM forecast execution impact read"}
        return result
