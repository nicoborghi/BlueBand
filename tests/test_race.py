"""End-to-end: real entrants -> results -> persisted state -> printed document."""

import re

import pytest

from core import race as R
from core.config import DOC_CLASSIFICATION, DOC_RESULTS
from core.entries import import_master, save_import
from core.models import EventEntry, Status
from core.parse import parse_time
from render import documents as D
from render.render import archive, to_html


@pytest.fixture(scope="session")
def entries(iscritti_path, comp):
    return import_master(iscritti_path, comp)


@pytest.fixture
def ev(store, entries):
    save_import(store, entries)
    return store


# ── format resolution ───────────────────────────────────────────────────────

@pytest.mark.parametrize("cat,event,round_key,kind", [
    ("AL", "ins_squadre", "Qualificazioni", R.TIMED_TEAM),
    ("AL", "vel_squadre", "Finali", R.TIMED_TEAM),
    ("AL", "ins_individuale", "Qualificazioni", R.TIMED),
    ("ED", "madison", "Finale", R.MADISON),
    ("AL", "omnium", "Scratch", R.SCRATCH),
    ("AL", "omnium", "Tempo Race", R.TEMPO),
    ("AL", "omnium", "Eliminazione", R.ELIMINATION),
    ("AL", "omnium", "Corsa a Punti", R.POINTS),
    ("AL", "omnium", "Qualificazioni Batteria 1", R.POINTS),
    ("AL", "velocita", "Qualificazioni", R.TIMED),
    ("AL", "velocita", "Quarti", R.BRACKET),
    ("AL", "keirin", "Turno 1", R.BRACKET),
])
def test_phase_format(comp, cat, event, round_key, kind):
    assert R.round_format(comp, cat, event, round_key) == kind


# ── entrants ────────────────────────────────────────────────────────────────

def test_entrants_are_bibs_teams_or_pairs(entries, comp):
    # counted off the entry list, never written down here: the file is
    # re-imported while the championship runs and a number typed in a test
    # would only say when it was typed
    entered = [r for r in entries.riders.values()
               if r.cat == "AL" and "omnium" in (r.events or {})]
    bibs = R.entrants(entries, comp, "AL", "omnium", "Scratch")
    assert bibs and len(bibs) <= len(entered)
    assert all(b.isdigit() for b in bibs)

    teams = R.entrants(entries, comp, "AL", "ins_squadre", "Qualificazioni")
    assert all(k in entries.teams for k in teams)
    # a rappresentativa that fields two squadre is "LOMBARDIA A" and
    # "LOMBARDIA B": what is checked is that the label is the regione's
    labels = [entries.teams[k].label for k in teams]
    assert any(name.startswith("LOMBARDIA") for name in labels)

    pairs = R.entrants(entries, comp, "ED", "madison", "Finale")
    assert pairs and all(k in entries.pairs for k in pairs)


def test_entrant_riders_resolves_teams(entries, comp):
    teams = R.entrants(entries, comp, "AL", "ins_squadre", "Qualificazioni")
    riders = R.entrant_riders(teams[0], entries)
    assert 1 <= len(riders) <= 4
    assert all(r.cat == "AL" for r in riders)


# ── a full race, persisted ──────────────────────────────────────────────────

def test_points_race_survives_a_reload(ev, entries, comp):
    state = R.ensure_state(ev, comp, "AL", "omnium", "Corsa a Punti", entries)
    assert state.n_sprint == 9 and state.n_laps == 45

    bibs = [int(b) for b in state.entrants[:6]]
    state.payload["sprints"] = "-".join(
        ",".join(str(b) for b in bibs[:4]) for _ in range(2))
    state.payload["laps_gained"] = str(bibs[5])
    R.set_status(state, str(bibs[4]), Status.DNF)
    ev.save_race(state)

    # a fresh load must classify identically
    back = ev.load_race(state.race_id)
    assert back.payload["sprints"] == state.payload["sprints"]
    result = R.classify(back, entries, comp)
    assert result.by_key(str(bibs[5])).data["total"] == 20  # lap gained
    assert result.by_key(str(bibs[4])).label == "DNF"
    assert result.placings[0].key == str(bibs[5])


def test_team_pursuit_qualification_end_to_end(ev, entries, comp):
    state = R.ensure_state(ev, comp, "AL", "ins_squadre", "Qualificazioni",
                           entries)
    keys = state.entrants[:3]
    state.payload["times"] = {keys[0]: parse_time("3:34,050"),
                              keys[1]: parse_time("3:31,370")}
    ev.save_race(state)

    result = R.classify(ev.load_race(state.race_id), entries, comp)
    assert [p.key for p in result.placings][:2] == [keys[1], keys[0]]
    assert result.pending >= 1  # the third team has no time

    doc = D.race_classification(state, result, entries, comp, communique="15")
    html = to_html(doc, comp)
    assert "3:31,370" in html
    assert "INSEGUIMENTO A SQUADRE" in html
    assert "Comunicato n. 15" in html


def test_team_pursuit_results_mark_the_qualifiers(ev, entries, comp):
    """The qualifying sheet says who goes through: bold, then a heavier rule."""
    state = R.ensure_state(ev, comp, "AL", "ins_squadre", "Qualificazioni",
                           entries)
    keys = state.entrants[:6]
    state.payload["times"] = {k: parse_time(f"3:3{i},000")
                              for i, k in enumerate(keys)}
    result = R.classify(state, entries, comp)

    doc = D.race_classification(state, result, entries, comp)
    table = doc.tables[0]
    assert [c.label for c in table.columns] == \
        ["Ris.", "Num.", "Cognome", "Nome", "UCI ID", "Team", "Tempo"]

    firsts = [r for r in table.rows if r.get("rank")]
    assert all(r["_bold"] == {"group", "time"} for r in firsts[:4])
    assert not firsts[4].get("_bold")
    # the cut is the only strong rule on the sheet
    assert [i for i, r in enumerate(firsts)
            if "group-start-strong" in r.get("_class", "")] == [4]

    # a finals sheet has nothing left to qualify for
    state.payload["final_heats"] = [[keys[0], keys[3]], [keys[1], keys[2]]]
    finals = D.race_classification(state, R.classify(state, entries, comp),
                                   entries, comp)
    assert not any(r.get("_bold") for r in finals.tables[0].rows)


def test_a_saved_race_follows_the_check_in(ev, entries, comp):
    """Re-composing the squadre must not leave ghosts in a saved race."""
    state = R.ensure_state(ev, comp, "AL", "ins_squadre", "Qualificazioni",
                           entries)
    gone, kept = state.entrants[0], state.entrants[1]
    state.payload.update(heat_sides=[[gone, kept]], qual_ranking=[gone, kept],
                         heat_bibs={gone: "1, 2, 3, 4"},
                         times={gone: 1000, kept: 2000})
    R.set_status(state, gone, Status.DNS)
    ev.save_race(state)

    team = entries.teams.pop(gone)  # the jury re-composes: that squadra is gone
    try:
        back = R.ensure_state(ev, comp, "AL", "ins_squadre", "Qualificazioni",
                              entries)
    finally:
        entries.teams[gone] = team
    p = back.payload
    assert gone not in back.entrants and kept in back.entrants
    assert p["heat_sides"] == [["", kept]]
    assert p["qual_ranking"] == [kept]
    assert gone not in p["heat_bibs"] and gone not in p["times"]
    assert gone not in back.statuses


def test_a_rider_entered_after_the_race_was_opened_reaches_the_track(
        ev, entries, comp):
    """The verifica goes on all day: an individual race has to follow it.

    A rider added at the check-in - one who turned up, or whose entry the jury
    accepted late - was not on the entry list when the race was first opened.
    The race keeps its own copy of the entrants, so without this she would be
    on no start order and on no classification of a specialità she rode.
    """
    key = ("AL", "velocita", "Qualificazioni")
    state = R.ensure_state(ev, comp, *key, entries)
    was = len(state.entrants)
    ev.save_race(state)

    late = next(r for r in entries.by_cat("AL")
                if r.bib is not None and str(r.bib) not in state.entrants)
    late.events["velocita"] = EventEntry()  # the jury enters her at the verifica
    try:
        back = R.ensure_state(ev, comp, *key, entries)
        assert str(late.bib) in back.entrants
        assert len(back.entrants) == was + 1
        # and in bib order, like everybody else on the sheet
        assert back.entrants == sorted(back.entrants, key=int)
    finally:
        del late.events["velocita"]

    # ...and NP takes her back off it: the same list, read the same way
    off = R.ensure_state(ev, comp, *key, entries)
    assert str(late.bib) not in off.entrants and len(off.entrants) == was


def test_a_composed_round_keeps_the_riders_it_was_seeded_with(
        ev, entries, comp):
    """Only the rounds nobody composed follow the entry list.

    A turno of a velocità rides the twelve the 200 m sent through; a keirin
    starts its first round off the entry list, by the UCI table. Resyncing the
    first would wipe the seeding and put the whole category on the track.
    """
    assert not R.is_seeded_round(comp, "AL", "velocita", "Qualificazioni")
    assert R.is_seeded_round(comp, "AL", "velocita", "Quarti")
    assert R.is_seeded_round(comp, "AL", "velocita", "Finali")
    assert not R.is_seeded_round(comp, "AL", "keirin", "Turno 1")
    assert R.is_seeded_round(comp, "AL", "keirin", "Semifinali")

    seeded = R.ensure_state(ev, comp, "AL", "velocita", "Quarti", entries)
    seeded.entrants = ["1", "2", "3", "4"]
    ev.save_race(seeded)
    back = R.ensure_state(ev, comp, "AL", "velocita", "Quarti", entries)
    assert back.entrants == ["1", "2", "3", "4"]


def test_heat_bibs_do_not_outlive_the_team(entries, comp):
    """A hand-typed side stands only while its numbers are the team's."""
    from ui.pages.races import _side_bibs

    key = next(k for k, t in entries.teams.items()
               if t.event == "ins_squadre" and len(t.riders) > 2)
    bibs = [entries.riders[k].bib for k in entries.teams[key].riders]
    # a stale composition, from bibs that are no longer in this team
    ov = {key: "997, 998, 999, 996"}
    assert _side_bibs(key, entries, ov) == ", ".join(str(b) for b in bibs)
    assert key not in ov
    # the same numbers as the entry list: no copy is kept
    ov = {key: ", ".join(str(b) for b in bibs)}
    assert _side_bibs(key, entries, ov) and key not in ov


def test_team_pursuit_from_qualification_to_the_champion(ev, entries, comp):
    """The whole flow: qualify, load the finals, ride them, print the sheets."""
    from ui.pages.races import _load_finals

    qual = R.ensure_state(ev, comp, "AL", "ins_squadre", "Qualificazioni",
                          entries)
    keys = qual.entrants[:6]
    qual.payload["times"] = {k: parse_time(f"3:5{i},000")
                             for i, k in enumerate(keys)}
    ev.save_race(qual)
    ranking = [p.key for p in R.classify(qual, entries, comp).placings
               if p.position]
    _load_finals(qual, R.classify(qual, entries, comp), entries, comp, ev,
                 "Finali")

    fin = R.ensure_state(ev, comp, "AL", "ins_squadre", "Finali", entries)
    assert fin.entrants == ranking[:4]          # only the qualified start
    assert fin.payload["final_heats"] == [[ranking[2], ranking[3]],
                                          [ranking[0], ranking[1]]]

    # the 3/4 final rides fastest and still stays third
    fin.payload["times"] = {ranking[2]: parse_time("3:40,000"),
                            ranking[3]: parse_time("3:41,000"),
                            ranking[0]: parse_time("3:45,000"),
                            ranking[1]: parse_time("3:44,000")}
    result = R.classify(fin, entries, comp)
    assert [p.key for p in result.placings][:5] == \
        [ranking[1], ranking[0], ranking[2], ranking[3], ranking[4]]
    # whoever did not qualify keeps the time of the qualification
    assert result.by_key(ranking[4]).data["time"] == \
        qual.payload["times"][ranking[4]]

    results = to_html(D.race_classification(fin, result, entries, comp,
                                            by_final=True), comp)
    assert ("FINALE 3°/4° POSTO" in results
            and "FINALE 1°/2° POSTO" in results)
    assert "SQUADRA CAMPIONE" not in results

    final = to_html(D.race_classification(fin, result, entries, comp,
                                          champion=True), comp)
    assert "SQUADRA CAMPIONE D" in final  # the apostrophe is escaped
    assert R.entrant_label(ranking[4], entries) in final  # everyone is ranked


def test_individual_pursuit_from_qualification_to_the_champion(ev, entries, comp):
    """The inseguimento individuale runs the same flow, one rider a side."""
    from ui.pages.races import _load_finals

    qual = R.ensure_state(ev, comp, "AL", "ins_individuale", "Qualificazioni",
                          entries)
    assert qual.fmt == R.TIMED
    # the sheets say by themselves where the first rider starts and what the
    # qualification qualifies for
    note = comp.event("ins_individuale").note()
    assert "rettilineo d'arrivo" in note and "migliori 4 tempi" in note
    assert comp.round_of("AL", "ins_individuale", "Qualificazioni").qualify == 4

    keys = qual.entrants[:6]
    qual.payload["times"] = {k: parse_time(f"3:5{i},000")
                             for i, k in enumerate(keys)}
    ev.save_race(qual)
    result = R.classify(qual, entries, comp)
    ranking = [p.key for p in result.placings if p.position]
    # the risultati rule a line under the fourth time, as on the sheet a
    # squadre: the qualifiers are bold and the cut is a heavier rule
    quali = to_html(D.race_classification(qual, result, entries, comp,
                                          doc_kind="risultati"), comp)
    assert "group-start-strong" in quali

    _load_finals(qual, result, entries, comp, ev, "Finali")
    fin = R.ensure_state(ev, comp, "AL", "ins_individuale", "Finali", entries)
    assert fin.entrants == ranking[:4]
    assert fin.payload["final_heats"] == [[ranking[2], ranking[3]],
                                          [ranking[0], ranking[1]]]
    # the ordine di partenza of the finals is the seeding, not the entry list
    partenti = to_html(D.race_startlist(fin, entries, comp,
                                        heats=[[[int(ranking[2])],
                                                [int(ranking[3])]],
                                               [[int(ranking[0])],
                                                [int(ranking[1])]]]), comp)
    assert "3°/4°" in partenti and "1°/2°" in partenti
    # an inseguimento individuale is ridden by riders: the number on the sheet
    # is the dorsale, called by that name, and the UCI ID is on it as on every
    # other sheet of a race against the clock
    heads = re.findall(r"<th[^>]*>([^<]*)</th>", partenti)
    assert "Dors." in heads and "Num." not in heads
    assert "UCI ID" in heads

    fin.payload["times"] = {ranking[2]: parse_time("3:40,000"),
                            ranking[3]: parse_time("3:41,000"),
                            ranking[0]: parse_time("3:45,000"),
                            ranking[1]: parse_time("3:44,000")}
    res = R.classify(fin, entries, comp)
    assert [p.key for p in res.placings][:5] == \
        [ranking[1], ranking[0], ranking[2], ranking[3], ranking[4]]

    risultati = to_html(D.race_classification(fin, res, entries, comp,
                                              by_final=True), comp)
    assert ("FINALE 3°/4° POSTO" in risultati
            and "FINALE 1°/2° POSTO" in risultati)

    classifica = to_html(D.race_classification(
        fin, res, entries, comp, champion=True,
        champion_label="CAMPIONE D'ITALIA"), comp)
    assert "CAMPIONE D" in classifica
    # whoever did not qualify is ranked below the finalists, on the time of
    # the qualification
    assert ranking[4] in [p.key for p in res.placings]


def test_a_final_left_a_pari_merito_names_no_champion(ev, entries, comp):
    """The 1°/2° is not ridden: two seconde and no squadra campione.

    The 3/4 final below it is ridden as usual and still decides third and
    fourth: leaving one final unridden does not move the other.
    """
    from ui.pages.races import _load_finals

    qual = R.ensure_state(ev, comp, "AL", "ins_squadre", "Qualificazioni",
                          entries)
    keys = qual.entrants[:6]
    qual.payload["times"] = {k: parse_time(f"3:5{i},000")
                             for i, k in enumerate(keys)}
    ev.save_race(qual)
    result = R.classify(qual, entries, comp)
    ranking = [p.key for p in result.placings if p.position]
    _load_finals(qual, result, entries, comp, ev, "Finali")

    fin = R.ensure_state(ev, comp, "AL", "ins_squadre", "Finali", entries)
    fin.payload["finals_tied"] = [1]
    fin.payload["times"] = {ranking[2]: parse_time("3:40,000"),
                            ranking[3]: parse_time("3:41,000")}
    res = R.classify(fin, entries, comp)
    assert [p.label for p in res.placings][:5] == \
        ["2°", "2°", "3°", "4°", "5°"]
    assert [p.position for p in res.placings][:5] == [2, 2, 3, 4, 5]
    # the 1/2 was not ridden: no time goes in that column
    assert [p.data["time"] for p in res.placings][:2] == [None, None]
    # the 1/2 will not be ridden: nothing is still to come on this sheet
    assert res.pending == 0

    classifica = to_html(D.race_classification(
        fin, res, entries, comp, champion=True,
        champion_label="CAMPIONE D'ITALIA"), comp)
    assert "CAMPIONE D" not in classifica

    risultati = to_html(D.race_classification(fin, res, entries, comp,
                                              by_final=True), comp)
    assert "FINALE 1°/2° POSTO" in risultati


def test_a_squadra_out_in_qualification_stays_on_the_final_classification(
        ev, entries, comp):
    """DSQ in qualification: no place, but the classifica files the decision.

    And it follows the qualification: withdraw the decision there and the
    squadra takes its place back on the sheet, without re-seeding the finals.
    """
    from ui.pages.races import _load_finals

    qual = R.ensure_state(ev, comp, "AL", "ins_squadre", "Qualificazioni",
                          entries)
    keys = qual.entrants[:6]
    qual.payload["times"] = {k: parse_time(f"3:5{i},000")
                             for i, k in enumerate(keys)}
    R.set_status(qual, keys[5], Status.DSQ)
    ev.save_race(qual)
    _load_finals(qual, R.classify(qual, entries, comp), entries, comp, ev,
                 "Finali")

    fin = R.ensure_state(ev, comp, "AL", "ins_squadre", "Finali", entries)
    result = R.classify(fin, entries, comp)
    out = result.by_key(keys[5])
    assert out is not None and out.position is None
    assert out.label == "DSQ"
    assert result.placings[-1].key == keys[5]
    # the time it rode never prints next to a DSQ
    html = to_html(D.race_classification(fin, result, entries, comp), comp)
    assert R.entrant_label(keys[5], entries) in html and "DSQ" in html
    assert "3:55,000" not in html

    R.set_status(qual, keys[5], Status.OK)
    ev.save_race(qual)
    fin = R.ensure_state(ev, comp, "AL", "ins_squadre", "Finali", entries)
    assert R.classify(fin, entries, comp).by_key(keys[5]).label == "6°"


def test_madison_scores_by_pair(ev, entries, comp):
    state = R.ensure_state(ev, comp, "ED", "madison", "Finale", entries)
    assert state.fmt == R.MADISON
    bib_of = R.pair_bib_map(state, entries)
    first_two = state.entrants[:2]
    a, b = bib_of[first_two[0]], bib_of[first_two[1]]

    state.payload["sprints"] = f"{a},{b}-{b},{a}"
    ev.save_race(state)
    result = R.classify(ev.load_race(state.race_id), entries, comp)
    # pair b wins the double-points final sprint
    assert result.placings[0].key == b
    doc = D.race_classification(state, result, entries, comp)
    html = to_html(doc, comp)
    assert "Coppia" in html
    assert entries.pairs[first_two[1]].label in html


def test_elimination_live_sheet(ev, entries, comp):
    state = R.ensure_state(ev, comp, "DA", "omnium", "Eliminazione", entries)
    bibs = [int(b) for b in state.entrants]
    state.payload["eliminated"] = ",".join(str(b) for b in bibs[-3:])
    result = R.classify(state, entries, comp)
    assert result.pending == len(bibs) - 3
    assert result.placings[-1].key == str(bibs[-3])  # first out is last
    assert result.placings[0].label == ""  # still racing


def test_startlist_document_with_heats(ev, entries, comp):
    state = R.ensure_state(ev, comp, "AL", "ins_individuale", "Qualificazioni",
                           entries)
    bibs = [int(b) for b in state.entrants[:4]]
    heats = [[[bibs[0]], [bibs[1]]], [[bibs[2]], [bibs[3]]]]
    doc = D.race_startlist(state, entries, comp, heats=heats, communique="124")
    html = to_html(doc, comp)
    # the number of the batteria once, against its first side
    assert [c.label for c in doc.tables[0].columns][0] == "Batt."
    assert [r.get("group") for r in doc.tables[0].rows] == ["1", "", "2", ""]
    assert "Comunicato n. 124" in html
    # a batteria opens with a rule; one rider a side needs no more than a
    # hairline (the class names are in the stylesheet too - look at the rows)
    classes = [r.get("_class", "") for r in doc.tables[0].rows]
    assert classes == ["", "", "group-start", ""]


def test_a_velocita_start_order_is_ruled_like_its_results(ev, entries, comp):
    """A hairline opens each batteria, and nothing comes between its two riders.

    The heavy rule and the rule between sides are what a sheet of quartetti
    needs to read as blocks of four against four. On a velocità a batteria is
    two lines that belong together, and the risultati of the same round have
    ruled them that way all along.
    """
    state = R.ensure_state(ev, comp, "AL", "velocita", "Qualificazioni",
                           entries)
    bibs = [int(b) for b in state.entrants[:4]]

    # the 200 m: one start at a time, a hairline per starter
    solo = [[[b]] for b in bibs[:3]]
    rows = D.race_startlist(state, entries, comp, heats=solo).tables[0].rows
    assert [r.get("_class", "") for r in rows] == ["", "group-start",
                                                   "group-start"]

    # the batterie of the turno 1: the rule opens the batteria, not the rider
    pairs = [[[bibs[0]], [bibs[1]]], [[bibs[2]], [bibs[3]]]]
    rows = D.race_startlist(state, entries, comp, heats=pairs).tables[0].rows
    assert [r.get("_class", "") for r in rows] == ["", "", "group-start", ""]

    # a quartetto against a quartetto keeps both of its rules: the heavy one
    # between batterie, the light one between the two squadre of a batteria
    teams = R.ensure_state(ev, comp, "AL", "ins_squadre", "Qualificazioni",
                           entries)
    sides = [[r.bib for r in R.entrant_riders(k, entries, "AL")]
             for k in teams.entrants[:4]]
    rows = D.race_startlist(teams, entries, comp,
                            heats=[sides[:2], sides[2:]]).tables[0].rows
    classes = [r.get("_class", "") for r in rows]
    assert classes.count("side-start") == 2          # one per batteria
    assert classes.count("group-start-strong") == 1  # between the two


def test_archive_writes_a_reprintable_file(ev, entries, comp):
    state = R.ensure_state(ev, comp, "AL", "omnium", "Scratch", entries)
    state.payload["sprints"] = ",".join(state.entrants[:5])
    result = R.classify(state, entries, comp)
    doc = D.race_classification(state, result, entries, comp, communique="94")
    p = archive(ev, doc, comp, number="94")
    assert p.name.startswith("094_")
    if p.suffix == ".pdf":               # with a browser; the HTML is the fallback
        assert p.read_bytes().startswith(b"%PDF")
        return
    text = p.read_text(encoding="utf-8")
    assert text.lstrip().startswith("<!doctype html>")
    assert "Comunicato n. 94" in text


# ── what a prova di gruppo prints ───────────────────────────────────────────

def test_the_classifica_of_a_prova_lists_who_never_started_as_dns(
        ev, entries, comp):
    """A DNS is a sigla like the others: at the foot of the table, not a note.

    The rider stays on the sheet of the prova she was called to - in an omnium
    she rides the next one, and a number that vanishes here is the one nobody
    can account for afterwards.
    """
    state = R.ensure_state(ev, comp, "AL", "omnium", "Scratch", entries)
    bibs = state.entrants[:5]
    state.payload["sprints"] = ",".join(bibs[1:])
    R.set_status(state, bibs[0], Status.DNS)
    doc = D.race_classification(state, R.classify(state, entries, comp),
                                entries, comp)
    rows = doc.tables[0].rows
    assert [r["rank"] for r in rows if r["rank"]][-1] == "DNS"
    assert str(bibs[0]) in {str(r.get("bib")) for r in rows}
    assert "DNS" not in doc.legend


def test_the_riders_who_left_the_race_print_in_the_order_they_left(
        ev, entries, comp):
    """Reverse order of the DNF field, and a scesa carries no points."""
    state = R.ensure_state(ev, comp, "AL", "omnium", "Corsa a Punti", entries)
    bibs = state.entrants[:6]
    state.payload["sprints"] = ",".join(bibs[:4])
    R.set_statuses_from_text(state, f"{bibs[0]}, {bibs[1]}", Status.DNF)
    R.set_statuses_from_text(state, f"{bibs[2]}, {bibs[3]}", Status.ABD)
    result = R.classify(state, entries, comp)
    order = [p.key for p in result.placings]
    assert order[-4:] == [bibs[1], bibs[0], bibs[3], bibs[2]]
    assert result.by_key(bibs[0]).data["total"] > 0     # DNF keeps its points
    assert result.by_key(bibs[2]).data["total"] == 0    # ABD does not


def test_an_ammonizione_prints_a_w_on_the_sheets_that_follow(ev, entries, comp):
    from core import decisions as DEC

    state = R.ensure_state(ev, comp, "AL", "omnium", "Scratch", entries)
    bib = int(state.entrants[0])
    DEC.add(ev, DEC.Decision(cat="AL", event="omnium", round_key="Scratch",
                             bibs=str(bib), penalty=DEC.WARNING,
                             text="ammonizione"))
    warned = R.warnings_carried(ev, comp, "AL", "omnium", "Tempo Race")
    assert warned == {bib: "Scratch"}

    # written on the dorsale itself - "1 W" - and not in a column of its own
    rows = D.race_startlist(state, entries, comp, warned=warned).tables[0].rows
    assert [r["bib"] for r in rows if str(r.get("bib")).endswith(" W")] \
        == [f"{bib} W"]
    plain = D.race_startlist(state, entries, comp).tables[0]
    assert not any(str(r.get("bib")).endswith(" W") for r in plain.rows)
    assert [c.key for c in plain.columns] == [
        c.key for c in D.race_startlist(state, entries, comp,
                                        warned=warned).tables[0].columns]


def test_bad_input_does_not_crash_the_race(ev, entries, comp):
    state = R.ensure_state(ev, comp, "AL", "omnium", "Corsa a Punti", entries)
    state.payload["sprints"] = "1,2,tre-4"
    result = R.classify(state, entries, comp)
    assert result.placings == []
    assert any("non è un dorsale valido" in w for w in result.warnings)


# ── reset ───────────────────────────────────────────────────────────────────

def test_reset_event_removes_every_round_and_heat(store):
    """Impostazioni -> «Azzera una gara»: the whole event goes, not one round."""
    for round_key in ("Qualificazioni", "Qualificazioni-Batteria 1", "Finali"):
        st = store.get_race("AL", "ins_squadre", round_key)
        st.payload["heats"] = "1-2"
        store.save_race(st)
    other = store.get_race("AL", "omnium", "Scratch")
    store.save_race(other)

    assert [s.round_key for s in R.saved_races(store, "AL", "ins_squadre")] == [
        "Finali", "Qualificazioni", "Qualificazioni-Batteria 1"]

    removed = R.reset_event(store, "AL", "ins_squadre")

    assert len(removed) == 3
    assert R.saved_races(store, "AL", "ins_squadre") == []
    assert store.load_race(other.race_id) is not None      # untouched
    # nothing is lost for good: every deleted file kept its snapshot
    assert all(store.snapshots(store.race_rel(rid)) for rid in removed)
    assert [e["action"] for e in store.read_journal()][-1] == "reset_event"


def test_reset_event_on_nothing_is_a_no_op(store):
    assert R.reset_event(store, "ES", "keirin") == []
    assert store.read_journal() == []


def test_has_results_ignores_an_untouched_startlist(store):
    st = store.get_race("DA", "scratch", "Finale")
    st.entrants = ["12", "13"]
    assert not R.has_results(st)
    st.payload["sprints"] = "12,13"
    assert R.has_results(st)


# ── madison: pairing, batterie, qualification (UCI 3.2.157) ─────────────────

@pytest.fixture
def madison(ev, entries, comp):
    """ES madison composed: numbers 1..N, coppie dealt into the two batterie."""
    keys = R.entrants(entries, comp, "ES", "madison")
    setup = R.ensure_state(ev, comp, "ES", "madison", "Composizione coppie",
                           entries)
    setup.payload[R.PAIR_NUMBERS] = R.default_numbers(keys)
    setup.payload[R.PAIR_HEATS] = R.spread_heats(keys, 2)
    setup.payload[R.ELIMINATE] = 2
    ev.save_race(setup)
    R.apply_pair_numbers(ev, comp, entries)
    return ev


def test_the_setup_round_is_composed_not_ridden(comp):
    assert R.round_format(comp, "ES", "madison", "Composizione coppie") == R.SETUP
    assert R.setup_round(comp, "ES", "madison") == "Composizione coppie"
    assert comp.round_of("ES", "madison", "Composizione coppie").docs == []
    # the batterie the programme schedules, in order
    assert R.heat_rounds(comp, "ES", "madison") == [
        (1, "Qualificazioni Batteria 1"), (2, "Qualificazioni Batteria 2")]


def test_a_batteria_starts_only_its_own_coppie(madison, entries, comp):
    """The bug this round exists to fix: both heats used to start everybody."""
    everyone = R.entrants(entries, comp, "ES", "madison")
    b1 = R.ensure_state(madison, comp, "ES", "madison",
                        "Qualificazioni Batteria 1", entries)
    b2 = R.ensure_state(madison, comp, "ES", "madison",
                        "Qualificazioni Batteria 2", entries)

    assert len(b1.entrants) + len(b2.entrants) == len(everyone)
    assert not set(b1.entrants) & set(b2.entrants)
    assert sorted(b1.entrants + b2.entrants) == sorted(everyone)


def test_pair_numbers_reach_the_scoring_and_the_sheet(madison, entries, comp):
    """The number the jury assigns is the number it types into the sprints."""
    b1 = R.ensure_state(madison, comp, "ES", "madison",
                        "Qualificazioni Batteria 1", entries)
    numbers = [entries.pairs[k].bib for k in b1.entrants]
    assert numbers == sorted(numbers) and all(numbers)
    assert R.pair_bib_map(b1, entries) == {k: str(entries.pairs[k].bib)
                                           for k in b1.entrants}

    b1.payload["sprints"] = ",".join(str(n) for n in reversed(numbers))
    result = R.classify(b1, entries, comp)
    assert result.placings[0].key == str(numbers[-1])  # last number, first home

    doc = D.race_startlist(b1, entries, comp, show_bib=False)
    html = to_html(doc, comp)
    heads = [c.label for c in doc.tables[0].columns]
    assert heads[0] == "Coppia" and "Dors." not in heads
    # both riders carry the number in bold; the second one wears it red
    assert html.count('class="c b red"') == len(b1.entrants)
    assert "Dors." in [c.label for c in D.race_startlist(
        b1, entries, comp, show_bib=True).tables[0].columns]


def test_qualifiers_are_counted_among_those_who_started(comp):
    """3.2.157: an equal number out of each heat, among the teams who started."""
    from core.formats.base import Placing, Result

    placings = [Placing(key=str(i), position=i) for i in range(1, 7)]
    placings.append(Placing(key="7", status=Status.DNS))
    placings.append(Placing(key="8", status=Status.DNF))
    result = Result(placings=placings)

    through, out = R.heat_cut(result, 2)
    # 7 started (six finishers plus the DNF), two go out: five qualify
    assert through == ["1", "2", "3", "4", "5"]
    # the coppia that never started is not one of the eliminated, it is absent
    assert out == ["6", "8"]
    # whoever did not finish does not progress either (classification rule A)
    assert "8" not in through


def test_the_final_starts_the_qualifiers_and_nobody_else(madison, entries, comp):
    heats = {}
    for n, key in R.heat_rounds(comp, "ES", "madison"):
        state = R.ensure_state(madison, comp, "ES", "madison", key, entries)
        order = [str(entries.pairs[k].bib) for k in state.entrants]
        state.payload["sprints"] = ",".join(order)   # finish in startlist order
        madison.save_race(state)
        heats[n] = state.entrants

    info = R.load_qualified(madison, comp, entries, "ES", "madison")

    assert not info["missing"]
    expected = sum(max(0, len(v) - 2) for v in heats.values())
    assert len(info["qualified"]) == expected
    # dealt across the batterie: the winners first, then the seconds
    assert info["qualified"][:2] == [heats[1][0], heats[2][0]]

    fin = R.ensure_state(madison, comp, "ES", "madison", "Finale", entries)
    assert fin.entrants == info["qualified"]
    # reloading must not quietly put the eliminated coppie back on the startlist
    assert len(fin.entrants) < len(R.entrants(entries, comp, "ES", "madison"))


def test_a_madison_without_batterie_starts_everybody(ev, entries, comp):
    """ED and DA ride the final straight off: no heats, no qualification."""
    everyone = R.entrants(entries, comp, "ED", "madison")
    fin = R.ensure_state(ev, comp, "ED", "madison", "Finale", entries)
    assert fin.entrants == everyone
    assert R.heat_rounds(comp, "ED", "madison") == []


def test_eliminated_never_fewer_than_two(comp):
    # 14 coppie on a 333.33 m track (limit 20): nothing forces a cut, and the
    # regulation's floor of two stands anyway
    assert R.eliminated_suggestion(comp, [7, 7]) == 2
    # 26 started, 20 fit: three out of each heat brings the field inside
    assert R.eliminated_suggestion(comp, [13, 13]) == 3


def test_the_cut_counts_only_the_coppie_that_started(madison, entries, comp):
    """3.2.157: a DNS is not one of the eliminated, and takes no place away."""
    b1 = R.ensure_state(madison, comp, "ES", "madison",
                        "Qualificazioni Batteria 1", entries)
    # the cut in force travels onto the batteria, so its sheets keep saying it
    assert b1.payload[R.ELIMINATE] == 2
    assert R.qualify_count(b1, 2) == len(b1.entrants) - 2

    R.set_status(b1, b1.entrants[-1], Status.DNS)
    assert R.qualify_count(b1, 2) == len(b1.entrants) - 3
    # still two eliminated among the six who started, not three
    b1.payload["sprints"] = ",".join(str(entries.pairs[k].bib)
                                     for k in b1.entrants[:-1])
    through, out = R.heat_qualifiers(b1, entries, comp, 2)
    assert len(through) == len(b1.entrants) - 3 and len(out) == 2
    assert b1.entrants[-1] not in through + out


def test_the_results_sheet_rules_off_the_qualifiers(madison, entries, comp):
    """The heavier rule under the last coppia through - the jury's own line."""
    from core.config import DOC_RESULTS

    b1 = R.ensure_state(madison, comp, "ES", "madison",
                        "Qualificazioni Batteria 1", entries)
    b1.payload["sprints"] = ",".join(str(entries.pairs[k].bib)
                                     for k in b1.entrants)
    result = R.classify(b1, entries, comp)
    doc = D.race_classification(b1, result, entries, comp,
                                doc_kind=DOC_RESULTS, subtitle="Risultati")

    rows = doc.tables[0].rows
    cut = [i for i, r in enumerate(rows)
           if "group-start-strong" in r.get("_class", "")]
    assert len(cut) == 1
    through = R.qualify_count(b1, 2)
    # the rule opens the line of the first coppia that did not make it
    assert rows[cut[0]]["rank"] == f"{through + 1}°"

    # a startlist has nothing to rule off
    start = D.race_startlist(b1, entries, comp)
    assert not any("group-start-strong" in r.get("_class", "")
                   for r in start.tables[0].rows)


def test_the_startlist_runs_in_coppia_number_order(madison, entries, comp):
    """The sheet is read by number: renumbering re-orders it, region or not."""
    keys = R.entrants(entries, comp, "ES", "madison")
    setup = madison.load_race(R.race_key("ES", "madison", "Composizione coppie"))
    # hand the numbers out backwards: the entry order and the numbers now
    # disagree, which is exactly the case the sheet has to follow
    setup.payload[R.PAIR_NUMBERS] = {k: len(keys) - i
                                     for i, k in enumerate(keys)}
    madison.save_race(setup)
    R.apply_pair_numbers(madison, comp, entries)

    b1 = R.ensure_state(madison, comp, "ES", "madison",
                        "Qualificazioni Batteria 1", entries)
    numbers = [entries.pairs[k].bib for k in b1.entrants]
    assert numbers == sorted(numbers)

    doc = D.race_startlist(b1, entries, comp, show_bib=False)
    printed = [r["group"] for r in doc.tables[0].rows if r.get("group")]
    assert printed == [str(n) for n in numbers for _ in (0, 1)]


def test_a_coppia_carries_its_letter_on_the_sheets(madison, entries, comp):
    """A region that fields two coppie keeps the A/B next to them everywhere.

    The number says who is on the track; the letter says which of the two
    coppie of that rappresentativa it is, and the jury reads both off the same
    line - as it does for the two quartetti of a squadra.
    """
    pairs = [k for k in R.entrants(entries, comp, "ES", "madison")
             if entries.pairs[k].letter]
    assert pairs, "the fixture must field a region with two coppie"
    key = pairs[0]
    assert R.entrant_label(key, entries) == entries.pairs[key].label

    b1 = R.ensure_state(madison, comp, "ES", "madison",
                        "Qualificazioni Batteria 1", entries)
    teams = {r["team"] for r in D.race_startlist(b1, entries, comp).tables[0].rows
             if r.get("team")}
    assert any(t.endswith((" A", " B")) for t in teams)


def test_the_madison_sheets_carry_no_society(madison, entries, comp):
    """A coppia is read by number and region: the society is width off the names."""
    from core.config import DOC_CLASSIFICATION, DOC_RESULTS

    b1 = R.ensure_state(madison, comp, "ES", "madison",
                        "Qualificazioni Batteria 1", entries)
    b1.payload["sprints"] = ",".join(str(entries.pairs[k].bib)
                                     for k in b1.entrants)
    result = R.classify(b1, entries, comp)
    for kind in (DOC_RESULTS, DOC_CLASSIFICATION):
        doc = D.race_classification(b1, result, entries, comp, doc_kind=kind)
        keys = [c.key for c in doc.tables[0].columns]
        assert "club" not in keys and "team" in keys
    # the classifica can still ask for it: it is the sheet the societies file
    doc = D.race_classification(b1, result, entries, comp,
                                doc_kind=DOC_CLASSIFICATION, show_club=True)
    keys = [c.key for c in doc.tables[0].columns]
    assert "club" in keys and "club_code" in keys


def test_the_final_classification_names_the_champion_coppia(madison, entries,
                                                            comp):
    """SQUADRA CAMPIONE D'ITALIA, under the names of the winning coppia."""
    fin = R.ensure_state(madison, comp, "ES", "madison", "Finale", entries)
    fin.payload["sprints"] = ",".join(str(entries.pairs[k].bib)
                                      for k in fin.entrants)
    result = R.classify(fin, entries, comp)
    rows = D.race_classification(fin, result, entries, comp,
                                 champion=True).tables[0].rows
    bands = [(i, r) for i, r in enumerate(rows) if r.get("_banner")]
    assert len(bands) == 1
    i, band = bands[0]
    assert band["_banner"] == "SQUADRA CAMPIONE D'ITALIA"
    # under the names, as on the inseguimento - not out in the number column
    assert band["_banner_at"] == "last_name"
    assert rows[0]["rank"] == "1°" and i == 2
    # the results of the same race name nobody: the title is the classifica's
    assert not any(r.get("_banner") for r in
                   D.race_classification(fin, result, entries, comp,
                                         doc_kind="risultati").tables[0].rows)


def test_a_coppia_that_did_not_start_is_classified_last(madison, entries, comp):
    """DNS/DNF/DSQ go to the bottom, in that order, and score nothing.

    The jury types a coppia number into those fields; the status belongs to
    the coppia. Stored under the number it landed on nobody at all, and a
    coppia that never took the start was classified as if it had ridden - and
    counted among the starters for the 3.2.157 cut.
    """
    b1 = R.ensure_state(madison, comp, "ES", "madison",
                        "Qualificazioni Batteria 1", entries)
    bibs = [entries.pairs[k].bib for k in b1.entrants]
    b1.payload["sprints"] = ",".join(str(b) for b in bibs)

    keys = R.status_keys(b1, entries, R.MADISON)
    # the last three of the sprint, so their own result would not put them last
    R.set_statuses_from_text(b1, str(bibs[-1]), Status.DNS, keys=keys)
    R.set_statuses_from_text(b1, str(bibs[-2]), Status.DNF, keys=keys)
    R.set_statuses_from_text(b1, str(bibs[-3]), Status.DSQ, keys=keys)
    # stored on the coppia, not on the number that was typed
    assert set(b1.statuses) == {b1.entrants[-1], b1.entrants[-2],
                                b1.entrants[-3]}

    result = R.classify(b1, entries, comp)
    tail = [p.status for p in result.placings[-3:]]
    assert tail == [Status.DNF, Status.DNS, Status.DSQ]
    assert all(p.position is None and not p.data["total"]
               for p in result.placings[-3:])
    # and the sheet prints them at the bottom, by status - the coppia that
    # never started among them, under its own sigla
    doc = D.race_classification(b1, result, entries, comp,
                                doc_kind="risultati")
    rows = doc.tables[0].rows
    assert [r["rank"] for r in rows if r["rank"]][-3:] == ["DNF", "DNS", "DSQ"]
    # a coppia that did not start is not one of the eliminated (3.2.157)
    assert R.qualify_count(b1, 2) == len(b1.entrants) - 3


def test_the_team_sprint_starts_one_squadra_at_a_time(ev, entries, comp):
    """Velocità a squadre: an ordine di partenza, not batterie.

    Every squadra rides alone, so the sheet counts starts. The inseguimento,
    where two squadre start on opposite straights, keeps its batterie.
    """
    from core.parse import parse_heats
    from ui.pages.races import _entrant_bibs

    assert comp.event("vel_squadre").teams_per_start == 1
    assert comp.event("ins_squadre").teams_per_start == 2

    state = R.ensure_state(ev, comp, "AL", "vel_squadre", "Qualificazioni",
                           entries)
    # one squadra per start, in the order they are called
    state.payload["heats"] = "/".join(
        ",".join(str(b) for b in _entrant_bibs(k, entries))
        for k in state.entrants)
    heats = parse_heats(state.payload["heats"])
    assert len(heats) == len(state.entrants) and all(len(h) == 1 for h in heats)

    doc = D.race_startlist(state, entries, comp, heats=heats)
    assert doc.tables[0].columns[0].label == "Ord."
    assert "batterie" not in doc.info          # it would just count the squadre
    assert f"{len(state.entrants)} squadre" in doc.info

    ins = R.ensure_state(ev, comp, "AL", "ins_squadre", "Qualificazioni",
                         entries)
    pairs = ins.entrants[:4]
    ins.payload["heats"] = "/".join(
        "-".join(",".join(str(b) for b in _entrant_bibs(k, entries))
                 for k in pairs[i:i + 2]) for i in (0, 2))
    doc = D.race_startlist(ins, entries, comp,
                           heats=parse_heats(ins.payload["heats"]))
    assert doc.tables[0].columns[0].label == "Batt."
    assert "2 batterie" in doc.info


def test_a_finale_diretta_is_headed_by_its_batterie(ev, entries, comp):
    """«Finale diretta»: the first column is the batteria, not «Finale».

    A velocità a squadre or an inseguimento a squadre with too few squadre for
    two finals rides once against the clock, and `core.rounds` calls that one
    fase *Finale* because it is the whole event. Nothing qualified into it: it
    is ridden batteria by batteria like the qualification it replaces, and the
    ordine di partenza has to say so - the column head reading «Finale» made
    the sheet announce a final that is not being ridden. The Finali seeded from
    a qualification are the ones that keep it.
    """
    from core import rounds as RD
    from ui.pages.races import _entrant_bibs

    keys = R.entrants(entries, comp, "AL", "ins_squadre")
    heats = [[_entrant_bibs(k, entries) for k in keys[i:i + 2]]
             for i in (0, 2)]

    item = comp.scheduled("AL", "ins_squadre")
    kept = list(item.rounds)
    try:
        item.rounds = RD.propose(comp, "AL", "ins_squadre",
                                 RD.Options(direct_final=True))
        assert [r.key for r in item.rounds] == [RD.FINAL]
        state = R.ensure_state(ev, comp, "AL", "ins_squadre", RD.FINAL, entries)
        doc = D.race_startlist(state, entries, comp, heats=heats)
        assert doc.tables[0].columns[0].label == "Batt."
        assert [r.get("group") for r in doc.tables[0].rows][0] == "1"
    finally:
        item.rounds = kept

    fin = R.ensure_state(ev, comp, "AL", "ins_squadre", "Finali", entries)
    doc = D.race_startlist(fin, entries, comp, heats=heats)
    assert doc.tables[0].columns[0].label == "Finale"


def test_a_disqualified_time_never_prints(ev, entries, comp):
    """DSQ and a time on the same line read as a result. The race keeps it."""
    state = R.ensure_state(ev, comp, "AL", "ins_squadre", "Qualificazioni",
                           entries)
    good, out = state.entrants[0], state.entrants[1]
    state.payload["times"] = {good: parse_time("3:31,370"),
                              out: parse_time("3:29,000")}
    R.set_status(state, out, Status.DSQ)
    result = R.classify(state, entries, comp)

    html = to_html(D.race_classification(state, result, entries, comp), comp)
    assert "3:31,370" in html            # the squadra that was classified
    assert "3:29,000" not in html        # the one that was not
    assert "DSQ" in html
    # the time is still on the race: a decision can be withdrawn
    assert result.by_key(out).data["time"] == parse_time("3:29,000")


def test_the_team_sprint_sheets_say_what_they_always_say(ev, entries, comp):
    """The three default notes, and the cut under the fourth squadra."""
    from core.config import DOC_RESULTS
    from core.parse import parse_time
    from ui.pages.races import _default_notes

    tsp = comp.event("vel_squadre")
    assert tsp.note() == ("Cambio ogni mezzo giro.\n"
                          "Si qualificano per le finali le prime 4 squadre.")
    assert tsp.note(finals=True) == ("La prima squadra parte sul rettilineo "
                                     "opposto.\nCambio ogni mezzo giro.")

    qual = R.ensure_state(ev, comp, "AL", "vel_squadre", "Qualificazioni",
                          entries)
    assert _default_notes(qual, comp, ev)[DOC_RESULTS] == \
        "Si qualificano per le finali le prime 4 squadre."

    # ...and the sheet draws the line the note announces
    qual.payload["times"] = {k: parse_time(f"0:1{i},000")
                             for i, k in enumerate(qual.entrants[:6])}
    result = R.classify(qual, entries, comp)
    doc = D.race_classification(qual, result, entries, comp,
                                doc_kind=DOC_RESULTS)
    firsts = [r for r in doc.tables[0].rows if r.get("rank")]
    assert [i for i, r in enumerate(firsts)
            if "group-start-strong" in r.get("_class", "")] == [4]

    fin = R.ensure_state(ev, comp, "AL", "vel_squadre", "Finali", entries)
    assert DOC_RESULTS not in _default_notes(fin, comp, ev)


def test_a_dorsale_belongs_to_a_category(ev, entries, comp):
    """The bug this exists to stop: an AL sheet listing ES, ED and DA riders.

    Dorsali are handed out per category - number 2 is worn by four riders at
    these championships - and an individual race holds its startlist as bare
    numbers. Resolved across the whole competition, every line of every
    startlist came out four riders long, and a batteria sheet picked whichever
    rider the entry list happened to hold last.
    """
    from core.parse import parse_heats
    from ui.pages.races import _entrant_bibs

    shared = [b for b in {r.bib for r in entries.riders.values() if r.bib}
              if len({r.cat for r in entries.riders.values()
                      if r.bib == b}) > 1]
    assert shared, "the entry list must reuse a number across categories"
    bib = str(sorted(shared)[0])
    assert len(R.entrant_riders(bib, entries)) > 1          # every category
    for cat in ("ES", "AL"):
        got = R.entrant_riders(bib, entries, cat)
        assert len(got) == 1 and got[0].cat == cat

    # an individual startlist: one line per entrant, all of them AL
    state = R.ensure_state(ev, comp, "AL", "omnium", "Scratch", entries)
    rows = D.race_startlist(state, entries, comp).tables[0].rows
    assert len(rows) == len(state.entrants)
    assert {r["cat"] for r in rows} == {"AL"}

    # ...and one composed in batterie, where the bibs are read off the notation
    ts = R.ensure_state(ev, comp, "AL", "vel_squadre", "Qualificazioni", entries)
    ts.payload["heats"] = "/".join(
        ",".join(str(b) for b in _entrant_bibs(k, entries, "AL"))
        for k in ts.entrants)
    rows = D.race_startlist(ts, entries, comp,
                            heats=parse_heats(ts.payload["heats"])).tables[0].rows
    assert rows and {r["cat"] for r in rows} == {"AL"}


# ── what a sheet says, and about whom ───────────────────────────────────────

def test_a_sheet_is_written_about_the_riders_it_is_printed_for(comp):
    """"La prima atleta parte sul rettilineo d'arrivo" on a categoria femminile."""
    ip = comp.event("ins_individuale")
    assert ip.note().startswith("Il primo atleta parte")
    assert ip.note(female=True).startswith("La prima atleta parte")
    # only what changes has a second form: a squadra is feminine either way
    assert comp.event("ins_squadre").note(female=True) == \
        comp.event("ins_squadre").note()
    assert comp.female("DA") and comp.female("ED")
    assert not comp.female("AL") and not comp.female("ES")


def test_the_note_of_a_race_follows_its_category(ev, entries, comp):
    from core.config import DOC_STARTLIST
    from ui.pages.races import _note_field

    for cat, opening in (("AL", "Il primo atleta"), ("DA", "La prima atleta")):
        state = R.ensure_state(ev, comp, cat, "ins_individuale",
                               "Qualificazioni", entries)
        assert _note_field(state, comp, DOC_STARTLIST).startswith(opening)


# ── who is still not in the arrival ─────────────────────────────────────────

def test_a_bunch_race_says_who_is_not_in_the_arrival(ev, entries, comp):
    """The last volata is the arrival: whoever is not in it was not placed."""
    state = R.ensure_state(ev, comp, "ED", "omnium", "Scratch", entries)
    kind = state.fmt
    assert R.bunch_unplaced(state, entries, kind) == []   # nothing typed yet

    listed, missing = state.entrants[:-3], state.entrants[-3:]
    state.payload["sprints"] = ",".join(listed)
    assert R.bunch_unplaced(state, entries, kind) == [int(b) for b in missing]

    # a decision is a result: the jury took them out of the race itself
    R.set_status(state, missing[0], Status.DNF)
    R.set_status(state, missing[1], Status.DSQ)
    assert R.bunch_unplaced(state, entries, kind) == [int(missing[2])]

    state.payload["sprints"] = ",".join(state.entrants)
    assert R.bunch_unplaced(state, entries, kind) == []


def test_nothing_is_missing_while_the_race_is_still_on(ev, entries, comp):
    """Half the field is legitimately absent from the volata just called."""
    state = R.ensure_state(ev, comp, "ED", "omnium", "Corsa a Punti", entries)
    planned = state.n_sprint
    assert planned > 1

    four = ",".join(state.entrants[:4])
    state.payload["sprints"] = "-".join([four] * (planned - 1))
    assert R.bunch_unplaced(state, entries, state.fmt) == []
    # the last one closes the race: now the sheet has to place everybody
    state.payload["sprints"] = "-".join([four] * planned)
    assert len(R.bunch_unplaced(state, entries, state.fmt)) == \
        len(state.entrants) - 4


def test_an_eliminazione_says_it_through_pending(ev, entries, comp):
    """It has no volate: the riders still in it are counted one by one."""
    state = R.ensure_state(ev, comp, "ED", "omnium", "Eliminazione", entries)
    state.payload["eliminated"] = ",".join(state.entrants[:3])
    assert R.bunch_unplaced(state, entries, state.fmt) == []
    assert R.classify(state, entries, comp).pending == len(state.entrants) - 3


def test_zz_widths(madison, entries, comp, ev):
    b1 = R.ensure_state(madison, comp, "ES", "madison",
                        "Qualificazioni Batteria 1", entries)
    doc = D.race_classification(b1, R.classify(b1, entries, comp), entries,
                                comp, doc_kind="risultati")
    _zz("madison risultati", doc)
    st = R.ensure_state(ev, comp, "AL", "omnium", "Corsa a Punti", entries)
    st.payload["sprints"] = ",".join(st.entrants[:4])
    doc = D.race_classification(st, R.classify(st, entries, comp), entries,
                                comp, doc_kind="risultati", show_sprints=True)
    _zz("omnium corsa a punti", doc)
    doc = D.entry_list(entries, comp, "AL")
    _zz("elenco iscritti", doc)


def _zz(name, doc):
    for t in doc.tables:
        print("==", name, "font", t.font_size)
        for c in t.columns:
            print(f"   {c.key:12s} w={c.w:6.2f} pct={c.pct:6.2f} "
                  f"= {194 * c.pct / 100:5.1f}mm  head={c.label!r}")


# ── the mark of a prova against the clock ───────────────────────────────────

def test_the_time_column_of_a_team_event_is_centred_and_bold(ev, entries, comp):
    """On the velocità e l'inseguimento a squadre the time *is* the result.

    It is read down the column and not against the name beside it, so it prints
    centred and bold - on the risultati as on the classifica.
    """
    state = R.ensure_state(ev, comp, "AL", "vel_squadre", "Qualificazioni",
                           entries)
    keys = state.entrants[:2]
    state.payload["times"] = {k: parse_time(f"1:0{i},500")
                              for i, k in enumerate(keys)}
    result = R.classify(state, entries, comp)

    for doc_kind in (DOC_RESULTS, DOC_CLASSIFICATION):
        doc = D.race_classification(state, result, entries, comp,
                                    doc_kind=doc_kind)
        time = next(c for c in doc.tables[0].columns if c.key == "time")
        assert (time.align, time.bold) == ("c", True), doc_kind
