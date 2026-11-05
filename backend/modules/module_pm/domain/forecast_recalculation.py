"""Pure helpers for deriving Forecast work from an Actual read snapshot."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING


def decimal_or_none(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def remaining_work_minutes(planned_quantity, remaining_quantity, planned_minutes):
    """Scale planned work by the documented quantity ratio.

    Activity productivity has no normalized contract today.  The supported S-04.3
    fallback is therefore the immutable Baseline duration multiplied by the
    remaining/planned quantity ratio.  Missing or zero inputs remain unavailable.
    """
    planned = decimal_or_none(planned_quantity)
    remaining = decimal_or_none(remaining_quantity)
    if planned is None or remaining is None or planned <= 0 or planned_minutes is None or planned_minutes <= 0:
        return None
    return int((Decimal(planned_minutes) * remaining / planned).to_integral_value(rounding=ROUND_CEILING))
