"""Pure S-01B dependency and CPM calculation core.

The engine consumes S-01A ``WorkCalendar`` instances.  It neither persists a
schedule nor changes master planning, WEP, work orders, or Actual facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal

from .scheduling_calendar import CalendarException, CalendarValidationError, WorkCalendar


UTC = timezone.utc
DependencyType = Literal[
    "finish_to_start", "start_to_start", "finish_to_finish", "start_to_finish",
]
VALID_DEPENDENCY_TYPES = frozenset(DependencyType.__args__)


class SchedulingValidationError(ValueError):
    """Raised for an invalid dependency graph or invalid scheduling input."""


@dataclass(frozen=True)
class ActivityScheduleInput:
    activity_id: str
    calendar: WorkCalendar | None
    work_minutes: int | None
    earliest_start: datetime | None = None
    latest_finish: datetime | None = None
    exceptions: tuple[CalendarException, ...] = ()


@dataclass(frozen=True)
class ActivityDependency:
    predecessor_id: str
    successor_id: str
    dependency_type: DependencyType = "finish_to_start"


@dataclass(frozen=True)
class ScheduleItem:
    activity_id: str
    scheduling_state: str
    block_reason: str | None = None
    early_start: datetime | None = None
    early_finish: datetime | None = None
    late_start: datetime | None = None
    late_finish: datetime | None = None
    total_float_minutes: int | None = None
    is_critical: bool = False


@dataclass(frozen=True)
class ScheduleCalculation:
    state: Literal["complete", "partial"]
    project_finish: datetime | None
    items: tuple[ScheduleItem, ...]


def _utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None:
        raise SchedulingValidationError(f"{label} must include a timezone")
    return value.astimezone(UTC)


def _topological_order(activity_ids: set[str], dependencies: Iterable[ActivityDependency]) -> list[str]:
    successors = {activity_id: [] for activity_id in activity_ids}
    indegree = {activity_id: 0 for activity_id in activity_ids}
    for dependency in dependencies:
        if dependency.dependency_type not in VALID_DEPENDENCY_TYPES:
            raise SchedulingValidationError("Unsupported dependency type")
        if dependency.predecessor_id == dependency.successor_id:
            raise SchedulingValidationError("An activity cannot depend on itself")
        if dependency.predecessor_id not in activity_ids or dependency.successor_id not in activity_ids:
            raise SchedulingValidationError("Dependencies must reference scheduled activities")
        successors[dependency.predecessor_id].append(dependency.successor_id)
        indegree[dependency.successor_id] += 1
    queue = sorted(activity_id for activity_id, degree in indegree.items() if degree == 0)
    result: list[str] = []
    while queue:
        activity_id = queue.pop(0)
        result.append(activity_id)
        for successor in sorted(successors[activity_id]):
            indegree[successor] -= 1
            if indegree[successor] == 0:
                queue.append(successor)
                queue.sort()
    if len(result) != len(activity_ids):
        raise SchedulingValidationError("Dependency graph contains a cycle")
    return result


def calculate_schedule(
    project_start: datetime,
    activities: Iterable[ActivityScheduleInput],
    dependencies: Iterable[ActivityDependency] = (),
) -> ScheduleCalculation:
    """Calculate forward/backward CPM dates using productive calendar minutes.

    Any missing calendar or duration produces an explicit blocked item.  Dates
    are never invented; therefore a blocked graph has a ``partial`` result and
    deliberately exposes no critical path or float values.
    """
    project_start = _utc(project_start, "project_start")
    inputs = tuple(activities)
    by_id = {activity.activity_id: activity for activity in inputs}
    if len(by_id) != len(inputs) or not by_id:
        raise SchedulingValidationError("Activities must be non-empty and have unique ids")
    edges = tuple(dependencies)
    order = _topological_order(set(by_id), edges)
    incoming = {activity_id: [] for activity_id in by_id}
    outgoing = {activity_id: [] for activity_id in by_id}
    for edge in edges:
        incoming[edge.successor_id].append(edge)
        outgoing[edge.predecessor_id].append(edge)

    calculated: dict[str, ScheduleItem] = {}
    for activity_id in order:
        activity = by_id[activity_id]
        if activity.calendar is None:
            calculated[activity_id] = ScheduleItem(activity_id, "blocked_calendar", "missing_calendar")
            continue
        if activity.work_minutes is None or activity.work_minutes < 0:
            calculated[activity_id] = ScheduleItem(activity_id, "blocked_insufficient_estimate", "missing_work_minutes")
            continue
        predecessors = [calculated[edge.predecessor_id] for edge in incoming[activity_id]]
        if any(item.early_start is None or item.early_finish is None for item in predecessors):
            calculated[activity_id] = ScheduleItem(activity_id, "blocked_dependency", "predecessor_unscheduled")
            continue
        earliest = max(project_start, _utc(activity.earliest_start, "earliest_start") if activity.earliest_start else project_start)
        finish_bounds: list[datetime] = []
        for edge in incoming[activity_id]:
            predecessor = calculated[edge.predecessor_id]
            if edge.dependency_type == "finish_to_start":
                earliest = max(earliest, predecessor.early_finish)  # type: ignore[arg-type]
            elif edge.dependency_type == "start_to_start":
                earliest = max(earliest, predecessor.early_start)  # type: ignore[arg-type]
            elif edge.dependency_type == "finish_to_finish":
                finish_bounds.append(predecessor.early_finish)  # type: ignore[arg-type]
            else:  # start_to_finish
                finish_bounds.append(predecessor.early_start)  # type: ignore[arg-type]
        try:
            start = activity.calendar.start_at_or_after(earliest, activity.exceptions)
            finish = activity.calendar.finish_after(start, activity.work_minutes, activity.exceptions)
            for bound in finish_bounds:
                if finish < bound:
                    start = activity.calendar.start_before(bound, activity.work_minutes, activity.exceptions)
                    start = activity.calendar.start_at_or_after(max(start, earliest), activity.exceptions)
                    finish = activity.calendar.finish_after(start, activity.work_minutes, activity.exceptions)
            if activity.latest_finish and finish > _utc(activity.latest_finish, "latest_finish"):
                calculated[activity_id] = ScheduleItem(activity_id, "blocked_external", "latest_finish_constraint")
            else:
                calculated[activity_id] = ScheduleItem(activity_id, "ready", early_start=start, early_finish=finish)
        except CalendarValidationError as exc:
            calculated[activity_id] = ScheduleItem(activity_id, "blocked_calendar", str(exc))

    scheduled = [item for item in calculated.values() if item.early_finish is not None]
    if len(scheduled) != len(inputs):
        return ScheduleCalculation("partial", None, tuple(calculated[activity_id] for activity_id in order))
    project_finish = max(item.early_finish for item in scheduled if item.early_finish is not None)
    late: dict[str, tuple[datetime, datetime]] = {}
    for activity_id in reversed(order):
        activity = by_id[activity_id]
        finish_deadline = project_finish
        start_deadline: datetime | None = None
        for edge in outgoing[activity_id]:
            successor_start, successor_finish = late[edge.successor_id]
            if edge.dependency_type == "finish_to_start":
                finish_deadline = min(finish_deadline, successor_start)
            elif edge.dependency_type == "finish_to_finish":
                finish_deadline = min(finish_deadline, successor_finish)
            elif edge.dependency_type == "start_to_start":
                start_deadline = min(start_deadline, successor_start) if start_deadline else successor_start
            else:  # start_to_finish
                start_deadline = min(start_deadline, successor_finish) if start_deadline else successor_finish
        assert activity.calendar is not None and activity.work_minutes is not None
        latest_start = activity.calendar.start_before(finish_deadline, activity.work_minutes, activity.exceptions)
        if start_deadline:
            latest_start = min(latest_start, activity.calendar.start_at_or_before(start_deadline, activity.exceptions))
        latest_finish = activity.calendar.finish_after(latest_start, activity.work_minutes, activity.exceptions)
        late[activity_id] = (latest_start, latest_finish)

    result: list[ScheduleItem] = []
    for activity_id in order:
        early = calculated[activity_id]
        latest_start, latest_finish = late[activity_id]
        assert early.early_start is not None
        float_minutes = int((latest_start - early.early_start).total_seconds() // 60)
        result.append(ScheduleItem(
            activity_id=activity_id, scheduling_state="ready", early_start=early.early_start,
            early_finish=early.early_finish, late_start=latest_start, late_finish=latest_finish,
            total_float_minutes=float_minutes, is_critical=float_minutes == 0,
        ))
    return ScheduleCalculation("complete", project_finish, tuple(result))
