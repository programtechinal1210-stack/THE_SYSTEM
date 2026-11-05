from abc import ABC, abstractmethod
from typing import Optional, List
from ..entities.role import Role

class IRoleRepository(ABC):
    @abstractmethod
    async def save(self, role: Role) -> Role:
        pass

    @abstractmethod
    async def get_by_id(self, role_id: int) -> Optional[Role]:
        pass

    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Role]:
        pass

    @abstractmethod
    async def list(self) -> List[Role]:
        pass

    @abstractmethod
    async def delete(self, role_id: int) -> bool:
        pass
