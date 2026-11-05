from datetime import date
from typing import Literal
from uuid import UUID
from decimal import localcontext
from pydantic import BaseModel,ConfigDict,Field,field_validator,model_validator
from .financial_policy import decimal,COST_SCALE


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')


class StocktakeCreate(Strict):
    warehouse_id:UUID
    count_type:Literal['FULL','PARTIAL','CYCLE','SURPRISE','CONTINUOUS']='FULL'
    all_locations:bool=True
    location_id:UUID|None=None
    item_ids:list[UUID]=Field(default_factory=list,max_length=200)
    stock_status:Literal['AVAILABLE','QUARANTINE','DAMAGED']|None=None
    reason:str=Field(min_length=3,max_length=2000)

    @model_validator(mode='after')
    def scope(self):
        if self.all_locations and self.location_id:raise ValueError('All-location scope cannot specify a location')
        if len(set(self.item_ids))!=len(self.item_ids):raise ValueError('Duplicate scope items')
        if len(self.reason.strip())<3:raise ValueError('Documented count reason required')
        partial=bool(self.item_ids or not self.all_locations or self.stock_status)
        if self.count_type=='FULL' and partial:raise ValueError('FULL requires the complete countable warehouse scope')
        if self.count_type=='PARTIAL' and not partial:raise ValueError('PARTIAL requires an explicit limited scope')
        return self


class CountEntry(Strict):
    quantity:str
    recount:bool=False
    reason:str|None=Field(default=None,max_length=2000)

    @field_validator('quantity')
    @classmethod
    def nonnegative(cls,value):
        if decimal(value)<0:raise ValueError('Count cannot be negative')
        return value

    @model_validator(mode='after')
    def recount_reason(self):
        if self.recount and len((self.reason or '').strip())<3:raise ValueError('Documented recount reason required')
        return self


class ObservedCount(CountEntry):
    item_id:UUID
    location_id:UUID|None=None
    stock_status:Literal['AVAILABLE','QUARANTINE','DAMAGED']='AVAILABLE'


class GainBasis(Strict):
    stocktake_line_id:UUID
    unit_cost:str
    reason:str=Field(min_length=3,max_length=2000)

    @model_validator(mode='after')
    def exact_cost(self):
        value=decimal(self.unit_cost)
        with localcontext() as ctx:
            ctx.prec=50
            if value<0 or value!=value.quantize(COST_SCALE):raise ValueError('Exact nonnegative valuation unit cost required')
        if len(self.reason.strip())<3:raise ValueError('Documented gain cost basis required')
        return self


class CountSettlement(Strict):
    document_date:date
    reason:str=Field(min_length=3,max_length=2000)
    valuation_basis:list[GainBasis]=Field(default_factory=list,max_length=200)

    @model_validator(mode='after')
    def distinct_basis(self):
        if len({r.stocktake_line_id for r in self.valuation_basis})!=len(self.valuation_basis):raise ValueError('Duplicate cost basis')
        if len(self.reason.strip())<3:raise ValueError('Documented settlement reason required')
        return self
