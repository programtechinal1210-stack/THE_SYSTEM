# shared/shared_core/base_entity.py
from datetime import datetime
from typing import Optional
from uuid import UUID


class BaseEntity:
    def __init__(
        self,
        id: Optional[UUID] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
