"""Omnium: four races, one classification.

Scratch, tempo race and elimination are scored by placing on the UCI scale
(40 for the win, then -2 per place down to 2 for 20th, 1 from 21st on). The
points race is different: the points actually scored in it are **added** to the
running total, so a rider can still overturn the standings in the last race.
Ties are broken by the placing in the points race.
"""

from __future__ import annotations

from ..i18n import msg
from ..models import STATUS_ORDER, Status
from .base import CLASSIFIED, Placing, Result, sort_by_status

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
                          statuses: dict[str, Status] | None = None) -> Result:
    """Combine up to four round results into the omnium standings.

    A prova a rider did not finish is not an omnium result: the DNF, DNS or DSQ
    taken in any of the four is carried into the standings, where the rider is
    listed under the classified with the sigla and no placing. A declassamento
    is a placing like any other and travels as one; an explicit `statuses` entry
    (the caller knows better) wins over what the prove say.
    """
    statuses = dict(statuses or {})
    keys: list[str] = list(entrants or [])
    for name in ROUNDS:
        for p in (rounds.get(name).placings if rounds.get(name) else []):
            if p.key not in keys:
                keys.append(p.key)

    totals: dict[str, int] = {k: 0 for k in keys}
    per_round: dict[str, dict[str, int]] = {k: {} for k in keys}
    tiebreak: dict[str, int] = {}
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
                tiebreak[p.key] = p.position or 10 ** 6
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

    placings = []
    for k in keys:
        status = statuses.get(k) or carried.get(k, Status.OK)
        scored = per_round.get(k, {})
        placings.append(Placing(key=k, status=status, data={
            "events": scored,
            "total": totals.get(k, 0) if status in CLASSIFIED else 0,
            # what the rider took into the corsa a punti: the column that sheet
            # is scored from, and the one the classifica opens on
            "carried": sum(scored.get(n) or 0 for n in PLACING_ROUNDS),
            **detail.get(k, {}),
            **{points_key(name): scored.get(name) for name in ROUNDS},
        }))

    placings.sort(key=lambda p: (-p.data["total"], tiebreak.get(p.key, 10 ** 6)))
    placings = sort_by_status(placings)
    n = 0
    for p in placings:
        if p.status in CLASSIFIED:
            n += 1
            p.position = n

    done = [name for name in ROUNDS if rounds.get(name)]
    return Result(placings=placings, columns=["total"],
                  warnings=([] if len(done) == len(ROUNDS) else
                            [msg("partial_standings", done=len(done),
                                 total=len(ROUNDS), rounds=", ".join(done))]))
