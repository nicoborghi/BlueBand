"""The keirin: the UCI tables of 3.2.135 and the tournament they describe.

The first round is composed by the jury - a keirin is seeded from nothing - and
everything after it comes from the tables: the recuperi, the semifinali, the two
finals and the classification. The tables themselves are checked against the
worked example printed in the regulation (28 riders, four batterie of seven),
line for line: that example is the specification.
"""

import pytest

from core import race as R
from core.config import DOC_RESULTS, DOC_RESULTS_REP
from core.entries import import_master, save_import
from core.formats import keirin as K
from core.models import Status


@pytest.fixture(scope="session")
def entries(iscritti_path, comp):
    return import_master(iscritti_path, comp)


@pytest.fixture
def ev(store, entries):
    save_import(store, entries)
    return store


# ── the tables themselves ───────────────────────────────────────────────────

def test_the_number_entered_picks_the_tournament():
    """One row of 3.2.135 per band, and the bands meet without a gap."""
    assert [s.heats for s in K.scheme_for(36).stages] == [6, 2]
    assert K.scheme_for(36).stages[0].qualify == 1
    assert K.scheme_for(20).stages[0] == K.Stage("Turno 1", 3, 2, 3, 2)
    assert K.scheme_for(28).stages[0] == K.Stage("Turno 1", 4, 2, 4, 1)
    # under fifteen riders there are no recuperi and no semifinali at all: the
    # two batterie of the first round send three each to the final for the title
    assert [s.key for s in K.scheme_for(12).stages] == [K.TURNO1]
    assert K.scheme_for(12).stages[0].qualify == 3
    # a quarter-final appears from 43 riders up
    assert [s.key for s in K.scheme_for(45).stages] == [K.TURNO1, K.QUARTI,
                                                        K.SEMI]
    # outside the table the nearest row still reads correctly
    assert K.scheme_for(8).stages[0].heats == 2
    assert K.scheme_for(200).stages[0].heats == 10


def test_every_row_of_the_table_fills_the_semifinals():
    """Twelve riders reach the two semifinali, whichever band is run.

    The arithmetic of the table is what says the transcription is right: a row
    that sent eleven or thirteen riders into two batterie of six would be a
    typo, and it would only show up on the day.
    """
    for sch in K.SCHEMES[1:]:
        into = sch.stages[-2].through if len(sch.stages) > 1 else 0
        assert into == 12, sch


def test_the_repechages_reproduce_the_uci_table():
    """28 riders, four batterie of seven, two through: the printed example."""
    orders = [[f"{h}{i}" for i in range(1, 8)] for h in "ABCD"]
    left = K.not_qualified(orders, 2)
    assert K.repechage_heats(left, 4) == [
        ["A3", "D4", "C5", "B6", "A7"],
        ["B3", "C4", "B5", "A6", "D7"],
        ["C3", "B4", "A5", "D6", "C7"],
        ["D3", "A4", "D5", "C6", "B7"]]


def test_the_semifinals_reproduce_the_uci_table():
    """Same example: the winners, then the seconds the other way round."""
    orders = [[f"{h}{i}" for i in range(1, 8)] for h in "ABCD"]
    rep = [[f"R{h}{i}" for i in range(1, 6)] for h in "ABCD"]
    stage = K.scheme_for(28).stages[0]
    assert K.next_heats(stage, orders, rep, 2) == [
        ["A1", "D1", "B2", "C2", "RA1", "RD1"],
        ["B1", "C1", "A2", "D2", "RB1", "RC1"]]


def test_a_repechage_barely_ever_meets_the_same_batteria_twice():
    """What the matrix is for: as few riders as possible who have already met.

    Six batterie with one rider through - the band the Allievi are run under -
    leave five riders each. The riders just under the cut go one to each
    recupero, and no recupero ever takes three from the same batteria: with six
    batterie read backwards and one further round at every row, a batteria can
    only come back once. The printed UCI table does exactly the same thing
    (QB3 and QB5 both ride recupero B in the 28-rider example): perfection is
    not on offer here, and the jury can edit what comes out.
    """
    orders = [[f"{h}{i}" for i in range(1, 7)] for h in "ABCDEF"]
    heats = K.repechage_heats(K.not_qualified(orders, 1), 6)
    assert all(len(h) == 5 for h in heats)
    assert [h[0] for h in heats] == [f"{c}2" for c in "ABCDEF"]
    for heat in heats:
        assert len({k[0] for k in heat}) >= len(heat) - 1


def test_the_finals_are_named_after_the_places_they_ride_for():
    """Not a constant: ten riders make a 1°-6° and a 7°-10°."""
    assert K.final_labels(6, 6) == ("1°-6°", "7°-12°")
    assert K.final_labels(6, 4) == ("1°-6°", "7°-10°")
    assert K.final_labels(6, 0) == ("1°-6°", "")


def test_a_small_keirin_goes_from_the_batterie_straight_to_the_finals():
    """Twelve riders: no recuperi, no semifinali - the two batterie decide.

    The same machinery one round shorter, which is the point of the tournament
    being a row of a table instead of a branch in the code.
    """
    sch = K.scheme_for(12)
    assert sch.next_key(K.TURNO1) == K.FINALI
    orders = [[f"A{i}" for i in range(1, 7)], [f"B{i}" for i in range(1, 7)]]
    top, rest = K.final_heats(orders, sch.stages[0].qualify)
    assert top == ["A1", "B1", "A2", "B2", "A3", "B3"]
    assert rest == ["A4", "B4", "A5", "B5", "A6", "B6"]
    assert K.final_labels(len(top), len(rest)) == ("1°-6°", "7°-12°")
    # ten riders make two batterie of five, and the second final is 7°-10°
    short = [h[:5] for h in orders]
    top, rest = K.final_heats(short, 3)
    assert K.final_labels(len(top), len(rest)) == ("1°-6°", "7°-10°")


def test_a_start_order_goes_up_by_dorsale():
    """Who is in a batteria is the composition; the sheet is read by number."""
    assert K.in_bib_order([["12", "3", "40"], ["7", "1"]]) == \
        [["3", "12", "40"], ["1", "7"]]


def test_the_batteria_of_a_rider_who_did_not_ride_leaves_her_out():
    """A DNS qualifies for nothing and rides no recupero - but is not lost."""
    orders = [["1", "2", "3"], ["4", "5", "6"]]
    statuses = {"2": Status.DNS}
    assert K.not_qualified(orders, 1, statuses) == [["3"], ["5", "6"]]
    # she is still somebody the round left behind: the classification files her
    assert K.left_behind(orders, 1, statuses) == ["3", "5", "6", "2"]


# ── the whole event, through the service ────────────────────────────────────

CAT, EVENT = "AL", "keirin"


def _compose_first_round(ev, comp, el, cat=CAT):
    """What the jury types: the entrants dealt over the batterie of the table."""
    st = R.ensure_state(ev, comp, cat, EVENT, K.TURNO1, el)
    n = R.keirin_scheme(comp, el, cat, EVENT).stages[0].heats
    heats = [[] for _ in range(n)]
    for i, key in enumerate(st.entrants):
        heats[i % n].append(key)
    st.payload["heats"] = R.heats_text(K.in_bib_order(heats))
    ev.save_race(st)
    return st


def _ride(state, key="heats", results="results"):
    """Every batteria finishes in the order it was composed in."""
    state.payload[results] = R.heats_text(R.bracket_heats(state, key))
    return R.bracket_heats(state, key)


def test_the_scheme_is_read_from_the_riders_actually_entered(ev, comp, entries):
    sch = R.keirin_scheme(comp, entries, CAT, EVENT)
    n = len(R.keirin_entrants(entries, comp, CAT, EVENT))
    assert sch.lo <= n <= sch.hi
    assert sch.stages[0].heats == R.keirin_heats(
        comp, entries, R.ensure_state(ev, comp, CAT, EVENT, K.TURNO1, entries))


def test_a_keirin_runs_from_the_first_round_to_the_champion(ev, comp, entries):
    """The whole tournament: every round composed by the sheet before it."""
    el = entries
    t1 = _compose_first_round(ev, comp, el)
    stage = R.keirin_scheme(comp, el, CAT, EVENT).stages[0]
    heats = _ride(t1)
    ev.save_race(t1)

    # the risultati of the first round compose its recuperi, and nothing else
    what, n = R.load_keirin_round(ev, comp, el, t1, DOC_RESULTS)
    assert (what, n) == (K.REPECHAGES, stage.rep_heats)
    rep = R.bracket_heats(t1, R.REP_HEATS)
    # everybody the batterie did not qualify, and nobody twice
    left = {k for h in heats for k in h[stage.qualify:]}
    assert {k for h in rep for k in h} == left
    # and the riders just under the cut are one to each recupero, so that no
    # batteria sends two of them into the same one
    where = {k: i for i, h in enumerate(heats) for k in h}
    assert [where[h[0]] for h in rep] == list(range(len(rep)))
    for heat in rep:
        assert len({where[k] for k in heat}) >= len(heat) - 1

    # the risultati of the recuperi compose the round after
    _ride(t1, R.REP_HEATS, R.REP_RESULTS)
    ev.save_race(t1)
    what, n = R.load_keirin_round(ev, comp, el, t1, DOC_RESULTS_REP)
    assert (what, n) == (K.SEMI, 2)

    sf = ev.load_race(R.race_key(CAT, EVENT, K.SEMI))
    assert len(sf.entrants) == 12 and len(R.bracket_heats(sf)) == 2
    # the winners of the batterie and the ones the recuperi sent back, and
    # every batteria in order of dorsale
    assert all(h == sorted(h, key=int) for h in R.bracket_heats(sf))
    semis = _ride(sf)
    ev.save_race(sf)

    # the risultati of the semifinali compose both finals at once
    what, n = R.load_keirin_round(ev, comp, el, sf, DOC_RESULTS)
    assert (what, n) == (K.FINALI, 2)
    fin = ev.load_race(R.race_key(CAT, EVENT, K.FINALI))
    assert R.keirin_final_labels(fin) == ("1°-6°", "7°-12°")
    top = R.bracket_heats(fin)[0]
    low = R.bracket_heats(fin, R.HEATS_B)[0]
    assert len(top) == 6 and len(low) == 6
    assert set(top) == {k for h in semis for k in h[:3]}
    assert len(fin.entrants) == 12

    fin.payload["results"] = R.heats_text([top])
    fin.payload[R.RESULTS_B] = R.heats_text([low])
    ev.save_race(fin)

    res = R.keirin_standings(ev, comp, el, CAT, EVENT)
    order = [p.key for p in res.placings]
    assert order[:6] == top                # the final for the title
    assert order[6:12] == low              # and the one under it
    assert res.placings[0].position == 1 and res.placings[11].position == 12
    # everybody entered is on the classification, and only once
    assert len(order) == len(set(order)) == len(
        R.keirin_entrants(el, comp, CAT, EVENT))


def test_a_keirin_with_one_final_sends_nobody_to_the_second(ev, comp, entries):
    """The jury's own decision, taken on the first round: one final, not two.

    The table of 3.2.135 ends with 1°-6° and 7°-12°; a programme that rides
    only the first is not running a different tournament - the semifinali
    qualify exactly the same six - it just does not line the others up again.
    They keep the places the round they went out in gives them, which is what
    the classification does for everybody under the finals anyway.
    """
    el = entries
    t1 = _compose_first_round(ev, comp, el)
    assert R.keirin_has_final_b(ev, comp, CAT, EVENT)   # the register plans it
    t1.payload[R.FINAL_B] = False
    _ride(t1)
    ev.save_race(t1)
    R.load_keirin_round(ev, comp, el, t1, DOC_RESULTS)
    _ride(t1, R.REP_HEATS, R.REP_RESULTS)
    ev.save_race(t1)
    assert not R.keirin_has_final_b(ev, comp, CAT, EVENT)

    R.load_keirin_round(ev, comp, el, t1, DOC_RESULTS_REP)
    sf = ev.load_race(R.race_key(CAT, EVENT, K.SEMI))
    semis = _ride(sf)
    ev.save_race(sf)

    what, n = R.load_keirin_round(ev, comp, el, sf, DOC_RESULTS)
    assert (what, n) == (K.FINALI, 1)                   # one final, not two
    fin = ev.load_race(R.race_key(CAT, EVENT, K.FINALI))
    top = R.bracket_heats(fin)[0]
    assert set(top) == {k for h in semis for k in h[:3]}
    assert not R.bracket_heats(fin, R.HEATS_B)
    assert len(fin.entrants) == 6
    assert R.keirin_final_labels(fin) == ("1°-6°", "")
    # and the sheet that composed it publishes that one batteria, once
    assert len(R.keirin_composition(comp, el, sf, DOC_RESULTS,
                                    final_b=False)) == 1

    fin.payload["results"] = R.heats_text([top])
    ev.save_race(fin)
    res = R.keirin_standings(ev, comp, el, CAT, EVENT)
    order = [p.key for p in res.placings]
    assert order[:6] == top
    # the six the semifinali did not qualify are 7° and down, ridden or not
    assert set(order[6:12]) == {k for h in semis for k in h[3:]}
    assert len(order) == len(set(order)) == len(
        R.keirin_entrants(el, comp, CAT, EVENT))


def test_with_one_final_the_classifica_generale_is_that_final(ev, comp,
                                                              entries):
    """One final, one classification: its six riders and nobody else.

    Two finals are filed one under the other because each of them is a race
    that was ridden and files its own decisions. With only the finale 1°-6°
    the classifica generale *is* its result: no other race placed anybody, so
    the sheet carries the six places the tournament decided and stops there.
    """
    from ui.pages.races import _keirin_blocks

    el = entries
    t1 = _compose_first_round(ev, comp, el)
    t1.payload[R.FINAL_B] = False
    _ride(t1)
    ev.save_race(t1)
    R.load_keirin_round(ev, comp, el, t1, DOC_RESULTS)
    _ride(t1, R.REP_HEATS, R.REP_RESULTS)
    ev.save_race(t1)
    R.load_keirin_round(ev, comp, el, t1, DOC_RESULTS_REP)
    sf = ev.load_race(R.race_key(CAT, EVENT, K.SEMI))
    _ride(sf)
    ev.save_race(sf)
    R.load_keirin_round(ev, comp, el, sf, DOC_RESULTS)

    fin = ev.load_race(R.race_key(CAT, EVENT, K.FINALI))
    top = R.bracket_heats(fin)[0]
    fin.payload["results"] = R.heats_text([list(reversed(top))])
    ev.save_race(fin)

    res = R.keirin_standings(ev, comp, el, CAT, EVENT)
    result, extra, block_title = _keirin_blocks(fin, res, el, comp, 10,
                                                False, True, [])
    assert not extra and not block_title
    # only the six who rode it, in the order they finished it
    assert [p.key for p in result.placings] == list(reversed(top))
    assert [p.position for p in result.placings] == [1, 2, 3, 4, 5, 6]


def test_only_the_riders_a_round_left_behind_ride_its_recuperi(ev, comp,
                                                              entries):
    """The pool of a recupero is not the categoria: it is who did not qualify.

    It is what the composition grid measures "non ancora in batteria" against,
    and what says that a rider already through has no business in a recupero.
    """
    el = entries
    t1 = _compose_first_round(ev, comp, el)
    heats = _ride(t1)
    ev.save_race(t1)
    pool = R.keirin_repechage_pool(comp, el, t1)
    qualify = R.keirin_scheme(comp, el, CAT, EVENT).stages[0].qualify
    assert set(pool) == {k for h in heats for k in h[qualify:]}
    assert not {h[0] for h in heats} & set(pool)


def test_below_the_finals_the_round_reached_ranks_the_rider(ev, comp, entries):
    """Out in the recuperi is ahead of out in the first round, and inside a
    round the place in the batteria decides."""
    el = entries
    t1 = _compose_first_round(ev, comp, el)
    heats = _ride(t1)
    ev.save_race(t1)
    R.load_keirin_round(ev, comp, el, t1, DOC_RESULTS)
    rep = R.bracket_heats(t1, R.REP_HEATS)
    _ride(t1, R.REP_HEATS, R.REP_RESULTS)
    # one rider is thrown out of her batteria in the first round: she never
    # rides a recupero, so she goes out there and is filed with her decision
    out = heats[0][-1]
    R.set_status(t1, out, Status.DSQ)
    ev.save_race(t1)

    res = R.keirin_standings(ev, comp, el, CAT, EVENT)
    order = [p.key for p in res.placings]
    # the recuperi are the last round ridden: their seconds come first, then
    # all their thirds, and so on down - the UCI's own "all ranked 13"
    seconds = [h[1] for h in rep]
    assert order[:len(seconds)] == seconds
    assert order[len(seconds):2 * len(seconds)] == [h[2] for h in rep]
    # and the squalificata is at the bottom, without a placing
    last = res.placings[-1]
    assert last.key == out and last.status is Status.DSQ and not last.position


def test_a_relegation_settles_a_batteria_and_stops_there(ev, comp, entries):
    """REL says who won that batteria; it does not follow the rider about."""
    el = entries
    t1 = _compose_first_round(ev, comp, el)
    heats = _ride(t1)
    down = heats[0][0]
    R.set_status(t1, down, Status.REL)
    ev.save_race(t1)

    # on the sheet of the round she keeps her place, with the word beside it
    sheet = R.heat_result(t1, heats, R.bracket_orders(t1))
    first = next(p for p in sheet.placings if p.key == down)
    assert first.label == "1° REL" and first.data["heat_no"] == 1
    # ...and on the classification of the specialità she is classified
    assert down not in R.keirin_statuses(R.all_statuses(t1))


def test_the_two_races_of_a_round_keep_their_own_decisions(ev, comp, entries):
    """A rider declassata in the recuperi was not declassata in the turno."""
    el = entries
    t1 = _compose_first_round(ev, comp, el)
    _ride(t1)
    ev.save_race(t1)
    R.load_keirin_round(ev, comp, el, t1, DOC_RESULTS)
    rep = R.bracket_heats(t1, R.REP_HEATS)
    _ride(t1, R.REP_HEATS, R.REP_RESULTS)

    in_rep = rep[0][0]
    R.set_status(t1, in_rep, Status.DNS, R.STATUSES_REP)
    ev.save_race(t1)
    t1 = ev.load_race(R.race_key(CAT, EVENT, K.TURNO1))

    assert R.statuses_of(t1) == {}
    assert R.statuses_of(t1, R.STATUSES_REP) == {in_rep: Status.DNS}
    assert R.all_statuses(t1) == {in_rep: Status.DNS}
    # and she did not qualify for the semifinali, whatever the order says
    what, _n = R.load_keirin_round(ev, comp, el, t1, DOC_RESULTS_REP)
    sf = ev.load_race(R.race_key(CAT, EVENT, what))
    assert in_rep not in sf.entrants


def test_a_category_of_twenty_rides_three_batterie(ev, comp, entries):
    """DA: another row of the table, same machinery - two through per batteria."""
    el = entries
    t1 = _compose_first_round(ev, comp, el, cat="DA")
    stage = R.keirin_scheme(comp, el, "DA", EVENT).stages[0]
    assert (stage.heats, stage.qualify) == (3, 2)
    heats = _ride(t1)
    ev.save_race(t1)

    what, n = R.load_keirin_round(ev, comp, el, t1, DOC_RESULTS)
    assert (what, n) == (K.REPECHAGES, 3)
    _ride(t1, R.REP_HEATS, R.REP_RESULTS)
    ev.save_race(t1)
    what, _n = R.load_keirin_round(ev, comp, el, t1, DOC_RESULTS_REP)
    sf = ev.load_race(R.race_key("DA", EVENT, K.SEMI))
    # six from the batterie, six from the recuperi
    assert len(sf.entrants) == 12
    assert {k for h in heats for k in h[:2]} <= set(sf.entrants)


# ── what the programme states, and who overrules it ─────────────────────────

def test_the_second_final_is_stated_by_the_programme_before_it_is_inferred(
        ev, comp, entries):
    """The keirin's own version of the velocità's 5°-8°: three answers, in order."""
    import dataclasses

    # inferred: the CITA26 finals round files a risultati finale B
    assert R.keirin_has_final_b(ev, comp, "AL", EVENT) is True

    item = comp.scheduled("AL", EVENT)
    stated = dataclasses.replace(comp, programme=[
        dataclasses.replace(i, final_b=False) if i is item else i
        for i in comp.programme])
    assert R.keirin_has_final_b(ev, stated, "AL", EVENT) is False

    # ... and the jury on the day still beats it
    first = R.keirin_first_round(stated, "AL", EVENT)
    st = R.ensure_state(ev, stated, "AL", EVENT, first, entries)
    st.payload[R.FINAL_B] = True
    ev.save_race(st)
    assert R.keirin_has_final_b(ev, stated, "AL", EVENT) is True
