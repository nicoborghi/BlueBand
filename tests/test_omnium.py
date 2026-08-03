"""The omnium as the jury files it: four prove, and the sheets between them.

Each prova is read into the next. The classifica parziale after one of them is
the ordine di partenza of the one that follows, so that is the sheet the
register numbers and the risultati of the prova itself go out unnumbered; the
corsa a punti is scored on the running omnium total, from the points each rider
brought into it.
"""

import re

import pytest

from core import communiques as C
from core import race as R
from core.config import (DOC_CLASSIFICATION, DOC_PARTIAL, DOC_RACE,
                         DOC_RESULTS, DOC_STARTLIST)
from core.entries import import_master, save_import
from core.formats import omnium as O
from core.formats.base import Placing, Result
from core.models import Status
from render import documents as D
from render.render import to_html
from ui.pages.races import _doc_kinds, _omnium_points_cols, _omnium_subtitle


@pytest.fixture(scope="session")
def entries(iscritti_path, comp):
    return import_master(iscritti_path, comp)


@pytest.fixture
def ev(store, entries):
    save_import(store, entries)
    return store


def _res(order, statuses=None):
    statuses = statuses or {}
    return Result(placings=[Placing(key=k, position=i + 1,
                                    status=statuses.get(k, Status.OK))
                            for i, k in enumerate(order)])


def _text(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


# ── scoring ─────────────────────────────────────────────────────────────────

def test_a_prova_not_finished_is_carried_into_the_standings():
    """A DNF in one prova takes the rider out of the omnium classification."""
    rounds = {O.SCRATCH: _res(["A", "B", "C"]),
              O.TEMPO: _res(["A", "C", "B"], {"B": Status.DNF})}
    res = O.omnium_classification(rounds)
    assert res.by_key("B").status is Status.DNF
    assert res.by_key("B").position is None
    assert res.by_key("B").data["total"] == 0
    # the classified are numbered without it
    assert [p.key for p in res.placings if p.position] == ["A", "C"]
    assert res.placings[-1].key == "B"


def test_the_worst_status_of_the_four_prove_wins():
    rounds = {O.SCRATCH: _res(["A", "B"], {"B": Status.DNF}),
              O.TEMPO: _res(["A", "B"], {"B": Status.DSQ})}
    assert O.omnium_classification(rounds).by_key("B").status is Status.DSQ


def test_a_declassamento_is_not_carried():
    """REL is a placing like any other: it scores, and the omnium goes on.

    The declassamento belongs to the prova it was taken in - it is on that
    sheet - and the rider is classified there, so he takes its points into the
    standings like everybody else.
    """
    rounds = {O.SCRATCH: _res(["A", "B"], {"B": Status.REL})}
    res = O.omnium_classification(rounds)
    assert res.by_key("B").status is Status.OK
    assert res.by_key("B").position == 2
    assert res.by_key("B").data["total"] == 38


def test_an_explicit_status_wins_over_what_the_prove_say():
    rounds = {O.SCRATCH: _res(["A", "B"], {"B": Status.DNF})}
    res = O.omnium_classification(rounds, statuses={"B": Status.DNS})
    assert res.by_key("B").status is Status.DNS


def test_the_standings_carry_what_each_rider_took_into_the_points_race():
    rounds = {O.SCRATCH: _res(["A", "B"]),
              O.TEMPO: _res(["A", "B"]),
              O.ELIMINATION: _res(["A", "B"]),
              O.POINTS_RACE: Result(placings=[
                  Placing(key="B", position=1,
                          data={"total": 40, "sprints": [5, 3], "laps": 1}),
                  Placing(key="A", position=2, data={"total": 0})])}
    res = O.omnium_classification(rounds)
    b = res.by_key("B")
    assert b.data["carried"] == 38 * 3        # the three prove, not the race
    assert b.data["total"] == 38 * 3 + 40
    # the volate and the giri travel too: the classifica prints the sheet the
    # corsa a punti was scored on
    assert b.data["sprints"] == [5, 3] and b.data["laps"] == 1


# ── the standings between two prove ─────────────────────────────────────────

def test_partial_standings_stop_at_the_prova_asked_for(ev, entries, comp):
    scratch = R.ensure_state(ev, comp, "AL", "omnium", "Scratch", entries)
    bibs = scratch.entrants[:4]
    scratch.payload["sprints"] = ",".join(bibs)
    ev.save_race(scratch)

    tempo = R.ensure_state(ev, comp, "AL", "omnium", "Tempo Race", entries)
    tempo.payload["sprints"] = "-".join(reversed(bibs))
    ev.save_race(tempo)

    after_scratch = R.omnium_standings(ev, comp, entries, "AL", upto=O.SCRATCH)
    assert after_scratch.by_key(bibs[0]).data["total"] == 40
    assert after_scratch.by_key(bibs[0]).data[O.points_key(O.TEMPO)] is None

    after_tempo = R.omnium_standings(ev, comp, entries, "AL", upto=O.TEMPO)
    assert after_tempo.by_key(bibs[0]).data[O.points_key(O.TEMPO)] is not None
    assert (after_tempo.by_key(bibs[0]).data["total"]
            > after_scratch.by_key(bibs[0]).data["total"])


def test_the_points_race_sheet_runs_on_the_omnium_total():
    result = Result(placings=[Placing(key="7", position=1,
                                      data={"total": 20, "sprints": [5, 5]}),
                              Placing(key="9", position=2, data={"total": 6})],
                    columns=["points", "laps", "total"])
    out = R.omnium_points_race(result, {"7": 96, "9": 84})
    assert out.by_key("7").data["carried"] == 96
    assert out.by_key("7").data["total"] == 116
    assert out.by_key("9").data["total"] == 90


def test_a_prova_carries_the_points_its_placings_are_worth():
    out = R.omnium_prova_points(_res(["A", "B", "C"]), O.ELIMINATION)
    assert [p.data["prova_points"] for p in out.placings] == [40, 38, 36]
    assert "prova_points" in out.columns


# ── the sheets of a prova ───────────────────────────────────────────────────

@pytest.mark.parametrize("round_key, docs", [
    (O.SCRATCH, [DOC_STARTLIST, DOC_RESULTS, DOC_PARTIAL]),
    (O.TEMPO, [DOC_STARTLIST, DOC_RACE, DOC_RESULTS, DOC_PARTIAL]),
    (O.ELIMINATION, [DOC_STARTLIST, DOC_RESULTS, DOC_PARTIAL]),
    (O.POINTS_RACE, [DOC_STARTLIST, DOC_RESULTS, DOC_CLASSIFICATION]),
])
def test_the_documents_a_prova_files(ev, entries, comp, round_key, docs):
    state = R.ensure_state(ev, comp, "AL", "omnium", round_key, entries)
    assert _doc_kinds(comp, state) == docs


def test_the_classifica_parziale_says_which_prova_it_starts(ev, entries, comp):
    def subtitle(round_key):
        state = R.ensure_state(ev, comp, "AL", "omnium", round_key, entries)
        return _omnium_subtitle(state, DOC_PARTIAL)

    assert subtitle(O.SCRATCH) == ("Risultati Scratch e Ordine di Partenza "
                                   "Tempo Race")
    assert subtitle(O.TEMPO) == ("Classifica Parziale e Ordine Partenza "
                                 "Eliminazione")
    assert subtitle(O.ELIMINATION) == ("Classifica Parziale e Ordine Partenza "
                                       "Corsa a Punti")


def test_the_points_columns_of_each_sheet(ev, entries, comp):
    def cols(round_key, doc):
        state = R.ensure_state(ev, comp, "AL", "omnium", round_key, entries)
        return [head for _key, head in _omnium_points_cols(state, doc)]

    # the first one has one prova to show and nothing to total
    assert cols(O.SCRATCH, DOC_PARTIAL) == ["Punti Scratch"]
    assert cols(O.TEMPO, DOC_PARTIAL) == ["Punti Scratch", "Punti Tempo Race",
                                          "Punti Totali"]
    assert cols(O.ELIMINATION, DOC_PARTIAL) == [
        "Punti Scratch", "Punti Tempo Race", "Punti Eliminazione",
        "Punti Totali"]
    assert cols(O.TEMPO, DOC_RESULTS) == ["Punti Tempo Race"]
    assert cols(O.ELIMINATION, DOC_RESULTS) == ["Punti Eliminazione"]
    assert cols(O.POINTS_RACE, DOC_RESULTS) == []


# ── the register ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("cat, round_key, doc, number", [
    # the sheet that goes out is the classifica parziale; the risultati of the
    # prova and the partenti of the next one are the jury's own
    ("ED", O.SCRATCH, DOC_STARTLIST, "39"),
    ("ED", O.SCRATCH, DOC_RESULTS, "-1"),
    ("ED", O.SCRATCH, DOC_PARTIAL, "53"),
    ("ED", O.TEMPO, DOC_RACE, "-1"),
    ("ED", O.TEMPO, DOC_RESULTS, "61"),
    ("ED", O.TEMPO, DOC_PARTIAL, "62"),
    ("ED", O.ELIMINATION, DOC_STARTLIST, "-1"),
    ("ED", O.ELIMINATION, DOC_RESULTS, "65"),
    ("ED", O.ELIMINATION, DOC_PARTIAL, "66"),
    ("ED", O.POINTS_RACE, DOC_STARTLIST, "-1"),
    ("ED", "", DOC_CLASSIFICATION, "70"),
    ("AL", O.SCRATCH, DOC_PARTIAL, "97"),
    ("AL", O.ELIMINATION, DOC_PARTIAL, "106"),
])
def test_the_register_numbers_the_omnium_sheets(comp, cat, round_key, doc,
                                                number):
    assert C.number_for(comp, cat, "omnium", round_key, doc) == number


def test_no_number_is_planned_twice(comp):
    planned = [c.n for c in comp.communiques]
    assert len(planned) == len(set(planned))


# ── what the sheets print ───────────────────────────────────────────────────

def _sheet(ev, entries, comp, round_key, doc, **kw):
    state = R.ensure_state(ev, comp, "ED", "omnium", round_key, entries)
    bibs = state.entrants[:6]
    state.payload["sprints"] = ",".join(bibs)
    ev.save_race(state)
    result = R.classify(state, entries, comp)
    if doc == DOC_PARTIAL:
        result = R.omnium_standings(ev, comp, entries, "ED", upto=round_key)
    return D.race_classification(state, result, entries, comp, doc_kind=doc,
                                 **kw), state


def test_the_classifica_parziale_is_an_ordine_di_partenza(ev, entries, comp):
    """No Ris. column after the scratch, and the lanes alternate down it."""
    doc, _ = _sheet(ev, entries, comp, O.SCRATCH, DOC_PARTIAL,
                    show_rank=False, lane_col=True,
                    points_cols=[(O.points_key(O.SCRATCH), "Punti Scratch")])
    heads = [c.label for c in doc.tables[0].columns]
    assert "Ris." not in heads
    assert "Punti Scratch" in heads
    # the untitled column: grey, and never bold
    lane = next(c for c in doc.tables[0].columns if c.key == "lane")
    assert lane.label == "" and lane.muted and not lane.bold
    lanes = [r["lane"] for r in doc.tables[0].rows]
    assert lanes[:4] == ["Balau.", "Corda", "Balau.", "Corda"]
    text = _text(to_html(doc, comp))
    assert "Balau." in text and "Corda" in text


def test_the_points_race_sheet_starts_from_the_points_carried(ev, entries,
                                                              comp):
    doc, _ = _sheet(ev, entries, comp, O.POINTS_RACE, DOC_RESULTS,
                    show_carried=True, show_uci=False)
    heads = [c.label for c in doc.tables[0].columns]
    assert "Punti" in heads              # before the volate
    assert heads.index("Punti") < heads.index("1")
    assert "UCI ID" not in heads


def test_the_omnium_classifica_files_the_society_by_name(ev, entries, comp):
    doc, _ = _sheet(ev, entries, comp, O.POINTS_RACE, DOC_CLASSIFICATION,
                    show_club=True, show_club_code=False)
    heads = [c.label for c in doc.tables[0].columns]
    assert "Società" in heads and "Cod. Soc." not in heads
