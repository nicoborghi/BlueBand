"""Turn race data into printable HTML.

One renderer for every document (startlist, results, classification, register):
a `Document` holds a title block, one or more `Table`s and an optional
*Decisione* note; `to_html` produces either a fragment to embed in the app or a
self-contained page for the archive. Nothing here imports streamlit.
"""

from __future__ import annotations

import base64
import colorsys
import mimetypes
import re
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.config import (ALIGN_LEFT, ALIGN_RIGHT, DEFAULT_NAME_WIDTH,
                         NAME_FULL, SIG_TEXT, SLOT_NONE, SLOT_PRINTED_AT,
                         FONTS, Branding, Competition, default_text_color,
                         font_value, text_color)
from core.i18n import label, ordinal
from core.models import number_text

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

    `min_mm` is the one thing a weight cannot express: how narrow this column
    may actually get on paper. A name that loses its last letters is still a
    name; `DNF` truncated to `DN...` and a UCI ID missing two digits are not
    the thing they are printed for. Those columns declare the millimetres they
    need and the table gives them, out of what the others were sharing.
    """

    key: str
    label: str | None = None  # None: use the key. "": a column with no heading
    align: str = "l"  # l | c | r
    w: float = 10
    bold: bool = False
    wrap: bool = False  # text columns stay on one line by default
    muted: bool = False  # printed grey: a counter, not data of the race
    tight: bool = False  # one digit wide: no side padding to give the names
    min_mm: float = 0  # never narrower than this on paper (see SHEET_MM)

    def __post_init__(self):
        # an explicit "" is a heading the sheet deliberately leaves blank (the
        # row counter): only an omitted label falls back to the key
        self.label = self.key if self.label is None else self.label
        self.pct = 0.0  # filled in by Table


#: How wide a printed table is on the narrowest paper the app uses: A4
#: portrait less the two `--pad-x` margins of print.css. A floor written in
#: millimetres is measured against this, so a column that must read whole
#: reads whole on the tightest sheet - on a landscape one it simply gets more.
SHEET_MM = 194.0


def _hold_floors(cols: list[Column]) -> None:
    """Give every column its `min_mm` back, out of what the others share.

    The floors are held first and the rest of the sheet is rescaled onto what
    is left - which is what makes the guarantee a guarantee: a corsa a punti
    with a dozen volate no longer buys its columns out of the Ris. one.

    Where the floors alone would fill the sheet there is nothing to take from,
    and the plain weights stand: the caller has asked for more columns than the
    paper holds, and that is a decision for the sheet, not for a rounding here.
    """
    floors = [100 * c.min_mm / SHEET_MM for c in cols]
    short = [i for i, c in enumerate(cols) if c.pct < floors[i]]
    if not short:
        return
    need = sum(floors[i] - cols[i].pct for i in short)
    spare = sum(c.pct for i, c in enumerate(cols) if i not in short)
    if need >= spare:
        return
    for i, c in enumerate(cols):
        c.pct = round(floors[i] if i in short
                      else c.pct * (spare - need) / spare, 3)


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
        _hold_floors(self.columns)

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
class Note:
    """One block under the table of a sheet, tinted by what it says.

    A squalifica and "i primi due passano alla finale" are both prose in a box,
    and for years they were the same box. They are not the same thing: one is a
    sanction a team may appeal, the other is how the torneo is run. So a block
    carries its `kind` - one of `core.decisions.NOTE_KINDS` - and the sheet
    colours it accordingly (`print.css`, tints set in Impostazioni).

    `title` is the one word above the text ("SQUALIFICA"); empty on the plain
    note, which needs no announcing.
    """

    text: str
    kind: str = "note"
    title: str = ""


@dataclass
class Document:
    title: str
    subtitle: str = ""
    info: str = ""
    legend: str = ""
    #: "7", "92 RET" - already formatted, and empty when the sheet goes out
    #: under no number of its own (`core.models.number_text`), which is what a
    #: sheet carried on another one's comunicato does
    communique: str = ""
    draft: bool = False  # provisional sheet: no number, "NON DEFINITIVO" instead
    pages: str = ""  # "1/2"
    date: str = ""
    #: Prose printed above the tables, as HTML: what the jury typed into the
    #: *foglio intestato*, read through `render.markup`. Empty on every sheet
    #: the app composes itself - those are tables, and a table says it all.
    body: str = ""
    tables: list[Table] = field(default_factory=list)
    #: The tinted blocks - the decisions of the race, in the order they were
    #: taken. They print above the note, which is the standing text of the
    #: sheet and says nothing about anybody.
    notes: list[Note] = field(default_factory=list)
    decision: str = ""
    slug: str = ""
    landscape: bool = False

    def __post_init__(self):
        self.slug = self.slug or slugify(self.title)
        # one reading of "no number" for the head of the sheet, the name it is
        # filed under and everything that asks: empty. A `-1` off an older
        # register or a race saved before this is the same answer
        self.communique = number_text(self.communique)

    @property
    def blocks(self) -> list[Note]:
        """Everything printed under the table: the decisions, then the note.

        The note is the last block and keeps the plain tint it has always had:
        it is what the sheet says about itself, and a colour on it would say
        that somebody was sanctioned.
        """
        return list(self.notes) + ([Note(self.decision)] if self.decision else [])

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


def hex_color(value: str, default: str = "") -> str:
    """A `#rrggbb` from whatever was stored, or `default`.

    The tint of a cell is written straight into the `style` of the sheet, so
    what goes in there is a colour and nothing else: a value typed into
    settings.json by hand cannot become markup on the printed programme.
    """
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", str(value or "").strip())
    return f"#{m.group(1).lower()}" if m else default


# ── the tints of the note blocks ────────────────────────────────────────────

def darken(hex_color: str, lightness: float = 0.34,
           saturate: float = 1.7) -> str:
    """The rule of a tinted box, derived from the tint itself.

    One colour per kind is set in Impostazioni and the border comes from it:
    asking the jury for two colours per provvedimento would be asking it to do
    the design of the sheet, and the pair would drift apart the first time one
    of them was changed.

    Not simply the tint scaled towards black - a pastel scaled that way goes
    muddy brown, and a squalifica ruled in mud does not read as a squalifica.
    The hue is kept, the lightness is taken down to `lightness` and the
    saturation up: a pink box gets a red rule, a peach one an orange rule, and
    the grey of the note - which has no hue to keep - stays grey.

    An unreadable value comes back unchanged, which leaves the box ruled in
    whatever was typed instead of taking the sheet down.
    """
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", str(hex_color or "").strip())
    if not m:
        return str(hex_color or "")
    r, g, b = (int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, _l, s = colorsys.rgb_to_hls(r, g, b)
    rgb = colorsys.hls_to_rgb(h, lightness, min(1.0, s * saturate))
    return "#" + "".join(f"{round(v * 255):02x}" for v in rgb)


def note_css_vars(colors: dict[str, str]) -> str:
    """The tints as custom properties, for the wrapper of the page.

    `--note-<kind>` and `--note-<kind>-rule` per kind: print.css states the
    shape of a block and takes every colour from here, so recolouring a
    provvedimento is a setting and never an edit to the stylesheet.
    """
    return "".join(f"--note-{k}: {v};--note-{k}-rule: {darken(v)};"
                   for k, v in (colors or {}).items())


def font_css_vars(fonts: dict[str, str]) -> str:
    """The characters as custom properties, for the wrapper of the page.

    `--font-<element>` per entry of `config.FONTS`: print.css states what an
    element *is* and takes its typeface and its size from here, so setting the
    titolo two points larger is a setting and never an edit to the stylesheet.

    What does not read as a font never reaches the style: `config.font_value`
    has already dropped it on the way into `Branding`, and it is checked again
    here because this is the function that writes into the tag.
    """
    return "".join(f"--font-{k}: {value};"
                   for k, v in (fonts or {}).items()
                   if (value := font_value(k, v)))


def color_css_vars(colors: dict[str, str]) -> str:
    """The colours of the elements as custom properties, for the wrapper.

    Only what the jury changed: print.css names each of them with the colour
    the sheet has always printed as the fallback, so an element nobody touched
    is not written into the page at all (`config.TEXT_COLORS`).
    """
    return "".join(f"--color-{k}: {value};"
                   for k, v in (colors or {}).items()
                   if (value := text_color(k, v)))


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


#: What `align` means for a block image: the left and right margins that push
#: it to a side. The other two carry the distance from the paper edge.
_SIDES = {ALIGN_LEFT: ("auto", "0"), ALIGN_RIGHT: ("0", "auto")}


def image_style(b: Branding, which: str) -> str:
    """Inline style for one of the two framing images, or "" for a letterhead.

    Empty is not "no opinion": it is the default - the image is the width of
    the sheet and sits against its edge, which is what the stylesheet already
    says and what a letterhead drawn for A4 wants.
    """
    frac, align = b.image_box(which)
    off = b.image_offset(which)
    if frac >= 1.0 and not off:
        return ""
    right, left = _SIDES.get(align, ("auto", "auto"))
    edge = f"{off:g}mm" if off else "0"
    top, bottom = (edge, "0") if which == "header" else ("0", edge)
    width = f"width:{frac * 100:g}%;" if frac < 1.0 else ""
    return f"{width}margin:{top} {right} {bottom} {left};"


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
            css: bool = True, timestamp: bool = True) -> str:
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

    `timestamp=False` drops the "Emesso il ..." line from the foot, keeping the
    rest of it. A sheet that is reprinted as the day goes on - the medagliere -
    otherwise differs from the copy already handed out by nothing but the
    minute it came off the printer, which is the one difference nobody wants to
    have to explain. The page number, where there is one, stays.

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
        docs = [merge_names(d, comp.branding.name_width) for d in docs]

    b = comp.branding
    ctx = {
        "head": head,
        "footer": footer,
        "banner": data_uri(b.header_img, base) if banner and head else "",
        "banner_width": banner_width,
        "footer_img": data_uri(b.footer_img, base) if banner and head else "",
        # A letterhead is drawn to the paper width and stays there; a logo
        # given a size of its own carries it on the tag, so the preview in the
        # app - which never sees print.css - places it the same way the paper
        # does (`Branding.image_box`).
        # The two lines of slots - the one under the testata and the one over
        # the piè - as three items each, left to centre to right, and the air
        # asked for between each line and its edge of the paper (Impostazioni →
        # Aspetto dei comunicati). On the tag and not in print.css, because the
        # preview in the app never reads the stylesheet.
        "head_slots": b.slots("head"),
        "foot_slots": b.slots("foot"),
        # whether either line is printed at all: three cleared slots are a line
        # that is not there, not a line of three empty cells
        "head_line": any(i != SLOT_NONE for i in b.slots("head")),
        "foot_line": any(i != SLOT_NONE for i in b.slots("foot")),
        "head_gap": b.head_gap,
        "foot_gap": b.foot_gap,
        "banner_style": image_style(b, "header"),
        "footer_style": image_style(b, "footer"),
        # the jury signs with the scanned signature or with its name in bold:
        # one or the other, never both, and neither unless the sheet asks
        "signature": (data_uri(b.signature, base)
                      if signature and b.signature_mode != SIG_TEXT else ""),
        "signature_name": (b.signature_name
                           if signature and b.signature_mode == SIG_TEXT
                           else ""),
        "signature_label": b.signature_caption if signature else "",
        # Screen only: the preview is embedded in the app's own document, where
        # the stylesheet does not reach the image, so the size has to travel on
        # the tag itself. Left empty for print and for the PDF, which keep the
        # millimetres from print.css.
        "signature_style": (f"max-height:{sig_px}px;max-width:{sig_px * 3}px;"
                            "width:auto;height:auto;" if sig_px else ""),
        "printed_at": (f"{label('printed_at')} "
                       + datetime.now().strftime("%d/%m/%Y %H:%M")
                       if timestamp else ""),
        "page_numbers": page_numbers,
    }
    # A numbered sheet hands its whole foot to a @page margin box - the one
    # place Chrome prints the page number - so the band has to be as tall as
    # the strip plus the line above it, on either paper orientation.
    frac, align = b.image_box("footer")
    off = b.image_offset("footer") if ctx["footer_img"] else 0.0
    strip = image_ratio(b.footer_img, base) * frac if ctx["footer_img"] else 0.0
    gap = round(b.foot_gap)
    ctx["foot_mm"] = round(210 * strip + off) + LINE_MM + gap
    ctx["foot_mm_land"] = round(297 * strip + off) + LINE_MM + gap
    # The margin box of a numbered sheet is one line of text, and the page
    # number has to be in it: it is the only place Chrome resolves counter().
    # So the foot the slots describe collapses to the one item that can share
    # that line - «Emesso il …», where the jury put it - and the box takes the
    # side its slot sits on.
    ctx["foot_box_align"] = b.slot_side("foot", SLOT_PRINTED_AT) or ALIGN_RIGHT
    ctx["foot_box_text"] = (ctx["printed_at"]
                            if b.slot_side("foot", SLOT_PRINTED_AT) else "")
    # the numbered sheet paints the strip as the background of a margin box,
    # so the width, the side and the distance from the paper edge have to be
    # said again in those two words
    ctx["foot_size"] = f"{frac * 100:g}% auto"
    ctx["foot_pos"] = f"{align} bottom {off:g}mm"
    doc_tpl = _env.get_template("document.html.j2")
    body = "\n".join(doc_tpl.render(doc=d, **ctx) for d in docs)

    return _env.get_template("page.html.j2").render(
        standalone=standalone, css=_css() if css or standalone else "", body=body,
        header_color=b.color or "#0a5688",
        note_vars=note_css_vars(b.note_colors),
        font_vars=font_css_vars(b.fonts) + color_css_vars(b.text_colors),
        font_family=font_value("family", b.fonts.get("family"))
        or FONTS["family"],
        footline_size=font_value("footline", b.fonts.get("footline"))
        or FONTS["footline"],
        footline_color=text_color("footline", b.text_colors.get("footline"))
        or default_text_color("footline", b.color),
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
                workdir: str | Path | None, timestamp: bool = True) -> bytes:
    """PDF bytes, numbering the sheets when there is more than one.

    Two passes: nothing but the browser knows how many sheets a table takes, so
    the first pass answers that question and the second one prints "pag. n/m"
    in the bottom margin. A one-page comunicato - most of them - never pays for
    the second pass.
    """
    from .import pdf as _pdf
    html = to_html(docs, comp, standalone=True, signature=signature,
                   timestamp=timestamp)
    data = _pdf.html_to_pdf(html, workdir=workdir)
    if _pdf.page_count(data) > 1:
        html = to_html(docs, comp, standalone=True, signature=signature,
                       page_numbers=True, timestamp=timestamp)
        data = _pdf.html_to_pdf(html, workdir=workdir)
    return data


def out_name(docs: list[Document], number: str | int = "", ext: str = "pdf") -> str:
    """`007_AL_ins_squadre_qualificazioni.pdf` - the name inside the out folder.

    The jury files by comunicato number, then category, event, fase and
    batteria; a classification adds `_classifica` (see `models.race_slug`).
    A sheet that goes out under no number of its own is filed by its name
    alone - nothing is invented to sort it by.
    """
    if docs and docs[0].draft:
        # not a comunicato yet: it must not take a number, nor sort among them
        return f"{label('draft')}_{docs[0].slug}.{ext}"
    n = number_text(number or (docs[0].communique if docs else "")) \
        .replace(" ", "-")
    prefix = f"{int(n):03d}_" if n.isdigit() else (f"{n}_" if n else "")
    return f"{prefix}{docs[0].slug if docs else label('document_slug')}.{ext}"


def archive(store, docs: Document | Iterable[Document], comp: Competition,
            *, number: str | int = "", signature: bool = True,
            fmt: str = "pdf", timestamp: bool = True) -> Path:
    """Write a copy under `out/`, named by comunicato number.

    `fmt="pdf"` renders through a headless Chromium and falls back to the
    self-contained HTML when no browser is installed.
    """
    if isinstance(docs, Document):
        docs = [docs]
    docs = list(docs)
    html = to_html(docs, comp, standalone=True, signature=signature,
                   timestamp=timestamp)

    if fmt == "pdf":
        from .import pdf as _pdf
        try:
            data = _render_pdf(docs, comp, signature=signature,
                               workdir=store.out_dir, timestamp=timestamp)
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
           signature: bool = True, workdir: str | Path | None = None,
           timestamp: bool = True) -> bytes:
    """PDF bytes for one or more documents (for a download button)."""
    if isinstance(docs, Document):
        docs = [docs]
    return _render_pdf(list(docs), comp, signature=signature, workdir=workdir,
                       timestamp=timestamp)


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
        return ordinal(int(pos))
    return str(pos)

# Column weights shared by the startlist / classification renderers. They keep
# the workbook's column order; the table normalises them so a sheet always fits
# the page whatever combination a document asks for.


#: The columns of a rider, and how wide each one is. A *pair* and not a
#: `Column`: the heading is looked up when the sheet is built, so it comes out
#: in the language the competition is being run in.
RIDER_COLS = (("bib", 7), ("last_name", 20), ("first_name", 15),
              ("uci_id", 20), ("club", 22), ("region", 17))

#: Eleven digits and the padding around them, at the 9pt the tables are set
#: in: what a UCI ID needs to print whole. It is the number the federation
#: files the result under and half of one is worse than none, so wherever the
#: column appears it is never squeezed below this (`Column.min_mm`).
MIN_UCI_MM = 21.0

#: The Ris. column holds `DNF`, `DNS`, `ABD` as well as `10°`: three capitals
#: and the padding. A sigla is the whole of what that line says.
MIN_RANK_MM = 8.5


def cols_rider(minimal: bool = False) -> list[Column]:
    """The rider columns, headed from the catalogue (`minimal` drops the club)."""
    return [Column(k, label(k), "c" if k in ("bib", "uci_id") else "l", w,
                   min_mm=MIN_UCI_MM if k == "uci_id" else 0)
            for k, w in RIDER_COLS if not (minimal and k == "club")]

# Plain row counter down the left edge: it says how many riders there are and
# gives the jury something to point at on paper. Not a placing - hence grey.
COL_INDEX = Column("_idx", "", "r", 4, muted=True)


def numbered(rows: list[dict]) -> list[dict]:
    """Fill the counter column, 1..n in the order the rows are already in."""
    for i, r in enumerate(rows, start=1):
        r["_idx"] = i
    return rows

W_RANK = 7         # Ris. (never below MIN_RANK_MM: see cols_rider)
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
        # a declared non-starter prints the not-starting code where the bib would be
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


#: What the merged column keeps of the two it replaces, when the caller does
#: not say. The competition's own figure is `branding.name_width`, set in
#: Impostazioni → Nome: see `core.config.DEFAULT_NAME_WIDTH`.
FULL_NAME_W = DEFAULT_NAME_WIDTH


def merge_names(doc: Document, width: float = FULL_NAME_W) -> Document:
    """A copy of `doc` with Cognome and Nome merged into a single column.

    `width` is the fraction of the two replaced columns the merged one keeps,
    and everything that pointed at either of them - the bold and red marks, the
    column a band starts under - is moved onto it.
    """
    return replace(doc, tables=[_merge_table(t, width) for t in doc.tables])


def _merge_table(t: Table, width: float = FULL_NAME_W) -> Table:
    keys = [c.key for c in t.columns]
    if not ("last_name" in keys and "first_name" in keys):
        return t
    width = width * sum(c.w for c in t.columns
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


def section_start(row: dict) -> dict:
    """Mark a row as the first of a section - the next categoria on a grid.

    A rule between one thing and the next, and deliberately neither of the
    other two: lighter than the qualification cut (`group_start(strong)`,
    which is a decision of the jury) and heavier than the hairline that tells
    one coppia from the next. Like `side_start` it opens no block of its own -
    a categoria is as long as it is, and must be free to run over the page.
    """
    row["_class"] = (row.get("_class", "") + " section-start").strip()
    return row


def side_start(row: dict) -> dict:
    """Mark a row as the second team of a batteria: ruled off, but not a block.

    Same rule as `group_start` draws, and deliberately no block of its own -
    see `Table.blocks`: a batteria must not be split over two sheets.
    """
    row["_class"] = (row.get("_class", "") + " side-start").strip()
    return row
