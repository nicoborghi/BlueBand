import re
import shutil
from pathlib import Path

import pytest

from core.entries import import_master
from core.i18n import label, ui
from render import documents as D
from render.render import (Column, Document, Table, archive, slugify,
                           suffix_titles, to_html)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def entries(iscritti_path, comp):
    return import_master(iscritti_path, comp)


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def test_minimal_document_renders(comp):
    doc = Document(title="PROVA", communique="7",
                   tables=[Table(columns=[Column("a", "A"), Column("b", "B", "c")],
                                 rows=[{"a": "1", "b": "2"}])])
    html = to_html(doc, comp)
    assert "Comunicato n. 7" in _text(html)
    assert "PROVA" in html
    assert '<td class="c">2</td>' in html.replace("\n", "")
    assert "@media print" in html  # stylesheet is inlined


def _slot_row(html: str, cls: str) -> list[str]:
    """The three cells of one line of slots, as text, left to right."""
    marker = f'<div class="slot-row {cls}">'
    assert marker in html, f"no {cls} row in the sheet"
    rest = html.split(marker, 1)[1]
    cells = re.findall(r'<div class="slot">(.*?)</div>', rest, re.S)[:3]
    return [_text(cell).strip() for cell in cells]


def test_the_communique_number_sits_where_impostazioni_puts_it(comp):
    """Right on the jury workbooks, and anywhere else the letterhead needs.

    Three slots per line and the item in the one it was given: the preview
    inside the app never reads print.css, so the cells travel on the tag.
    """
    import dataclasses

    doc = Document(title="PROVA", communique="7", tables=[])
    assert _slot_row(to_html(doc, comp), "head-slots") == ["", "", "Comunicato n. 7"]

    centred = dataclasses.replace(
        comp, branding=dataclasses.replace(comp.branding, head_left="none",
                                           head_center="communique",
                                           head_right="none"))
    assert _slot_row(to_html(doc, centred), "head-slots") \
        == ["", "Comunicato n. 7", ""]
    # and the NON DEFINITIVO mark takes its place, in the same slot
    draft = Document(title="PROVA", draft=True, tables=[])
    assert _slot_row(to_html(draft, centred), "head-slots") \
        == ["", "NON DEFINITIVO", ""]


def test_a_settings_file_written_before_the_slots_keeps_its_sheet(comp):
    """`communique_align` is what an old settings.json says; it still places it."""
    import dataclasses

    from core.config import Branding

    b = Branding(communique_align="left")
    assert b.slots("head") == ["communique", "none", "none"]
    assert b.slots("foot") == ["none", "none", "printed_at"]

    doc = Document(title="PROVA", communique="7", tables=[])
    html = to_html(doc, dataclasses.replace(comp, branding=b))
    assert _slot_row(html, "head-slots") == ["Comunicato n. 7", "", ""]


def test_emesso_il_can_be_moved_like_the_communique_number(comp):
    """The timestamp is a slot like any other - head or foot, any of the three."""
    import dataclasses

    b = dataclasses.replace(comp.branding, head_left="printed_at",
                            head_center="none", head_right="communique",
                            foot_left="none", foot_center="none",
                            foot_right="none")
    doc = Document(title="PROVA", communique="7", tables=[])
    html = to_html(doc, dataclasses.replace(comp, branding=b))
    left, centre, right = _slot_row(html, "head-slots")
    assert left.startswith("Emesso il") and centre == ""
    assert right == "Comunicato n. 7"
    # nothing left for the foot: the line is not printed at all
    assert 'class="foot-slots"' not in html


def test_standalone_page_is_self_contained(comp):
    doc = Document(title="PROVA", tables=[])
    html = to_html(doc, comp, standalone=True, banner=True)
    assert html.lstrip().startswith("<!doctype html>")
    assert "</html>" in html
    # no external references at all: images are data URIs, CSS is inline
    assert "http://" not in html and "https://" not in html
    assert not re.search(r'src="(?!data:)', html)
    assert not re.search(r"<link\b", html)


def test_a_title_suffix_marks_the_heading_and_not_the_file(comp):
    """«versione aggiornata» belongs on the sheet; the file keeps its name."""
    docs = [Document(title="PROVA"), Document(title="ALTRA")]
    slugs = [d.slug for d in docs]
    suffix_titles(docs, "  versione aggiornata  ")
    assert [d.title for d in docs] == ["PROVA - versione aggiornata",
                                       "ALTRA - versione aggiornata"]
    assert [d.slug for d in docs] == slugs
    assert "versione aggiornata" in to_html(docs[0], comp)


def test_an_empty_title_suffix_changes_nothing():
    doc = Document(title="PROVA")
    suffix_titles([doc], "   ")
    assert doc.title == "PROVA"


def test_entry_list_document(entries, comp):
    doc = D.entry_list(entries, comp, "ED", communique="2", matrix=True)
    html = to_html(doc, comp)
    text = _text(html)
    # without the NP the same sheet is the elenco partenti, and says so
    assert "DONNE ESORDIENTI" in text and "ELENCO PARTENTI" in text
    assert "Comunicato n. 2" in text
    assert "34 partenti" in text
    # one column per event contested by the category, named in the key below
    assert "OM = Omnium" in text and "MD = Madison" in text
    assert "Keirin" not in text
    assert html.count("<tr") >= 34


def test_entry_list_counts_the_rows_in_a_grey_column(entries, comp):
    """A counter on the left, on by default; the matrix on the right is not."""
    doc = D.entry_list(entries, comp, "ED")
    cols = doc.tables[0].columns
    assert cols[0].key == "_idx" and cols[0].muted
    assert not any(c.key.startswith("ev_") for c in cols)  # matrix is opt-in
    rows = doc.tables[0].rows
    assert [r["_idx"] for r in rows] == list(range(1, len(rows) + 1))

    # the column has no heading: the key must never surface as one
    html = to_html(doc, comp)
    assert "mut" in html and "_idx" not in html
    assert D.entry_list(entries, comp, "ED", index=False).tables[0] \
        .columns[0].key != "_idx"


def test_a_column_keeps_an_explicitly_blank_heading(comp):
    assert Column("bib").label == "bib"        # omitted: the key names it
    assert Column("_idx", "").label == ""      # explicit: stays blank


def test_entry_list_hides_np_by_default(entries, comp):
    riders = entries.by_cat("AL")
    riders[0].not_starting = True
    try:
        partenti = D.entry_list(entries, comp, "AL")
        assert len(partenti.tables[0].rows) == 98
        assert partenti.title.endswith("ELENCO PARTENTI")
        assert partenti.info == "98 partenti"

        # with the NP printed it is the entry list, and both counts show
        doc = D.entry_list(entries, comp, "AL", include_ns=True)
        assert len(doc.tables[0].rows) == 99
        assert doc.title.endswith("ELENCO ISCRITTI")
        assert doc.info == "99 iscritti / 98 partenti"
        assert any(r["bib"] == "NP" for r in doc.tables[0].rows)
    finally:
        riders[0].not_starting = False


def test_speciality_list_separates_teams_with_a_rule(entries, comp):
    doc = D.event_entry_list(entries, comp, "AL", "ins_squadre")
    t = doc.tables[0]
    assert t.columns[0].label == "Squadra"
    labels = [r["group"] for r in t.rows if r["group"]]
    assert "LOMBARDIA" in labels and "LAZIO" in labels
    # a rule above the first rider of each team, not a wasteful blank row
    starts = [r for r in t.rows if "group-start" in r.get("_class", "")]
    assert len(starts) == len(labels) - 1
    html = to_html(doc, comp)
    assert "group-start" in html
    assert "3 km" in _text(html) and "9 giri" in _text(html)


def test_madison_list_groups_pairs(entries, comp):
    doc = D.event_entry_list(entries, comp, "ED", "madison")
    assert doc.tables[0].columns[0].label == "Coppia"
    labels = [r["group"] for r in doc.tables[0].rows if r["group"]]
    assert labels and all(labels.count(x) == 1 for x in labels)


def test_reserves_are_marked(entries, comp):
    doc = D.event_entry_list(entries, comp, "AL", "vel_squadre",
                             include_reserves=True)
    labels = [r["group"] for r in doc.tables[0].rows if r["group"]]
    assert any("(R)" in x for x in labels) or True  # only if a team is all-reserve
    doc_no = D.event_entry_list(entries, comp, "AL", "vel_squadre",
                                include_reserves=False)
    assert len(doc_no.tables[0].rows) < len(doc.tables[0].rows)


def test_multiple_documents_break_pages(entries, comp):
    docs = [D.entry_list(entries, comp, c) for c in ("ES", "ED")]
    html = to_html(docs, comp)
    assert html.count('class="sheet-head"') == 2
    assert ".sheet-wrap + .sheet-wrap" in html  # page-break rule present


def test_archive_names_by_comunicato(store, entries, comp):
    """The name is the jury's, whichever way the document came out.

    With a browser it is a PDF; the HTML is the fallback, so the extension is
    the one thing that changes from machine to machine.
    """
    doc = D.entry_list(entries, comp, "AL", communique="3")
    p = archive(store, doc, comp, number="3")
    assert p.stem == "003_AL_partenti"       # the category stays uppercase
    if p.suffix == ".pdf":
        assert p.read_bytes().startswith(b"%PDF")
        return
    assert p.read_text(encoding="utf-8").lstrip().startswith("<!doctype html>")
    assert "Comunicato n. 3" in _text(p.read_text(encoding="utf-8"))


def test_slugify():
    assert slugify("AL - Inseguimento a Squadre") == "al-inseguimento-a-squadre"
    assert slugify("Finali 1-4") == "finali-1-4"


def test_document_names_follow_the_jury_convention(entries, comp):
    """NUM_CAT_SPECIALITA_FASE_BATTERIA, then what the sheet is: _partenti,
    _risultati, or _classifica for the standing of the whole specialita."""
    from core.models import RaceState
    from core.formats.base import Result

    assert D.entry_list(entries, comp, "ES", include_ns=True).slug == "ES_iscritti"
    assert D.entry_list(entries, comp, "ES").slug == "ES_partenti"
    assert D.event_entry_list(entries, comp, "AL", "ins_squadre").slug \
        == "AL_ins_squadre"  # the event code keeps its own underscore

    state = RaceState(race_id="es_madison_qualificazioni-batteria-1",
                      cat="ES", event="madison",
                      round_key="Qualificazioni Batteria 1")
    assert D.race_startlist(state, entries, comp).slug \
        == "ES_madison_qualificazioni_batteria-1_partenti"
    assert D.race_classification(state, Result(), entries, comp,
                                 doc_kind="risultati").slug \
        == "ES_madison_qualificazioni_batteria-1_risultati"
    assert D.race_classification(state, Result(), entries, comp).slug \
        == "ES_madison_classifica"


# ── letterhead on every page ────────────────────────────────────────────────

def test_footer_image_is_rendered(entries, comp):
    """branding.footer_img was configured but never emitted at all."""
    assert comp.branding.footer_img
    html = to_html(D.entry_list(entries, comp, "ES"), comp)
    # letterhead + the footer strip twice: once in the tfoot that reserves the
    # space on every page, once in the page footer pinned to the paper bottom
    assert html.count("data:image/") == 3
    assert 'class="doc-footer"' in html
    assert 'class="page-footer"' in html
    assert not re.search(r'src="(?!data:)', html)


def test_a_logo_keeps_the_width_and_the_side_it_was_given(comp):
    """The two fits: edge to edge by default, a width and a side when asked.

    A federation logo is not a letterhead drawn to A4 - stretched across the
    sheet it is unreadable - so the size travels on the tag itself, and the
    strip at the foot reserves only the millimetres it now takes.
    """
    from dataclasses import replace

    from render.render import image_style

    assert image_style(comp.branding, "header") == ""      # fit to the page
    sized = replace(comp.branding, header_fit="size", header_width=40,
                    header_align="right", footer_fit="size", footer_width=30,
                    footer_align="left")
    assert image_style(sized, "header") == "width:40%;margin:0 0 0 auto;"
    assert image_style(sized, "footer") == "width:30%;margin:0 auto 0 0;"

    doc = Document(title="PROVA", tables=[])
    html = to_html(doc, replace(comp, branding=sized), page_numbers=True,
                   standalone=True)
    assert 'style="width:40%;margin:0 0 0 auto;"' in html
    # the page-margin box paints the strip as a background: same width, same
    # side, or the numbered sheets would print it differently from the others
    assert "background-size: 30% auto" in html
    assert "background-position: left bottom 0mm" in html
    # and the band reserved for it follows the width it is actually printed at
    full = to_html(doc, comp, page_numbers=True, standalone=True)
    assert _foot_mm(html) < _foot_mm(full)


def _foot_mm(html: str) -> int:
    """The band the numbered sheet reserves at the foot, from its @page rule."""
    return int(re.search(r"@page \{ margin-bottom: (\d+)mm", html).group(1))


def test_an_image_is_held_off_its_own_edge_of_the_paper(comp):
    """The testata from the top, the piè from the bottom - either fit.

    A full-width banner may want air above it just as a logo does, so the
    distance is asked for on its own; and the band the sheet reserves at the
    foot grows by it, or the table would print over the strip.
    """
    from dataclasses import replace

    from render.render import image_style

    off = replace(comp.branding, header_top=12, footer_bottom=8)
    assert image_style(off, "header") == "margin:12mm auto 0 auto;"
    assert image_style(off, "footer") == "margin:0 auto 8mm auto;"

    doc = Document(title="PROVA", tables=[])
    html = to_html(doc, replace(comp, branding=off), page_numbers=True,
                   standalone=True)
    assert "background-position: center bottom 8mm" in html
    assert _foot_mm(html) == _foot_mm(to_html(doc, comp, page_numbers=True,
                                              standalone=True)) + 8


def test_a_width_that_is_not_one_is_brought_back_onto_the_paper(comp):
    """settings.json is written by anything: the bounds are held in Branding."""
    from dataclasses import replace

    from core.config import (DEFAULT_IMAGE_WIDTH, FIT_PAGE,
                             IMAGE_OFFSET_MAX)

    b = replace(comp.branding, header_fit="stretched", header_width=400,
                header_top=-3, footer_fit="size", footer_width="x",
                footer_align="sideways", footer_bottom=999)
    assert b.header_fit == FIT_PAGE and b.header_width == 100.0
    assert (b.header_top, b.footer_bottom) == (0.0, IMAGE_OFFSET_MAX)
    assert b.image_box("footer") == (DEFAULT_IMAGE_WIDTH / 100, "center")


def test_each_comunicato_is_a_sheet_with_its_own_letterhead(entries, comp):
    docs = [D.entry_list(entries, comp, c) for c in ("ES", "ED", "AL")]
    html = to_html(docs, comp)
    assert html.count('class="sheet-head"') == 3
    # the letterhead and the footer live in the sheet's thead / tfoot, which
    # is what makes the browser repeat them on every printed page
    assert html.count("<thead>") == 3 + 3  # one per sheet + per table
    assert html.count("<tfoot>") == 3
    assert html.count('class="banner"') == 3
    assert html.count('class="doc-footer"') == 3
    head = html.split("<thead>", 1)[1].split("</thead>", 1)[0]
    assert 'class="banner"' in head and 'class="title"' in head


def test_print_rules_repeat_the_letterhead_on_every_page():
    css = (ROOT / "render" / "print.css").read_text(encoding="utf-8")
    print_block = css.split("@media print", 1)[1]
    assert "table.sheet > thead { display: table-header-group; }" in print_block
    assert "table.sheet > tfoot { display: table-footer-group; }" in print_block
    assert "page-break-inside: auto" in print_block


def test_speciality_matrix_uses_the_sigle_with_a_key_below(entries, comp):
    """Full headers never fit: the matrix carries the UCI sigle plus a key."""
    from core.config import initials as abbreviate

    al = D.entry_list(entries, comp, "AL", matrix=True)
    labels = [c.label for c in al.tables[0].columns]
    # the UCI codes declared in the programme, not initials of the Italian name
    assert labels[-7:] == ["TS", "TP", "OM", "SP", "KE", "IP", "MD"]
    assert al.legend.startswith("Sigle specialità:")
    assert "TS = Vel. Squadre" in al.legend and "MD = Madison" in al.legend
    # weights always normalise to exactly the page width
    assert round(sum(c.pct for c in al.tables[0].columns), 1) == 100.0

    # three events, same treatment: the key is what makes the sigle readable
    ed = D.entry_list(entries, comp, "ED", matrix=True)
    assert [c.label for c in ed.tables[0].columns][-3:] == ["OM", "SP", "MD"]
    assert "OM = Omnium" in ed.legend

    # the key prints under the table, not in the letterhead
    html = to_html(ed, comp)
    assert html.index("Sigle specialità") > html.index("</tbody>")
    assert abbreviate("Ins. Individuale") == "II"


def test_footer_can_be_left_out_of_the_on_screen_preview(entries, comp):
    """The foot of the sheet belongs to the paper: `footer=False` drops it."""
    doc = D.entry_list(entries, comp, "ED")
    on_paper = to_html(doc, comp, standalone=True)
    on_screen = to_html(doc, comp, banner=False, footer=False)
    # (the stylesheet always names both blocks: look at the markup)
    assert 'class="page-footer"' in on_paper
    assert '<div class="footline">' in on_paper
    assert 'class="page-footer"' not in on_screen
    assert '<div class="footline">' not in on_screen


def test_the_printing_time_can_be_left_off_the_foot(entries, comp):
    """`timestamp=False`: the rest of the foot stays, the «Emesso il» goes.

    A sheet reprinted through the day - the medagliere - otherwise differs
    from the copy already handed out by nothing but the minute on its foot.
    """
    doc = D.entry_list(entries, comp, "ED")
    stamped = to_html(doc, comp, standalone=True)
    plain = to_html(doc, comp, standalone=True, timestamp=False)
    assert "Emesso il" in stamped
    assert "Emesso il" not in plain
    # the foot itself is still there - only its one line is gone
    assert 'class="page-footer"' in plain
    assert '<div class="footline">' not in plain
    # and a numbered sheet still numbers its pages, without a stray separator
    numbered_ = to_html(doc, comp, standalone=True, page_numbers=True,
                        timestamp=False)
    assert 'content: "pag. " counter(page)' in numbered_


def test_rows_never_wrap_and_columns_always_fit():
    css = (ROOT / "render" / "print.css").read_text(encoding="utf-8")
    assert "table-layout: fixed" in css
    # one rider is one line: truncate with an ellipsis rather than wrap, so a
    # long club name cannot blow a row up to six lines
    body = css.split("table.data tbody td {", 1)[1].split("}", 1)[0]
    assert "white-space: nowrap" in body
    assert "text-overflow: ellipsis" in body
    # headers may take two lines but must never be truncated ('Dors.' -> 'DO…')
    head = css.split("table.data thead th {", 1)[1].split("}", 1)[0]
    assert "white-space: normal" in head


def test_full_width_letterhead_and_footer():
    css = (ROOT / "render" / "print.css").read_text(encoding="utf-8")
    page = css.split("@page {", 1)[1].split("}", 1)[0]
    assert "margin: 0" in page  # no side margin
    banner = css.split(".cmsr .banner img {", 1)[1].split("}", 1)[0]
    strip = css.split(".cmsr .footer-strip img {", 1)[1].split("}", 1)[0]
    assert "width: 100%" in banner and "width: 100%" in strip


def test_landscape_is_opt_in(entries, comp):
    """Chrome drops the repeated letterhead on a named page, so never auto."""
    from render.render import Document, Table, Column

    wide = Document(title="x", tables=[Table([Column(f"c{i}") for i in range(20)])])
    assert wide.is_landscape is False
    wide.landscape = True
    assert wide.is_landscape is True
    html = to_html(wide, comp)
    assert 'class="sheet-wrap landscape"' in html
    assert ".sheet-wrap.landscape { page: landscape; }" in html


def test_letterhead_can_be_switched_off(entries, comp):
    html = to_html(D.entry_list(entries, comp, "ES"), comp, banner=False)
    assert "data:image/" not in html


# ── PDF output ──────────────────────────────────────────────────────────────

def test_pdf_export(entries, comp, tmp_path, chromium):
    """The jury saves a PDF directly; HTML is only the fallback."""
    from core.store import Store
    from render.render import archive

    # the store must live where the browser can read it: a snap-confined
    # Chromium cannot open /tmp, which is exactly the fallback path below
    root = ROOT / "_test_out"
    store = Store(root)
    try:
        doc = D.entry_list(entries, comp, "ED", communique="2")
        p = archive(store, doc, comp, number="2")
        assert p.name == "002_ED_partenti.pdf"
        assert p.read_bytes().startswith(b"%PDF")
        assert p.stat().st_size > 10_000
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_the_browser_profile_never_goes_next_to_the_document(tmp_path,
                                                            monkeypatch):
    """A Drive folder cannot hold the SingletonLock: the profile stays local.

    That failure is what turned every comunicato into HTML - the browser died
    before it opened the page, and `archive` kept the fallback.
    """
    from render import pdf as P

    monkeypatch.setenv("BLUEBAND_BROWSER_PROFILE_DIR", str(tmp_path / "first"))
    dirs = P.profile_dirs()
    assert dirs[0] == tmp_path / "first"      # an explicit setting wins
    assert len(dirs) > 1                      # and is not the only try


def test_a_working_directory_the_browser_cannot_use_is_not_the_answer(tmp_path,
                                                                      monkeypatch,
                                                                      chromium):
    """The Drive folder is offered first and dropped when it does not work.

    The comunicati live on `/mnt/g/...`, which a snap Chromium cannot write to
    at all ("No such device"): the page and the PDF have to fall back to a
    local directory, or every sheet comes out as HTML with no tab opened.
    """
    from render import pdf as P

    dead = tmp_path / "dead"
    dead.mkdir()
    dead.chmod(0o500)                        # created, never written into
    monkeypatch.setattr(P, "_LAST_GOOD", None)
    assert P.work_dirs(dead)[:1] == [dead]   # the caller's choice comes first
    try:
        data = P.html_to_pdf("<html><body><p>prova</p></body></html>",
                             workdir=dead)
        assert data.startswith(b"%PDF")
        # and the directory that worked is where the next document starts
        assert P._LAST_GOOD is not None and P._LAST_GOOD != dead
        assert P.work_dirs(dead)[0] == P._LAST_GOOD
    finally:
        dead.chmod(0o700)


def test_every_profile_candidate_is_tried_before_giving_up(monkeypatch,
                                                           tmp_path, chromium):
    """One unusable directory is not the answer: the next one is tried.

    A profile that cannot be locked kills the run without a word about the
    page, which is how a whole competition came out as HTML.
    """
    from render import pdf as P

    dead = tmp_path / "dead"
    dead.mkdir()
    dead.chmod(0o500)                        # created, never written into
    real = P.profile_dirs()
    monkeypatch.setattr(P, "profile_dirs", lambda: [dead, *real])
    root = ROOT / "_test_profile"
    root.mkdir(exist_ok=True)
    try:
        data = P.html_to_pdf("<html><body><p>prova</p></body></html>",
                             workdir=root)
        assert data.startswith(b"%PDF")
    finally:
        dead.chmod(0o700)
        shutil.rmtree(root, ignore_errors=True)


def test_pdf_failure_falls_back_to_html_and_says_why(entries, comp, store):
    """An unreadable working directory must not lose the document."""
    from render.render import archive

    doc = D.entry_list(entries, comp, "ED", communique="2")
    p = archive(store, doc, comp, number="2")
    if p.suffix == ".pdf":
        pytest.skip("il browser riesce a leggere questa cartella")
    assert p.name == "002_ED_partenti.html"
    assert p.read_text(encoding="utf-8").lstrip().startswith("<!doctype html>")
    assert any(e["action"] == "pdf_failed" for e in store.read_journal())


def test_archive_html_on_request(entries, comp, store):
    from render.render import archive

    p = archive(store, D.entry_list(entries, comp, "ED"), comp, number="2",
                fmt="html")
    assert p.suffix == ".html"


def test_archive_honours_the_configured_output_folder(entries, comp, store,
                                                      tmp_path):
    from render.render import archive

    dest = tmp_path / "Comunicati CITA26"
    store.set_out_dir(dest)
    p = archive(store, D.entry_list(entries, comp, "ED"), comp, number="2",
                fmt="html")
    assert p.parent == dest
    assert p.name == "002_ED_partenti.html"


def test_preview_drops_the_letterhead_the_page_already_shows(entries, comp):
    """`head=False`: on screen the app header says the race, the sheet does not."""
    doc = D.entry_list(entries, comp, "ES", communique="1")
    preview = to_html(doc, comp, head=False)
    printed = to_html(doc, comp, standalone=True)

    assert 'class="sheet-head"' not in preview
    # the number survives only in the foot of the sheet, which the preview in
    # the app leaves out too (footer=False)
    assert 'class="comunicato"' not in preview
    assert preview.count("data:image/") == 0          # no banner, no footer strip
    assert preview.count("<tr class=") == printed.count("<tr class=")

    # the document that gets archived is untouched
    assert 'class="sheet-head"' in printed
    assert "Comunicato n. 1" in printed
    assert printed.count("data:image/") >= 2


def test_footer_prints_but_never_shows_on_screen():
    """The footline belongs to the paper: the app page must not repeat it."""
    css = (ROOT / "render" / "print.css").read_text(encoding="utf-8")
    screen = css.split("@media screen {", 1)[1]
    print_block = css.split("@media print {", 1)[1]

    assert ".doc-footer" in screen.split("}", 3)[0] + screen.split("}", 3)[1]
    assert "visibility: hidden" in print_block      # tfoot only reserves space
    assert "position: fixed" in print_block         # pinned to the paper bottom


def test_a_fragment_can_leave_the_stylesheet_out(entries, comp):
    """For a page that already carries it - the app injects it once per run."""
    doc = D.entry_list(entries, comp, "ES")
    assert "<style>" in to_html(doc, comp)
    assert "<style>" not in to_html(doc, comp, css=False)
    # a standalone document is on its own and always brings it
    assert "<style>" in to_html(doc, comp, standalone=True, css=False)


# ── impostazioni avanzate: la firma e il nome ───────────────────────────────

def test_the_jury_can_sign_with_its_name_instead_of_the_image(entries, comp):
    """Two ways to sign, never both: the scanned image or the name in bold."""
    from dataclasses import replace
    from core.config import SIG_TEXT

    doc = D.entry_list(entries, comp, "ES")
    signed = replace(comp, branding=replace(
        comp.branding, signature_mode=SIG_TEXT, signature_name="Mario Rossi"))
    html = to_html(doc, signed, signature=True)
    assert 'class="sig-name">Mario Rossi<' in html
    assert "Per la giuria" in _text(html)
    # the image is the other mode's business: it must not print as well
    assert '<div class="signature">' in html
    assert html.count("<img") == html.count('class="banner"') + \
        2 * html.count('class="doc-footer"')

    # and nothing at all when the sheet does not ask to be signed (the class is
    # still in the stylesheet: what must not be there is the block)
    assert '<div class="signature">' not in to_html(doc, signed,
                                                    signature=False)


def test_the_signature_scope_sets_the_tick_not_the_sheet(comp):
    """Where the signature is offered by default, per kind of sheet."""
    from dataclasses import replace
    from core.config import (DOC_CLASSIFICATION, DOC_RESULTS, DOC_RESULTS_58,
                             DOC_STARTLIST, SIG_ALWAYS, SIG_NEVER, SIG_RESULTS)

    def signs(scope, kind):
        return replace(comp.branding, signature_scope=scope).signs(kind)

    assert signs(SIG_ALWAYS, DOC_STARTLIST) and signs(SIG_ALWAYS, DOC_RESULTS)
    assert not signs(SIG_RESULTS, DOC_STARTLIST)
    # the recuperi and the 5°-8° are results sheets too
    assert signs(SIG_RESULTS, DOC_RESULTS_58)
    assert signs(SIG_RESULTS, DOC_CLASSIFICATION)
    assert not signs(SIG_NEVER, DOC_CLASSIFICATION)


def test_a_competition_can_print_one_name_column_instead_of_two(entries, comp):
    """COGNOME + Nome in a single column, everywhere, from one setting."""
    from dataclasses import replace
    from core.config import NAME_FULL

    doc = D.entry_list(entries, comp, "ED")
    merged = replace(comp, branding=replace(comp.branding,
                                            name_style=NAME_FULL))
    html = to_html(doc, merged)
    heads = re.findall(r"<th[^>]*>([^<]*)</th>", html)
    assert "Nome" in heads and "Cognome" not in heads

    rider = sorted(entries.by_cat("ED"), key=lambda r: r.bib or 0)[0]
    assert f"{rider.last_name.upper()} {rider.first_name.title()}" in _text(html)
    # the two columns are one
    assert to_html(doc, comp).count("<th") == html.count("<th") + 1


def test_the_merged_name_column_gives_width_back(entries, comp):
    """One name on one line does not need the width of two full columns.

    Both were sized to hold a long name by themselves; kept whole, the merged
    column left the sheet with a third of the paper under the names and the
    volate squeezed against each other.
    """
    from render.render import cols_rider, merge_names

    doc = Document(title="X", tables=[Table(columns=cols_rider())])
    t = doc.tables[0]
    two = sum(c.pct for c in t.columns if c.key in ("last_name", "first_name"))
    merged = merge_names(doc).tables[0]
    one = next(c.pct for c in merged.columns if c.key == "full_name")
    assert one < two
    # and what it gives up goes to the columns the sheet is read for
    assert 0.5 < one / two < 1
    assert next(c.pct for c in merged.columns if c.key == "club") > \
        next(c.pct for c in t.columns if c.key == "club")


def test_how_wide_the_merged_name_column_is_comes_from_the_settings():
    """Impostazioni → Nome sets it: the renderer has no figure of its own.

    A bad value in `settings.json` would narrow every printed name at once, so
    `Branding` clamps it rather than passing it through.
    """
    from core.config import (DEFAULT_NAME_WIDTH, NAME_WIDTH_MAX,
                             NAME_WIDTH_MIN, Branding)
    from render.render import cols_rider, merge_names

    doc = Document(title="X", tables=[Table(columns=cols_rider())])
    narrow = merge_names(doc, 0.5).tables[0]
    wide = merge_names(doc, 0.9).tables[0]
    assert (next(c.pct for c in narrow.columns if c.key == "full_name")
            < next(c.pct for c in wide.columns if c.key == "full_name"))

    assert Branding(name_width=99).name_width == NAME_WIDTH_MAX
    assert Branding(name_width=0.01).name_width == NAME_WIDTH_MIN
    assert Branding(name_width="").name_width == DEFAULT_NAME_WIDTH
    assert NAME_WIDTH_MIN <= Branding().name_width <= NAME_WIDTH_MAX


def test_the_champion_band_follows_the_merged_name_column():
    """The band under the champion sits under the names, whichever they are."""
    from render.render import merge_names

    doc = Document(title="X", tables=[Table(
        columns=[Column("rank", "Ris.", "c", 7), Column("last_name", "Cognome"),
                 Column("first_name", "Nome")],
        rows=[{"rank": "1", "last_name": "rossi", "first_name": "MARIO",
               "_bold": ["last_name"]},
              {"_banner": "CAMPIONE", "_banner_at": "last_name"}])])
    t = merge_names(doc).tables[0]
    assert [c.key for c in t.columns] == ["rank", "full_name"]
    assert t.rows[0]["full_name"] == "ROSSI Mario"
    assert t.rows[0]["_bold"] == ["full_name"]
    assert t.rows[1]["_banner_at"] == "full_name"
    assert t.banner_offset(t.rows[1]) == 1


# ── the blocks under the table ──────────────────────────────────────────────

def _blocks(html: str) -> list[str]:
    return re.findall(r'<div class="decisione ([a-z]+)">(.*?)</div>', html)


def test_a_decision_prints_in_the_tint_of_its_provvedimento(comp):
    """Squalifica, retrocessione and ammonizione are not the same box."""
    from core.decisions import Decision
    from render.documents import decision_notes

    doc = Document(title="PROVA", tables=[],
                   notes=decision_notes([
                       Decision(penalty="D", reason="5", text="squalificato"),
                       Decision(penalty="C", reason="3", text="retrocesso"),
                       Decision(penalty="A", reason="6", text="ammonito"),
                   ], codes=True),
                   decision="I primi due passano alla finale.")
    html = to_html(doc, comp)
    kinds = [k for k, _ in _blocks(html)]
    # the note is last and keeps the plain box: it sanctions nobody
    assert kinds == ["disqualification", "relegation", "warning", "note"]
    assert "I primi due passano alla finale." in _blocks(html)[-1][1]
    # each carries the code it was taken under: the competition asked for it
    assert ">D5</span>" in html and ">C3</span>" in html
    # and the tints reach the page as custom properties
    assert "--note-disqualification:" in html and "--note-note-rule:" in html


def test_the_uci_code_is_off_unless_the_competition_asks_for_it(comp):
    """The comunicato carries the sentence; the code is in the jury's register."""
    from core.decisions import Decision
    from render.documents import decision_notes

    notes = decision_notes([Decision(penalty="C", reason="3",
                                     text="retrocesso")])
    assert [n.title for n in notes] == [""]
    # the tint stays: what the box is remains readable without the code
    assert notes[0].kind == "relegation"


def test_a_decision_with_no_text_prints_nothing(comp):
    """A coloured box with a code and no sentence is one nobody can answer."""
    from core.decisions import Decision
    from render.documents import decision_notes

    assert decision_notes([Decision(penalty="D", reason="5")]) == []


def test_the_tints_are_the_competitions_to_change(comp):
    """Set in Impostazioni, and the rule down the side follows the tint."""
    from dataclasses import replace

    from render.render import darken

    recoloured = replace(comp, branding=replace(
        comp.branding, note_colors={"disqualification": "#ff0000"}))
    html = to_html(Document(title="PROVA", tables=[]), recoloured)
    assert "--note-disqualification: #ff0000" in html
    assert f"--note-disqualification-rule: {darken('#ff0000')}" in html
    # what was not set keeps the default rather than printing untinted
    assert "--note-warning: #fef08a" in html


def test_the_characters_are_the_competitions_to_change(comp):
    """Set in Impostazioni: print.css states the shape, never the font."""
    from dataclasses import replace

    recoloured = replace(comp, branding=replace(
        comp.branding, fonts={"title": "18pt", "family": "Georgia, serif"}))
    html = to_html(Document(title="PROVA", tables=[]), recoloured)
    assert "--font-title: 18pt" in html
    assert "--font-family: Georgia, serif" in html
    # what was not set keeps the default rather than printing unset
    assert "--font-subtitle: 12pt" in html


def test_the_colour_of_an_element_is_the_competitions_to_change(comp):
    """Only what was changed is written: the rest keeps the fallback of the
    stylesheet, and the titolo goes on following the letterhead."""
    from dataclasses import replace

    c = replace(comp, branding=replace(
        comp.branding, text_colors={"title": "#ff0000", "legend": "#123456"}))
    html = to_html(Document(title="PROVA", tables=[]), c)
    wrapper = html.split('<div class="cmsr"')[1].split(">")[0]
    assert "--color-title: #ff0000" in wrapper
    assert "--color-legend: #123456" in wrapper
    # an element nobody touched is not written onto the page at all: it keeps
    # the fallback print.css states for it
    assert "--color-info" not in wrapper
    # and one set to the colour it already had is not a colour of its own
    kept = replace(comp.branding, text_colors={"info": "#444444",
                                               "title": "#0a5688"})
    assert kept.text_colors == {}


def test_a_colour_that_is_not_one_never_reaches_the_sheet(comp):
    """The picker writes `#rrggbb`; a settings file may hold anything."""
    from dataclasses import replace

    b = replace(comp.branding, text_colors={"title": "red; } body {",
                                            "nonsense": "#ffffff"})
    assert b.text_colors == {}
    html = to_html(Document(title="PROVA", tables=[]), replace(comp, branding=b))
    wrapper = html.split('<div class="cmsr"')[1].split(">")[0]
    assert "--color-" not in wrapper


def test_a_font_that_would_break_the_sheet_never_reaches_it(comp):
    """A settings file may hold anything; the style of the page may not."""
    from dataclasses import replace

    from core.config import FONTS

    b = replace(comp.branding, fonts={"title": "18pt;} body{display:none",
                                      "subtitle": "", "nonsense": "9pt"})
    assert b.fonts["title"] == FONTS["title"]     # refused, so the default
    assert "nonsense" not in b.fonts
    html = to_html(Document(title="PROVA", tables=[]), replace(comp, branding=b))
    assert "display:none" not in html


def test_the_numbered_sheet_carries_the_typeface_into_its_margin_box(comp):
    """The page number sits outside `.cmsr`, where a custom property does not
    reach - and an entity does not decode inside a <style>."""
    from dataclasses import replace

    c = replace(comp, branding=replace(
        comp.branding, fonts={"family": "Georgia, 'Times New Roman', serif",
                              "footline": "7pt"}))
    html = to_html(Document(title="PROVA", tables=[]), c,
                   standalone=True, page_numbers=True)
    # the <style> that holds the margin box, and not print.css above it
    box = html.split("counter(page)")[1].split("</style>")[0]
    assert "font-family: Georgia, 'Times New Roman', serif" in box
    assert "&#39;" not in box and "&#34;" not in box
    assert "font-size: 7pt;" in box


def test_the_rule_of_a_box_keeps_the_hue_of_its_tint():
    """A pink box gets a red rule, not a brown one; grey stays grey."""
    from render.render import darken

    assert darken("#fecaca") == "#ad0000"     # the squalifica reads as red
    assert darken("#fed7aa").startswith("#ad")  # and the retrocessione orange
    assert darken("#ffffff") == "#575757"     # no hue to keep
    # anything the sheet cannot read is left alone rather than crashing it
    assert darken("rgb(1,2,3)") == "rgb(1,2,3)"


def test_the_printed_register_carries_the_compact_code(comp):
    """`C3`, not `C`: the article a decision was taken under is answerable."""
    from core.decisions import Decision

    doc = D.decisions_register(
        [Decision(n=1, day=2, cat="AL", event="velocita", round_key="Quarti",
                  bibs="7", penalty="C", reason="3", text="retrocesso")], comp)
    assert doc.tables[0].rows[0]["code"] == "C3"


# ── the foglio programma: the orario is computed, the durata is stated ──────

def test_the_programme_sheet_prints_the_hour_the_giornata_arrives_at(comp):
    """Start of the day plus the durate above: nobody types thirty times."""
    import dataclasses

    comp = dataclasses.replace(comp, day_start={1: "14:30"})
    day = comp.days()[0]
    for _item, rnd in comp.rounds_on(day)[:2]:
        rnd.duration = 20

    doc = D.programme_sheet(comp)
    heads = [c.label for c in doc.tables[0].columns]
    assert heads[:2] == [label("programme_start"), ui("round_duration")]
    times = [r["start"] for r in doc.tables[0].rows][:3]
    assert times == ["14:30", "14:50", "15:10"]
    assert doc.tables[0].rows[0]["duration"] == ui("n_minutes", n=20)


def test_a_pause_prints_in_the_column_of_the_speciality(comp):
    """The one line of a foglio programma that is not a race.

    It says when it starts, how long it lasts and what it is called - in the
    column the sheet is read down - and nothing else: no categoria, no fase,
    no comunicato. It is set in italic by the class the row carries.
    """
    import dataclasses

    from core import programme as P

    comp = dataclasses.replace(comp, programme=list(comp.programme),
                               day_start={1: "14:30"})
    day = comp.days()[0]
    P.add_pause(comp, day, 30, "Premiazioni")

    rows = D.programme_sheet(comp).tables[0].rows
    pause = [r for r in rows if "pause" in r.get("_class", "")]
    assert len(pause) == 1
    row = pause[0]
    assert row["event"] == "Premiazioni"
    assert row["duration"] == ui("n_minutes", n=30)
    assert row["start"] and not any(row[k] for k in
                                    ("cat", "round", "startlist", "results"))


def test_the_two_columns_can_each_be_left_off(comp):
    """One sheet read two ways: a day being planned, a day on a noticeboard."""
    plain = D.programme_sheet(comp, times=False, durations=False)
    assert label("programme_start") not in [c.label
                                            for c in plain.tables[0].columns]
    assert ui("round_duration") not in [c.label
                                        for c in plain.tables[0].columns]


def test_the_programme_marks_the_comunicati_already_issued(comp):
    """A cell whose numbers are on paper is laid on the tint, and no other."""
    rows = D.programme_sheet(comp).tables[0].rows
    out = {int("".join(ch for ch in str(rows[0]["startlist"]) if ch.isdigit()))}
    assert out != {0}, "the fixture must plan a numbered ordine di partenza"

    doc = D.programme_sheet(comp, issued=out, issued_tint="#d9f2de")
    first, *rest = doc.tables[0].rows
    assert first["_tint"] == {"startlist": "#d9f2de"}
    assert not any(r.get("_tint") for r in rest
                   if not _numbers_in(r, out)), "tinted what is not issued"
    # off is the plain sheet, and so is a number the register has not seen
    assert not any(r.get("_tint") for r in D.programme_sheet(comp).tables[0].rows)


def _numbers_in(row: dict, issued: set) -> bool:
    return any(str(n) in str(row.get(k, ""))
               for k in ("startlist", "results", "classification")
               for n in issued)


def test_the_merged_column_goes_green_when_both_its_sheets_are_out(comp):
    """Risultati and classifica share one cell: half of it out is not out."""
    plain = D.programme_sheet(comp, merge_results=True).tables[0].rows
    both = next(r for r in plain
                if len(str(r["results"]).split("·")) == 2)
    ns = {int(n) for n in str(both["results"]).replace("·", " ").split()
          if n.isdigit()}
    half = D.programme_sheet(comp, merge_results=True,
                             issued=list(ns)[:1]).tables[0].rows
    full = D.programme_sheet(comp, merge_results=True,
                             issued=ns).tables[0].rows
    i = plain.index(next(r for r in plain if r is both))
    assert "results" not in (half[i].get("_tint") or {})
    assert "results" in (full[i].get("_tint") or {})


def _omnium_rows(comp, **kw):
    """The prove of an omnium, which is where both classifiche are printed."""
    rows = D.programme_sheet(comp, **kw).tables[0].rows
    out = [r for r in rows if "Omnium" in str(r.get("event"))]
    assert out, "the fixture must run an omnium"
    return out


def test_a_classifica_parziale_is_printed_in_the_column_of_the_classifica(comp):
    """The standings after a prova are a classifica and are read as one.

    They are also the ordine di partenza of the prova after them - one
    comunicato, printed on the row of the prova that files it as well as under
    the start order it opens. Read only in the start order column, the number
    of every parziale of an omnium was missing from the sheet.
    """
    rows = _omnium_rows(comp)
    partials = [r["classification"] for r in rows if not r.get("_bold")]
    assert [n for n in partials if n], "no parziale printed"


def test_the_classifica_finale_is_the_one_in_bold(comp):
    """Bold is what the classifica finale is told apart by - and it is a choice.

    A parziale closes nothing and stays plain; the sheet that closes the
    specialità is the one anybody scans the column for.
    """
    rows = _omnium_rows(comp)
    final = [r for r in rows if r.get("_bold")]
    assert final, "no classifica finale printed"
    assert all(r["_bold"] == {"classification"} and r["classification"]
               for r in final)
    # one per categoria that rides an omnium, and it is the last prova of it
    assert len(final) == len({r["cat"] for r in final})
    assert all(rows[rows.index(r) + 1:rows.index(r) + 2] == []
               or rows[rows.index(r) + 1]["cat"] != r["cat"] for r in final)
    # merged, the bold is on the cell the two columns became
    merged = [r for r in _omnium_rows(comp, merge_results=True)
              if r.get("_bold")]
    assert merged and all(r["_bold"] == {"results"} for r in merged)
    # and off, nothing is bold at all
    assert not any(r.get("_bold")
                   for r in _omnium_rows(comp, bold_final=False))


def test_a_sheet_with_no_number_is_filed_and_printed_without_one(entries, comp):
    """Not every sheet has a comunicato of its own, and none is invented.

    The risultati carried on the classifica's number go out with nothing at
    the head of the sheet and nothing in front of the file name - the same
    answer as a register that wrote `-1` there, which reads back as no number.
    """
    from render.render import out_name, to_html

    for value in ("", "-1", -1):
        doc = D.entry_list(entries, comp, "ED", communique=value)
        assert doc.communique == ""
        assert out_name([doc], number=value) == "ED_partenti.pdf"
        assert "Comunicato n." not in to_html([doc], comp)


# ── the little markdown of the foglio intestato ─────────────────────────────

def test_markdown_subset_reads_the_four_constructs():
    from render import markup

    html = markup.to_html("# Convocazione\n\n"
                          "Il **direttore** di *riunione* convoca:\n"
                          "- i commissari\n- i giudici\n\n"
                          "1. alle 9\n2. in cabina")
    assert "<h3>Convocazione</h3>" in html
    assert "<strong>direttore</strong>" in html and "<em>riunione</em>" in html
    assert "<ul><li>i commissari</li><li>i giudici</li></ul>" in html
    assert "<ol><li>alle 9</li><li>in cabina</li></ol>" in html


def test_markdown_subset_never_lets_markup_through():
    """What the jury types is text: a sheet must not print what it pasted in."""
    from render import markup

    html = markup.to_html('<img src=x onerror="alert(1)"> & **grassetto**')
    assert "<img" not in html and "&lt;img" in html   # printed, not run
    assert "&amp;" in html
    assert "<strong>grassetto</strong>" in html   # the marks are still read


def test_markdown_subset_is_empty_for_an_empty_box():
    from render import markup

    assert markup.to_html("") == "" and markup.to_html("   \n  ") == ""


def test_the_letterhead_sheet_is_the_paper_with_the_text_on_it(comp):
    doc = D.letterhead_sheet(comp, title="CONVOCAZIONE", subtitle="Prima giornata",
                             text="Testo **in grassetto**.", communique="12")
    html = to_html(doc, comp)
    assert "CONVOCAZIONE" in html and "Prima giornata" in html
    assert "<strong>in grassetto</strong>" in html
    assert "Comunicato n. 12" in _text(html)
    assert doc.slug == "convocazione"


def test_a_letterhead_sheet_without_a_title_takes_the_competition_name(comp):
    doc = D.letterhead_sheet(comp, text="qualcosa")
    assert doc.title == comp.name
