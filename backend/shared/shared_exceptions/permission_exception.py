from .base_exception import BaseException

class PermissionException(BaseException):
    def __init__(self, action: str):
        super().__init__(
            message=f"User does not have permission to perform '{action}'",
            code="PERMISSION_DENIED"
        )
