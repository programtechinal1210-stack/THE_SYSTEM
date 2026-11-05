-- 0004 Security hardening: MFA, hashed refresh tokens, key rotation, alerts, leaked-password screening.
-- Adds columns/tables only; never alters existing data.
ALTER TABLE users ADD COLUMN mfa_secret TEXT;
ALTER TABLE users ADD COLUMN mfa_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE user_sessions ADD COLUMN refresh_token_hash TEXT;
ALTER TABLE user_sessions ADD COLUMN mfa_verified INTEGER NOT NULL DEFAULT 0;
ALTER TABLE user_sessions ADD COLUMN token_kid TEXT;
CREATE TABLE jwt_keys (kid TEXT PRIMARY KEY, secret TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, retired_at TEXT);
CREATE TABLE security_events (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, kind TEXT NOT NULL, ip_address TEXT NOT NULL DEFAULT '', user_agent TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX ix_security_events_user ON security_events(user_id, created_at);
CREATE TABLE rate_limits (bucket TEXT PRIMARY KEY, tokens REAL NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
-- Backfill SHA-256 fingerprints for pre-existing sessions (Python fills NULLs on next login too).
UPDATE user_sessions SET refresh_token_hash=lower(hex(randomblob(32))) WHERE refresh_token_hash IS NULL;
INSERT OR IGNORE INTO notification_templates(id,type,subject_template,body_template,channel,is_active) VALUES
(lower(hex(randomblob(16))),'core.security.new_login','دخول جديد إلى حسابك','تم تسجيل دخول إلى حساب {username} من {ip_address}. إن لم تكن أنت فغيّر كلمتك فورًا.','in_app',1),
(lower(hex(randomblob(16))),'core.security.mfa_enabled','تم تفعيل التحقق بخطوتين','تم تفعيل التحقق بخطوتين لحساب {username}.','in_app',1),
(lower(hex(randomblob(16))),'core.security.password_changed','تم تغيير كلمة المرور','تم تغيير كلمة مرور حساب {username}. أُنهيت كل الجلسات الأخرى.','in_app',1);
