from dataclasses import dataclass
from shared.shared_core import BaseCommand

@dataclass
class LoginUserCommand(BaseCommand):
    username: str
    password: str
