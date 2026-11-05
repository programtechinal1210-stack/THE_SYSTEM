from typing import List, Optional, Type
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from pydantic import BaseModel
from datetime import datetime

class BaseNotificationRepository:
    def __init__(self, session: AsyncSession, model: Type, entity: Type[BaseModel]):
        self.session = session; self.model = model; self.entity = entity

    def _to_entity(self, m): return self.entity(**{c.name: getattr(m, c.name) for c in m.__table__.columns})

    async def all(self, skip=0, limit=100):
        r = await self.session.execute(select(self.model).offset(skip).limit(limit))
        return [self._to_entity(m) for m in r.scalars().all()]

    async def get_by_user(self, user_id: UUID, unread_only: bool=False, limit: int=50, skip: int=0):
        stmt = select(self.model).where(self.model.user_id == user_id)
        if unread_only: stmt = stmt.where(self.model.is_read == False)
        stmt = stmt.order_by(self.model.created_at.desc(), self.model.id.desc()).offset(skip).limit(limit)
        r = await self.session.execute(stmt)
        return [self._to_entity(m) for m in r.scalars().all()]

    async def unread_count(self, user_id: UUID) -> int:
        r = await self.session.execute(select(func.count()).select_from(self.model).where(self.model.user_id == user_id, self.model.is_read == False))
        return r.scalar() or 0

    async def mark_read(self, notification_ids: List[UUID], user_id: UUID):
        await self.session.execute(update(self.model).where(self.model.id.in_(notification_ids), self.model.user_id == user_id).values(is_read=True, read_at=datetime.now()))
        await self.session.flush()

    async def mark_all_read(self, user_id: UUID):
        await self.session.execute(update(self.model).where(self.model.user_id == user_id, self.model.is_read == False).values(is_read=True, read_at=datetime.now()))
        await self.session.flush()

    async def save(self, entity):
        data = entity.model_dump(exclude={'id','created_at','read_at','delivered_at'}, exclude_none=False)
        m = self.model(**data); self.session.add(m); await self.session.flush(); return self._to_entity(m)

