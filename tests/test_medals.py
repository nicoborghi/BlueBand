"""Il medagliere: which race decides a specialità, and who its places go to."""

from __future__ import annotations

import pytest

from core import medals as M
from core import recap as RC
from core.i18n import label
from core.config import Category, Competition, Event, ProgrammeItem, Round
from core.models import (EntryList, EventEntry, RaceState, Rider, Status,
                         Team, race_id)

SCRATCH, PURSUIT = "scratch", "ins_squadre"


@pytest.fixture
def comp():
    """Two specialità of one categoria: a bunch race and a team pursuit.

    Written here rather than taken from the championship's own programme: what
    is under test is which round a place is read off, and that has to be
    stated in the test rather than looked up in a file that changes with the
    season.
    """
    rounds = [Round(key="Qualificazioni"), Round(key="Finale")]
    return Competition(
        categories={"AL": Category(code="AL")},
        events={SCRATCH: Event(code=SCRATCH, name="Scratch", fmt="group"),
                PURSUIT: Event(code=PURSUIT, name="Inseguimento a Squadre",
                               fmt="timed_team", team_size=2)},
        programme=[ProgrammeItem(cat="AL", event=SCRATCH, rounds=rounds),
                   ProgrammeItem(cat="AL", event=PURSUIT,
                                 rounds=[Round(key="Finali")])])


@pytest.fixture
def el():
    """Four riders of three regioni, two of them a quartetto."""
    riders = {}
    for key, bib, region, club in (("a", 1, "LOMBARDIA", "GS Pippo"),
                                   ("b", 2, "VENETO", "GS Pluto"),
                                   ("c", 3, "TOSCANA", "GS Paperino"),
                                   ("d", 4, "LOMBARDIA", "GS Paperino")):
        riders[key] = Rider(key=key, bib=bib, cat="AL", last_name=region[:3],
                            first_name="Mario", region=region, club=club,
                            events={SCRATCH: EventEntry(),
                                    PURSUIT: EventEntry()})
    teams = {"AL:ins_squadre:LOMBARDIA:": Team(
        key="AL:ins_squadre:LOMBARDIA:", cat="AL", event=PURSUIT,
        region="LOMBARDIA", riders=["a", "d"])}
    return EntryList(riders=riders, teams=teams)


def _save(store, cat, event, round_key, fmt, **payload) -> None:
    store.save_race(RaceState(
        race_id=race_id(cat, event, round_key), cat=cat, event=event,
        round_key=round_key, fmt=fmt, entrants=["1", "2", "3", "4"],
        payload=payload))


def _bunch(store, round_key, arrival, **payload):
    """One bunch race, decided by the arrival the jury typed."""
    _save(store, "AL", SCRATCH, round_key, "scratch", sprints=arrival,
          **payload)


# ── which race decides a specialità ─────────────────────────────────────────

def test_the_last_round_of_the_programme_is_the_one_that_places(store, comp, el):
    _bunch(store, "Qualificazioni", "3,4,1,2")
    _bunch(store, "Finale", "1,2,3,4")
    result, where, complete = M.final_result(store, comp, el, "AL", SCRATCH)
    assert where == "Finale" and complete
    assert [p.key for p in result.placings][:3] == ["1", "2", "3"]


def test_a_specialita_whose_final_has_not_been_ridden_is_not_concluded(
        store, comp, el):
    """The qualifying places nobody: a medagliere counts titles, not heats."""
    _bunch(store, "Qualificazioni", "3,4,1,2")
    result, where, complete = M.final_result(store, comp, el, "AL", SCRATCH)
    assert where == "Qualificazioni" and not complete
    assert result is not None          # it is a ranking, just not the final one

    found = M.survey(store, comp, el)
    assert [(p.cat, p.event) for p in found.places] == []
    assert ("AL", SCRATCH, True) in found.open_events


def test_the_open_specialita_are_counted_only_when_asked_for(store, comp, el):
    _bunch(store, "Qualificazioni", "3,4,1,2")
    found = M.survey(store, comp, el, include_unfinished=True)
    assert [(p.position, p.key) for p in found.places] == [(1, "3"), (2, "4"),
                                                           (3, "1")]
    assert all(not p.complete for p in found.places)


def test_a_startlist_without_a_result_places_nobody(store, comp, el):
    _bunch(store, "Qualificazioni", "")
    _bunch(store, "Finale", "")
    found = M.survey(store, comp, el, include_unfinished=True)
    assert found.places == []
    assert found.open_events == [("AL", SCRATCH, False),
                                 ("AL", PURSUIT, False)]


# ── who the place belongs to ────────────────────────────────────────────────

def test_a_place_goes_to_the_squadra_of_the_rider(store, comp, el):
    _bunch(store, "Finale", "2,1,3,4")
    places = M.podiums(store, comp, el)
    assert [(p.position, p.teams) for p in places] == [
        (1, ["VENETO"]), (2, ["LOMBARDIA"]), (3, ["TOSCANA"])]


def test_the_squadra_is_whatever_the_programme_says_it_is(store, comp, el):
    _bunch(store, "Finale", "2,1,3,4")
    places = M.podiums(store, comp, el, group=RC.BY_CLUB)
    assert [p.teams for p in places] == [["GS Pluto"], ["GS Pippo"],
                                         ["GS Paperino"]]


def test_a_quartetto_counts_for_every_squadra_behind_it(store, comp, el):
    """One regione at a championship; by società it can be two, and both count."""
    key = "AL:ins_squadre:LOMBARDIA:"
    assert M.teams_of(key, el, "AL") == ["LOMBARDIA"]
    assert M.teams_of(key, el, "AL", RC.BY_CLUB) == ["GS Pippo", "GS Paperino"]


def test_a_disqualified_entrant_carries_no_place(store, comp, el):
    _bunch(store, "Finale", "2,1,3,4")
    state = store.load_race(race_id("AL", SCRATCH, "Finale"))
    state.statuses = {"1": Status.DSQ.value}
    store.save_race(state)
    places = M.podiums(store, comp, el)
    assert "1" not in [p.key for p in places]


# ── the table ───────────────────────────────────────────────────────────────

def test_the_medagliere_ranks_by_gold_then_silver_then_bronze():
    places = [M.Podium(cat="AL", event=SCRATCH, position=n, key=str(n),
                       label=str(n), teams=[team])
              for n, team in ((1, "VENETO"), (2, "LOMBARDIA"),
                              (3, "LOMBARDIA"), (2, "LOMBARDIA"))]
    table = M.medal_table(places)
    assert [(t.team, t.gold, t.silver, t.bronze, t.total) for t in table] == [
        ("VENETO", 1, 0, 0, 1), ("LOMBARDIA", 0, 2, 1, 3)]


def test_a_squadra_with_no_medals_is_not_a_line_of_the_table(store, comp, el):
    _bunch(store, "Finale", "2,1,3")     # 4 (LOMBARDIA) is not placed at all
    table = M.medal_table(M.podiums(store, comp, el))
    assert [t.team for t in table] == ["VENETO", "LOMBARDIA", "TOSCANA"]


def test_a_broken_race_costs_its_own_specialita_and_no_more(store, comp, el):
    """A file the scoring cannot read must not take the page down with it."""
    _bunch(store, "Finale", "not, a, result")
    found = M.survey(store, comp, el, include_unfinished=True)
    assert found.places == []
    assert ("AL", SCRATCH, False) in found.open_events


def test_two_squadre_with_the_same_medals_share_a_position():
    """1, 2, 2, 4 - nothing is left to separate them, so nothing pretends to."""
    places = [M.Podium(cat="AL", event=SCRATCH, position=n, key=str(n),
                       label=str(n), teams=[team])
              for n, team in ((1, "VENETO"), (1, "LOMBARDIA"),
                              (1, "TOSCANA"), (2, "LAZIO"))]
    table = M.medal_table(places)
    assert [(pos, t.team) for pos, t in M.ranked(table)] == [
        (1, "LOMBARDIA"), (1, "TOSCANA"), (1, "VENETO"), (4, "LAZIO")]


# ── the printed sheet ───────────────────────────────────────────────────────

def test_the_medagliere_prints_what_the_page_shows(store, comp, el):
    from render import documents as D
    from render.render import to_html

    _bunch(store, "Finale", "2,1,3,4")
    found = M.survey(store, comp, el)
    doc = D.medal_table(found, comp)
    html = to_html(doc, comp, banner=False, footer=False)

    # the table itself, and the podiums it is counted from under it
    assert [t.title for t in doc.tables] == ["", "PODI"]
    assert doc.info.startswith("1 specialità conclusa")
    for region in ("VENETO", "LOMBARDIA", "TOSCANA"):
        assert region in html
    # the inseguimento a squadre has not been ridden: named, not counted
    assert "Inseguimento" in doc.blocks[0].text
    assert found.counted == 1


def test_the_printed_medagliere_can_be_the_table_alone(store, comp, el):
    _bunch(store, "Finale", "2,1,3,4")
    from render import documents as D
    doc = D.medal_table(M.survey(store, comp, el), comp, detail=False)
    assert len(doc.tables) == 1 and doc.slug == "medagliere"


def test_a_provisional_medagliere_says_so_on_the_paper(store, comp, el):
    from render import documents as D
    _bunch(store, "Qualificazioni", "2,1,3,4")
    doc = D.medal_table(M.survey(store, comp, el, include_unfinished=True),
                        comp)
    assert "provvisorio" in doc.legend


# ── a madison is classified by coppia number, not by dorsale ────────────────

MADISON = "madison"


def test_a_madison_place_goes_to_the_coppia_and_not_to_a_dorsale(store):
    """The placing key of a madison is the coppia's number, not an entrant.

    Read as a dorsale it matched whoever wears that number in the categoria -
    one rider, and one who need not even be in the race. The medagliere has to
    map it back to the coppia, the way the race page does.
    """
    from core.models import Pair

    comp = Competition(
        categories={"AL": Category(code="AL")},
        events={MADISON: Event(code=MADISON, name="Madison", fmt="madison")},
        programme=[ProgrammeItem(cat="AL", event=MADISON,
                                 rounds=[Round(key="Finale")])])
    riders = {}
    for key, bib, region in (("a", 11, "LOMBARDIA"), ("b", 12, "LOMBARDIA"),
                             ("c", 21, "VENETO"), ("d", 22, "VENETO"),
                             # the rider who wears the coppia's number: what
                             # the medagliere used to credit the place to
                             ("e", 1, "TOSCANA"), ("f", 2, "TOSCANA")):
        riders[key] = Rider(key=key, bib=bib, cat="AL", last_name=f"R{bib}",
                            first_name="Mario", region=region,
                            events={MADISON: EventEntry(pair=bib // 10)})
    # the coppia races under a number of its own: 1 and 2, the numbers the
    # arrival below is called with
    pairs = {"AL:madison:LOMBARDIA:": Pair(key="AL:madison:LOMBARDIA:",
                                           cat="AL", region="LOMBARDIA",
                                           bib=1, riders=["a", "b"]),
             "AL:madison:VENETO:": Pair(key="AL:madison:VENETO:", cat="AL",
                                        region="VENETO", bib=2,
                                        riders=["c", "d"])}
    el = EntryList(riders=riders, pairs=pairs)

    store.save_race(RaceState(
        race_id=race_id("AL", MADISON, "Finale"), cat="AL", event=MADISON,
        round_key="Finale", fmt="madison", entrants=list(pairs),
        payload={"sprints": "2,1"}))

    places = M.podiums(store, comp, el)
    assert [p.position for p in places] == [1, 2]
    # the coppia, both its riders, and the regione behind them
    assert places[0].teams == ["VENETO"] and places[1].teams == ["LOMBARDIA"]
    assert [len(p.names) for p in places] == [2, 2]
    assert "TOSCANA" not in [t for p in places for t in p.teams]


def test_a_madison_is_scored_by_the_number_the_jury_gave_the_coppia(store):
    """The coppia races under the number assigned in its setup round.

    The number lives on the entry list only once it has been stamped there
    (`race.apply_pair_numbers`), and the arrival the jury types is called with
    it. Without that stamp the scoring fell back on the dorsale of each
    coppia's first rider, the arrival matched nobody, and the medagliere read
    a classification that was not the one on the comunicato.
    """
    from core.config import ROUND_SETUP
    from core.models import Pair

    comp = Competition(
        categories={"AL": Category(code="AL")},
        events={MADISON: Event(code=MADISON, name="Madison", fmt="madison")},
        programme=[ProgrammeItem(cat="AL", event=MADISON, rounds=[
            Round(key="Composizione coppie", kind=ROUND_SETUP),
            Round(key="Finale")])])
    riders = {}
    for key, bib, region in (("a", 41, "LOMBARDIA"), ("b", 42, "LOMBARDIA"),
                             ("c", 51, "VENETO"), ("d", 52, "VENETO")):
        riders[key] = Rider(key=key, bib=bib, cat="AL", last_name=f"R{bib}",
                            first_name="Mario", region=region,
                            events={MADISON: EventEntry()})
    pairs = {"AL:madison:LOMBARDIA:": Pair(key="AL:madison:LOMBARDIA:",
                                           cat="AL", region="LOMBARDIA",
                                           riders=["a", "b"]),
             "AL:madison:VENETO:": Pair(key="AL:madison:VENETO:", cat="AL",
                                        region="VENETO", riders=["c", "d"])}
    el = EntryList(riders=riders, pairs=pairs)

    # the jury numbers the coppie 1 and 2 - not 41 and 51 - and calls the
    # arrival with those numbers: coppia 2 wins
    store.save_race(RaceState(
        race_id=race_id("AL", MADISON, "Composizione coppie"), cat="AL",
        event=MADISON, round_key="Composizione coppie", fmt="madison",
        entrants=list(pairs),
        payload={"pair_numbers": {"AL:madison:LOMBARDIA:": 1,
                                  "AL:madison:VENETO:": 2}}))
    store.save_race(RaceState(
        race_id=race_id("AL", MADISON, "Finale"), cat="AL", event=MADISON,
        round_key="Finale", fmt="madison", entrants=list(pairs),
        payload={"sprints": "2,1"}))

    places = M.podiums(store, comp, el)
    assert [(p.position, p.teams[0]) for p in places] == \
        [(1, "VENETO"), (2, "LOMBARDIA")]


def test_the_podium_line_is_the_line_up_the_classification_prints(store, comp,
                                                                  el):
    """Who rode, then the rider a riserva replaced - marked `(ris)`.

    The same line-up the classification of that race carries: he rode the
    qualification and earned the squadra its time, so he is on the sheet and
    on the podium. A reserve entered and never used is on neither.
    """
    key = "AL:ins_squadre:LOMBARDIA:"
    el.teams[key].reserves = ["b"]          # bib 2, not entered as a starter
    store.save_race(RaceState(
        race_id=race_id("AL", PURSUIT, "Finali"), cat="AL", event=PURSUIT,
        round_key="Finali", fmt="timed_team", entrants=[key],
        payload={"times": {key: 1000},
                 # she rode in place of bib 4, who rode the qualification
                 "heat_bibs": {key: "1, 2"}, "qual_bibs": {key: "1, 4"}}))
    place = [p for p in M.podiums(store, comp, el) if p.event == PURSUIT][0]
    ris = f"({label('reserve_short')})"
    assert [n.endswith(ris) for n in place.names] == [False, False, True]
    # the one marked is the rider who lost his place, not the reserve who rode
    assert place.names[-1].startswith(el.riders["d"].full_name)


def test_a_reserve_who_did_not_ride_is_not_on_the_podium_line(store, comp, el):
    key = "AL:ins_squadre:LOMBARDIA:"
    el.teams[key].reserves = ["b"]
    store.save_race(RaceState(
        race_id=race_id("AL", PURSUIT, "Finali"), cat="AL", event=PURSUIT,
        round_key="Finali", fmt="timed_team", entrants=[key],
        payload={"times": {key: 1000}, "heat_bibs": {key: "1, 4"}}))
    place = [p for p in M.podiums(store, comp, el) if p.event == PURSUIT][0]
    assert not any("ris" in n for n in place.names)
    assert len(place.names) == 2
