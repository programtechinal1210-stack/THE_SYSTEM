from typing import List, TypeVar, Generic
from dataclasses import dataclass

T = TypeVar('T')

@dataclass
class PaginatedList(Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    
    @property
    def total_pages(self) -> int:
        return (self.total + self.size - 1) // self.size if self.size > 0 else 0
    
    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages
    
    @property
    def has_previous(self) -> bool:
        return self.page > 1
