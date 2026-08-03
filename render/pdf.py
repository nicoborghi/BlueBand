"""Render a comunicato straight to PDF.

Uses a headless Chromium — the same engine the jury would print with by hand,
so the PDF is exactly what Ctrl-P produces, minus the browser's own date/URL
header. No extra Python dependency: if no Chromium is installed the caller
falls back to saving the HTML.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from core.i18n import msg

CANDIDATES = ["chromium", "chromium-browser", "google-chrome",
              "google-chrome-stable", "chrome", "msedge"]

TIMEOUT = 120


class PdfError(RuntimeError):
    """Chromium is missing or failed to produce the file."""


def browser() -> str | None:
    """Path of a usable Chromium/Chrome binary, or None."""
    for name in CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    return None


def available() -> bool:
    return browser() is not None


def profile_dirs() -> list[Path]:
    """Where Chromium may keep the throwaway profile of one run, best first.

    Not next to the document: the comunicati folder is usually a Drive or a
    Windows share, and a filesystem without symlinks cannot hold the
    `SingletonLock` Chromium creates before it opens anything - the run dies
    there and the sheet comes out as HTML. The profile is a scratch directory,
    so it belongs on a local disk whatever the output folder is.

    A snap Chromium is confined on top of that: it cannot see /tmp at all and
    is denied the hidden directories of $HOME, but `~/snap/<name>/current` is
    its own writable home. That is tried first when the binary is a snap.
    """
    out: list[Path] = []
    env = os.environ.get("BLUEBAND_BROWSER_PROFILE_DIR")
    if env:
        out.append(Path(env))
    # `chromium-browser` on Ubuntu is a shell shim in front of the snap, so the
    # path of the binary does not always say it is one: the snap home is tried
    # whenever it is there, whichever name was found
    for name in ("chromium", "chromium-browser", "chrome"):
        home = Path.home() / "snap" / name / "current"
        if home.is_dir():
            out.append(home / ".blueband")
    out.append(Path(tempfile.gettempdir()))
    out.append(Path.home() / ".cache" / "blueband")
    return out


def page_count(data: bytes) -> int:
    """How many sheets a PDF Chromium just produced takes. 1 if unreadable.

    Chromium writes an uncompressed page tree, so the /Count of the root Pages
    node is there in plain sight - no PDF library for one integer.
    """
    counts = [int(n) for n in re.findall(rb"/Count\s+(\d+)", data)]
    return max(counts) if counts else 1


def html_to_pdf(html: str, *, workdir: str | Path | None = None) -> bytes:
    """Convert a standalone HTML page to PDF bytes.

    `workdir` should be a directory the browser can read: a snap-confined
    Chromium cannot open files under /tmp, so pass a path inside the competition
    folder when one is available.
    """
    exe = browser()
    if exe is None:
        raise PdfError(msg("pdf_no_browser"))

    base = Path(workdir) if workdir else Path(tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".pdf-", dir=base))
    src, out = tmp / "doc.html", tmp / "doc.pdf"
    err = ""
    try:
        src.write_text(html, encoding="utf-8")
        # each candidate is a different filesystem, and only running it says
        # whether this browser can write there: the first that produces the
        # file wins, and the last error is the one reported
        for candidate in profile_dirs():
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                profile = Path(tempfile.mkdtemp(prefix="profile-",
                                                dir=candidate))
            except OSError as exc:
                err = str(exc)
                continue
            try:
                cmd = [
                    exe, "--headless", "--disable-gpu", "--no-sandbox",
                    f"--user-data-dir={profile}",
                    "--no-pdf-header-footer",          # no date / URL band
                    "--virtual-time-budget=10000",
                    f"--print-to-pdf={out}",
                    src.as_uri(),
                ]
                proc = subprocess.run(cmd, capture_output=True,
                                      timeout=TIMEOUT)
                if out.exists():
                    return out.read_bytes()
                err = proc.stderr.decode(errors="replace")[-500:]
            finally:
                shutil.rmtree(profile, ignore_errors=True)
        raise PdfError(msg("pdf_failed", error=err))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
