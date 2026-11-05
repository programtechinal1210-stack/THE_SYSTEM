from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date as Date
from sqlalchemy.ext.asyncio import AsyncSession

from core.access import require
from infrastructure.database.db_context import get_session
from ..application.currency_service import CurrencyService
from ..infrastructure.repositories.currency_repository import CurrencyRepository

router = APIRouter(tags=["currency"])


class CurrencyOut(BaseModel):
    model_config = {"from_attributes": True}
    id: UUID
    code: str
    name: str
    symbol: str = ""
    is_anchor: bool = False
    is_active: bool = True


class CurrencyIn(BaseModel):
    code: str
    name: str
    symbol: str = ""
    is_anchor: bool = False


class RateIn(BaseModel):
    from_currency: str
    to_currency: str
    rate: Decimal = Field(gt=0, max_digits=28, allow_inf_nan=False)
    effective_date: Date
    source: str = "manual"


class ConvertIn(BaseModel):
    amount: Decimal = Field(max_digits=28, allow_inf_nan=False)
    from_currency: str
    to_currency: str
    date: Optional[Date] = None


def svc(s: AsyncSession = Depends(get_session, scope="function")):
    return CurrencyService(s)


def repo(s: AsyncSession = Depends(get_session, scope="function")):
    return CurrencyRepository(s)


@router.get("/currencies", response_model=List[CurrencyOut])
async def list_currencies(request: Request, repo=Depends(repo)):
    require(request, "core.currency.view")
    return [CurrencyOut.model_validate(c) for c in await repo.list_currencies(active_only=False)]


@router.post("/currencies", response_model=CurrencyOut, status_code=201)
async def create_currency(request: Request, data: CurrencyIn, svc=Depends(svc)):
    require(request, "core.currency.manage")
    if await svc.repo.currency_by_code(data.code):
        raise HTTPException(409, "Currency code already exists")
    m = await svc.add_currency(data.code, data.name, data.symbol, data.is_anchor)
    return CurrencyOut.model_validate(m)


@router.get("/rate")
async def rate(request: Request, from_: str = Query(..., alias="from"), to: str = Query(...),
               date: Optional[Date] = Query(None), svc=Depends(svc)):
    require(request, "core.currency.view")
    result = await svc.get_rate_snapshot(from_, to, date)
    result["rate"] = str(result["rate"]) if result["rate"] is not None else None
    return result


@router.post("/convert")
async def convert(request: Request, data: ConvertIn, svc=Depends(svc)):
    require(request, "core.currency.view")
    try:
        result = await svc.convert(data.amount, data.from_currency, data.to_currency, data.date)
    except ValueError as error:
        raise HTTPException(422, str(error))
    if result is None:
        raise HTTPException(422, "No exchange rate available for the requested pair and date")
    return {"amount": str(data.amount), "from": data.from_currency, "to": data.to_currency,
            "converted": str(result), "date": data.date}


@router.get("/rates")
async def list_rates(request: Request, from_: Optional[str] = Query(None, alias="from"),
                     to: Optional[str] = Query(None), repo=Depends(repo)):
    require(request, "core.currency.view")
    f_row = await repo.currency_by_code(from_) if from_ else None
    t_row = await repo.currency_by_code(to) if to else None
    if (from_ and not f_row) or (to and not t_row):
        raise HTTPException(422, "Unknown currency")
    f = f_row.id if f_row else None
    t = t_row.id if t_row else None
    rows = await repo.list_rates(from_id=f, to_id=t)
    return [{"id": str(r.id), "from_currency": str(r.from_currency),
             "to_currency": str(r.to_currency), "rate": r.rate_decimal,
             "effective_date": r.effective_date, "source": r.source} for r in rows]


@router.post("/rates", status_code=201)
async def create_rate(request: Request, data: RateIn, svc=Depends(svc)):
    require(request, "core.currency.manage")
    try:
        m = await svc.set_rate(data.from_currency, data.to_currency, data.rate,
                               data.effective_date, data.source)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"id": str(m.id), "from_currency": str(m.from_currency),
            "to_currency": str(m.to_currency), "rate": m.rate_decimal,
            "effective_date": m.effective_date, "source": m.source}
