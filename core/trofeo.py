"""La classifica del Trofeo delle Regioni: points per prova, summed per regione.

A Trofeo delle Regioni is not decided by medals. It is decided by a points
table applied to *every* prova of the meeting (art. 8 for a prova di
qualificazione, art. 9 for the finale nazionale), and the squadra with the most
points at the end of the day wins it. This module is that count, and nothing
else: it reads what the jury has filed, applies the table of the regolamento,
and hands back a ranking that can be checked line by line.

The rules it implements, in the words of the regolamento (art. 9):

* **punti piazzamento.** The first ten of each prova score
  14-12-10-8-6-5-4-3-2-1 (art. 8, for the qualifications: 10-9-8-…-1). A place
  is a place, so a relegated entrant keeps the points of the position she was
  put back to; a DSQ has no position and scores none.
* **punti partecipazione.** *1 punto per: Atleta / Team / Coppia Madison* -
  one point per **entità che prende il via**, not per rider: a quartetto is
  one point and not four, a coppia madison one and not two. Whoever does not
  start (NP dichiarato alla verifica, DNS) scores nothing; whoever starts and
  does not finish has started, and scores it.
* **parità.** Settled in the order the regolamento states it: more gare won on
  the day, then more punti partecipazione, then the better score in the last
  prova of the programme. Two squadre that are equal on all four share a
  position - there is nothing left to separate them.

An event is counted **once**, on its final classification, exactly as the
medagliere counts it: the same reading (`core.medals.final_result`), so the
two tables of the Statistiche page can never disagree about which race decided
what. An event whose last round has not been ridden is reported as open
rather than scored off its qualifying, and the caller decides whether to count
it anyway (a Trofeo read between two races is provisional, and says so).

Nothing here writes. A race the scoring cannot read costs its own event
and no more.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import medals as M
from . import race as R
from . import recap as RC
from .config import (EVENT_ENTRY_LIST, ROUND_PAUSE, Competition,
                     is_pause)
from .models import EntryList, Status

#: Art. 9 - la finale nazionale. The first ten of every prova score.
FINAL_POINTS: dict[int, int] = {1: 14, 2: 12, 3: 10, 4: 8, 5: 6,
                                6: 5, 7: 4, 8: 3, 9: 2, 10: 1}

#: Art. 8 - le prove di qualificazione. The same shape, a flatter table.
QUALIFYING_POINTS: dict[int, int] = {1: 10, 2: 9, 3: 8, 4: 7, 5: 6,
                                     6: 5, 7: 4, 8: 3, 9: 2, 10: 1}

SCALE_FINAL = "final"
SCALE_QUALIFYING = "qualifying"

#: Which table a meeting is scored on. The finale is the default: it is the
#: one the app was asked for, and a qualification says so in Impostazioni.
SCALES: dict[str, dict[int, int]] = {SCALE_FINAL: FINAL_POINTS,
                                     SCALE_QUALIFYING: QUALIFYING_POINTS}

#: *1 punto per: Atleta / Team / Coppia Madison* - per entity, per prova.
PARTICIPATION_POINT = 1

#: An entrant who never took the start. NP is declared at the verifica delle
#: licenze and keeps the rider off the startlist altogether; DNS is the jury
#: writing down, on the race itself, that a rider on the sheet did not line up.
DID_NOT_START = (Status.DNS, Status.NS)

#: The statuses that carry a position. The same two the medagliere counts: a
#: relegated entrant is still classified, a disqualified one is not.
PLACED = (Status.OK, Status.REL)


def points_of(position: int | None, scale: str = SCALE_FINAL) -> int:
    """What one position is worth on the table in force. Off the table: 0."""
    return SCALES.get(scale, FINAL_POINTS).get(position or 0, 0)


# ── what one squadra took out of one prova ──────────────────────────────────

@dataclass
class EventScore:
    """One squadra's score in one event, with what it is made of."""

    cat: str
    event: str
    team: str
    points: int = 0           # punti piazzamento
    participation: int = 0    # punti partecipazione
    starters: int = 0         # entità che hanno preso il via
    wins: int = 0             # prove vinte (position 1)
    #: (position, what it rode under) of every place that scored, best first.
    places: list[tuple[int, str]] = field(default_factory=list)
    complete: bool = True     # False: the event is not over yet

    @property
    def total(self) -> int:
        return self.points + self.participation


@dataclass
class TeamScore:
    """One line of the classifica del Trofeo."""

    team: str
    points: int = 0
    participation: int = 0
    starters: int = 0
    wins: int = 0
    #: The score of this squadra in the last prova of the programme - the
    #: third tie-break of art. 9, and only ever read for that.
    last_points: int = 0
    events: list[EventScore] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.points + self.participation

    @property
    def tie_key(self) -> tuple:
        """What separates two squadre, in the order the regolamento says.

        Total points; then gare vinte; then punti partecipazione; then the
        score in the last prova of the giornata. Everything past this is a
        genuine tie, and the table shares a position rather than inventing one.
        """
        return (-self.total, -self.wins, -self.participation, -self.last_points)

    @property
    def sort_key(self) -> tuple:
        return (*self.tie_key, self.team.lower())


# ── the last prova of the programme ─────────────────────────────────────────

def last_event(comp: Competition) -> tuple[str, str]:
    """(categoria, event) of the last prova ridden, or ("", "").

    The third tie-break of art. 9 is *il miglior punteggio dell'ultima prova in
    programma nella giornata*, so the running order decides it and not the
    order the programme happens to list the races in (`Competition.rounds_on`).
    A pausa is not a prova, and the composizione of a madison is not ridden at
    all - neither can be the last thing of the day.
    """
    for day in reversed(comp.days()):
        for item, rnd in reversed(comp.rounds_on(day)):
            if rnd.kind == ROUND_PAUSE or is_pause(item):
                continue
            return item.cat, item.event
    return "", ""


# ── the count ───────────────────────────────────────────────────────────────

@dataclass
class Standings:
    """One reading of the whole competition, scored."""

    rows: list[TeamScore] = field(default_factory=list)
    #: (categoria, event, whether anything at all has been filed)
    open_events: list[tuple[str, str, bool]] = field(default_factory=list)
    counted: int = 0                          # prove concluded and scored
    scale: str = SCALE_FINAL
    last: tuple[str, str] = ("", "")          # the prova the tie-break reads
    #: Every squadra's score in every prova, in programme order: the detail
    #: the sheet prints under the table so a line can be checked.
    scores: list[EventScore] = field(default_factory=list)


def standings(store, comp: Competition, el: EntryList, *,
              group: str = RC.DEFAULT_GROUP, cats: list[str] | None = None,
              events: list[str] | None = None,
              include_unfinished: bool = False,
              scale: str = SCALE_FINAL) -> Standings:
    """Score the competition: one line per squadra, the winner first.

    `cats` and `events` restrict what is read (None = all of them);
    `include_unfinished` scores the event whose last round has not been
    ridden yet, marked `complete=False` on every score they produced.
    """
    # a madison is scored by the number the jury gave the coppia, and that
    # number is on the entry list only once it has been stamped there. The
    # medagliere does this before it reads a placing; a classifica that decides
    # who wins the Trofeo must not be the one page that does not.
    R.apply_pair_numbers(store, comp, el)

    out = Standings(scale=scale, last=last_event(comp))
    seen: set[tuple[str, str]] = set()
    for item in comp.programme:
        # a pausa is not a prova and the elenco iscritti is not a race: neither
        # can be scored, and neither belongs among the prove still open
        if is_pause(item) or item.event == EVENT_ENTRY_LIST:
            continue
        if cats is not None and item.cat not in cats:
            continue
        if events is not None and item.event not in events:
            continue
        if (item.cat, item.event) in seen:
            continue            # an event is scored once, on its finale
        seen.add((item.cat, item.event))
        result, where, complete = M.final_result(store, comp, el,
                                                 item.cat, item.event)
        if not complete:
            out.open_events.append((item.cat, item.event, result is not None))
        if result is None or (not complete and not include_unfinished):
            continue
        out.counted += 1
        deciding = (store.load_race(R.race_key(item.cat, item.event, where))
                    if where else None)
        out.scores.extend(score_event(result, deciding, comp, el, item.cat,
                                      item.event, group=group, scale=scale,
                                      complete=complete))

    out.rows = _rows(out.scores, out.last)
    return out


def score_event(result, deciding, comp: Competition, el: EntryList,
                cat: str, event: str, *, group: str = RC.DEFAULT_GROUP,
                scale: str = SCALE_FINAL,
                complete: bool = True) -> list[EventScore]:
    """What every squadra took out of one prova, best first.

    One pass over the classification. Each placing is **one entità** - a rider,
    a quartetto, a coppia madison - so counting the placings that took the
    start is counting the punti partecipazione, and no format has to be asked
    what its entrants are.
    """
    keys = M.placing_keys(deciding, comp, el)
    scores: dict[str, EventScore] = {}
    counted: set[str] = set()

    def line(team: str) -> EventScore:
        return scores.setdefault(team, EventScore(cat=cat, event=event,
                                                  team=team,
                                                  complete=complete))

    for placing in result.placings:
        key = keys.get(placing.key, placing.key)
        if key in counted:
            continue            # one entità, one line of the classification
        counted.add(key)
        teams = M.teams_of(key, el, cat, group)
        if not teams:
            continue            # nobody to credit: an entrant with no squadra
        started = placing.status not in DID_NOT_START
        who = entrant_name(key, el, cat)
        points = (points_of(placing.position, scale)
                  if placing.status in PLACED else 0)
        for team in teams:
            score = line(team)
            if started:
                score.starters += 1
                score.participation += PARTICIPATION_POINT
            if points:
                score.points += points
                score.places.append((placing.position, who))
            if placing.position == 1 and placing.status in PLACED:
                score.wins += 1

    for score in scores.values():
        score.places.sort()
    return sorted(scores.values(), key=lambda s: (-s.total, s.team.lower()))


def entrant_name(key: str, el: EntryList, cat: str) -> str:
    """What a scoring entrant is called on the detail sheet.

    A quartetto and a coppia ride under a name of their own ("TOSCANA A"); a
    rider rides under a dorsale, and a dorsale alone is not something a jury
    can check against a comunicato at the premiazione - so hers is followed by
    her name.
    """
    who = R.entrant_label(key, el)
    if key in el.teams or key in el.pairs:
        return who
    names = M.names_of(key, el, cat)
    return f"{who} {names[0]}" if names else who


def _rows(scores: list[EventScore], last: tuple[str, str]) -> list[TeamScore]:
    """The per-prova scores added up into the classifica."""
    rows: dict[str, TeamScore] = {}
    for score in scores:
        row = rows.setdefault(score.team, TeamScore(team=score.team))
        row.points += score.points
        row.participation += score.participation
        row.starters += score.starters
        row.wins += score.wins
        row.events.append(score)
        if (score.cat, score.event) == last:
            row.last_points += score.total
    return sorted(rows.values(), key=lambda t: t.sort_key)


def ranked(rows: list[TeamScore]) -> list[tuple[int, TeamScore]]:
    """The classifica with its positions, a genuine tie sharing one.

    Art. 9 separates two squadre by gare vinte, punti partecipazione and the
    last prova of the day. Two that are equal on all of them are equal, and
    numbering them 4 and 5 would say the table knows something it does not.
    """
    out: list[tuple[int, TeamScore]] = []
    last_key, last_pos = None, 0
    for i, row in enumerate(rows, start=1):
        pos = last_pos if row.tie_key == last_key else i
        out.append((pos, row))
        last_key, last_pos = row.tie_key, pos
    return out


def champion(rows: list[TeamScore]) -> str:
    """The squadra proclaimed champion, or "" where nothing is decided yet.

    Art. 9: *il Comitato Regionale che al termine della Finale Nazionale
    risulterà primo in graduatoria*. First and alone: two squadre sharing the
    lead are not a champion, they are a tie the jury has to settle.
    """
    places = ranked(rows)
    leaders = [r for pos, r in places if pos == 1]
    return leaders[0].team if len(leaders) == 1 else ""


def scores_of(found: Standings, cat: str, event: str) -> list[EventScore]:
    """Every squadra's score in one prova, best first."""
    return [s for s in found.scores if (s.cat, s.event) == (cat, event)]
