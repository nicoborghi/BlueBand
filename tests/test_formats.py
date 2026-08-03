"""Race-format tests, including results transcribed from the jury workbooks."""

from core.formats.group import (POINTS, SCRATCH, TEMPO,
                                elimination_classification, group_classification)
from core.formats.timed import (final_label, finals_classification,
                                seed_finals, seed_finals_text,
                                timed_classification)
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
    assert {p.key: p.data["total"] for p in r.placings}["2"] == 0


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
    r = elimination_classification(startlist=[1, 2, 3, 4, 5],
                                   eliminated=[5, 4, 3, 2])
    assert order(r) == ["1", "2", "3", "4", "5"]
    assert labels(r) == ["1°", "2°", "3°", "4°", "5°"]


def test_elimination_in_progress_leaves_the_leaders_blank():
    r = elimination_classification(startlist=[1, 2, 3, 4, 5], eliminated=[5, 4])
    assert r.pending == 3
    assert order(r) == ["1", "2", "3", "4", "5"]
    assert labels(r) == ["", "", "", "4°", "5°"]


def test_elimination_ignores_riders_who_did_not_start():
    r = elimination_classification(startlist=[1, 2, 3, 4],
                                   eliminated=[4, 3],
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
