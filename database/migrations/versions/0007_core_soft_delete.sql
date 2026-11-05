-- 0007 Soft-delete contract: shared recycle bin keyed to User UUID.
CREATE TABLE recycle_bin (
    id CHAR(32) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id CHAR(32) NOT NULL,
    deleted_by CHAR(32) NOT NULL,
    deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reason TEXT,
    metadata TEXT,
    restored_at TEXT,
    restored_by CHAR(32),
    PRIMARY KEY (id),
    FOREIGN KEY (deleted_by) REFERENCES users (id),
    FOREIGN KEY (restored_by) REFERENCES users (id)
);
CREATE UNIQUE INDEX uq_recycle_entity ON recycle_bin (entity_type, entity_id) WHERE restored_at IS NULL;
CREATE INDEX ix_recycle_entity_type ON recycle_bin (entity_type, deleted_at);
CREATE INDEX ix_recycle_deleted_by ON recycle_bin (deleted_by);
