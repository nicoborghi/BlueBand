"""Bunch races: corsa a punti, scratch, tempo race, eliminazione.

Scoring follows the UCI regulations as applied in the jury workbooks:

* **corsa a punti / madison** - 5-3-2-1 to the first four of each sprint,
  10-6-4-2 in the final sprint; a lap gained is +20, a lap lost -20; ties are
  broken by the placing in the last sprint.
* **tempo race** - 1 point to the winner of each sprint (the +20/-20 lap rule
  applies as well).
* **scratch** - no points, the finishing order is the classification.
* **eliminazione** - riders are entered in the order they are eliminated; the
  first one out is last, the winner is the last number typed. While the race is
  running the riders still in it print with a blank position, so the same sheet
  works as a live provisional - and the winner is one of them until the jury
  writes the number down: a rider is never placed by the app for not having
  been typed.
"""

from __future__ import annotations

from ..i18n import msg
from ..models import Status
from ..parse import duplicates, unknown
from .base import (CLASSIFIED, Placing, Result, assign_positions,
                   leaving_order, sort_by_status, sort_placings)

#: Whose total is printed at all. A ritirata keeps what she scored before she
#: left - she rode those volate - so the column stands next to her DNF; a scesa
#: and a squalificata have no total to show (see `group_classification`).
SCORING = (Status.OK, Status.DNF)

SPRINT_POINTS = [5, 3, 2, 1]
FINAL_SPRINT_POINTS = [10, 6, 4, 2]
LAP_POINTS = 20
MIN_SPRINT_FINISHERS = 4

POINTS = "points"
TEMPO = "tempo"
SCRATCH = "scratch"
MADISON = "madison"


def group_classification(startlist: list[int], sprints: list[list[int]], *,
                         scoring: str = POINTS, n_sprint: int | None = None,
                         laps_gained: list[int] | None = None,
                         laps_lost: list[int] | None = None,
                         statuses: dict[str, Status] | None = None) -> Result:
    """Classify a bunch race. `startlist` and sprint entries are bibs."""
    statuses = dict(statuses or {})
    warnings: list[str] = []
    n_sprint = n_sprint if n_sprint is not None else len(sprints)

    if n_sprint and len(sprints) > n_sprint:
        warnings.append(msg("extra_sprints", n=len(sprints), planned=n_sprint))

    known = set(startlist)
    points: dict[int, int] = {b: 0 for b in startlist}
    per_sprint: dict[int, list[int]] = {b: [0] * len(sprints) for b in startlist}

    for i, sprint in enumerate(sprints):
        for dup in duplicates(sprint):
            warnings.append(msg("sprint_duplicate_bib", bib=dup, n=i + 1))
        for miss in unknown(sprint, startlist):
            warnings.append(msg("sprint_unknown_bib", bib=miss, n=i + 1))

        valid = [b for b in sprint if b in known]
        if scoring in (POINTS, MADISON):
            if len(valid) < MIN_SPRINT_FINISHERS:
                warnings.append(msg("sprint_too_few", n=i + 1, found=len(valid),
                                    expected=MIN_SPRINT_FINISHERS))
            is_final = (i == len(sprints) - 1) and (i == n_sprint - 1 or not n_sprint)
            scale = FINAL_SPRINT_POINTS if is_final else SPRINT_POINTS
            for rank, bib in enumerate(valid[:len(scale)]):
                points[bib] += scale[rank]
                per_sprint[bib][i] = scale[rank]
        elif scoring == TEMPO:
            if valid:
                points[valid[0]] += 1
                per_sprint[valid[0]][i] = 1

    # A pari punti decide il passaggio all'ultima volata, e *solo* quello: chi
    # in quell'ordine non c'e' non ha un passaggio da far valere. Tenere il
    # piazzamento dell'ultima volata in cui il corridore compariva metteva a
    # confronto una volata con un'altra, e faceva precedere chi all'ultima non
    # era passato davanti a chi ci era passato quarto.
    final = [b for b in (sprints[-1] if sprints else []) if b in known]
    last_sprint_rank: dict[int, int] = {b: 10 ** 6 for b in startlist}
    for rank, bib in enumerate(final):
        last_sprint_rank[bib] = rank

    # laps gained / lost
    lap_net: dict[int, int] = {b: 0 for b in startlist}
    for bib in (laps_gained or []):
        if bib in known:
            lap_net[bib] += 1
        else:
            warnings.append(msg("lap_gained_unknown", bib=bib))
    for bib in (laps_lost or []):
        if bib in known:
            lap_net[bib] -= 1
        else:
            warnings.append(msg("lap_lost_unknown", bib=bib))

    placings: list[Placing] = []
    for bib in startlist:
        key = str(bib)
        status = statuses.get(key, Status.OK)
        # a rider who came down of her own accord scores nothing: the volate she
        # took before that are not printed either, or the sheet reads as if she
        # had been classified on them (a ritirata keeps hers - she was racing
        # until the race stopped her)
        scored = status is not Status.ABD
        total = points[bib] + LAP_POINTS * lap_net[bib]
        shown = total if status in SCORING else 0
        placings.append(Placing(key=key, status=status, data={
            "sprints": per_sprint[bib] if scored else [0] * len(sprints),
            "points": points[bib] if scored else 0,
            "laps": lap_net[bib] if scored else 0,
            "total": shown,
            "_sort": -(total if status is Status.OK else 0),
            "_tiebreak": last_sprint_rank[bib],
        }))

    if scoring == SCRATCH:
        # the finishing order is the last (only) sprint; unlisted riders follow
        order = [b for b in (sprints[-1] if sprints else []) if b in known]
        rank = {b: i for i, b in enumerate(order)}
        for p in placings:
            p.data["_sort"] = rank.get(int(p.key), 10 ** 6)
            p.data["_tiebreak"] = 0
            p.data.pop("points", None)
            p.data["sprints"] = []

    placings.sort(key=lambda p: (p.data["_sort"], p.data["_tiebreak"], int(p.key)))
    placings = sort_placings(placings, order=leaving_order(statuses))
    assign_positions(placings)

    cols = [] if scoring == SCRATCH else ["points", "laps", "total"]
    return Result(placings=placings, warnings=warnings, columns=cols)


def elimination_classification(startlist: list[int], eliminated: list[int], *,
                               statuses: dict[str, Status] | None = None) -> Result:
    """Classify an elimination race from the order riders were eliminated in."""
    statuses = dict(statuses or {})
    warnings: list[str] = []
    known = set(startlist)

    for dup in duplicates(eliminated):
        warnings.append(msg("eliminated_twice", bib=dup))
    for miss in unknown(eliminated, startlist):
        warnings.append(msg("bib_not_entered", bib=miss))
    if len(eliminated) > len(startlist):
        warnings.append(msg("too_many_eliminations", n=len(eliminated),
                            starters=len(startlist)))

    def status_of_bib(bib: int) -> Status:
        return statuses.get(str(bib), Status.OK)

    # only riders who took the start and finished are numbered; the first one
    # eliminated is last, so positions count down from the number of classified
    classified = [b for b in startlist if status_of_bib(b) in CLASSIFIED]
    order = [b for b in eliminated if b in known and status_of_bib(b) in CLASSIFIED]
    still = [b for b in classified if b not in set(order)]

    position: dict[int, int | None] = {}
    n = len(classified)
    for i, bib in enumerate(order):
        position[bib] = n - i
    for bib in still:
        # nobody is placed by not being typed. A dorsale missing from the field
        # is a dorsale the segreteria has still to write down, and the last one
        # left is the winner of the race - the one line of the sheet that must
        # never be filled in by the app on its own. It stays pending, above the
        # blank line, until it is typed.
        position[bib] = None

    placings = [Placing(key=str(b), status=status_of_bib(b),
                        position=position.get(b))
                for b in startlist]
    # riders still in the race print first with a blank position, so the same
    # sheet doubles as a live provisional classification
    placings.sort(key=lambda p: (p.position is not None, p.position or 0,
                                 int(p.key)))
    placings = sort_by_status(placings, leaving_order(statuses))

    return Result(placings=placings, warnings=warnings, pending=len(still))
