from fastapi import HTTPException
from .center_service import system_value

async def validate_password(session,password):
    minimum=await system_value(session,'core.security.password_length')
    if len(password)<minimum: raise HTTPException(422,f'كلمة المرور يجب أن تحتوي على {minimum} حرفًا على الأقل')
    if len(password)>128: raise HTTPException(422,'كلمة المرور تتجاوز الحد الأقصى (128 حرفًا)')
    from infrastructure.authentication.leaked_passwords import contains_banned
    banned = contains_banned(password)
    if banned: raise HTTPException(422,'كلمة المرور شائعة ومسربة؛ اختر كلمة مختلفة تمامًا')
    if await system_value(session,'core.security.password_complexity'):
        if not (any(c.isupper() for c in password) and any(c.islower() for c in password) and any(c.isdigit() for c in password) and any(not c.isalnum() for c in password)):
            raise HTTPException(422,'كلمة المرور تحتاج حروفًا كبيرة وصغيرة وأرقامًا ورموزًا')

async def configure_tokens(session,jwt):
    jwt.access_token_expire_minutes=await system_value(session,'core.security.session_minutes')
    jwt.refresh_token_expire_days=await system_value(session,'core.security.refresh_days')
