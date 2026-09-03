# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for the Windows build.

    pyinstaller packaging/blueband.spec --noconfirm

Three things make a Streamlit app awkward to freeze, and each has one answer
here:

* **Streamlit reads its own version at runtime**, out of the installed
  distribution's metadata, and dies without it. `copy_metadata` puts the
  `.dist-info` of streamlit and of everything that does the same into the
  bundle.
* **Its frontend is data, not code**: `streamlit/static/` is the whole compiled
  React app, and `streamlit/runtime/` carries `.proto` and JSON beside the
  modules. `collect_data_files` takes them wholesale.
* **The app resolves its own files relative to `__file__`**
  (`core.catalogue`, `render.render`, `app.py`), so the regulations, the
  templates, the stylesheet and the wordmark are placed at the *same relative
  paths inside the bundle* as they have in the repository. Nothing in the app
  had to learn about `sys._MEIPASS` except `core.paths`.

`onedir`, not `onefile`: a one-file build unpacks 100 MB to a temporary folder
on every start, which is four seconds and a Defender scan each time the jury
opens the console. The folder is what the installer installs.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import (collect_data_files, collect_submodules,
                                     copy_metadata)

ROOT = Path(SPECPATH).parent          # noqa: F821 - PyInstaller injects these

# `collect_submodules` imports the package to walk it, and it walks whatever
# `sys.path` says - which, for the `pyinstaller` console script, does not
# include the directory the spec is being run from. Without this it finds no
# `core` at all, returns an empty list *with only a warning*, and the bundle
# builds clean and then dies on `No module named 'core'` at the first page.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── what the app carries with it ────────────────────────────────────────────
#
# Same relative layout as the repository: `regulations/events.json` is read as
# `Path(core/catalogue.py).parent.parent / "regulations"`, and inside the
# bundle that resolves to the root of the unpacked tree.
datas = [
    (str(ROOT / "app.py"), "."),
    (str(ROOT / "regulations"), "regulations"),
    (str(ROOT / "render" / "templates"), "render/templates"),
    (str(ROOT / "render" / "print.css"), "render"),
    # the wordmark and the icon: data inside a *code* package, so
    # `collect_submodules("ui")` below does not reach them
    (str(ROOT / "ui" / "track.svg"), "ui"),
    (str(ROOT / "ui" / "track_text_ink.svg"), "ui"),
]

# Streamlit's frontend and the metadata it reads its own version from. The
# metadata list is not decoration: each of these packages looks itself up at
# import, and a missing `.dist-info` is an ImportError at start-up, not a
# warning at build time.
datas += collect_data_files("streamlit", include_py_files=False)
for package in ("streamlit", "pandas", "numpy", "pyarrow", "altair", "pydeck",
                "jinja2", "openpyxl", "xlrd", "pyyaml", "pillow",
                "tornado", "click", "gitpython", "packaging", "protobuf",
                "watchdog", "narwhals", "tenacity", "toml", "typing_extensions"):
    try:
        datas += copy_metadata(package)
    except Exception:                 # noqa: BLE001 - an optional one is fine
        pass

# ── what it must not carry ──────────────────────────────────────────────────
#
# pandas, numpy and pyarrow are *not* on this list and that is a decision, not
# an oversight: they are three quarters of the installed size and they are what
# `st.dataframe` and `st.data_editor` are made of. Doing without them meant
# hand-writing the tables and the grids, and the result was worse to use than
# the widgets - so the size is paid on purpose (see `docs/reference/build.md`).
#
# What is excluded is only what a *scientific* working environment drags along
# and no jury laptop needs. Build in a clean virtual environment anyway: this
# list is a safety net, not a guarantee.
excludes = [
    "matplotlib", "scipy", "IPython", "notebook", "pytest", "sphinx",
    "tkinter", "PyQt5", "PyQt6", "PySide6", "astropy", "sklearn",
]

hiddenimports = [
    # Streamlit finds its own commands and elements by walking packages, which
    # PyInstaller's static analysis does not follow
    "streamlit.runtime.scriptrunner.magic_funcs",
    "streamlit.web.cli",
    # the entry list readers are imported inside the functions that use them,
    # so nothing at module level points at them - and `xlrd` is reached only
    # through pandas, by name, when the file is a legacy `.xls`
    "openpyxl", "xlrd",
    # `st.dataframe` and `st.data_editor` import pyarrow inside the call
    "pyarrow",
]

# **The app itself.** The analysis starts at `launcher.py`, which imports
# Streamlit and hands it `app.py` as a *path* - so nothing in the graph ever
# reaches `core`, `ui` or `render`, and a bundle built without this line starts
# and then dies on `No module named 'core'` at the first page. They are
# collected whole rather than named one by one: the pages are reached through
# a dict in `app.py` (`PAGES`) and the formats through `core.race`, neither of
# which is an import a static analysis can follow either.
for package in ("core", "ui", "render"):
    hiddenimports += collect_submodules(package)

# **numpy, whole.** PyInstaller's own hook collects the top of numpy and leaves
# parts of `numpy._core` out of the archive, and the bundle then fails at
# `import pandas` with "No module named 'numpy._core._exceptions'" - reported
# as a broken numpy installation, which it is not. pandas and pyarrow reach
# into their own submodules the same way (by name, at runtime), so all three
# are collected whole rather than trusted to static analysis.
for package in ("numpy", "pandas", "pyarrow"):
    hiddenimports += collect_submodules(package)

a = Analysis(                          # noqa: F821
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)                      # noqa: F821

exe = EXE(                             # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BlueBand",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX is off on purpose: it saves perhaps 15 MB and it is the single most
    # reliable way to have a fresh installer flagged by Defender SmartScreen,
    # which on a jury laptop the morning of a championship is not a trade.
    upx=False,
    # The console window stays: it is the only thing the jury can close to stop
    # the server. Hidden, the program keeps running after the browser tab is
    # shut and the next start finds its port taken - with nothing on screen to
    # explain why.
    console=True,
    icon=str(ROOT / "packaging" / "blueband.ico"),
)

coll = COLLECT(                        # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="BlueBand",
)
