"""Input contracts for the EMO registry foundation."""
from datetime import date
from decimal import Decimal
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Code = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=180)]
MeterType = Literal["hours", "distance", "cycles", "energy", "none"]
OwnershipType = Literal["owned", "rented", "leased", "borrowed"]
LifecycleStatus = Literal["in_service", "suspended", "retired", "disposed"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _json_object(value):
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    if len(json.dumps(value, ensure_ascii=False)) > 16000:
        raise ValueError("JSON object exceeds 16000 characters")
    return value


class CategoryInput(Input):
    category_code: Code
    name_ar: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)]
    name_en: Annotated[str, StringConstraints(max_length=180)] = ""
    parent_id: UUID | None = None
    meter_type: MeterType
    meter_unit: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
    output_unit: ShortText | None = None
    fuel_unit: ShortText | None = None
    spec_schema: dict = Field(default_factory=dict)
    inspection_schema: dict = Field(default_factory=dict)
    maintenance_rules: dict = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("spec_schema", "inspection_schema", "maintenance_rules")
    @classmethod
    def validate_json_object(cls, value):
        return _json_object(value)


class CategoryUpdate(Input):
    category_code: Code | None = None
    name_ar: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)] | None = None
    name_en: Annotated[str, StringConstraints(max_length=180)] | None = None
    parent_id: UUID | None = None
    meter_type: MeterType | None = None
    meter_unit: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)] | None = None
    output_unit: ShortText | None = None
    fuel_unit: ShortText | None = None
    spec_schema: dict | None = None
    inspection_schema: dict | None = None
    maintenance_rules: dict | None = None
    is_active: bool | None = None
    version: int = Field(ge=1)

    @field_validator("spec_schema", "inspection_schema", "maintenance_rules")
    @classmethod
    def validate_json_objects(cls, value):
        return None if value is None else _json_object(value)

    @model_validator(mode="after")
    def validate_non_nullable_fields(self):
        for field in (
            "category_code", "name_ar", "name_en", "meter_type", "meter_unit",
            "spec_schema", "inspection_schema", "maintenance_rules", "is_active",
        ):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class AssetInput(Input):
    asset_code: Code
    asset_name: Name
    category_id: UUID
    serial_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    manufacturer: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ""
    model: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ""
    ownership_type: OwnershipType
    owner_entity_id: UUID | None = None
    responsible_entity_id: UUID | None = None
    custodian_ref_type: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    custodian_ref_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    home_location: Annotated[str, StringConstraints(max_length=300)] | None = None
    current_location: Annotated[str, StringConstraints(max_length=300)] | None = None
    lifecycle_status: LifecycleStatus = "in_service"
    meter_initial: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=6)
    acquisition_date: date | None = None
    acquisition_value: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=4)
    currency_id: UUID | None = None
    rental_contract_ref: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    specifications: dict = Field(default_factory=dict)
    notes: Annotated[str, StringConstraints(max_length=4000)] = ""

    @field_validator("specifications")
    @classmethod
    def validate_specifications(cls, value):
        return _json_object(value)

    @field_validator("custodian_ref_id")
    @classmethod
    def require_custodian_type(cls, value, info):
        if value and not info.data.get("custodian_ref_type"):
            raise ValueError("custodian_ref_type is required with custodian_ref_id")
        return value

    @model_validator(mode="after")
    def validate_acquisition_currency(self):
        if self.acquisition_value is not None and self.currency_id is None:
            raise ValueError("currency_id is required when acquisition_value is provided")
        return self


class AssetUpdate(Input):
    asset_name: Name | None = None
    serial_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    manufacturer: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    model: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    ownership_type: OwnershipType | None = None
    owner_entity_id: UUID | None = None
    responsible_entity_id: UUID | None = None
    custodian_ref_type: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    custodian_ref_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    home_location: Annotated[str, StringConstraints(max_length=300)] | None = None
    current_location: Annotated[str, StringConstraints(max_length=300)] | None = None
    acquisition_date: date | None = None
    acquisition_value: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=4)
    currency_id: UUID | None = None
    rental_contract_ref: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    specifications: dict | None = None
    notes: Annotated[str, StringConstraints(max_length=4000)] | None = None
    version: int = Field(ge=1)

    @field_validator("specifications")
    @classmethod
    def validate_specifications(cls, value):
        return None if value is None else _json_object(value)

    @model_validator(mode="after")
    def validate_non_nullable_fields(self):
        for field in ("asset_name", "ownership_type", "responsible_entity_id", "specifications", "notes"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
