"""Il medagliere: how many first, second and third places each squadra took.

One question, asked at the end of every championship - *how did we do* - and
one honest answer. The count is built from what the jury has actually filed,
never from a guess:

* a **specialità is counted once**, on its final classification. Which race
  that is depends on the format: an omnium, a velocità and a keirin are
  decided across every round (`race.*_standings`), everything else on the last
  round the programme lists that has a result;
* a specialità whose last round is still empty is **not concluded** and is
  reported as such rather than counted from a qualifying round. The caller
  decides whether to include it (a championship read at the end of day one is
  half provisional, and the jury knows it);
* a medal goes to the **squadra**, under whatever "squadra" means here -
  regione, società, provincia or nazione (`recap.group_of`). A quartetto or a
  coppia counts once for each distinct squadra behind it, which is one of them
  at a regional championship and can be several when the grouping is by
  società.

Nothing here writes, composes or classifies anything the app does not already
compute: a race that cannot be classified is skipped, with the reason kept on
`Podium.warnings`, so a broken file costs its own line and not the page.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import race as R
from . import recap as RC
from .config import Competition
from .formats.base import Result
from .i18n import label
from .models import EntryList, Status

#: The places a medagliere counts. Fourth place is not a medal, and a table
#: that carried it would stop being the one the jury is asked for.
MEDALS = (1, 2, 3)


@dataclass
class Podium:
    """One podium place of one specialità, with the squadra behind it."""

    cat: str
    event: str
    position: int
    key: str                   # entrant key: bib, team key or pair key
    label: str                 # what it rides under ("LOMBARDIA A", "17")
    names: list[str] = field(default_factory=list)   # the riders, by name
    teams: list[str] = field(default_factory=list)   # the squadre credited
    round_key: str = ""        # where the classification came from
    complete: bool = True      # False: the last round has no result yet


@dataclass
class TeamMedals:
    """One line of the medagliere."""

    team: str
    gold: int = 0
    silver: int = 0
    bronze: int = 0

    @property
    def total(self) -> int:
        return self.gold + self.silver + self.bronze

    def count(self, position: int) -> None:
        if position == 1:
            self.gold += 1
        elif position == 2:
            self.silver += 1
        elif position == 3:
            self.bronze += 1

    @property
    def sort_key(self) -> tuple:
        """Ranked the way a medagliere is: golds first, then silvers, then
        bronzes, then alphabetically. A single gold stands above any number of
        silvers - that is what the table is for."""
        return (-self.gold, -self.silver, -self.bronze, self.team.lower())


# ── the final classification of one specialità ──────────────────────────────

#: Formats decided across every round rather than on the last one.
AGGREGATE = ("omnium", "sprint", "keirin")


def deciding_rounds(comp: Competition, cat: str, event: str) -> list[str]:
    """The rounds a final classification can come from, in programme order.

    The batterie are left out: they qualify, they do not place. So is the
    composition round, which is not ridden at all.
    """
    rounds = R.final_rounds(comp, cat, event)
    return rounds or [r.key for r in comp.rounds(cat, event)]


def last_placing_round(store, comp: Competition, el: EntryList, cat: str,
                       event: str) -> tuple[str, Result | None]:
    """(round key, its classification) - the last round that actually places.

    Walked backwards from the end of the programme: the first round that has
    been saved *and* classifies somebody is the one that decided the event. A
    round saved with a startlist and no result answers nothing and is passed
    over, which is what makes a half-run event show up as not concluded
    instead of being counted off its qualifying.
    """
    for key in reversed(deciding_rounds(comp, cat, event)):
        state = store.load_race(R.race_key(cat, event, key))
        if state is None or not ridden(state, comp):
            continue
        result = _classify(state, el, comp)
        if result is not None and any(p.position for p in result.placings):
            return key, result
    return "", None


def final_result(store, comp: Competition, el: EntryList, cat: str,
                 event: str) -> tuple[Result | None, str, bool]:
    """(classification, round it came from, whether the event is concluded).

    `None` when the specialità has no result at all. The event is concluded
    when the last round of its programme is the one that placed the field:
    anything earlier means the jury has more racing to run, and the standings
    are still provisional.
    """
    rounds = deciding_rounds(comp, cat, event)
    where, result = last_placing_round(store, comp, el, cat, event)
    if result is None:
        return None, "", False
    complete = bool(rounds) and where == rounds[-1]

    if comp.event(event).fmt in AGGREGATE:
        # decided across every round: the aggregate is the classification, and
        # the last round having placed its own field is what says it is over
        aggregate = _standings(store, comp, el, cat, event)
        if aggregate is not None and any(p.position
                                         for p in aggregate.placings):
            return aggregate, "", complete
    return result, where, complete


def ridden(state, comp: Competition) -> bool:
    """Whether the jury has entered what decides this race.

    A saved race is not a result: every round is written to disk the moment
    its ordine di partenza is composed, hours before it is ridden. For most
    formats that is harmless - a race against the clock with no times places
    nobody, a bracket with no batterie ordered places nobody - but **a prova
    di gruppo classifies its startlist even when nothing has been typed**: with
    no volate everybody is on nought points and the arrival comes out in
    dorsale order. Counted as a podium, that hands the title to the lowest
    number in the race.

    So the bunch races are asked for the field that decides them - the
    arrival, the riders eliminated - and everything else is left to its own
    classification, which already answers honestly.
    """
    kind = state.fmt or R.round_format(comp, state.cat, state.event,
                                       state.round_key)
    payload = state.payload or {}
    if kind == R.ELIMINATION:
        return bool(str(payload.get("eliminated", "")).strip())
    if kind in R.BUNCH:
        return bool(str(payload.get("sprints", "")).strip())
    return True


def _classify(state, el: EntryList, comp: Competition) -> Result | None:
    """`race.classify`, but a race that cannot be read costs only itself."""
    try:
        return R.classify(state, el, comp)
    except Exception:                                    # noqa: BLE001
        return None


def _standings(store, comp: Competition, el: EntryList, cat: str,
               event: str) -> Result | None:
    """The aggregate classification of an omnium / velocità / keirin.

    The same three calls the race page makes for the *classifica finale*
    sheet (`ui.pages.races._standings`), guarded: these read every round of
    the event off disk, and a medagliere must not go down with one of them.
    """
    fmt = comp.event(event).fmt
    try:
        if fmt == "omnium":
            return R.omnium_standings(store, comp, el, cat, event)
        if fmt == "sprint":
            return R.sprint_standings(store, comp, el, cat, event)
        if fmt == "keirin":
            return R.keirin_standings(store, comp, el, cat, event)
    except Exception:                                    # noqa: BLE001
        return None
    return None


# ── who a place belongs to ──────────────────────────────────────────────────

def teams_of(key: str, el: EntryList, cat: str,
             group: str = RC.DEFAULT_GROUP) -> list[str]:
    """The squadre behind an entrant key, in order and without repeats.

    One name for a rider; one for a quartetto or a coppia of a regional
    championship; several only where the grouping cuts across the squadra that
    was entered - riders of three società in one quartetto regionale. Each of
    them is credited with the place: the alternative is crediting none.
    """
    out: list[str] = []
    for rider in R.entrant_riders(key, el, cat):
        name = RC.group_of(rider, group)
        if name and name not in out:
            out.append(name)
    if out:
        return out
    # a team or a coppia whose riders are not on the list any more still knows
    # which regione entered it
    entity = el.teams.get(key) or el.pairs.get(key)
    region = (getattr(entity, "region", "") or "").strip()
    return [region] if region and group == RC.BY_REGION else []


def reserves_of(key: str, el: EntryList) -> list[str]:
    """The riders entered as reserves of a quartetto or a coppia."""
    entity = el.teams.get(key) or el.pairs.get(key)
    return list(getattr(entity, "reserves", None) or [])


def names_of(key: str, el: EntryList, cat: str, state=None) -> list[str]:
    """Who is on this place - the riders the race classified, and only them.

    For a quartetto or a coppia this is **the line-up of the race that decided
    the specialità**, exactly as that race's own classification prints it
    (`race.team_lineup`): the riders who rode it, then - marked `(ris)` - the
    rider a reserve took the place of, who is on the sheet because he rode the
    qualification and earned the squadra its time. A reserve entered and never
    used is on neither sheet, and is not named here either.

    Without the race - an aggregate classification, an individual entrant -
    the entrants are all there is, and a reserve who never rode is not one.
    """
    entity = el.teams.get(key) or el.pairs.get(key)
    if state is None or entity is None:
        return [r.full_name for r in R.entrant_riders(key, el, cat)]
    mark = label("reserve_short")
    return [f"{r.full_name} ({mark})" if replaced else r.full_name
            for r, replaced in R.team_lineup(state, key, el)]


def placing_keys(state, comp: Competition, el: EntryList) -> dict[str, str]:
    """placing key -> entrant key, where the race is not scored by entrant.

    A madison is called, scored and classified by **coppia number**: what is on
    the placing is the number the coppia raced under, not the coppia. Read as
    an entrant that number is a dorsale, and it matched whoever wears it in the
    category - one rider, and often one who is not even in the race. The race
    page reads it back through the same map (`race.status_keys`).

    Empty for every other format, where the placing already carries the
    entrant: a bib, a quartetto, a coppia key.
    """
    if state is None:
        return {}
    kind = state.fmt or R.round_format(comp, state.cat, state.event,
                                       state.round_key)
    return R.status_keys(state, el, kind)


# ── the medagliere ──────────────────────────────────────────────────────────

@dataclass
class Survey:
    """What one reading of the competition found.

    Both halves come out of the same pass: the podiums, and the specialità
    that are not concluded. Reading it twice would mean loading every race of
    the championship twice, on a page the jury opens between two races.
    """

    places: list[Podium] = field(default_factory=list)
    #: (categoria, specialità, whether anything at all has been filed)
    open_events: list[tuple[str, str, bool]] = field(default_factory=list)
    counted: int = 0        # specialità concluded and counted


def survey(store, comp: Competition, el: EntryList, *,
           group: str = RC.DEFAULT_GROUP, cats: list[str] | None = None,
           events: list[str] | None = None,
           include_unfinished: bool = False) -> Survey:
    """Read the whole competition once: podiums, and what is still open.

    `cats` and `events` restrict what is read (None = all of them);
    `include_unfinished` keeps the specialità whose last round has not been
    ridden yet, their places marked `complete=False`.
    """
    # A madison is scored by the number the jury gave the coppia in its setup
    # round, and that number lives on the entry list only once it has been
    # stamped there. Without this every madison was scored against the dorsale
    # of each coppia's first rider - the arrival the jury typed then matched
    # nobody, and the medagliere read a classification that was not the one on
    # the comunicato. The Gare, Partenti and Stampa pages each do the same
    # before they read a number; a medagliere must not be the one page that
    # does not (`race.apply_pair_numbers`).
    R.apply_pair_numbers(store, comp, el)

    out = Survey()
    seen: set[tuple[str, str]] = set()
    for item in comp.programme:
        if cats is not None and item.cat not in cats:
            continue
        if events is not None and item.event not in events:
            continue
        if (item.cat, item.event) in seen:
            continue        # a specialità is read once, not once per round
        seen.add((item.cat, item.event))
        result, where, complete = final_result(store, comp, el,
                                               item.cat, item.event)
        if not complete:
            out.open_events.append((item.cat, item.event, result is not None))
        if result is None or (not complete and not include_unfinished):
            continue
        out.counted += 1
        # the race that decided the specialità: who rode it - a riserva who
        # took a place, the rider she replaced - is on it and nowhere else
        deciding = (store.load_race(R.race_key(item.cat, item.event, where))
                    if where else None)
        keys = placing_keys(deciding, comp, el)
        for placing in result.placings:
            if placing.position not in MEDALS:
                continue
            if placing.status not in (Status.OK, Status.REL):
                continue    # a place is a place; a DSQ carries none
            key = keys.get(placing.key, placing.key)
            out.places.append(Podium(
                cat=item.cat, event=item.event, position=placing.position,
                key=key,
                label=R.entrant_label(key, el),
                names=names_of(key, el, item.cat, deciding),
                teams=teams_of(key, el, item.cat, group),
                round_key=where, complete=complete))
    return out


def podiums(store, comp: Competition, el: EntryList, **kw) -> list[Podium]:
    """Every podium place of the competition, in programme order."""
    return survey(store, comp, el, **kw).places


def medal_table(places: list[Podium]) -> list[TeamMedals]:
    """The medagliere itself: one line per squadra, best first."""
    table: dict[str, TeamMedals] = {}
    for place in places:
        for team in place.teams:
            table.setdefault(team, TeamMedals(team=team)).count(place.position)
    return sorted(table.values(), key=lambda t: t.sort_key)


def ranked(table: list[TeamMedals]) -> list[tuple[int, TeamMedals]]:
    """The medagliere with its positions, ties sharing one: 1, 2, 2, 4.

    Two squadre with the same three counts are in the same position - there is
    nothing left to separate them, and numbering them 2 and 3 would say the
    table knows something it does not.
    """
    out: list[tuple[int, TeamMedals]] = []
    last_key, last_pos = None, 0
    for i, team in enumerate(table, start=1):
        key = (team.gold, team.silver, team.bronze)
        pos = last_pos if key == last_key else i
        out.append((pos, team))
        last_key, last_pos = key, pos
    return out


def unfinished(store, comp: Competition, el: EntryList,
               **kw) -> list[tuple[str, str, bool]]:
    """(categoria, specialità, has any result) of what is not concluded yet.

    What the medagliere is *not* counting, so a jury reading a table that
    looks short can see why in one glance.
    """
    return survey(store, comp, el, **kw).open_events
