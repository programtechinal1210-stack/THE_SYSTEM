from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from .financial_policy import quantity, decimal, money


class Line(BaseModel):
    model_config = ConfigDict(extra='forbid')
    item_id: UUID
    unit_id: UUID | None = None
    location_id: UUID | None = None
    request_line_id: UUID | None = None
    destination_location_id: UUID | None = None
    dispatch_line_id: UUID | None = None
    origin_line_id: UUID | None = None
    value_adjustment_amount: str | None = Field(default=None,max_length=40)
    quantity: str = Field(max_length=40)
    transaction_currency: str | None = Field(default=None, max_length=10)
    original_unit_price: str | None = Field(default=None, max_length=40)

    @field_validator('quantity')
    @classmethod
    def valid_quantity(cls, value, info):
        if info.data.get('value_adjustment_amount') is not None and decimal(value)==0:
            return '0'
        quantity(value)
        return value

    @field_validator('value_adjustment_amount')
    @classmethod
    def valid_value_change(cls,value):
        if value is not None:
            amount=decimal(value)
            if not amount or money(amount)!=amount:
                raise ValueError('Value correction must be nonzero and exact to six decimals')
            return str(money(amount))
        return value

    @field_validator('original_unit_price')
    @classmethod
    def valid_price(cls, value):
        if value is not None and decimal(value) < 0:
            raise ValueError('Price cannot be negative')
        return value


class Document(BaseModel):
    model_config = ConfigDict(extra='forbid')
    organization_id: UUID
    warehouse_id: UUID
    document_type: Literal['RECEIPT', 'ISSUE_DIRECT', 'TRANSFER_DIRECT', 'TRANSFER_DISPATCH', 'TRANSFER_RECEIPT', 'LOSS_TRANSIT', 'ISSUE_CUSTODY', 'CONSUMPTION', 'RETURN_INTERNAL', 'STATUS_CHANGE', 'SCRAP', 'RETURN_SUPPLIER', 'ADJUSTMENT']
    adjustment_kind: Literal['VALUE'] | None = None
    counterparty_reference: str | None = Field(default=None,max_length=300)
    source_stock_status: Literal['AVAILABLE','QUARANTINE','DAMAGED'] | None = None
    target_stock_status: Literal['AVAILABLE','QUARANTINE','DAMAGED'] | None = None
    destination_warehouse_id: UUID | None = None
    beneficiary_user_id: UUID | None = None
    custody_due_date: date | None = None
    reason: str | None = Field(default=None, max_length=1000)
    document_date: date
    document_no: str | None = Field(default=None, min_length=1, max_length=80)
    source_module: Literal['equipment'] | None = None
    source_type: Literal['fuel_event', 'fuel_return_event', 'maintenance_order', 'part_lifecycle'] | None = None
    source_id: UUID | None = None
    lines: list[Line] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def source_reference_is_complete(self):
        if self.document_type=='ADJUSTMENT':
            if self.adjustment_kind!='VALUE' or not (self.reason or '').strip() or self.source_module:
                raise ValueError('Value-only correction requires its kind, reason and no external Actual source')
            if any(decimal(line.quantity)!=0 or line.value_adjustment_amount is None or not line.origin_line_id or line.unit_id or line.location_id or line.request_line_id for line in self.lines):
                raise ValueError('Value-only correction requires zero quantity, original reference and signed amount; no physical location/unit/request')
        elif self.adjustment_kind or any(line.value_adjustment_amount is not None for line in self.lines):
            raise ValueError('Value correction fields require ADJUSTMENT')
        if self.document_type=='RETURN_SUPPLIER':
            if not (self.counterparty_reference or '').strip() or not (self.reason or '').strip():
                raise ValueError('Supplier/RMA reference and return reason are required')
            if self.source_module or any(not line.origin_line_id or line.request_line_id for line in self.lines):
                raise ValueError('Supplier return requires original receipt lines and no external consumption source')
        elif self.counterparty_reference is not None:
            raise ValueError('Counterparty reference requires a supplier return')
        status_operation=self.document_type in ('STATUS_CHANGE','SCRAP')
        if status_operation:
            if not self.reason or not self.reason.strip() or not self.source_stock_status:
                raise ValueError('A stock status and documented reason are required')
            if self.document_type=='STATUS_CHANGE':
                if not self.target_stock_status or self.target_stock_status==self.source_stock_status:
                    raise ValueError('Distinct source and target stock statuses are required')
            elif self.target_stock_status or self.source_stock_status=='AVAILABLE':
                raise ValueError('Disposal requires damaged or quarantine stock and no destination')
            if self.source_module or any(line.request_line_id for line in self.lines):
                raise ValueError('Status/disposal cannot fulfill a request or external Actual')
        elif self.source_stock_status or self.target_stock_status:
            raise ValueError('Stock status fields require a status/disposal operation')
        custody=self.document_type in ('ISSUE_CUSTODY','CONSUMPTION','RETURN_INTERNAL')
        if custody:
            if not self.beneficiary_user_id or self.destination_warehouse_id or self.source_module:
                raise ValueError('Custody requires a holder and local warehouse; external consumption integration is not active')
            derived=self.document_type!='ISSUE_CUSTODY'
            if any(bool(line.origin_line_id)!=derived for line in self.lines):
                raise ValueError('Consumption and return require an original custody issue line')
            if self.document_type=='ISSUE_CUSTODY' and any(not line.destination_location_id for line in self.lines):
                raise ValueError('A custody location is required')
            if derived and any(line.request_line_id for line in self.lines):
                raise ValueError('Custody settlement cannot fulfill a request a second time')
            if any(line.dispatch_line_id for line in self.lines):
                raise ValueError('Custody operations cannot settle a transfer dispatch')
            if self.document_type=='CONSUMPTION' and any(line.destination_location_id for line in self.lines):
                raise ValueError('Consumption cannot create a destination balance')
            if self.custody_due_date and (derived or self.custody_due_date<self.document_date):
                raise ValueError('Custody due date cannot precede issue date or be supplied on settlement')
        elif self.beneficiary_user_id or self.custody_due_date or (any(line.origin_line_id for line in self.lines) and self.document_type not in ('RETURN_SUPPLIER','ADJUSTMENT')):
            raise ValueError('Custody fields require a custody operation')
        transfer = self.document_type.startswith('TRANSFER_') or self.document_type == 'LOSS_TRANSIT'
        if self.document_type == 'LOSS_TRANSIT' and (not self.reason or not self.reason.strip()):
            raise ValueError('A documented loss reason is required')
        if transfer:
            if not self.destination_warehouse_id or self.destination_warehouse_id == self.warehouse_id:
                raise ValueError('Distinct source and destination warehouses are required')
            if self.source_module or any(line.request_line_id for line in self.lines):
                raise ValueError('Transfer cannot fulfill a request or equipment consumption')
            if any(bool(line.dispatch_line_id) != (self.document_type in ('TRANSFER_RECEIPT','LOSS_TRANSIT')) for line in self.lines):
                raise ValueError('Dispatch line is required only for transfer receipts')
        elif not custody and (self.destination_warehouse_id or any(line.destination_location_id or line.dispatch_line_id for line in self.lines)):
            raise ValueError('Transfer fields require a transfer document')
        values = (self.source_module, self.source_type, self.source_id)
        if any(value is not None for value in values) and any(value is None for value in values):
            raise ValueError('All source reference fields must be supplied together')
        if self.source_type == 'fuel_event' and self.document_type != 'ISSUE_DIRECT':
            raise ValueError('Fuel event source references require an ISSUE_DIRECT document')
        if self.source_type == 'fuel_return_event' and self.document_type != 'RECEIPT':
            raise ValueError('Fuel return event source references require a RECEIPT document')
        return self


class Posting(BaseModel):
    model_config = ConfigDict(extra='forbid')
    idempotency_key: str = Field(min_length=1, max_length=120)


class Reversal(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_date: date
    reason: str = Field(min_length=3,max_length=2000)

    @model_validator(mode='after')
    def documented(self):
        if len(self.reason.strip())<3:raise ValueError('A documented reversal reason is required')
        return self


class DocumentDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=3,max_length=2000)

    @field_validator('reason')
    @classmethod
    def documented_reason(cls,value):
        if len(value.strip())<3:raise ValueError('A documented decision reason is required')
        return value.strip()


class FinancialControls(BaseModel):
    model_config = ConfigDict(extra='forbid')
    posting_enabled: bool = False
    closed_through: date | None = None
