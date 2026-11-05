ALTER TABLE hr_field_tasks
ADD COLUMN state_reason TEXT NOT NULL DEFAULT '';

ALTER TABLE hr_workforce_requests
ADD COLUMN decision_note TEXT NOT NULL DEFAULT '';

ALTER TABLE hr_attendance
ADD COLUMN recorded_by_user_id CHAR(32) REFERENCES users(id);

ALTER TABLE hr_attendance
ADD COLUMN decision_note TEXT NOT NULL DEFAULT '';
