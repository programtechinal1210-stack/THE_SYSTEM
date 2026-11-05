from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from ...domain.entities.permission import Permission
from ..models.permission_model import PermissionModel
from ..models.role_permission_model import RolePermissionModel

class PermissionRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, permission: Permission) -> Permission:
        perm_model = PermissionModel(
            id=permission.id,
            code=permission.code,
            name=permission.name,
            description=permission.description,
            system=permission.system,
            resource=permission.resource,
            action=permission.action
        )

        if permission.id:
            await self._session.merge(perm_model)
        else:
            self._session.add(perm_model)

        await self._session.flush()

        return Permission(
            id=perm_model.id,
            code=perm_model.code,
            name=perm_model.name,
            description=perm_model.description,
            system=perm_model.system,
            resource=perm_model.resource,
            action=perm_model.action,
            created_at=perm_model.created_at
        )

    async def get_by_id(self, perm_id: int) -> Optional[Permission]:
        stmt = select(PermissionModel).where(PermissionModel.id == perm_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return Permission(
            id=model.id,
            code=model.code,
            name=model.name,
            description=model.description,
            system=model.system,
            resource=model.resource,
            action=model.action,
            created_at=model.created_at
        )

    async def get_by_code(self, code: str) -> Optional[Permission]:
        stmt = select(PermissionModel).where(PermissionModel.code == code)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if not model:
            return None
        return Permission(
            id=model.id,
            code=model.code,
            name=model.name,
            description=model.description,
            system=model.system,
            resource=model.resource,
            action=model.action,
            created_at=model.created_at
        )

    async def get_all(self):
        return await self.list()

    async def list(self) -> List[Permission]:
        stmt = select(PermissionModel)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [
            Permission(
                id=m.id,
                code=m.code,
                name=m.name,
                description=m.description,
                system=m.system,
                resource=m.resource,
                action=m.action,
                created_at=m.created_at
            )
            for m in models
        ]

    async def delete(self, perm_id: int) -> bool:
        # حذف الروابط من role_permissions أولاً
        stmt_rp = delete(RolePermissionModel).where(RolePermissionModel.permission_id == perm_id)
        await self._session.execute(stmt_rp)
        await self._session.flush()
        
        # ثم حذف الصلاحية
        stmt = delete(PermissionModel).where(PermissionModel.id == perm_id)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0
