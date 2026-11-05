from typing import TypeVar, Generic, Optional

T = TypeVar('T')

class Result(Generic[T]):
    def __init__(self, is_success: bool, value: Optional[T] = None, error: Optional[str] = None):
        self.is_success = is_success
        self.value = value
        self.error = error
    
    @classmethod
    def success(cls, value: T) -> 'Result[T]':
        return cls(True, value)
    
    @classmethod
    def failure(cls, error: str) -> 'Result[T]':
        return cls(False, error=error)
    
    def unwrap(self) -> T:
        if not self.is_success:
            raise ValueError(f"Attempted to unwrap failed result: {self.error}")
        return self.value
