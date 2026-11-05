from typing import Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.followup_model import FollowUpModel
from shared.shared_audit.dtos.followup_dto import (
    CreateFollowupDTO,
    UpdateFollowupDTO,
    FollowupResponseDTO,
)


class FollowupService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: UUID,
        data: CreateFollowupDTO,
    ) -> FollowupResponseDTO:
        model = FollowUpModel(
            user_id=user_id,
            **data.model_dump(exclude_none=True),
        )
        self.session.add(model)
        await self.session.flush()
        return FollowupResponseDTO.model_validate(model)

    async def get_by_entity(
        self,
        entity_type: str,
        entity_id: UUID,
    ) -> List[FollowupResponseDTO]:
        stmt = (
            select(FollowUpModel)
            .where(
                FollowUpModel.entity_type == entity_type,
                FollowUpModel.entity_id == entity_id,
            )
            .order_by(FollowUpModel.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return [
            FollowupResponseDTO.model_validate(m)
            for m in result.scalars().all()
        ]

    async def get_by_id(
        self,
        followup_id: UUID,
    ) -> Optional[FollowupResponseDTO]:
        result = await self.session.execute(
            select(FollowUpModel).where(
                FollowUpModel.id == followup_id
            )
        )
        model = result.scalar_one_or_none()
        return (
            FollowupResponseDTO.model_validate(model)
            if model
            else None
        )

    async def update(
        self,
        followup_id: UUID,
        data: UpdateFollowupDTO,
    ) -> Optional[FollowupResponseDTO]:
        from sqlalchemy import update

        await self.session.execute(
            update(FollowUpModel)
            .where(FollowUpModel.id == followup_id)
            .values(**data.model_dump(exclude_none=True))
        )
        await self.session.flush()
        return await self.get_by_id(followup_id)

    async def delete(self, followup_id: UUID) -> bool:
        from sqlalchemy import delete

        result = await self.session.execute(
            delete(FollowUpModel).where(
                FollowUpModel.id == followup_id
            )
        )
        await self.session.flush()
        return result.rowcount > 0