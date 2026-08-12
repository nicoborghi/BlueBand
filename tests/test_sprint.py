"""The velocità as a whole: 200 m -> turno 1 + recuperi -> quarti -> semi ->
finali -> classifica. Every round composed by the app, nothing typed as
notation - which is what the jury does at the track.
"""

import pytest

from core import race as R
from core.config import DOC_RESULTS, DOC_RESULTS_REP
from core.entries import import_master, save_import
from core.formats import sprint as S
from core.i18n import ui
from core.models import Status
from core.parse import parse_time


@pytest.fixture(scope="session")
def entries(iscritti_path, comp):
    return import_master(iscritti_path, comp)


@pytest.fixture
def ev(store, entries):
    save_import(store, entries)
    return store


# ── the tables themselves ───────────────────────────────────────────────────

def test_twelve_qualified_ride_six_batterie():
    ranked = [str(i) for i in range(1, 13)]
    heats = S.mirror_pairs(ranked)
    assert len(heats) == 6
    assert heats[0] == ["1", "12"] and heats[5] == ["6", "7"]


def test_the_repechages_split_the_losers_by_their_batteria():
    """1, 4, 6 against 2, 3, 5 - the UCI table, not a serpentine."""
    losers = [f"L{i}" for i in range(1, 7)]
    assert S.repechage_heats(losers) == [["L1", "L4", "L6"],
                                         ["L2", "L3", "L5"]]


def test_the_jury_confirms_the_repechage_composition(ev, comp, entries):
    """A recupero the jury re-composed is the one that is ridden - until the
    turno 1 sends a different field to it, when it is seeded again."""
    el = entries
    qual = _qualify(ev, comp, el)
    R.load_sprint_round(ev, comp, el, qual)
    t1 = ev.load_race(R.race_key("AL", "velocita", S.TURNO1))
    heats = R.bracket_heats(t1)
    t1.payload["results"] = R.heats_text([[h[0], h[1]] for h in heats])

    seeded = R.sprint_repechages(t1)
    # two riders swapped between the two recuperi: same field, other batterie
    mine = [[seeded[1][0]] + seeded[0][1:], [seeded[0][0]] + seeded[1][1:]]
    t1.payload[R.REP_HEATS] = R.heats_text(mine)
    assert R.sprint_repechages(t1) == mine

    # the turno 1 is corrected and somebody else goes to the recuperi: the
    # composition on the race is about a field that no longer exists
    t1.payload["results"] = R.heats_text([[h[1], h[0]] for h in heats])
    reseeded = R.sprint_repechages(t1)
    assert {k for h in reseeded for k in h} == {h[0] for h in heats}
    assert reseeded == S.repechage_heats([h[0] for h in heats])


def test_the_repechés_are_the_last_two_of_the_quarti():
    """The winner of the second repechage meets the winner of batteria 1."""
    winners = [f"W{i}" for i in range(1, 7)]
    heats = S.quarter_heats(winners, ["R1", "R2"])
    assert heats == [["W1", "R2"], ["W2", "R1"], ["W3", "W6"], ["W4", "W5"]]


def test_the_semifinals_pair_the_first_quarto_with_the_last():
    assert S.semifinal_heats(["A", "B", "C", "D"]) == [["A", "D"], ["B", "C"]]


def test_the_finals_ride_the_3_4_first():
    assert S.final_heats(["W1", "W2"], ["L1", "L2"]) == [["L1", "L2"],
                                                         ["W1", "W2"]]


def test_a_batteria_is_won_by_taking_two_prove():
    assert S.heat_winner(["a", "b", "a"], ["a", "b"]) == "a"
    assert S.heat_winner(["a", "a"], ["a", "b"]) == "a"
    assert S.heat_winner(["a", "b"], ["a", "b"]) == ""      # the bella is due
    assert S.heat_result(["b", "b"], ["a", "b"]) == ["b", "a"]
    assert S.heat_result(["b"], ["a", "b"]) == []           # still open


def test_below_the_eighth_place_the_200_m_decides():
    res = S.scheme_classification(
        finals=[["c", "d"], ["a", "b"]],           # 3/4 ridden first
        final_5_8=["e", "f", "g", "h"],
        qual_ranking=["a", "b", "c", "d", "e", "f", "g", "h", "z", "y"])
    order = [p.key for p in res.placings]
    assert order[:8] == ["a", "b", "c", "d", "e", "f", "g", "h"]
    assert order[8:] == ["z", "y"]                  # qualifying order, as ridden
    assert res.placings[0].position == 1 and res.placings[9].position == 10


# ── the whole event, through the service ────────────────────────────────────

def _qualify(ev, comp, el, cat="AL", event="velocita", final_5_8=True):
    """Ride the 200 m: a time for everybody, fastest bib first.

    The scheme and the 5°-8° are both settled on this round, so a test that
    starts here says which of the two velocità it is riding rather than
    inheriting whatever the championship file happens to plan this year.
    """
    key = R.sprint_qualifying(comp, cat, event)
    st = R.ensure_state(ev, comp, cat, event, key, el)
    st.payload[R.SCHEME] = "12"
    st.payload[R.FINAL_58] = final_5_8
    st.payload["times"] = {k: parse_time(f"11,{i:03d}")
                           for i, k in enumerate(st.entrants)}
    ev.save_race(st)
    return st


def test_the_scheme_is_read_back_from_the_qualifying_round(ev, comp, entries):
    st = _qualify(ev, comp, entries)
    assert R.sprint_scheme(ev, comp, "AL", "velocita").qualify == 12
    st.payload[R.SCHEME] = "8"
    ev.save_race(st)
    assert R.sprint_scheme(ev, comp, "AL", "velocita").qualify == 8


def test_a_programme_without_a_first_round_runs_to_eight(ev, comp, entries,
                                                         monkeypatch):
    """Nothing chosen yet: the programme decides, by the rounds it schedules.

    Every category of CITA 26 rides the twelve - the ED went from the quarti to
    the first round on 05.08.2026 - so the fallback is exercised on a programme
    with the first round taken out, which is what a small category looks like.
    """
    rounds = type(comp).rounds
    monkeypatch.setattr(type(comp), "rounds",
                        lambda self, cat, event: [
                            r for r in rounds(self, cat, event)
                            if r.key != S.TURNO1])
    assert R.sprint_scheme(ev, comp, "ED", "velocita").key == "8"


def test_a_velocita_runs_from_the_200_m_to_the_champion(ev, comp, entries):
    el, cat = entries, "AL"
    qual = _qualify(ev, comp, el)
    ranked = [p.key for p in R.classify(qual, el, comp).placings if p.position]

    # 200 m -> Turno 1: twelve riders, six batterie, mirror-paired
    nxt, n = R.load_sprint_round(ev, comp, el, qual)
    assert (nxt, n) == (S.TURNO1, 6)
    t1 = ev.load_race(R.race_key(cat, "velocita", S.TURNO1))
    assert R.bracket_heats(t1)[0] == [ranked[0], ranked[11]]

    # the faster rider wins every batteria of the first round
    heats = R.bracket_heats(t1)
    t1.payload["results"] = R.heats_text([[h[0], h[1]] for h in heats])
    # the repechages compose themselves from the losers
    rep = R.sprint_repechages(t1)
    assert rep == [[heats[0][1], heats[3][1], heats[5][1]],
                   [heats[1][1], heats[2][1], heats[4][1]]]
    t1.payload[R.REP_RESULTS] = R.heats_text(rep)   # they finish as they line up
    ev.save_race(t1)

    # Turno 1 -> Quarti: six winners plus the two repêchés
    nxt, n = R.load_sprint_round(ev, comp, el, t1)
    assert (nxt, n) == (S.QUARTI, 4)
    q = ev.load_race(R.race_key(cat, "velocita", S.QUARTI))
    assert R.bracket_heats(q) == [[heats[0][0], rep[1][0]],
                                  [heats[1][0], rep[0][0]],
                                  [heats[2][0], heats[5][0]],
                                  [heats[3][0], heats[4][0]]]

    # the quarti are ridden at the best of three
    qh = R.bracket_heats(q)
    q.payload[R.RUNS] = {str(i): [h[0], h[0]] for i, h in enumerate(qh)}
    q.payload["results"] = R.heats_text(
        [S.heat_result([h[0], h[0]], h) for h in qh])
    ev.save_race(q)

    # Quarti -> Semifinali, and the 5°-8° final onto the finals race
    nxt, n = R.load_sprint_round(ev, comp, el, q)
    assert (nxt, n) == (S.SEMI, 2)
    sf = ev.load_race(R.race_key(cat, "velocita", S.SEMI))
    assert R.bracket_heats(sf) == [[qh[0][0], qh[3][0]], [qh[1][0], qh[2][0]]]
    fin = ev.load_race(R.race_key(cat, "velocita", S.FINALI))
    assert R.bracket_heats(fin, R.HEATS_58) == [[h[1] for h in qh]]

    sh = R.bracket_heats(sf)
    sf.payload["results"] = R.heats_text([[h[0], h[1]] for h in sh])
    ev.save_race(sf)

    # Semifinali -> Finali: the 3°/4° first, the 1°/2° second
    nxt, n = R.load_sprint_round(ev, comp, el, sf)
    assert (nxt, n) == (S.FINALI, 2)
    fin = ev.load_race(R.race_key(cat, "velocita", S.FINALI))
    assert R.bracket_heats(fin) == [[sh[0][1], sh[1][1]], [sh[0][0], sh[1][0]]]
    # and the eight of the finals round are the four finalists plus the 5°-8°
    assert len(fin.entrants) == 8

    fh = R.bracket_heats(fin)
    fin.payload["results"] = R.heats_text([[h[0], h[1]] for h in fh])
    fin.payload[R.RESULTS_58] = R.heats_text(R.bracket_heats(fin, R.HEATS_58))
    ev.save_race(fin)

    res = R.sprint_standings(ev, comp, el, cat, "velocita")
    order = [p.key for p in res.placings]
    assert order[0] == fh[1][0] and order[1] == fh[1][1]     # the 1°/2° final
    assert order[2] == fh[0][0] and order[3] == fh[0][1]     # the 3°/4°
    assert order[4:8] == [h[1] for h in qh]                  # the 5°-8°
    # everybody else on their 200 m, in that order and no other
    assert order[8:] == [k for k in ranked if k not in order[:8]]
    assert res.placings[0].position == 1


def _ridden_turno_1(ev, comp, el):
    """A turno 1 with every batteria and every recupero ridden."""
    qual = _qualify(ev, comp, el)
    R.load_sprint_round(ev, comp, el, qual)
    t1 = ev.load_race(R.race_key("AL", "velocita", S.TURNO1))
    heats = R.bracket_heats(t1)
    t1.payload["results"] = R.heats_text([[h[0], h[1]] for h in heats])
    t1.payload[R.REP_RESULTS] = R.heats_text(R.sprint_repechages(t1))
    ev.save_race(t1)
    return t1


def test_the_jury_can_redraw_the_quarti_before_they_are_loaded(ev, comp,
                                                               entries):
    """The seeding is a starting point: what the jury types is what starts.

    The eight are the same eight - the composition only says who meets whom -
    and it is what the quarti are loaded with, and what the block printed under
    the risultati recuperi announces.
    """
    el = entries
    t1 = _ridden_turno_1(ev, comp, el)
    seeded = R.heats_from_text(R.sprint_next(ev, comp, el, t1)[1]["heats"])

    # the jury swaps the two riders of the first quarto with those of the last
    fixed = [seeded[3], seeded[1], seeded[2], seeded[0]]
    t1.payload[R.NEXT_HEATS] = R.heats_text(fixed)

    nxt, n = R.load_sprint_round(ev, comp, el, t1)
    assert (nxt, n) == (S.QUARTI, 4)
    q = ev.load_race(R.race_key("AL", "velocita", S.QUARTI))
    assert R.bracket_heats(q) == fixed
    # and the sheet that publishes it says the same thing
    blocks = R.sprint_composition(ev, comp, el, t1, DOC_RESULTS_REP)
    assert blocks[0][1] == fixed
    # it is filed with the round that composed it: pressing the button again
    # does not seed it back to the table
    assert R.bracket_heats(ev.load_race(t1.race_id), R.NEXT_HEATS) == fixed


def test_a_redrawn_quarto_is_seeded_again_when_the_field_changes(ev, comp,
                                                                 entries):
    """A composition holds only while it is about the same riders.

    A recupero corrected sends somebody else to the quarti: the jury's pairing
    is about riders who are no longer all in it, and starting it would leave
    the newcomer out of the race.
    """
    el = entries
    t1 = _ridden_turno_1(ev, comp, el)
    seeded = R.heats_from_text(R.sprint_next(ev, comp, el, t1)[1]["heats"])
    t1.payload[R.NEXT_HEATS] = R.heats_text(
        [seeded[3], seeded[1], seeded[2], seeded[0]])

    # the first recupero was won by the rider behind, who takes the place in
    # the quarti of the one written down first
    rep = R.bracket_orders(t1, R.REP_RESULTS)
    was, comes_up = rep[0][0], rep[0][1]
    rep[0] = [comes_up, was] + rep[0][2:]
    t1.payload[R.REP_RESULTS] = R.heats_text(rep)

    fresh = R.heats_from_text(R.sprint_next(ev, comp, el, t1)[1]["heats"])
    flat = [k for h in fresh for k in h]
    assert comes_up in flat and was not in flat
    assert fresh == S.quarter_heats(
        [k for k in R.heat_winners(R.bracket_orders(t1)) if k],
        [k for k in R.heat_winners(
            R.bracket_orders(t1, R.REP_RESULTS)) if k])


def test_a_velocita_without_the_5_8_final_still_fills_those_places(ev, comp,
                                                                   entries):
    """The 5°-8° turned off: no race, no sheet, and the places still decided.

    With the finals 1°-4° alone nothing after the quarti separated anybody
    under the fourth place, and the classification goes on from the fifth with
    the one race they all rode: the 200 m. The four beaten in the quarti are in
    it like everybody else - they hold no place of their own, because no race
    gave them one.
    """
    el, cat = entries, "AL"
    qual = _qualify(ev, comp, el, final_5_8=False)
    ranked = [p.key for p in R.classify(qual, el, comp).placings if p.position]
    assert R.sprint_has_58(ev, comp, cat, "velocita") is False

    R.load_sprint_round(ev, comp, el, qual)
    t1 = ev.load_race(R.race_key(cat, "velocita", S.TURNO1))
    heats = R.bracket_heats(t1)
    t1.payload["results"] = R.heats_text([[h[0], h[1]] for h in heats])
    t1.payload[R.REP_RESULTS] = R.heats_text(R.sprint_repechages(t1))
    ev.save_race(t1)

    R.load_sprint_round(ev, comp, el, t1)
    q = ev.load_race(R.race_key(cat, "velocita", S.QUARTI))
    qh = R.bracket_heats(q)
    q.payload["results"] = R.heats_text([[h[0], h[1]] for h in qh])
    ev.save_race(q)

    # the quarti compose the semifinali and nothing else
    R.load_sprint_round(ev, comp, el, q)
    assert R.sprint_composition(ev, comp, el, q, DOC_RESULTS) == [
        (R.composition_title(ui("semifinals_full")),
         [[qh[0][0], qh[3][0]], [qh[1][0], qh[2][0]]])]

    sf = ev.load_race(R.race_key(cat, "velocita", S.SEMI))
    sh = R.bracket_heats(sf)
    sf.payload["results"] = R.heats_text([[h[0], h[1]] for h in sh])
    ev.save_race(sf)

    R.load_sprint_round(ev, comp, el, sf)
    fin = ev.load_race(R.race_key(cat, "velocita", S.FINALI))
    assert R.bracket_heats(fin, R.HEATS_58) == []
    assert len(fin.entrants) == 4          # the four finalists, nobody else
    fh = R.bracket_heats(fin)
    fin.payload["results"] = R.heats_text([[h[0], h[1]] for h in fh])
    ev.save_race(fin)

    res = R.sprint_standings(ev, comp, el, cat, "velocita")
    order = [p.key for p in res.placings]
    assert order[:4] == [fh[1][0], fh[1][1], fh[0][0], fh[0][1]]
    # from the fifth place the classification is the 200 m, in that order and
    # in no other: a rider out in the turno 1 who qualified faster than one
    # beaten in the quarti is ahead of her
    assert order[4:] == [k for k in ranked if k not in order[:4]]
    assert res.placings[7].position == 8
    beaten = [h[1] for h in qh]
    assert set(order[4:]) >= set(beaten)


def test_a_decision_taken_in_a_final_stands_in_the_classification(ev, comp,
                                                                  entries):
    """A rider squalificata in the 1°/2° final leaves the classification.

    The places renumber under her - whoever is left wins - and she is filed at
    the bottom with her decision, which is what the sheet is for.
    """
    el, cat = entries, "AL"
    qual = _qualify(ev, comp, el)
    R.load_sprint_round(ev, comp, el, qual)
    t1 = ev.load_race(R.race_key(cat, "velocita", S.TURNO1))
    heats = R.bracket_heats(t1)
    t1.payload["results"] = R.heats_text(heats)
    t1.payload[R.REP_RESULTS] = R.heats_text(R.sprint_repechages(t1))
    ev.save_race(t1)
    R.load_sprint_round(ev, comp, el, t1)
    q = ev.load_race(R.race_key(cat, "velocita", S.QUARTI))
    q.payload["results"] = R.heats_text(R.bracket_heats(q))
    ev.save_race(q)
    R.load_sprint_round(ev, comp, el, q)
    sf = ev.load_race(R.race_key(cat, "velocita", S.SEMI))
    sf.payload["results"] = R.heats_text(R.bracket_heats(sf))
    ev.save_race(sf)
    R.load_sprint_round(ev, comp, el, sf)

    fin = ev.load_race(R.race_key(cat, "velocita", S.FINALI))
    fh = R.bracket_heats(fin)
    fin.payload["results"] = R.heats_text(fh)
    R.set_status(fin, fh[1][0], Status.DSQ)
    ev.save_race(fin)

    res = R.sprint_standings(ev, comp, el, cat, "velocita")
    first = res.placings[0]
    assert first.key == fh[1][1] and first.position == 1
    out = res.placings[-1]
    assert out.key == fh[1][0] and out.status is Status.DSQ and not out.position


def test_the_eight_scheme_goes_straight_to_the_quarti(ev, comp, entries):
    """Eight qualify from the 200 m and the first round is not ridden.

    Same machinery, one round shorter - which is the point of the scheme being
    a choice on the qualifying round instead of a branch in the code.
    """
    el, cat = entries, "ED"
    key = R.sprint_qualifying(comp, cat, "velocita")
    st = R.ensure_state(ev, comp, cat, "velocita", key, el)
    st.payload[R.SCHEME] = "8"
    ev.save_race(st)
    assert R.sprint_scheme(ev, comp, cat, "velocita").note.startswith(
        "Si qualificano direttamente ai quarti")
    st.payload["times"] = {k: parse_time(f"12,{i:03d}")
                           for i, k in enumerate(st.entrants)}
    ev.save_race(st)

    nxt, n = R.load_sprint_round(ev, comp, el, st)
    assert (nxt, n) == (S.QUARTI, 4)
    q = ev.load_race(R.race_key(cat, "velocita", S.QUARTI))
    ranked = [p.key for p in R.classify(st, el, comp).placings if p.position]
    assert R.bracket_heats(q)[0] == [ranked[0], ranked[7]]


def test_a_start_order_composes_nothing_under_it(ev, comp, entries):
    """The batterie print on the results sheet that composed them, once."""
    el = entries
    qual = _qualify(ev, comp, el)
    R.load_sprint_round(ev, comp, el, qual)
    t1 = ev.load_race(R.race_key("AL", "velocita", S.TURNO1))
    t1.payload["results"] = R.heats_text(R.bracket_heats(t1))
    assert R.sprint_composition(ev, comp, el, t1, "partenti") == []
    blocks = R.sprint_composition(ev, comp, el, t1, "risultati")
    # the heading says what the block is: the start order of the round it names
    assert [b[0] for b in blocks] == ["Turno 1 - Recuperi - Ordine di Partenza"]
    blocks = R.sprint_composition(ev, comp, el, t1, "risultati_recuperi")
    assert [b[0] for b in blocks] == ["Quarti di Finale - Ordine di Partenza"]


def test_the_prove_are_marked_on_the_sheet(ev, comp, entries):
    """One column per prova, an X against whoever took it."""
    el = entries
    qual = _qualify(ev, comp, el)
    R.load_sprint_round(ev, comp, el, qual)
    t1 = ev.load_race(R.race_key("AL", "velocita", S.TURNO1))
    heats = R.bracket_heats(t1)[:1]
    runs = {"0": [heats[0][1], heats[0][0], heats[0][1]]}   # 2-1 to the second
    orders = [S.heat_result(runs["0"], heats[0])]
    res = R.heat_result(t1, heats, orders, runs=runs, n_runs=3)
    assert res.columns == ["heat_no", "run_1", "run_2", "run_3"]
    winner, loser = res.placings[0], res.placings[1]
    assert winner.key == heats[0][1] and winner.position == 1
    assert winner.data["run_1"] == "X" and winner.data["run_2"] == ""
    assert loser.data["run_2"] == "X" and loser.position == 2


# ── how the sheets read ─────────────────────────────────────────────────────

def test_a_race_under_the_kilometre_is_called_in_metres():
    """The velocità is the 200 m, and half a lap is not a distance."""
    from render.documents import distance_line as _distance_line

    assert _distance_line(27, 0.2, 0.5, 0) == "27 partenti  ·  200 m"
    assert _distance_line(0, 0.5, 1.5, 0) == "500 m  ·  1.5 giri"
    assert _distance_line(8, 3, 9, 0, unit="squadre") == \
        "8 squadre  ·  3 km  ·  9 giri"


def test_the_200_m_prints_its_time_in_bold(ev, comp, entries):
    """The qualifying mark of a velocità is what the sheet is read for."""
    from render import documents as D

    qual = _qualify(ev, comp, entries)
    doc = D.race_classification(qual, R.classify(qual, entries, comp), entries,
                                comp, doc_kind="risultati")
    time_col = next(c for c in doc.tables[0].columns if c.key == "time")
    assert time_col.bold


def test_the_batteria_is_printed_once_over_its_own_riders(ev, comp, entries):
    """Batt. first, then the placing inside it - and the number not repeated."""
    from render import documents as D

    el = entries
    qual = _qualify(ev, comp, el)
    R.load_sprint_round(ev, comp, el, qual)
    t1 = ev.load_race(R.race_key("AL", "velocita", S.TURNO1))
    heats = R.bracket_heats(t1)
    t1.payload["results"] = R.heats_text(heats)
    res = R.heat_result(t1, heats, R.bracket_orders(t1))

    doc = D.race_classification(t1, res, el, comp, doc_kind="risultati",
                                show_count=False)
    table = doc.tables[0]
    assert [c.key for c in table.columns][:3] == ["heat_no", "rank", "bib"]
    assert [r["heat_no"] for r in table.rows] == \
        [x for n in range(1, 7) for x in (n, "")]
    assert doc.info == ""          # a sheet of batterie counts nothing


def test_a_dns_in_a_round_is_ranked_on_the_200_m(ev, comp, entries):
    """DNS on the round, a place on the classifica: two different questions.

    She really did not start that turno, and the sheet of the turno files that.
    But missing a round is losing it, not abandoning the specialità: she had
    ridden the 200 m, and that time is what ranks her at the end.
    """
    el, cat = entries, "AL"
    qual = _qualify(ev, comp, el)
    R.load_sprint_round(ev, comp, el, qual)
    t1 = ev.load_race(R.race_key(cat, "velocita", S.TURNO1))
    heats = R.bracket_heats(t1)

    absent = heats[0][1]                       # qualified, then not at the gate
    t1.payload["results"] = R.heats_text([[h[0], h[1]] for h in heats])
    R.set_status(t1, absent, Status.DNS)
    ev.save_race(t1)

    # what the jury typed is what stays on disk: this reads it, it does not
    # rewrite it
    assert R.statuses_of(t1)[absent] is Status.DNS

    # the sheet of the round prints the round's own status
    result = R.heat_result(t1, heats, R.bracket_orders(t1))
    assert [p.status for p in result.placings if p.key == absent] == [Status.DNS]

    # ...and it stays on that sheet: the classification of the specialità does
    # not carry it, the way it does not carry a REL
    statuses = R.sprint_statuses(ev, comp, cat, "velocita",
                                 R.statuses_of(t1))
    assert absent not in statuses
    standings = R.sprint_standings(ev, comp, el, cat, "velocita")
    out = [p for p in standings.placings if p.key == absent]
    assert out and out[0].status is Status.OK and out[0].position


def test_a_dsq_in_a_round_stays_a_dsq(ev, comp, entries):
    """The other decision: a disqualification follows her to the end.

    A DNS says she was not there for that round; a DSQ says she was thrown out
    of the specialità, and no 200 m time buys that back.
    """
    el, cat = entries, "AL"
    qual = _qualify(ev, comp, el)
    R.load_sprint_round(ev, comp, el, qual)
    t1 = ev.load_race(R.race_key(cat, "velocita", S.TURNO1))
    heats = R.bracket_heats(t1)

    out_key = heats[0][1]
    t1.payload["results"] = R.heats_text([[h[0], h[1]] for h in heats])
    R.set_status(t1, out_key, Status.DSQ)
    ev.save_race(t1)

    statuses = R.sprint_statuses(ev, comp, cat, "velocita", R.statuses_of(t1))
    assert statuses[out_key] is Status.DSQ
    standings = R.sprint_standings(ev, comp, el, cat, "velocita")
    out = [p for p in standings.placings if p.key == out_key]
    assert out and out[0].status is Status.DSQ and not out[0].position


def test_a_dns_on_the_200_m_stays_a_dns(ev, comp, entries):
    """She never took a start at all: that one is a real non-starter."""
    el, cat = entries, "AL"
    qual = _qualify(ev, comp, el)
    never = qual.entrants[-1]
    del qual.payload["times"][never]           # no time: she never rode
    R.set_status(qual, never, Status.DNS)
    ev.save_race(qual)

    assert never not in R.sprint_started(ev, comp, cat, "velocita")
    statuses = R.sprint_statuses(ev, comp, cat, "velocita",
                                 R.statuses_of(qual))
    assert statuses[never] is Status.DNS


def test_a_rel_stays_in_its_batteria(ev, comp, entries):
    """A declassata keeps her place and her batteria: «2° REL», where she rode.

    REL is a place with a word next to it, not a way out of the sheet. Sorted
    to the bottom like a DNF she left her batteria and - the Batt. column
    printing her number again down there - opened what read as another one.
    """
    el, cat = entries, "AL"
    qual = _qualify(ev, comp, el)
    R.load_sprint_round(ev, comp, el, qual)
    t1 = ev.load_race(R.race_key(cat, "velocita", S.TURNO1))
    heats = R.bracket_heats(t1)
    t1.payload["results"] = R.heats_text([[h[0], h[1]] for h in heats])

    down = heats[0][0]                          # the winner of the first heat
    R.set_status(t1, down, Status.REL)
    ev.save_race(t1)

    res = R.heat_result(t1, heats, R.bracket_orders(t1))
    first = res.placings[0]
    assert first.key == down                    # still the first line of the sheet
    assert first.status is Status.REL and first.position == 1
    assert first.label == "1° REL"              # the place, with REL beside it
    assert first.data["heat_no"] == 1

    # ...and it stays there: a relegation settles one prova, it does not follow
    # the rider onto the classification of the specialità the way a DNF does
    ev.save_race(t1)
    out = R.sprint_statuses(ev, comp, cat, "velocita", R.all_statuses(t1))
    assert down not in out
    standings = R.sprint_standings(ev, comp, el, cat, "velocita")
    assert [p.status for p in standings.placings if p.key == down] == [Status.OK]

    # and every batteria is still one block, in the order they were ridden
    assert [p.data["heat_no"] for p in res.placings] == \
        [h + 1 for h in range(len(heats)) for _ in range(2)]


def test_the_two_races_of_a_round_keep_their_own_decisions(ev, comp, entries):
    """Turno 1 and its recuperi are two races: two sheets, two sets of statuses.

    A rider relegated in the recuperi was not relegated in the turno, and one
    who did not turn up for the recuperi rode the turno perfectly well. Stored
    in one place they contradicted whichever sheet they did not belong to.
    """
    el, cat = entries, "AL"
    qual = _qualify(ev, comp, el)
    R.load_sprint_round(ev, comp, el, qual)
    t1 = ev.load_race(R.race_key(cat, "velocita", S.TURNO1))
    heats = R.bracket_heats(t1)
    t1.payload["results"] = R.heats_text([[h[0], h[1]] for h in heats])
    rep = R.sprint_repechages(t1)
    t1.payload[R.REP_RESULTS] = R.heats_text(rep)

    in_turno, in_rep = heats[0][0], rep[0][0]
    R.set_status(t1, in_turno, Status.REL)                       # the round's
    R.set_status(t1, in_rep, Status.DNS, R.STATUSES_REP)         # the recuperi's
    ev.save_race(t1)
    t1 = ev.load_race(R.race_key(cat, "velocita", S.TURNO1))     # and reloaded

    assert R.statuses_of(t1) == {in_turno: Status.REL}
    assert R.statuses_of(t1, R.STATUSES_REP) == {in_rep: Status.DNS}
    # each sheet reads its own, and neither carries the other's
    turno = R.heat_result(t1, heats, R.bracket_orders(t1))
    assert {p.key: p.status for p in turno.placings if p.status is not Status.OK} \
        == {in_turno: Status.REL}
    recuperi = R.heat_result(t1, rep, R.bracket_orders(t1, R.REP_RESULTS),
                             scope=R.STATUSES_REP)
    assert {p.key: p.status for p in recuperi.placings
            if p.status is not Status.OK} == {in_rep: Status.DNS}

    # the classification of the specialità is the one that reads both
    both = R.all_statuses(t1)
    assert both == {in_turno: Status.REL, in_rep: Status.DNS}


# ── what the programme states, and who overrules it ─────────────────────────
#
# Three answers, in this order: the day, the programme, the inference. The
# third is what every file written before `ProgrammeItem` carried these fields
# falls back on, so it is tested first - it is the one that must not have moved.

def test_the_scheme_is_inferred_from_the_rounds_when_nobody_states_it(ev, comp):
    """A programme that says nothing reads exactly as it always did."""
    assert R.sprint_scheme(ev, comp, "ES", "velocita").key == "12"   # has a Turno 1


def test_a_programme_that_states_the_scheme_is_believed(ev, comp):
    import dataclasses

    item = comp.scheduled("ES", "velocita")
    stated = dataclasses.replace(comp, programme=[
        dataclasses.replace(i, scheme="8") if i is item else i
        for i in comp.programme])
    assert R.sprint_scheme(ev, stated, "ES", "velocita").key == "8"


def test_the_day_beats_the_programme(ev, comp, entries):
    """The jury at the track has the last word - it always did."""
    import dataclasses

    item = comp.scheduled("ES", "velocita")
    stated = dataclasses.replace(comp, programme=[
        dataclasses.replace(i, scheme="8") if i is item else i
        for i in comp.programme])
    qual = R.sprint_qualifying(stated, "ES", "velocita")
    st = R.ensure_state(ev, stated, "ES", "velocita", qual, entries)
    st.payload[R.SCHEME] = "12"
    ev.save_race(st)
    assert R.sprint_scheme(ev, stated, "ES", "velocita").key == "12"


def test_the_5_8_final_is_stated_by_the_programme_before_it_is_inferred(ev, comp):
    """`False` has to survive being stated: it is a race that is not ridden."""
    import dataclasses

    item = comp.scheduled("ES", "velocita")
    # inferred: the CITA26 finals round files no risultati 5°-8°
    assert R.sprint_has_58(ev, comp, "ES", "velocita") is False

    for stated in (True, False):
        prog = dataclasses.replace(comp, programme=[
            dataclasses.replace(i, final_5_8=stated) if i is item else i
            for i in comp.programme])
        assert R.sprint_has_58(ev, prog, "ES", "velocita") is stated
