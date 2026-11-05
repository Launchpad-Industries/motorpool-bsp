# BSP Card Generator
# Copyright (C) 2026 William Becker
# Licensed under the GNU General Public License v3 or later. See LICENSE.
#
# PyInstaller spec for the tester build of Motor Pool. Build with
# `python tools/build.py`, not by calling PyInstaller directly: that script
# builds in a clean virtual environment and checks the result for secrets.
#
# One-folder build (MotorPool.exe + _internal\): starts in about a second.
# A one-file exe would unpack ~40 MB to a temp folder on every launch.
# Only the files listed in `datas` are bundled; nothing else from the repo,
# your home folder or ~/.motorpool can end up in the build.

from PyInstaller.utils.hooks import collect_submodules

SNAP = "snapshot"

datas = [
    ("bsp/web", "bsp/web"),
    (f"{SNAP}/mm-data", "mm-data"),
    (f"{SNAP}/cache", "cache"),
    (f"{SNAP}/data", "data"),
    (f"{SNAP}/official.tsv", "."),
    (f"{SNAP}/bsp-options.tsv", "."),
    (f"{SNAP}/fonts/fonts.css", "fonts"),
    (f"{SNAP}/snapshot.json", "."),
]

# Development-only modules and heavy libraries the app doesn't use.
LEFT_OUT = {"bsp.sheet", "bsp.setup_data", "bsp.report"}
excludes = ["playwright", "numpy", "scipy", "matplotlib", "pandas", "tkinter",
            "IPython", "pytest", "PIL.ImageQt", *LEFT_OUT]

a = Analysis(
    ["motorpool.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=[m for m in collect_submodules("bsp") if m not in LEFT_OUT],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MotorPool",
    console=True,          # the console window is the "close to quit" switch
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="MotorPool", upx=False)
