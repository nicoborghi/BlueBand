"""Race-format tests, including results transcribed from the jury workbooks."""

from core.formats.group import (POINTS, SCRATCH, TEMPO,
                                elimination_classification, group_classification)
from core.formats.timed import (final_label, final_places,
                                finals_classification, seed_finals,
                                seed_finals_text, timed_classification)
from core.models import Status
from core.parse import parse_time


def order(result):
    return [p.key for p in result.placings]


def labels(result):
    return [p.label for p in result.placings]


# ── corsa a punti ───────────────────────────────────────────────────────────

def test_points_race_scoring():
    """5-3-2-1 per sprint, 10-6-4-2 in the last one."""
    r = group_classification(
        startlist=[1, 2, 3, 4, 5],
        sprints=[[1, 2, 3, 4], [2, 1, 3, 4]],
        scoring=POINTS, n_sprint=2)
    pts = {p.key: p.data["total"] for p in r.placings}
    assert pts["1"] == 5 + 6      # 1st then 2nd in the double-points sprint
    assert pts["2"] == 3 + 10
    assert pts["3"] == 2 + 4
    assert pts["4"] == 1 + 2
    assert pts["5"] == 0
    assert order(r) == ["2", "1", "3", "4", "5"]
    assert labels(r)[:2] == ["1°", "2°"]


def test_points_race_laps_are_worth_20():
    r = group_classification(startlist=[1, 2, 3, 4],
                             sprints=[[1, 2, 3, 4]],
                             scoring=POINTS, n_sprint=1, laps_gained=[4],
                             laps_lost=[1])
    pts = {p.key: p.data["total"] for p in r.placings}
    assert pts["4"] == 2 + 20         # last-sprint points + a lap gained
    assert pts["1"] == 10 - 20
    assert order(r)[0] == "4"
    assert order(r)[-1] == "1"


def test_points_race_ties_broken_by_last_sprint():
    r = group_classification(startlist=[1, 2, 3, 4],
                             sprints=[[1, 2, 3, 4], [2, 1, 3, 4]],
                             scoring=POINTS, n_sprint=2)
    # 1 and 2 both on 11; rider 2 won the final sprint
    assert {p.key: p.data["total"] for p in r.placings}["1"] == 11
    assert {p.key: p.data["total"] for p in r.placings}["2"] == 13
    r2 = group_classification(startlist=[1, 2], sprints=[[1, 2], [2, 1]],
                              scoring=POINTS, n_sprint=2)
    assert order(r2) == ["2", "1"]


def test_only_the_last_sprint_breaks_a_tie():
    """Chi all'ultima volata non e' passato non ha un piazzamento da opporre.

    La giuria batte i quattro che fanno punti, non tutto il gruppo: tenere il
    piazzamento dell'ultima volata in cui il corridore compariva confrontava
    una volata con un'altra, e faceva precedere chi all'ultima non era passato
    davanti a chi ci era passato quarto.
    """
    # #5 vince la prima volata (5 punti) e all'ultima non passa; #6 e' 2o nella
    # prima (3) e 4o nell'ultima, doppia (2): pari a 5, ma #6 ha il passaggio
    r = group_classification(startlist=[1, 2, 3, 4, 5, 6],
                             sprints=[[5, 6, 3, 4], [1, 2, 3, 6]],
                             scoring=POINTS, n_sprint=2)
    pts = {p.key: p.data["total"] for p in r.placings}
    assert pts["5"] == pts["6"] == 5
    assert order(r).index("6") < order(r).index("5")


def test_points_race_warns_on_short_sprint_and_unknown_bib():
    r = group_classification(startlist=[1, 2, 3, 4], sprints=[[1, 2], [1, 2, 3, 9]],
                             scoring=POINTS, n_sprint=2)
    assert any("almeno 4" in w for w in r.warnings)
    assert any("9" in w and "partenti" in w for w in r.warnings)


def test_duplicate_bib_in_a_sprint_is_flagged():
    r = group_classification(startlist=[1, 2, 3, 4], sprints=[[1, 1, 2, 3]],
                             scoring=POINTS, n_sprint=1)
    assert any("ripetuto" in w for w in r.warnings)


# ── tempo race / scratch ────────────────────────────────────────────────────

def test_tempo_race_gives_one_point_to_each_sprint_winner():
    r = group_classification(startlist=[1, 2, 3],
                             sprints=[[1, 2, 3], [2, 1, 3], [1, 3, 2]],
                             scoring=TEMPO, n_sprint=3)
    pts = {p.key: p.data["total"] for p in r.placings}
    assert pts == {"1": 2, "2": 1, "3": 0}
    assert order(r) == ["1", "2", "3"]


def test_scratch_is_the_finishing_order():
    r = group_classification(startlist=[1, 2, 3, 4], sprints=[[3, 1, 4, 2]],
                             scoring=SCRATCH, n_sprint=1)
    assert order(r) == ["3", "1", "4", "2"]
    assert labels(r) == ["1°", "2°", "3°", "4°"]
    assert r.columns == []


# ── statuses ────────────────────────────────────────────────────────────────

def test_dnf_dns_dsq_are_ranked_after_the_classified():
    r = group_classification(
        startlist=[1, 2, 3, 4, 5],
        sprints=[[1, 2, 3, 4]], scoring=POINTS, n_sprint=1,
        statuses={"2": Status.DNF, "3": Status.DNS, "5": Status.DSQ})
    assert order(r)[0] == "1"
    assert labels(r)[-3:] == ["DNF", "DNS", "DSQ"]
    assert [p.key for p in r.placings if p.status is Status.OK] == ["1", "4"]
    # a ritirata keeps the points she scored before she left: she rode those
    # volate, and a zero next to the DNF would say she scored nothing
    assert {p.key: p.data["total"] for p in r.placings}["2"] == 6


def test_the_riders_who_left_are_ranked_by_when_they_left():
    """DNF and ABD in reverse order of entry: the last to leave heads them.

    And a scesa prints no points at all - she came down of her own accord -
    while a ritirata keeps hers.
    """
    r = group_classification(
        startlist=[1, 2, 3, 4, 5, 6],
        sprints=[[2, 3, 4, 5]], scoring=POINTS, n_sprint=1,
        statuses={"2": Status.DNF, "3": Status.DNF,
                  "4": Status.ABD, "5": Status.ABD})
    assert order(r) == ["1", "6", "3", "2", "5", "4"]
    points = {p.key: p.data["total"] for p in r.placings}
    assert points["2"] == 10 and points["3"] == 6     # DNF: kept
    assert points["4"] == 0 and points["5"] == 0      # ABD: hidden
    assert all(v == 0 for v in r.by_key("4").data["sprints"])


def test_relegated_rider_is_classified_last():
    """REL is classified - unlike DNF it keeps a place, at the back."""
    r = group_classification(startlist=[1, 2, 3], sprints=[[1, 2, 3]],
                             scoring=POINTS, n_sprint=1,
                             statuses={"1": Status.REL})
    assert order(r) == ["2", "3", "1"]
    assert labels(r) == ["1°", "2°", "3° REL"]
    assert r.by_key("1").position == 3


# ── eliminazione ────────────────────────────────────────────────────────────

def test_elimination_first_out_is_last():
    """The winner is the last number typed, and it is typed like the others."""
    r = elimination_classification(startlist=[1, 2, 3, 4, 5],
                                   eliminated=[5, 4, 3, 2, 1])
    assert order(r) == ["1", "2", "3", "4", "5"]
    assert labels(r) == ["1°", "2°", "3°", "4°", "5°"]
    assert not r.pending


def test_elimination_never_wins_a_race_for_a_rider_nobody_typed():
    """The last one left is the winner of the race: the app does not decide
    that on its own, whether the number is missing because the segreteria has
    not written it down yet or because it should not be in the race at all."""
    r = elimination_classification(startlist=[1, 2, 3, 4, 5],
                                   eliminated=[5, 4, 3, 2])
    assert r.by_key("1").label == "" and r.pending == 1
    assert labels(r) == ["", "2°", "3°", "4°", "5°"]


def test_elimination_in_progress_leaves_the_leaders_blank():
    r = elimination_classification(startlist=[1, 2, 3, 4, 5], eliminated=[5, 4])
    assert r.pending == 3
    assert order(r) == ["1", "2", "3", "4", "5"]
    assert labels(r) == ["", "", "", "4°", "5°"]


def test_elimination_ignores_riders_who_did_not_start():
    r = elimination_classification(startlist=[1, 2, 3, 4],
                                   eliminated=[4, 3, 1],
                                   statuses={"2": Status.DNS})
    # only three riders are classified, so the first eliminated is 3rd
    assert r.by_key("4").label == "3°"
    assert r.by_key("3").label == "2°"
    assert r.by_key("1").label == "1°"
    assert r.by_key("2").label == "DNS"


def test_elimination_flags_duplicates():
    r = elimination_classification(startlist=[1, 2, 3], eliminated=[3, 3])
    assert any("due volte" in w for w in r.warnings)


# ── timed races ─────────────────────────────────────────────────────────────

def test_team_pursuit_qualification_matches_the_workbook():
    """AL Inseguimento a Squadre, qualificazioni (comunicato 15)."""
    times = {
        "LOMBARDIA B": parse_time("03:31,370"),
        "VENETO A": parse_time("03:34,050"),
    }
    r = timed_classification(list(times), times)
    assert order(r) == ["LOMBARDIA B", "VENETO A"]
    assert labels(r) == ["1°", "2°"]
    assert r.by_key("LOMBARDIA B").data["time"] == 211370


def test_team_sprint_qualification_matches_the_workbook():
    """AL Velocità a Squadre (comunicato 21) - sub-minute times."""
    times = {"LOMBARDIA": parse_time("00:34,670"),
             "EMILIA ROMAGNA": parse_time("00:34,750")}
    r = timed_classification(list(times), times)
    assert order(r) == ["LOMBARDIA", "EMILIA ROMAGNA"]


def test_individual_pursuit_qualification_matches_the_workbook():
    """AL Inseguimento Individuale (comunicato 129)."""
    times = {"CECCARELLO": parse_time("03:36,962"),
             "LONGO": parse_time("03:37,873")}
    r = timed_classification(list(times), times)
    assert order(r) == ["CECCARELLO", "LONGO"]


def test_entrants_without_a_time_stay_pending():
    r = timed_classification(["A", "B", "C"], {"A": 1000, "C": 900})
    assert r.pending == 1
    assert order(r) == ["C", "A", "B"]
    assert labels(r) == ["1°", "2°", ""]


def test_who_is_still_to_go_is_listed_in_start_order():
    """Half a classifica, half the list of who is still on the line.

    The dorsali say nothing while a chilometro is being ridden: what the jury
    reads down the bottom of the sheet is who starts next, so the ones without
    a time follow the grid (`race.start_order`) and not the entry order.
    """
    entrants = ["1", "2", "3", "4", "5"]
    r = timed_classification(entrants, {"3": 900},
                             order=["5", "3", "1", "4", "2"])
    assert order(r) == ["3", "5", "1", "4", "2"]

    # a squadra the grid does not place keeps the entry order, at the bottom
    r = timed_classification(entrants, {}, order=["4", "2"])
    assert order(r) == ["4", "2", "1", "3", "5"]

    # and with no grid composed at all nothing moves
    assert order(timed_classification(entrants, {})) == entrants


def test_timed_statuses():
    r = timed_classification(["A", "B", "C"], {"A": 1000, "B": 900},
                             statuses={"C": Status.DNS})
    assert labels(r) == ["1°", "2°", "DNS"]
    assert order(r) == ["B", "A", "C"]


# ── finals seeding ──────────────────────────────────────────────────────────

def test_the_3_4_final_rides_first():
    ranking = ["Q1", "Q2", "Q3", "Q4"]
    assert seed_finals(ranking) == [["Q3", "Q4"], ["Q1", "Q2"]]
    assert final_label(3) == "3°/4°" and final_label(1) == "1°/2°"


def test_seed_finals_text_for_teams():
    ranking = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]]
    assert seed_finals_text(ranking) == \
        "9,10,11,12-13,14,15,16/1,2,3,4-5,6,7,8"


def test_seed_finals_with_fewer_than_four_qualified():
    assert seed_finals(["A", "B"]) == [["A", "B"]]


def test_each_final_rides_for_its_own_places():
    """The 3/4 final cannot promote anyone: it decides 3rd and 4th."""
    ranking = ["Q1", "Q2", "Q3", "Q4"]
    heats = seed_finals(ranking)
    times = {"Q1": 212000, "Q2": 211000, "Q3": 210000, "Q4": 213000}
    r = finals_classification(heats, times, qualification=ranking)
    assert order(r) == ["Q2", "Q1", "Q3", "Q4"]
    assert labels(r) == ["1°", "2°", "3°", "4°"]
    # the fastest time of the day was ridden in the 3/4 final and stays third
    assert r.placings[2].data["time"] == 210000


def test_finals_keep_the_qualifying_order_and_times_below():
    r = finals_classification([["Q1", "Q2"]], {"Q1": 100, "Q2": 200},
                              qualification=["Q1", "Q2", "Q3", "Q4"],
                              qual_times={"Q3": 900, "Q4": 950})
    assert order(r) == ["Q1", "Q2", "Q3", "Q4"]
    assert labels(r) == ["1°", "2°", "3°", "4°"]
    assert [p.data["time"] for p in r.placings] == [100, 200, 900, 950]


def test_the_final_classification_files_the_qualifying_decisions():
    """A squadra DSQ in the qualification is on the classifica, with its DSQ.

    It never rode a final and has no place, but the classification of the
    specialità is where the decision is filed: leaving it off the sheet says
    the squadra was never at the meeting.
    """
    r = finals_classification([["Q1", "Q2"]], {"Q1": 100, "Q2": 200},
                              qualification=["Q1", "Q2", "Q3"],
                              qual_times={"Q3": 900, "X": 880, "Y": 870},
                              qual_out={"X": Status.DSQ, "Y": Status.DNS})
    # non-classified in the order of always (models.STATUS_ORDER): DNS, DSQ
    assert order(r) == ["Q1", "Q2", "Q3", "Y", "X"]
    assert labels(r) == ["1°", "2°", "3°", "DNS", "DSQ"]
    assert [p.position for p in r.placings[3:]] == [None, None]


def test_a_final_lost_on_a_decision_is_won_by_the_other_team():
    """Squalificata in the 1/2 final: the other squadra is first, not second."""
    ranking = ["Q1", "Q2", "Q3", "Q4"]
    r = finals_classification(seed_finals(ranking),
                              {"Q1": 211000, "Q2": 212000,
                               "Q3": 210000, "Q4": 213000},
                              statuses={"Q1": Status.DSQ},
                              qualification=ranking)
    assert order(r) == ["Q2", "Q3", "Q4", "Q1"]
    assert labels(r) == ["1°", "2°", "3°", "DSQ"]


# ── finali a pari merito ────────────────────────────────────────────────────

def test_the_1_2_final_left_a_pari_merito_gives_two_seconds():
    """Finale non disputata: nobody is first, the two finalists are both 2°."""
    ranking = ["Q1", "Q2", "Q3", "Q4"]
    r = finals_classification(seed_finals(ranking),
                              {"Q3": 210000, "Q4": 213000},
                              qualification=ranking, tied=[1])
    assert order(r) == ["Q1", "Q2", "Q3", "Q4"]
    assert labels(r) == ["2°", "2°", "3°", "4°"]
    assert [p.position for p in r.placings] == [2, 2, 3, 4]


def test_the_3_4_final_left_a_pari_merito_does_not_move_the_1_2():
    ranking = ["Q1", "Q2", "Q3", "Q4"]
    r = finals_classification(seed_finals(ranking),
                              {"Q1": 212000, "Q2": 211000},
                              qualification=ranking, tied=[3])
    assert order(r) == ["Q2", "Q1", "Q3", "Q4"]
    assert labels(r) == ["1°", "2°", "4°", "4°"]


def test_both_finals_a_pari_merito_keep_the_places_below_intact():
    """Two finals unridden: 2°, 2°, 4°, 4° - and the fifth is still fifth."""
    ranking = ["Q1", "Q2", "Q3", "Q4", "Q5"]
    r = finals_classification(seed_finals(ranking), {},
                              qualification=ranking,
                              qual_times={"Q5": 220000}, tied=[1, 3])
    assert labels(r) == ["2°", "2°", "4°", "4°", "5°"]
    assert [p.position for p in r.placings] == [2, 2, 4, 4, 5]
    # a final that will not be ridden is not a time still to come
    assert r.pending == 0


def test_a_pari_merito_final_with_one_team_squalificata():
    """One of the two is out: the other keeps the place alone, and 4th is 4th."""
    ranking = ["Q1", "Q2", "Q3", "Q4"]
    r = finals_classification(seed_finals(ranking),
                              {"Q1": 212000, "Q2": 211000},
                              statuses={"Q4": Status.DSQ},
                              qualification=ranking, tied=[3])
    assert order(r) == ["Q2", "Q1", "Q3", "Q4"]
    assert labels(r) == ["1°", "2°", "3°", "DSQ"]


def test_final_places_fall_back_on_the_order_the_finals_are_ridden():
    ranking = ["Q1", "Q2", "Q3", "Q4"]
    assert final_places(seed_finals(ranking), ranking) == [3, 1]
    assert final_places([["A", "B"], ["C", "D"]], []) == [1, 3]


def test_a_final_closed_on_the_qualifying_times_still_has_a_winner():
    """Non disputata, ma decisa: the qualifying time places the two."""
    ranking = ["Q1", "Q2", "Q3", "Q4"]
    quali = {"Q1": 211000, "Q2": 210000, "Q3": 213000, "Q4": 212000}
    r = finals_classification(seed_finals(ranking), {}, qualification=ranking,
                              qual_times=quali, on_qual=[1, 3])
    # Q2 qualified faster than Q1 and Q4 faster than Q3
    assert order(r) == ["Q2", "Q1", "Q4", "Q3"]
    assert labels(r) == ["1°", "2°", "3°", "4°"]
    # the time on the sheet is the one they rode - the qualifying one
    assert [p.data["time"] for p in r.placings] == [210000, 211000,
                                                    212000, 213000]
    assert r.pending == 0


def test_one_final_ridden_and_the_other_on_the_qualifying_times():
    ranking = ["Q1", "Q2", "Q3", "Q4"]
    quali = {"Q1": 211000, "Q2": 210000, "Q3": 213000, "Q4": 212000}
    r = finals_classification(seed_finals(ranking),
                              {"Q1": 209000, "Q2": 209500},
                              qualification=ranking, qual_times=quali,
                              on_qual=[3])
    assert order(r) == ["Q1", "Q2", "Q4", "Q3"]
    assert labels(r) == ["1°", "2°", "3°", "4°"]
    assert r.placings[0].data["time"] == 209000     # ridden: the final's time
    assert r.placings[2].data["time"] == 212000     # not ridden: qualifying


def test_a_pari_merito_final_carries_no_time_at_all():
    """Nothing was ridden for that place: the Tempo column stays empty."""
    ranking = ["Q1", "Q2", "Q3", "Q4"]
    r = finals_classification(seed_finals(ranking),
                              {"Q1": 209000, "Q2": 209500},
                              qualification=ranking,
                              qual_times={"Q1": 211000, "Q2": 210000},
                              tied=[1])
    assert labels(r)[:2] == ["2°", "2°"]
    assert [p.position for p in r.placings][:2] == [2, 2]
    # neither the qualifying time nor anything typed in the finals
    assert [p.data["time"] for p in r.placings][:2] == [None, None]
    # even a pari merito the sheet reads in qualifying order
    assert order(r)[:2] == ["Q2", "Q1"]
