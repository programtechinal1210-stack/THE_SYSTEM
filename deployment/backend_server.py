"""Packaged FastAPI entry point with explicit, backed-up migrations."""
import os
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path


def source_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def prepare_imports():
    sys.path.insert(0, str(source_root()))


def database_path():
    from sqlalchemy.engine import make_url
    from core.config import settings
    return Path(make_url(settings.DATABASE_URL).database).resolve()


def backup_database(path):
    if not path.exists() or path.stat().st_size == 0:
        return None
    backup_root = Path(os.environ["THE_SYSTEM_DATA_ROOT"]) / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    target = backup_root / f"core-before-migration-{datetime.now():%Y%m%d-%H%M%S}.db"
    shutil.copy2(path, target)
    return target


def migrate_and_seed():
    from scripts.migrate_core import migrate
    from scripts.bootstrap_core import bootstrap
    path = database_path()
    backup = backup_database(path)
    try:
        migrate(path)
        bootstrap(path)
    except Exception:
        if backup:
            shutil.copy2(backup, path)
        raise


def main():
    prepare_imports()
    os.environ.setdefault("THE_SYSTEM_MIGRATIONS_DIR", str(source_root() / "database" / "migrations" / "versions"))
    migrate_and_seed()
    from api.main import app
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("BACKEND_PORT", "8001")), log_level="info")


if __name__ == "__main__":
    log_root = Path(os.getenv("THE_SYSTEM_DATA_ROOT", ".")) / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    with (log_root / "backend-startup.log").open("a", encoding="utf-8") as log:
        log.write(f"\n[{datetime.now().astimezone().isoformat()}] starting\n")
        try:
            main()
        except BaseException:
            traceback.print_exc(file=log)
            raise
