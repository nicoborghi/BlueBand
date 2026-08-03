"""The comunicato register: the CITA 26 plan, and issuing numbers at print time."""

import pytest

from core import communiques as C
from core.config import (DOC_ALL_KINDS, DOC_CLASSIFICATION, DOC_RESULTS,
                         DOC_STARTLIST, EVENT_ENTRY_LIST)


# ── the authored CITA 26 register ───────────────────────────────────────────

def test_planned_register_is_the_2026_numbering(comp):
    plan = C.planned(comp)
    assert len(plan) == 138
    assert [c.n for c in plan] == list(range(1, 139))


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
    ("AL", "velocita", "Qualificazioni", DOC_RESULTS, 88),
    ("AL", "omnium", "", DOC_CLASSIFICATION, 111),
    ("AL", "madison", "Qualificazioni Batteria 1", DOC_STARTLIST, 121),
    ("DA", "madison", "", DOC_CLASSIFICATION, 138),
])
def test_find_returns_the_planned_number(comp, cat, event, round_key, doc, n):
    c = C.find(comp, cat, event, round_key, doc)
    assert c is not None, f"{cat} {event} {round_key} {doc} non è in registro"
    assert c.n == n


def test_ret_is_preserved(comp):
    ret = [c for c in comp.communiques if c.ret]
    assert [c.n for c in ret] == [92]
    assert ret[0].label == "92 RET"
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
    assert e.n == 139  # the plan ends at 138
    assert C.next_free(comp, C.load(store)) == 140


def test_issue_accepts_an_explicit_number_and_ret(store, comp):
    e = C.issue(store, comp, cat="AL", event="omnium",
                round_key="Qualificazioni Batteria 1", doc=DOC_RESULTS,
                number="92 RET")
    assert e.n == 92 and e.ret and e.label == "92 RET"


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
    assert len(rows) == 138
    assert rows[0]["issued"] is True
    assert rows[1]["issued"] is False


def test_status_lists_off_plan_documents_too(store, comp):
    C.issue(store, comp, cat="AL", event="velocita", round_key="Extra",
            doc=DOC_RESULTS, title="Turno supplementare")
    rows = C.status(comp, C.load(store))
    assert len(rows) == 139
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
    assert "138 documenti" in html
    assert "92 RET" in html
    assert html.count("<tr") >= 138


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
