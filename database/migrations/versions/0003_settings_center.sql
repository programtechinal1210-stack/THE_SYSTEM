CREATE TABLE settings_scope_versions (scope_type TEXT NOT NULL, scope_id TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(scope_type,scope_id));
CREATE TABLE setting_overrides (setting_key TEXT NOT NULL, scope_type TEXT NOT NULL, scope_id TEXT NOT NULL, value TEXT NOT NULL, updated_by TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(setting_key,scope_type,scope_id));
CREATE TABLE settings_changes (id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id TEXT NOT NULL, setting_key TEXT NOT NULL, scope_type TEXT NOT NULL, scope_id TEXT NOT NULL, old_value TEXT, new_value TEXT, actor_id TEXT NOT NULL, actor_name TEXT NOT NULL, request_id TEXT, reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX ix_settings_changes_time ON settings_changes(created_at);
CREATE TABLE settings_operations (id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL, summary TEXT NOT NULL, actor_id TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, completed_at TEXT, result TEXT);
CREATE TABLE login_attempts (identity TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT);
INSERT OR IGNORE INTO permissions(code,name,system,resource,action) VALUES
('core.settings.security.manage','إدارة إعدادات الأمان','core','settings.security','manage'),
('core.settings.modules.manage','إدارة الوحدات','core','settings.modules','manage'),
('core.settings.backup.manage','إدارة النسخ الاحتياطي','core','settings.backup','manage'),
('core.settings.audit.view','عرض تغييرات الإعدادات','core','settings.audit','view'),
('core.settings.advanced.manage','إدارة الإعدادات المتقدمة','core','settings.advanced','manage');
