"""Currency contract: get_rate(from, to, date) + exchange_rate_snapshot."""
from datetime import datetime, date
from decimal import Decimal
from ..domain.decimal_policy import decimal_value, calculate
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..infrastructure.repositories.currency_repository import CurrencyRepository


class CurrencyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CurrencyRepository(session)

    async def get_anchor_snapshot(self, from_code, to_code, as_of=None, anchor='YER'):
        """Explicit anchor conversion using stored direct/inverse legs only.

        Never fall back to a different anchor or a guessed rate. Retain both
        source records and effective dates so a saved conversion is auditable.
        """
        as_of = date.fromisoformat(str(as_of or date.today())).isoformat()
        result = {'from': from_code, 'to': to_code, 'date': as_of,
                  'anchor': anchor, 'rate': None, 'rate_id': None,
                  'method': 'anchor', 'available': False, 'legs': []}
        currencies = {}
        for code in {from_code, to_code, anchor}:
            row = await self.repo.currency_by_code(code)
            if not row or not row.is_active:
                result['method'] = 'unknown_or_inactive_currency'
                return result
            currencies[code] = row
        if from_code == to_code:
            result.update(rate=Decimal(1), method='identity', available=True)
            return result
        for code in (from_code, to_code):
            leg = {'from': code, 'to': anchor, 'rate': '1', 'method': 'identity',
                   'rate_id': None, 'effective_date': None}
            if code != anchor:
                row = await self.repo.direct_rate(currencies[code].id, currencies[anchor].id, as_of)
                inverse = False
                if row is None:
                    row = await self.repo.direct_rate(currencies[anchor].id, currencies[code].id, as_of)
                    inverse = True
                if row is None:
                    result['missing_currency'] = code
                    return result
                value = decimal_value(row.rate_decimal)
                if value <= 0:
                    result['method'] = 'invalid_rate'
                    return result
                leg.update(rate=str(calculate(Decimal(1), value, divide=True) if inverse else value),
                           method='inverse' if inverse else 'direct', rate_id=str(row.id),
                           effective_date=str(row.effective_date), stored_rate=str(value))
            result['legs'].append(leg)
        result.update(rate=calculate(Decimal(result['legs'][0]['rate']),
                                     Decimal(result['legs'][1]['rate']), divide=True), available=True)
        return result

    async def add_currency(self, code: str, name: str, symbol: str = "", is_anchor: bool = False):
        return await self.repo.save_currency(code, name, symbol, is_anchor)

    async def set_rate(self, from_code: str, to_code: str, rate: Decimal,
                       effective_date: str, source: str = "manual"):
        f = await self.repo.currency_by_code(from_code)
        t = await self.repo.currency_by_code(to_code)
        if not f or not t:
            raise ValueError("Unknown currency code")
        rate = decimal_value(rate)
        if rate <= 0:
            raise ValueError("Rate must be positive")
        effective_date = date.fromisoformat(str(effective_date)).isoformat()
        return await self.repo.save_rate(f.id, t.id, rate, effective_date, source)

    async def _resolve(self, from_code: str, to_code: str, as_of: str):
        """Return (rate, rate_id, method) for the requested pair."""
        f = await self.repo.currency_by_code(from_code)
        t = await self.repo.currency_by_code(to_code)
        if not f or not t:
            return None, None, "unknown_currency"
        if from_code == to_code:
            return Decimal(1), None, "identity"
        direct = await self.repo.direct_rate(f.id, t.id, as_of)
        if direct:
            return decimal_value(direct.rate_decimal), str(direct.id), "direct"
        inverse = await self.repo.direct_rate(t.id, f.id, as_of)
        if inverse:
            return calculate(Decimal(1), decimal_value(inverse.rate_decimal), divide=True), str(inverse.id), "inverse"
        anchor = await self.repo.anchor_id()
        if not anchor or f.id == anchor or t.id == anchor:
            return None, None, "unavailable"
        f_anchor = await self.repo.direct_rate(f.id, anchor, as_of)
        t_anchor = await self.repo.direct_rate(t.id, anchor, as_of)
        if f_anchor and t_anchor:
            return calculate(decimal_value(f_anchor.rate_decimal), decimal_value(t_anchor.rate_decimal), divide=True), None, "cross"
        return None, None, "unavailable"

    async def get_rate(self, from_code: str, to_code: str, as_of: Optional[str] = None) -> Optional[Decimal]:
        as_of = date.fromisoformat(str(as_of or date.today())).isoformat()
        rate, _, _ = await self._resolve(from_code, to_code, as_of)
        return rate

    async def get_rate_snapshot(self, from_code: str, to_code: str,
                                as_of: Optional[str] = None) -> dict:
        as_of = date.fromisoformat(str(as_of or date.today())).isoformat()
        rate, rate_id, method = await self._resolve(from_code, to_code, as_of)
        return {
            "from": from_code,
            "to": to_code,
            "rate": rate,
            "date": as_of,
            "rate_id": rate_id,
            "method": method,
            "available": rate is not None,
        }

    async def convert(self, amount, from_code: str, to_code: str,
                      as_of: Optional[str] = None) -> Optional[Decimal]:
        rate = await self.get_rate(from_code, to_code, as_of)
        if rate is None:
            return None
        return calculate(decimal_value(amount), rate)
