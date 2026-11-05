"""Persistence for the shared entity directory."""
from uuid import UUID


class BaseRepo:
    def __init__(self, session, model, mapper):
        self.session = session; self.model = model; self.mapper = mapper
    async def all(self, skip=0, limit=100):
        from sqlalchemy import select
        r = await self.session.execute(select(self.model).offset(skip).limit(limit).order_by(self.model.name))
        return [self.mapper.to_entity(m) for m in r.scalars().all()]
    async def get(self, id: UUID):
        from sqlalchemy import select
        r = await self.session.execute(select(self.model).where(self.model.id == id))
        m = r.scalar_one_or_none()
        return self.mapper.to_entity(m) if m else None
    async def save(self, entity):
        data = entity.model_dump(exclude={'id','created_at','updated_at'}, exclude_none=False)
        if entity.id:
            from sqlalchemy import update
            await self.session.execute(update(self.model).where(self.model.id == entity.id).values(**data))
            await self.session.flush(); return await self.get(entity.id)
        else:
            m = self.model(**data); self.session.add(m); await self.session.flush()
            return self.mapper.to_entity(m)
    async def delete(self, id: UUID):
        from sqlalchemy import delete
        r = await self.session.execute(delete(self.model).where(self.model.id == id))
        await self.session.flush(); return r.rowcount > 0

