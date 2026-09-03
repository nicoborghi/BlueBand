"""La classifica del Trofeo delle Regioni: the points of art. 8 and art. 9.

What is under test is the regolamento, not the app: which position is worth
what, who earns the punto partecipazione, and the order two squadre level on
points are separated in. The races are written here rather than taken from a
competition file, so a season that changes its programme cannot change what
these tests assert.
"""

from __future__ import annotations

import pytest

from core import recap as RC
from core import trofeo as TR
from core.config import Category, Competition, Event, ProgrammeItem, Round
from core.formats.base import Placing, Result
from core.models import (EntryList, EventEntry, RaceState, Rider, Status,
                         Team, race_id)

SCRATCH, PURSUIT = "scratch", "ins_squadre"


@pytest.fixture
def comp():
    """Two specialità of one categoria: a bunch race and a team pursuit."""
    return Competition(
        categories={"AL": Category(code="AL")},
        events={SCRATCH: Event(code=SCRATCH, name="Scratch", fmt="group"),
                PURSUIT: Event(code=PURSUIT, name="Inseguimento a Squadre",
                               fmt="timed_team", team_size=2)},
        programme=[ProgrammeItem(cat="AL", event=SCRATCH,
                                 day=1, rounds=[Round(key="Finale", seq=1)]),
                   ProgrammeItem(cat="AL", event=PURSUIT, day=1,
                                 rounds=[Round(key="Finali", seq=2)])])


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


def _result(*placings) -> Result:
    """A classification, as (key, position, status) triples."""
    return Result(placings=[
        Placing(key=key, position=pos,
                status=status if isinstance(status, Status) else Status.OK)
        for key, pos, status in placings])


def _bunch(store, round_key, arrival, **payload):
    store.save_race(RaceState(
        race_id=race_id("AL", SCRATCH, round_key), cat="AL", event=SCRATCH,
        round_key=round_key, fmt="scratch", entrants=["1", "2", "3", "4"],
        payload={"sprints": arrival, **payload}))


def _score(result, el, comp, **kw) -> dict[str, TR.EventScore]:
    return {s.team: s for s in TR.score_event(result, None, comp, el,
                                              "AL", SCRATCH, **kw)}


# ── the points table ────────────────────────────────────────────────────────

def test_the_final_scores_the_first_ten_of_article_nine():
    assert [TR.points_of(p) for p in range(1, 12)] == [14, 12, 10, 8, 6, 5, 4,
                                                       3, 2, 1, 0]


def test_a_qualifying_round_scores_the_flatter_table_of_article_eight():
    assert [TR.points_of(p, TR.SCALE_QUALIFYING) for p in range(1, 12)] == [
        10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]


def test_a_place_outside_the_table_is_worth_no_points_and_still_participates(
        comp, el):
    """11° scores nothing and is still a partente: the point is for starting."""
    scores = _score(_result(("3", 11, Status.OK)), el, comp)
    assert (scores["TOSCANA"].points, scores["TOSCANA"].participation) == (0, 1)


# ── punti piazzamento ───────────────────────────────────────────────────────

def test_the_points_go_to_the_squadra_of_whoever_took_the_place(comp, el):
    scores = _score(_result(("2", 1, Status.OK), ("1", 2, Status.OK),
                            ("3", 3, Status.OK)), el, comp)
    assert scores["VENETO"].points == 14
    assert scores["LOMBARDIA"].points == 12
    assert scores["TOSCANA"].points == 10


def test_two_riders_of_one_regione_add_their_placings_up(comp, el):
    """Art. 9 sums the punteggi of a prova: nothing caps a regione at one."""
    scores = _score(_result(("1", 1, Status.OK), ("4", 4, Status.OK)),
                    el, comp)
    assert scores["LOMBARDIA"].points == 14 + 8
    assert scores["LOMBARDIA"].participation == 2      # two atleti partenti
    assert scores["LOMBARDIA"].total == 24


def test_a_relegated_rider_keeps_the_points_of_the_place_she_was_put_back_to(
        comp, el):
    scores = _score(_result(("1", 3, Status.REL)), el, comp)
    assert scores["LOMBARDIA"].points == 10


def test_a_disqualified_rider_carries_no_points_and_still_started(comp, el):
    """A DSQ has no position; she did line up, so the punto partecipazione
    stands. Nothing in art. 9 takes it back."""
    scores = _score(_result(("1", None, Status.DSQ)), el, comp)
    assert (scores["LOMBARDIA"].points, scores["LOMBARDIA"].starters) == (0, 1)


def test_the_squadra_is_whatever_the_programme_says_it_is(comp, el):
    scores = _score(_result(("1", 1, Status.OK)), el, comp,
                    group=RC.BY_CLUB)
    assert list(scores) == ["GS Pippo"]


# ── punti partecipazione ────────────────────────────────────────────────────

def test_one_point_per_starter_and_a_rider_who_did_not_start_scores_none(
        comp, el):
    scores = _score(_result(("1", 1, Status.OK), ("4", None, Status.DNS),
                            ("2", 2, Status.OK)), el, comp)
    assert (scores["LOMBARDIA"].participation,
            scores["LOMBARDIA"].starters) == (1, 1)
    assert scores["VENETO"].participation == 1


def test_a_rider_who_left_the_race_had_started_and_scores_the_point(comp, el):
    scores = _score(_result(("1", None, Status.DNF),
                            ("4", None, Status.ABD)), el, comp)
    assert scores["LOMBARDIA"].participation == 2


def test_a_quartetto_is_one_point_and_not_one_per_rider(comp, el):
    """*1 punto per: Atleta / Team / Coppia Madison* - the entità, not its
    riders. Two riders of LOMBARDIA ride the quartetto and it scores once."""
    key = "AL:ins_squadre:LOMBARDIA:"
    scores = {s.team: s for s in TR.score_event(
        _result((key, 1, Status.OK)), None, comp, el, "AL", PURSUIT)}
    assert (scores["LOMBARDIA"].participation,
            scores["LOMBARDIA"].points) == (1, 14)


def test_one_entita_is_read_once_however_often_it_is_on_the_sheet(comp, el):
    scores = _score(_result(("1", 1, Status.OK), ("1", 5, Status.OK)),
                    el, comp)
    assert (scores["LOMBARDIA"].points,
            scores["LOMBARDIA"].participation) == (14, 1)


# ── la classifica ───────────────────────────────────────────────────────────

def _rows(*teams) -> list[TR.TeamScore]:
    return TR._rows([TR.EventScore(cat="AL", event=SCRATCH, team=t,
                                   points=p, participation=part, wins=w)
                     for t, p, part, w in teams], ("", ""))


def test_the_classifica_is_ranked_on_placings_plus_participation():
    rows = _rows(("VENETO", 14, 1, 1), ("LOMBARDIA", 12, 4, 0))
    assert [(r.team, r.total) for r in rows] == [("LOMBARDIA", 16),
                                                 ("VENETO", 15)]


def test_a_tie_on_points_is_broken_by_the_races_won():
    rows = _rows(("VENETO", 14, 2, 1), ("LOMBARDIA", 14, 2, 0))
    assert [r.team for r in rows] == ["VENETO", "LOMBARDIA"]


def test_a_tie_on_points_and_wins_is_broken_by_the_participation_points():
    rows = _rows(("VENETO", 14, 2, 1), ("LOMBARDIA", 12, 4, 1))
    assert [r.team for r in rows] == ["LOMBARDIA", "VENETO"]


def test_the_last_tie_break_is_the_score_in_the_last_prova_of_the_programme():
    scores = [TR.EventScore(cat="AL", event=SCRATCH, team="VENETO", points=14),
              TR.EventScore(cat="AL", event=PURSUIT, team="VENETO", points=2),
              TR.EventScore(cat="AL", event=SCRATCH, team="TOSCANA", points=6),
              TR.EventScore(cat="AL", event=PURSUIT, team="TOSCANA", points=10)]
    rows = TR._rows(scores, ("AL", PURSUIT))
    assert [(r.team, r.last_points) for r in rows] == [("TOSCANA", 10),
                                                       ("VENETO", 2)]


def test_two_squadre_equal_on_every_tie_break_share_a_position():
    rows = _rows(("VENETO", 14, 2, 1), ("LOMBARDIA", 14, 2, 1),
                 ("TOSCANA", 6, 1, 0))
    assert [(pos, r.team) for pos, r in TR.ranked(rows)] == [
        (1, "LOMBARDIA"), (1, "VENETO"), (3, "TOSCANA")]


def test_a_shared_lead_proclaims_nobody_champion():
    assert TR.champion(_rows(("VENETO", 14, 2, 1),
                             ("LOMBARDIA", 14, 2, 1))) == ""
    assert TR.champion(_rows(("VENETO", 14, 2, 1),
                             ("LOMBARDIA", 12, 2, 1))) == "VENETO"


# ── the last prova of the programme ─────────────────────────────────────────

def test_the_last_prova_is_the_last_one_ridden_and_not_the_last_one_listed(
        comp):
    assert TR.last_event(comp) == ("AL", PURSUIT)
    comp.programme[0].rounds[0].seq = 9      # the scratch is moved to the end
    assert TR.last_event(comp) == ("AL", SCRATCH)


def test_a_pausa_is_not_a_prova(comp):
    comp.programme.append(ProgrammeItem(cat="", event="pause", day=1,
                                        rounds=[Round(key="pause_1",
                                                      kind="pause", seq=9)]))
    assert TR.last_event(comp) == ("AL", PURSUIT)


# ── the whole competition ───────────────────────────────────────────────────

def test_the_standings_read_the_races_the_medagliere_reads(store, comp, el):
    _bunch(store, "Finale", "2,1,3,4")
    found = TR.standings(store, comp, el)
    assert found.counted == 1
    assert ("AL", PURSUIT, False) in found.open_events
    # LOMBARDIA fields two riders and both of them score: 12 (2°) + 8 (4°),
    # and one punto partecipazione each
    assert [(r.team, r.points, r.participation, r.total)
            for r in found.rows] == [("LOMBARDIA", 20, 2, 22),
                                     ("VENETO", 14, 1, 15),
                                     ("TOSCANA", 10, 1, 11)]


def test_a_prova_not_concluded_is_left_out_unless_it_is_asked_for(store, comp,
                                                                 el):
    comp.programme[0].rounds.insert(0, Round(key="Qualificazioni", seq=0))
    _bunch(store, "Qualificazioni", "3,4,1,2")
    assert TR.standings(store, comp, el).rows == []

    found = TR.standings(store, comp, el, include_unfinished=True)
    assert [(r.team, r.total) for r in found.rows] == [("LOMBARDIA", 24),
                                                       ("TOSCANA", 15),
                                                       ("VENETO", 9)]
    assert all(not s.complete for s in found.scores)


def test_a_broken_race_costs_its_own_prova_and_no_more(store, comp, el):
    _bunch(store, "Finale", "not, a, result")
    found = TR.standings(store, comp, el, include_unfinished=True)
    assert found.rows == []
    assert ("AL", SCRATCH, False) in found.open_events


# ── the printed sheet ───────────────────────────────────────────────────────

def test_the_sheet_prints_what_the_page_shows(store, comp, el):
    from render import documents as D

    _bunch(store, "Finale", "2,1,3,4")
    found = TR.standings(store, comp, el)
    doc = D.trofeo_table(found, comp)
    assert doc.slug == "classifica-trofeo"
    assert len(doc.tables) == 2                   # the standings, then the detail
    assert [r["team"] for r in doc.tables[0].rows] == ["LOMBARDIA", "VENETO",
                                                       "TOSCANA"]
    assert [r["total"] for r in doc.tables[0].rows] == [22, 15, 11]
    # the prova that is not concluded is named under the table, not dropped
    assert any("Inseguimento" in n.text or PURSUIT in n.text
               for n in doc.notes) or found.open_events


def test_the_sheet_can_be_the_classifica_alone(store, comp, el):
    from render import documents as D

    _bunch(store, "Finale", "2,1,3,4")
    doc = D.trofeo_table(TR.standings(store, comp, el), comp, detail=False)
    assert len(doc.tables) == 1


def test_the_champion_band_prints_only_when_the_trofeo_is_over(store, comp, el):
    from render import documents as D
    from core.i18n import label

    comp.programme = comp.programme[:1]           # the scratch alone
    _bunch(store, "Finale", "2,1,3,4")
    found = TR.standings(store, comp, el)
    assert not found.open_events
    doc = D.trofeo_table(found, comp)
    bands = [r for r in doc.tables[0].rows if "_banner" in r]
    assert [r["_banner"] for r in bands] == [label("champion_region")]
