"""The fasi a specialità runs, proposed from the regulation.

The proposer is judged against one thing: a programme that was actually
ridden. `test_the_proposal_rebuilds_the_programme_that_was_ridden` walks every
race of CITA26 and asks for it back from the format, the track length and the
table of distances - and the fasi, the documents each one files and the order
they go out in have to come back identical. What cannot be derived from any of
those (a lap count the jury rounded, the half lap a 200 m is written as) comes
back empty on purpose, and is listed here rather than papered over.
"""

from __future__ import annotations

import pytest

from core import rounds as RD
from core.config import (DOC_CLASSIFICATION, DOC_RESULTS, DOC_RESULTS_58,
                         DOC_RESULTS_B, DOC_RESULTS_REP, DOC_STARTLIST,
                         DOC_STARTLIST_REP, ROUND_SETUP, Competition, Event)
from core.formats import keirin as K
from core.formats import omnium as O
from core.formats import sprint as S


def _comp(fmt: str, *, track_len: float = 1 / 3, **event) -> Competition:
    """A competition of one specialità, ridden by one categoria."""
    return Competition(track_len=track_len,
                       events={"ev": Event(code="ev", fmt=fmt, **event)})


def _keys(fmt: str, **opts) -> list[str]:
    comp = _comp(fmt)
    return [r.key for r in RD.propose(comp, "AL", "ev", RD.Options(**opts))]


# ── which fasi a format runs ────────────────────────────────────────────────

def test_a_velocita_runs_the_fasi_of_the_scheme_it_qualifies_on():
    """Twelve qualified ride a turno 1 the eight do not - one table, two lists."""
    assert _keys("sprint", scheme="12") == [
        RD.QUALIFYING, S.TURNO1, S.QUARTI, S.SEMI, S.FINALI]
    assert _keys("sprint", scheme="8") == [
        RD.QUALIFYING, S.QUARTI, S.SEMI, S.FINALI]


def test_a_keirin_is_proposed_as_a_shape_and_no_more():
    """How many batterie it rides is UCI 3.2.135 on the day, not the programme."""
    assert _keys("keirin") == [K.TURNO1, K.SEMI, K.FINALI]


def test_an_omnium_runs_its_four_prove_and_the_batterie_it_was_given():
    assert _keys("omnium") == O.ROUNDS
    assert _keys("omnium", heats=2) == [
        RD.HEAT_SETUP, "Qualificazioni Batteria 1", "Qualificazioni Batteria 2",
    ] + O.ROUNDS


def test_a_madison_is_composed_before_it_is_ridden():
    """The coppie get their number and their batteria in a fase nobody rides."""
    assert _keys("madison") == [RD.PAIRING, RD.FINAL]
    assert _keys("madison", heats=2) == [
        RD.PAIRING, "Qualificazioni Batteria 1", "Qualificazioni Batteria 2",
        RD.FINAL]


def test_a_race_against_the_clock_is_ridden_twice():
    for fmt in ("timed", "timed_team"):
        assert _keys(fmt) == [RD.QUALIFYING, RD.FINALS]


def test_one_race_is_the_whole_event_where_there_is_nothing_to_qualify_for():
    for fmt in ("group", "elimination", "time_trial"):
        assert _keys(fmt) == [RD.FINAL]


def test_the_entry_list_is_not_a_race_and_runs_nothing():
    assert _keys("entrylist") == []


# ── the documents each fase files ───────────────────────────────────────────

def _docs(fmt: str, key: str, **opts) -> list[str]:
    return RD.docs_for(_comp(fmt), "AL", "ev", key, RD.Options(**opts))


def test_the_classification_hangs_off_the_last_fase_and_only_it():
    assert _docs("sprint", S.FINALI)[-1] == DOC_CLASSIFICATION
    assert DOC_CLASSIFICATION not in _docs("sprint", S.SEMI)
    assert _docs("madison", RD.FINAL, heats=2)[-1] == DOC_CLASSIFICATION
    assert DOC_CLASSIFICATION not in _docs("madison",
                                           "Qualificazioni Batteria 1", heats=2)


def test_the_recuperi_are_the_second_sheet_of_the_fase_that_sends_riders_to_them():
    """Not a fase of their own: a velocità files them under the turno 1."""
    assert _docs("sprint", S.TURNO1) == [DOC_STARTLIST, DOC_RESULTS,
                                         DOC_RESULTS_REP]
    # ... and a keirin publishes their ordine di partenza too, because its
    # batterie are composed from a table and not read off the results above
    assert _docs("keirin", K.TURNO1) == [DOC_STARTLIST, DOC_RESULTS,
                                         DOC_STARTLIST_REP, DOC_RESULTS_REP]
    # the scheme that rides no repechages files no sheet for them
    assert _docs("sprint", S.QUARTI, scheme="8") == [DOC_STARTLIST, DOC_RESULTS]


def test_a_final_that_is_ridden_first_files_first():
    """The 5°-8° and the keirin's second final are ridden before the title one."""
    assert _docs("sprint", S.FINALI, final_5_8=True) == [
        DOC_STARTLIST, DOC_RESULTS_58, DOC_RESULTS, DOC_CLASSIFICATION]
    assert _docs("keirin", K.FINALI, final_b=True) == [
        DOC_STARTLIST, DOC_RESULTS_B, DOC_RESULTS, DOC_CLASSIFICATION]


def test_a_final_that_is_not_ridden_files_nothing():
    assert DOC_RESULTS_58 not in _docs("sprint", S.FINALI, final_5_8=False)
    assert DOC_RESULTS_B not in _docs("keirin", K.FINALI, final_b=False)


def test_a_fase_that_is_composed_and_not_ridden_files_nothing():
    setup = RD.propose(_comp("madison"), "AL", "ev", RD.Options())[0]
    assert setup.kind == ROUND_SETUP and setup.docs == []
    assert setup.distance is None and setup.laps is None


# ── the numbers ─────────────────────────────────────────────────────────────

def test_the_giri_come_from_the_distance_and_the_track(monkeypatch):
    """12 km on a 333 m track is 36 giri, and the volate follow the giri."""
    monkeypatch.setattr(RD.DIST, "load",
                        lambda: {RD.DIST.LAPS_PER_SPRINT: 5,
                                 "ev": {"AL": {O.POINTS_RACE: 12}}})
    rnd = RD.propose_round(_comp("omnium"), "AL", "ev", O.POINTS_RACE)
    assert (rnd.distance, rnd.laps, rnd.sprints) == (12.0, 36, 7)


def test_a_track_of_another_length_gives_another_lap_count(monkeypatch):
    monkeypatch.setattr(RD.DIST, "load",
                        lambda: {RD.DIST.LAPS_PER_SPRINT: 5,
                                 "ev": {"AL": {O.POINTS_RACE: 12}}})
    rnd = RD.propose_round(_comp("omnium", track_len=0.25), "AL", "ev",
                           O.POINTS_RACE)
    assert (rnd.laps, rnd.sprints) == (48, 9)


def test_the_one_volata_a_scratch_finishes_on_is_not_written_down():
    """Every sheet derives it; a `sprints: 1` in the file would only repeat it."""
    rnd = RD.propose_round(_comp("omnium"), "AL", "ev", O.SCRATCH)
    assert rnd.sprints is None


def test_what_no_table_can_answer_comes_back_empty():
    """A blank field the jury fills in, never a number it has to notice is wrong."""
    # the 200 m lanciati is not a lap count - it is the last 200 metres
    assert RD.propose_round(_comp("sprint"), "AL", "ev", RD.QUALIFYING).laps is None
    # a keirin states its giri and no distance at all
    keirin = RD.propose_round(_comp("keirin"), "AL", "ev", K.TURNO1)
    assert keirin.distance is None and keirin.laps is None


def test_a_velocita_batteria_is_two_riders_and_a_keirin_batteria_is_not():
    """Six line up in a keirin, and how many batterie is the UCI table's call."""
    sprint = {r.key: r for r in RD.propose(_comp("sprint"), "AL", "ev")}
    assert sprint[S.QUARTI].heat_size == 2 and sprint[S.QUARTI].qualify == 1
    # nobody qualifies out of the finals
    assert sprint[S.FINALI].heat_size is None and sprint[S.FINALI].qualify is None
    keirin = {r.key: r for r in RD.propose(_comp("keirin"), "AL", "ev")}
    assert all(r.heat_size is None for r in keirin.values())


def test_a_qualification_against_the_clock_states_how_many_it_sends_on():
    rounds = {r.key: r for r in
              RD.propose(_comp("timed_team"), "AL", "ev", RD.Options(qualify=4))}
    assert rounds[RD.QUALIFYING].qualify == 4
    assert rounds[RD.FINALS].qualify is None


def test_a_batteria_never_eliminates_fewer_than_the_two_of_3_2_157():
    setup = RD.propose(_comp("madison"), "AL", "ev",
                       RD.Options(heats=2, eliminate=1))[0]
    assert setup.eliminate == 2


# ── reverting ───────────────────────────────────────────────────────────────

def test_reverting_twice_is_reverting_once():
    comp = _comp("madison")
    once = RD.propose_round(comp, "AL", "ev", RD.FINAL)
    assert RD.propose_round(comp, "AL", "ev", RD.FINAL) == once


def test_what_the_jury_changed_is_worked_out_and_not_recorded():
    """The proposal is recomputed and compared - nothing in the file says so."""
    comp = _comp("timed_team")
    rnd = RD.propose_round(comp, "AL", "ev", RD.QUALIFYING)
    assert RD.edited(comp, "AL", "ev", rnd) == set()
    from dataclasses import replace
    assert RD.edited(comp, "AL", "ev", replace(rnd, laps=42)) == {"laps"}
    assert RD.edited(comp, "AL", "ev",
                     replace(rnd, laps=42, qualify=8)) == {"laps", "qualify"}


# ── against the programme that was ridden ───────────────────────────────────

#: What the regulation cannot know, and must therefore not be judged on:
#:
#: * `laps` - the jury rounds them. CITA26 rides its 8 km batterie over 25 giri
#:   and its 12 km corse a punti over 35, where the track makes them 24 and 36;
#:   the 200 m is written 0.5 whatever the track measures; a keirin states its
#:   giri and no distance for them to come from.
#: * `sprints` - they follow the giri, so they differ wherever those do.
#: * `note`, `label`, `start` - the jury's own words.
NOT_DERIVABLE = {"laps", "sprints", "note", "label"}

DERIVABLE = ("key", "kind", "docs", "distance", "qualify", "eliminate",
             "heat_size")


@pytest.mark.parametrize("field", DERIVABLE)
def test_the_proposal_rebuilds_the_programme_that_was_ridden(comp, field):
    """Every race of CITA26, asked back from the format and the track length.

    The fasi, what each one files and the order they go out in are the whole
    point of the builder: if they came back even slightly different, a jury
    building next year's championship would be correcting the app instead of
    the programme.
    """
    wrong = []
    for item in comp.programme:
        if not item.rounds:
            continue
        opts = RD.options_of(comp, item.cat, item.event)
        proposed = {r.key: r for r in RD.propose(comp, item.cat, item.event, opts)}
        for rnd in item.rounds:
            fresh = proposed.get(rnd.key)
            if fresh is None:
                wrong.append(f"{item.cat} {item.event}: {rnd.key} not proposed")
            elif getattr(fresh, field) != getattr(rnd, field):
                wrong.append(f"{item.cat} {item.event} {rnd.key}: {field} "
                             f"{getattr(fresh, field)!r} != {getattr(rnd, field)!r}")
        extra = [k for k in proposed if k not in [r.key for r in item.rounds]]
        if extra:
            wrong.append(f"{item.cat} {item.event}: {extra} not in the programme")
    assert not wrong, "\n".join(wrong)


def test_the_options_of_a_scheduled_race_are_read_back_off_it(comp):
    """The ↩ button must re-propose *this* race, not a default one."""
    es = RD.options_of(comp, "ES", "velocita")
    assert es.scheme == "12" and es.final_5_8 is False
    assert RD.options_of(comp, "AL", "keirin").final_b is True
    omnium = RD.options_of(comp, "ES", "omnium")
    assert (omnium.heats, omnium.eliminate) == (2, 5)
    assert RD.options_of(comp, "AL", "ins_squadre").qualify == 4


def test_reproposing_a_race_keeps_what_no_regulation_can_propose():
    """A button called *riproponi* must not eat the timetable."""
    from dataclasses import replace as _replace

    comp = _comp("timed_team")
    comp.programme.append(__import__("core.config", fromlist=["ProgrammeItem"])
                          .ProgrammeItem(cat="AL", event="ev", day=1))
    item = comp.programme[0]
    item.rounds = RD.propose(comp, "AL", "ev")
    item.rounds[0] = _replace(item.rounds[0], start="14:30", note="da confermare",
                              label="200 m", laps=99)

    back = RD.apply(comp, "AL", "ev", RD.Options())
    assert back[0].start == "14:30"          # kept: no table proposes a time
    assert back[0].note == "da confermare"   # kept: it is the jury's own line
    assert back[0].label == "200 m"          # kept: what the sheets call it
    assert back[0].laps != 99                # put back: it is a proposal
