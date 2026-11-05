from .base_exception import BaseException

class NotFoundException(BaseException):
    def __init__(self, entity_name: str, identifier: str):
        super().__init__(
            message=f"{entity_name} with identifier '{identifier}' not found",
            code="NOT_FOUND"
        )
