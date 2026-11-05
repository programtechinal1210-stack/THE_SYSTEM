from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select
from typing import Optional, List
from uuid import UUID

from modules.module_users.infrastructure.models.user_model import UserModel
from modules.module_users.infrastructure.models.user_role_model import UserRoleModel
from modules.module_users.domain.entities.user import User
from modules.module_users.infrastructure.mappers.user_mapper import UserMapper


class UserRepositorySync:

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        try:
            stmt = (
                select(UserModel)
                .where(UserModel.id == user_id)
                .options(
                    joinedload(UserModel.roles).joinedload(UserRoleModel.role)
                )
            )
            result = self.session.execute(stmt)
            model = result.unique().scalar_one_or_none()
            
            if model:
                return UserMapper.to_entity(model)
            return None
                
        except Exception as e:
            print(f"UserRepositorySync error: {str(e)}")
            return None

    def get_by_username(self, username: str) -> Optional[User]:
        stmt = (
            select(UserModel)
            .where(UserModel.username == username)
            .options(
                joinedload(UserModel.roles).joinedload(UserRoleModel.role)
            )
        )
        result = self.session.execute(stmt)
        model = result.unique().scalar_one_or_none()
        return UserMapper.to_entity(model) if model else None

    def get_all(self, skip: int = 0, limit: int = 100) -> List[User]:
        stmt = (
            select(UserModel)
            .offset(skip)
            .limit(limit)
            .options(
                joinedload(UserModel.roles).joinedload(UserRoleModel.role)
            )
        )
        result = self.session.execute(stmt)
        models = result.unique().scalars().all()
        return [UserMapper.to_entity(model) for model in models]

    def save(self, user: User) -> User:
        model = UserMapper.to_model(user)
        merged = self.session.merge(model)
        self.session.flush()
        return UserMapper.to_entity(merged)

    def delete(self, user_id: UUID, soft: bool = True) -> bool:
        model = self.session.get(UserModel, user_id)
        if not model:
            return False
        if soft:
            model.is_active = False
        else:
            self.session.delete(model)
        self.session.flush()
        return True
