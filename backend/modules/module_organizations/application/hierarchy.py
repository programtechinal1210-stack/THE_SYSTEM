from fastapi import HTTPException
from infrastructure.database.models.organization_model import OrganizationModel


async def validate_parent(session, parent_id, uid=None):
    seen = {uid} if uid else set()
    while parent_id:
        if parent_id in seen:
            raise HTTPException(409, "Organizational cycle")
        seen.add(parent_id)
        parent = await session.get(OrganizationModel, parent_id)
        if not parent or not parent.is_active:
            raise HTTPException(422, "Parent must be an active organizational unit")
        parent_id = parent.parent_id


