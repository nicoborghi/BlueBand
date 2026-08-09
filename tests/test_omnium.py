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


def test_riders_on_the_same_points_are_split_by_the_last_prova():
    """From 21st on everybody scores 1: the classifica still ranks them.

    The parziale of the scratch is a classifica, not the ordine di partenza of
    the prova that follows: the tail on one point is read in the order they
    crossed the line, not in the order the entrants happen to be listed in.
    """
    order = [f"r{i}" for i in range(1, 26)]
    res = O.omnium_classification({O.SCRATCH: _res(list(reversed(order)))})
    tail = [p.key for p in res.placings if p.data["total"] == 1]
    assert len(tail) == 5                            # 21st to 25th
    assert tail == list(reversed(order))[20:]

    # and the prova ridden last is the one that separates them: the same five
    # are on one point in both, in the other order in the tempo race
    tempo = list(reversed(order))[:20] + order[:5]
    res = O.omnium_classification({O.SCRATCH: _res(list(reversed(order))),
                                   O.TEMPO: _res(tempo)})
    tail = [p.key for p in res.placings if p.data["total"] == 2]
    assert tail == order[:5]


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


def test_the_points_race_sheet_is_ordered_on_the_omnium_total():
    """It is the last prova: its risultati are the classifica of the omnium.

    Whoever won the race has not won the omnium unless the total says so, and
    two riders on the same total are separated by this race (3.2.109).
    """
    result = Result(placings=[Placing(key="7", position=1, data={"total": 20}),
                              Placing(key="9", position=2, data={"total": 6}),
                              Placing(key="4", position=3, data={"total": 6})],
                    columns=["points", "laps", "total"])
    out = R.omnium_points_race(result, {"7": 60, "9": 84, "4": 84})
    assert [p.key for p in out.placings] == ["9", "4", "7"]
    assert [p.position for p in out.placings] == [1, 2, 3]
    assert [p.data["total"] for p in out.placings] == [90, 90, 80]


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
    assert _doc_kinds(comp, state, ev) == docs


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
    ("ED", O.SCRATCH, DOC_PARTIAL, "54"),
    ("ED", O.TEMPO, DOC_RACE, "-1"),
    ("ED", O.TEMPO, DOC_RESULTS, "63"),
    ("ED", O.TEMPO, DOC_PARTIAL, "64"),
    ("ED", O.ELIMINATION, DOC_STARTLIST, "-1"),
    ("ED", O.ELIMINATION, DOC_RESULTS, "67"),
    ("ED", O.ELIMINATION, DOC_PARTIAL, "68"),
    ("ED", O.POINTS_RACE, DOC_STARTLIST, "-1"),
    ("ED", "", DOC_CLASSIFICATION, "72"),
    ("AL", O.SCRATCH, DOC_PARTIAL, "101"),
    ("AL", O.ELIMINATION, DOC_PARTIAL, "110"),
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


def test_the_elenco_partenti_of_the_scratch_carries_the_uci_id(ev, entries,
                                                               comp):
    """The sheet that starts the omnium is read against the licences."""
    state = R.ensure_state(ev, comp, "ED", "omnium", O.SCRATCH, entries)
    heads = [c.label for c in
             D.race_startlist(state, entries, comp).tables[0].columns]
    assert "UCI ID" in heads


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


# ── the batterie di qualificazione ──────────────────────────────────────────
#
# An omnium with more riders than the prove take is ridden with a corsa a punti
# di qualificazione in two batterie. Who rides where is a decision of the jury,
# taken in the composition round; who rides the four prove is what the batterie
# qualified. Nothing of this is the madison's, except the machinery.

QUALIF_1 = "Qualificazioni Batteria 1"
QUALIF_2 = "Qualificazioni Batteria 2"


@pytest.fixture
def composed(ev, entries, comp):
    """ES omnium composed: the iscritti dealt into the two batterie."""
    keys = R.entrants(entries, comp, "ES", "omnium")
    setup = R.ensure_state(ev, comp, "ES", "omnium", "Composizione batterie",
                           entries)
    setup.payload[R.PAIR_HEATS] = R.spread_heats(keys, 2)
    setup.payload[R.ELIMINATE] = 5
    ev.save_race(setup)
    return ev


def test_the_omnium_composition_round_is_composed_not_ridden(comp):
    assert R.round_format(comp, "ES", "omnium",
                          "Composizione batterie") == R.SETUP
    assert R.setup_round(comp, "ES", "omnium") == "Composizione batterie"
    assert R.is_composed(comp, "ES", "omnium")
    assert R.heat_rounds(comp, "ES", "omnium") == [(1, QUALIF_1), (2, QUALIF_2)]
    # what the batterie qualify for is the omnium itself: all four prove
    assert R.final_rounds(comp, "ES", "omnium") == O.ROUNDS
    # a categoria without qualification is ridden straight off
    assert not R.is_composed(comp, "ED", "omnium")


def test_the_riders_keep_their_dorsale(composed, entries, comp):
    """No numbers to hand out: an omnium composes batterie and nothing else."""
    pr = R.pairing(composed, comp, "ES", "omnium", entries)
    assert not pr.numbered
    assert all(pr.number(k) == int(k) for k in pr.pairs)
    assert pr.eliminate == 5           # what the programme says


def test_each_batteria_starts_only_its_own_riders(composed, entries, comp):
    everyone = R.entrants(entries, comp, "ES", "omnium")
    b1 = R.ensure_state(composed, comp, "ES", "omnium", QUALIF_1, entries)
    b2 = R.ensure_state(composed, comp, "ES", "omnium", QUALIF_2, entries)

    assert set(b1.entrants) | set(b2.entrants) == set(everyone)
    assert not set(b1.entrants) & set(b2.entrants)
    assert len(b1.entrants) < len(everyone)
    # by dorsale, which is what the ordine di partenza is read by
    assert b1.entrants == sorted(b1.entrants, key=int)
    # the cut in force travels onto the batteria, so its sheets keep saying it
    assert b1.payload[R.ELIMINATE] == 5


def test_without_a_composition_both_batterie_hold_everybody(ev, entries, comp):
    """Before the jury composes anything there is nothing to split the field by.

    The startlist of a batteria is the entry list until the composition round
    says otherwise - what it must not be is silently half of it.
    """
    everyone = R.entrants(entries, comp, "ES", "omnium")
    b1 = R.ensure_state(ev, comp, "ES", "omnium", QUALIF_1, entries)
    assert b1.entrants == everyone


def _ride(store, entries, comp, round_key):
    """Ride one batteria: everybody finishes, in startlist order."""
    state = R.ensure_state(store, comp, "ES", "omnium", round_key, entries)
    state.payload["sprints"] = ",".join(state.entrants)
    store.save_race(state)
    return state


def test_the_prove_start_who_the_batterie_qualified(composed, entries, comp):
    b1 = _ride(composed, entries, comp, QUALIF_1)
    b2 = _ride(composed, entries, comp, QUALIF_2)

    info = R.load_qualified(composed, comp, entries, "ES", "omnium")

    assert not info["missing"]
    assert len(info["qualified"]) == (len(b1.entrants) - 5
                                      + len(b2.entrants) - 5)
    # dealt across the batterie: the winners first, then the seconds
    assert info["qualified"][:2] == [b1.entrants[0], b2.entrants[0]]
    # all four prove are loaded together: the field rides the whole omnium
    assert info["rounds"] == O.ROUNDS
    for name in O.ROUNDS:
        prova = R.ensure_state(composed, comp, "ES", "omnium", name, entries)
        assert prova.entrants == info["qualified"]
    # reopening must not put the eliminated riders back on the startlist
    scratch = R.ensure_state(composed, comp, "ES", "omnium", O.SCRATCH, entries)
    assert len(scratch.entrants) < len(R.entrants(entries, comp, "ES",
                                                  "omnium"))


def test_the_classification_is_over_the_qualified_field(composed, entries,
                                                        comp):
    _ride(composed, entries, comp, QUALIF_1)
    _ride(composed, entries, comp, QUALIF_2)
    info = R.load_qualified(composed, comp, entries, "ES", "omnium")

    field = R.omnium_field(composed, comp, entries, "ES", "omnium")
    assert field == info["qualified"]
    # whoever went out in the qualification is not in the standings at all
    res = R.omnium_standings(composed, comp, entries, "ES", "omnium")
    assert {p.key for p in res.placings} == set(info["qualified"])


def test_an_omnium_without_batterie_starts_everybody(ev, entries, comp):
    """ED rides the four prove straight off: no qualification, no cut."""
    everyone = R.entrants(entries, comp, "ED", "omnium")
    scratch = R.ensure_state(ev, comp, "ED", "omnium", O.SCRATCH, entries)
    assert scratch.entrants == everyone
    assert R.omnium_field(ev, comp, entries, "ED", "omnium") == everyone
