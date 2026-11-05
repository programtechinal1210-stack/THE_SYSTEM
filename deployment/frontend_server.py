"""Packaged Django service entry point."""
import os
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path


def source_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def backup_database(path):
    if not path.exists() or path.stat().st_size == 0:
        return None
    backup_root = Path(os.environ["THE_SYSTEM_DATA_ROOT"]) / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    target = backup_root / f"frontend-before-migration-{datetime.now():%Y%m%d-%H%M%S}.db"
    shutil.copy2(path, target)
    return target


def main():
    sys.path.insert(0, str(source_root()))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    database = Path(settings.DATABASES["default"]["NAME"]).resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    backup = backup_database(database)
    try:
        call_command("migrate", interactive=False, verbosity=0)
    except Exception:
        if backup:
            shutil.copy2(backup, database)
        raise
    from config.wsgi import application
    from waitress import serve
    serve(application, host="127.0.0.1", port=int(os.getenv("FRONTEND_PORT", "8000")), threads=8)


if __name__ == "__main__":
    log_root = Path(os.getenv("THE_SYSTEM_DATA_ROOT", ".")) / "logs"
    log_root.mkdir(parents=True, exist_ok=True)
    with (log_root / "frontend-startup.log").open("a", encoding="utf-8") as log:
        log.write(f"\n[{datetime.now().astimezone().isoformat()}] starting\n")
        try:
            main()
        except BaseException:
            traceback.print_exc(file=log)
            raise
