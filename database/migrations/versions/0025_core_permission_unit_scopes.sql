CREATE TABLE role_permission_unit_scopes (
    role_permission_id INTEGER NOT NULL,
    unit_id CHAR(32) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (role_permission_id, unit_id),
    FOREIGN KEY (role_permission_id) REFERENCES role_permissions(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES organizations(id) ON DELETE RESTRICT
);

CREATE INDEX ix_role_permission_unit_scopes_unit
    ON role_permission_unit_scopes(unit_id, role_permission_id);
