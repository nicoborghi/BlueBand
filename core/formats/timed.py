"""Timed races: individual and team pursuit, km, 500 m, team sprint.

Entrants are individual riders or whole teams; a team has **one** time, not a
time typed on an arbitrary rider row (the old track.py stored it per rider).
Heats come from the jury's shorthand, `1,2-3,4/5,6-7,8`: `/` separates heats,
`-` the two sides of a heat, `,` the riders of one team.

Finals are loaded from the qualification: the first four qualified ride two
finals, 3rd against 4th first and 1st against 2nd last. Each final assigns the
places it rides for; whoever did not qualify keeps the order - and the time -
of the qualification.
"""

from __future__ import annotations

from typing import Iterable

from ..i18n import msg, ordinal
from ..models import Status
from ..parse import duplicates, format_heats
from .base import CLASSIFIED, Placing, Result, sort_by_status

# The finals in the order they are ridden, as indexes into the qualification
# ranking: the 3/4 final opens, the title final closes.
FINALS = [(2, 3), (0, 1)]


def timed_classification(entrants: list[str], times: dict[str, int], *,
                         statuses: dict[str, Status] | None = None,
                         qualification: dict[str, int] | None = None) -> Result:
    """Rank entrants by time (ms, ascending). Missing times are left pending."""
    statuses = dict(statuses or {})
    warnings: list[str] = []

    def data_for(e: str) -> dict:
        return {"time": times.get(e), "qual": (qualification or {}).get(e)}

    timed_, pending, out = [], [], []
    for e in entrants:
        st = statuses.get(e, Status.OK)
        if st not in CLASSIFIED:
            out.append(e)
        elif times.get(e):
            timed_.append(e)
        else:
            pending.append(e)

    timed_.sort(key=lambda e: (times[e], e))
    placings = [Placing(key=e, status=statuses.get(e, Status.OK),
                        data=data_for(e)) for e in timed_ + pending + out]

    n = 0
    for p in placings:
        if p.status in CLASSIFIED and p.data.get("time"):
            n += 1
            p.position = n
    placings = sort_by_status(placings)

    dup = [t for t in duplicates([times[e] for e in timed_])]
    for t in dup:
        warnings.append(msg("same_time", ms=t))

    return Result(placings=placings, warnings=warnings,
                  columns=["time"], pending=len(pending))


# ── heats ───────────────────────────────────────────────────────────────────

def seed_finals(ranking: list[str]) -> list[list[str]]:
    """The finals of a team pursuit, in the order they are ridden."""
    return [[ranking[a], ranking[b]] for a, b in FINALS
            if a < len(ranking) and b < len(ranking)]


def seed_finals_text(ranking_bibs: list[list[int]]) -> str:
    """Heat string for the finals, where each entrant is a list of bibs."""
    return format_heats(seed_finals(ranking_bibs))


def final_place(heat: list[str], ranking: list[str]) -> int:
    """The best place a final rides for: 1 for the 1/2 final, 3 for the 3/4."""
    places = [ranking.index(e) + 1 for e in heat if e in ranking]
    return min(places) if places else 0


def final_label(place: int) -> str:
    """3 -> '3°/4°'. What the sheet calls the final riding for those places."""
    return f"{ordinal(place)}/{ordinal(place + 1)}" if place else ""


def final_places(final_heats: list[list[str]], ranking: list[str]) -> list[int]:
    """The best place each final rides for, in the order they are ridden.

    A final composed by hand - one the qualification did not seed - has nobody
    in the ranking to read a place off: it falls back on the order the heats
    are in, which is the order they are ridden (3/4 first, then 1/2).
    """
    return [final_place(h, ranking) or 2 * i + 1
            for i, h in enumerate(final_heats)]


def finals_classification(final_heats: list[list[str]],
                          times: dict[str, int], *,
                          statuses: dict[str, Status] | None = None,
                          qualification: list[str] | None = None,
                          qual_times: dict[str, int] | None = None,
                          qual_out: dict[str, Status] | None = None,
                          tied: Iterable[int] | None = None,
                          on_qual: Iterable[int] | None = None) -> Result:
    """Classify the finals against the qualification they were loaded from.

    Each final assigns the places it rides for - the 3/4 final cannot promote
    anyone to second - so the sheet reads the same whichever final ran first.
    Whoever did not qualify keeps the qualifying order below the finalists, and
    the time they set there: it is the only time they rode.

    A final that is not ridden is closed in one of two ways, and the jury says
    which. Both are given by the place the final rides for - 1 for the 1/2, 3
    for the 3/4 - and neither moves anybody below: two entrants take two places
    whatever decided them, so whoever follows is 3rd, or 5th, as before.

    * `tied`: **a pari merito**. Neither of the two places is assigned on its
      own - the two share the lower one: both are 2°, or both 4°. They carry
      no time at all: nothing was ridden for that place.
    * `on_qual`: **on the qualifying times**. The two are placed 1° and 2° (or
      3° and 4°) by the time they set in the qualification, which is the only
      time they rode, and that is the time the sheet carries.

    `qual_out` are the squadre the qualification did not classify - DNS, DSQ,
    DNF. They never reach the finals, but the classification of the specialità
    is the sheet that files the decision taken on them: they print at the
    bottom, with their status and no place, like every other non-classified.
    """
    statuses = dict(statuses or {})
    ranking = list(qualification or [])
    qual_times = dict(qual_times or {})
    ex_aequo = set(tied or ())
    from_qual = set(on_qual or ()) - ex_aequo
    placings: list[Placing] = []
    seen: set[str] = set()

    def qual_key(e: str) -> tuple:
        """The qualification's own order: its time, then where it ranked."""
        t = qual_times.get(e)
        return (t is None, t or 0,
                ranking.index(e) if e in ranking else len(ranking))

    for base, heat in zip(final_places(final_heats, ranking), final_heats):
        if base in ex_aequo:
            # not ridden: the two keep the order the qualification put them in
            # and share the second of the two places the final rides for. And
            # no time - the final was not ridden and nothing decided it, so a
            # time in that column would be a result nobody rode for.
            for e in sorted(heat, key=qual_key):
                seen.add(e)
                placings.append(Placing(
                    key=e, status=statuses.get(e, Status.OK),
                    position=base + 1,
                    data={"time": None, "final": base,
                          "tied": True, "unridden": True}))
            continue
        if base in from_qual:
            # not ridden either, but decided: the qualifying times place the
            # two, and the time on the sheet is the one they set there
            for i, e in enumerate(sorted(heat, key=qual_key)):
                seen.add(e)
                placings.append(Placing(
                    key=e, status=statuses.get(e, Status.OK),
                    position=base + i,
                    data={"time": qual_times.get(e, times.get(e)),
                          "final": base, "heat_place": i + 1,
                          "unridden": True}))
            continue
        ranked = sorted(heat, key=lambda e: (times.get(e) is None,
                                             times.get(e, 0), e))
        for i, e in enumerate(ranked):
            seen.add(e)
            placings.append(Placing(key=e, status=statuses.get(e, Status.OK),
                                    position=base + i,
                                    data={"time": times.get(e), "final": base,
                                          "heat_place": i + 1}))
    placings.sort(key=lambda p: p.position or 0)

    n = len(placings)
    for e in ranking:
        if e in seen:
            continue
        n += 1
        placings.append(Placing(key=e, status=statuses.get(e, Status.OK),
                                position=n,
                                data={"time": qual_times.get(e, times.get(e)),
                                      "qual": True}))

    for e, st in (qual_out or {}).items():
        if e in seen or e in ranking:
            continue
        placings.append(Placing(key=e, status=statuses.get(e, st),
                                data={"time": qual_times.get(e), "qual": True}))

    # the finals are seeded, so this sheet has a full order on it the moment it
    # is loaded - before a single time is taken. Say how many are still to come:
    # read without that, the places above look like a result. A final that is
    # not going to be ridden - a pari merito or closed on the qualifying times
    # - is not counted: no time is coming for it.
    waiting = {p.key for p in placings if p.data.get("final") is not None
               and not p.data.get("unridden")}
    missing = sum(1 for e in seen if not times.get(e) and e in waiting
                  and statuses.get(e, Status.OK) in CLASSIFIED)

    ordered = sort_by_status(placings)
    # renumber: a squadra squalificata in a final does not keep the place the
    # heat gave it, and the one that beat nobody still wins. Without a decision
    # this is a no-op - the finals are seeded 1/2 and 3/4, so the places they
    # assign are already 1..n. Two a pari merito are numbered as one block:
    # they take two places between them and print the lower of the two.
    n = i = 0
    for p in ordered:
        if p.status not in CLASSIFIED:
            p.position = None
    while i < len(ordered):
        p = ordered[i]
        if p.status not in CLASSIFIED:
            i += 1
            continue
        block = [p]
        while p.data.get("tied") and i + len(block) < len(ordered):
            q = ordered[i + len(block)]
            if (q.status not in CLASSIFIED or not q.data.get("tied")
                    or q.data.get("final") != p.data.get("final")):
                break
            block.append(q)
        n += len(block)
        for q in block:
            q.position = n
            if q.data.get("tied"):
                # left alone by a decision on the other squadra, there is
                # nobody to share the place with: it is a place like any other
                q.data["tied"] = len(block) > 1
        i += len(block)
    return Result(placings=ordered, columns=["time"], pending=missing)


# ── team helpers ────────────────────────────────────────────────────────────

def team_bibs(team, riders: dict) -> list[int]:
    """Bibs of a team's riders, in order."""
    return [riders[k].bib for k in team.riders
            if k in riders and riders[k].bib is not None]


def entrant_label(key: str, riders: dict, teams: dict, pairs: dict) -> str:
    """Human label for a rider bib, a team key or a pair key."""
    if key in teams:
        return teams[key].label
    if key in pairs:
        return pairs[key].label
    for r in riders.values():
        if str(r.bib) == str(key):
            return f"{r.bib} {r.full_name}"
    return str(key)
