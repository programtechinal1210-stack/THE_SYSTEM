from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator

from .catalog import Input

PartText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
IdempotencyKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class PartInstallInput(Input):
    inventory_item_id: UUID
    mount_position: PartText
    part_serial_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    lot_number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    installed_at: datetime
    maintenance_order_id: UUID | None = None
    installation_inventory_document_id: UUID
    idempotency_key: IdempotencyKey

    @field_validator("installed_at")
    @classmethod
    def installed_at_must_be_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone-aware timestamp required")
        return value.astimezone(timezone.utc)


class PartRemovalInput(Input):
    removed_at: datetime
    reason_code: PartText
    removal_inventory_document_id: UUID
    idempotency_key: IdempotencyKey

    @field_validator("removed_at")
    @classmethod
    def removed_at_must_be_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone-aware timestamp required")
        return value.astimezone(timezone.utc)


class PartReplacementInput(PartInstallInput):
    removed_at: datetime
    removal_reason_code: PartText
    removal_inventory_document_id: UUID

    @field_validator("removed_at")
    @classmethod
    def removed_at_must_be_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone-aware timestamp required")
        return value.astimezone(timezone.utc)
