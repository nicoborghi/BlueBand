"""The table of regulation distances, and what it answers when it says nothing.

The distance is the one number of a fase that cannot be derived: giri come
from it and the track length, sprint come from the giri, but 4 km is 4 km
because the regulation says so. The table is therefore the *input* of the whole
proposal chain, and two things about it have to hold: it must be seeded from a
programme that was really ridden (nothing invented), and a lookup it cannot
answer must come back empty rather than approximate.
"""

from __future__ import annotations

import json

import pytest

from core import distances as D
from core.config import Competition, ProgrammeItem, Round
from core.formats import group as GROUP


# ── looking a distance up ───────────────────────────────────────────────────

TABLE = {
    D.META: "1 January 2026",
    "omnium": {"ES": {"Scratch": 4, "Tempo Race": 4, "qualificazioni": 8},
               "*": {"Scratch": 10}},
    "madison": {"AL": {"qualificazioni": 10, "final": 20}},
    "ins_squadre": {"AL": {"*": 3}},
    "scratch": {"ES": 5},
}


@pytest.mark.parametrize("event, cat, round_key, km", [
    # the fase by its own name
    ("omnium", "ES", "Scratch", 4.0),
    # ... and by the family it belongs to: every batteria of qualificazione is
    # ridden over the same distance, and the programme numbers them
    ("omnium", "ES", "Qualificazioni Batteria 2", 8.0),
    ("madison", "AL", "Finale", 20.0),
    ("madison", "AL", "Finali", 20.0),
    # `*` is every fase of that categoria
    ("ins_squadre", "AL", "Qualificazioni", 3.0),
    ("ins_squadre", "AL", "Finali", 3.0),
    # a categoria of `*` is the distance that holds whoever rides it, and the
    # named categoria still wins over it
    ("omnium", "DA", "Scratch", 10.0),
    ("omnium", "ES", "Scratch", 4.0),
    # one number instead of a mapping: the shorthand a hand-edited file grows
    ("scratch", "ES", "Finale", 5.0),
    # nothing to say: an empty field on the page, never a guess
    ("keirin", "AL", "Finali", 0.0),
    ("omnium", "ES", "Eliminazione", 0.0),
    ("madison", "ES", "Finale", 0.0),
])
def test_a_distance_is_looked_up_from_the_fase_out(event, cat, round_key, km):
    assert D.distance(event, cat, round_key, table=TABLE) == km


def test_a_broken_table_answers_nothing_rather_than_raising():
    """A regulation nobody can read must not take the Programma page down."""
    for junk in ({}, {"omnium": "quattro"}, {"omnium": {"ES": None}},
                 {"omnium": {"ES": {"Scratch": "quattro"}}}):
        assert D.distance("omnium", "ES", "Scratch", table=junk) == 0.0


def test_the_family_of_a_fase_is_read_off_its_name():
    assert D.family_of("Qualificazioni Batteria 1") == "qualificazioni"
    assert D.family_of("Finale") == "final"
    assert D.family_of("Finali") == "final"
    assert D.family_of("Semifinali") == ""      # a fase of its own, not a final
    assert D.family_of("") == ""


# ── seeding it from a programme ─────────────────────────────────────────────

def _comp(*rounds: tuple[str, str, str, float]) -> Competition:
    """A programme of (cat, event, round key, km) and nothing else."""
    items: dict[tuple[str, str], ProgrammeItem] = {}
    for cat, event, key, km in rounds:
        item = items.setdefault((cat, event),
                                ProgrammeItem(cat=cat, event=event, day=1))
        item.rounds.append(Round(key=key, distance=km))
    return Competition(programme=list(items.values()))


def _seeded(comp) -> dict:
    """What `seed` harvested about the distances, without the sprint interval."""
    return {k: v for k, v in D.seed(comp).items() if k not in D.RESERVED}


def test_one_distance_for_every_fase_collapses_into_one_line():
    """`*` is what the jury would have written: it is the same race throughout."""
    comp = _comp(("AL", "ins_squadre", "Qualificazioni", 3.0),
                 ("AL", "ins_squadre", "Finali", 3.0))
    assert _seeded(comp) == {"ins_squadre": {"AL": {"*": 3.0}}}


def test_fasi_ridden_over_different_distances_keep_a_line_each():
    comp = _comp(("AL", "madison", "Qualificazioni Batteria 1", 10.0),
                 ("AL", "madison", "Qualificazioni Batteria 2", 10.0),
                 ("AL", "madison", "Finale", 20.0))
    assert _seeded(comp) == {"madison": {"AL": {"qualificazioni": 10.0,
                                               "final": 20.0}}}


def test_a_fase_with_no_distance_seeds_nothing():
    """The eliminazione of an omnium declares none, and must not become a 0."""
    comp = _comp(("ES", "omnium", "Scratch", 4.0),
                 ("ES", "omnium", "Eliminazione", 0.0))
    assert _seeded(comp) == {"omnium": {"ES": {"Scratch": 4.0}}}


def test_the_seed_of_a_competition_with_no_distances_is_empty():
    assert _seeded(Competition()) == {}


# ── how often a bunch race sprints ──────────────────────────────────────────

EVERY_FIVE = {D.LAPS_PER_SPRINT: 5}


@pytest.mark.parametrize("laps, kind, n", [
    # on the interval the table states
    (45, GROUP.MADISON, 9),
    (25, GROUP.MADISON, 5),
    (35, GROUP.POINTS, 7),
    # the tempo race is not on an interval: every lap from the fifth
    (12, GROUP.TEMPO, 8),
    (15, GROUP.TEMPO, 11),
    # a scratch has the one volata it finishes on
    (12, GROUP.SCRATCH, 1),
    # a race against the clock has none
    (9, "timed", 0),
])
def test_the_volate_of_a_round_follow_the_interval_or_the_rule(laps, kind, n):
    assert D.sprints(laps, kind, table=EVERY_FIVE) == n


def test_without_an_interval_it_derives_what_it_always_derived():
    """A missing regulation is yesterday's behaviour, not a zero."""
    from core.config import sprints_from_laps
    for laps, kind in ((35, GROUP.POINTS), (12, GROUP.TEMPO), (12, GROUP.SCRATCH)):
        assert D.sprints(laps, kind, table={}) == sprints_from_laps(laps, kind)


def test_the_interval_is_read_off_a_programme_that_was_ridden():
    comp = _comp(("ES", "madison", "Finale", 16.0))
    comp.programme[0].rounds[0].laps = 45
    comp.programme[0].rounds[0].sprints = 9
    assert D.seed_laps_per_sprint(comp) == 5.0


def test_an_interval_that_is_not_one_is_not_guessed():
    """Two rounds disagreeing means the competition has no single interval."""
    comp = _comp(("ES", "madison", "Finale", 16.0),
                 ("AL", "madison", "Finale", 20.0))
    comp.programme[0].rounds[0].laps, comp.programme[0].rounds[0].sprints = 45, 9
    comp.programme[1].rounds[0].laps, comp.programme[1].rounds[0].sprints = 60, 10
    assert D.seed_laps_per_sprint(comp) == 0.0


def test_the_tempo_race_is_left_out_of_the_harvest():
    """It sprints on every lap from the fifth: it would poison the average."""
    comp = _comp(("ES", "omnium", "Corsa a Punti", 12.0),
                 ("ES", "omnium", "Tempo Race", 4.0))
    points, tempo = comp.programme[0].rounds
    points.laps, points.sprints = 35, 7
    tempo.laps, tempo.sprints = 12, 8
    assert D.seed_laps_per_sprint(comp) == 5.0


# ── the file that ships with the app ────────────────────────────────────────

def test_the_shipped_table_is_json_the_app_can_read():
    """Replaced by hand when the regulations change: a typo is a blank page."""
    with D.FILE.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict) and data.get(D.META)
    assert D.events(data), "the shipped table names no specialità"
    assert D.laps_per_sprint(data) > 0, "no sprint interval was harvested"


def test_the_shipped_volate_are_the_volate_the_programme_states(comp):
    """The interval must reproduce every sprint count the real programme writes.

    This is what says the harvested number is a rule and not a coincidence:
    22 rounds, four categorie, three distances, one interval.
    """
    from core import race as R

    for item in comp.programme:
        for rnd in item.rounds:
            if rnd.sprints and rnd.laps:
                kind = R.round_format(comp, item.cat, item.event, rnd.key)
                assert D.sprints(rnd.laps, kind) == rnd.sprints, \
                    f"{item.cat} {item.event} {rnd.key}"


def test_the_shipped_table_says_what_the_programme_it_was_seeded_from_says(comp):
    """It was harvested from a competition that ran; it must still agree with it.

    Not a tautology: the file is edited by hand afterwards, and this is what
    says whether an edit contradicted the programme it came from.
    """
    for item in comp.programme:
        for rnd in item.rounds:
            if rnd.distance:
                assert D.distance(item.event, item.cat, rnd.key) == rnd.distance
