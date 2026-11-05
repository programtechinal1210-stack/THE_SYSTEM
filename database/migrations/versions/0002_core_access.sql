ALTER TABLE user_roles ADD COLUMN scope VARCHAR(20) NOT NULL DEFAULT 'self' CHECK (scope IN ('self','organization','institution'));
ALTER TABLE notifications ADD COLUMN event_key VARCHAR(200);
CREATE UNIQUE INDEX uq_notification_event_recipient ON notifications(user_id,event_key) WHERE event_key IS NOT NULL;
CREATE INDEX ix_users_organization ON users(organization_id);
CREATE UNIQUE INDEX uq_user_setting_key ON user_settings(user_id,setting_key);
CREATE UNIQUE INDEX uq_user_notification_preference ON user_notification_settings(user_id,notification_type,channel);
