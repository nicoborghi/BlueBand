"""Turn `ui/track.svg` into the `.ico` the Windows build wants.

    python packaging/make_icon.py

The icon is generated rather than committed as a binary: the wordmark is the
SVG, and an `.ico` checked in beside it is a copy that goes stale the first
time the logo is touched.

Rasterised with the same headless Chromium the app already prints comunicati
with (`render.pdf`), so the build needs nothing installed that a jury laptop
does not already have - no cairo, no Inkscape, no ImageMagick. On Windows that
is Edge, which is always there.

Pillow, which Streamlit brings in anyway, writes the multi-resolution `.ico`:
Windows picks 16 for the taskbar and 256 for the desktop, and an icon that
carries only one of them is resampled into mush at the other.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SOURCE = ROOT / "ui" / "track.svg"
TARGET = ROOT / "packaging" / "blueband.ico"

#: What Windows asks for, largest first. 256 is the desktop and the installer,
#: 16 is the taskbar and the title bar.
SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]

#: Rendered well above the largest size and scaled down: a browser screenshot
#: of an SVG is taken at the CSS size, and 256 straight off has visibly harder
#: edges than 512 resampled to 256.
RENDER = 512


def png_from_svg(svg: Path, size: int = RENDER) -> bytes:
    """Screenshot the SVG on a transparent page, at `size` square.

    Where the browser is asked to work is `render.pdf`'s problem, already
    solved there and reused here rather than guessed at again: a snap Chromium
    cannot see `/tmp` at all, so a plain `TemporaryDirectory` produces no file
    and no error worth reading (see `pdf.work_dirs`).
    """
    from render import pdf

    browser = pdf.browser()
    if browser is None:
        raise SystemExit("no Chromium/Edge found to rasterise the icon "
                         f"(tried {', '.join(pdf.CANDIDATES)})")
    # the SVG is drawn into a page of exactly its own size, with no margin and
    # no background: anything else lands in the icon as a white square
    page = (f'<!doctype html><meta charset="utf-8">'
            f"<style>html,body{{margin:0;padding:0;background:transparent}}"
            f"img{{display:block;width:{size}px;height:{size}px}}</style>"
            f'<img src="{svg.as_uri()}">')
    problem = "no directory the browser could work in"
    for base in pdf.work_dirs():
        try:
            base.mkdir(parents=True, exist_ok=True)
            work = Path(tempfile.mkdtemp(prefix=".icon-", dir=base))
        except OSError as exc:
            problem = str(exc)
            continue
        html, out = work / "icon.html", work / "icon.png"
        try:
            html.write_text(page, encoding="utf-8")
            done = subprocess.run(
                [browser, "--headless", "--disable-gpu", "--no-sandbox",
                 f"--user-data-dir={work / 'profile'}",
                 "--default-background-color=00000000",  # keep transparency
                 f"--window-size={size},{size}",
                 f"--screenshot={out}", html.as_uri()],
                capture_output=True, timeout=120)
            if out.exists():
                return out.read_bytes()
            problem = done.stderr.decode(errors="replace")[-500:]
        except (OSError, subprocess.TimeoutExpired) as exc:
            problem = str(exc)
        finally:
            shutil.rmtree(work, ignore_errors=True)
    raise SystemExit(f"the browser produced no PNG: {problem}")


def main() -> int:
    if not SOURCE.exists():
        raise SystemExit(f"{SOURCE} is missing")
    from PIL import Image

    image = Image.open(io.BytesIO(png_from_svg(SOURCE))).convert("RGBA")
    if not image.getbbox():
        raise SystemExit("the browser rendered an empty page - is the SVG "
                         "readable from where the browser was allowed to run?")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    image.save(TARGET, format="ICO", sizes=SIZES)
    print(f"{TARGET.relative_to(ROOT)} written "
          f"({TARGET.stat().st_size / 1024:.1f} kB, "
          f"{len(SIZES)} resolutions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
