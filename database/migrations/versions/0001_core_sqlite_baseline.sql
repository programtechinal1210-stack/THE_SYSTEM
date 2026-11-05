-- THE_SYSTEM Core SQLite Baseline 0001
-- Generated from certified data/core.db
-- Reusable institutional Core only; no GOMS business tables.
PRAGMA foreign_keys=ON;
BEGIN TRANSACTION;

-- TABLE: activity_stream
CREATE TABLE activity_stream (
	id CHAR(32) NOT NULL, 
	source_type VARCHAR(50) NOT NULL, 
	source_id CHAR(32), 
	actor_id CHAR(32), 
	actor_name VARCHAR(200), 
	verb VARCHAR(50) NOT NULL, 
	object_type VARCHAR(100), 
	object_id CHAR(32), 
	object_name VARCHAR(500), 
	description_ar TEXT, 
	description_en TEXT, 
	metadata JSON, 
	target_url VARCHAR(500), 
	app_version VARCHAR(20), 
	device_type VARCHAR(50), 
	location_info JSON, 
	session_id VARCHAR(100), 
	importance_score INTEGER, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_id) REFERENCES users (id)
);

-- TABLE: audit_alerts
CREATE TABLE audit_alerts (
	id CHAR(32) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	module VARCHAR(100), 
	action_type VARCHAR(50), 
	entity_type VARCHAR(100), 
	severity_threshold VARCHAR(20), 
	conditions JSON, 
	cooldown_minutes INTEGER, 
	notify_users JSON, 
	notify_roles JSON, 
	notify_channels JSON, 
	is_active BOOLEAN, 
	last_triggered_at DATETIME, 
	trigger_count INTEGER, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	created_by CHAR(32), 
	updated_by CHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);

-- TABLE: audit_anomalies
CREATE TABLE audit_anomalies (
	id CHAR(32) NOT NULL, 
	anomaly_type_id CHAR(32) NOT NULL, 
	anomaly_type_code VARCHAR(50), 
	title VARCHAR(300) NOT NULL, 
	description TEXT, 
	severity VARCHAR(20), 
	related_audit_ids JSON, 
	related_user_id CHAR(32), 
	related_ip VARCHAR(50), 
	evidence JSON, 
	detection_rule_matched JSON, 
	resolution_status VARCHAR(20), 
	detected_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	detected_by_rule VARCHAR(100), 
	resolved_at DATETIME, 
	resolved_by CHAR(32), 
	resolution_notes TEXT, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(anomaly_type_id) REFERENCES audit_anomaly_types (id), 
	FOREIGN KEY(related_user_id) REFERENCES users (id), 
	FOREIGN KEY(resolved_by) REFERENCES users (id)
);

-- TABLE: audit_anomaly_types
CREATE TABLE audit_anomaly_types (
	id CHAR(32) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name_ar VARCHAR(200) NOT NULL, 
	name_en VARCHAR(200), 
	description TEXT, 
	default_severity VARCHAR(20), 
	detection_rule JSON NOT NULL, 
	auto_notify BOOLEAN, 
	auto_block BOOLEAN, 
	auto_create_followup BOOLEAN, 
	notify_roles JSON, 
	notify_channels JSON, 
	is_active BOOLEAN, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

-- TABLE: audit_cleanup_logs
CREATE TABLE audit_cleanup_logs (
	id CHAR(32) NOT NULL, 
	policy_id CHAR(32), 
	entity_type VARCHAR(100) NOT NULL, 
	date_range_start DATETIME, 
	date_range_end DATETIME, 
	records_archived INTEGER, 
	records_deleted INTEGER, 
	records_skipped INTEGER, 
	started_at DATETIME, 
	completed_at DATETIME, 
	duration_seconds INTEGER, 
	status VARCHAR(20), 
	error_message TEXT, 
	executed_by VARCHAR(50), 
	archive_path TEXT, 
	archive_size_bytes BIGINT, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(policy_id) REFERENCES audit_retention_policies (id)
);

-- TABLE: audit_configurations
CREATE TABLE audit_configurations (
	id CHAR(32) NOT NULL, 
	module VARCHAR(100) NOT NULL, 
	entity_type VARCHAR(100), 
	audit_create BOOLEAN, 
	audit_update BOOLEAN, 
	audit_delete BOOLEAN, 
	audit_view BOOLEAN, 
	audit_export BOOLEAN, 
	audit_login BOOLEAN, 
	detail_level VARCHAR(20), 
	monitored_fields JSON, 
	retention_days INTEGER, 
	notify_on_critical BOOLEAN, 
	notify_on_warning BOOLEAN, 
	is_active BOOLEAN, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	created_by CHAR(32), 
	updated_by CHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);

-- TABLE: audit_exports
CREATE TABLE audit_exports (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	export_type VARCHAR(50) NOT NULL, 
	export_name VARCHAR(200), 
	entity_type VARCHAR(100), 
	date_range_start DATETIME, 
	date_range_end DATETIME, 
	filters_applied JSON, 
	record_count INTEGER, 
	file_size_bytes BIGINT, 
	file_path TEXT, 
	file_hash VARCHAR(64), 
	status VARCHAR(20), 
	error_message TEXT, 
	ip_address VARCHAR(50), 
	user_agent TEXT, 
	is_downloaded BOOLEAN, 
	download_count INTEGER, 
	started_at DATETIME, 
	completed_at DATETIME, 
	duration_seconds INTEGER, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

-- TABLE: audit_logs
CREATE TABLE audit_logs (
	id BIGINT NOT NULL, 
	user_id CHAR(32), 
	action VARCHAR(100) NOT NULL, 
	entity_type VARCHAR(100) NOT NULL, 
	entity_id CHAR(32), 
	module VARCHAR(100), 
	action_type VARCHAR(50), 
	old_value JSON, 
	new_value JSON, 
	changes_summary TEXT, 
	changes_summary_en TEXT, 
	ip_address VARCHAR(50), 
	user_agent TEXT, 
	session_id VARCHAR(100), 
	severity VARCHAR(20), 
	related_entity_type VARCHAR(50), 
	related_entity_id CHAR(32), 
	metadata JSON, 
	duration_ms INTEGER, 
	status_code INTEGER, 
	auth_method VARCHAR(50), 
	token_id CHAR(32), 
	is_system_action BOOLEAN, 
	impersonated_by CHAR(32), 
	mfa_verified BOOLEAN, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(impersonated_by) REFERENCES users (id)
);

-- TABLE: audit_reports
CREATE TABLE audit_reports (
	id CHAR(32) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	report_type VARCHAR(50) NOT NULL, 
	filters JSON, 
	date_range_start DATETIME, 
	date_range_end DATETIME, 
	modules JSON, 
	result_data JSON, 
	summary_ar TEXT, 
	summary_en TEXT, 
	key_findings JSON, 
	charts JSON, 
	status VARCHAR(50), 
	created_by CHAR(32), 
	recipients JSON, 
	is_scheduled BOOLEAN, 
	schedule_cron VARCHAR(50), 
	schedule_next_run DATETIME, 
	is_sent BOOLEAN, 
	sent_at DATETIME, 
	generated_at DATETIME, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

-- TABLE: audit_retention_policies
CREATE TABLE audit_retention_policies (
	id CHAR(32) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	entity_type VARCHAR(100) NOT NULL, 
	module VARCHAR(100), 
	retention_days INTEGER NOT NULL, 
	archive_before_delete BOOLEAN, 
	archive_retention_days INTEGER, 
	cleanup_schedule VARCHAR(50), 
	cleanup_hour INTEGER, 
	custom_conditions JSON, 
	exclude_critical BOOLEAN, 
	exclude_with_followups BOOLEAN, 
	is_active BOOLEAN, 
	last_cleanup_at DATETIME, 
	last_cleanup_records INTEGER, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	created_by CHAR(32), 
	updated_by CHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);

-- TABLE: entities
CREATE TABLE entities (
	id CHAR(32) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	code VARCHAR(50), 
	entity_type_id CHAR(32) NOT NULL, 
	contact_person VARCHAR(100), 
	phone VARCHAR(20), 
	email VARCHAR(255), 
	address TEXT, 
	parent_id CHAR(32), 
	is_active BOOLEAN, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	FOREIGN KEY(entity_type_id) REFERENCES entity_types (id), 
	FOREIGN KEY(parent_id) REFERENCES entities (id)
);

-- TABLE: entity_types
CREATE TABLE entity_types (
	id CHAR(32) NOT NULL, 
	code VARCHAR(30) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description TEXT, 
	is_active BOOLEAN, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

-- TABLE: execution_history
CREATE TABLE execution_history (
	id CHAR(32) NOT NULL, 
	entity_type VARCHAR(50) NOT NULL, 
	entity_id CHAR(32) NOT NULL, 
	action VARCHAR(50) NOT NULL, 
	user_id CHAR(32), 
	old_data JSON, 
	new_data JSON, 
	notes TEXT, 
	execution_type VARCHAR(50), 
	duration_seconds INTEGER, 
	is_delayed BOOLEAN, 
	delay_reason TEXT, 
	location_info JSON, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

-- TABLE: follow_ups
CREATE TABLE follow_ups (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	entity_type VARCHAR(100), 
	entity_id CHAR(32), 
	notes TEXT, 
	status_before VARCHAR(50), 
	status_after VARCHAR(50), 
	progress_percentage INTEGER, 
	followup_type VARCHAR(50), 
	due_date DATETIME, 
	resolution TEXT, 
	resolved_by CHAR(32), 
	resolved_at DATETIME, 
	is_escalated BOOLEAN, 
	escalated_to CHAR(32), 
	escalated_at DATETIME, 
	category VARCHAR(50), 
	tags JSON, 
	reminder_sent_at DATETIME, 
	reminder_count INTEGER, 
	snooze_until DATETIME, 
	auto_resolve BOOLEAN, 
	priority_score INTEGER, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(resolved_by) REFERENCES users (id), 
	FOREIGN KEY(escalated_to) REFERENCES users (id)
);

-- TABLE: followup_categories
CREATE TABLE followup_categories (
	id CHAR(32) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name_ar VARCHAR(100) NOT NULL, 
	name_en VARCHAR(100), 
	description TEXT, 
	icon VARCHAR(50), 
	color VARCHAR(20), 
	default_priority VARCHAR(20), 
	default_due_days INTEGER, 
	auto_escalate BOOLEAN, 
	escalate_after_days INTEGER, 
	priority INTEGER, 
	is_active BOOLEAN, 
	is_system BOOLEAN, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

-- TABLE: followup_templates
CREATE TABLE followup_templates (
	id CHAR(32) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	category_id CHAR(32), 
	default_title VARCHAR(300), 
	default_notes TEXT, 
	default_priority VARCHAR(20), 
	default_due_days INTEGER, 
	default_tags JSON, 
	auto_escalate BOOLEAN, 
	escalate_after_days INTEGER, 
	escalate_to_role_id INTEGER, 
	send_reminders BOOLEAN, 
	reminder_interval_hours INTEGER, 
	max_reminders INTEGER, 
	is_active BOOLEAN, 
	is_system BOOLEAN, 
	created_by CHAR(32), 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(category_id) REFERENCES followup_categories (id), 
	FOREIGN KEY(escalate_to_role_id) REFERENCES roles (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

-- TABLE: notification_channels
CREATE TABLE notification_channels (
	id CHAR(32) NOT NULL, 
	code VARCHAR(30) NOT NULL, 
	name_ar VARCHAR(50) NOT NULL, 
	name_en VARCHAR(50) NOT NULL, 
	is_active BOOLEAN, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

-- TABLE: notification_templates
CREATE TABLE notification_templates (
	id CHAR(32) NOT NULL, 
	type VARCHAR(50) NOT NULL, 
	subject_template TEXT, 
	body_template TEXT NOT NULL, 
	channel VARCHAR(30), 
	is_active BOOLEAN, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (type)
);

-- TABLE: notifications
CREATE TABLE notifications (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	content TEXT NOT NULL, 
	type VARCHAR(50) NOT NULL, 
	link VARCHAR(500), 
	entity_type VARCHAR(50), 
	entity_id CHAR(32), 
	is_read BOOLEAN, 
	read_at DATETIME, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- TABLE: organizations
CREATE TABLE organizations (
	id CHAR(32) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	parent_id CHAR(32), 
	is_active BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(parent_id) REFERENCES organizations (id)
);

-- TABLE: permissions
CREATE TABLE permissions (
	id INTEGER NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	description VARCHAR(255), 
	system VARCHAR(50) NOT NULL, 
	resource VARCHAR(50) NOT NULL, 
	action VARCHAR(30) NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);

-- TABLE: role_permissions
CREATE TABLE role_permissions (
	id INTEGER NOT NULL, 
	role_id INTEGER NOT NULL, 
	permission_id INTEGER NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_role_permissions UNIQUE (role_id, permission_id), 
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
	FOREIGN KEY(permission_id) REFERENCES permissions (id)
);

-- TABLE: roles
CREATE TABLE roles (
	id INTEGER NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	description VARCHAR(255), 
	is_system BOOLEAN DEFAULT 'false' NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);

-- TABLE: settings_audit_log
CREATE TABLE settings_audit_log (
	id CHAR(32) NOT NULL, 
	setting_key VARCHAR(100) NOT NULL, 
	old_value JSON, 
	new_value JSON, 
	changed_by CHAR(32), 
	changed_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(changed_by) REFERENCES users (id)
);

-- TABLE: settings_categories
CREATE TABLE settings_categories (
	id CHAR(32) NOT NULL, 
	code VARCHAR(50) NOT NULL, 
	name_ar VARCHAR(100) NOT NULL, 
	name_en VARCHAR(100) NOT NULL, 
	icon VARCHAR(50), 
	priority INTEGER, 
	is_active BOOLEAN, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (code)
);

-- TABLE: system_settings
CREATE TABLE system_settings (
	id CHAR(32) NOT NULL, 
	"key" VARCHAR(100) NOT NULL, 
	category_id CHAR(32), 
	value JSON NOT NULL, 
	default_value JSON, 
	data_type VARCHAR(20), 
	description_ar TEXT, 
	description_en TEXT, 
	is_encrypted BOOLEAN, 
	is_required BOOLEAN, 
	is_active BOOLEAN, 
	validation_rules JSON, 
	options JSON, 
	created_by CHAR(32), 
	updated_by CHAR(32), 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE ("key"), 
	FOREIGN KEY(category_id) REFERENCES settings_categories (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(updated_by) REFERENCES users (id)
);

-- TABLE: user_notification_settings
CREATE TABLE user_notification_settings (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	notification_type VARCHAR(50) NOT NULL, 
	channel VARCHAR(30) NOT NULL, 
	is_enabled BOOLEAN, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- TABLE: user_roles
CREATE TABLE user_roles (
	id INTEGER NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	role_id INTEGER NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_user_roles UNIQUE (user_id, role_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE
);

-- TABLE: user_sessions
CREATE TABLE user_sessions (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	session_token VARCHAR(500) NOT NULL, 
	refresh_token VARCHAR(500) NOT NULL, 
	ip_address VARCHAR(45) NOT NULL, 
	user_agent VARCHAR(255), 
	login_time DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	expiry_time DATETIME NOT NULL, 
	last_activity DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	logout_time DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- TABLE: user_settings
CREATE TABLE user_settings (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	setting_key VARCHAR(100) NOT NULL, 
	value JSON NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- TABLE: users
CREATE TABLE users (
	id CHAR(32) NOT NULL, 
	username VARCHAR(50) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	full_name VARCHAR(200) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	phone VARCHAR(20), 
	organization_id CHAR(32) NOT NULL, 
	position VARCHAR(100), 
	is_active BOOLEAN DEFAULT 'true' NOT NULL, 
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

-- INDEX: ix_activity_stream_created_at
CREATE INDEX ix_activity_stream_created_at ON activity_stream (created_at);

-- INDEX: ix_audit_logs_action
CREATE INDEX ix_audit_logs_action ON audit_logs (action);

-- INDEX: ix_audit_logs_created_at
CREATE INDEX ix_audit_logs_created_at ON audit_logs (created_at);

-- INDEX: ix_audit_logs_entity_type
CREATE INDEX ix_audit_logs_entity_type ON audit_logs (entity_type);

-- INDEX: ix_audit_logs_module
CREATE INDEX ix_audit_logs_module ON audit_logs (module);

-- INDEX: ix_audit_logs_severity
CREATE INDEX ix_audit_logs_severity ON audit_logs (severity);

-- INDEX: ix_audit_logs_user_id
CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

-- INDEX: ix_execution_history_created_at
CREATE INDEX ix_execution_history_created_at ON execution_history (created_at);

-- INDEX: ix_execution_history_entity_type
CREATE INDEX ix_execution_history_entity_type ON execution_history (entity_type);

-- INDEX: ix_follow_ups_entity_id
CREATE INDEX ix_follow_ups_entity_id ON follow_ups (entity_id);

-- INDEX: ix_follow_ups_entity_type
CREATE INDEX ix_follow_ups_entity_type ON follow_ups (entity_type);

-- INDEX: ix_follow_ups_user_id
CREATE INDEX ix_follow_ups_user_id ON follow_ups (user_id);

-- INDEX: ix_notifications_is_read
CREATE INDEX ix_notifications_is_read ON notifications (is_read);

-- INDEX: ix_notifications_type
CREATE INDEX ix_notifications_type ON notifications (type);

-- INDEX: ix_notifications_user_id
CREATE INDEX ix_notifications_user_id ON notifications (user_id);

-- INDEX: ix_permissions_code
CREATE UNIQUE INDEX ix_permissions_code ON permissions (code);

-- INDEX: ix_roles_name
CREATE UNIQUE INDEX ix_roles_name ON roles (name);

-- INDEX: ix_user_sessions_refresh_token
CREATE UNIQUE INDEX ix_user_sessions_refresh_token ON user_sessions (refresh_token);

-- INDEX: ix_user_sessions_session_token
CREATE UNIQUE INDEX ix_user_sessions_session_token ON user_sessions (session_token);

-- INDEX: ix_users_email
CREATE UNIQUE INDEX ix_users_email ON users (email);

-- INDEX: ix_users_username
CREATE UNIQUE INDEX ix_users_username ON users (username);

COMMIT;
