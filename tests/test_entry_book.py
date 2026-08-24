"""Building the elenco iscritti of a competition from what the federation sends.

The federal export is a flat list with no specialità in it; what a meeting is
run from is a workbook with a sheet per categoria and a column per specialità
of that categoria. These are about that translation - and about the two things
it must never get wrong: the dorsali, and the work already done in the file.
"""

import pytest

from conftest import EXAMPLE_ENTRIES, EXAMPLE_PROGRAMME
from core import entries as E
from core import entry_book as B
from core import entry_formats as F
from core import programme as P
from core.config import load_competition


@pytest.fixture
def comp():
    """A competition whose programme says nothing about its own file layout.

    Which is every competition being set up: the mapping used to have to be
    written into `entries:` by hand before anything could be imported at all,
    and now it comes from the format (`core.entry_formats`).
    """
    return F.applied(load_competition(EXAMPLE_PROGRAMME), "ksport")


@pytest.fixture
def master():
    """The same competition, read as the workbook *this app writes*.

    Two layouts and two jobs: the arriving file is a ksport export with its
    header five rows down, and what is built from it is ours - a sheet per
    categoria, the header on the first row.
    """
    return F.applied(load_competition(EXAMPLE_PROGRAMME), "master")


@pytest.fixture
def entries(comp):
    """The fictional field that ships with the repo (`example`).

    Which is the point of it being fictional: a real elenco is a few hundred
    minors' personal data and cannot be in the repo, so these used to run on
    the one laptop that has the Drive folder mounted and skip everywhere else.
    """
    return E.import_ksport_export(EXAMPLE_ENTRIES, comp)


# ── the format, which is what makes the file readable at all ────────────────

def test_a_competition_that_states_no_layout_is_read_by_the_format(comp):
    """Nothing had to be typed into `programme.yaml` for this to be readable."""
    bare = load_competition(EXAMPLE_PROGRAMME)
    assert not bare.entry_sheet.ksport, "the fixture is not testing anything"
    assert comp.entry_sheet.ksport["CodiceUci"] == "uci_id"
    assert comp.entry_sheet.check_in == {"Verificato": "checked_in",
                                         "NP": "not_starting"}


def test_what_a_programme_states_itself_wins_over_the_format(tmp_path):
    """A federation that renames a column is a line in the table; a meeting
    that reads a file of its own is a line in its programme."""
    written = tmp_path / "programme.yaml"
    written.write_text("name: Una riunione che legge un file suo\n"
                       "entries:\n"
                       "  ksport:\n"
                       '    "Tessera UCI": uci_id\n', encoding="utf-8")
    comp = load_competition(written)
    mine = dict(comp.entry_sheet.ksport)
    assert mine == {"Tessera UCI": "uci_id"}
    assert F.applied(comp, "ksport").entry_sheet.ksport == {
        **F.layout("ksport")["ksport"], **mine}


def test_the_sample_export_is_read_whole(entries):
    assert len(entries.riders) == 140
    assert not entries.warnings, "the example file must read without a complaint"
    assert {r.cat for r in entries.riders.values()} == {"ES", "ED", "AL", "DA",
                                                        "JU", "DJ"}


# ── the dorsali ─────────────────────────────────────────────────────────────

def test_a_file_that_numbers_nobody_is_not_a_file_with_numbers(entries):
    """All of them or none: a half-numbered file is one somebody has edited."""
    assert not B.has_bibs(entries)
    assert len(B.missing_bibs(entries)) == 1


def test_the_bibs_can_be_dealt_out_down_the_file(entries, comp):
    B.numbered(entries, comp, B.AS_IMPORTED)
    assert B.has_bibs(entries)
    assert sorted(r.bib for r in entries.riders.values()) == list(
        range(1, len(entries.riders) + 1))


def test_the_bibs_can_run_on_from_one_categoria_to_the_next(entries, comp):
    """1…N, N+1…M: one run, in the order the programme lists the categorie."""
    B.numbered(entries, comp, B.BY_CAT_RUNNING)
    assert B.has_bibs(entries)
    numbers = sorted(r.bib for r in entries.riders.values())
    assert numbers == list(range(1, len(numbers) + 1))
    first = [c for c in comp.cat_order()
             if any(r.cat == c for r in entries.riders.values())][0]
    assert min(r.bib for r in entries.riders.values() if r.cat == first) == 1
    # and no categoria interleaves with another
    for cat in comp.cat_order():
        bibs = sorted(r.bib for r in entries.riders.values() if r.cat == cat)
        if bibs:
            assert bibs == list(range(bibs[0], bibs[0] + len(bibs)))


def test_the_bibs_can_start_again_in_every_categoria(entries, comp):
    """Which is only usable where two categorie never line up together."""
    B.numbered(entries, comp, B.BY_CAT_RESTART)
    for cat in comp.cat_order():
        bibs = sorted(r.bib for r in entries.riders.values() if r.cat == cat)
        if bibs:
            assert bibs == list(range(1, len(bibs) + 1))


# ── the workbook ────────────────────────────────────────────────────────────

def test_the_workbook_has_the_federal_sheet_and_one_per_categoria(
        entries, comp, master, tmp_path):
    import openpyxl

    B.numbered(entries, comp, B.BY_CAT_RUNNING)
    out = B.build(entries, master, tmp_path / "Iscritti.xlsx")
    wb = openpyxl.load_workbook(out)
    assert wb.sheetnames[0] == B.KSPORT
    riding = [c for c in comp.cat_order() if B.events_of(comp, c)
              and any(r.cat == c for r in entries.riders.values())]
    assert wb.sheetnames[1:] == riding

    # one column per specialità that categoria rides, and the two the giuria
    # fills in - which the federation's own file has no place for. The header
    # is the first row: the empty ones above it in the federation's template
    # are a letterhead, and this file is ours.
    assert master.entry_sheet.header_row == 1
    ws = wb[riding[0]]
    headers = [c.value for c in ws[master.entry_sheet.header_row]]
    events = [comp.event(e).short for e in B.events_of(comp, riding[0])]
    assert headers[-len(events) - 2:] == events + ["Verificato", "NP"]


def test_the_workbook_is_read_back_by_the_importer(entries, comp, master,
                                                   tmp_path):
    """It is written to be read: the same importer, and nothing lost."""
    B.numbered(entries, comp, B.BY_CAT_RUNNING)
    out = B.build(entries, master, tmp_path / "Iscritti.xlsx")
    back = E.import_master(out, master)
    assert len(back.riders) == len(entries.riders)
    assert B.has_bibs(back)
    assert {r.full_name for r in back.riders.values()} == {
        r.full_name for r in entries.riders.values()}


def test_following_the_programme_keeps_the_work_already_done(
        entries, comp, master, tmp_path):
    """A specialità added is a column added, and nothing anybody ticked moves.

    Which is the whole reason the file is read back before it is written
    again: a rebuild that started from the export would throw away the
    iscrizioni, the dorsali and the verifica of everybody in it.
    """
    B.numbered(entries, comp, B.BY_CAT_RUNNING)
    out = B.build(entries, master, tmp_path / "Iscritti.xlsx")

    worked = E.import_master(out, master)
    rider = next(r for r in worked.riders.values() if r.cat == "ES")
    rider.events["omnium"] = E.EventEntry(starter=True)
    rider.checked_in = True
    B.build(worked, master, out)

    P.add_item(master, "ES", "eliminazione", 1)
    B.sync(out, master)

    import openpyxl
    ws = openpyxl.load_workbook(out)["ES"]
    headers = [c.value for c in ws[master.entry_sheet.header_row]]
    assert "Eliminazione" in headers
    back = E.import_master(out, master)
    kept = back.riders[rider.key]
    assert kept.events["omnium"].starter and kept.checked_in
    assert kept.bib == rider.bib
