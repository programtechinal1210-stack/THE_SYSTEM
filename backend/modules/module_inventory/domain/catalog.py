"""Inventory catalog input contracts (INV-01 foundation)."""
from typing import Annotated, Literal, Optional
from uuid import UUID
import json
from decimal import Decimal, InvalidOperation
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Unit(Input):
    code: Code
    name: Name
    dimension: Annotated[str, StringConstraints(max_length=40)] = ''
    precision: int = Field(default=3, ge=0, le=6)
    is_active: bool = True


class Category(Input):
    organization_id: UUID
    parent_id: Optional[UUID] = None
    code: Code
    name_ar: Name
    name_en: Annotated[str, StringConstraints(max_length=200)] = ''
    is_active: bool = True


class Item(Input):
    organization_id: UUID
    category_id: Optional[UUID] = None
    code: Code
    name_ar: Name
    name_en: Annotated[str, StringConstraints(max_length=200)] = ''
    base_unit_id: Optional[UUID] = None
    tracking_policy: Literal['none', 'lot', 'serial', 'lot_serial'] = 'none'
    attributes_json: Annotated[str, StringConstraints(max_length=8000)] = '{}'
    aliases_json: Annotated[str, StringConstraints(max_length=4000)] = '[]'
    barcode: Annotated[str, StringConstraints(strip_whitespace=True,max_length=120)] | None = None
    item_type: Literal['MATERIAL','SPARE_PART','CONSUMABLE','TOOL','OTHER'] = 'MATERIAL'
    notes: Annotated[str, StringConstraints(max_length=4000)] = ''
    is_active: bool = True

    @field_validator('aliases_json')
    @classmethod
    def aliases_array(cls,value):
        try: parsed=json.loads(value)
        except (ValueError,RecursionError): raise ValueError('Aliases must be a JSON string array') from None
        if not isinstance(parsed,list) or len(parsed)>50 or any(not isinstance(v,str) or not v.strip() or len(v)>120 for v in parsed):
            raise ValueError('Aliases require at most 50 nonempty strings of up to 120 characters')
        return json.dumps(list(dict.fromkeys(v.strip() for v in parsed)),ensure_ascii=False)

    @field_validator('attributes_json')
    @classmethod
    def attributes_object(cls, value):
        def invalid_constant(value):
            raise ValueError('Non-finite JSON number')
        try:
            parsed = json.loads(value, parse_float=Decimal, parse_constant=invalid_constant)
        except (ValueError, InvalidOperation, RecursionError):
            raise ValueError('attributes_json must be a valid finite JSON object') from None
        if not isinstance(parsed, dict):
            raise ValueError('attributes_json must be a JSON object')
        return value


class ItemUnit(Input):
    unit_id: UUID
    factor_num: Annotated[str, StringConstraints(max_length=28)] = '1'
    factor_den: Annotated[str, StringConstraints(max_length=28)] = '1'
    is_purchase: bool = False
    is_issue: bool = False

    @field_validator('factor_num', 'factor_den')
    @classmethod
    def positive_factor(cls, value):
        try:
            number = Decimal(value)
            if not number.is_finite() or number <= 0 or number.adjusted() > 18 or number.as_tuple().exponent < -12:
                raise ValueError()
        except (ValueError, InvalidOperation):
            raise ValueError('Factors must be finite positive decimals, up to 19 integer and 12 fractional digits') from None
        return value


class Warehouse(Input):
    organization_id: UUID
    operating_department_id: Optional[UUID] = None
    code: Code
    name: Name
    warehouse_type: Literal['central', 'branch', 'independent'] = 'central'
    parent_id: Optional[UUID] = None
    manager_user_id: Optional[UUID] = None
    operation_mode: Literal['centralized', 'hybrid', 'decentralized', 'independent'] = 'centralized'
    status: Literal['active', 'suspended', 'closed'] = 'active'


class Location(Input):
    code: Code
    name: Name
    parent_id: Optional[UUID] = None
    location_type: Literal['zone', 'aisle', 'shelf', 'bin', 'yard', 'cold'] = 'shelf'
    is_active: bool = True


KINDS = {
    'units': ('inv_units', Unit, 'code', None, None, False),
    'categories': ('inv_categories', Category, 'code', None, None, True),
    'items': ('inv_items', Item, 'code', None, None, True),
    'warehouses': ('inv_warehouses', Warehouse, 'code', None, None, True),
}
