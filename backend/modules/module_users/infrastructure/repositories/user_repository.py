from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload, selectinload
from ...domain.interfaces.i_user_repository import IUserRepository
from ...domain.entities.user import User
from ..models.user_model import UserModel
from ..models.user_role_model import UserRoleModel
from ..mappers.user_mapper import UserMapper

class UserRepository(IUserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def save(self, user: User) -> User:
        user_model = UserMapper.to_model(user)
        
        if user.id:
            await self._session.merge(user_model)
        else:
            self._session.add(user_model)
        
        await self._session.flush()
        
        stmt = select(UserModel).where(UserModel.id == user_model.id).options(
            joinedload(UserModel.roles).joinedload(UserRoleModel.role)
        )
        result = await self._session.execute(stmt)
        saved_model = result.unique().scalar_one()
        
        return UserMapper.to_entity(saved_model)
    
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        stmt = select(UserModel).where(UserModel.id == user_id).options(
            joinedload(UserModel.roles).joinedload(UserRoleModel.role)
        )
        result = await self._session.execute(stmt)
        model = result.unique().scalar_one_or_none()
        return UserMapper.to_entity(model) if model else None
    
    async def get_by_username(self, username: str) -> Optional[User]:
        stmt = select(UserModel).where(UserModel.username == username).options(
            joinedload(UserModel.roles).joinedload(UserRoleModel.role)
        )
        result = await self._session.execute(stmt)
        model = result.unique().scalar_one_or_none()
        return UserMapper.to_entity(model) if model else None
    
    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(UserModel).where(UserModel.email == email).options(
            joinedload(UserModel.roles).joinedload(UserRoleModel.role)
        )
        result = await self._session.execute(stmt)
        model = result.unique().scalar_one_or_none()
        return UserMapper.to_entity(model) if model else None
    
    async def list(self, skip: int = 0, limit: int = 100) -> List[User]:
        stmt = select(UserModel).offset(skip).limit(limit).options(
            joinedload(UserModel.roles).joinedload(UserRoleModel.role)
        )
        result = await self._session.execute(stmt)
        models = result.unique().scalars().all()
        return [UserMapper.to_entity(model) for model in models]
    
    async def delete(self, user_id: UUID) -> bool:
        stmt = delete(UserModel).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0
    
    async def exists(self, username: str) -> bool:
        stmt = select(UserModel.id).where(UserModel.username == username)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None
