"""Velocità and Keirin: round-based brackets.

Composition follows the UCI tables in Part 3(`regulations/part3_UCI.md`):

* heats are seeded **serpentine** on the current ranking - with two riders per
  heat that is the familiar mirror pairing `N1-N24, N2-N23, …`, and with seven
  riders it reproduces the keirin table `A: R1 R8 R9 R16 R17 R24 R25`;
* the riders who do not qualify go to the repechages, composed the same way
  over the losers in order;
* riders knocked out in a round are ranked below those knocked out later, and
  among themselves by the 200 m qualifying time.

Nothing here is hard-coded to a particular bracket: the number of heats and how
many advance come from `programme.yaml`, so a category with fewer entries runs
a shorter bracket without a code change.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from ..i18n import msg, ui
from ..models import Status
from ..parse import duplicates
from .base import CLASSIFIED, Placing, Result, sort_by_status


# ── composition ─────────────────────────────────────────────────────────────

def serpentine_heats(ranking: list[str], n_heats: int) -> list[list[str]]:
    """Distribute a ranking over `n_heats` in snake order (UCI seeding)."""
    if n_heats <= 0:
        return []
    heats: list[list[str]] = [[] for _ in range(n_heats)]
    for i, key in enumerate(ranking):
        row, col = divmod(i, n_heats)
        heats[col if row % 2 == 0 else n_heats - 1 - col].append(key)
    return heats


def compose_round(ranking: list[str], *, heat_size: int = 2,
                  n_heats: int | None = None) -> list[list[str]]:
    """Heats for a round, from the ranking that feeds it."""
    if not ranking:
        return []
    if n_heats is None:
        n_heats = max(1, ceil(len(ranking) / max(heat_size, 1)))
    return [h for h in serpentine_heats(ranking, n_heats) if h]


# ── one round ───────────────────────────────────────────────────────────────

class RoundOutcome:
    """Who advanced and who went out, for one round."""

    def __init__(self, advancing: list[str], eliminated: list[str],
                 warnings: list[str], placings: dict[str, tuple[int, int]]):
        self.advancing = advancing
        self.eliminated = eliminated        # best first
        self.warnings = warnings
        self.placings = placings            # key -> (heat index, place in heat)


def round_outcome(heats: list[list[str]], orders: list[list[str]], *,
                  qualify: int = 1,
                  statuses: dict[str, Status] | None = None) -> RoundOutcome:
    """Resolve a round from the heat compositions and their finishing orders."""
    statuses = dict(statuses or {})
    warnings: list[str] = []
    advancing: list[str] = []
    per_place: dict[int, list[str]] = {}
    placings: dict[str, tuple[int, int]] = {}

    flat = [k for h in heats for k in h]
    for dup in duplicates(flat):
        warnings.append(msg("key_in_two_heats", who=dup))

    for h, heat in enumerate(heats):
        order = orders[h] if h < len(orders) else []
        unknown = [k for k in order if k not in heat]
        for k in unknown:
            warnings.append(msg("not_in_this_heat", who=k, n=h + 1))
        ranked = [k for k in order if k in heat]
        ranked += [k for k in heat if k not in ranked]      # not yet finished
        if not order:
            warnings.append(msg("heat_no_result", n=h + 1))
        # places are counted among the riders who actually raced, so a DNS
        # does not take a qualifying slot from the rider behind it
        place = 0
        for key in ranked:
            if statuses.get(key, Status.OK) not in CLASSIFIED:
                placings[key] = (h, None)
                continue
            placings[key] = (h, place)
            if order and place < qualify:
                advancing.append(key)
            else:
                per_place.setdefault(place, []).append(key)
            place += 1

    # non-qualifiers rank by their place in the heat: all the 2nds, then the 3rds
    eliminated = [k for place in sorted(per_place) for k in per_place[place]]
    return RoundOutcome(advancing, eliminated, warnings, placings)


# ── final classification ────────────────────────────────────────────────────

def bracket_classification(final_orders: dict[str, list[list[str]]],
                           eliminated_by_round: list[tuple[str, list[str]]],
                           *, qual_ranking: list[str] | None = None,
                           statuses: dict[str, Status] | None = None) -> Result:
    """Assemble the whole event's classification.

    `final_orders` maps a final's name to its heats' finishing orders, best
    final first: `{"Finali 1-4": [[a, b], [c, d]], "Finali 5-8": [[...]]}`
    gives places 1-2 to the first heat and 3-4 to the second, then 5-8.
    `eliminated_by_round` is ordered earliest round first; riders eliminated
    later finish ahead of those eliminated earlier.
    """
    statuses = dict(statuses or {})
    qual_rank = {k: i for i, k in enumerate(qual_ranking or [])}
    order: list[str] = []
    seen: set[str] = set()

    for name in final_orders:
        for heat in final_orders[name]:
            for key in heat:
                if key not in seen:
                    seen.add(key)
                    order.append(key)

    for _round_name, keys in reversed(eliminated_by_round):
        for key in sorted(keys, key=lambda k: qual_rank.get(k, 10 ** 6)):
            if key not in seen:
                seen.add(key)
                order.append(key)

    for key in (qual_ranking or []):
        if key not in seen:
            seen.add(key)
            order.append(key)

    placings = [Placing(key=k, status=statuses.get(k, Status.OK)) for k in order]
    n = 0
    for p in placings:
        if p.status in CLASSIFIED:
            n += 1
            p.position = n
    return Result(placings=sort_by_status(placings))


def next_round_ranking(outcome: RoundOutcome, qual_ranking: list[str]
                       ) -> list[str]:
    """Advancing riders, re-seeded on their qualification order."""
    rank = {k: i for i, k in enumerate(qual_ranking)}
    return sorted(outcome.advancing, key=lambda k: rank.get(k, 10 ** 6))


# ── the velocità as it is actually ridden ───────────────────────────────────
#
# A velocità is not a bracket the app invents round by round: it is one of a
# handful of *schemes*, decided before the 200 m are ridden and printed on the
# start order ("Si qualificano per il 1° turno i migliori 12 tempi"). The scheme
# fixes how many qualify, which rounds are ridden, and - this is the part that
# was done by hand - which loser of which heat lines up against whom in the
# next one. Everything below is that table, and nothing in it is guessed.

#: **Programme vocabulary, not a label.** These strings are the keys the
#: rounds are scheduled under in `programme.yaml` and saved under in
#: `races/<id>.json`: translating them would stop the app finding a race.
#: What the jury *reads* is in `core.i18n`.
TURNO1 = "Turno 1"
QUARTI = "Quarti"
SEMI = "Semifinali"
FINALI = "Finali"

#: Rounds ridden as two runs plus a decider, instead of one straight race.
BEST_OF_THREE = (QUARTI, SEMI, FINALI)


@dataclass(frozen=True)
class Scheme:
    """One way of running a velocità, from the 200 m to the classification."""

    key: str
    # The two lines a scheme is read by are held as catalogue keys and looked
    # up when they are asked for: a scheme is a module constant, built at
    # import, and a word frozen there would be in whatever language the app
    # started in rather than the one the competition is run in.
    label_key: str            # what the dropdown says
    qualify: int              # how many the 200 m qualify
    rounds: tuple[str, ...]   # the rounds ridden, in order
    note_key: str             # the decision the qualifying start order opens on
    repechage: bool = False   # a repechage inside the first round

    @property
    def label(self) -> str:
        return ui(self.label_key)

    @property
    def note(self) -> str:
        return msg(self.note_key)

    def next_round(self, round_key: str) -> str:
        """The round that follows this one, '' at the end of the event."""
        rounds = list(self.rounds)
        if round_key not in rounds:
            return ""
        i = rounds.index(round_key)
        return rounds[i + 1] if i + 1 < len(rounds) else ""


SCHEMES: dict[str, Scheme] = {
    "12": Scheme(
        key="12",
        label_key="scheme_12",
        qualify=12,
        rounds=(TURNO1, QUARTI, SEMI, FINALI),
        note_key="note_scheme_12",
        repechage=True),
    "8": Scheme(
        key="8",
        label_key="scheme_8",
        qualify=8,
        rounds=(QUARTI, SEMI, FINALI),
        note_key="note_scheme_8"),
}

DEFAULT_SCHEME = "12"


def scheme(key: str) -> Scheme:
    """The scheme by key, falling back to the one with the repechages."""
    return SCHEMES.get(str(key or ""), SCHEMES[DEFAULT_SCHEME])


# ── how each round is composed ──────────────────────────────────────────────

def mirror_pairs(ranked: list[str]) -> list[list[str]]:
    """1-N, 2-(N-1), … - the pairing every round of a velocità is seeded with.

    Twelve qualified give six batterie (1-12, 2-11, …); the same table pairs
    the eight of the quarti and the four of the semifinali. An odd rider at the
    bottom has nobody left to meet and is dropped by the caller's arithmetic,
    not silently paired with himself.
    """
    return [[ranked[i], ranked[-1 - i]] for i in range(len(ranked) // 2)]


#: Repechages of the first round (UCI table): which heats' losers meet.
#: Six losers ride two batterie of three - 1, 4, 6 against 2, 3, 5 - so that no
#: batteria of the first round sends two riders into the same repechage.
REPECHAGE_TABLE: dict[int, tuple[tuple[int, ...], ...]] = {
    6: ((1, 4, 6), (2, 3, 5)),
    4: ((1, 4), (2, 3)),
}


def repechage_heats(losers: list[str]) -> list[list[str]]:
    """The repechage batterie, from the losers of the first round in heat order.

    `losers[i]` is the rider beaten in batteria i+1. Outside the table - a
    first round of a size these championships do not run - the losers are
    seeded serpentine over heats of three, which is the same idea generalised.
    """
    table = REPECHAGE_TABLE.get(len(losers))
    if not table:
        return compose_round(losers, heat_size=3)
    return [[losers[n - 1] for n in row] for row in table]


def quarter_heats(winners: list[str], repechage_winners: list[str] = ()
                  ) -> list[list[str]]:
    """The quarti: the first round's winners in order, then who came back.

    The repêchés are the last two of the eight, so the first batteria of the
    first round meets the winner of the *second* repechage and the second meets
    the winner of the first - the pairing the jury draws by hand.
    """
    return mirror_pairs(list(winners) + list(repechage_winners))


def semifinal_heats(quarter_winners: list[str]) -> list[list[str]]:
    """1° against 4°, 2° against 3° - by the batteria they won, not by time."""
    return mirror_pairs(list(quarter_winners))


def final_5_8_heat(quarter_losers: list[str]) -> list[list[str]]:
    """The 5°-8° final: one race of four, the riders beaten in the quarti."""
    losers = [k for k in quarter_losers if k]
    return [losers] if losers else []


def final_heats(semi_winners: list[str], semi_losers: list[str]
                ) -> list[list[str]]:
    """The finals in the order they are ridden: the 3°/4° first, then the 1°/2°."""
    out = []
    if len(semi_losers) >= 2:
        out.append(list(semi_losers[:2]))
    if len(semi_winners) >= 2:
        out.append(list(semi_winners[:2]))
    return out


# ── best of three ───────────────────────────────────────────────────────────

def heat_winner(runs: list[str], sides: list[str], *, wins: int = 2) -> str:
    """Who took the batteria, from the winner of each prova. '' while open.

    Two prove and a decider: whoever wins two of them has won, and the bella is
    not ridden when the same rider took both prove - which is why it prints as
    *ev. bella* and stays empty more often than not.
    """
    won = {k: 0 for k in sides}
    for r in runs:
        if r in won:
            won[r] += 1
    for key, n in won.items():
        if n >= wins:
            return key
    return ""


def heat_result(runs: list[str], sides: list[str], *, wins: int = 2
                ) -> list[str]:
    """The batteria's finishing order (winner first), [] while it is open."""
    winner = heat_winner(runs, sides, wins=wins)
    if not winner:
        return []
    return [winner] + [k for k in sides if k != winner]


# ── the classification of the whole event ───────────────────────────────────

def scheme_classification(*, finals: list[list[str]],
                          final_5_8: list[str] = (),
                          qual_ranking: list[str] = (),
                          statuses: dict[str, Status] | None = None) -> Result:
    """Places from the finals, everybody else on the 200 m.

    `finals` are the finals as they were ridden - the 3°/4° first, then the
    1°/2° - so the sheet is read off the same list the track ran. `final_5_8`
    is the 5°-8° when it was ridden and empty when it was not: with the finals
    1°-4° alone the classification goes on with the 200 m from the fifth place,
    which is the only race the riders under the finals all rode. A rider
    knocked out in the first round and one knocked out in the quarti are
    separated by that race and by nothing else.
    """
    statuses = dict(statuses or {})
    order: list[str] = []
    seen: set[str] = set()

    def add(keys):
        for key in keys:
            if key and key not in seen:
                seen.add(key)
                order.append(key)

    # the 1°/2° final is ridden last and read first
    for heat in reversed(list(finals)):
        add(heat)
    add(final_5_8)
    add(qual_ranking)

    placings = [Placing(key=k, status=statuses.get(k, Status.OK)) for k in order]
    n = 0
    for p in placings:
        if p.status in CLASSIFIED:
            n += 1
            p.position = n
    return Result(placings=sort_by_status(placings))
