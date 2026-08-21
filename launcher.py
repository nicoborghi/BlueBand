"""Blue Band as a program: start the server, open the browser, wait.

`streamlit run app.py` is a command line, and a jury does not have one. This
is what the icon on the desktop starts instead. It does three things and
nothing else:

1. picks a free port, so a second copy - or anything else already on 8501 -
   does not make the app fail to start with a message nobody will read;
2. starts Streamlit **in this process** through `bootstrap.run`, because the
   packaged program has no `streamlit` on any PATH to re-exec;
3. opens the browser at that port once the server answers.

Streamlit is closed by closing this window (or the console it runs from). The
tab is only a view of it: closing the tab leaves the server running, which is
what lets the jury reopen it from the browser history mid-competition.

Run from a checkout this file works too - `python launcher.py` - which is how
the packaged behaviour gets tested without building an installer.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

#: Where the app is, bundled or not. `sys._MEIPASS` is PyInstaller's unpacked
#: tree; in a checkout it is simply this file's folder.
HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))

#: The script Streamlit is asked to run. It is inside the bundle, alongside the
#: packages it imports, so nothing here has to teach Streamlit about the app.
APP = HERE / "app.py"

#: How long to wait for the server before opening the tab anyway. It answers in
#: about a second on a laptop; a tab opened too early shows a connection error
#: the jury then has to reload past.
STARTUP_TIMEOUT = 30.0


def free_port(preferred: int = 8501) -> int:
    """`preferred` when nothing holds it, otherwise whatever the OS gives.

    `BLUEBAND_PORT` pins it: a jury that has bookmarked the address, and the
    build check that has to know where to knock.
    """
    fixed = os.environ.get("BLUEBAND_PORT")
    if fixed and fixed.isdigit():
        return int(fixed)
    for port in (preferred, 0):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
                return probe.getsockname()[1]
            except OSError:
                continue
    return preferred


def answering(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.25)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def open_when_ready(port: int) -> None:
    """Open the browser once the server is up, in a thread of its own."""
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if answering(port):
            break
        time.sleep(0.2)
    webbrowser.open_new_tab(f"http://localhost:{port}")


def options(port: int) -> dict:
    """Streamlit's settings for the packaged app.

    Passed as `flag_options` - what `streamlit run --server.port` fills in -
    and not as `STREAMLIT_*` environment: the environment is *below* the
    defaults Streamlit resolves for a port it finds busy, so a port set that
    way is silently swapped for the next one up and the browser is then opened
    on the wrong one.

    It has to be said here at all because `.streamlit/config.toml` is read from
    the *working directory*, and the working directory of a program started
    from a desktop icon is anybody's guess.
    """
    return {
        "server.port": port,
        "server.address": "localhost",
        # the "Save PDF" link hands the browser a freshly written file out of
        # `static/` (see `ui.download`); without this it is a 404
        "server.enableStaticServing": True,
        # a program, not a development server: no file watcher, no reload on
        # save, no first-run e-mail prompt
        "server.fileWatcherType": "none",
        "server.headless": True,
        "browser.gatherUsageStats": False,
        "global.developmentMode": False,
    }


#: What the bundle has to contain to be a working program, checked by
#: `--check`. Every one of these is loaded through `Path(__file__)` at some
#: point and would otherwise go missing silently.
REQUIRED = ("app.py", "regulations/events.json", "regulations/distances.json",
            "regulations/penalties.json", "render/print.css",
            "render/templates/document.html.j2", "render/templates/page.html.j2",
            "header/track.svg", "header/track_text_ink.svg")

#: Imported by `--check`. `app.py` itself is not: it calls `set_page_config`
#: on import, which needs a running Streamlit. These reach everything it would.
MODULES = ("core.config", "core.entries", "core.store", "core.paths",
           "core.race", "core.medals", "core.decisions", "core.catalogue",
           "render.render", "render.documents", "render.pdf",
           "ui.state", "ui.style", "ui.download",
           "ui.pages.races", "ui.pages.check_in", "ui.pages.decisions",
           "ui.pages.documents", "ui.pages.stats", "ui.pages.programme",
           "ui.pages.settings", "ui.pages.setup")


def check() -> int:
    """Is this bundle whole? Imports every module, finds every data file.

    The failure it is written for: `core` was not in the bundle at all, and the
    program started, served a page and only then died - so a check that the
    server answers says nothing. This one fails at the door, and names what is
    missing.
    """
    import importlib

    sys.path.insert(0, str(HERE))
    missing = [name for name in REQUIRED if not (HERE / name).exists()]
    broken = []
    for name in MODULES:
        try:
            importlib.import_module(name)
        except Exception as exc:                              # noqa: BLE001
            broken.append(f"{name}: {exc}")
    for line in [f"missing file: {name}" for name in missing] + \
                [f"import failed: {line}" for line in broken]:
        print(line, file=sys.stderr)
    if missing or broken:
        return 1
    print(f"ok - {len(MODULES)} modules, {len(REQUIRED)} data files, "
          f"from {HERE}")
    return 0


def main() -> int:
    if "--check" in sys.argv:
        return check()
    if not APP.exists():
        print(f"app.py not found next to the launcher ({APP})", file=sys.stderr)
        return 1
    # the bundle is importable as itself: `import core`, `import ui` and the
    # `Path(__file__).parent.parent` every module resolves its data with
    sys.path.insert(0, str(HERE))

    # Streamlit checks for the served folder at start-up and warns when it is
    # not there. It is created by the first save (`ui.download`), which is
    # after the warning has already gone past the jury.
    (HERE / "static").mkdir(parents=True, exist_ok=True)

    port = free_port()
    flags = options(port)
    threading.Thread(target=open_when_ready, args=(port,), daemon=True).start()

    from streamlit.web import bootstrap

    bootstrap.load_config_options(flag_options=flags)
    bootstrap.run(str(APP), is_hello=False, args=[], flag_options=flags)
    return 0


if __name__ == "__main__":
    sys.exit(main())
