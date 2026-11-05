"""Read-only, deterministic projection of dated Work Order actual quantities."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import text

from .planning_service import PlanningService


SUPPORTED_EVENT_TYPES = frozenset({"quantity_update"})
EXCLUDED_WORK_ORDER_STATUSES = frozenset({"rejected"})


def _canonical_decimal(value: Decimal) -> str:
    value = Decimal(0) if value == 0 else value
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _digest(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _as_decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class ActualReadAdapter(PlanningService):
    """Build the scheduling Actual input without persisting another Actual truth."""

    async def read(self, project_id: str, actual_as_of: datetime):
        # Both source and consumer permissions must authorize the same project.
        project = await self.project(project_id, "pm.execution.view")
        await self.project(project_id, "pm.schedule.view")
        cutoff = _as_utc(actual_as_of)

        activities = (await self.session.execute(text(
            "SELECT id,activity_code,name,planned_quantity,unit,deleted_at "
            "FROM pm_activities WHERE project_id=:p ORDER BY id"
        ), {"p": project_id})).mappings().all()
        orders = (await self.session.execute(text(
            "SELECT id,activity_id,work_order_code,status,actual_quantity_snapshot,deleted_at "
            "FROM pm_work_orders WHERE project_id=:p ORDER BY id"
        ), {"p": project_id})).mappings().all()
        events = (await self.session.execute(text(
            "SELECT id,project_id,work_order_id,activity_id,before_quantity,after_quantity,"
            "delta,event_type,recorded_by,recorded_at FROM pm_execution_quantity_events "
            "WHERE project_id=:p ORDER BY recorded_at,id"
        ), {"p": project_id})).mappings().all()

        source = {
            "contract_version": "s04.2-v1",
            "project_id": project_id,
            "organization_id": project["organization_id"],
            "actual_as_of": cutoff.isoformat(),
            "activities": [dict(row) for row in activities],
            "work_orders": [dict(row) for row in orders],
            "events": [dict(row) for row in events],
        }
        input_hash = _digest(source)
        issues = []
        excluded = []
        activity_rows = {row["id"]: row for row in activities}
        order_rows = {row["id"]: row for row in orders}
        accepted_by_activity = {row["id"]: Decimal(0) for row in activities}
        accepted_ids_by_activity = {row["id"]: [] for row in activities}
        lifetime_by_order = {row["id"]: Decimal(0) for row in orders}
        seen_event_ids = set()

        for event in events:
            event_id = event["id"]
            if event_id in seen_event_ids:
                issues.append({"code": "duplicate_event_id", "event_id": event_id, "blocking": True})
                continue
            seen_event_ids.add(event_id)
            order = order_rows.get(event["work_order_id"])
            activity = activity_rows.get(event["activity_id"])
            if not order or not activity:
                issues.append({"code": "missing_event_reference", "event_id": event_id, "blocking": True})
                continue
            if order["activity_id"] != event["activity_id"]:
                issues.append({"code": "activity_unit_scope_mismatch", "event_id": event_id,
                               "work_order_id": order["id"], "blocking": True})
                continue
            if event["event_type"] not in SUPPORTED_EVENT_TYPES:
                issues.append({"code": "unsupported_event_type", "event_id": event_id,
                               "event_type": event["event_type"], "blocking": True})
                continue
            delta = _as_decimal(event["delta"])
            if delta is None:
                issues.append({"code": "invalid_event_quantity", "event_id": event_id, "blocking": True})
                continue
            if order["deleted_at"] is not None or order["status"] in EXCLUDED_WORK_ORDER_STATUSES:
                excluded.append({"event_id": event_id, "work_order_id": order["id"],
                                 "reason": "deleted_work_order" if order["deleted_at"] else "rejected_work_order"})
                continue
            try:
                recorded_at = _as_utc(datetime.fromisoformat(event["recorded_at"]))
            except (TypeError, ValueError):
                issues.append({"code": "missing_or_invalid_event_date", "event_id": event_id, "blocking": True})
                continue
            lifetime_by_order[order["id"]] += delta
            if recorded_at <= cutoff:
                accepted_by_activity[activity["id"]] += delta
                accepted_ids_by_activity[activity["id"]].append(event_id)

        undated_by_activity = {row["id"]: Decimal(0) for row in activities}
        for order in orders:
            if order["deleted_at"] is not None or order["status"] in EXCLUDED_WORK_ORDER_STATUSES:
                continue
            snapshot = _as_decimal(order["actual_quantity_snapshot"])
            if snapshot is None:
                issues.append({"code": "invalid_actual_snapshot", "work_order_id": order["id"], "blocking": True})
                continue
            proven = lifetime_by_order[order["id"]]
            difference = snapshot - proven
            if difference > 0:
                undated_by_activity.setdefault(order["activity_id"], Decimal(0))
                undated_by_activity[order["activity_id"]] += difference
                issues.append({"code": "undated_actual", "work_order_id": order["id"],
                               "quantity": _canonical_decimal(difference), "blocking": True})
            elif difference < 0:
                issues.append({"code": "snapshot_event_mismatch", "work_order_id": order["id"],
                               "snapshot": _canonical_decimal(snapshot),
                               "event_total": _canonical_decimal(proven), "blocking": True})

        result_items = []
        for activity in activities:
            actual = accepted_by_activity[activity["id"]]
            planned = _as_decimal(activity["planned_quantity"])
            unit = (activity["unit"] or "").strip()
            item_issues = []
            if activity["deleted_at"] is not None:
                item_issues.append("deleted_activity")
            if planned is None:
                item_issues.append("invalid_planned_quantity")
                issues.append({"code": "invalid_planned_quantity", "activity_id": activity["id"], "blocking": True})
            if not unit:
                item_issues.append("missing_unit")
                issues.append({"code": "missing_unit", "activity_id": activity["id"], "blocking": True})
            overrun = planned is not None and actual > planned
            if overrun:
                item_issues.append("actual_overrun")
                issues.append({"code": "actual_overrun", "activity_id": activity["id"],
                               "quantity": _canonical_decimal(actual - planned), "blocking": False})
            result_items.append({
                "activity_id": activity["id"], "activity_code": activity["activity_code"],
                "unit": unit or None, "planned_quantity": _canonical_decimal(planned) if planned is not None else None,
                "actual_quantity": _canonical_decimal(actual),
                "undated_actual": _canonical_decimal(undated_by_activity.get(activity["id"], Decimal(0))),
                "remaining_quantity": _canonical_decimal(max(planned - actual, Decimal(0))) if planned is not None else None,
                "overrun": overrun, "source_event_ids": accepted_ids_by_activity[activity["id"]],
                "issues": item_issues,
            })

        output_core = {
            "project_id": project_id, "organization_id": project["organization_id"],
            "actual_as_of": cutoff.isoformat(), "input_hash": input_hash,
            "items": result_items, "excluded_events": excluded,
            "issues": sorted(issues, key=lambda item: (item["code"], item.get("event_id", ""),
                                                        item.get("work_order_id", ""), item.get("activity_id", ""))),
        }
        result = dict(output_core, output_hash=_digest(output_core))
        self.request.state.audit_export = True
        self.request.state.audit_details = {
            "entity_type": "pm.actual_read", "entity_id": project_id,
            "new": {"organization_id": project["organization_id"], "actual_as_of": cutoff.isoformat(),
                    "input_hash": input_hash, "output_hash": result["output_hash"],
                    "source_event_ids": sorted(seen_event_ids),
                    "blocking_issue_count": sum(1 for issue in issues if issue["blocking"])},
            "summary": "PM scheduling Actual projection read",
        }
        return result
