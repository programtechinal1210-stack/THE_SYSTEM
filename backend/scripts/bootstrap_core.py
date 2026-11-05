"""Idempotent platform definitions and explicit first-administrator provisioning."""
import argparse
import getpass
import json
import sqlite3
import sys
from uuid import uuid4
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def seed_definitions(db):
    for resource in ("users", "roles", "permissions", "organizations", "settings", "notifications", "audit", "followups", "currency", "recycle"):
        for action in ("view", "manage", "export"):
            code = f"core.{resource}.{action}"
            db.execute("INSERT OR IGNORE INTO permissions(code,name,system,resource,action) VALUES(?,?,?,?,?)",
                       (code, code, "core", resource, action))
    for key, value, kind in [("core.system_name", "THE_SYSTEM", "string"), ("core.language", "ar", "string"),
                             ("core.theme", "light", "string"), ("core.font_size", 16, "integer")]:
        db.execute('INSERT OR IGNORE INTO system_settings(id,key,value,default_value,data_type,is_active,is_encrypted,is_required) VALUES(?,?,?,?,?,1,0,1)',
                   (uuid4().hex, key, json.dumps(value), json.dumps(value), kind))
    db.execute("INSERT OR IGNORE INTO notification_templates(id,type,subject_template,body_template,channel,is_active) VALUES(?,?,?,?,?,1)",
               (uuid4().hex, "core.user.created", "Welcome", "Your account {username} is ready.", "in_app"))
    # Preserve legacy permissions; copy recognized grants to their namespaced counterparts.
    db.execute("INSERT OR IGNORE INTO role_permissions(role_id,permission_id) SELECT rp.role_id,new.id FROM role_permissions rp JOIN permissions old ON old.id=rp.permission_id JOIN permissions new ON new.code='core.' || old.code WHERE old.code NOT LIKE 'core.%'")


def bootstrap(database, username=None, password=None):
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA foreign_keys=ON")
        seed_definitions(db)
        if username:
            if db.execute("SELECT 1 FROM user_roles ur JOIN roles r ON r.id=ur.role_id WHERE r.name='admin'").fetchone():
                raise ValueError("Administrator already provisioned")
            if not password or len(password) < 12:
                raise ValueError("Password must contain at least 12 characters")
            from infrastructure.authentication.password_hasher import PasswordHasher
            oid, uid = uuid4().hex, uuid4().hex
            db.execute("INSERT INTO organizations(id,name,is_active) VALUES(?,?,1)", (oid, "Institution"))
            db.execute("INSERT OR IGNORE INTO roles(name,is_system) VALUES('admin',1)")
            rid = db.execute("SELECT id FROM roles WHERE name='admin'").fetchone()[0]
            db.execute("INSERT INTO users(id,username,password_hash,full_name,email,organization_id,is_active) VALUES(?,?,?,?,?,?,1)",
                (uid, username, PasswordHasher().hash(password), username, username + "@core.local", oid))
            db.execute("INSERT INTO user_roles(user_id,role_id,scope) VALUES(?,?,'institution')", (uid, rid))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("database")
    parser.add_argument("--admin")
    args = parser.parse_args()
    bootstrap(args.database, args.admin, getpass.getpass("New administrator password: ") if args.admin else None)
    print("Core definitions provisioned")
