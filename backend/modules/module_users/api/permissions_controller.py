# modules/module_users/api/permissions_controller.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.db_context import get_session
from modules.module_users.infrastructure.repositories.permission_repository import PermissionRepository
from modules.module_users.application.dtos.permission_dto import PermissionDTO, CreatePermissionDTO
from api.dependencies import get_current_user
from modules.module_users.domain.entities.user import User
from modules.module_users.domain.entities.permission import Permission

permissions_router = APIRouter(prefix="/api/v1/permissions", tags=["permissions"])

async def get_permission_repository(session: AsyncSession = Depends(get_session, scope="function")):
    return PermissionRepository(session)


@permissions_router.get("/", response_model=list[PermissionDTO])
async def list_permissions(
    current_user: User = Depends(get_current_user),
    permission_repo: PermissionRepository = Depends(get_permission_repository)
):
    permissions = await permission_repo.get_all()
    return [PermissionDTO.from_entity(permission) for permission in permissions]


@permissions_router.get("/{permission_id}", response_model=PermissionDTO)
async def get_permission(
    permission_id: int,
    current_user: User = Depends(get_current_user),
    permission_repo: PermissionRepository = Depends(get_permission_repository)
):
    permission = await permission_repo.get_by_id(permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail=f"Permission {permission_id} not found")
    return PermissionDTO.from_entity(permission)


@permissions_router.post("/", response_model=PermissionDTO, status_code=201)
async def create_permission(
    perm_data: CreatePermissionDTO,
    current_user: User = Depends(get_current_user),
    permission_repo: PermissionRepository = Depends(get_permission_repository)
):
    permission = Permission(
        code=perm_data.code,
        name=perm_data.name,
        description=perm_data.description,
        system=perm_data.system,
        resource=perm_data.resource,
        action=perm_data.action
    )
    saved = await permission_repo.save(permission)
    return PermissionDTO.from_entity(saved)



@permissions_router.put("/{permission_id}", response_model=PermissionDTO)
async def update_permission(
    permission_id: int,
    perm_data: CreatePermissionDTO,
    current_user: User = Depends(get_current_user),
    permission_repo: PermissionRepository = Depends(get_permission_repository)
):
    permission = await permission_repo.get_by_id(permission_id)
    if not permission:
        raise HTTPException(status_code=404, detail=f"Permission {permission_id} not found")
    
    permission.code = perm_data.code
    permission.name = perm_data.name
    permission.description = perm_data.description
    permission.system = perm_data.system
    permission.resource = perm_data.resource
    permission.action = perm_data.action
    
    saved = await permission_repo.save(permission)
    return PermissionDTO.from_entity(saved)

@permissions_router.delete("/{permission_id}", status_code=204)
async def delete_permission(
    permission_id: int,
    current_user: User = Depends(get_current_user),
    permission_repo: PermissionRepository = Depends(get_permission_repository)
):
    deleted = await permission_repo.delete(permission_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Permission {permission_id} not found")

