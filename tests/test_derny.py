"""The derny lap chart: the columns, the lost laps, the standings, the times."""

import pytest

from core.formats import derny as DY
from core.models import Status


def call(*rows):
    """`call((5, 0), (3, 1))` -> the log the judge would have produced."""
    return [{"bib": b, "at": float(t)} for b, t in rows]


def lap(bibs, t0=0.0, step=1.0):
    return [(b, t0 + i * step) for i, b in enumerate(bibs)]


# ── the columns ─────────────────────────────────────────────────────────────

def test_a_new_column_opens_when_the_head_comes_round():
    log = call(*lap([5, 3, 7], 0), *lap([5, 3, 7], 10))
    b = DY.board(log)
    assert b.columns == [[5, 3, 7], [5, 3, 7]]
    assert b.leader_laps == 2


def test_a_column_opens_on_whoever_repeats_not_only_on_the_leader():
    # the head changed: 3 is first through now, and the lap still cuts
    log = call(*lap([5, 3, 7], 0), *lap([3, 5, 7], 10))
    assert DY.board(log).columns == [[5, 3, 7], [3, 5, 7]]


def test_an_empty_call_is_an_empty_chart():
    b = DY.board([])
    assert (b.columns, b.order, b.leader_laps) == ([], [], 0)


# ── the lap lost ────────────────────────────────────────────────────────────

def test_the_column_a_rider_comes_back_in_is_the_one_marked_late():
    log = call(*lap([5, 3, 9], 0), *lap([5, 3], 10), *lap([5, 3, 9], 20))
    # grey in the column he missed, red in the one he reappears in
    assert DY.board(log).late == {(9, 2)}


def test_nobody_is_late_while_everybody_is_on_the_same_lap():
    assert DY.board(call(*lap([5, 3], 0), *lap([5, 3], 10))).late == set()


def test_a_rider_lapped_is_printed_in_red_in_the_lap_he_did_not_ride():
    # 9 misses the second column and shows up again in the third
    log = call(*lap([5, 3, 9], 0), *lap([5, 3], 10), *lap([5, 3, 9], 20))
    b = DY.board(log)
    assert b.columns == [[5, 3, 9], [5, 3], [5, 3, 9]]
    assert b.lost == [[], [9], []]
    assert b.down == {5: 0, 3: 0, 9: 1}
    assert b.laps[9] == 2          # two laps ridden while the head did three


def test_two_laps_lost_in_a_row_are_two_marks_and_two_asterisks():
    log = call(*lap([5, 9], 0), *lap([5], 10), *lap([5], 20), *lap([5, 9], 30))
    b = DY.board(log)
    assert b.lost == [[], [9], [9], []]
    assert b.down[9] == 2


def test_a_lap_is_lost_as_soon_as_the_head_cuts_one_without_him():
    """He does not have to reappear for the giro to be gone.

    The head comes round again and he is not in the column: the lap went there
    and then, and that is when the jury has to know it. Only the column now
    open is not counted - he may still be coming through it.
    """
    log = call(*lap([5, 9], 0), *lap([5], 10), *lap([5], 20))
    b = DY.board(log)
    assert b.lost == [[], [9], []]      # the closed one, not the open one
    assert b.down[9] == 1


# ── the standings ───────────────────────────────────────────────────────────

def test_full_laps_first_then_the_lapped_in_the_order_they_passed():
    log = call(*lap([5, 3, 9], 0), *lap([5, 3], 10), *lap([5, 3, 9], 20))
    assert DY.board(log).order == [5, 3, 9]


def test_a_rider_not_yet_through_this_lap_is_not_a_rider_a_lap_down():
    # 7 has not been called in the column now open: he is still behind 5 and 3,
    # and still on the same lap as them
    log = call(*lap([5, 3, 7], 0), *lap([5, 3], 10))
    b = DY.board(log)
    assert b.order == [5, 3, 7]
    assert b.down[7] == 0


# ── the lap times ───────────────────────────────────────────────────────────

def test_lap_times_are_the_gaps_between_one_call_and_the_next():
    log = call((5, 0), (5, 20), (5, 41))
    b = DY.board(log)
    assert b.times[5] == [20.0, 21.0]
    # without a gun the first passage closes nothing
    assert b.lap_col[5] == [1, 2]


def test_a_gun_taken_gives_the_first_lap_a_time_of_its_own():
    b = DY.board(call((5, 10), (5, 30)), start=0.0)
    assert b.times[5] == [10.0, 20.0]
    assert b.lap_col[5] == [0, 1]


# ── what stands out ─────────────────────────────────────────────────────────

def test_nothing_is_judged_before_the_third_lap_time():
    assert not DY.spread([20.0, 40.0]).known


def test_a_lap_far_off_the_mean_is_flagged_and_the_others_are_not():
    times = [20.0, 20.1, 19.9, 20.0, 34.0]
    sp = DY.spread(times, sigma=1.5)
    assert sp.outliers == [4]
    assert sp.mean == pytest.approx(22.8)


def test_a_rider_lapping_at_the_same_time_every_lap_has_no_outlier():
    assert DY.spread([20.0] * 6, sigma=3.0).outliers == []


def test_the_flag_lands_on_the_column_of_the_lap_that_came_out_wrong():
    at = [0, 20, 40, 60, 80, 140]          # the last lap is a minute long
    log = call(*[(5, t) for t in at])
    b = DY.board(log)
    assert DY.flagged(b, sigma=1.5) == {(5, 5)}


# ── the log is the state ────────────────────────────────────────────────────

def test_deleting_a_passage_leaves_nothing_of_it_behind():
    payload = {}
    for bib in (5, 3, 4, 9):               # 4 was never on the track
        DY.add(payload, bib)
    assert DY.remove(payload, 2)
    assert [r["bib"] for r in DY.passages(payload)] == [5, 3, 9]
    assert DY.board(DY.passages(payload)).columns == [[5, 3, 9]]


def test_removing_out_of_range_changes_nothing():
    payload = {}
    DY.add(payload, 5)
    assert not DY.remove(payload, 7)
    assert len(DY.passages(payload)) == 1


def test_a_malformed_line_is_skipped_not_raised():
    payload = {DY.PASSAGES: [{"bib": "x", "at": 1}, {"bib": 5, "at": 2}]}
    assert DY.passages(payload) == [{"bib": 5, "at": 2.0}]


# ── the classification ──────────────────────────────────────────────────────

def test_the_classification_ranks_on_laps_and_carries_no_column_by_default():
    log = call(*lap([5, 3, 9], 0), *lap([5, 3], 10), *lap([5, 3, 9], 20))
    r = DY.derny_classification([3, 5, 9], log)
    assert [p.key for p in r.placings] == ["5", "3", "9"]
    assert [p.position for p in r.placings] == [1, 2, 3]
    assert r.by_key("9").data == {"laps_done": 2, "laps_down": 1}
    # the giri ridden are never a column; the giri persi only when asked for
    assert r.columns == []


def test_the_giri_persi_are_a_column_when_the_jury_asks_for_them():
    log = call(*lap([5, 9], 0), *lap([5], 10), *lap([5, 9], 20))
    r = DY.derny_classification([5, 9], log, show_laps_down=True)
    assert r.columns == ["laps_down"]


def test_a_rider_never_called_is_pending_and_ranks_last():
    r = DY.derny_classification([5, 8], call(*lap([5], 0)))
    assert r.pending == 1
    assert [p.key for p in r.placings] == ["5", "8"]


def test_a_rider_taken_out_of_the_race_falls_behind_the_classified():
    log = call(*lap([5, 3], 0), *lap([5, 3], 10))
    r = DY.derny_classification([5, 3], log, statuses={"5": Status.DNF})
    assert [p.key for p in r.placings] == ["3", "5"]
    assert r.by_key("5").position is None


# ── what the page draws out of it ───────────────────────────────────────────

def test_the_chart_greys_the_lost_lap_reds_the_return_and_yellows_the_odd_time():
    from ui import derny as UI

    # 9 loses a lap, and 5's last lap takes three times as long as the others
    log = call((5, 0), (3, 1), (9, 2), (5, 20), (3, 21),
               (5, 40), (3, 41), (9, 42), (5, 120))
    html = UI._chart_html(DY.board(log), sigma=1.0)
    assert html.count("<th>") == 4
    assert 'class="dy-lost">9<' in html      # the lap he did not ride, grey
    assert 'class="dy-late">9<' in html      # where he came back, in red
    assert 'class="dy-hot">5<' in html       # the lap nobody can explain


def test_the_standings_read_as_the_speaker_reads_them():
    from ui import derny as UI

    log = call(*lap([5, 9], 0), *lap([5], 10), *lap([5, 9], 20))
    html = UI._standings_html(DY.board(log),
                              {5: "ROSSI Marco", 9: "BIANCHI Luca"})
    # place with the °, name whole, and no column of giri
    assert "dy-pos'>1°<" in html and "dy-pos'>2°<" in html
    assert "ROSSI Marco<" in html and "BIANCHI Luca<" in html
    assert "dy-laps" not in html
    assert html.count("class='dy-star'>*<") == 1


# ── what each rider's card says ─────────────────────────────────────────────

def test_the_splits_list_every_passage_with_its_lap_time():
    from ui import derny as UI

    log = call(*lap([5, 3], 0), *lap([5, 3], 20), *lap([5, 3], 40))
    html = UI._splits_html(DY.board(log), 5, sigma=3.0)
    assert html.count("<tr>") == 4          # the head and three passages
    assert "20,00" in html.replace(".", ",") or "20.00" in html


def test_a_rider_with_a_giro_out_of_the_band_gets_a_yellow_card():
    from ui import derny as UI

    steady = [20.0, 20.1, 19.9, 20.0]
    assert "dy-card-hot" not in UI._card(5, steady, "ROSSI Marco", 1.5)
    assert "dy-card-hot" in UI._card(5, [*steady, 34.0], "ROSSI Marco", 1.5)


# ── the call as the jury corrects it ────────────────────────────────────────

def test_a_passage_goes_back_in_where_it_happened():
    payload = {}
    for bib in (5, 3):
        DY.add(payload, bib)
    DY.add(payload, 9, at=1.0, index=1)
    assert [r["bib"] for r in DY.passages(payload)] == [5, 9, 3]


def test_the_number_the_judge_could_not_read_cuts_no_lap():
    log = call((5, 0), ("?", 1), ("?", 2), (3, 3), (5, 20))
    b = DY.board(log)
    assert b.columns == [[5, "?", "?", 3], [5]]
    assert b.order == [5, 3]                # it is nobody's placing
    assert DY.UNKNOWN not in b.laps


def test_a_dorsale_is_read_from_what_the_jury_typed():
    assert DY.as_bib(" 7 ") == 7
    assert DY.as_bib("?") == DY.UNKNOWN
    assert DY.as_bib("") is None and DY.as_bib("x") is None


def test_an_hour_typed_back_lands_on_the_day_of_the_race():
    import datetime as dt

    from ui import derny as UI

    ref = dt.datetime(2026, 9, 2, 10, 40).timestamp()
    at = UI._parse_clock("10:41:07.3", ref)
    assert dt.datetime.fromtimestamp(at).strftime("%Y-%m-%d %H:%M:%S") \
        == "2026-09-02 10:41:07"
    assert UI._parse_clock("nonsense", ref) is None


def test_idem_repeats_the_lap_before_it_in_the_order_it_was_called():
    from ui import derny as UI

    # the field came through 5, 3, 9 and is coming through again as a bunch
    log = call(*lap([5, 3, 9], 0), *lap([5, 3, 9], 20))
    assert UI._last_group(log, len(log)) == [5, 3, 9]
    # with the next lap already started, what is repeated is the full one
    log += call((5, 40))
    assert UI._last_group(log, len(log)) == [5, 3, 9]
    # and there is nothing to repeat before the first number is called
    assert UI._last_group([], 0) == []


# ── the finish: the distance is ridden and the race stops making laps ───────

def test_the_race_is_over_when_the_head_has_ridden_the_distance():
    # a derny of two giri: 5 wins it, and 3 and 9 come in behind
    log = call((5, 0), (3, 1), (9, 2), (5, 20), (3, 22), (9, 24))
    b = DY.board(log, laps=2)
    assert b.over
    assert b.columns == [[5, 3, 9], [5, 3, 9]]
    assert b.order == [5, 3, 9]


def test_after_the_winner_has_crossed_nothing_opens_another_lap():
    # 5 rides its two giri while 3 is still out: 3 comes in on the same column
    log = call((5, 0), (3, 1), (5, 20), (5, 40), (3, 41))
    b = DY.board(log, laps=2)
    assert b.over
    # the third call of 5 would have cut a lap; the race was already won
    assert b.columns == [[5, 3], [5, 5, 3]]
    assert not DY.board(log).over          # and without the distance, nothing


def test_the_classification_is_read_off_the_arrival_once_it_is_over():
    log = call((5, 0), (3, 1), (9, 2), (5, 20), (9, 21), (3, 22))
    r = DY.derny_classification([3, 5, 9], log, laps=2)
    assert [p.key for p in r.placings] == ["5", "9", "3"]
