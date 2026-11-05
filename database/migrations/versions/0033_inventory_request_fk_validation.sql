-- SQLite retains a deferred violation counter after a referenced parent table
-- is rebuilt and renamed, even when all final foreign keys resolve correctly.
-- Validate EVERY actual FK before returning deferred checking to immediate mode.
-- foreign_keys stays ON throughout; a real violation aborts this transaction.
CREATE TEMP TABLE inv_request_fk_validation_guard (
 violation_count INTEGER NOT NULL CHECK(violation_count=0)
);
INSERT INTO inv_request_fk_validation_guard(violation_count)
 SELECT count(*) FROM pragma_foreign_key_check;
DROP TABLE inv_request_fk_validation_guard;
PRAGMA defer_foreign_keys=OFF;
