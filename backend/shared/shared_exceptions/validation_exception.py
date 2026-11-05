from typing import List, Dict
from .base_exception import BaseException

class ValidationException(BaseException):
    def __init__(self, errors: List[Dict[str, str]]):
        self.errors = errors
        super().__init__(
            message="Validation failed",
            code="VALIDATION_ERROR"
        )
    
    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "errors": self.errors
        }
