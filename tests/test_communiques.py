"""The comunicato register: the CITA 26 plan, and issuing numbers at print time."""

import pytest

from core import communiques as C
from core.config import (DOC_ALL_KINDS, DOC_CLASSIFICATION, DOC_RESULTS,
                         DOC_STARTLIST, EVENT_ENTRY_LIST)


# ── the authored CITA 26 register ───────────────────────────────────────────

def test_planned_register_is_the_2026_numbering(comp):
    plan = C.planned(comp)
    assert len(plan) == 140
    assert [c.n for c in plan] == list(range(1, 141))


@pytest.mark.parametrize("cat,event,round_key,doc,n", [
    # every one of these was read off the number printed on a jury workbook
    ("ES", EVENT_ENTRY_LIST, "", DOC_STARTLIST, 1),
    ("DA", EVENT_ENTRY_LIST, "", DOC_STARTLIST, 4),
    ("ES", "madison", "Qualificazioni Batteria 1", DOC_STARTLIST, 5),
    ("AL", "ins_squadre", "Qualificazioni", DOC_STARTLIST, 7),
    ("AL", "ins_squadre", "Qualificazioni", DOC_RESULTS, 15),
    ("ED", "madison", "", DOC_CLASSIFICATION, 17),
    ("AL", "vel_squadre", "Finali", DOC_STARTLIST, 22),
    ("AL", "ins_squadre", "", DOC_CLASSIFICATION, 30),
    ("ES", "velocita", "Qualificazioni", DOC_STARTLIST, 33),
    ("ED", "omnium", "Scratch", DOC_STARTLIST, 39),
    ("AL", "keirin", "Turno 1", DOC_STARTLIST, 37),
    ("AL", "velocita", "Qualificazioni", DOC_RESULTS, 89),
    ("AL", "omnium", "", DOC_CLASSIFICATION, 115),
    ("AL", "madison", "Qualificazioni Batteria 1", DOC_STARTLIST, 123),
    ("DA", "madison", "", DOC_CLASSIFICATION, 140),
])
def test_find_returns_the_planned_number(comp, cat, event, round_key, doc, n):
    c = C.find(comp, cat, event, round_key, doc)
    assert c is not None, f"{cat} {event} {round_key} {doc} non è in registro"
    assert c.n == n


def test_ret_is_preserved(comp):
    ret = [c for c in comp.communiques if c.ret]
    assert [c.n for c in ret] == [93]
    assert ret[0].label == "93 RET"
    assert "Omnium" in ret[0].title


def test_generated_plan_covers_every_document(comp):
    plan = C.plan_from_programme(comp)
    assert len(plan) > len(comp.cat_order())
    assert [c.n for c in plan] == list(range(1, len(plan) + 1))
    assert plan[0].title == "Iscritti ES"
    assert all(c.doc in DOC_ALL_KINDS for c in plan)


# ── issuing ─────────────────────────────────────────────────────────────────

def test_issue_uses_the_planned_number(store, comp):
    e = C.issue(store, comp, cat="AL", event="ins_squadre",
                round_key="Qualificazioni", doc=DOC_STARTLIST)
    assert e.n == 7 and not e.ret
    assert e.issued_at
    assert [i.n for i in C.load(store)] == [7]


def test_issue_off_plan_takes_the_next_free_number(store, comp):
    e = C.issue(store, comp, cat="AL", event="velocita", round_key="Extra",
                doc=DOC_RESULTS, title="Turno supplementare")
    assert e.n == 141  # the plan ends at 140
    assert C.next_free(comp, C.load(store)) == 142


def test_issue_accepts_an_explicit_number_and_ret(store, comp):
    e = C.issue(store, comp, cat="AL", event="omnium",
                round_key="Qualificazioni Batteria 1", doc=DOC_RESULTS,
                number="93 RET")
    assert e.n == 93 and e.ret and e.label == "93 RET"


def test_reissuing_replaces_rather_than_duplicates(store, comp):
    C.issue(store, comp, cat="AL", event="ins_squadre", round_key="Qualificazioni",
            doc=DOC_STARTLIST)
    C.issue(store, comp, cat="AL", event="ins_squadre", round_key="Qualificazioni",
            doc=DOC_STARTLIST, file="007_x.html")
    register = C.load(store)
    assert len(register) == 1
    assert register[0].file == "007_x.html"
    assert C.duplicates(register) == []


def test_status_marks_what_has_been_issued(store, comp):
    C.issue(store, comp, cat="ES", event=EVENT_ENTRY_LIST, round_key="",
            doc=DOC_STARTLIST)
    rows = C.status(comp, C.load(store))
    assert len(rows) == 140
    assert rows[0]["issued"] is True
    assert rows[1]["issued"] is False


def test_status_lists_off_plan_documents_too(store, comp):
    C.issue(store, comp, cat="AL", event="velocita", round_key="Extra",
            doc=DOC_RESULTS, title="Turno supplementare")
    rows = C.status(comp, C.load(store))
    assert len(rows) == 141
    assert "fuori programma" in rows[-1]["title"]


# ── printable register ──────────────────────────────────────────────────────

def test_register_document(store, comp):
    from render.documents import comunicati_register
    from render.render import to_html

    C.issue(store, comp, cat="ES", event=EVENT_ENTRY_LIST, round_key="",
            doc=DOC_STARTLIST)
    rows = C.status(comp, C.load(store))
    doc = comunicati_register(rows, comp)
    html = to_html(doc, comp)
    assert "REGISTRO COMUNICATI" in html
    assert "140 documenti" in html
    assert "93 RET" in html
    assert html.count("<tr") >= 140


# ── what the Gare page pre-fills ────────────────────────────────────────────

def test_a_sheet_the_register_does_not_plan_opens_unnumbered(comp):
    """No number is better than another sheet's number.

    The register plans the risultati of each batteria and the classifica of the
    specialità; the risultati of a finale it does not carry. That field used to
    open on the first number planned for the same specialità - the batteria's -
    and the finale went out under it.
    """
    from core.communiques import UNNUMBERED, number_for

    def n(round_key, doc):
        return number_for(comp, "ES", "madison", round_key, doc)

    assert n("Qualificazioni Batteria 1", DOC_RESULTS) == "10"
    assert n("Finale", DOC_STARTLIST) == "12"
    # planned for the specialità, whatever fase is open
    assert n("Finale", DOC_CLASSIFICATION) == "18"
    assert n("Finale", DOC_RESULTS) == UNNUMBERED


@pytest.fixture
def rebuilt():
    """The register as the rules would write it, on a competition of its own.

    A copy, not the session fixture: rebuilding rewrites every entry, and the
    rest of the suite reads the authored CITA 26 register.
    """
    from conftest import programme_path
    from core.config import load_competition

    comp = load_competition(programme_path())
    comp.communiques = C.autonumber(comp, [], rebuild=True)
    return comp


def test_the_number_of_a_merged_sheet_goes_on_the_classification(rebuilt):
    """One comunicato, one number, and it is printed once.

    A madison is one finale and its classifica *is* that ordine d'arrivo: the
    two are one sheet on one number. Printed under both columns of the
    programme it read as two comunicati, so the number goes where people look
    it up - on the classifica - and the risultati under it carry none.
    """
    comp = rebuilt
    spec = next(c for c in comp.communiques
                if [s.doc for s in c.sheets] == [DOC_RESULTS,
                                                 DOC_CLASSIFICATION]
                and c.event == "madison")

    def n(doc, round_key=""):
        return C.number_for(comp, spec.cat, "madison", round_key, doc)

    assert n(DOC_CLASSIFICATION) == str(spec.n)
    assert n(DOC_RESULTS, spec.round_key) == C.UNNUMBERED

    # off, the sheets of the comunicato both print it - same number, twice
    comp.number_on_classification = False
    assert n(DOC_RESULTS, spec.round_key) == str(spec.n)


def test_the_start_order_carried_by_results_keeps_its_own_answer(rebuilt):
    """Only the classifica takes the number off another sheet.

    A velocità publishes the risultati of a turno with the ordine di partenza
    of the next: two sheets, one number, and the number is the risultati' -
    there is no classifica in it to move it onto.
    """
    comp = rebuilt
    spec = next(c for c in comp.communiques
                if c.event == "velocita" and c.doc == DOC_RESULTS
                and any(s.doc == DOC_STARTLIST for s in c.sheets[1:]))
    assert C.number_for(comp, spec.cat, "velocita", spec.round_key,
                        DOC_RESULTS) == str(spec.n)


@pytest.mark.parametrize("value, text", [
    ("7", "7"), (7, "7"), ("  12  ", "12"), ("92 RET", "92 RET"),
    # what a register written before this said for "no number", and what an
    # empty field says now
    ("-1", ""), (-1, ""), ("0", ""), ("", ""), (None, ""),
])
def test_no_number_reads_the_same_however_it_was_written(value, text):
    from core.models import number_text

    assert number_text(value) == text
