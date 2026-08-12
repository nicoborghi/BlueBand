"""The specialità offered ready-made, and what an added one comes out as.

Declaring an event by hand is seven fields, and the one that matters is the
format: an inseguimento declared `group` runs the wrong machinery all week and
says nothing about it. The catalogue exists so that the seven are right without
anybody typing them.
"""

from __future__ import annotations

import json

import pytest

from core import catalogue as CAT
from core import i18n as I
from core import rounds as RD
from core.config import Competition


@pytest.fixture(autouse=True)
def italian():
    """Every test here reads a name, and a name is language-dependent."""
    I.set_language(I.DEFAULT)
    yield
    I.set_language(I.DEFAULT)


def test_the_shipped_catalogue_is_json_the_app_can_read():
    with CAT.FILE.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict) and data.get(CAT.META)
    assert CAT.codes(), "the catalogue offers no specialità"


@pytest.mark.parametrize("code", CAT.codes())
def test_every_specialita_names_a_format_the_app_knows(code):
    """A format the code does not know is a race that cannot be scored."""
    from ui.pages.programme import FORMATS

    ev = CAT.event(code)
    assert ev.fmt in FORMATS
    assert ev.name and ev.short and ev.abbr


def test_a_specialita_comes_out_ready_to_schedule():
    ev = CAT.event("ins_squadre", order=3)
    assert (ev.fmt, ev.abbr, ev.team_size, ev.order) == ("timed_team", "TP", 4, 3)


def test_one_the_catalogue_does_not_know_is_still_an_event():
    """The grid has always allowed a code typed by hand; it still does."""
    ev = CAT.event("gimkana")
    assert ev.code == "gimkana" and ev.fmt == "group"


def test_the_name_is_the_language_the_competition_is_run_in():
    """It is not a label: it is written into the file and printed as it stands."""
    assert CAT.name("ins_individuale") == "INSEGUIMENTO INDIVIDUALE"
    I.set_language("en")
    assert CAT.name("ins_individuale") == "INDIVIDUAL PURSUIT"
    assert CAT.name("ins_individuale", short=True) == "Ind. Pursuit"


def test_a_language_the_catalogue_has_no_name_for_falls_back():
    """Same rule as the rest of the app: an Italian word, never an empty one."""
    I.set_language("en")
    assert CAT.name("boh") == "boh"


# ── the chilometro, on the machinery of the inseguimento ────────────────────

def test_the_chilometro_is_ridden_against_the_clock_like_a_pursuit():
    """Same scoring, same sheets - one race instead of a qualification and finals."""
    from core import race as R

    comp = Competition(track_len=0.25)
    comp.events["chilometro"] = CAT.event("chilometro")
    comp.events["ins_individuale"] = CAT.event("ins_individuale")

    km = RD.propose(comp, "DA", "chilometro")
    assert [r.key for r in km] == [RD.FINAL]        # nothing to qualify for
    assert km[0].docs[-1] == "classifica"
    assert (km[0].distance, km[0].laps) == (1.0, 4.0)

    assert R.round_format(comp, "DA", "chilometro", RD.FINAL) \
        == R.round_format(comp, "DA", "ins_individuale", RD.QUALIFYING)


def test_a_chilometro_is_ridden_in_pairs_unless_it_is_not():
    """Two at a time, one per straight, is the default; the jury may split them."""
    from core import race as R

    comp = Competition(track_len=0.25)
    comp.events["chilometro"] = CAT.event("chilometro")
    assert comp.events["chilometro"].teams_per_start == 2

    kind = R.round_format(comp, "DA", "chilometro", RD.FINAL)
    # its one fase is called *Finale* because it is the whole event, and that
    # must not be read as "seeded from a qualification, nothing to choose"
    assert R.can_choose_starts(comp, "chilometro", kind, RD.FINAL)


def test_the_500_is_the_same_race_over_half_the_distance():
    comp = Competition(track_len=1 / 3)
    comp.events["500"] = CAT.event("500")
    rnd = RD.propose(comp, "DA", "500")[0]
    # half-lap resolution, because it is ridden against the clock
    assert (rnd.distance, rnd.laps) == (0.5, 1.5)
