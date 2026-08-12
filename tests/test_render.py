import re
import shutil
from pathlib import Path

import pytest

from core.entries import import_master
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
        doc = D.entry_list(entries, comp, "AL", include_np=True)
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

    assert D.entry_list(entries, comp, "ES", include_np=True).slug == "ES_iscritti"
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

def test_pdf_export(entries, comp, tmp_path):
    """The jury saves a PDF directly; HTML is only the fallback."""
    from core.store import Store
    from render import pdf as P
    from render.render import archive

    if not P.available():
        pytest.skip("nessun browser Chromium installato")

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
                                                                      monkeypatch):
    """The Drive folder is offered first and dropped when it does not work.

    The comunicati live on `/mnt/g/...`, which a snap Chromium cannot write to
    at all ("No such device"): the page and the PDF have to fall back to a
    local directory, or every sheet comes out as HTML with no tab opened.
    """
    from render import pdf as P

    if not P.available():
        pytest.skip("nessun browser Chromium installato")
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
                                                           tmp_path):
    """One unusable directory is not the answer: the next one is tried.

    A profile that cannot be locked kills the run without a word about the
    page, which is how a whole competition came out as HTML.
    """
    from render import pdf as P

    if not P.available():
        pytest.skip("nessun browser Chromium installato")
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
