-- PM completion review, acceptance and close-out. All execution values remain read-only.
CREATE TABLE pm_completion_cases (
 id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
 project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
 entity_type TEXT NOT NULL CHECK(entity_type IN ('project','activity')),
 entity_id CHAR(32) NOT NULL CHECK(length(entity_id)=32),
 status TEXT NOT NULL CHECK(status IN ('in_review','ready_for_acceptance','accepted','requires_treatment','closed')),
 version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 CHECK(entity_type!='project' OR status='closed'),
 UNIQUE(id,project_id),
 UNIQUE(project_id,entity_type,entity_id)
);
CREATE INDEX ix_pm_completion_cases_project ON pm_completion_cases(project_id,status,entity_type);

CREATE TABLE pm_completion_events (
 id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
 project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
 case_id CHAR(32) NOT NULL,
 action TEXT NOT NULL,
 from_status TEXT,
 to_status TEXT,
 actor_user_id CHAR(32) NOT NULL REFERENCES users(id),
 notes TEXT NOT NULL DEFAULT '',
 metadata TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL,
 FOREIGN KEY(case_id,project_id) REFERENCES pm_completion_cases(id,project_id),
 UNIQUE(id,project_id,case_id)
);
CREATE INDEX ix_pm_completion_events_case ON pm_completion_events(project_id,case_id,created_at,id);
CREATE TRIGGER pm_completion_events_no_update
BEFORE UPDATE ON pm_completion_events
BEGIN
 SELECT RAISE(ABORT,'completion events are immutable');
END;
CREATE TRIGGER pm_completion_events_no_delete
BEFORE DELETE ON pm_completion_events
BEGIN
 SELECT RAISE(ABORT,'completion events are immutable');
END;

CREATE TABLE pm_completion_issues (
 id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
 project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
 case_id CHAR(32) NOT NULL,
 description TEXT NOT NULL,
 issue_type TEXT NOT NULL,
 severity TEXT NOT NULL CHECK(severity IN ('critical','high','medium','low')),
 blocking INTEGER NOT NULL DEFAULT 1 CHECK(blocking IN (0,1)),
 owner_user_id CHAR(32) REFERENCES users(id),
 target_date TEXT,
 status TEXT NOT NULL CHECK(status IN ('open','in_progress','resolved','verified')),
 resolution_notes TEXT NOT NULL DEFAULT '',
 created_by CHAR(32) NOT NULL REFERENCES users(id),
 verified_by CHAR(32) REFERENCES users(id),
 verified_at TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 FOREIGN KEY(case_id,project_id) REFERENCES pm_completion_cases(id,project_id),
 UNIQUE(id,project_id,case_id)
);
CREATE INDEX ix_pm_completion_issues_case ON pm_completion_issues(project_id,case_id,status,blocking);

CREATE TABLE pm_completion_attachments (
 id CHAR(32) PRIMARY KEY CHECK(length(id)=32),
 project_id CHAR(32) NOT NULL REFERENCES pm_projects(id),
 case_id CHAR(32) NOT NULL,
 issue_id CHAR(32),
 category TEXT NOT NULL CHECK(category IN ('review_evidence','receipt_minutes','closeout_document','issue_evidence')),
 filename TEXT NOT NULL,
 content_type TEXT NOT NULL,
 size INTEGER NOT NULL CHECK(size>0 AND size<=5242880),
 sha256 TEXT NOT NULL,
 content BLOB NOT NULL,
 created_by CHAR(32) NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL,
 FOREIGN KEY(case_id,project_id) REFERENCES pm_completion_cases(id,project_id),
 FOREIGN KEY(issue_id,project_id,case_id) REFERENCES pm_completion_issues(id,project_id,case_id)
);
CREATE INDEX ix_pm_completion_attachments_case ON pm_completion_attachments(project_id,case_id,created_at);
CREATE INDEX ix_pm_completion_attachments_issue ON pm_completion_attachments(issue_id,category);
