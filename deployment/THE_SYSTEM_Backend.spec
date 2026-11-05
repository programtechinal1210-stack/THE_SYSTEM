# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent
backend = root / "backend"
sys.path.insert(0, str(backend))
hidden = []
def runtime_module(name):
    return not any(part in {"tests", "test", "static", "templates"} for part in name.split("."))
for package in ("api", "core", "infrastructure", "modules", "shared"):
    hidden += collect_submodules(package, filter=runtime_module)
hidden += ["scripts.migrate_core", "scripts.bootstrap_core", "aiosqlite"]
a = Analysis(
    [str(root / "deployment" / "backend_server.py")], pathex=[str(backend)],
    datas=[(str(root / "database" / "migrations" / "versions"), "database/migrations/versions")],
    hiddenimports=hidden, excludes=["pytest", "matplotlib", "scipy"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="THE_SYSTEM_Backend", console=True, icon=None)
