"""Explicit transactional SQLite migrations; never implicit at startup."""
import argparse
import hashlib
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = Path(os.getenv("THE_SYSTEM_MIGRATIONS_DIR", ROOT / "database/migrations/versions"))


def statements(script):
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            yield buffer
            buffer = ""
    if buffer.strip() and not all(x.strip().startswith("--") for x in buffer.splitlines()):
        raise ValueError("Incomplete migration statement")


def migrate(path, adopt_baseline=False):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        db.execute("CREATE TABLE IF NOT EXISTS core_schema_versions(version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        for file in sorted(VERSIONS.glob("[0-9]*.sql")):
            script = file.read_text(encoding="utf-8-sig")
            checksum = hashlib.sha256(script.encode()).hexdigest()
            old = db.execute("SELECT checksum FROM core_schema_versions WHERE version=?", (file.stem,)).fetchone()
            if old:
                if old[0] != checksum:
                    raise ValueError("Applied migration changed: " + file.name)
                continue
            if file.name == "0055_daily_work_operations.sql":
                db.commit()
                db.execute("PRAGMA foreign_keys=OFF")
                try:
                    db.execute("BEGIN IMMEDIATE")
                    for statement in statements(script):
                        sql = "\n".join(line for line in statement.splitlines() if not line.strip().startswith("--")).strip()
                        if sql.upper() not in {"BEGIN;", "BEGIN TRANSACTION;", "COMMIT;", "PRAGMA FOREIGN_KEYS=OFF;", "PRAGMA FOREIGN_KEYS=ON;"}:
                            db.execute(statement)
                    if db.execute("PRAGMA foreign_key_check").fetchall():
                        raise ValueError("Foreign key violations in migration 0055")
                    db.execute("INSERT INTO core_schema_versions(version,checksum) VALUES (?,?)", (file.stem, checksum))
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.execute("PRAGMA foreign_keys=ON")
                    if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                        raise RuntimeError("Could not re-enable foreign keys after migration 0055")
                continue
            exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='users'").fetchone()
            if file.name.startswith("0001") and exists:
                if not adopt_baseline:
                    raise ValueError("Existing database requires --adopt-baseline after backup")
                with sqlite3.connect(":memory:") as reference:
                    reference.executescript(script)
                    for (table,) in reference.execute("SELECT name FROM sqlite_master WHERE type='table'"):
                        if db.execute(f'PRAGMA table_info("{table}")').fetchall() != reference.execute(f'PRAGMA table_info("{table}")').fetchall():
                            raise ValueError("Baseline mismatch: " + table)
            else:
                for statement in statements(script):
                    sql = "\n".join(line for line in statement.splitlines() if not line.strip().startswith("--")).strip()
                    if sql.upper() not in {"BEGIN;", "BEGIN TRANSACTION;", "COMMIT;", "PRAGMA FOREIGN_KEYS=OFF;", "PRAGMA FOREIGN_KEYS=ON;"}:
                        db.execute(statement)
            db.execute("INSERT INTO core_schema_versions(version,checksum) VALUES (?,?)", (file.stem, checksum))
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("Foreign key violations")
        db.commit()
        db.execute("PRAGMA foreign_keys=ON")
        if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("Foreign keys are not enabled after migrations")
        db.execute("PRAGMA journal_mode=WAL")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--adopt-baseline", action="store_true")
    args = parser.parse_args()
    print(migrate(args.database, args.adopt_baseline))
