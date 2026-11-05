# modules/module_users/application/handlers/login_user_handler.py
from modules.module_users.domain.interfaces.i_user_repository import IUserRepository
from infrastructure.authentication.password_hasher import PasswordHasher
from infrastructure.authentication.jwt_handler import JWTHandler
from modules.module_users.infrastructure.repositories.user_session_repository import UserSessionRepository
from shared.shared_core import Result
from core.config import settings
from ..commands.login_user import LoginUserCommand
from fastapi import Request


class LoginUserHandler:
    def __init__(
        self,
        user_repository: IUserRepository,
        password_hasher: PasswordHasher,
        jwt_handler: JWTHandler,
        session_repository: UserSessionRepository = None,
        request: Request = None
    ):
        self.user_repository = user_repository
        self.password_hasher = password_hasher
        self.jwt_handler = jwt_handler
        self.session_repository = session_repository
        self.request = request
    
    async def handle(self, command: LoginUserCommand) -> Result[dict]:
        # Get user by username
        user = await self.user_repository.get_by_username(command.username)
        if not user:
            return Result.failure("Invalid username or password")
        
        # Check if user is active
        if not user.is_active:
            return Result.failure("User account is inactive")
        
        # Verify password
        if not self.password_hasher.verify(command.password, user.password_hash):
            return Result.failure("Invalid username or password")
        
        from modules.module_settings.application.security_policy import configure_tokens
        from modules.module_settings.application.center_service import system_value
        from sqlalchemy import text
        db = self.user_repository._session
        await configure_tokens(db, self.jwt_handler)
        if not await system_value(db, 'core.security.multiple_sessions'):
            await db.execute(text('UPDATE user_sessions SET is_active=0,logout_time=CURRENT_TIMESTAMP WHERE user_id=:uid'), {'uid':user.id.hex})
        # Generate tokens
        access_token = self.jwt_handler.create_access_token({
            "sub": str(user.id),
            "username": user.username,
            "full_name": user.full_name,
            "roles": [role.name for role in user.roles]
        })
        
        refresh_token = self.jwt_handler.create_refresh_token({
            "sub": str(user.id)
        })
        
        # Get client IP and User-Agent
        client_ip = "127.0.0.1"
        user_agent = "Unknown"
        if self.request:
            client_ip = self.request.client.host if self.request.client else "127.0.0.1"
            user_agent = self.request.headers.get("user-agent", "Unknown")
        
        # Save session (if session repository is available)
        if self.session_repository:
            await self.session_repository.create_session(
                user_id=user.id,
                session_token=access_token,
                refresh_token=refresh_token,
                ip_address=client_ip,
                user_agent=user_agent,
                expiry_minutes=self.jwt_handler.access_token_expire_minutes
            )
        
        return Result.success({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "user_id": user.id,
            "username": user.username,
            "full_name": user.full_name
        })
