"""Sprint / keirin brackets and omnium aggregate scoring."""

import pytest

from core import race as R
from core.entries import import_master, save_import
from core.formats import omnium as O
from core.formats import sprint as S
from core.formats.base import Placing, Result
from core.models import Status


@pytest.fixture(scope="session")
def entries(iscritti_path, comp):
    return import_master(iscritti_path, comp)


@pytest.fixture
def ev(store, entries):
    save_import(store, entries)
    return store


# ── seeding ─────────────────────────────────────────────────────────────────

def test_two_rider_heats_use_the_mirror_pairing():
    """UCI 1/4 finals: 1-8, 2-7, 3-6, 4-5."""
    ranking = [f"R{i}" for i in range(1, 9)]
    heats = S.compose_round(ranking, heat_size=2)
    assert heats == [["R1", "R8"], ["R2", "R7"], ["R3", "R6"], ["R4", "R5"]]


def test_semifinals_pairing_is_1_4_and_2_3():
    heats = S.compose_round(["R1", "R2", "R3", "R4"], heat_size=2)
    assert heats == [["R1", "R4"], ["R2", "R3"]]


def test_keirin_first_round_matches_the_uci_table():
    """28 riders in 4 heats of 7(UCI Part 3, keirin composition example)."""
    ranking = [f"R{i}" for i in range(1, 29)]
    heats = S.serpentine_heats(ranking, 4)
    assert heats[0] == ["R1", "R8", "R9", "R16", "R17", "R24", "R25"]
    assert heats[1] == ["R2", "R7", "R10", "R15", "R18", "R23", "R26"]
    assert heats[2] == ["R3", "R6", "R11", "R14", "R19", "R22", "R27"]
    assert heats[3] == ["R4", "R5", "R12", "R13", "R20", "R21", "R28"]


def test_repechage_composition_over_the_losers():
    """12 losers into 4 heats of 3: 1-8-9, 2-7-10, 3-6-11, 4-5-12."""
    losers = [f"L{i}" for i in range(1, 13)]
    heats = S.serpentine_heats(losers, 4)
    assert heats[0] == ["L1", "L8", "L9"]
    assert heats[3] == ["L4", "L5", "L12"]


def test_compose_round_handles_an_odd_field():
    heats = S.compose_round(["A", "B", "C", "D", "E"], heat_size=2)
    assert sum(len(h) for h in heats) == 5
    assert all(h for h in heats)


# ── rounds ──────────────────────────────────────────────────────────────────

def test_round_outcome_advances_the_winners():
    heats = [["A", "B"], ["C", "D"]]
    orders = [["B", "A"], ["C", "D"]]
    out = S.round_outcome(heats, orders, qualify=1)
    assert out.advancing == ["B", "C"]
    assert out.eliminated == ["A", "D"]
    assert out.placings["B"] == (0, 0) and out.placings["A"] == (0, 1)


def test_round_outcome_with_two_qualifiers_per_heat():
    heats = [["A", "B", "C"], ["D", "E", "F"]]
    orders = [["C", "A", "B"], ["E", "F", "D"]]
    out = S.round_outcome(heats, orders, qualify=2)
    assert out.advancing == ["C", "A", "E", "F"]
    assert out.eliminated == ["B", "D"]


def test_round_outcome_flags_a_missing_result():
    out = S.round_outcome([["A", "B"], ["C", "D"]], [["A", "B"]], qualify=1)
    assert any("Batteria 2" in w for w in out.warnings)
    assert out.advancing == ["A"]


def test_round_outcome_ignores_a_rider_who_did_not_start():
    out = S.round_outcome([["A", "B"]], [["A", "B"]], qualify=1,
                          statuses={"A": Status.DNS})
    assert out.advancing == ["B"]


# ── final bracket classification ────────────────────────────────────────────

def test_bracket_classification_orders_finals_then_rounds():
    finals = {"Finali 1-4": [["A", "B"], ["C", "D"]],
              "Finali 5-8": [["E", "F"], ["G", "H"]]}
    eliminated = [("Turno 1", ["M", "N"]), ("Quarti", ["I", "L"])]
    res = S.bracket_classification(
        finals, eliminated, qual_ranking=["A", "B", "C", "D", "E", "F", "G",
                                          "H", "I", "L", "M", "N"])
    assert [p.key for p in res.placings] == [
        "A", "B", "C", "D", "E", "F", "G", "H", "I", "L", "M", "N"]
    assert res.placings[0].label == "1°"
    assert res.placings[-1].position == 12


def test_riders_out_later_finish_ahead():
    res = S.bracket_classification(
        {}, [("Turno 1", ["Z"]), ("Semifinali", ["Y"])],
        qual_ranking=["Y", "Z"])
    assert [p.key for p in res.placings] == ["Y", "Z"]


# ── omnium ──────────────────────────────────────────────────────────────────

def test_uci_placing_points():
    assert O.placing_points(1) == 40
    assert O.placing_points(2) == 38
    assert O.placing_points(20) == 2
    assert O.placing_points(21) == 1
    assert O.placing_points(40) == 1
    assert O.placing_points(None) == 0


def _res(order):
    return Result(placings=[Placing(key=k, position=i + 1)
                            for i, k in enumerate(order)])


def test_omnium_sums_the_first_three_events():
    competitions = {O.SCRATCH: _res(["A", "B", "C"]),
                    O.TEMPO: _res(["B", "A", "C"]),
                    O.ELIMINATION: _res(["A", "C", "B"])}
    res = O.omnium_classification(competitions)
    total = {p.key: p.data["total"] for p in res.placings}
    assert total["A"] == 40 + 38 + 40
    assert total["B"] == 38 + 40 + 36
    assert total["C"] == 36 + 36 + 38
    assert [p.key for p in res.placings] == ["A", "B", "C"]
    assert any("parziale" in w for w in res.warnings)


def test_points_race_points_are_added_not_converted():
    competitions = {O.SCRATCH: _res(["A", "B"]),
                    O.TEMPO: _res(["A", "B"]),
                    O.ELIMINATION: _res(["A", "B"]),
                    O.POINTS_RACE: Result(placings=[
                        Placing(key="B", position=1, data={"total": 40}),
                        Placing(key="A", position=2, data={"total": 0})])}
    res = O.omnium_classification(competitions)
    total = {p.key: p.data["total"] for p in res.placings}
    assert total["A"] == 40 * 3  # three wins, nothing in the points race
    assert total["B"] == 38 * 3 + 40  # overturns it in the last competition
    assert [p.key for p in res.placings] == ["B", "A"]
    assert res.warnings == []


def test_omnium_tie_is_broken_by_the_points_race():
    competitions = {O.SCRATCH: _res(["A", "B"]),
                    O.TEMPO: _res(["B", "A"]),
                    O.POINTS_RACE: Result(placings=[
                        Placing(key="B", position=1, data={"total": 10}),
                        Placing(key="A", position=2, data={"total": 10})])}
    res = O.omnium_classification(competitions)
    total = {p.key: p.data["total"] for p in res.placings}
    assert total["A"] == total["B"]
    assert [p.key for p in res.placings] == ["B", "A"]


def test_omnium_excludes_a_rider_who_abandoned_from_the_places():
    """On the classification with her sigla, out of the places and the points."""
    competitions = {O.SCRATCH: _res(["A", "B"])}
    res = O.omnium_classification(competitions, statuses={"B": Status.DNF})
    assert [(p.key, p.position) for p in res.placings] == [("A", 1), ("B", None)]
    assert res.by_key("B").data["total"] == 0
    assert res.notes == []


# ── integration with the store ──────────────────────────────────────────────

def test_omnium_standings_from_saved_races(ev, entries, comp):
    scratch = R.ensure_state(ev, comp, "AL", "omnium", "Scratch", entries)
    bibs = scratch.entrants[:4]
    scratch.payload["sprints"] = ",".join(bibs)
    ev.save_race(scratch)

    tempo = R.ensure_state(ev, comp, "AL", "omnium", "Tempo Race", entries)
    tempo.payload["sprints"] = "-".join(f"{b}" for b in reversed(bibs))
    ev.save_race(tempo)

    res = R.omnium_standings(ev, comp, entries, "AL")
    assert res.placings
    assert res.by_key(bibs[0]).data["total"] >= 40
    assert any("parziale" in w for w in res.warnings)


def test_bracket_round_through_the_race_service(ev, entries, comp):
    state = R.ensure_state(ev, comp, "AL", "velocita", "Quarti", entries)
    assert state.fmt == R.BRACKET
    bibs = state.entrants[:8]
    state.payload["heats"] = "/".join(f"{bibs[i]},{bibs[7 - i]}"
                                      for i in range(4))
    state.payload["results"] = "/".join(f"{bibs[7 - i]},{bibs[i]}"
                                        for i in range(4))
    ev.save_race(state)

    outcome = R.bracket_round(ev.load_race(state.race_id), comp)
    assert outcome.advancing == [bibs[7], bibs[6], bibs[5], bibs[4]]
    assert outcome.eliminated == [bibs[0], bibs[1], bibs[2], bibs[3]]

    res = R.classify(state, entries, comp)
    assert res.columns == ["heat_no"]
    assert res.placings[0].data["heat_no"] == 1
    assert res.placings[0].label == "1°"


def test_compose_bracket_round_from_a_ranking(ev, entries, comp):
    state = R.ensure_state(ev, comp, "AL", "velocita", "Quarti", entries)
    ranking = state.entrants[:8]
    txt = R.compose_bracket_round(state, comp, ranking)
    assert txt == "/".join(f"{ranking[i]},{ranking[7 - i]}" for i in range(4))


# ── l'eliminazione corsa per sé ─────────────────────────────────────────────
#
# Not a prova of an omnium: an event of its own, run direttamente. It used to
# fall through `round_format` onto the points race and every sheet of it was
# scored on volate nobody rode.

@pytest.fixture(scope="session")
def example():
    """The fictional programme shipped with the app - it has an eliminazione."""
    from pathlib import Path

    from core.config import load_competition

    path = (Path(__file__).resolve().parent.parent / "competitions"
            / "example" / "programme.yaml")
    if not path.exists():
        pytest.skip(f"no example competition at {path}")
    return load_competition(path)


def test_a_standalone_elimination_is_scored_as_one(example):
    cat = next(c for c in example.cat_order()
               if "eliminazione" in example.events_for(c))
    rnd = example.rounds(cat, "eliminazione")[0]
    assert R.round_format(example, cat, "eliminazione", rnd.key) == R.ELIMINATION


def test_a_standalone_elimination_ranks_on_the_order_they_went_out(example):
    from core.models import RaceState

    cat = next(c for c in example.cat_order()
               if "eliminazione" in example.events_for(c))
    rnd = example.rounds(cat, "eliminazione")[0]
    state = RaceState(race_id=R.race_key(cat, "eliminazione", rnd.key),
                      cat=cat, event="eliminazione", round_key=rnd.key,
                      fmt=R.ELIMINATION, entrants=["1", "2", "3"],
                      payload={"eliminated": "3, 2, 1"})
    result = R.classify(state, None, example)
    assert [p.key for p in result.placings] == ["1", "2", "3"]
