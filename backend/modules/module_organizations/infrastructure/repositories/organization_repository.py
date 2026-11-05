from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from infrastructure.database.models.organization_model import OrganizationModel
from ...domain.entities.organization import Organization
from ..mappers.organization_mapper import OrganizationMapper

class OrganizationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session; self.model = OrganizationModel

    async def save(self, entity: Organization) -> Organization:
        data = entity.model_dump(exclude={'id'}, exclude_none=False)
        if entity.id:
            stmt = update(self.model).where(self.model.id == entity.id).values(**data)
            await self.session.execute(stmt); await self.session.flush()
            return await self.get_by_id(entity.id)
        else:
            model = self.model(**data); self.session.add(model)
            await self.session.flush(); return OrganizationMapper.to_entity(model)

    async def get_by_id(self, id: UUID) -> Optional[Organization]:
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        model = result.scalar_one_or_none()
        return OrganizationMapper.to_entity(model) if model else None

    async def get_all(self, skip=0, limit=50) -> List[Organization]:
        stmt = select(self.model).offset(skip).limit(limit).order_by(self.model.name)
        result = await self.session.execute(stmt)
        return [OrganizationMapper.to_entity(m) for m in result.scalars().all()]

    async def delete(self, id: UUID) -> bool:
        result = await self.session.execute(delete(self.model).where(self.model.id == id))
        await self.session.flush(); return result.rowcount > 0
