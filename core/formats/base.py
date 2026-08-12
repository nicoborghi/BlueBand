"""Shared result model for every race format.

A format takes the startlist plus whatever the jury typed and returns an
ordered list of `Placing`. Sorting is the same everywhere: classified entrants
by their own result, then REL, DNF, DNS, NP, DSQ - one convention replacing the
three incompatible sentinel schemes of the old track.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..i18n import ordinal
from ..models import LEFT_RACE, STATUS_ORDER, Status, status_of


@dataclass
class Placing:
    """One entrant's result in one race."""

    key: str                       # rider bib as str, or team / pair key
    position: int | None = None    # None = not classified (or still racing)
    status: Status = Status.OK
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        """What goes in the 'Ris.' column.

        A relegated entrant is still classified - it is moved to the back but
        keeps a place - so it prints as e.g. '8° REL'. DNF/DNS/DSQ/NP are not
        classified and print as the bare status.

        A place shared *a pari merito* - a final of an inseguimento the jury
        left unridden - prints as the place itself, twice: both entrants are
        2°, or both 4°, and the place above stays empty.
        """
        if self.status is Status.REL:
            return f"{ordinal(self.position)} REL" if self.position else "REL"
        if self.status is not Status.OK:
            return self.status.value
        return ordinal(self.position) if self.position else ""


@dataclass
class Result:
    """A format's output: the classification plus anything the jury must see."""

    placings: list[Placing] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)   # extra data columns
    pending: int = 0               # entrants without a result yet (live sheets)

    def by_key(self, key: str) -> Placing | None:
        return next((p for p in self.placings if p.key == key), None)

    @property
    def order(self) -> list[str]:
        return [p.key for p in self.placings]


def leaving_order(statuses: dict[str, Status]) -> dict[str, int]:
    """Rank inside DNF and ABD: whoever left the race last comes first.

    A prova di gruppo is not over for the riders who leave it - they are still
    classified behind the finishers, and among themselves by how far they got.
    The jury has no lap chart for that, but it does have the order it wrote the
    numbers down in: the field is typed as the riders come off the track, so
    the *last* number typed is the one who rode longest and heads them.

    The order of the field is the order of the dict: the status fields rewrite
    their whole group on every run (`race.set_statuses_from_text`), so what is
    stored is what was typed, left to right.
    """
    out: dict[str, int] = {}
    for status in LEFT_RACE:
        group = [k for k, v in statuses.items() if v is status]
        out.update({k: -i for i, k in enumerate(group)})
    return out


def sort_placings(placings: list[Placing],
                  tiebreak: dict[str, float] | None = None,
                  order: dict[str, int] | None = None) -> list[Placing]:
    """Classified first (by position), then the non-classified by status.

    `order` ranks entrants *inside* one status - the ritirati by the moment
    they left the race, see `leaving_order`. It is nothing to the classified,
    who are separated by their own result long before it is read.
    """
    tb = tiebreak or {}
    seq = order or {}

    def key(p: Placing):
        return (STATUS_ORDER.get(p.status, 9), seq.get(p.key, 0),
                p.position if p.position is not None else 10 ** 6,
                tb.get(p.key, 0))

    return sorted(placings, key=key)


def sort_by_status(placings: list[Placing],
                   order: dict[str, int] | None = None) -> list[Placing]:
    """Move the non-classified to the bottom, keeping the current order intact.

    Use this when positions are already computed (elimination, brackets):
    `sort_placings` would re-order by position and lose a deliberate ordering.
    """
    seq = order or {}
    return sorted(placings, key=lambda p: (STATUS_ORDER.get(p.status, 9),
                                           seq.get(p.key, 0)))


CLASSIFIED = (Status.OK, Status.REL)


def assign_positions(placings: list[Placing]) -> list[Placing]:
    """Number the classified entrants 1..n in their current order."""
    n = 0
    for p in placings:
        if p.status in CLASSIFIED:
            n += 1
            p.position = n
        else:
            p.position = None
    return placings


def statuses_from(state_statuses: dict[str, str]) -> dict[str, Status]:
    return {k: status_of(v) for k, v in (state_statuses or {}).items()}


def split_out(entrants: Iterable[str], statuses: dict[str, Status]
              ) -> tuple[list[str], list[str]]:
    """(still racing, out) - everything but OK/REL is out, and REL keeps a place."""
    racing, out = [], []
    for e in entrants:
        s = statuses.get(e, Status.OK)
        (racing if s in CLASSIFIED else out).append(e)
    return racing, out
