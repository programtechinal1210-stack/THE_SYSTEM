"""Composition of authorized entity references; no arbitrary table or URL lookup."""
from dataclasses import replace
from uuid import UUID
from fastapi import APIRouter, Depends, Request
from core.module_registry import registry
from infrastructure.database.db_context import get_session
from infrastructure.database.models.organization_model import OrganizationModel
from modules.module_users.infrastructure.models.user_model import UserModel
from modules.module_organizations.infrastructure.models.entity_model import EntityModel

router = APIRouter(prefix="/api/v1/references", tags=["entity references"])


async def user_reference(session, actor, admin, scopes, identifier):
    target = await session.get(UserModel, identifier)
    if target and (admin or "institution" in scopes or target.id == actor.id or
                   ("organization" in scopes and target.organization_id == actor.organization_id)):
        return {"label": target.full_name, "href": f"/users/{target.id}/"}


async def unit_reference(session, actor, admin, scopes, identifier):
    target = await session.get(OrganizationModel, identifier)
    if target and (admin or "institution" in scopes or target.id == actor.organization_id):
        return {"label": target.name, "href": "/organizations/tree/"}


async def entity_reference(session, actor, admin, scopes, identifier):
    # Shared directory records are institution-wide reference data, not user-owned.
    target = await session.get(EntityModel, identifier)
    if target:
        return {"label": target.name, "href": "/organizations/"}


for module, name, permission, resolver in (
    ("users", "users.user", "core.users.view", user_reference),
    ("organizations", "organizations.unit", "core.organizations.view", unit_reference),
    ("entities", "entities.entity", "core.organizations.view", entity_reference),
):
    registry.modules[module] = replace(registry.modules[module], entity_types=(name,))
    registry.register_entity(module, name, permission, resolver)


@router.get("/{entity_type}/{entity_id}")
async def resolve(entity_type: str, entity_id: UUID, request: Request, session=Depends(get_session, scope="function")):
    return await registry.resolve_entity(entity_type, entity_id, request, session)
