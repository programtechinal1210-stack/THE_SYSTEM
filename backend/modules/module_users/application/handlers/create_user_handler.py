from modules.module_users.domain.entities.user import User
from modules.module_users.domain.interfaces.i_user_repository import IUserRepository
from modules.module_users.domain.interfaces.i_role_repository import IRoleRepository
from infrastructure.authentication.password_hasher import PasswordHasher
from shared.shared_core import Result
from ..commands.create_user import CreateUserCommand

class CreateUserHandler:
    def __init__(
        self,
        user_repository: IUserRepository,
        role_repository: IRoleRepository,
        password_hasher: PasswordHasher
    ):
        self.user_repository = user_repository
        self.role_repository = role_repository
        self.password_hasher = password_hasher
    
    async def handle(self, command: CreateUserCommand) -> Result[User]:
        # Check if username exists
        if await self.user_repository.exists(command.username):
            return Result.failure(f"Username '{command.username}' already exists")
        
        # Hash password
        password_hash = self.password_hasher.hash(command.password)
        
        # Create user
        user = User(
            username=command.username,
            password_hash=password_hash,
            full_name=command.full_name,
            email=command.email,
            organization_id=command.organization_id,
            phone=command.phone,
            position=command.position,
            is_active=True
        )
        
        # Add roles
        if command.role_names:
            for role_name in command.role_names:
                role = await self.role_repository.get_by_name(role_name)
                if not role:
                    return Result.failure(f"Role '{role_name}' not found")
                user.add_role(role)
        
        # Save user
        try:
            saved_user = await self.user_repository.save(user)
            from sqlalchemy import text
            for role in user.roles:
                await self.user_repository._session.execute(text("INSERT INTO user_roles(user_id,role_id,scope) VALUES(:uid,:rid,'self')"), {"uid": user.id.hex, "rid": role.id})
            return Result.success(await self.user_repository.get_by_id(user.id))
        except Exception as e:
            return Result.failure(f"Failed to create user: {str(e)}")
