# infrastructure/database/repositories/base_repository.py
from typing import Optional, List, TypeVar, Generic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

T = TypeVar('T')


class BaseRepository(Generic[T]):

    def __init__(self, session: AsyncSession):
        self.session = session
        self.model = None

    async def save(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get_by_id(self, id: int) -> Optional[T]:
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, id: int, **kwargs) -> Optional[T]:
        stmt = update(self.model).where(self.model.id == id).values(**kwargs)
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            return None
        await self.session.flush()
        return await self.get_by_id(id)

    async def delete(self, id: int) -> bool:
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar()
