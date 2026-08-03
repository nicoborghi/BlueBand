from core.config import (DOC_ALL_KINDS, Competition, laps_from_distance,
                         sprints_from_laps, validate)


def test_programme_is_valid(comp):
    assert validate(comp) == []
    assert comp.short == "CITA26"
    assert comp.track_len == 0.33333


def test_categories_and_specialities(comp):
    assert comp.cat_order() == ["ES", "ED", "AL", "DA"]
    assert comp.cat("AL").name == "UOMINI ALLIEVI"
    # Esordienti contest three titles, Allievi seven (comunicato STP 016/2026)
    assert set(comp.events_for("ES")) == {"madison", "velocita", "omnium"}
    assert set(comp.events_for("ED")) == {"madison", "velocita", "omnium"}
    assert len(set(comp.events_for("AL"))) == 7
    assert len(set(comp.events_for("DA"))) == 7


def test_event_abbreviations(comp):
    """Sigle UCI: declared in the programme, derived when they are not."""
    from core.config import Competition, Event

    assert comp.event("ins_squadre").abbr == "TP"
    assert comp.event("madison").abbr == "MD"
    events = [s for s in comp.event_order() if s != "entry_list"]
    assert list(comp.event_headers(events, abbr=True).values()) == \
        ["TS", "TP", "OM", "SP", "KE", "IP", "MD"]
    assert comp.event_headers(["omnium"])["omnium"] == "Omnium"

    # not declared: the format decides, and colliding sigle keep the full name
    c = Competition(events={
        "a": Event(code="a", short="Corsa a Punti", fmt="group"),
        "b": Event(code="b", short="Scratch", fmt="group"),
    })
    assert c.event("a").abbr == "PR"
    assert c.event_headers(["a", "b"], abbr=True) == {"a": "Corsa a Punti",
                                                      "b": "Scratch"}


def test_distances_come_from_the_workbooks(comp):
    # ES madison qualificazioni is 8 km / 25 giri, NOT the 24 giri the track
    # length would imply - explicit programme values must win.
    assert comp.distances("ES", "madison",
                          "Qualificazioni Batteria 1") == (8.0, 25.0, 5)
    assert comp.distances("AL", "madison", "Finale") == (20.0, 60.0, 12)
    assert comp.distances("AL", "omnium", "Corsa a Punti") == (15.0, 45.0, 9)
    assert comp.distances("DA", "ins_individuale", "Qualificazioni") == (2.0, 6.0, 0)
    assert comp.distances("AL", "ins_squadre", "Finali") == (3.0, 9.0, 0)


def test_defaults_derived_from_track_length():
    # 3 km on a 333 m track = 9 laps; timed competitions keep half-lap resolution.
    # A nominal 0.33333 must not push these up to 9.5 / 2.0(old track.py bug).
    assert laps_from_distance(3, 0.33333, "timed") == 9.0
    assert laps_from_distance(0.5, 0.33333, "timed") == 1.5
    assert laps_from_distance(4, 0.25, "timed") == 16.0
    assert laps_from_distance(1.1, 0.25, "timed") == 4.5  # rounds up, not to 4
    assert laps_from_distance(12, 0.33333, "group") == 36
    assert sprints_from_laps(36, "points") == 6
    assert sprints_from_laps(15, "tempo") == 11
    assert sprints_from_laps(15, "scratch") == 1


def test_comunicato_register(comp):
    """The register is the 2026 numbering, verified against the jury workbooks."""
    assert len(comp.communiques) == 138
    by_n = {c.n: c for c in comp.communiques}
    assert [c.n for c in comp.communiques] == list(range(1, 139))

    assert by_n[1].title == "Iscritti ES"
    assert (by_n[5].cat, by_n[5].event, by_n[5].doc) == ("ES", "madison", "partenti")
    assert by_n[7].round_key == "Qualificazioni"  # AL Ins. Squadre StartList_Qual
    assert by_n[30].doc == "classifica"  # AL Ins. Squadre classifica
    assert by_n[92].ret and by_n[92].label == "92 RET"
    assert by_n[93].title.startswith("AL Omnium Qualificazioni Batteria 2")
    assert (by_n[138].cat, by_n[138].event) == ("DA", "madison")

    # every entry resolves to a known category and event
    for c in comp.communiques:
        assert c.cat in comp.categories, c
        assert c.event in comp.events, c
        assert c.doc in DOC_ALL_KINDS, c


def test_days(comp):
    assert comp.days() == [1, 2, 3, 4]
    per_day = {d: sum(1 for c in comp.communiques if c.day == d) for d in comp.days()}
    assert per_day == {1: 32, 2: 55, 3: 33, 4: 18}


# ── what a squadra is, at this competition ──────────────────────────────────

def test_the_programme_says_what_a_squadra_is(comp):
    """A campionato italiano is ridden by rappresentative regionali."""
    assert comp.team_group == "region"
    assert comp.team_name == "Squadra"


def test_an_unknown_grouping_falls_back_instead_of_grouping_by_nothing():
    from dataclasses import replace
    from core.config import EntrySheet

    odd = replace(Competition(), entry_sheet=EntrySheet(team_group="sponsor"))
    assert odd.team_group == "region"


def test_the_word_printed_for_a_squadra_is_the_one_chosen():
    """`team` and `team_en` are the same word: the sheets said Squadra / Team."""
    from dataclasses import replace
    from core import i18n as I
    from core.config import EntrySheet

    club = replace(Competition(), entry_sheet=EntrySheet(team_group="club",
                                                         team_name="Società"))
    assert (club.team_group, club.team_name) == ("club", "Società")
    try:
        I.set_overrides({"team": club.team_name, "team_en": club.team_name})
        assert I.label("team") == I.label("team_en") == "Società"
    finally:
        I.set_overrides({})
    assert (I.label("team"), I.label("team_en")) == ("Squadra", "Team")
