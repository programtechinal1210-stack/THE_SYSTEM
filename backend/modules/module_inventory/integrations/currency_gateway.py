"""Consume the existing Core currency service; never accept a client FX rate."""
from datetime import date
from decimal import Decimal, localcontext, ROUND_HALF_UP
from modules.module_currency.application.currency_service import CurrencyService
from ..domain.financial_policy import decimal, money, COST_SCALE


class InventoryCurrencyGateway:
    def __init__(self, session):
        self.service = CurrencyService(session)

    async def receipt_snapshot(self, quantity, original_unit_price, transaction_currency,
                               valuation_currency, document_date):
        as_of = date.fromisoformat(str(document_date)).isoformat()
        q = decimal(quantity, positive=True)
        price = decimal(original_unit_price)
        if price < 0:
            raise ValueError('Negative receipt price')
        source = await self.service.repo.currency_by_code(transaction_currency)
        target = await self.service.repo.currency_by_code(valuation_currency)
        if not source or not target or not source.is_active or not target.is_active:
            raise ValueError('FX_RATE_UNAVAILABLE')
        snapshot = await self.service.get_rate_snapshot(transaction_currency, valuation_currency, as_of)
        snapshot['legs'] = []
        if snapshot['method'] in ('direct', 'inverse'):
            record = await self.service.repo.direct_rate(
                source.id if snapshot['method']=='direct' else target.id,
                target.id if snapshot['method']=='direct' else source.id, as_of)
            snapshot['legs'] = [{'rate_id': str(record.id), 'effective_date': str(record.effective_date),
                'source': record.source, 'stored_rate': record.rate_decimal, 'method': snapshot['method']}]
        elif snapshot['method'] == 'cross':
            anchor_id = await self.service.repo.anchor_id()
            anchor = await self.service.repo.currency_by_id(anchor_id) if anchor_id else None
            if not anchor or not anchor.is_active:
                raise ValueError('FX_RATE_UNAVAILABLE')
            snapshot = await self.service.get_anchor_snapshot(transaction_currency, valuation_currency, as_of, anchor=anchor.code)
        if not snapshot['available'] or snapshot['rate'] is None:
            raise ValueError('FX_RATE_UNAVAILABLE')
        rate = decimal(str(snapshot['rate']), positive=True)
        with localcontext() as ctx:
            ctx.prec = 50
            original = money(q * price)
            converted = money(original * rate)
            unit_cost = (converted / q).quantize(COST_SCALE, rounding=ROUND_HALF_UP)
        return {
            'transaction_currency': transaction_currency,
            'original_unit_price': str(price), 'original_amount': str(original),
            'valuation_currency': valuation_currency, 'fx_rate': str(rate),
            'fx_as_of': as_of,
            'fx_effective_dates': [leg['effective_date'] for leg in snapshot['legs'] if leg['effective_date']],
            'fx_source_ref': {**snapshot, 'rate': str(snapshot['rate'])},
            'amount_valuation': str(converted), 'unit_cost_valuation': str(unit_cost),
        }
