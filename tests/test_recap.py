"""The riepilogo per squadra: who of ours rides what, and in which batteria."""

from __future__ import annotations

import pytest

from core import recap as RC
from core.models import EntryList, EventEntry, Heat, RaceState, Rider
from render import documents as D
from render.render import to_html


@pytest.fixture
def el():
    """Two regioni, three riders, one of them a riserva in the madison."""
    riders = {}
    # a pair number is written as a letter: 1 is squadra A, and a reserve of it
    # prints AR (`EventEntry.flag`)
    for key, bib, cat, last, region, club, events in (
            ("a", 1, "AL", "ROSSI", "Emilia-Romagna", "GS Pippo",
             {"velocita": EventEntry(),
              "madison": EventEntry(pair=1)}),
            ("b", 2, "AL", "BIANCHI", "Emilia-Romagna", "GS Pluto",
             {"madison": EventEntry(starter=False, pair=1)}),
            ("c", 3, "ES", "VERDI", "Veneto", "GS Paperino",
             {"velocita": EventEntry()})):
        riders[key] = Rider(key=key, bib=bib, cat=cat, last_name=last,
                            first_name="Mario", region=region, club=club,
                            events=events)
    return EntryList(riders=riders)


# ── who a squadra is ────────────────────────────────────────────────────────

def test_the_squadre_are_the_regioni_or_the_societa(el):
    assert RC.teams(el) == ["Emilia-Romagna", "Veneto"]
    assert RC.teams(el, RC.BY_CLUB) == ["GS Paperino", "GS Pippo", "GS Pluto"]


def test_a_rider_without_one_is_not_a_squadra_of_their_own(el):
    """An untitled sheet helps nobody: the missing regione is a check-in finding."""
    el.riders["a"].region = ""
    assert RC.teams(el) == ["Emilia-Romagna", "Veneto"]  # b is still there
    el.riders["b"].region = ""
    assert RC.teams(el) == ["Veneto"]


def test_the_riders_of_a_squadra_come_by_bib_and_by_category(el):
    assert [r.key for r in RC.riders_of(el, "Emilia-Romagna")] == ["a", "b"]
    assert [r.key for r in RC.riders_of(el, "Emilia-Romagna", "ES")] == []
    assert [r.key for r in RC.riders_of(el, "GS Pippo", group=RC.BY_CLUB)] == ["a"]


def test_the_events_are_listed_in_the_order_of_the_programme(el, comp):
    codes = RC.events_of(el.riders["a"], comp)
    assert set(codes) == {"velocita", "madison"}
    assert codes == [c for c in comp.event_order() if c in codes]


# ── which batteria, where one has been composed ─────────────────────────────

def test_a_race_with_no_batterie_yet_places_nobody(store, comp):
    assert RC.heat_index(store, comp, EntryList()) == {}


def test_the_heats_of_a_bunch_race_are_read_from_the_state():
    state = RaceState(race_id="x", cat="AL", event="omnium",
                      heats=[Heat(number=1, entrants=["1", "2"]),
                             Heat(number=2, entrants=["3"])])
    assert RC.heats_of(state) == [(1, ["1", "2"]), (2, ["3"])]


def test_the_heats_of_a_velocita_are_read_from_the_bracket():
    # the bracket is held as the jury's own shorthand, not as a list
    state = RaceState(race_id="x", cat="AL", event="velocita",
                      payload={"heats": "1-8/2-7"})
    assert RC.heats_of(state) == [(1, ["1", "8"]), (2, ["2", "7"])]


def test_a_batteria_scheduled_as_a_round_of_its_own_is_that_batteria():
    """The inseguimento runs 'Qualificazioni Batteria 1' as a race in itself."""
    state = RaceState(race_id="x", cat="AL", event="ins_individuale",
                      round_key="Qualificazioni Batteria 3",
                      entrants=["1", "2"])
    assert RC.heats_of(state) == [(3, ["1", "2"])]


def test_an_empty_race_answers_nothing():
    assert RC.heats_of(RaceState(race_id="x", cat="AL", event="omnium")) == []


def test_the_index_keeps_the_first_round_that_places_a_rider(store, comp, el):
    """A squadra lines up in the first round; the later ones are not known yet."""
    cat, event = "AL", "velocita"
    rounds = [r.key for r in comp.rounds(cat, event)]
    assert len(rounds) > 1
    from core.race import race_key

    for rnd, heats in ((rounds[1], "9/1"), (rounds[0], "1-2/3")):
        store.save_race(RaceState(race_id=race_key(cat, event, rnd), cat=cat,
                                  event=event, round_key=rnd,
                                  payload={"heats": heats}))
    index = RC.heat_index(store, comp, el)
    assert index[(cat, event, "a")] == (rounds[0], 1)   # bib 1, first round


# ── the sheet ───────────────────────────────────────────────────────────────

def test_the_recap_names_the_squadra_and_keeps_it_on_one_table(el, comp):
    """Every categoria on the same grid: a manager reads one page, not four."""
    doc = D.team_recap(el, comp, "Emilia-Romagna")
    assert doc.title.startswith("Emilia-Romagna")
    assert "RIEPILOGO" in doc.title
    assert len(doc.tables) == 1
    assert "2 atleti" in doc.info


def test_the_events_are_columns_marked_X_or_by_pairing(el, comp):
    doc = D.team_recap(el, comp, "Emilia-Romagna", all_events=False)
    keys = [c.key for c in doc.tables[0].columns]
    assert keys[-2:] == ["ev_velocita", "ev_madison"]
    marks = {r["last_name"]: (r["ev_velocita"], r["ev_madison"])
             for r in doc.tables[0].rows}
    assert marks["ROSSI"] == ("X", "A")       # entered, coppia A
    assert marks["BIANCHI"] == ("", "AR")     # riserva of coppia A


def test_a_specialita_nobody_here_rides_gets_no_column(el, comp):
    doc = D.team_recap(el, comp, "Veneto", all_events=False)
    assert [c.key for c in doc.tables[0].columns][-1] == "ev_velocita"


def test_by_default_every_specialita_of_the_categorie_is_a_column(el, comp):
    """The blank grid: the sheet is what the specialità are collected on.

    It goes out before the verifica as often as after it, and a colleague with
    a pen needs the column of a specialità nobody has entered yet.
    """
    doc = D.team_recap(el, comp, "Veneto")
    keys = [c.key for c in doc.tables[0].columns if c.key.startswith("ev_")]
    assert set(keys) == {f"ev_{s}" for s in comp.events_for("ES")}
    assert len(keys) > 1                    # not just the velocita they ride
    # and in the order of the programme, like every other sheet
    assert keys == [f"ev_{s}" for s in comp.event_order() if f"ev_{s}" in keys]
    assert doc.tables[0].rows[0]["ev_velocita"] == "X"


def test_the_column_heads_are_abbreviated_and_keyed_under_the_table(el, comp):
    doc = D.team_recap(el, comp, "Emilia-Romagna", all_events=False)
    heads = [c.label for c in doc.tables[0].columns][-2:]
    assert all(len(h) <= 6 for h in heads)
    for head in heads:
        assert head in doc.legend
    assert comp.event("madison").short in doc.legend


def test_the_short_names_can_head_the_columns_instead_of_the_sigle(el, comp):
    """«Madison» over the column instead of «MD» keyed under the table.

    The sigla is right where a dozen specialità have to fit; a manager reading
    their own squadra would rather not look anything up.
    """
    doc = D.team_recap(el, comp, "Emilia-Romagna", short_headers=True,
                       all_events=False)
    heads = [c.label for c in doc.tables[0].columns][-2:]
    assert heads == [comp.event("velocita").short, comp.event("madison").short]
    # nothing to key any more, but what the caselle say is still explained
    assert comp.event("madison").abbr not in doc.legend
    assert "X iscritto" in doc.legend
    # and the head is what has to fit: the columns are wider than the marks
    abbr = D.team_recap(el, comp, "Emilia-Romagna", all_events=False)
    assert (next(c.pct for c in doc.tables[0].columns if c.key == "ev_madison")
            > next(c.pct for c in abbr.tables[0].columns
                   if c.key == "ev_madison"))


def test_a_composed_batteria_follows_the_mark(el, comp):
    heats = {("AL", "velocita", "a"): ("Qualificazioni", 2)}
    doc = D.team_recap(el, comp, "Emilia-Romagna", heats=heats)
    assert doc.tables[0].rows[0]["ev_velocita"] == "X 2"


def test_grouping_by_club_prints_the_regione_instead(el, comp):
    """The squadra is the title: the column that names it would repeat it."""
    by_region = D.team_recap(el, comp, "Emilia-Romagna", show_tail=True)
    by_club = D.team_recap(el, comp, "GS Pippo", group=RC.BY_CLUB,
                           show_tail=True)
    tail = [c.key for c in by_region.tables[0].columns
            if not c.key.startswith("ev_")][-1]
    tail_club = [c.key for c in by_club.tables[0].columns
                 if not c.key.startswith("ev_")][-1]
    assert (tail, tail_club) == ("club", "region")


def test_a_squadra_with_nobody_in_it_prints_no_table(el, comp):
    doc = D.team_recap(el, comp, "Piemonte")
    assert doc.tables == [] and "0 atleti" in doc.info


def test_the_societa_is_off_by_default_and_the_uci_id_on(el, comp):
    """The squadra is the title; what a manager checks is the UCI ID."""
    doc = D.team_recap(el, comp, "Emilia-Romagna")
    keys = [c.key for c in doc.tables[0].columns]
    assert "club" not in keys and "uci_id" in keys
    keys = [c.key for c in D.team_recap(el, comp, "Emilia-Romagna",
                                        show_tail=True,
                                        uci_id=False).tables[0].columns]
    assert "club" in keys and "uci_id" not in keys


def test_a_rule_is_drawn_where_the_categoria_changes(el, comp):
    """Four categorie on one grid read as four blocks, not as one list."""
    el.riders["b"].cat = "ES"
    doc = D.team_recap(el, comp, "Emilia-Romagna")
    rows = doc.tables[0].rows
    ruled = [r["last_name"] for r in rows
             if "section-start" in r.get("_class", "")]
    # the rule opens the second categoria, and nothing is ruled off above the
    # first rider on the sheet
    assert ruled == [rows[1]["last_name"]]
    assert rows[0]["cat"] != rows[1]["cat"]
    plain = D.team_recap(el, comp, "Emilia-Romagna", rule_categories=False)
    assert not any("section-start" in r.get("_class", "")
                   for r in plain.tables[0].rows)


def test_the_recap_renders(el, comp):
    doc = D.team_recap(el, comp, "Emilia-Romagna", show_tail=True,
                       heats={("AL", "velocita", "a"): ("Qualificazioni", 2)})
    html = to_html(doc, comp)
    assert "Emilia-Romagna" in html and "X 2" in html
    assert "GS Pippo" in html


# ── the tabella specialità ──────────────────────────────────────────────────

def test_the_speciality_table_counts_a_category_across_the_programme(el, comp):
    rows, total = RC.speciality_table(el, comp)

    assert [r.cat for r in rows] == comp.cat_order()
    al = next(r for r in rows if r.cat == "AL")
    # verified is "has a specialità": both AL riders are entered in one
    assert (al.entries, al.checked_in, al.missing) == (2, 2, 0)
    assert al.per_event["velocita"] == 1
    # starters, as every other count of an event is: the second AL rider is the
    # riserva of that coppia, and a riserva does not line up
    assert al.per_event["madison"] == 1
    assert total.entries == 3 and total.per_event["velocita"] == 2


def test_a_category_that_does_not_contest_an_event_has_no_number(el, comp):
    """Blank, not zero: a zero reads as 'nobody entered', which is different."""
    rows, _total = RC.speciality_table(el, comp)
    es = next(r for r in rows if r.cat == "ES")
    assert es.per_event["keirin"] is RC.NOT_CONTESTED
    assert "keirin" not in comp.events_for("ES")
    assert es.per_event["velocita"] == 1


def test_the_speciality_table_prints(el, comp):
    doc = D.speciality_table(el, comp)
    html = to_html(doc, comp)
    assert "TABELLA SPECIALITÀ" in html
    # every categoria, then the totals line
    for cat in comp.cat_order():
        assert f">{cat}<" in html
    assert "Totale" in html
    # the sigle of the specialità are keyed under the table
    assert "SP = Velocità" in html


def test_the_speciality_table_can_be_headed_by_the_short_names(el, comp):
    doc = D.speciality_table(el, comp, short_headers=True)
    html = to_html(doc, comp)
    assert comp.event("velocita").short in html
    # the head says it: there is no key left to print
    assert "SP = Velocità" not in html and doc.legend == ""
