"""SQLite operational actions. Backup paths are server-owned, never supplied by clients."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy.engine import make_url
from core.config import settings
from scripts.backup_core import backup

def database_path():
    url=make_url(settings.DATABASE_URL)
    if not url.drivername.startswith('sqlite'): raise ValueError('هذه العملية خاصة بـ SQLite')
    return Path(url.database).resolve()

def backup_root():
    root=database_path().parent/'settings-backups'
    root.mkdir(parents=True,exist_ok=True)
    return root

def backups():
    return [{'id':p.stem,'name':p.name,'size':p.stat().st_size,
             'created_at':datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat()}
            for p in sorted(backup_root().glob('snapshot-*.db'),key=lambda p:p.stat().st_mtime,reverse=True)]

def snapshot(keep=10):
    name='snapshot-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8]
    result=backup(database_path(),backup_root()/(name+'.db'))
    for item in (backups()[keep:] if keep is not None else []):
        (backup_root()/item['name']).unlink()
    return {'id':name,'size':result.stat().st_size,'scope':'قاعدة النواة فقط؛ الملفات وقاعدة جلسات Django غير مشمولة'}

def inspect_database():
    path=database_path()
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        integrity=db.execute('PRAGMA integrity_check').fetchall()
        foreign=db.execute('PRAGMA foreign_key_check').fetchall()
    return {'name':path.name,'size':path.stat().st_size,'integrity_ok':integrity==[('ok',)],
            'foreign_key_violations':len(foreign),'checked_at':datetime.now(timezone.utc).isoformat()}

def restore(snapshot_id,actor_id,actor_name,request_id):
    import re
    if not re.fullmatch(r'snapshot-[0-9]{8}T[0-9]{6}-[a-f0-9]{8}',snapshot_id): raise ValueError('نسخة غير صالحة')
    source=backup_root()/(snapshot_id+'.db')
    if not source.is_file(): raise ValueError('النسخة غير موجودة')
    with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src:
        if src.execute('PRAGMA integrity_check').fetchall()!=[('ok',)] or src.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('فشل التحقق من سلامة النسخة')
        with sqlite3.connect(database_path()) as current:
            if src.execute('SELECT version,checksum FROM core_schema_versions ORDER BY version').fetchall()!=current.execute('SELECT version,checksum FROM core_schema_versions ORDER BY version').fetchall():
                raise ValueError('إصدار النسخة لا يطابق مخطط النظام')
        rescue=snapshot(None)
        with sqlite3.connect(database_path(),timeout=30) as target:
            src.backup(target)
            target.execute('UPDATE user_sessions SET is_active=0,logout_time=CURRENT_TIMESTAMP')
            # Ensure the administrator can sign in after restoring a maintenance snapshot.
            target.execute("UPDATE system_settings SET value='false' WHERE key='core.maintenance'")
    record={'restored':snapshot_id,'rescue':rescue['id'],'at':datetime.now(timezone.utc).isoformat(),'actor_id':actor_id,'actor_name':actor_name,'request_id':request_id}
    (backup_root()/('restore-'+uuid4().hex+'.json')).write_text(json.dumps(record),encoding='utf-8')
    with sqlite3.connect(database_path()) as db:
        db.execute("INSERT INTO settings_operations(id,kind,status,summary,actor_id,completed_at,result) VALUES(?,'restore','completed','Database restored',?,CURRENT_TIMESTAMP,?)",(uuid4().hex,actor_id,json.dumps(record)))
    return record
