from typing import Optional, List, Type
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from pydantic import BaseModel

class BaseSettingRepository:
    def __init__(self, session: AsyncSession, model: Type, entity: Type[BaseModel]):
        self.session = session; self.model = model; self.entity = entity

    def _to_entity(self, m): return self.entity(**{c.name: getattr(m, c.name) for c in m.__table__.columns})

    async def all(self, skip=0, limit=100):
        r = await self.session.execute(select(self.model).offset(skip).limit(limit))
        return [self._to_entity(m) for m in r.scalars().all()]

    async def get(self, id: UUID):
        r = await self.session.execute(select(self.model).where(self.model.id == id))
        m = r.scalar_one_or_none(); return self._to_entity(m) if m else None

    async def save(self, entity):
        data = entity.model_dump(exclude={'id','created_at','updated_at'}, exclude_none=False)
        if entity.id:
            await self.session.execute(update(self.model).where(self.model.id == entity.id).values(**data))
            await self.session.flush(); return await self.get(entity.id)
        else:
            m = self.model(**data); self.session.add(m); await self.session.flush(); return self._to_entity(m)

    async def delete(self, id: UUID):
        r = await self.session.execute(delete(self.model).where(self.model.id == id))
        await self.session.flush(); return r.rowcount > 0
