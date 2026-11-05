from typing import Optional
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.currency_model import CurrencyModel
from ..models.exchange_rate_model import ExchangeRateModel


class CurrencyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def currency_by_code(self, code: str) -> Optional[CurrencyModel]:
        return await self.session.scalar(select(CurrencyModel).where(CurrencyModel.code == code))

    async def currency_by_id(self, cid: UUID) -> Optional[CurrencyModel]:
        return await self.session.scalar(select(CurrencyModel).where(CurrencyModel.id == cid))

    async def list_currencies(self, active_only: bool = True):
        q = select(CurrencyModel)
        if active_only:
            q = q.where(CurrencyModel.is_active.is_(True))
        return (await self.session.scalars(q.order_by(CurrencyModel.code))).all()

    async def anchor_id(self) -> Optional[UUID]:
        c = await self.session.scalar(
            select(CurrencyModel).where(CurrencyModel.is_anchor.is_(True)).limit(1))
        return c.id if c else None

    async def direct_rate(self, from_id: UUID, to_id: UUID, as_of: str) -> Optional[ExchangeRateModel]:
        return await self.session.scalar(
            select(ExchangeRateModel)
            .where(ExchangeRateModel.from_currency == from_id,
                   ExchangeRateModel.to_currency == to_id,
                   ExchangeRateModel.effective_date <= as_of)
            .order_by(ExchangeRateModel.effective_date.desc(), ExchangeRateModel.created_at.desc(), ExchangeRateModel.id.desc())
            .limit(1))

    async def list_rates(self, from_id: Optional[UUID] = None, to_id: Optional[UUID] = None,
                         limit: int = 100):
        q = select(ExchangeRateModel).order_by(ExchangeRateModel.effective_date.desc()).limit(limit)
        if from_id:
            q = q.where(ExchangeRateModel.from_currency == from_id)
        if to_id:
            q = q.where(ExchangeRateModel.to_currency == to_id)
        return (await self.session.scalars(q)).all()

    async def save_currency(self, code: str, name: str, symbol: str = "",
                            is_anchor: bool = False, is_active: bool = True) -> CurrencyModel:
        m = CurrencyModel(code=code, name=name, symbol=symbol,
                          is_anchor=is_anchor, is_active=is_active)
        self.session.add(m)
        await self.session.flush()
        return m

    async def save_rate(self, from_currency: UUID, to_currency: UUID, rate: Decimal,
                        effective_date: str, source: str = "manual") -> ExchangeRateModel:
        m = ExchangeRateModel(from_currency=from_currency, to_currency=to_currency,
                              rate=float(rate), rate_decimal=str(rate), effective_date=effective_date, source=source)
        self.session.add(m)
        await self.session.flush()
        return m
