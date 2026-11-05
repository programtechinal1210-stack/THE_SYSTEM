from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel

class SystemSetting(BaseModel):
    model_config = {"from_attributes": True}
    id: Optional[UUID] = None; key: str = ""; category_id: Optional[UUID] = None
    value: Any = None; default_value: Any = None; data_type: str = "string"
    description_ar: Optional[str] = None; description_en: Optional[str] = None
    is_encrypted: bool = False; is_required: bool = True; is_active: bool = True
    validation_rules: Optional[dict] = None; options: Optional[dict] = None
    created_by: Optional[UUID] = None; updated_by: Optional[UUID] = None
    created_at: Optional[datetime] = None; updated_at: Optional[datetime] = None
