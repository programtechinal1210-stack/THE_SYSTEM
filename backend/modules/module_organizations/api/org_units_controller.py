from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from infrastructure.database.db_context import get_session
from infrastructure.database.models.organization_model import OrganizationModel
from modules.module_users.infrastructure.models.user_model import UserModel

router = APIRouter(prefix="/api/v1/org-units", tags=["organizational hierarchy"])


class UnitInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    parent_id: UUID | None = None
    is_active: bool = True


def output(unit):
    return {"id": str(unit.id), "name": unit.name, "parent_id": str(unit.parent_id) if unit.parent_id else None, "is_active": unit.is_active}


def check_scope(request, uid=None):
    if request.state.is_admin or "institution" in request.state.scopes:
        return
    if uid and uid == request.state.user.organization_id:
        return
    raise HTTPException(403, "Outside organizational scope")


from ..application.hierarchy import validate_parent


@router.get("")
@router.get("/tree")
async def list_units(request: Request, session=Depends(get_session, scope="function")):
    stmt = select(OrganizationModel).order_by(OrganizationModel.name)
    if not request.state.is_admin and "institution" not in request.state.scopes:
        stmt = stmt.where(OrganizationModel.id == request.state.user.organization_id)
    return [output(unit) for unit in (await session.scalars(stmt)).all()]


@router.post("", status_code=201)
async def create_unit(data: UnitInput, request: Request, session=Depends(get_session, scope="function")):
    check_scope(request)
    await validate_parent(session, data.parent_id)
    unit = OrganizationModel(**data.model_dump())
    session.add(unit)
    await session.flush()
    return output(unit)


@router.get("/{uid}")
async def get_unit(uid: UUID, request: Request, session=Depends(get_session, scope="function")):
    check_scope(request, uid)
    unit = await session.get(OrganizationModel, uid)
    if not unit:
        raise HTTPException(404, "Organizational unit not found")
    return output(unit)


@router.put("/{uid}")
async def update_unit(uid: UUID, data: UnitInput, request: Request, session=Depends(get_session, scope="function")):
    check_scope(request)
    unit = await session.get(OrganizationModel, uid)
    if not unit:
        raise HTTPException(404, "Organizational unit not found")
    await validate_parent(session, data.parent_id, uid)
    if not data.is_active:
        users = await session.scalar(select(func.count()).select_from(UserModel).where(UserModel.organization_id == uid, UserModel.is_active.is_(True)))
        children = await session.scalar(select(func.count()).select_from(OrganizationModel).where(OrganizationModel.parent_id == uid, OrganizationModel.is_active.is_(True)))
        if users or children:
            raise HTTPException(409, "Move or deactivate active users and children first")
    request.state.audit_details = {"entity_type": "core.organization", "entity_id": str(uid), "old": output(unit), "new": data.model_dump(mode="json")}
    for key, value in data.model_dump().items():
        setattr(unit, key, value)
    await session.flush()
    return output(unit)
