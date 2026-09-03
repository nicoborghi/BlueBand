"""Omnium: four races, one classification.

Scratch, tempo race and elimination are scored by placing on the UCI scale
(40 for the win, then -2 per place down to 2 for 20th, 1 from 21st on). The
points race is different: the points actually scored in it are **added** to the
running total, so a rider can still overturn the standings in the last race.
Ties are broken by the passage at the last sprint of the points race, and
between two riders that sprint has not separated - a classifica parziale, where
the points race has not been ridden - by the placing in the last prova ridden.
"""

from __future__ import annotations

from ..i18n import msg
from ..models import STATUS_ORDER, Status
from .base import (CLASSIFIED, Placing, Result, assign_positions,
                   sort_by_status)

#: **Programme vocabulary, not a label.** These strings are the keys the
#: rounds are scheduled under in `programme.yaml` and saved under in
#: `races/<id>.json`: translating them would stop the app finding a race.
#: What the jury *reads* is in `core.i18n`.
SCRATCH = "Scratch"
TEMPO = "Tempo Race"
ELIMINATION = "Eliminazione"
POINTS_RACE = "Corsa a Punti"
ROUNDS = [SCRATCH, TEMPO, ELIMINATION, POINTS_RACE]

# The three prove scored on the placing scale: what a rider carries into the
# corsa a punti, and what the classifiche parziali are made of.
PLACING_ROUNDS = [SCRATCH, TEMPO, ELIMINATION]


def points_key(name: str) -> str:
    """Where the points of one prova live in a placing's data."""
    return f"e_{name}"


def placing_points(position: int | None) -> int:
    """UCI omnium scale: 40, 38, 36 … 2 for 20th, then 1."""
    if not position or position < 1:
        return 0
    if position <= 20:
        return 42 - 2 * position
    return 1


def omnium_classification(rounds: dict[str, Result], *,
                          entrants: list[str] | None = None,
                          expected: list[str] | None = None,
                          statuses: dict[str, Status] | None = None) -> Result:
    """Combine the results of the prove into the omnium standings.

    A prova a rider did not finish ends her omnium: a DNF, DNS, ABD or DSQ
    taken in any of them keeps her out of the ordine di partenza of what
    follows (`race.left_event`) and out of the places. It does not take her off
    the classification: she stays on it under the classified, with her sigla
    and without a position, exactly as the risultati of the prova she took it
    in print her (`race.omnium_points_race`). That is what a classifica is for
    - it answers for the event, not for one sheet - and it is the same
    reading everywhere, so the jury never has to reconcile two tables.

    A declassamento is a placing like any other and travels as one; an explicit
    `statuses` entry (the caller knows better) wins over what the prove say,
    and takes the rider out the same way.

    `expected` are the prove this omnium is made of - what the programme
    schedules for that categoria (`race.omnium_prove`), which is not always the
    four of the UCI omnium. It is what the standings call themselves partial
    against: an omnium of three prove is complete on the third, and saying «3
    su 4» on its classifica would report a race nobody has failed to ride.
    """
    expected = list(expected or ROUNDS)
    statuses = dict(statuses or {})
    keys: list[str] = list(entrants or [])
    for name in ROUNDS:
        for p in (rounds.get(name).placings if rounds.get(name) else []):
            if p.key not in keys:
                keys.append(p.key)

    totals: dict[str, int] = {k: 0 for k in keys}
    per_round: dict[str, dict[str, int]] = {k: {} for k in keys}
    tiebreak: dict[str, int] = {}
    last_place: dict[str, int] = {}       # placing in the last prova ridden
    detail: dict[str, dict] = {}
    carried: dict[str, Status] = {}

    for name in ROUNDS:
        res = rounds.get(name)
        if res is None:
            continue
        for p in res.placings:
            if name == POINTS_RACE:
                # the points race adds its own points, not a placing score
                pts = int((p.data or {}).get("total") or 0)
                # il passaggio all'ultima volata, non la posizione in classifica
                # della corsa a punti: due pari punti nell'omnium non sono pari
                # punti in quella corsa, e la sua classifica li avrebbe separati
                # su un criterio che l'omnium non applica (`formats.group`)
                tiebreak[p.key] = int((p.data or {}).get("_tiebreak", 10 ** 6))
                # the volate and the giri of that race, so the classifica can
                # print the sheet the jury scored it on
                detail[p.key] = {"sprints": (p.data or {}).get("sprints") or [],
                                 "laps": (p.data or {}).get("laps") or 0}
            else:
                pts = placing_points(p.position) if p.status in CLASSIFIED else 0
            if p.status not in CLASSIFIED:
                worst = carried.get(p.key)
                if worst is None or STATUS_ORDER[p.status] > STATUS_ORDER[worst]:
                    carried[p.key] = p.status
            per_round[p.key][name] = pts
            totals[p.key] = totals.get(p.key, 0) + pts
            # the prove are read in order, so what stays is the placing in the
            # last one ridden: it is what separates two riders on the same
            # points (below, in the sort)
            last_place[p.key] = p.position or 10 ** 6

    placings = []
    for k in keys:
        status = statuses.get(k) or carried.get(k, Status.OK)
        # a rider who did not finish the event' scores nothing in it: the
        # prove she did ride are on their own risultati, and a total printed
        # next to a sigla reads as a result the omnium never awarded. The same
        # rule the sheet applies to the time of a squalificata
        # (`documents._result_cells`), applied where the points are counted.
        scored = per_round.get(k, {}) if status in CLASSIFIED else {}
        placings.append(Placing(key=k, status=status, data={
            "events": scored,
            "total": totals.get(k, 0) if status in CLASSIFIED else 0,
            # what the rider took into the corsa a punti: the column that sheet
            # is scored from, and the one the classifica opens on
            "carried": sum(scored.get(n) or 0 for n in PLACING_ROUNDS),
            **(detail.get(k, {}) if status in CLASSIFIED else {}),
            **{points_key(name): scored.get(name) for name in ROUNDS},
        }))

    # points first; then, between riders on the same points, the placing in the
    # last prova ridden - from the 21st place down a whole group of them scores
    # 1 point, and a classifica that left them in startlist order would be read
    # as saying they finished that way. La corsa a punti decide la classifica
    # finale (3.2.109) ed e' chiesta per prima, essendo l'ultima prova: come in
    # ogni corsa a punti il pari merito si scioglie sull'ultima volata.
    placings.sort(key=lambda p: (-p.data["total"], tiebreak.get(p.key, 10 ** 6),
                                 last_place.get(p.key, 10 ** 6)))
    placings = assign_positions(sort_by_status(placings))

    done = [name for name in expected if rounds.get(name)]
    return Result(placings=placings, columns=["total"],
                  warnings=([] if len(done) == len(expected) else
                            [msg("partial_standings", done=len(done),
                                 total=len(expected), rounds=", ".join(done))]))
