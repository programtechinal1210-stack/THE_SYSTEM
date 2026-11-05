# infrastructure/database/repositories/user_session_repository.py
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete


from modules.module_users.infrastructure.models.user_session_model import UserSessionModel
class UserSessionRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_session(
        self,
        user_id: UUID,
        session_token: str,
        refresh_token: str,
        ip_address: str,
        user_agent: Optional[str] = None,
        expiry_minutes: int = 60,
        mfa_verified: bool = False,
        token_kid: str = "legacy",
    ) -> UserSessionModel:
        from infrastructure.authentication.jwt_handler import JWTHandler
        expiry_time = datetime.utcnow() + timedelta(minutes=expiry_minutes)

        session = UserSessionModel(
            user_id=user_id,
            session_token=session_token,
            refresh_token=refresh_token,
            refresh_token_hash=JWTHandler.token_fingerprint(refresh_token),
            ip_address=ip_address,
            user_agent=user_agent,
            expiry_time=expiry_time,
            mfa_verified=mfa_verified,
            token_kid=token_kid,
            is_active=True
        )

        self.session.add(session)
        await self.session.flush()
        return session

    async def get_session_by_token(self, session_token: str) -> Optional[UserSessionModel]:
        stmt = select(UserSessionModel).where(
            UserSessionModel.session_token == session_token,
            UserSessionModel.is_active == True,
            UserSessionModel.expiry_time > datetime.utcnow()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_session_by_refresh_token(self, refresh_token: str) -> Optional[UserSessionModel]:
        stmt = select(UserSessionModel).where(
            UserSessionModel.refresh_token == refresh_token,
            UserSessionModel.is_active == True
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_session(self, session_token: str) -> bool:
        stmt = update(UserSessionModel).where(
            UserSessionModel.session_token == session_token
        ).values(is_active=False, logout_time=datetime.utcnow())
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def revoke_all_user_sessions(self, user_id: UUID) -> int:
        stmt = update(UserSessionModel).where(
            UserSessionModel.user_id == user_id,
            UserSessionModel.is_active == True
        ).values(is_active=False, logout_time=datetime.utcnow())
        result = await self.session.execute(stmt)
        return result.rowcount
