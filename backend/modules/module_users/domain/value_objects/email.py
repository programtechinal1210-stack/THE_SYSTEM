import re
from shared.shared_exceptions import ValidationException

class Email:
    def __init__(self, value: str):
        self._value = value
        if not self.validate():
            raise ValidationException([{"field": "email", "message": "Invalid email format"}])
    
    @property
    def value(self) -> str:
        return self._value
    
    def validate(self) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, self._value))
    
    def equals(self, other) -> bool:
        if not isinstance(other, Email):
            return False
        return self._value == other._value
    
    def __str__(self) -> str:
        return self._value
