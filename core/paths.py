"""Where things are, when the app is a program rather than a checkout.

Run from the repository - `streamlit run app.py` - everything the app needs is
next to the code, and every path in this file answers with the repository. That
is the arrangement the whole codebase grew up with and none of it changes.

Installed from the Windows installer it is two different places, and conflating
them is how a jury loses a championship:

* **what the program is** - the regulations, the templates, the stylesheet, the
  letterhead. Read-only, replaced wholesale by the next version, and under
  PyInstaller it lives in the bundle (`sys._MEIPASS`). `bundle()`.
* **what the jury made** - the competitions, the results, the comunicati. It
  must outlive an uninstall, be findable without a file manager and be easy to
  copy to a stick at the end of the day, so it goes in the user's Documents and
  never inside the installation. `data()`.

`COMMISSAIRE_TRACK_DATA` still overrides the second one, as it always has.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: What the jury's folder is called, under Documents.
APP_DIR_NAME = "BlueBand"


def frozen() -> bool:
    """True when running from the PyInstaller bundle, not from a checkout."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def bundle() -> Path:
    """The read-only tree: regulations, templates, print.css, the wordmark."""
    if frozen():
        return Path(sys._MEIPASS)                             # noqa: SLF001
    return Path(__file__).resolve().parent.parent


def documents() -> Path:
    """The user's Documents folder, or their home when there is no such thing.

    Read from the shell rather than assumed to be `~/Documents`: a Windows
    with OneDrive on has moved it, and writing a championship to a folder the
    jury cannot find in Esplora risorse is the same as losing it.
    """
    if os.name == "nt":
        try:
            import ctypes.wintypes

            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            # CSIDL_PERSONAL = 5, SHGFP_TYPE_CURRENT = 0
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
                return Path(buf.value)
        except Exception:                                     # noqa: BLE001
            pass
    home = Path.home()
    return home / "Documents" if (home / "Documents").is_dir() else home


def data() -> Path:
    """Where the jury's work lives - the parent of `competitions/`.

    The environment wins, then the installation's own folder in Documents,
    then - in a checkout - the repository, which is where the competitions
    have always been.
    """
    env = os.environ.get("COMMISSAIRE_TRACK_DATA_ROOT")
    if env:
        return Path(env)
    if frozen():
        return documents() / APP_DIR_NAME
    return Path(__file__).resolve().parent.parent


def served() -> Path:
    """The directory Streamlit serves at `/app/static`.

    Streamlit takes it from the folder of the script it was given, so it is the
    bundle's - which is why the installer puts the program somewhere the user
    can write (a per-user install, not Program Files): the copies of the last
    saved PDFs are written here so the browser has a URL it will follow, and a
    read-only installation would break the "Apri il PDF" link and nothing else.
    """
    return bundle() / "static"
