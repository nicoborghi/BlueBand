"""Turn race data into printable HTML.

One renderer for every document (startlist, results, classification, register):
a `Document` holds a title block, one or more `Table`s and an optional
*Decisione* note; `to_html` produces either a fragment to embed in the app or a
self-contained page for the archive. Nothing here imports streamlit.
"""

from __future__ import annotations

import base64
import mimetypes
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.config import NAME_FULL, SIG_TEXT, Competition
from core.i18n import label

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
CSS_FILE = HERE / "print.css"

# Height of the "Emesso il ... · pag. n/m" line on a numbered sheet: the rest
# of the foot band is the strip itself (see page.html.j2).
LINE_MM = 5

# How tall the signature is drawn in the previews inside the app - screen only,
# the paper keeps the millimetres in print.css. Raise it to enlarge it.
SIG_PREVIEW_PX = 34

_env = Environment(loader=FileSystemLoader(TEMPLATES),
                   autoescape=select_autoescape(["html", "j2"]),
                   trim_blocks=True, lstrip_blocks=True)


# ── document model ──────────────────────────────────────────────────────────

@dataclass
class Column:
    """One column of a printed table.

    `w` is a *weight*, not a width: the table normalises the weights of its
    columns to percentages summing to 100, so a sheet can never starve a
    column into a two-character sliver (which is what turned 'Cognome' into
    'Cog nom e' when widths were declared piecemeal).
    """

    key: str
    label: str | None = None  # None: use the key. "": a column with no heading
    align: str = "l"  # l | c | r
    w: float = 10
    bold: bool = False
    wrap: bool = False  # text columns stay on one line by default
    muted: bool = False  # printed grey: a counter, not data of the race
    tight: bool = False  # one digit wide: no side padding to give the names

    def __post_init__(self):
        # an explicit "" is a heading the sheet deliberately leaves blank (the
        # row counter): only an omitted label falls back to the key
        self.label = self.key if self.label is None else self.label
        self.pct = 0.0  # filled in by Table


@dataclass
class Table:
    columns: list[Column]
    rows: list[dict[str, Any]] = field(default_factory=list)
    font_size: int = 9
    # A sheet that carries two races - the results of the round and the start
    # order of the next - says which is which above each table, in the words
    # of the document's own subtitle. Empty on a sheet with one table.
    title: str = ""

    def __post_init__(self):
        total = sum(c.w for c in self.columns) or 1
        for c in self.columns:
            c.pct = round(100 * c.w / total, 3)

    @property
    def wide(self) -> bool:
        """Sheets this wide need landscape to stay readable."""
        return len(self.columns) >= 11

    @property
    def grouped(self) -> bool:
        """True when the rows are cut into teams / pairs / heat sides."""
        return any("group-start" in r.get("_class", "") for r in self.rows)

    def banner_offset(self, row: dict[str, Any]) -> int:
        """How many cells a band leaves empty on its left.

        A band normally runs the whole width of the sheet; `_banner_at` names
        the column it should start under instead (the champion sits under the
        names, not out in the placing column).
        """
        keys = [c.key for c in self.columns]
        at = row.get("_banner_at")
        return keys.index(at) if at in keys else 0

    @property
    def blocks(self) -> list[list[dict[str, Any]]]:
        """The rows in printing blocks: one per heat, or per team / pair.

        Each block goes out as its own `<tbody>`, which print keeps whole: a
        quartetto split over two sheets is unreadable at the track, and the
        rider left alone on the next page looks like he is riding by himself.

        The second team of a batteria opens with `side-start`, not with a
        group: it is ruled off like any other group but does not start a block,
        so both sides of a batteria print on the same sheet - the jury reads a
        batteria as one thing, and comparing the two teams is the point of it.
        """
        out: list[list[dict[str, Any]]] = []
        for row in self.rows:
            if out and "group-start" not in row.get("_class", ""):
                out[-1].append(row)
            else:
                out.append([row])
        return out


@dataclass
class Document:
    title: str
    subtitle: str = ""
    info: str = ""
    legend: str = ""
    communique: str = ""  # "7", "92 RET" - already formatted
    draft: bool = False  # provisional sheet: no number, "NON DEFINITIVO" instead
    pages: str = ""  # "1/2"
    date: str = ""
    tables: list[Table] = field(default_factory=list)
    decision: str = ""
    slug: str = ""
    landscape: bool = False

    def __post_init__(self):
        self.slug = self.slug or slugify(self.title)

    @property
    def is_landscape(self) -> bool:
        """Landscape is opt-in, never automatic.

        Chrome does not repeat a table header group across the pages of a
        named page, so a landscape comunicato loses its letterhead on every
        continuation sheet - the one thing these documents must not lose.
        Portrait keeps it, and the normalised column widths make even the
        widest classification readable.
        """
        return self.landscape


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", str(text).lower())
    return re.sub(r"[\s_-]+", "-", s).strip("-") or label("document_slug")


# ── assets ──────────────────────────────────────────────────────────────────

def data_uri(path: str | Path | None, base: Path | None = None) -> str:
    """Embed an image as a data: URI (SVG, PNG, JPEG). '' when unavailable."""
    if not path:
        return ""
    p = Path(path)
    if not p.is_absolute() and base:
        p = base / p
    if not p.exists():
        return ""
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"


def image_ratio(path: str | Path | None, base: Path | None = None,
                default: float = 0.12) -> float:
    """height / width of an image, for sizing it against the paper width."""
    if not path:
        return default
    p = Path(path)
    if not p.is_absolute() and base:
        p = base / p
    if not p.exists():
        return default
    if p.suffix.lower() == ".svg":
        head = p.read_text(encoding="utf-8", errors="replace")[:2000]
        box = re.search(r'viewBox="[\d.\s]*?([\d.]+)[\s,]+([\d.]+)"', head)
        if box:
            w, h = float(box.group(1)), float(box.group(2))
            return h / w if w else default
        return default
    try:
        from PIL import Image
        with Image.open(p) as im:
            return im.height / im.width
    except Exception:
        return default


def _css() -> str:
    return CSS_FILE.read_text(encoding="utf-8")


def stylesheet() -> str:
    """print.css itself, for whoever has to put it on the page by hand.

    The app is that case: `st.html` sanitises the fragment it is handed and
    throws its `<style>` away, so the previews have to get the stylesheet from
    somewhere else (see `ui.style`).
    """
    return _css()


# ── rendering ───────────────────────────────────────────────────────────────

def to_html(docs: Document | Iterable[Document], comp: Competition, *,
            standalone: bool = False, banner: bool = True, head: bool = True,
            banner_width: int = 620, signature: bool = False,
            footer: bool = True, assets_base: Path | None = None,
            page_numbers: bool = False, sig_px: int = 0,
            css: bool = True) -> str:
    """Render one or more documents. `standalone` yields a complete HTML page.

    `head=False` drops the whole letterhead block - banner, communiqué number,
    title, subtitle, distance line - and prints the table alone. That is what
    the on-screen preview wants: the app page already says which race this is,
    right above the table, and the block only pushed it below the fold.

    `footer=False` leaves out the foot of the sheet (competition, venue, time
    of printing) altogether. The preview in the app passes it: on paper that
    block belongs at the bottom of every page, on screen it is noise under the
    table - and hiding it with `@media screen` alone does not survive being
    embedded in the app's own document.

    On paper the footer is emitted twice: inline in each document, which only
    reserves its height in the repeated `tfoot`, and once as a *running* copy
    that print pins to the bottom of every sheet.

    `css=False` leaves the stylesheet out of a fragment, for a page that
    already carries it. A standalone document always brings its own.

    `page_numbers` adds "pag. n/m" in the bottom margin of the paper. It is set
    by `to_pdf`/`archive` on the second pass, once the first one has shown the
    document really spans more than one sheet: only the printer knows how many
    sheets a table takes.
    """
    if isinstance(docs, Document):
        docs = [docs]
    docs = list(docs)
    base = assets_base or HERE.parent  # the track/ package root
    # every sheet goes through here, preview and paper alike: this is the one
    # place that has to know how the competition sets a rider's name
    if comp.branding.name_style == NAME_FULL:
        docs = [merge_names(d) for d in docs]

    b = comp.branding
    ctx = {
        "head": head,
        "footer": footer,
        "banner": data_uri(b.header_img, base) if banner and head else "",
        "banner_width": banner_width,
        "footer_img": data_uri(b.footer_img, base) if banner and head else "",
        # the jury signs with the scanned signature or with its name in bold:
        # one or the other, never both, and neither unless the sheet asks
        "signature": (data_uri(b.signature, base)
                      if signature and b.signature_mode != SIG_TEXT else ""),
        "signature_name": (b.signature_name
                           if signature and b.signature_mode == SIG_TEXT
                           else ""),
        "signature_label": b.signature_label if signature else "",
        # Screen only: the preview is embedded in the app's own document, where
        # the stylesheet does not reach the image, so the size has to travel on
        # the tag itself. Left empty for print and for the PDF, which keep the
        # millimetres from print.css.
        "signature_style": (f"max-height:{sig_px}px;max-width:{sig_px * 3}px;"
                            "width:auto;height:auto;" if sig_px else ""),
        "printed_at": (f"{label('printed_at')} "
                       + datetime.now().strftime("%d/%m/%Y %H:%M")),
        "page_numbers": page_numbers,
    }
    # A numbered sheet hands its whole foot to a @page margin box - the one
    # place Chrome prints the page number - so the band has to be as tall as
    # the strip plus the line above it, on either paper orientation.
    strip = image_ratio(b.footer_img, base) if ctx["footer_img"] else 0.0
    ctx["foot_mm"] = round(210 * strip) + LINE_MM
    ctx["foot_mm_land"] = round(297 * strip) + LINE_MM
    doc_tpl = _env.get_template("document.html.j2")
    body = "\n".join(doc_tpl.render(doc=d, **ctx) for d in docs)

    return _env.get_template("page.html.j2").render(
        standalone=standalone, css=_css() if css or standalone else "", body=body,
        header_color=b.color or "#0a5688",
        page_title=docs[0].title if docs else comp.name, **ctx)


def suffix_titles(docs: Iterable[Document], suffix: str) -> None:
    """Add `suffix` to the title of every document, in place.

    What the jury writes in the box - "versione aggiornata", "rettifica" - is
    part of the heading and nothing else: the slug was fixed when the document
    was built, so the file keeps the name the comunicato is filed under and a
    reprint lands on the same sheet rather than beside it.
    """
    suffix = (suffix or "").strip()
    if not suffix:
        return
    for d in docs:
        d.title = f"{d.title} - {suffix}"


def _render_pdf(docs: list[Document], comp: Competition, *, signature: bool,
                workdir: str | Path | None) -> bytes:
    """PDF bytes, numbering the sheets when there is more than one.

    Two passes: nothing but the browser knows how many sheets a table takes, so
    the first pass answers that question and the second one prints "pag. n/m"
    in the bottom margin. A one-page comunicato - most of them - never pays for
    the second pass.
    """
    from .import pdf as _pdf
    html = to_html(docs, comp, standalone=True, signature=signature)
    data = _pdf.html_to_pdf(html, workdir=workdir)
    if _pdf.page_count(data) > 1:
        html = to_html(docs, comp, standalone=True, signature=signature,
                       page_numbers=True)
        data = _pdf.html_to_pdf(html, workdir=workdir)
    return data


def out_name(docs: list[Document], number: str | int = "", ext: str = "pdf") -> str:
    """`007_AL_ins_squadre_qualificazioni.pdf` - the name inside the out folder.

    The jury files by comunicato number, then category, specialità, fase and
    batteria; a classification adds `_classifica` (see `models.race_slug`).
    """
    if docs and docs[0].draft:
        # not a comunicato yet: it must not take a number, nor sort among them
        return f"{label('draft')}_{docs[0].slug}.{ext}"
    n = str(number or (docs[0].communique if docs else "")).replace(" ", "-")
    prefix = f"{int(n):03d}_" if n.isdigit() else (f"{n}_" if n else "")
    return f"{prefix}{docs[0].slug if docs else label('document_slug')}.{ext}"


def archive(store, docs: Document | Iterable[Document], comp: Competition,
            *, number: str | int = "", signature: bool = True,
            fmt: str = "pdf") -> Path:
    """Write a copy under `out/`, named by comunicato number.

    `fmt="pdf"` renders through a headless Chromium and falls back to the
    self-contained HTML when no browser is installed.
    """
    if isinstance(docs, Document):
        docs = [docs]
    docs = list(docs)
    html = to_html(docs, comp, standalone=True, signature=signature)

    if fmt == "pdf":
        from .import pdf as _pdf
        try:
            data = _render_pdf(docs, comp, signature=signature,
                               workdir=store.out_dir)
        except _pdf.PdfError as exc:
            # keep the HTML rather than losing the document, but record why:
            # a sandboxed browser cannot read every directory (a snap Chromium
            # is blocked from /tmp), and a silent downgrade is confusing
            store.journal(action="pdf_failed", target=out_name(docs, number),
                          extra={"reason": str(exc)[:200]})
        else:
            return store.write_out(out_name(docs, number, "pdf"), data,
                                   action="archive_pdf")

    return store.write_out(out_name(docs, number, "html"), html)


def to_pdf(docs: Document | Iterable[Document], comp: Competition, *,
           signature: bool = True, workdir: str | Path | None = None) -> bytes:
    """PDF bytes for one or more documents (for a download button)."""
    if isinstance(docs, Document):
        docs = [docs]
    return _render_pdf(list(docs), comp, signature=signature, workdir=workdir)


# ── table helpers ───────────────────────────────────────────────────────────

def zebra(rows: list[dict]) -> list[dict]:
    """Tag alternate rows for the striped background."""
    for i, r in enumerate(rows):
        if i % 2:
            r["_class"] = (r.get("_class", "") + " alt").strip()
    return rows


def position_label(pos: int | str | None) -> str:
    """1 -> '1°'; statuses and blanks pass through."""
    if pos is None or pos == "":
        return ""
    if isinstance(pos, int) or str(pos).isdigit():
        return f"{int(pos)}°"
    return str(pos)

# Column weights shared by the startlist / classification renderers. They keep
# the workbook's column order; the table normalises them so a sheet always fits
# the page whatever combination a document asks for.


COLS_RIDER = [Column(k, label(k), "c" if k in ("bib", "uci_id") else "l", w)
              for k, w in (("bib", 7), ("last_name", 20), ("first_name", 15),
                           ("uci_id", 20), ("club", 22), ("region", 17))]

COLS_RIDER_MIN = [c for c in COLS_RIDER if c.key != "club"]

# Plain row counter down the left edge: it says how many riders there are and
# gives the jury something to point at on paper. Not a placing - hence grey.
COL_INDEX = Column("_idx", "", "r", 4, muted=True)


def numbered(rows: list[dict]) -> list[dict]:
    """Fill the counter column, 1..n in the order the rows are already in."""
    for i, r in enumerate(rows, start=1):
        r["_idx"] = i
    return rows

W_RANK = 7         # Ris.
W_GROUP = 22       # Squadra / Coppia / Batteria - region names are long
W_SPRINT = 4       # one sprint column
W_LAPS = 6         # Giri
W_TOTAL = 7        # Tot.
W_TIME = 14        # Tempo
W_LANE = 9         # Balau. / Corda - where a rider lines up for the next prova
W_POINTS = 12      # "Punti Tempo Race" - a heading that has to read whole


def rider_row(rider, **extra) -> dict:
    """Standard cells for one rider; `extra` adds/overrides columns."""
    row = {
        # a declared non-starter prints "NP" where the bib would be
        "bib": label("not_starting") if rider.not_starting else (rider.bib or ""),
        "last_name": rider.last_name,
        "first_name": rider.first_name,
        "uci_id": rider.uci_id,
        "club": rider.club,
        "club_code": rider.club_code,
        "region": rider.region,
        "cat": rider.cat,
    }
    return row | extra


# ── one name instead of two ─────────────────────────────────────────────────
#
# A competition may set its sheets with a single *Nome* column - "ROSSI Mario"
# - instead of Cognome and Nome side by side. It is a matter of how the sheets
# are set, not of what the race knows, so nothing upstream changes: the tables
# are built with both columns as always and merged here, on the way out.

def full_name(last: str, first: str) -> str:
    """'rossi', 'mario luigi' -> 'ROSSI Mario Luigi'.

    The surname in capitals is what makes the two readable as one string: it
    is the half the sheet is sorted and called by.
    """
    return " ".join(p for p in (str(last).upper().strip(),
                                _titled(first)) if p)


def _titled(name: str) -> str:
    """'MARIA-LUISA' -> 'Maria-Luisa', leaving what is already set alone."""
    s = str(name).strip()
    return s.title() if s.isupper() or s.islower() else s


#: What the merged column keeps of the two it replaces. "ROSSI Mario Luigi" is
#: one string set on one line: it does not need the width of two columns, each
#: of which was sized to hold a long name by itself. The rest goes back to the
#: columns the sheet is actually read for - the volate, the points, the society.
FULL_NAME_W = 0.72


def merge_names(doc: Document) -> Document:
    """A copy of `doc` with Cognome and Nome merged into a single column.

    The merged column takes the width of the two it replaces, and everything
    that pointed at either of them - the bold and red marks, the column a band
    starts under - is moved onto it.
    """
    return replace(doc, tables=[_merge_table(t) for t in doc.tables])


def _merge_table(t: Table) -> Table:
    keys = [c.key for c in t.columns]
    if not ("last_name" in keys and "first_name" in keys):
        return t
    width = FULL_NAME_W * sum(c.w for c in t.columns
                              if c.key in ("last_name", "first_name"))
    cols = []
    for c in t.columns:
        if c.key == "first_name":
            continue
        # a copy even where nothing changes: `Table` normalises the weights of
        # the columns it is given, in place, and the document this one is made
        # from is still the caller's
        cols.append(replace(c, key="full_name", label=label("first_name"),
                            w=width) if c.key == "last_name" else replace(c))

    rows = []
    for row in t.rows:
        row = dict(row)
        if "last_name" in row or "first_name" in row:
            row["full_name"] = full_name(row.pop("last_name", ""),
                                         row.pop("first_name", ""))
        for mark in ("_bold", "_red"):
            if mark in row:
                marked = {"full_name" if k in ("last_name", "first_name") else k
                          for k in row[mark]}
                row[mark] = (marked if isinstance(row[mark], set)
                             else sorted(marked))
        if row.get("_banner_at") in ("last_name", "first_name"):
            row["_banner_at"] = "full_name"
        rows.append(row)
    return Table(columns=cols, rows=rows, font_size=t.font_size, title=t.title)


def group_start(row: dict, strong: bool = False) -> dict:
    """Mark a row as the first of a team / pair / heat.

    Groups are separated by a rule above the first row rather than by a blank
    spacer row: it reads more clearly and costs no vertical space, which
    matters on a classification that has to fit the page.
    """
    row["_class"] = (row.get("_class", "") +
                     (" group-start-strong" if strong else " group-start")).strip()
    return row


def side_start(row: dict) -> dict:
    """Mark a row as the second team of a batteria: ruled off, but not a block.

    Same rule as `group_start` draws, and deliberately no block of its own -
    see `Table.blocks`: a batteria must not be split over two sheets.
    """
    row["_class"] = (row.get("_class", "") + " side-start").strip()
    return row
