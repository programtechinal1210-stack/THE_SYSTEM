# modules/module_users/api/roles_controller.py
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import bindparam, text

from infrastructure.database.db_context import get_session
from modules.module_users.infrastructure.repositories.role_repository import RoleRepository
from modules.module_users.infrastructure.repositories.permission_repository import PermissionRepository
from modules.module_users.application.dtos.role_dto import RoleDTO, CreateRoleDTO, UpdateRoleDTO
from modules.module_users.application.dtos.permission_dto import PermissionDTO
from api.dependencies import get_current_user
from modules.module_users.domain.entities.user import User
from modules.module_users.domain.entities.role import Role
from modules.module_users.domain.entities.permission import Permission

roles_router = APIRouter(prefix="/api/v1/roles", tags=["roles"])


class PermissionUnitScopes(BaseModel):
    unit_ids: list[UUID] = Field(min_length=1)


def require_admin(request):
    if not request.state.is_admin:
        raise HTTPException(403, "Administrator required")

async def get_role_repository(session: AsyncSession = Depends(get_session, scope="function")):
    return RoleRepository(session)

async def get_permission_repository(session: AsyncSession = Depends(get_session, scope="function")):
    return PermissionRepository(session)


@roles_router.get("/", response_model=list[RoleDTO])
async def list_roles(
    current_user: User = Depends(get_current_user),
    role_repo: RoleRepository = Depends(get_role_repository)
):
    roles = await role_repo.get_all()
    return [RoleDTO.from_entity(role) for role in roles]


@roles_router.get("/{role_id}", response_model=RoleDTO)
async def get_role(
    role_id: int,
    current_user: User = Depends(get_current_user),
    role_repo: RoleRepository = Depends(get_role_repository)
):
    role = await role_repo.get_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")
    return RoleDTO.from_entity(role)


@roles_router.post("/", response_model=RoleDTO, status_code=201)
async def create_role(
    role_data: CreateRoleDTO,
    current_user: User = Depends(get_current_user),
    role_repo: RoleRepository = Depends(get_role_repository)
):
    if role_data.name == "admin":
        raise HTTPException(403, "Reserved role name")
    role = Role(name=role_data.name, description=role_data.description)
    saved = await role_repo.save(role)
    return RoleDTO.from_entity(saved)


@roles_router.put("/{role_id}", response_model=RoleDTO)
async def update_role(
    role_id: int,
    role_data: UpdateRoleDTO,
    current_user: User = Depends(get_current_user),
    role_repo: RoleRepository = Depends(get_role_repository)
):
    role = await role_repo.get_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")
    
    if role.is_system:
        raise HTTPException(403, "System roles cannot be renamed")
    if role_data.name is not None:
        role.name = role_data.name
    if role_data.description is not None:
        role.description = role_data.description
    
    saved = await role_repo.save(role)
    return RoleDTO.from_entity(saved)


@roles_router.delete("/{role_id}", status_code=204)
async def delete_role(
    role_id: int,
    current_user: User = Depends(get_current_user),
    role_repo: RoleRepository = Depends(get_role_repository)
):
    role = await role_repo.get_by_id(role_id)
    if role and role.is_system:
        raise HTTPException(403, "System role cannot be deleted")
    deleted = await role_repo.delete(role_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")



@roles_router.get("/{role_id}/permissions", response_model=list[PermissionDTO])
async def get_role_permissions(
    role_id: int,
    current_user: User = Depends(get_current_user),
    role_repo: RoleRepository = Depends(get_role_repository)
):
    role = await role_repo.get_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")
    return [PermissionDTO.from_entity(p) for p in role.permissions]

@roles_router.post("/{role_id}/permissions", status_code=201)
async def assign_permission_to_role(
    role_id: int,
    permission_data: dict,
    current_user: User = Depends(get_current_user),
    role_repo: RoleRepository = Depends(get_role_repository),
    perm_repo: PermissionRepository = Depends(get_permission_repository)
):
    role = await role_repo.get_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found")
    
    perm_id = permission_data.get("permission_id")
    if not perm_id:
        raise HTTPException(status_code=400, detail="permission_id required")
    
    permission = await perm_repo.get_by_id(perm_id)
    if not permission:
        raise HTTPException(status_code=404, detail=f"Permission {perm_id} not found")
    
    await role_repo.assign_permission(role_id, perm_id)
    return {"detail": "Permission assigned to role"}


@roles_router.delete("/{role_id}/permissions/{permission_id}", status_code=204)
async def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    current_user: User = Depends(get_current_user),
    role_repo: RoleRepository = Depends(get_role_repository)
):
    await role_repo.remove_permission(role_id, permission_id)


@roles_router.get("/{role_id}/permissions/{permission_id}/unit-scopes")
async def get_permission_unit_scopes(
    role_id: int,
    permission_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session, scope="function"),
):
    require_admin(request)
    from core.module_registry import registry
    permission_code = await session.scalar(text(
        "SELECT code FROM permissions WHERE id=:permission"
    ), {"permission": permission_id})
    if not await session.scalar(text(
        "SELECT 1 FROM role_permissions WHERE role_id=:role AND permission_id=:permission"
    ), {"role": role_id, "permission": permission_id}):
        raise HTTPException(404, "Role permission assignment not found")
    if not permission_code or registry.unit_scope_owner(permission_code) is None:
        raise HTTPException(422, "Permission does not support unit-bound scopes")
    rows = (await session.execute(text(
        "SELECT s.unit_id,o.name FROM role_permission_unit_scopes s "
        "JOIN role_permissions rp ON rp.id=s.role_permission_id "
        "JOIN organizations o ON o.id=s.unit_id "
        "WHERE rp.role_id=:role AND rp.permission_id=:permission ORDER BY o.name"
    ), {"role": role_id, "permission": permission_id})).mappings().all()
    return {"unit_ids": [row["unit_id"] for row in rows],
            "units": [{"id": row["unit_id"], "name": row["name"]} for row in rows]}


@roles_router.put("/{role_id}/permissions/{permission_id}/unit-scopes")
async def set_permission_unit_scopes(
    role_id: int,
    permission_id: int,
    data: PermissionUnitScopes,
    request: Request,
    session: AsyncSession = Depends(get_session, scope="function"),
):
    require_admin(request)
    from core.module_registry import registry
    permission_code = await session.scalar(text(
        "SELECT code FROM permissions WHERE id=:permission"
    ), {"permission": permission_id})
    assignment_id = await session.scalar(text(
        "SELECT id FROM role_permissions WHERE role_id=:role AND permission_id=:permission"
    ), {"role": role_id, "permission": permission_id})
    if assignment_id is None:
        raise HTTPException(404, "Role permission assignment not found")
    if not permission_code or registry.unit_scope_owner(permission_code) is None:
        raise HTTPException(422, "Permission does not support unit-bound scopes")
    unit_ids = sorted({unit.hex for unit in data.unit_ids})
    existing = set((await session.execute(text(
        "SELECT id FROM organizations WHERE is_active=1 AND id IN :ids"
    ).bindparams(bindparam("ids", expanding=True)),
        {"ids": unit_ids})).scalars())
    if existing != set(unit_ids):
        raise HTTPException(422, "Every scoped unit must exist and be active")
    old_ids = list((await session.execute(text(
        "SELECT unit_id FROM role_permission_unit_scopes WHERE role_permission_id=:assignment "
        "ORDER BY unit_id"
    ), {"assignment": assignment_id})).scalars())
    await session.execute(text(
        "DELETE FROM role_permission_unit_scopes WHERE role_permission_id=:assignment"
    ), {"assignment": assignment_id})
    await session.execute(text(
        "INSERT INTO role_permission_unit_scopes(role_permission_id,unit_id) "
        "VALUES(:assignment,:unit)"
    ), [{"assignment": assignment_id, "unit": unit_id} for unit_id in unit_ids])
    request.state.audit_details = {
        "entity_type": "core.role_permission",
        "entity_id": None,
        "old": {"role_id": role_id, "permission": permission_code, "unit_ids": old_ids},
        "new": {"role_id": role_id, "permission": permission_code, "unit_ids": unit_ids},
        "summary": "Core permission exact-unit scope updated",
    }
    return {"permission": permission_code, "unit_ids": unit_ids}


@roles_router.delete("/{role_id}/permissions/{permission_id}/unit-scopes", status_code=204)
async def clear_permission_unit_scopes(
    role_id: int,
    permission_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session, scope="function"),
):
    require_admin(request)
    from core.module_registry import registry
    permission_code = await session.scalar(text(
        "SELECT code FROM permissions WHERE id=:permission"
    ), {"permission": permission_id})
    assignment_id = await session.scalar(text(
        "SELECT id FROM role_permissions WHERE role_id=:role AND permission_id=:permission"
    ), {"role": role_id, "permission": permission_id})
    if assignment_id is None:
        raise HTTPException(404, "Role permission assignment not found")
    if not permission_code or registry.unit_scope_owner(permission_code) is None:
        raise HTTPException(422, "Permission does not support unit-bound scopes")
    old_ids = list((await session.execute(text(
        "SELECT unit_id FROM role_permission_unit_scopes WHERE role_permission_id=:assignment "
        "ORDER BY unit_id"
    ), {"assignment": assignment_id})).scalars())
    if not old_ids:
        raise HTTPException(404, "Unit scope is not configured")
    await session.execute(text(
        "DELETE FROM role_permission_unit_scopes WHERE role_permission_id=:assignment"
    ), {"assignment": assignment_id})
    request.state.audit_details = {
        "entity_type": "core.role_permission",
        "entity_id": None,
        "old": {"role_id": role_id, "permission": permission_code, "unit_ids": old_ids},
        "new": {"scope": "role default; unit restriction removed"},
        "summary": "Core permission exact-unit restriction removed",
    }
