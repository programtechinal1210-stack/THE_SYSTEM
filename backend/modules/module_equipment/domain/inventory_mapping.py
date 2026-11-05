from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FuelInventoryMappingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization_id: UUID
    item_id: UUID
    warehouse_id: UUID
    is_active: bool = True
