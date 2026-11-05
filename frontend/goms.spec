# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# جمع بيانات Django
django_datas = collect_data_files('django')

# المجلدات التي سيتم تضمينها
datas = [
    ('modules', 'modules'),
    ('shared', 'shared'),
    ('data', 'data'),
    ('config', 'config'),
    ('templates', 'templates'),
    ('staticfiles', 'staticfiles'),
    ('static', 'static'),
    ('media', 'media'),
    ('core', 'core'),
    ('locale_backup', 'locale_backup'),
    ('db.sqlite3', 'db.sqlite3'),
] + django_datas

# الوحدات المخفية
hiddenimports = [
    'django',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_htmx',
    'crispy_forms',
    'crispy_tailwind',
    'waitress',
    'core',
    'modules.module_auth',
    'modules.module_users',
    'modules.module_notifications',
    'modules.module_organizations',
]

# إضافة الوحدات الفرعية لكل وحدة
for module in hiddenimports[:]:
    try:
        hiddenimports.extend(collect_submodules(module))
    except:
        pass

a = Analysis(
    ['entry.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyd = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyd,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GOMS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codepage_utf8=False,
    icon=None,
)
