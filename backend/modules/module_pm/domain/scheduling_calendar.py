"""Pure, deterministic calendar arithmetic for PM scheduling (S-01A).

No persistence, HTTP, resource allocation, or Actual execution behavior lives
here.  All public datetimes are timezone-aware and normalized to UTC.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


UTC = timezone.utc
WEEKDAY_NAMES = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                 "friday": 4, "saturday": 5, "sunday": 6}


class CalendarValidationError(ValueError):
    """Raised when a calendar is ambiguous, invalid, or cannot be calculated."""


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise CalendarValidationError("Calendar intervals must be timezone-aware")
        if self.end <= self.start:
            raise CalendarValidationError("Calendar interval must have a positive duration")

    def utc(self) -> "Interval":
        return Interval(self.start.astimezone(UTC), self.end.astimezone(UTC))


@dataclass(frozen=True)
class CalendarException:
    start: datetime
    end: datetime
    availability_mode: str
    replacement_intervals: tuple[Interval, ...] = ()

    def __post_init__(self) -> None:
        Interval(self.start, self.end)
        if self.availability_mode not in {"close", "add", "replace"}:
            raise CalendarValidationError("Unsupported exception availability mode")
        if self.availability_mode == "replace" and not self.replacement_intervals:
            raise CalendarValidationError("Replacement exception requires replacement intervals")


@dataclass(frozen=True)
class ResolvedCalendar:
    calendar_id: str | None
    source: str | None


def resolve_calendar_id(
    activity_calendar_id: str | None,
    project_calendar_id: str | None,
    organization_calendar_id: str | None,
) -> ResolvedCalendar:
    """Resolve only explicit references; legacy projects deliberately remain unset."""
    if activity_calendar_id:
        return ResolvedCalendar(activity_calendar_id, "activity")
    if project_calendar_id:
        return ResolvedCalendar(project_calendar_id, "project")
    if organization_calendar_id:
        return ResolvedCalendar(organization_calendar_id, "organization")
    return ResolvedCalendar(None, None)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise CalendarValidationError("Datetime must include a timezone")
    return value.astimezone(UTC)


def _parse_clock(value: str) -> time:
    try:
        parsed = time.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise CalendarValidationError(f"Invalid clock value: {value!r}") from exc
    if parsed.tzinfo is not None:
        raise CalendarValidationError("Clock values must be local and timezone-free")
    return parsed


def _weekday(key: object) -> int:
    if isinstance(key, int) or (isinstance(key, str) and key.isdigit()):
        value = int(key)
        if 0 <= value <= 6:
            return value
    if isinstance(key, str) and key.casefold() in WEEKDAY_NAMES:
        return WEEKDAY_NAMES[key.casefold()]
    raise CalendarValidationError(f"Invalid weekday: {key!r}")


def _strict_local(local_date: date, clock: time, zone: ZoneInfo, day_offset: int = 0) -> datetime:
    naive = datetime.combine(local_date + timedelta(days=day_offset), clock)
    # fold=0 is the documented deterministic policy for an ambiguous fall-back time.
    value = naive.replace(tzinfo=zone, fold=0)
    round_trip = value.astimezone(UTC).astimezone(zone).replace(tzinfo=None)
    if round_trip != naive:
        raise CalendarValidationError(f"Nonexistent local time in {zone.key}: {naive.isoformat()}")
    return value


def _subtract(intervals: Sequence[Interval], closed: Interval) -> list[Interval]:
    result: list[Interval] = []
    close_start, close_end = closed.utc().start, closed.utc().end
    for candidate in intervals:
        current = candidate.utc()
        if close_end <= current.start or close_start >= current.end:
            result.append(current)
            continue
        if current.start < close_start:
            result.append(Interval(current.start, close_start))
        if close_end < current.end:
            result.append(Interval(close_end, current.end))
    return result


def _normalize(intervals: Iterable[Interval]) -> list[Interval]:
    ordered = sorted((item.utc() for item in intervals), key=lambda item: (item.start, item.end))
    normalized: list[Interval] = []
    for item in ordered:
        if normalized and item.start <= normalized[-1].end:
            previous = normalized[-1]
            normalized[-1] = Interval(previous.start, max(previous.end, item.end))
        else:
            normalized.append(item)
    return normalized


class WorkCalendar:
    """Materializes productive UTC intervals from a weekly local-time pattern.

    Pattern shape::

      {"0": [{"start": "08:00", "end": "17:00",
              "breaks": [{"start": "12:00", "end": "13:00"}]}]}

    `end` earlier than `start` denotes a night shift.  Breaks are mandatory as
    explicit windows when present; an aggregate `break_minutes` is checked
    against them so a calculation never needs to guess where a break occurs.
    """

    def __init__(self, timezone_name: str, weekly_pattern: Mapping[object, Sequence[Mapping[str, object]]]):
        try:
            self.zone = ZoneInfo(timezone_name)
        except (TypeError, ZoneInfoNotFoundError) as exc:
            raise CalendarValidationError(f"Unknown timezone: {timezone_name!r}") from exc
        self.timezone_name = timezone_name
        self.pattern: dict[int, tuple[Mapping[str, object], ...]] = {}
        for key, periods in weekly_pattern.items():
            weekday = _weekday(key)
            if not isinstance(periods, Sequence) or isinstance(periods, (str, bytes)):
                raise CalendarValidationError("Weekly pattern periods must be a sequence")
            self.pattern[weekday] = tuple(periods)
        self._validate_pattern()

    def _period_intervals(self, local_day: date, period: Mapping[str, object]) -> list[Interval]:
        start_clock = _parse_clock(str(period.get("start", "")))
        end_clock = _parse_clock(str(period.get("end", "")))
        end_offset = int(period.get("end_day_offset", 1 if end_clock <= start_clock else 0))
        if end_offset not in (0, 1) or (end_offset == 0 and end_clock <= start_clock):
            raise CalendarValidationError("Invalid shift end or end_day_offset")
        start = _strict_local(local_day, start_clock, self.zone)
        end = _strict_local(local_day, end_clock, self.zone, end_offset)
        available = [Interval(start, end)]
        breaks = period.get("breaks", ())
        if not isinstance(breaks, Sequence) or isinstance(breaks, (str, bytes)):
            raise CalendarValidationError("Breaks must be a sequence")
        total_break_minutes = 0
        for entry in breaks:
            if not isinstance(entry, Mapping):
                raise CalendarValidationError("Break entry must be an object")
            break_start_clock = _parse_clock(str(entry.get("start", "")))
            break_end_clock = _parse_clock(str(entry.get("end", "")))
            break_start_offset = int(entry.get(
                "start_day_offset", 1 if end_offset and break_start_clock < start_clock else 0
            ))
            break_offset = int(entry.get("end_day_offset", 1 if break_end_clock <= break_start_clock else 0))
            break_interval = Interval(
                _strict_local(local_day, break_start_clock, self.zone, break_start_offset),
                _strict_local(local_day, break_end_clock, self.zone, break_start_offset + break_offset),
            ).utc()
            shift = Interval(start, end).utc()
            if break_interval.start < shift.start or break_interval.end > shift.end:
                raise CalendarValidationError("Break must fall inside its shift")
            total_break_minutes += int((break_interval.end - break_interval.start).total_seconds() // 60)
            available = _subtract(available, break_interval)
        declared_break_minutes = period.get("break_minutes")
        if declared_break_minutes is not None and int(declared_break_minutes) != total_break_minutes:
            raise CalendarValidationError("break_minutes must equal explicit break windows")
        return available

    def _validate_pattern(self) -> None:
        anchor = date(2026, 1, 5)  # Monday; validation is timezone-aware and deterministic.
        for weekday, periods in self.pattern.items():
            local_day = anchor + timedelta(days=weekday)
            produced: list[Interval] = []
            for period in periods:
                if not isinstance(period, Mapping):
                    raise CalendarValidationError("Shift period must be an object")
                produced.extend(self._period_intervals(local_day, period))
            normalized = _normalize(produced)
            if sum((item.end - item.start for item in normalized), timedelta()) != sum(
                (item.end - item.start for item in produced), timedelta()
            ):
                raise CalendarValidationError("Productive shift windows may not overlap")

    def available_intervals(
        self, start: datetime, end: datetime, exceptions: Iterable[CalendarException] = ()
    ) -> list[Interval]:
        start_utc, end_utc = _utc(start), _utc(end)
        if end_utc <= start_utc:
            raise CalendarValidationError("Calculation range must be positive")
        local_start = start_utc.astimezone(self.zone).date() - timedelta(days=1)
        local_end = end_utc.astimezone(self.zone).date()
        intervals: list[Interval] = []
        current = local_start
        while current <= local_end:
            for period in self.pattern.get(current.weekday(), ()):
                intervals.extend(self._period_intervals(current, period))
            current += timedelta(days=1)
        bounded: list[Interval] = []
        for item in intervals:
            interval = item.utc()
            clipped_start, clipped_end = max(interval.start, start_utc), min(interval.end, end_utc)
            if clipped_start < clipped_end:
                bounded.append(Interval(clipped_start, clipped_end))
        result = _normalize(bounded)
        for exception in exceptions:
            window = Interval(_utc(exception.start), _utc(exception.end))
            if exception.availability_mode == "close":
                result = _subtract(result, window)
            elif exception.availability_mode == "add":
                result = _normalize([*result, window])
            else:  # replace
                result = _normalize([*_subtract(result, window), *exception.replacement_intervals])
        return _normalize(result)

    def finish_after(
        self, start: datetime, work_minutes: int, exceptions: Iterable[CalendarException] = ()
    ) -> datetime:
        if work_minutes < 0:
            raise CalendarValidationError("Work minutes cannot be negative")
        cursor = _utc(start)
        if work_minutes == 0:
            return cursor
        remaining = timedelta(minutes=work_minutes)
        # A finite, explicit horizon protects callers from calendars with no capacity.
        horizon = cursor + timedelta(days=3660)
        for interval in self.available_intervals(cursor, horizon, exceptions):
            capacity = interval.end - interval.start
            if capacity >= remaining:
                return interval.start + remaining
            remaining -= capacity
        raise CalendarValidationError("Calendar has insufficient capacity in the calculation horizon")

    def start_at_or_after(
        self, start: datetime, exceptions: Iterable[CalendarException] = ()
    ) -> datetime:
        """Return the first productive instant at or after ``start`` in UTC."""
        cursor = _utc(start)
        for interval in self.available_intervals(cursor, cursor + timedelta(days=3660), exceptions):
            return max(cursor, interval.start)
        raise CalendarValidationError("Calendar has insufficient capacity in the calculation horizon")

    def start_before(
        self, finish: datetime, work_minutes: int, exceptions: Iterable[CalendarException] = ()
    ) -> datetime:
        """Return the latest productive start whose work finishes no later than ``finish``."""
        if work_minutes < 0:
            raise CalendarValidationError("Work minutes cannot be negative")
        deadline = _utc(finish)
        if work_minutes == 0:
            return deadline
        remaining = timedelta(minutes=work_minutes)
        horizon = deadline - timedelta(days=3660)
        intervals = self.available_intervals(horizon, deadline, exceptions)
        for interval in reversed(intervals):
            capacity = interval.end - interval.start
            if capacity >= remaining:
                return interval.end - remaining
            remaining -= capacity
        raise CalendarValidationError("Calendar has insufficient capacity in the calculation horizon")

    def start_at_or_before(
        self, start: datetime, exceptions: Iterable[CalendarException] = ()
    ) -> datetime:
        """Return the latest productive instant at or before ``start`` in UTC."""
        cursor = _utc(start)
        # Include a productive interval that begins exactly at ``cursor``.
        intervals = self.available_intervals(
            cursor - timedelta(days=3660), cursor + timedelta(microseconds=1), exceptions
        )
        if not intervals:
            raise CalendarValidationError("Calendar has insufficient capacity in the calculation horizon")
        return min(cursor, intervals[-1].end)
