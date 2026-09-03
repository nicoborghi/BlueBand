"""Derny: the lap chart the judge calls, live.

A derny is called, not written up afterwards. The finish judge reads the
numbers out as they cross the line and somebody types them in; twenty minutes
later nobody remembers who was where, and the one question that matters -
*who is on the same lap as the leader* - has no answer left. So the only thing
this format stores is **the call itself**: one line per passage, the number and
the moment it was typed.

    payload["passages"] = [{"bib": 5, "at": 1756...}, ...]

Everything on screen is derived from that list, every time it is drawn: the
lap chart, who has lost a lap, the standings, the lap times, the outliers.
Nothing is cached, nothing is written twice, and a number typed by mistake is
undone by dropping its line - there is no second copy of it to go stale.

**How the laps are cut.** The head makes the lap: a new column opens the moment
a number is called that has already been called in the column now open. That
is the leader coming round again (or, if the head has changed, whoever is
first now) - and it needs no button pressed at the right instant.

**How a lap is lost.** A rider who is lapped does not pass in the column where
the leader passed twice: his number simply is not in it. He shows up again in
the column after, and *that* is when it is known. So a bib missing from the
columns between two of its own passages is a lap lost there: the chart prints
it back, in a grey light enough to read as "not here", in the column he should
have passed in, and marks the column where he did reappear in red - the grey
keeps the column complete to the eye, the red says a lap went.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from statistics import mean as _mean
from statistics import stdev as _stdev

from ..models import Status
from .base import Placing, Result, assign_positions, sort_by_status

#: The number nobody read. The finish judge sees somebody come through and
#: cannot say who: the passage happened and it belongs in the column, so it is
#: written down as `?`. It fills its place in the chart and nothing else - it
#: never cuts a lap (two `?` in one column are two different riders), it is
#: nobody's giro and it is in no classification. The jury turns it into a
#: dorsale in Cronologico as soon as it knows which one it was.
UNKNOWN = "?"

#: Payload keys. The log is the state; the other two are how it is read.
PASSAGES = "passages"
START = "derny_start"      # epoch of the gun, when the jury took it
SIGMA = "derny_sigma"      # the outlier threshold in force, in sigmas
SHOW_DOWN = "derny_laps_down"  # whether the classifica carries the giri persi

#: A mean over two numbers says nothing about the third. Below this the lap
#: times are printed and nothing is judged on them.
MIN_TIMES = 3

#: What "deviazione dalla media" can be set to, and where it starts. Three
#: sigmas over a race of forty laps is roughly one false flag per race - low
#: enough to be worth looking at every time, high enough not to be ignored.
SIGMAS = (1.0, 2.0, 3.0, 4.0, 5.0)
DEFAULT_SIGMA = 3.0


# ── the log ─────────────────────────────────────────────────────────────────

def as_bib(value) -> int | str | None:
    """A dorsale as the log holds it: an int, `?`, or None if it is neither."""
    if str(value).strip() == UNKNOWN:
        return UNKNOWN
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def passages(payload: dict | None) -> list[dict]:
    """The call as it stands: `[{"bib": int | "?", "at": float}]`, in order."""
    out = []
    for row in (payload or {}).get(PASSAGES) or []:
        try:
            bib = as_bib(row["bib"])
            at = float(row.get("at") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if bib is not None:
            out.append({"bib": bib, "at": at})
    return out


def add(payload: dict, bib: int | str, at: float | None = None,
        index: int | None = None) -> dict:
    """Write one passage down. `at` defaults to now, `index` to the end.

    `index` is how a passage nobody typed at the time is put back where it
    happened - the judge calls it half a lap later, and it belongs between two
    lines already written (`ui.derny`).
    """
    row = {"bib": as_bib(bib), "at": float(at if at is not None else time.time())}
    log = payload.setdefault(PASSAGES, [])
    log.insert(len(log) if index is None else max(0, min(int(index), len(log))),
               row)
    return row


def replace(payload: dict, log: list[dict]) -> None:
    """Put the whole call back, as the jury corrected it in Cronologico."""
    payload[PASSAGES] = [{"bib": as_bib(r["bib"]), "at": float(r["at"])}
                         for r in log if as_bib(r["bib"]) is not None]


def remove(payload: dict, index: int) -> bool:
    """Drop the passage at `index` - a number called that was never ridden.

    The list is the whole state, so this is the whole undo: nothing derived
    from it survives the drop, because nothing derived from it is stored.
    """
    log = payload.get(PASSAGES) or []
    if 0 <= index < len(log):
        del log[index]
        return True
    return False


def sigma_of(payload: dict | None) -> float:
    try:
        return float((payload or {}).get(SIGMA) or DEFAULT_SIGMA)
    except (TypeError, ValueError):
        return DEFAULT_SIGMA


# ── the chart ───────────────────────────────────────────────────────────────

@dataclass
class Board:
    """The lap chart, and everything read off it."""

    #: One list of bibs per lap, in the order they were called.
    columns: list[list[int]] = field(default_factory=list)
    #: Per column, the bibs that lost a lap there - what prints in grey, in
    #: the column they should have passed in.
    lost: list[list[int]] = field(default_factory=list)
    #: (bib, column) of every passage that comes back from a lap lost: the
    #: column where the rider actually reappeared, which is what prints in red.
    late: set[tuple[int, int]] = field(default_factory=set)
    #: The standings: full laps first, then one down, then two, each group in
    #: the order they last passed.
    order: list[int] = field(default_factory=list)
    down: dict[int, int] = field(default_factory=dict)     # laps lost
    laps: dict[int, int] = field(default_factory=dict)     # laps ridden
    #: Lap times, in seconds, per bib - one per lap that has one.
    times: dict[int, list[float]] = field(default_factory=dict)
    #: Whether the distance has been ridden: the winner has crossed the line
    #: and the chart makes no more laps (`board`, with the giri of the fase).
    over: bool = False
    #: Which column each of those lap times closes (same length as `times`).
    lap_col: dict[int, list[int]] = field(default_factory=dict)
    #: Every passage of a rider as it was called: (column, epoch), in order.
    #: The lap times are the gaps between these, and the parziali are read off
    #: them passage by passage (`ui.derny`).
    marks: dict[int, list[tuple[int, float]]] = field(default_factory=dict)

    @property
    def leader_laps(self) -> int:
        return max(self.laps.values(), default=0)


def board(log: list[dict], start: float | None = None,
          laps: float | int | None = None) -> Board:
    """Read the call into a lap chart. Pure: same list in, same chart out.

    `laps` is the distance the fase runs, from the programme. With it the chart
    knows when the race is **over**: the moment somebody completes that many
    giri the winner has crossed the line, and everybody else is riding in to
    finish. No new column opens after that - the riders still out come through
    once each, into the column the winner finished in, and that last passage of
    each of them is where they placed (`derny_classification`).

    Without it the chart is what it always was, and it keeps cutting laps for
    as long as numbers are called.
    """
    planned = int(laps or 0)
    b = Board()
    seen: dict[int, list[tuple[int, float]]] = {}

    for row in log:
        bib, at = row["bib"], row["at"]
        if bib == UNKNOWN:
            # somebody came through and nobody read the number: it fills the
            # column that is open and cuts nothing - two of them in one column
            # are two different riders, and neither is a giro of anybody's
            if not b.columns:
                b.columns.append([])
            b.columns[-1].append(bib)
            continue
        if not b.columns or (bib in b.columns[-1] and not b.over):
            b.columns.append([])
        b.columns[-1].append(bib)
        seen.setdefault(bib, []).append((len(b.columns) - 1, at))
        if planned and len(seen[bib]) >= planned:
            # the distance is ridden: whoever did it first is the winner, and
            # the race stops making laps here
            b.over = True

    b.lost = [[] for _ in b.columns]
    # the column being called into now. What is missing from it is not lost:
    # the rider may still be coming. What is missing from a column already
    # closed *is* - the giri have moved on without him, and that is the whole
    # of it: he does not have to reappear for the lap to be gone.
    open_col = len(b.columns) - 1
    for bib, marks in seen.items():
        cols = [c for c, _ in marks]
        b.laps[bib] = len(cols)
        gaps = 0
        for a, z in zip(cols, cols[1:]):
            if z > a + 1:
                # he reappears here, a lap (or two) behind: this is the column
                # where the loss is known, and the one the chart prints in red
                b.late.add((bib, z))
            for missing in range(a + 1, z):
                b.lost[missing].append(bib)
                gaps += 1
        for missing in range(cols[-1] + 1, open_col):
            # closed since he last came through: those giri are gone whether or
            # not he is called again. He is a lap down from the moment the head
            # cuts the next column without him, which is when the jury has to
            # know it - not when he shows up again two minutes later
            b.lost[missing].append(bib)
            gaps += 1
        b.down[bib] = gaps

        stamps = [t for _, t in marks]
        if start is not None:
            stamps = [float(start)] + stamps
        b.times[bib] = [round(z - a, 3) for a, z in zip(stamps, stamps[1:])]
        # the lap time closes on the passage that ends it: with a gun taken,
        # the first passage closes the first lap, without it the second does
        b.lap_col[bib] = cols if start is not None else cols[1:]

    # full laps first, then those a lap down and so on; inside a group,
    # whoever is furthest round leads, and at equal laps whoever passed first
    b.marks = seen
    b.order = sorted(seen, key=lambda x: (b.down[x], -seen[x][-1][0],
                                          seen[x][-1][1]))
    return b


# ── the lap times ───────────────────────────────────────────────────────────

@dataclass
class Spread:
    """What a rider's lap times look like: the middle, the width, the odd one."""

    mean: float | None = None
    sd: float | None = None
    outliers: list[int] = field(default_factory=list)  # indices into `times`

    @property
    def known(self) -> bool:
        return self.mean is not None


def spread(times: list[float], sigma: float = DEFAULT_SIGMA) -> Spread:
    """Mean, standard deviation and the laps that fall outside `sigma` of it.

    Nothing is judged before the third lap time (`MIN_TIMES`): with two of them
    the deviation is the gap between the two, and every lap is an outlier.
    """
    if len(times) < MIN_TIMES:
        return Spread()
    m, s = _mean(times), _stdev(times)
    if not s:
        return Spread(mean=m, sd=0.0)
    band = sigma * s
    return Spread(mean=m, sd=s,
                  outliers=[i for i, t in enumerate(times) if abs(t - m) > band])


def flagged(b: Board, sigma: float = DEFAULT_SIGMA) -> set[tuple[int, int]]:
    """(bib, column) of every lap whose time is more than `sigma` off the mean.

    That pair is a cell of the chart: what turns yellow is the number in the
    column of the lap that came out wrong, which is where to go and look.
    """
    out: set[tuple[int, int]] = set()
    for bib, times in b.times.items():
        cols = b.lap_col.get(bib) or []
        for i in spread(times, sigma).outliers:
            if i < len(cols):
                out.add((bib, cols[i]))
    return out


# ── the classification ──────────────────────────────────────────────────────

def derny_classification(startlist: list[int], log: list[dict],
                         start: float | None = None,
                         statuses: dict[str, Status] | None = None,
                         show_laps_down: bool = False,
                         laps: float | int | None = None) -> Result:
    """Rank a derny on the chart: laps first, then the order of the last call.

    The classifica of a derny is a placing and a name. How many giri the leader
    rode is the race, not the rider, and it is on the sheet's own info line
    already; the giri persi are a column the jury turns on when the race was
    ridden with riders a lap down (`show_laps_down`) - off, the asterisks that
    say the same thing are not printed either.
    """
    statuses = dict(statuses or {})
    b = board(log, start, laps)
    rank = {bib: i for i, bib in enumerate(b.order)}

    placings = [
        Placing(key=str(bib), status=statuses.get(str(bib), Status.OK),
                data={"laps_done": b.laps.get(bib, 0),
                      "laps_down": b.down.get(bib, 0)})
        for bib in sorted(startlist, key=lambda x: (rank.get(x, 10 ** 6), x))
    ]
    return Result(placings=assign_positions(sort_by_status(placings)),
                  columns=["laps_down"] if show_laps_down else [],
                  pending=sum(1 for x in startlist if x not in rank))
