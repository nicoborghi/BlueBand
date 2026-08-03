"""Shared 'save as PDF' control for the printable pages.

The document is written straight into the configured output folder - the point
is that it *is* saved, on Drive or on a stick, not that the browser downloads a
second copy somewhere in ~/Downloads.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import quote

import streamlit as st

from core.config import Competition
from core.i18n import msg, ui
from core.store import Store
from render import pdf as _pdf
from render.render import archive
from ui import notify

# Streamlit serves this directory at /app/static (see .streamlit/config.toml).
# A copy of the last few PDFs lives here only so the toast can offer a link the
# browser will actually follow: a file:// URL is refused by Chrome, and the
# output folder is usually on Drive, outside anything the app serves.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "recenti"
KEEP = 20  # copies kept before the oldest are dropped


def save_button(store: Store, docs, comp: Competition, *, number: str = "",
                signature: bool = False, key: str = "dl",
                label: str = "", container=None) -> Path | None:
    """Render the document into the output folder.

    Falls back to the self-contained HTML when no Chromium is installed, so
    the jury always gets a file.

    `container` is where the button goes. Everything the save produces - the
    frame that opens the tab above all - is written outside it: an element
    added under the button inside a bottom-aligned column moved the button up
    the moment it was pressed.
    """
    box = container if container is not None else st
    if not _pdf.available():
        box.caption(msg("chromium_missing"))
    if not box.button(label or ui("save_pdf"), key=f"btn_{key}"):
        return None

    # no spinner: it pushed the page down while Chromium started and the tab
    # opens by itself the moment the file is there
    path = archive(store, docs, comp, number=number, signature=signature)
    # Streamlit collapses a toast behind a "view more" past ~100 characters of
    # *source*, so nothing but the file name goes in there.
    st.toast(msg("saved_as", name=_short(path.name)),
             icon=notify.ICON_SAVE)
    open_in_new_tab(browser_link(path), path.name)
    return path


def open_in_new_tab(link: str, name: str = "") -> None:
    """Open the comunicato that was just saved, without a button to press.

    The jury saves a sheet to read it: one click should be enough. Rendered
    only in the run where the save happened, so a later rerun does not reopen
    an old document.

    A tab opened from script and not from the click itself can be stopped by
    the browser's popup blocker; when that happens the frame grows into the
    link it could not follow, so the document is never out of reach.
    """
    if not link:
        return
    open_label = msg("open_document", name=name)
    st.components.v1.html(f"""
        <script>
        const url = {link!r};
        if (!window.open(url, "_blank")) {{
            document.body.innerHTML =
                '<a href="' + url + '" target="_blank" '
                + 'style="font:400 14px system-ui;color:#1e6fd9">'
                + '{open_label}</a>';
            if (window.frameElement) window.frameElement.style.height = "28px";
        }}
        </script>""", height=0)


# Streamlit's own limit is 104 characters on the raw message; stay under it
# once the "Salvato ..." wording of `MSG["saved_as"]` is added.
_TOAST_CHARS = 90


def _short(name: str) -> str:
    """`name` clipped so the toast stays on one line, keeping the extension."""
    if len(name) <= _TOAST_CHARS:
        return name
    stem, _, suffix = name.rpartition(".")
    return f"{stem[:_TOAST_CHARS - len(suffix) - 2]}….{suffix}"


def browser_link(path: Path) -> str:
    """URL that opens `path` in a browser tab, or '' when it cannot.

    Only PDFs: Streamlit serves any other extension as text/plain, which would
    show a comunicato as HTML source. Failure is never fatal - the file is
    already saved where it belongs, the link is a convenience.
    """
    if path.suffix.lower() != ".pdf":
        return ""
    try:
        STATIC_DIR.mkdir(parents=True, exist_ok=True)
        copy = STATIC_DIR / path.name
        shutil.copyfile(path, copy)
        old = sorted(STATIC_DIR.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
        for stale in old[:-KEEP]:
            stale.unlink(missing_ok=True)
    except OSError:
        return ""
    # cache-busting: the same comunicato re-saved must not open the old copy
    return f"/app/static/{STATIC_DIR.name}/{quote(copy.name)}?v={int(copy.stat().st_mtime)}"
