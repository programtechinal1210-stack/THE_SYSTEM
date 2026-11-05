"""Exact, bounded inventory calculations; independent of persistence and HTTP."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

QUANTITY_SCALE = Decimal('0.000001')
VALUE_SCALE = Decimal('0.000001')
COST_SCALE = Decimal('0.000000000001')
MAXIMUM = Decimal('999999999999999999.999999')


def decimal(value, *, positive=False):
    if isinstance(value, (bool, float)):
        raise ValueError('Use exact decimal strings')
    try:
        result = Decimal(value)
        if not result.is_finite() or abs(result) > MAXIMUM or (positive and result <= 0):
            raise ValueError('Decimal outside supported range')
        return result
    except (InvalidOperation, TypeError):
        raise ValueError('Invalid decimal') from None


def quantity(value, precision=6):
    if precision not in range(7):
        raise ValueError('Invalid unit precision')
    result = decimal(value, positive=True)
    scale = Decimal(1).scaleb(-precision)
    if result != result.quantize(scale):
        raise ValueError('Quantity exceeds base unit precision')
    return result


def money(value):
    result = decimal(value)
    with localcontext() as ctx:
        ctx.prec = 50
        rounded = result.quantize(VALUE_SCALE, rounding=ROUND_HALF_UP)
    if abs(rounded) > MAXIMUM:
        raise ValueError('Value exceeds supported range')
    return rounded


def transfer_allocation(total_quantity, total_value, settled_quantity, settled_value, requested_quantity):
    """Allocate remaining historical value without cumulative rounding overdraft."""
    total_q = quantity(total_quantity)
    requested = quantity(requested_quantity)
    total_v = money(total_value)
    settled_q = decimal(settled_quantity)
    settled_v = money(settled_value)
    with localcontext() as ctx:
        ctx.prec = 50
        remaining_q = total_q - settled_q
        remaining_v = money(total_v - settled_v)
        if min(total_v, settled_q, settled_v, remaining_v) < 0 or remaining_q <= 0 or requested > remaining_q:
            raise ValueError('TRANSFER_SETTLEMENT_INCONSISTENT')
        allocated = remaining_v if requested == remaining_q else money(remaining_v * requested / remaining_q)
        if allocated < 0 or allocated > remaining_v:
            raise ValueError('TRANSFER_SETTLEMENT_INCONSISTENT')
        return allocated


@dataclass(frozen=True)
class Valuation:
    quantity_total: Decimal
    inventory_value: Decimal
    avg_cost: Decimal

    @classmethod
    def empty(cls):
        return cls(Decimal(0), Decimal(0), Decimal(0))

    def _validate(self):
        if (not all(x.is_finite() for x in (self.quantity_total, self.inventory_value, self.avg_cost))
                or min(self.quantity_total, self.inventory_value, self.avg_cost) < 0
                or (not self.quantity_total and self.inventory_value)):
            raise ValueError('Invalid valuation state')

    def receive(self, inbound_quantity, inbound_value):
        self._validate()
        q = quantity(inbound_quantity)
        v = money(inbound_value)
        if v < 0:
            raise ValueError('Inbound value cannot be negative')
        with localcontext() as ctx:
            ctx.prec = 50
            total = decimal(self.quantity_total + q)
            value = money(self.inventory_value + v)
            average = (value / total).quantize(COST_SCALE, rounding=ROUND_HALF_UP)
        return Valuation(total, value, average)

    def issue(self, outbound_quantity):
        self._validate()
        q = quantity(outbound_quantity)
        if q > self.quantity_total:
            raise ValueError('INSUFFICIENT_STOCK')
        with localcontext() as ctx:
            ctx.prec = 50
            # Final depletion takes the entire remaining value, including rounding.
            cost = self.inventory_value if q == self.quantity_total else money(self.inventory_value * q / self.quantity_total)
            remaining_q = self.quantity_total - q
            remaining_v = self.inventory_value - cost
            average = ((remaining_v / remaining_q).quantize(COST_SCALE, rounding=ROUND_HALF_UP)
                       if remaining_q else Decimal(0))
        return Valuation(remaining_q, remaining_v, average), cost
