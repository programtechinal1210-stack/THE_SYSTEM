"""28 significant digits, ROUND_HALF_EVEN; API values are decimal strings."""
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_EVEN


def decimal_value(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('Invalid decimal')
    if not result.is_finite() or len(result.as_tuple().digits) > 28 or abs(result.adjusted()) > 28:
        raise ValueError('Decimal must be finite and within 28 digits/exponent')
    return result


def calculate(left, right, divide=False):
    with localcontext() as context:
        context.prec = 28
        context.rounding = ROUND_HALF_EVEN
        return left / right if divide else left * right
