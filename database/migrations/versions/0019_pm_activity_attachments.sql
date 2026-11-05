-- Small protected attachments stored transactionally with the application database.
CREATE TABLE pm_activity_attachments (
 id CHAR(32) PRIMARY KEY,
 project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
 activity_id CHAR(32) NOT NULL,
 filename TEXT NOT NULL,
 content_type TEXT NOT NULL,
 size INTEGER NOT NULL CHECK(size>0 AND size<=5242880),
 sha256 TEXT NOT NULL,
 content BLOB NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL,
 FOREIGN KEY(activity_id,project_id) REFERENCES pm_activities(id,project_id) ON DELETE CASCADE
);
CREATE INDEX ix_pm_attachments_activity ON pm_activity_attachments(project_id,activity_id);
