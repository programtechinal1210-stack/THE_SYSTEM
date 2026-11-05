"""One API writer process per SQLite database; OS releases the lease on exit."""
from pathlib import Path
from sqlalchemy.engine import make_url

def acquire(url):
    parsed=make_url(url)
    if not parsed.drivername.startswith('sqlite'): return None
    db_path = Path(parsed.database)
    # DATABASE_URL may be relative when the process starts from backend/.
    if not db_path.is_absolute():
        db_path = (Path.cwd() / db_path).resolve()
    else:
        db_path = db_path.resolve()
    lock_path = db_path.with_name(db_path.stem + '.api.lock') if db_path.suffix else db_path.with_suffix('.api.lock')
    # 'core.db' -> 'core.api.lock' (with_suffix would also work, with_name is explicit).
    if db_path.suffix == '.db':
        lock_path = db_path.with_suffix('.api.lock')
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle=lock_path.open('a+b')
    except OSError as exc:
        raise RuntimeError(f'Cannot create lock file {lock_path} ({exc}). Stop the other API process, delete the stale lock, or check folder permissions.') from exc
    handle.seek(0)
    try:
        first = handle.read(1)
    except OSError:
        # Windows: another API process holds an LK_NBLCK lock on byte 0,
        # so even reading raises PermissionError before we reach msvcrt.locking.
        handle.close()
        raise RuntimeError('SQLite Core supports one API process per database. Stop the other API process before starting this instance.')
    if not first:
        try:
            handle.write(b'1'); handle.flush()
        except OSError:
            handle.close()
            raise RuntimeError('SQLite Core supports one API process per database. Stop the other API process before starting this instance.')
    handle.seek(0)
    try:
        import os
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise RuntimeError('SQLite Core supports one API process per database. Stop the other API process before starting this instance.')
    return handle
