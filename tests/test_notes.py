"""The lines a sheet opens on: which one a fase gets, and what it says.

The wordings come out of the catalogues and the rules out of
`regulations/notes.json`, so these are about the *table*: that a rule fires on
the fase the regulation means, that the number in the sentence is the one the
programme states, and that a line the jury has written is never taken away.
"""

import pytest

from conftest import programme_path
from core import notes as N
from core.config import DOC_RESULTS, DOC_STARTLIST, load_competition


@pytest.fixture
def comp():
    """The real championship: a 333 m track, and every format on it."""
    return load_competition(programme_path())


def _race(comp, cat, event):
    return next(i for i in comp.programme if i.cat == cat and i.event == event)


def _round(item, key):
    return next(r for r in item.rounds if r.key == key)


# ── which fase a rule is about ──────────────────────────────────────────────

def test_a_madison_heat_is_a_heat_and_not_a_qualification():
    """*Qualificazioni Batteria 1* is a batteria, whatever it qualifies for.

    The two families ask for different sentences - a batteria announces the
    coppie it eliminates, a qualificazione against the clock announces how many
    tempi go through - and the madison writes its batterie under both words.
    """
    assert N.family("Qualificazioni Batteria 1") == N.HEATS
    assert N.family("Qualificazioni") == N.QUALIFYING
    assert N.family("Turno 1") == N.ROUND1
    assert N.family("Recuperi") == N.REPECHAGE
    assert N.family("Finali") == N.FINALS


def test_half_a_giro_is_what_moves_the_start(comp):
    """Two squadre start half a lap apart, so the giri decide which straight."""
    assert N.half_laps(_round(_race(comp, "AL", "vel_squadre"), "Finali"))
    assert not N.half_laps(_round(_race(comp, "AL", "madison"), "Finale"))


# ── what the fase then says ─────────────────────────────────────────────────

def test_a_madison_batteria_announces_the_cut_the_composizione_decided(comp):
    """The number is the programme's: it is stated once, on the composizione."""
    item = _race(comp, "AL", "madison")
    said = N.for_round(comp, item, _round(item, "Qualificazioni Batteria 1"))
    assert said[DOC_STARTLIST] == ("Non si qualificano per la finale le ultime "
                                   "2 coppie tra le partenti.")


def test_a_pursuit_says_what_qualifies_and_where_the_first_one_starts(comp):
    """Two sentences on one sheet, in the order the table states them."""
    item = _race(comp, "AL", "ins_squadre")
    said = N.for_round(comp, item, _round(item, "Qualificazioni"))
    assert said[DOC_STARTLIST] == (
        "Si qualificano per le finali le prime 4 squadre.\n"
        "La prima squadra parte sul rettilineo d'arrivo.")
    # the risultati of a qualification is the sheet that says who went through
    assert said[DOC_RESULTS] == "Si qualificano per le finali le prime 4 squadre."


def test_the_sheet_is_written_about_the_riders_in_front_of_the_jury(comp):
    """*La prima atleta*, on a categoria femminile - and only there."""
    men = _race(comp, "AL", "ins_individuale")
    women = _race(comp, "DA", "ins_individuale")
    assert "Il primo atleta" in N.for_round(
        comp, men, _round(men, "Finali"))[DOC_STARTLIST]
    assert "La prima atleta" in N.for_round(
        comp, women, _round(women, "Finali"))[DOC_STARTLIST]


def test_a_333_track_changes_every_half_lap(comp):
    """A condition on the track, and it is the track this meeting is on."""
    assert N.track_metres(comp) == 333
    item = _race(comp, "AL", "vel_squadre")
    said = N.for_round(comp, item, _round(item, "Qualificazioni"))
    assert "Cambio ogni mezzo giro." in said[DOC_STARTLIST]


def test_nothing_is_announced_where_the_programme_states_no_number(comp):
    """A sentence with a hole in it is worse than no sentence: it goes to print."""
    item = _race(comp, "ED", "madison")     # no composizione, nothing eliminated
    for rnd in item.rounds:
        assert DOC_STARTLIST not in N.for_round(comp, item, rnd)


def test_a_composizione_announces_nothing_itself(comp):
    """Nobody rides it and it files no comunicato."""
    item = _race(comp, "AL", "madison")
    assert N.for_round(comp, item, _round(item, "Composizione coppie")) == {}


# ── frozen into the programme, and re-proposed under it ─────────────────────

def test_the_lines_are_written_onto_the_fase(comp):
    """What the jury reads in Programmazione is what will print."""
    item = _race(comp, "AL", "ins_squadre")
    assert N.refresh_item(comp, item, force=True)
    assert _round(item, "Qualificazioni").results_note == (
        "Si qualificano per le finali le prime 4 squadre.")


def test_a_line_follows_the_number_it_is_about(comp):
    """Change how many coppie go out and the sentence under it changes too."""
    item = _race(comp, "AL", "madison")
    N.refresh_item(comp, item, force=True)
    before = N.resolved(comp, item)
    _round(item, "Composizione coppie").eliminate = 3
    assert N.refresh_item(comp, item, before=before)
    assert "ultime 3 coppie" in _round(item, "Qualificazioni Batteria 1").sheet_note


def test_a_line_the_jury_wrote_is_never_taken_away(comp):
    """The regulation proposes; what is typed over it stays typed over."""
    item = _race(comp, "AL", "madison")
    N.refresh_item(comp, item, force=True)
    mine = "Le ultime due coppie non corrono la finale (decisione giuria)."
    _round(item, "Qualificazioni Batteria 1").sheet_note = mine
    before = N.resolved(comp, item)
    _round(item, "Composizione coppie").eliminate = 4
    N.refresh_item(comp, item, before=before)
    assert _round(item, "Qualificazioni Batteria 1").sheet_note == mine
    # and the one nobody touched has followed the number
    assert "ultime 4" in _round(item, "Qualificazioni Batteria 2").sheet_note


def test_repropose_puts_the_regulation_back(comp):
    """↩ Riproponi means the regulation, the jury's own wording included."""
    item = _race(comp, "AL", "madison")
    N.refresh_item(comp, item, force=True)
    _round(item, "Qualificazioni Batteria 1").sheet_note = "una mia riga"
    N.refresh_item(comp, item, force=True)
    assert "ultime 2 coppie" in _round(item,
                                       "Qualificazioni Batteria 1").sheet_note


# ── the wording, and rewriting it ───────────────────────────────────────────

def test_every_wording_a_rule_names_exists_in_the_catalogues():
    """A rule pointing at a key nothing says would print an empty line."""
    from core.i18n import CATALOGUES, DEFAULT, catalogue
    for key in N.keys():
        assert key in catalogue(DEFAULT).MSG, key
    for code in CATALOGUES:
        missing = [k for k in N.keys() if k not in catalogue(code).MSG]
        assert not missing, f"{code}: {missing}"


def test_an_installation_can_word_a_line_its_own_way(comp):
    """The catalogue is what the app ships, not what this federation says."""
    from core.i18n import set_texts
    item = _race(comp, "AL", "madison")
    rnd = _round(item, "Qualificazioni Batteria 1")
    try:
        set_texts({"it": {"note_madison_startlist": "Fuori le ultime {n}."}})
        assert N.for_round(comp, item, rnd)[DOC_STARTLIST] == "Fuori le ultime 2."
    finally:
        set_texts({})
    assert "Non si qualificano" in N.for_round(comp, item, rnd)[DOC_STARTLIST]
