from uuid import UUID
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from fastapi import HTTPException
from modules.module_notifications.infrastructure.models.notification_model import NotificationModel
from modules.module_notifications.infrastructure.models.notification_template_model import NotificationTemplateModel
from modules.module_settings.infrastructure.models.user_notification_setting_model import UserNotificationSettingModel


class NotificationService:
    def __init__(self, session):
        self.session = session

    async def emit(self, code, recipient, variables, event_key, entity_type=None, entity_id=None):
        from modules.module_settings.application.center_service import system_value
        if not await system_value(self.session, 'core.notifications.enabled'):
            return None
        template = await self.session.scalar(select(NotificationTemplateModel).where(
            NotificationTemplateModel.type == code, NotificationTemplateModel.is_active.is_(True),
            NotificationTemplateModel.channel == "in_app"))
        if not template:
            raise HTTPException(422, "Unknown in-app notification template")
        preference = await self.session.scalar(select(UserNotificationSettingModel).where(
            UserNotificationSettingModel.user_id == recipient, UserNotificationSettingModel.notification_type == code,
            UserNotificationSettingModel.channel == "in_app"))
        if preference is not None and not preference.is_enabled:
            return None
        try:
            title = (template.subject_template or code).format_map(variables)
            content = template.body_template.format_map(variables)
        except (KeyError, ValueError, AttributeError):
            raise HTTPException(422, "Missing or invalid template variables")
        stmt = insert(NotificationModel).values(user_id=recipient, type=code, title=title,
            content=content, event_key=event_key, entity_type=entity_type, entity_id=entity_id)
        await self.session.execute(stmt.on_conflict_do_nothing())
        return await self.session.scalar(select(NotificationModel).where(
            NotificationModel.user_id == recipient, NotificationModel.event_key == event_key))
