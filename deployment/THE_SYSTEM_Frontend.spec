# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent
frontend = root / "frontend"
sys.path.insert(0, str(frontend))
hidden = []
def runtime_module(name):
    return not any(part in {"tests", "test", "static", "templates"} for part in name.split("."))
for package in ("config", "core", "modules", "shared"):
    hidden += collect_submodules(package, filter=runtime_module)
for package in ("django_htmx", "crispy_forms", "crispy_tailwind", "whitenoise", "waitress"):
    hidden += collect_submodules(package, filter=runtime_module)
datas = []
for name in ("config", "core", "modules", "shared", "templates", "static", "staticfiles"):
    path = frontend / name
    if path.exists():
        datas.append((str(path), name))
a = Analysis(
    [str(root / "deployment" / "frontend_server.py")], pathex=[str(frontend)],
    datas=datas, hiddenimports=hidden, excludes=["pytest", "matplotlib", "scipy"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="THE_SYSTEM_Frontend", console=True, icon=None)
