from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from ...domain.interfaces.i_role_repository import IRoleRepository
from ...domain.entities.role import Role
from ...domain.entities.permission import Permission
from ..models.role_model import RoleModel
from ..models.role_permission_model import RolePermissionModel

class RoleRepository(IRoleRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, role: Role) -> Role:
        if role.id:
            stmt = delete(RolePermissionModel).where(RolePermissionModel.role_id == role.id)
            await self._session.execute(stmt)
            await self._session.flush()

        role_model = RoleModel(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system=role.is_system
        )

        if role.id:
            await self._session.merge(role_model)
        else:
            self._session.add(role_model)

        await self._session.flush()

        for permission in role.permissions:
            rp = RolePermissionModel(
                role_id=role_model.id,
                permission_id=permission.id
            )
            self._session.add(rp)

        await self._session.flush()

        stmt = select(RoleModel).where(RoleModel.id == role_model.id).options(
            selectinload(RoleModel.permissions).selectinload(RolePermissionModel.permission)
        )
        result = await self._session.execute(stmt)
        saved_model = result.scalar_one()

        saved_role = Role(
            id=saved_model.id,
            name=saved_model.name,
            description=saved_model.description,
            is_system=saved_model.is_system,
            created_at=saved_model.created_at
        )

        for rp in saved_model.permissions:
            if rp.permission:
                saved_role.add_permission(Permission(
                    id=rp.permission.id,
                    code=rp.permission.code,
                    name=rp.permission.name,
                    description=rp.permission.description,
                    system=rp.permission.system,
                    resource=rp.permission.resource,
                    action=rp.permission.action,
                    created_at=rp.permission.created_at
                ))

        return saved_role

    async def get_by_id(self, role_id: int) -> Optional[Role]:
        stmt = select(RoleModel).where(RoleModel.id == role_id).options(
            selectinload(RoleModel.permissions).selectinload(RolePermissionModel.permission)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        role = Role(
            id=model.id,
            name=model.name,
            description=model.description,
            is_system=model.is_system,
            created_at=model.created_at
        )

        for rp in model.permissions:
            if rp.permission:
                role.add_permission(Permission(
                    id=rp.permission.id,
                    code=rp.permission.code,
                    name=rp.permission.name,
                    description=rp.permission.description,
                    system=rp.permission.system,
                    resource=rp.permission.resource,
                    action=rp.permission.action,
                    created_at=rp.permission.created_at
                ))

        return role

    async def get_by_name(self, name: str) -> Optional[Role]:
        stmt = select(RoleModel).where(RoleModel.name == name).options(
            selectinload(RoleModel.permissions).selectinload(RolePermissionModel.permission)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            return None

        role = Role(
            id=model.id,
            name=model.name,
            description=model.description,
            is_system=model.is_system,
            created_at=model.created_at
        )

        for rp in model.permissions:
            if rp.permission:
                role.add_permission(Permission(
                    id=rp.permission.id,
                    code=rp.permission.code,
                    name=rp.permission.name,
                    description=rp.permission.description,
                    system=rp.permission.system,
                    resource=rp.permission.resource,
                    action=rp.permission.action,
                    created_at=rp.permission.created_at
                ))

        return role

    async def get_all(self):
        return await self.list()

    async def list(self) -> List[Role]:
        stmt = select(RoleModel).options(
            selectinload(RoleModel.permissions).selectinload(RolePermissionModel.permission)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        roles = []
        for model in models:
            role = Role(
                id=model.id,
                name=model.name,
                description=model.description,
                is_system=model.is_system,
                created_at=model.created_at
            )
            for rp in model.permissions:
                if rp.permission:
                    role.add_permission(Permission(
                        id=rp.permission.id,
                        code=rp.permission.code,
                        name=rp.permission.name,
                        description=rp.permission.description,
                        system=rp.permission.system,
                        resource=rp.permission.resource,
                        action=rp.permission.action,
                        created_at=rp.permission.created_at
                    ))
            roles.append(role)

        return roles

    
    async def assign_permission(self, role_id: int, permission_id: int):
        rp = RolePermissionModel(role_id=role_id, permission_id=permission_id)
        self._session.add(rp)
        await self._session.flush()

    async def remove_permission(self, role_id: int, permission_id: int):
        stmt = delete(RolePermissionModel).where(
            RolePermissionModel.role_id == role_id,
            RolePermissionModel.permission_id == permission_id
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def delete(self, role_id: int) -> bool:
        try:
            stmt = delete(RolePermissionModel).where(RolePermissionModel.role_id == role_id)
            await self._session.execute(stmt)
            await self._session.flush()

            stmt = delete(RoleModel).where(RoleModel.id == role_id)
            result = await self._session.execute(stmt)
            return result.rowcount > 0
        except Exception:
            return False

