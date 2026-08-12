"""Keirin: the tournament of UCI 3.2.135, from the first round to the finals.

A keirin is not seeded off a qualifying race the way a velocità is seeded off
the 200 m: there is no time to rank anybody on, so the jury composes the first
round itself. What the app knows - and what the jury must not have to look up
while the track is waiting - is *how many batterie* that round has and what
happens to the riders in them: the number of riders entered picks one row of
the UCI table, and that row fixes the whole tournament.

    da 29 a 42:  1° turno 6 batterie, il vincitore di ognuna in semifinale
                 recuperi 6 batterie, il vincitore di ognuna in semifinale
                 semifinali 2 batterie, i primi 3 alla finale 1°-6°,
                 gli altri alla finale 7°-12°

Two matrices do the composing, and neither of them is guessed:

* the **repechages** take the riders each batteria did not qualify and spread
  them so that as few as possible meet again - the firsts left behind in heat
  order, the seconds backwards, the thirds backwards from one place further
  round. With four batterie of seven that is the UCI 28-rider table line for
  line (`test_keirin.py`).
* the **round that follows** deals the qualifiers one *place* at a time - all
  the winners, then all the seconds, then the repêchés - snaking each block and
  turning it round between one block and the next, so that the winner of a
  batteria and the rider it beat do not line up together again. That is the
  same UCI example's semifinals, line for line.

Nothing here knows about storage or about Streamlit: the tables are data and
the composition is arithmetic over lists of entrant keys (dorsali, as strings).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..i18n import ordinal
from ..models import Status
from .base import CLASSIFIED, Placing, Result, sort_by_status

# The rounds a keirin is ridden in, as the programme names them. The repechages
# are *not* one of them: they are the second race of the round that sends riders
# to them, exactly as in a velocità (see `core.race`, § keirin).
#: **Programme vocabulary, not a label.** These strings are the keys the
#: rounds are scheduled under in `programme.yaml` and saved under in
#: `races/<id>.json`: translating them would stop the app finding a race.
#: What the jury *reads* is in `core.i18n`.
TURNO1 = "Turno 1"
QUARTI = "Quarti"
SEMI = "Semifinali"
FINALI = "Finali"

#: What the recuperi are called on the sheets that publish them. Not a round:
#: they are ridden inside the one whose batterie they take the riders from.
REPECHAGES = "Recuperi"


# ── the UCI table ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Stage:
    """One round of the tournament, as the table gives it.

    `qualify` riders per batteria go through to the next round; the others ride
    the repechages of this same round, when it has any, and `rep_qualify` of
    each of those go through as well.
    """

    key: str
    heats: int
    qualify: int
    rep_heats: int = 0
    rep_qualify: int = 0

    @property
    def repechages(self) -> bool:
        return self.rep_heats > 0 and self.rep_qualify > 0

    @property
    def through(self) -> int:
        """How many riders this round sends on, repechages included."""
        return self.heats * self.qualify + self.rep_heats * self.rep_qualify


@dataclass(frozen=True)
class Scheme:
    """How a keirin of this many riders is run: one row of UCI 3.2.135."""

    lo: int
    hi: int
    stages: tuple[Stage, ...]

    def stage(self, round_key: str) -> Stage | None:
        return next((s for s in self.stages if s.key == round_key), None)

    def next_key(self, round_key: str) -> str:
        """The round after this one - `FINALI` at the end of the tournament."""
        keys = [s.key for s in self.stages]
        if round_key not in keys:
            return ""
        i = keys.index(round_key)
        return keys[i + 1] if i + 1 < len(keys) else FINALI

    @property
    def last(self) -> Stage:
        """The round the two finals come out of."""
        return self.stages[-1]

    @property
    def rounds(self) -> list[str]:
        """Every round ridden, the finals included."""
        return [s.key for s in self.stages] + [FINALI]

    @property
    def final_size(self) -> int:
        """How many ride the first final: what the last round sends through."""
        return self.last.heats * self.last.qualify


#: UCI 3.2.135, the whole table. Read a row as: first round `heats` batterie,
#: `qualify` through from each, the rest to `rep_heats` repechages with
#: `rep_qualify` through from each - and so on down the stages. Every row ends
#: with two semifinali of six that send three each to the final 1°-6°, which is
#: why every band from 15 riders up finishes the same way.
SCHEMES: tuple[Scheme, ...] = (
    # 10-14: no repechages and no semifinals - the two batterie of the first
    # round *are* the tournament, and their top three ride for the title
    Scheme(10, 14, (Stage(TURNO1, 2, 3),)),
    Scheme(15, 21, (Stage(TURNO1, 3, 2, 3, 2), Stage(SEMI, 2, 3))),
    Scheme(22, 28, (Stage(TURNO1, 4, 2, 4, 1), Stage(SEMI, 2, 3))),
    Scheme(29, 42, (Stage(TURNO1, 6, 1, 6, 1), Stage(SEMI, 2, 3))),
    # from 43 riders up a quarter-final is ridden, with repechages of its own
    Scheme(43, 49, (Stage(TURNO1, 7, 1, 6, 2), Stage(QUARTI, 3, 2, 2, 3),
                    Stage(SEMI, 2, 3))),
    Scheme(50, 56, (Stage(TURNO1, 8, 1, 7, 2), Stage(QUARTI, 4, 2, 2, 2),
                    Stage(SEMI, 2, 3))),
    Scheme(57, 63, (Stage(TURNO1, 9, 1, 8, 2), Stage(QUARTI, 4, 2, 4, 1),
                    Stage(SEMI, 2, 3))),
    Scheme(64, 70, (Stage(TURNO1, 10, 1, 9, 2), Stage(QUARTI, 4, 2, 4, 1),
                    Stage(SEMI, 2, 3))),
)


def scheme_for(n_riders: int) -> Scheme:
    """The row of the table this many riders are run under.

    Below the table (a categoria that turns up with eight riders, which happens)
    the smallest row still reads correctly: two batterie, the first three of
    each in the final for the title. Above it, the largest.
    """
    for sch in SCHEMES:
        if sch.lo <= n_riders <= sch.hi:
            return sch
    return SCHEMES[0] if n_riders < SCHEMES[0].lo else SCHEMES[-1]


# ── reading a round's results ───────────────────────────────────────────────

def _ranked(order: list[str], statuses: dict[str, Status]) -> list[str]:
    """The riders of one batteria that its result classifies, in finishing order.

    A declassata is classified - she keeps the place she was given, at the back
    of the ones she was put behind - and a DNS, a DNF or a DSQ is not: neither
    qualifies for anything, and neither goes to the repechages.
    """
    return [k for k in order if statuses.get(k, Status.OK) in CLASSIFIED]


def qualified(orders: list[list[str]], qualify: int,
              statuses: dict[str, Status] | None = None) -> list[list[str]]:
    """Who goes through, one *place* at a time: [[the winners], [the 2nds], …].

    Blocks and not one flat list, because that is how the next round is
    composed: the winners are spread over the batterie first, then the seconds
    the other way round (see `spread`).
    """
    statuses = dict(statuses or {})
    ranked = [_ranked(o, statuses) for o in orders]
    return [[heat[p] for heat in ranked if p < len(heat)]
            for p in range(max(0, qualify))]


def not_qualified(orders: list[list[str]], qualify: int,
                  statuses: dict[str, Status] | None = None) -> list[list[str]]:
    """Per batteria, the riders it did not qualify - the ones the repechages ride."""
    statuses = dict(statuses or {})
    return [_ranked(o, statuses)[qualify:] for o in orders]


def left_behind(orders: list[list[str]], qualify: int,
                statuses: dict[str, Status] | None = None) -> list[str]:
    """Everybody this round leaves behind, best first.

    All the riders placed just under the cut, in batteria order, then all the
    ones under those, and so on - which is how UCI ranks them ("all ranked 13,
    all ranked 17"): with one line per rider, the batteria order breaks the tie.
    The riders the result does not classify come last: they are still out here,
    and the classification files them with their decision.
    """
    statuses = dict(statuses or {})
    rest = not_qualified(orders, qualify, statuses)
    depth = max((len(h) for h in rest), default=0)
    out = [h[p] for p in range(depth) for h in rest if p < len(h)]
    return out + [k for o in orders for k in o
                  if statuses.get(k, Status.OK) not in CLASSIFIED]


# ── composing the batterie ──────────────────────────────────────────────────

def spread(blocks: list[list[str]], n_heats: int) -> list[list[str]]:
    """Deal blocks of qualifiers over `n_heats`, one block at a time.

    Inside a block the riders snake - first heat, second, … and back - which is
    the seeding every UCI table is built on. Between one block and the next the
    snake starts from the other end, so that the winner of a batteria and the
    rider she beat in it are dealt to *different* batterie: with four heats of
    seven this is the semifinal table of the 28-rider example, QA1/QD1/QB2/QC2
    against QB1/QC1/QA2/QD2.
    """
    heats: list[list[str]] = [[] for _ in range(max(n_heats, 0))]
    if not heats:
        return []
    for b, block in enumerate(blocks):
        for i, key in enumerate(block):
            row, col = divmod(i, n_heats)
            forward = (row % 2 == 0) == (b % 2 == 0)
            heats[col if forward else n_heats - 1 - col].append(key)
    return heats


def repechage_heats(left: list[list[str]], n_heats: int) -> list[list[str]]:
    """The repechages, from the riders each batteria of the round left behind.

    `left[i]` are the riders batteria i+1 did not qualify, in finishing order.
    They are dealt one *place* at a time, and the order the batterie are read in
    turns round after the first row and moves on by one at every row after that:

        A B C D      the first riders left behind, in batteria order
        D C B A      the ones under them, backwards
        C B A D      and one further round for every row after
        B A D C
        A D C B

    which is the UCI repechage table of the 28-rider example, line for line. It
    is not decoration: read straight down, each repechage takes at most one
    rider from any batteria until there are more rows than batterie, so nobody
    lines up again against somebody already beaten.
    """
    heats: list[list[str]] = [[] for _ in range(max(n_heats, 0))]
    if not heats or not left:
        return []
    n = len(left)
    depth = max(len(h) for h in left)
    slot = 0
    for row in range(depth):
        # row 0 reads the batterie forwards; every row after reads them
        # backwards, starting one batteria further on each time
        order = list(range(n)) if row == 0 else \
            [(- 1 - i - (row - 1)) % n for i in range(n)]
        for src in order:
            if row < len(left[src]):
                heats[slot % n_heats].append(left[src][row])
                slot += 1
    return heats


def next_heats(stage: Stage, orders: list[list[str]],
               rep_orders: list[list[str]], n_heats: int,
               statuses: dict[str, Status] | None = None,
               rep_statuses: dict[str, Status] | None = None
               ) -> list[list[str]]:
    """The batterie of the round that follows `stage`.

    The qualifiers of the round come first, place by place, then the ones the
    repechages sent back in - each of those a block of its own, so that they are
    spread the same way (`spread`).
    """
    blocks = qualified(orders, stage.qualify, statuses)
    if stage.repechages:
        blocks += qualified(rep_orders, stage.rep_qualify, rep_statuses)
    return spread(blocks, n_heats)


def final_heats(orders: list[list[str]], qualify: int,
                statuses: dict[str, Status] | None = None
                ) -> tuple[list[str], list[str]]:
    """(the final for the title, the other one) out of the last round ridden.

    The first `qualify` of every batteria ride for the places the tournament is
    won in - 1°-6° when two semifinali send three each - and everybody else
    rides the final under it. Both are read place by place: the winners of the
    semifinali first, then the seconds, which is the order they lined up in.
    """
    statuses = dict(statuses or {})
    top = [k for block in qualified(orders, qualify, statuses) for k in block]
    return top, left_behind(orders, qualify, statuses)


def final_labels(n_top: int, n_rest: int) -> tuple[str, str]:
    """('1°-6°', '7°-12°') - what each final rides for, from how many ride it.

    Not a constant: ten riders in two batterie make a final 1°-6° and a final
    7°-10°, which is the smallest keirin 3.2.135 allows.
    """
    top = f"{ordinal(1)}-{ordinal(n_top)}" if n_top > 1 else ordinal(1)
    if n_rest <= 0:
        return top, ""
    first = n_top + 1
    last = n_top + n_rest
    return top, (f"{ordinal(first)}-{ordinal(last)}" if last > first
                 else ordinal(first))


def in_bib_order(heats: list[list[str]]) -> list[list[str]]:
    """Every batteria sorted by dorsale - the order a start order is read in.

    Who is composed against whom is the tournament's business; the *sheet* is
    read out loud at the gate, and there the numbers go up. Anything that is not
    a number keeps its place at the back rather than blowing up the sort.
    """
    def num(key: str):
        return (0, int(key)) if str(key).isdigit() else (1, 0)

    return [sorted(heat, key=num) for heat in heats]


# ── the classification of the whole event ───────────────────────────────────

def classification(finals: list[list[str]],
                   eliminated: list[tuple[str, list[str]]], *,
                   statuses: dict[str, Status] | None = None) -> Result:
    """Places from the two finals, everybody else by how far they got.

    `finals` are the two finals in the order they rank - the one for the title
    first - and `eliminated` is (round name, riders left behind) earliest round
    first: a rider knocked out in the semifinali finishes ahead of one knocked
    out in the recuperi of the first round, and inside one round they are
    ordered as `left_behind` reads them.

    A keirin has no qualifying time to fall back on - the first round is the
    first race of the event - so how far a rider got is all there is to rank her
    on, and that is what the UCI table itself says ("all ranked 13").
    """
    statuses = dict(statuses or {})
    order: list[str] = []
    seen: set[str] = set()

    def add(keys):
        for key in keys:
            if key and key not in seen:
                seen.add(key)
                order.append(key)

    for heat in finals:
        add(heat)
    for _round_name, keys in reversed(eliminated):
        add(keys)

    placings = [Placing(key=k, status=statuses.get(k, Status.OK)) for k in order]
    n = 0
    for p in placings:
        if p.status in CLASSIFIED:
            n += 1
            p.position = n
    return Result(placings=sort_by_status(placings))
