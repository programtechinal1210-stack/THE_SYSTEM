from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from shared.shared_core import BaseCommand

@dataclass
class CreateUserCommand(BaseCommand):
    username: str
    password: str
    full_name: str
    email: str
    organization_id: UUID
    phone: Optional[str] = None
    position: Optional[str] = None
    role_names: Optional[list[str]] = None
