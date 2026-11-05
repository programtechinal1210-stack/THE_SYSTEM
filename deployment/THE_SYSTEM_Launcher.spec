# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis([str(root / "launcher.py")], pathex=[str(root)], hiddenimports=[], datas=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="THE_SYSTEM", console=False, icon=None)
