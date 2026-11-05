from ...domain.entities.user import User
from ..models.user_model import UserModel
from ...domain.entities.role import Role

class UserMapper:
    @staticmethod
    def to_model(entity: User) -> UserModel:
        return UserModel(
            id=entity.id,
            username=entity.username,
            password_hash=entity.password_hash,
            full_name=entity.full_name,
            email=entity.email,
            phone=entity.phone,
            organization_id=entity.organization_id,
            position=entity.position,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at
        )
    
    @staticmethod
    def to_entity(model: UserModel) -> User:
        entity = User(
            id=model.id,
            username=model.username,
            password_hash=model.password_hash,
            full_name=model.full_name,
            email=model.email,
            phone=model.phone,
            organization_id=model.organization_id,
            position=model.position,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at
        )
        # تحميل الأدوار من العلاقة
        for user_role in model.roles:
            if user_role.role:
                entity.add_role(Role(
                    id=user_role.role.id,
                    name=user_role.role.name,
                    description=user_role.role.description,
                    is_system=user_role.role.is_system,
                    created_at=user_role.role.created_at
                    # تم إزالة updated_at
                ))
        return entity
