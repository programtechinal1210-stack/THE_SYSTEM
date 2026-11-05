"""Explicit repair for the verified 0004 schema-without-ledger incident.

Not part of startup or the migration runner. Default is read-only inspection.
Apply only to an offline database, with a new backup destination.
"""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from scripts.migrate_core import VERSIONS, statements

HASHES = {
    '0001_core_sqlite_baseline': '182b3db96e7f69d7cc9a39ee85c40446d7c52e3428e893863d67afae3a1df67c',
    '0002_core_access': '2586c9f7a957e6b73f0660d58070a2c70fa2327a8b6412e93ab0b9920e6dfc8c',
    '0003_settings_center': '60a0a4beec76e7a0e0855253293d07e88b982dd248e8f0ea8fc7a2344972742f',
    '0004_auth_hardening': 'a376585e5aa7624292ac39bb85447d453ebd31506d71283aa0820b0cd8013b61',
}
VERSION = '0004_auth_hardening'
TYPES = ('core.security.new_login', 'core.security.mfa_enabled', 'core.security.password_changed')


def schema(db):
    """Compare SQL tokens (including literals), ignoring layout and object order."""
    return [(kind, name, re.findall(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|\w+|[^\s]", sql or ''))
            for kind, name, sql in db.execute(
                "SELECT type,name,sql FROM sqlite_master WHERE name NOT IN "
                "('core_schema_versions','sqlite_autoindex_core_schema_versions_1') ORDER BY type,name")]


def inspect(db):
    scripts = {}
    with closing(sqlite3.connect(':memory:')) as reference:
        for version, expected in HASHES.items():
            script = (VERSIONS / (version + '.sql')).read_text(encoding='utf-8-sig')
            if hashlib.sha256(script.encode()).hexdigest() != expected:
                raise ValueError('Unexpected migration source: ' + version)
            scripts[version] = script
            reference.executescript(script)
        if schema(db) != schema(reference):
            raise ValueError('Database schema does not exactly match 0001 through 0004')
    recorded = dict(db.execute('SELECT version,checksum FROM core_schema_versions'))
    for version in list(HASHES)[:3]:
        if recorded.get(version) != HASHES[version]:
            raise ValueError('Unexpected migration history: ' + version)
    if set(recorded) - set(HASHES):
        raise ValueError('Later or unknown migrations: use the normal migration workflow')
    if VERSION in recorded and recorded[VERSION] != HASHES[VERSION]:
        raise ValueError('0004 checksum mismatch')
    missing = db.execute('SELECT count(*) FROM user_sessions WHERE refresh_token_hash IS NULL').fetchone()[0]
    templates = {name: db.execute('SELECT count(*) FROM notification_templates WHERE type=?', (name,)).fetchone()[0]
                 for name in TYPES}
    if any(n > 1 for n in templates.values()):
        raise ValueError('Duplicate security templates require separate reconciliation')
    if VERSION in recorded and (missing or not all(templates.values())):
        raise ValueError('Recorded 0004 has missing data effects; outside this repair contract')
    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('Database integrity failure')
    return {'recorded': VERSION in recorded, 'null_session_hashes': missing,
            'missing_templates': [name for name, n in templates.items() if not n]}, scripts[VERSION]


def reconcile(path, backup=None):
    path = Path(path).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        result, _ = inspect(db)
        if backup is None:
            return dict(result, applied=False)
        backup = Path(backup).resolve()
        if backup == path or backup.exists():
            raise ValueError('A new, separate backup destination is required')
        backup.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(backup)) as saved:
            db.backup(saved)
            if saved.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Backup integrity failure')
    with closing(sqlite3.connect(path)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        try:
            result, script = inspect(db)
            if not result['recorded']:
                # Execute only the original migration's data statements. No new
                # refresh algorithm, no resetting non-null session fingerprints.
                for statement in statements(script):
                    sql = '\n'.join(line for line in statement.splitlines() if not line.strip().startswith('--')).strip()
                    if sql.startswith(('UPDATE user_sessions ', 'INSERT OR IGNORE INTO notification_templates')):
                        db.execute(sql)
                db.execute('INSERT INTO core_schema_versions(version,checksum) VALUES (?,?)',
                           (VERSION, HASHES[VERSION]))
            inspect(db)
            db.commit()
        except Exception:
            db.rollback()
            raise
    return dict(result, applied=not result['recorded'], backup=str(backup))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('--backup', type=Path, help='Apply transactionally after verified backup; omit for inspection')
    args = parser.parse_args()
    print(json.dumps(reconcile(args.database, args.backup), indent=2))
