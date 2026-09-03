"""Race service: who is entered, which format applies, and how it scores.

Sits between the UI and `core/formats`. Everything it needs lives in the
persisted `RaceState.payload`, so a browser reload or a crash loses nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import zip_longest

from .config import (DOC_RESULTS, DOC_RESULTS_58, DOC_RESULTS_B,
                     DOC_RESULTS_REP, MIN_ELIMINATED, PREFIX_FINALS,
                     PREFIX_QUALIFYING, ROUND_SETUP, Competition,
                     madison_track_teams)
from .formats import derny as DY
from .formats import group as G
from .formats import keirin as K
from .formats import omnium as O
from .formats import timed as T
from .formats.base import CLASSIFIED, Result, assign_positions, sort_by_status
from .i18n import label, ui
from .models import (EntryList, RaceState, Rider, Status, split_heat,
                     status_of)
from .parse import ParseError, parse_bibs, parse_heats, parse_sprints

# Scoring kinds a round_key can resolve to.
POINTS = G.POINTS
TEMPO = G.TEMPO
SCRATCH = G.SCRATCH
MADISON = G.MADISON
ELIMINATION = "elimination"
TIMED = "timed"
TIMED_TEAM = "timed_team"
BRACKET = "bracket"  # sprint / keirin rounds (see formats.sprint)
DERNY = "derny"  # called live, lap by lap (see formats.derny)
SETUP = "setup"  # composed, not ridden: the madison pairing (see § pairing)

#: The prove di gruppo: everybody on the track at once, ranked on what happens
#: there. They share the decisions a bunch race takes - a rider who comes down
#: (ABD), one who is left in it (DNF), one who never started - and the sheets
#: that read them (`documents.race_classification`).
BUNCH = (POINTS, TEMPO, SCRATCH, MADISON, ELIMINATION)

# Omnium: the round_key name decides the scoring, not the event. The names are
# the ones `formats.omnium` schedules the prove under - spelled once, there.
OMNIUM_ROUNDS = {
    O.SCRATCH.lower(): SCRATCH,
    O.TEMPO.lower(): TEMPO,
    O.ELIMINATION.lower(): ELIMINATION,
    O.POINTS_RACE.lower(): POINTS,
}


def round_format(comp: Competition, cat: str, event: str, round_key: str) -> str:
    """Which scoring applies to one round_key of one race."""
    fmt = comp.event(event).fmt
    key = (round_key or "").strip().lower()

    if comp.round_of(cat, event, round_key).kind == ROUND_SETUP:
        return SETUP

    if fmt == "omnium":
        for name, scoring in OMNIUM_ROUNDS.items():
            if key.startswith(name):
                return scoring
        return POINTS  # batterie di qualificazione
    if fmt == "madison":
        return MADISON
    # an eliminazione ridden as its own event is scored the way the prova
    # of an omnium is - by the order the riders went out - and not on volate:
    # without this it fell through to POINTS and every sheet of it was wrong
    if fmt == "elimination":
        return ELIMINATION
    if fmt in ("timed", "time_trial"):
        return TIMED
    if fmt == "timed_team":
        return TIMED_TEAM
    if fmt in ("sprint", "keirin"):
        return TIMED if is_qualifying(round_key) else BRACKET
    if fmt == "derny":
        return DERNY
    return POINTS


def is_team_format(kind: str) -> bool:
    return kind in (TIMED_TEAM, MADISON)


def is_pursuit(comp: Competition, event: str, kind: str) -> bool:
    """True for a race against the clock whose finals come from a qualification.

    The inseguimento - individuale or a squadre - and the velocità a squadre are
    ridden twice: a qualification against the clock, then two finals seeded from
    it. The 200 m of a velocità and the qualifying of a keirin are timed too,
    but what they send riders to is a bracket, so none of the machinery that
    hangs off this applies to them.
    """
    return kind in (TIMED, TIMED_TEAM) and comp.event(event).fmt in (
        "timed", "time_trial", "timed_team")


# ── entrants ────────────────────────────────────────────────────────────────

def entrants(el: EntryList, comp: Competition, cat: str, event: str,
             round_key: str = "", *, include_reserves: bool = False) -> list[str]:
    """Entrant keys for a race: bibs for riders, team/pair keys otherwise."""
    kind = round_format(comp, cat, event, round_key)
    if kind == TIMED_TEAM:
        return [t.key for t in sorted(el.teams.values(),
                                      key=lambda t: (t.region, t.letter))
                if t.cat == cat and t.event == event and t.riders]
    if kind == MADISON:
        return [p.key for p in sorted(el.pairs.values(),
                                      key=lambda p: (p.region, p.number))
                if p.cat == cat and len(p.riders) >= 1]
    return [str(r.bib) for r in
            sorted(el.entered(cat, event, include_reserves=include_reserves),
            key=lambda r: (r.bib is None, r.bib or 0))
            if r.bib is not None]


def entrant_label(key: str, el: EntryList) -> str:
    """The name an entrant rides under - 'LOMBARDIA A', number or no number.

    A region that fields two coppie tells them apart with a letter, the way it
    tells its two quartetti apart, and it keeps it everywhere: on the sheets of
    the batterie as on the composition round. The coppia number answers "who is
    that on the track"; the letter answers "which of their two coppie is it",
    and the jury reads the second question off the same line.
    """
    if key in el.teams:
        return el.teams[key].label
    if key in el.pairs:
        return el.pairs[key].label
    return str(key)


def entrant_riders(key: str, el: EntryList, cat: str = "") -> list:
    """The riders behind an entrant key (one for a bib, several for a team).

    **A dorsale is unique inside a category and nowhere else.** At these
    championships the number 2 is worn by an ES, an ED, an AL and a DA rider,
    so an entrant given as a bare number - which is how every individual race
    holds its startlist - can only be resolved against the category that is
    racing. Pass `cat`: without it this matches whoever wears the number, and
    that is what put four riders, one per category, on one line of an AL
    sheet. Teams and coppie carry their category in the key and are safe.
    """
    if key in el.teams:
        t = el.teams[key]
        return [el.riders[k] for k in t.riders if k in el.riders]
    if key in el.pairs:
        p = el.pairs[key]
        return [el.riders[k] for k in p.riders if k in el.riders]
    return [r for r in el.riders.values() if str(r.bib) == str(key)
            and (not cat or r.cat == cat)]


def riders_by_bib(el: EntryList, cat: str = "") -> dict[str, Rider]:
    """dorsale -> rider, inside one category (see `entrant_riders`)."""
    return {str(r.bib): r for r in el.riders.values()
            if r.bib is not None and (not cat or r.cat == cat)}


# ── state helpers ───────────────────────────────────────────────────────────


#: How a timed round is ridden, as the jury decided it on the day: one start
#: at a time (an *ordine di partenza*) or two (batterie). The programme states
#: the usual shape of the event (`Event.teams_per_start`); this is the call
#: taken at the track, kept on the race so the sheets say what was ridden.
SOLO_STARTS = "solo_starts"


def can_choose_starts(comp: Competition, event: str, kind: str,
                      round_key: str, cat: str = "") -> bool:
    """Whether this round can be ridden one start at a time at all.

    Only a round against the clock: a bracket is ridden man against man
    whatever anybody chooses, and so is a finals round *that something seeded*
    - two squadre come out of a qualificazione and ride one per straight.

    **A finale nothing seeded is not that** (`is_seeded_round`). A velocità a
    squadre run as a finale diretta, an inseguimento a squadre with one fase,
    a chilometro: the fase is called *Finale* because it is the whole race, and
    it is ridden against the clock like any qualificazione - one at a time or
    two, as the regulation for the event says (`starts_per_race`) and as
    the jury may decide at the track. Reading the name alone forced them all
    into batterie of two and threw away a programme that said *uno alla
    volta* - on a velocità a squadre, whose own regulation says one.

    Without a categoria the question cannot be asked of the programme, and the
    name is all there is to go on.
    """
    if kind not in (TIMED, TIMED_TEAM):
        return False
    if comp.event(event).fmt == "time_trial":
        return True
    if not cat:
        return not is_finals(round_key)
    return not is_seeded_round(comp, cat, event, round_key, kind)


def solo_starts(comp: Competition, state) -> bool:
    """True when this round runs as a start order rather than as batterie.

    Three answers, in this order: what the jury decided on the race itself -
    an inseguimento individuale with a thin field is often ridden one atleta at
    a time - then what the programme says about *this* race, then what the
    event says in general (a velocità a squadre starts one squadra at a
    time, an inseguimento two).

    The middle one exists because the shape is not a property of the
    event: the same chilometro is ridden two at a time by a categoria with
    thirty entered and one at a time by the eight of another.
    """
    kind = state.fmt or round_format(comp, state.cat, state.event,
                                     state.round_key)
    if not can_choose_starts(comp, state.event, kind, state.round_key,
                             state.cat):
        return False
    choice = (state.payload or {}).get(SOLO_STARTS)
    if choice is not None:
        return bool(choice)
    return starts_per_race(comp, state.cat, state.event) == 1


def starts_per_race(comp: Competition, cat: str, event: str) -> int:
    """How many start together in this race, as the programme has it."""
    item = comp.scheduled(cat, event)
    stated = getattr(item, "teams_per_start", None) if item else None
    return int(stated or comp.event(event).teams_per_start)


def is_qualifying(round_key: str) -> bool:
    """True for the round a bracket event is seeded from (the 200 m, a keirin
    qualifying): it is ridden against the clock, not man against man."""
    return (round_key or "").strip().lower().startswith(PREFIX_QUALIFYING)


def is_finals(round_key: str) -> bool:
    """True for a round that rides for places instead of qualifying for them.

    The programme names them "Finale" / "Finali"; what hangs off this is what
    a finals sheet must not say - who qualifies, above all.
    """
    return (round_key or "").strip().lower().startswith(PREFIX_FINALS)


def is_seeded_round(comp: Competition, cat: str, event: str, round_key: str,
                    kind: str = "") -> bool:
    """True for a round another round composed: its startlist is not the entry list.

    A finals race rides whoever qualified for it, and every bracket round after
    the first is seeded from the one before (`load_sprint_round`). The first
    round of a keirin is not: the batterie come off the entry list by the UCI
    table, like the 200 m of a velocità.

    **A round can only be seeded by a round before it.** The name is not the
    answer on its own: a scratch, una corsa a punti, un'eliminazione, il
    chilometro are one race and `core.rounds` calls that race *Finale* - there
    is no qualification under it and nothing composed it, so it starts whoever
    is entered, like any other fase the whole elenco rides. Reading the name
    alone froze the startlist of every one of those events at the moment the
    race was first opened: an atleta iscritta alla verifica afterwards never
    reached the ordine di partenza, and the sheet went out without her.

    The composizione of a madison or of an omnium is not a fase that is ridden
    (`ROUND_SETUP`), so it does not count as the round before either.
    """
    if not (is_finals(round_key)
            or (kind or round_format(comp, cat, event, round_key)) == BRACKET):
        return False
    ridden = [r.key for r in comp.rounds(cat, event) if r.kind != ROUND_SETUP]
    return bool(ridden) and ridden[0] != round_key


#: The four decisions that end a rider's event. What she did is filed on
#: the sheet of the fase she did it in - that sheet prints the sigla - and
#: everything ridden afterwards is ridden without her: she is not on the ordine
#: di partenza of the next fase, not a dorsale the jury is asked for, and not a
#: line the app expects a result on. A declassamento is not among them: it
#: settles one fase and the rider carries on.
OUT_OF_EVENT = (Status.DNS, Status.DNF, Status.ABD, Status.DSQ)


def left_event(store, comp: Competition, cat: str, event: str,
               before: str = "") -> dict[str, Status]:
    """Who is out of this event before `before` is ridden, and under what.

    Read off the fasi already ridden, in the order the programme has them: a
    rider who took a DNS, a DNF, an ABD or a DSQ in one of them does not start
    what comes after (`OUT_OF_EVENT`). It is the *event* this answers for, not
    one sheet - the classifica of the event still names her, with the
    sigla, because that is what a classification is for.

    Only the fasi a whole entry list rides are read this way. A velocità is the
    exception the UCI writes itself - a DNS in a turno is losing that turno,
    not abandoning the event (`sprint_statuses`) - and its rounds are
    composed from the round before in any case, so their startlists never come
    through here.
    """
    out: dict[str, Status] = {}
    for rnd in comp.rounds(cat, event):
        if rnd.key == before:
            break
        st = store.load_race(race_key(cat, event, rnd.key))
        if st is None:
            continue
        for key, status in all_statuses(st).items():
            if status in OUT_OF_EVENT:
                out[key] = status
    return out


def ensure_state(store, comp: Competition, cat: str, event: str, round_key: str,
                 el: EntryList) -> RaceState:
    """Load the race, creating it with the programme's entrants and distances.

    A fase ridden by the whole entry list starts whoever is still in the
    event: whoever left it in a fase already ridden is dropped from the
    startlist here, once, so that every sheet and every field of the fase -
    ordine di partenza, arrivi, classifica - is made of the same riders
    (`left_event`).
    """
    kind = round_format(comp, cat, event, round_key)
    st = store.get_race(cat, event, round_key, fmt=kind)
    st.fmt = kind
    # the setup round rules the whole event: an entrant rides the batteria it
    # was assigned there, and what follows the batterie starts whoever they
    # qualified. True of a madison at every round, and of an omnium as soon as
    # the programme schedules a qualification for it
    composed = kind in (MADISON, SETUP) or is_composed(comp, cat, event)
    if composed:
        field = composed_entrants(store, comp, cat, event, round_key, el,
                                  state=st)
        if not heat_number(round_key) and kind != SETUP:
            # what the batterie qualified, less whoever has left the event
            # since: the prove of an omnium are ridden one after the other, and
            # a DNF in the first is not on the ordine di partenza of the second
            # (`left_event`). A batteria is not read this way - it is the
            # composition itself - and neither is the setup round.
            field = _still_in(store, comp, cat, event, round_key, field)
        _resync_entrants(st, field)
        if heat_number(round_key):
            # the cut in force when this batteria is ridden, kept on the race
            # itself: it is what its own sheets say, and what they said stays
            # true after the composition is touched again
            st.payload[ELIMINATE] = pairing(store, comp, cat, event, el).eliminate
    pursuit = is_pursuit(comp, event, kind)
    if pursuit and comp.round_of(cat, event, round_key).qualify:
        # a qualifying round qualifies: the finals it sends teams to are a race
        # of their own. Older versions seeded them into this one.
        (st.payload or {}).pop("final_heats", None)
    if not st.entrants:
        st.entrants = _still_in(store, comp, cat, event, round_key,
                                entrants(el, comp, cat, event, round_key))
    elif composed:
        pass  # already resynced above, against the composition
    elif is_team_format(kind) or pursuit:
        if not (st.payload or {}).get("final_heats"):
            # a finals race starts the four the qualification sent through, not
            # everybody on the entry list: its own startlist
            _resync_entrants(st, entrants(el, comp, cat, event, round_key))
    elif not is_seeded_round(comp, cat, event, round_key, kind):
        # an individual round nobody composed starts whoever is entered and is
        # still in the event: the verifica is allowed to go on after the
        # race was first opened, and so is a fase already ridden
        _resync_entrants(st, _still_in(store, comp, cat, event, round_key,
                                       entrants(el, comp, cat, event,
                                                round_key)))
    if pursuit and (st.payload or {}).get("final_heats"):
        _sync_qual_out(store, comp, el, cat, event, st)
    d, laps, sprints = comp.distances(cat, event, round_key)
    st.distance, st.n_laps, st.n_sprint = d, laps, sprints
    return st


def _still_in(store, comp: Competition, cat: str, event: str, round_key: str,
              current: list[str]) -> list[str]:
    """`current` less whoever left the event in a fase already ridden."""
    gone = left_event(store, comp, cat, event, round_key)
    return [k for k in current if k not in gone] if gone else current


def qualifying_round(comp: Competition, cat: str, event: str) -> str:
    """Key of the round the finals of this event are seeded from, '' if none."""
    return next((r.key for r in comp.rounds(cat, event)
                 if r.qualify and not is_finals(r.key)), "")


def _sync_qual_out(store, comp: Competition, el: EntryList, cat: str,
                   event: str, state: RaceState) -> None:
    """Re-read the qualification from the finals race, below the cut.

    A squadra DNS or DSQ in the qualification never reaches the finals, but the
    classification of the event has to say so: it is the sheet that files
    the decision. The four that ride the finals are frozen - they are on the
    track - while everything under them is read here instead of at the moment
    *Carica finali* was pressed: a decision taken, corrected or withdrawn
    afterwards reaches the sheet without re-seeding the finals.
    """
    key = qualifying_round(comp, cat, event)
    st = store.load_race(race_key(cat, event, key)) if key else None
    if st is None:
        return
    res = classify(st, el, comp)
    ranked = [p.key for p in res.placings if p.position]
    if not ranked:
        return          # nothing classified: the qualification was reset
    state.payload["qual_out"] = {p.key: p.status.value for p in res.placings
                                 if p.status is not Status.OK and not p.position}
    started = set(state.entrants)
    head = [k for k in (state.payload.get("qual_ranking") or []) if k in started]
    state.payload["qual_ranking"] = head + [k for k in ranked if k not in started]


def _resync_entrants(state: RaceState, current: list[str]) -> None:
    """Follow the entry list on a race that has no startlist of its own.

    A team race, and every individual round nobody composed, start whoever is
    entered: the entrants *are* the entry list read through the check-in. A
    saved race keeping its own copy would carry a squadra that no longer
    exists, print an atleta declared NP after it was opened, and - the one
    that bites during a championship - leave out the rider added at the
    verifica once the race had been created. The verifica goes on all day; the
    races have to follow it.

    What is keyed by entrant follows (statuses, times, the slot in the grid).
    The notation the jury typed is left alone: an unknown dorsale in it is
    flagged on screen, which is a question for the jury, not something to
    delete behind its back.
    """
    if not current or state.entrants == current:
        return
    live = set(current)
    dead = [k for k in state.entrants if k not in live]
    state.entrants = current
    p = state.payload or {}
    for k in dead:
        state.statuses.pop(k, None)
        for name in ("times", "qual_times", "heat_bibs", "qual_out"):
            if isinstance(p.get(name), dict):
                p[name].pop(k, None)
    if isinstance(p.get("qual_ranking"), list):
        p["qual_ranking"] = [k for k in p["qual_ranking"] if k in live]
    if isinstance(p.get("final_heats"), list):
        p["final_heats"] = [[k for k in h if k in live] for h in p["final_heats"]]
    if isinstance(p.get("heat_sides"), list):
        # the rest of the composition stands: only the slot of a squadra that
        # no longer exists is emptied, for the jury to fill again
        p["heat_sides"] = [[k if k in live else "" for k in row]
                           for row in p["heat_sides"]]


# ── statuses, one set per result sheet ──────────────────────────────────────
#
# A decision belongs to the race it was taken in, and two rounds of a velocità
# ride two races each: the recuperi inside the turno 1, the 5°-8° final inside
# the finali. A rider relegated in the recuperi was not relegated in the turno,
# and her DNS in the 5°-8° says nothing about the final for the title. So each
# results sheet keeps its own statuses: the round's own in `state.statuses`,
# the second race's in the payload, under the *scope* of its document.

STATUSES_REP = "statuses_rep"    # turno 1: the recuperi
STATUSES_58 = "statuses_5_8"     # finali: the 5°-8° final
STATUSES_B = "statuses_final_b"  # keirin finali: the final under the title one
STATUS_SCOPES = {DOC_RESULTS_REP: STATUSES_REP, DOC_RESULTS_58: STATUSES_58,
                 DOC_RESULTS_B: STATUSES_B}
ALL_SCOPES = ("", STATUSES_REP, STATUSES_58, STATUSES_B)


def status_scope(doc_kind: str) -> str:
    """Which set of statuses a sheet reads and writes ('' = the round's own)."""
    return STATUS_SCOPES.get(doc_kind, "")


def status_dict(state: RaceState, scope: str = "") -> dict[str, str]:
    """The raw map of one sheet, ready to be written into."""
    if not scope:
        return state.statuses
    return state.payload.setdefault(scope, {})


def statuses_of(state: RaceState, scope: str = "") -> dict[str, Status]:
    raw = (state.statuses if not scope
           else (state.payload or {}).get(scope)) or {}
    return {k: status_of(v) for k, v in raw.items()}


def all_statuses(state: RaceState) -> dict[str, Status]:
    """Every decision taken in this round, whichever of its races it was taken
    in - what the classification of the event has to read."""
    out: dict[str, Status] = {}
    for scope in ALL_SCOPES:
        out.update(statuses_of(state, scope))
    return out


def set_status(state: RaceState, key: str, status: Status,
               scope: str = "") -> None:
    if status is Status.OK:
        status_dict(state, scope).pop(key, None)
    else:
        status_dict(state, scope)[key] = status.value


def set_statuses_from_text(state: RaceState, text: str, status: Status,
                           *, keys: dict[str, str] | None = None,
                           scope: str = "") -> list[str]:
    """Apply 'DNF: 3, 12' style input; returns the keys that were set.

    `keys` translates what the jury types into what the status belongs to. In
    a madison the two are not the same thing: the number typed is the coppia's,
    and the status is the coppia's - stored under a number it landed on nobody,
    and a coppia that did not start was classified as if it had ridden.
    """
    keys = keys or {}
    out = []
    for b in parse_bibs(text):
        key = keys.get(str(b), str(b))
        set_status(state, key, status, scope)
        out.append(key)
    return out


# ── ammonizioni, read back onto the sheets ──────────────────────────────────
#
# A warning is filed in the jury's log (`core.decisions`), not in the race: it
# is a decision about a rider and it outlives the fase it was taken in. The
# sheets ask for it here, so that the Gare page and Stampa read the same thing.


def warnings_carried(store, comp: Competition, cat: str, event: str,
                     round_key: str = "") -> dict[int, str]:
    """dorsale -> the fase its ammonizione was taken in, up to `round_key`.

    What prints as a W beside the name. Empty when the log holds nothing for
    this event, which is what a sheet without the column means.
    """
    from . import decisions as DEC

    return DEC.warned_bibs(DEC.load(store), cat, event,
                           rounds=[r.key for r in comp.rounds(cat, event)],
                           upto=round_key)


def status_keys(state: RaceState, el: EntryList, kind: str) -> dict[str, str]:
    """What the jury types -> the key the status is stored under.

    Empty everywhere but a madison, where a race is called by coppia number
    and the entrant is the coppia (see `set_statuses_from_text`).
    """
    if kind != MADISON:
        return {}
    return {bib: key for key, bib in pair_bib_map(state, el).items()}


# ── classification ──────────────────────────────────────────────────────────

def classify(state: RaceState, el: EntryList, comp: Competition) -> Result:
    """Compute the classification from whatever the jury has entered so far."""
    kind = state.fmt or round_format(comp, state.cat, state.event,
                                     state.round_key)
    p = state.payload or {}
    statuses = statuses_of(state)

    try:
        if kind == ELIMINATION:
            return G.elimination_classification(
                startlist=[int(x) for x in state.entrants],
                eliminated=parse_bibs(p.get("eliminated", "")),
                statuses=statuses)

        if kind == DERNY:
            # nothing but the call the judge made: the chart, the laps lost and
            # the standings all come out of it (`formats.derny`)
            return DY.derny_classification(
                startlist=[int(x) for x in state.entrants],
                log=DY.passages(p), start=p.get(DY.START),
                statuses=statuses,
                # the giri persi are a column the jury turns on, on the race
                # itself, so Gare and Stampa print the same classifica
                show_laps_down=bool(p.get(DY.SHOW_DOWN)),
                # the distance the fase runs: it is what tells the chart the
                # race is over, and after that the arrival is what places the
                # riders still out (`formats.derny.board`)
                laps=state.n_laps)

        if kind == BRACKET:
            return _bracket_result(state, comp)

        if kind in (TIMED, TIMED_TEAM):
            times = {k: int(v) for k, v in (p.get("times") or {}).items() if v}
            qual = {k: int(v) for k, v in (p.get("qual_times") or {}).items() if v}
            finals = p.get("final_heats")
            if finals:
                out = {k: status_of(v)
                       for k, v in (p.get("qual_out") or {}).items()}
                return T.finals_classification(
                    finals, times, statuses=statuses,
                    qualification=p.get("qual_ranking") or [], qual_times=qual,
                    qual_out=out, tied=p.get("finals_tied") or (),
                    on_qual=p.get("finals_on_qual") or ())
            # the ones still to be timed are listed in start order and not in
            # entry order: while the fase is being ridden the sheet is half a
            # classifica and half the list of who is still to go
            return T.timed_classification(state.entrants, times,
                                          statuses=statuses, qualification=qual,
                                          order=start_order(state))

        # bunch races, individual or by pair
        startlist = bunch_startlist(state, el, kind)
        return G.group_classification(
            startlist=startlist,
            sprints=parse_sprints(p.get("sprints", "")),
            scoring=kind, n_sprint=state.n_sprint,
            laps_gained=parse_bibs(p.get("laps_gained", "")),
            laps_lost=parse_bibs(p.get("laps_lost", "")),
            statuses=_bunch_statuses(state, el, kind))
    except ParseError as exc:
        return Result(warnings=[str(exc)])


def bunch_unplaced(state: RaceState, el: EntryList, kind: str) -> list[int]:
    """Who a finished bunch race has no arrival for - the numbers still missing.

    The last volata of a prova di gruppo is its arrival: once it has been
    written, whoever is not in it has not been placed, and the classification
    ranks them behind everybody else on nothing at all. Only then - while the
    race is on, half the field is legitimately absent from the volata just
    called - and never for a rider the jury has already taken out of the race:
    a DNS, a DNF or a DSQ *is* the result. A declassata is classified and is
    expected in the arrival like anybody else.

    Empty for a race that is not scored on volate (an eliminazione says the
    same thing through `Result.pending`, rider by rider as they go out).
    """
    if kind not in (POINTS, TEMPO, SCRATCH, MADISON):
        return []
    try:
        sprints = parse_sprints((state.payload or {}).get("sprints", ""))
    except ParseError:
        return []
    planned = int(state.n_sprint or 0)
    if not sprints or len(sprints) < max(planned, 1):
        return []
    arrived = set(sprints[-1])
    statuses = _bunch_statuses(state, el, kind)
    return [b for b in bunch_startlist(state, el, kind)
            if b not in arrived
            and statuses.get(str(b), Status.OK) in CLASSIFIED]


def bunch_startlist(state: RaceState, el: EntryList, kind: str) -> list[int]:
    """The numbers a bunch race is scored by, in start order.

    Madison scores by pair, so the 'bib' is the pair's own number. Public
    because the sprint table checks what the jury types against it.
    """
    if kind == MADISON:
        return [_pair_bib(k, el, i) for i, k in enumerate(state.entrants)]
    return [int(x) for x in state.entrants]


def _bunch_statuses(state: RaceState, el: EntryList, kind: str
                    ) -> dict[str, Status]:
    """Statuses in the terms the scoring works in: bibs, coppia numbers.

    A madison keeps them on the coppia, which is what the jury declares DNS;
    the scoring reads a number. A status already stored under a number - the
    races written before `status_keys` existed - is left where it is rather
    than dropped.
    """
    st = statuses_of(state)
    if kind != MADISON:
        return st
    bib = pair_bib_map(state, el)
    return {bib.get(k, k): v for k, v in st.items()}


def _pair_bib(key: str, el: EntryList, index: int) -> int:
    """Pair bib: the one assigned by the jury, else the first rider's."""
    pair = el.pairs.get(key)
    if pair is None:
        return index + 1
    if pair.bib:
        return pair.bib
    for k in pair.riders:
        r = el.riders.get(k)
        if r and r.bib is not None:
            return r.bib
    return index + 1


def pair_bib_map(state: RaceState, el: EntryList) -> dict[str, str]:
    """entrant key -> the bib used for scoring (madison)."""
    return {k: str(_pair_bib(k, el, i)) for i, k in enumerate(state.entrants)}


def _bibs(value) -> list[int]:
    """A side as stored: '47, 51' from the builder, [47, 51] once loaded."""
    if isinstance(value, str):
        try:
            return parse_bibs(value)
        except ParseError:
            return []
    return [int(b) for b in value or []]


def team_lineup(state: RaceState, key: str, el: EntryList) -> list[tuple]:
    """(rider, replaced) for one team, in the order it prints.

    Who rode this race first, then whoever rode the qualification and lost the
    place to a reserve: the reserve is a starter now, but the classification
    still owes a line to the rider who earned the team its time.
    """
    p = state.payload or {}
    riders = entrant_riders(key, el)
    line = _bibs((p.get("heat_bibs") or {}).get(key))
    if not line:
        return [(r, False) for r in riders]
    team = el.teams.get(key) or el.pairs.get(key)
    # a reserve who rides is not in team.riders: take her from the reserves
    pool = riders + [el.riders[k] for k in (team.reserves if team else [])
                     if k in el.riders]
    by_bib = {r.bib: r for r in pool}
    out = [(by_bib[b], False) for b in line if b in by_bib]
    replaced = [b for b in _bibs((p.get("qual_bibs") or {}).get(key))
                if b not in line and b in by_bib]
    return out + [(by_bib[b], True) for b in replaced]


def start_order(state) -> list[str]:
    """The entrants in the order they start, once the grid has been composed.

    A race against the clock is ridden one start at a time, in the order the
    grid says, and that order is what everything reading a half-ridden race
    has to follow: the fields the times are typed into, and the sheet those
    times land on. Reading down a list still in entry order while the track
    runs in start order is how a time ends up on the wrong squadra.

    Whatever the grid does not place - a squadra not yet inserted, batterie
    still loose notation - keeps its entry order at the bottom: nothing
    disappears because the composition is unfinished.
    """
    order: list[str] = []
    seen: set[str] = set()
    for row in (state.payload or {}).get("heat_sides") or []:
        for key in row:
            if key and key not in seen and key in state.entrants:
                seen.add(key)
                order.append(key)
    return order + [k for k in state.entrants if k not in seen]


# ── brackets (velocità / keirin) ────────────────────────────────────────────

def heats_text(heats: list[list[str]]) -> str:
    """Heats as the jury's shorthand: `1-12/2-11`, the form everything reads."""
    return "/".join("-".join(str(k) for k in heat if k) for heat in heats if heat)


def heats_from_text(txt: str) -> list[list[str]]:
    """`1-12/2-11` -> [['1', '12'], ['2', '11']]. The inverse of `heats_text`."""
    return [[str(b) for b in side] for h in parse_heats(txt)
            for side in [[b for s in h for b in s]]] if txt else []


def bracket_heats(state: RaceState, key: str = "heats") -> list[list[str]]:
    """Heat composition stored on the race, as lists of entrant keys."""
    return heats_from_text((state.payload or {}).get(key, ""))


def bracket_orders(state: RaceState, key: str = "results") -> list[list[str]]:
    """Finishing order per heat, same shape as the composition."""
    return bracket_heats(state, key)


def heat_winners(orders: list[list[str]]) -> list[str]:
    """Who won each heat, in heat order - '' for a heat not yet decided."""
    return [h[0] if h else "" for h in orders]


def heat_losers(orders: list[list[str]]) -> list[str]:
    """Who was beaten in each heat (the second of a match), in heat order."""
    return [h[1] if len(h) > 1 else "" for h in orders]


def bracket_round(state: RaceState, comp: Competition):
    """Resolve one round of a bracket round_key."""
    from .formats import sprint as S

    round_key = comp.round_of(state.cat, state.event, state.round_key)
    return S.round_outcome(bracket_heats(state), bracket_orders(state),
                           qualify=round_key.qualify or 1,
                           statuses=statuses_of(state))


def compose_bracket_round(state: RaceState, comp: Competition,
                          ranking: list[str]) -> str:
    """Serpentine heat composition for this round_key, as the jury's shorthand."""
    from .formats import sprint as S

    round_key = comp.round_of(state.cat, state.event, state.round_key)
    heats = S.compose_round(ranking, heat_size=round_key.heat_size or 2)
    return "/".join(",".join(h) for h in heats)


def _bracket_result(state: RaceState, comp: Competition) -> Result:
    """Round results: each entrant placed within its own heat.

    Nobody leaves their batteria, whatever the jury decided about them: this
    sheet is the batterie (see `heat_result`).
    """
    from .formats.base import Placing

    outcome = bracket_round(state, comp)
    statuses = statuses_of(state)
    placings = []
    for key, (heat, place) in outcome.placings.items():
        placings.append(Placing(key=key, status=statuses.get(key, Status.OK),
                                position=None if place is None else place + 1,
                                data={"heat_no": heat + 1,
                                      "qualified": key in outcome.advancing}))
    placings.sort(key=lambda p: (p.data["heat_no"],
                                 p.position if p.position else 99))
    return Result(placings=placings,
                  warnings=outcome.warnings, columns=["heat_no"])


def heat_result(state: RaceState, heats: list[list[str]],
                orders: list[list[str]], *,
                runs: dict | None = None, n_runs: int = 0,
                labels: list[str] = (), scope: str = "") -> Result:
    """One block of batterie as a result: heat number, place, prove.

    Used for every sheet of a velocità - the first round, the recuperi, the
    quarti - because they are all the same thing: riders placed inside their
    own batteria. What changes between them is only how many prove it took,
    and that is `n_runs`: the column of each prova carries the mark of whoever
    won it.

    The statuses are the ones of this very sheet (`scope`, see § statuses),
    printed as the jury typed them: this sheet files this race. Reading them
    across the whole event is the classification's job (`sprint_statuses`).
    """
    from .formats.base import Placing

    statuses = statuses_of(state, scope)
    runs = runs or {}
    placings: list[Placing] = []
    for h, heat in enumerate(heats):
        order = orders[h] if h < len(orders) else []
        ranked = [k for k in order if k in heat]
        ranked += [k for k in heat if k not in ranked]
        won = [str(w) for w in (runs.get(str(h)) or runs.get(h) or [])]
        # what the batteria is called: "1", or - on a finals sheet, where the
        # number says nothing - the places it rides for
        name = labels[h] if h < len(labels) else h + 1
        place = 0
        for key in ranked:
            status = statuses.get(key, Status.OK)
            data = {"heat_no": name}
            for i in range(n_runs):
                data[f"run_{i + 1}"] = "X" if i < len(won) and won[i] == key else ""
            if status not in CLASSIFIED:
                placings.append(Placing(key=key, status=status, data=data))
                continue
            place += 1
            placings.append(Placing(key=key, status=status,
                                    position=place if order else None,
                                    data=data))
    cols = ["heat_no"] + [f"run_{i + 1}" for i in range(n_runs)]
    # in the order the batterie were ridden, and nobody moved out of hers. On a
    # ranking the non-classified go to the bottom; here the sheet *is* the
    # batterie, and a rider pushed down there reads as a batteria of her own -
    # which is what a REL did, when a REL is a place with a word next to it.
    return Result(placings=placings, columns=cols)


# ── velocità: one scheme from the 200 m to the classification ───────────────
#
# The jury decides how the event runs *before* it runs: "12 qual. - 1° turno -
# recuperi - semi - finali" is picked on the qualifying round and printed on
# its start order. From there every round is composed from the one before by
# the UCI table (see `formats.sprint`), and the only thing typed is who won.
#
# Two rounds carry a second block that is not a round of its own:
#   Turno 1  - the recuperi, ridden by the six losers (`rep_heats`)
#   Finali   - the 5°-8° final, ridden by the four beaten in the quarti
# They live on the race whose comunicato prints them, which is where the jury
# looks for them, and each has its own composition, results and sheet.
#
# The 5°-8° is the one of the two that is not always ridden: the programme
# says whether it is planned and the jury settles it on the qualifying round
# (`sprint_has_58`). Not ridden, the four beaten in the quarti take 5°-8° on
# their 200 m time and no sheet is filed for them.

SCHEME = "scheme"            # qualifying payload: which scheme is being run
FINAL_58 = "final_5_8"       # qualifying payload: is the 5°-8° final ridden
REP_RESULTS = "rep_results"  # first round: the repechages' finishing order
RESULTS_58 = "results_5_8"   # finals: the 5°-8° final's finishing order
HEATS_58 = "heats_5_8"       # finals: who rides it, from the quarti
RUNS = "runs"                # {heat index: winner of each prova}
NEXT_HEATS = "next_heats"    # the round this one sends out, as the jury fixed it


def is_sprint(comp: Competition, event: str) -> bool:
    """True for a velocità - the event these schemes describe."""
    return comp.event(event).fmt == "sprint"


def sprint_qualifying(comp: Competition, cat: str, event: str) -> str:
    """Key of the 200 m round: the only timed round of a velocità."""
    for r in comp.rounds(cat, event):
        if round_format(comp, cat, event, r.key) == TIMED:
            return r.key
    return ""


def sprint_started(store, comp: Competition, cat: str, event: str) -> set[str]:
    """Who took the start of the velocità: the riders with a 200 m time.

    The 200 m is the one race everybody rides, so it is what says whether a
    rider was in the event at all.
    """
    qual = sprint_qualifying(comp, cat, event)
    st = store.load_race(race_key(cat, event, qual)) if qual else None
    times = (st.payload or {}).get("times") if st is not None else None
    return {str(k) for k, v in (times or {}).items() if v}


def sprint_statuses(store, comp: Competition, cat: str, event: str,
                    statuses: dict[str, Status]) -> dict[str, Status]:
    """The statuses of a velocità *as an event*.

    Two things happen on the way from the sheets of the rounds to the sheet
    that closes the event.

    **A relegation does not travel.** REL is a decision about one prova: it
    settles who won that batteria, and that is the whole of its effect - the
    rider carries on in the event, and is classified by how far she got, like
    everybody else. Only what took her *out* of the event follows her onto
    its classification: DNF, DNS, DSQ.

    **A DNS after the start does not travel either.** A rider who has ridden
    the 200 m has taken the start of the event. Missing a round afterwards
    - a turno, a recupero, a semifinale - is losing that round, not abandoning
    the event: the sheet of that round files the DNS, and on the classification
    she is ranked like everybody else who went out there, on her 200 m time.
    She is not a DNF: a DNF is a rider who left a race she had started.

    Both are read here and nowhere else: the risultati of each round print
    what the jury typed on it - the REL beside the place it was given, the DNS
    of the round she did not start. That sheet files that round. A DNS on the
    200 m itself is a real one at both levels: she never started at all, has no
    time, and is not in `started`.

    What does follow her to the end is DNF and DSQ: a disqualification stays a
    disqualification, whichever round it was given in.
    """
    started = sprint_started(store, comp, cat, event)
    return {k: v for k, v in statuses.items()
            if v is not Status.REL
            and not (v is Status.DNS and str(k) in started)}


def sprint_scheme(store, comp: Competition, cat: str, event: str):
    """How this velocità is being run - what the day says, then the programme.

    Three answers, in this order and no other:

    1. what the jury chose on the qualifying round, which is the decision taken
       at the track and beats everything;
    2. what the programme *states* (`ProgrammeItem.scheme`), which is what the
       builder writes down when the race is scheduled;
    3. failing both, what the round list *implies* - with a first round the
       event runs twelve, without it the eight of a category too small for the
       repechages. Every programme written before the field existed lands here,
       and lands where it always did.

    Every CITA 26 category rides the twelve; the ED was moved onto it on
    05.08.2026, with 14 iscritte.
    """
    from .formats import sprint as S

    key = ""
    qual = sprint_qualifying(comp, cat, event)
    st = store.load_race(race_key(cat, event, qual)) if qual else None
    if st is not None:
        key = (st.payload or {}).get(SCHEME) or ""
    if not key:
        key = (comp.scheduled(cat, event) or _unscheduled()).scheme
    if not key:
        rounds = [r.key for r in comp.rounds(cat, event)]
        key = S.DEFAULT_SCHEME if S.TURNO1 in rounds else "8"
    return S.scheme(key)


def _unscheduled():
    """A race the programme does not schedule, so the fields below read empty."""
    from .config import ProgrammeItem
    return ProgrammeItem(cat="", event="")


def sprint_has_58(store, comp: Competition, cat: str, event: str) -> bool:
    """Whether this velocità rides its 5°-8° final.

    The programme says what was planned and the jury can still turn it round on
    the day, on the qualifying round where it picks the scheme too. It is one
    decision for the whole event: the four beaten in the quarti either
    have a race left or they are classified 5°-8° on how they got there.

    Same three answers as `sprint_scheme`: the day, then the programme
    (`ProgrammeItem.final_5_8`), then - for a file written before that field
    existed - whether the finals round files a *risultati 5°-8°* at all.
    """
    from .formats import sprint as S

    qual = sprint_qualifying(comp, cat, event)
    st = store.load_race(race_key(cat, event, qual)) if qual else None
    chosen = (st.payload or {}).get(FINAL_58) if st is not None else None
    if chosen is not None:
        return bool(chosen)
    stated = (comp.scheduled(cat, event) or _unscheduled()).final_5_8
    if stated is not None:
        return bool(stated)
    fin = next((r for r in comp.rounds(cat, event) if r.key == S.FINALI), None)
    return bool(fin and DOC_RESULTS_58 in (fin.docs or []))


def sprint_ranking(store, comp: Competition, el: EntryList, cat: str,
                   event: str) -> list[str]:
    """The 200 m classification: the order everything else is seeded on."""
    qual = sprint_qualifying(comp, cat, event)
    st = store.load_race(race_key(cat, event, qual)) if qual else None
    if st is None:
        return []
    return [p.key for p in classify(st, el, comp).placings if p.position]


def sprint_repechages(state: RaceState) -> list[list[str]]:
    """The repechage batterie of a first round, from its own results.

    Composed and not stored, unless the jury has said otherwise: they are the
    losers of the batterie above, and a result corrected upstairs has to reach
    them. What *is* stored is who won them (`rep_results`), which is a race and
    not an arithmetic - and the composition itself once the jury has confirmed
    it (`REP_HEATS`), because the seeding does not know that three of the
    riders it drew together are of the same region.

    The confirmed composition holds only while it is about the same riders: the
    moment the turno 1 sends a different field to the recuperi, it is seeded
    again - a stored composition would otherwise quietly leave somebody out of
    the race, or start somebody who is no longer in it.
    """
    from .formats import sprint as S

    losers = [k for k in heat_losers(bracket_orders(state)) if k]
    if not losers:
        return []
    fixed = bracket_heats(state, REP_HEATS)
    if fixed and {k for h in fixed for k in h} == set(losers):
        return fixed
    return S.repechage_heats(losers)


def sprint_fixed_heats(state: RaceState, auto: list[list[str]]
                       ) -> list[list[str]]:
    """The batterie this round sends out, as the jury composed them.

    Same idea as the recuperi (`sprint_repechages`), one round further on: the
    seeding pairs the qualified by the table - the winner of the first batteria
    against the last of the eight - and knows nothing about a rider who has
    just been carried off the track, two of the same società drawn together, or
    a jury decision that puts somebody elsewhere. What is typed on the round
    that composes them is kept on it (`NEXT_HEATS`) and is what everything
    downstream reads: the start order of the next round, the block printed
    under the risultati, and the race the button loads.

    It holds only while it is about the same riders: the moment the round that
    feeds it sends a different field through - a result corrected, a DSQ - the
    stored composition is dropped and the table seeds them again, rather than
    quietly starting somebody who is no longer qualified.
    """
    fixed = bracket_heats(state, NEXT_HEATS)
    if fixed and {k for h in fixed for k in h} == {k for h in auto for k in h}:
        return fixed
    return auto


def sprint_next(store, comp: Competition, el: EntryList, state: RaceState
                ) -> tuple[str, dict]:
    """(next round, payload it should carry) from the round just ridden.

    The one place that knows what follows what. Returns an empty round when
    there is nothing left to compose - the finals - or when the round in front
    of the jury has not been decided yet.
    """
    from .formats import sprint as S

    cat, event = state.cat, state.event
    sch = sprint_scheme(store, comp, cat, event)
    round_key = state.round_key

    if round_key == sprint_qualifying(comp, cat, event):
        ranked = [p.key for p in classify(state, el, comp).placings if p.position]
        heats = sprint_fixed_heats(state, S.mirror_pairs(ranked[:sch.qualify]))
        return (sch.rounds[0] if heats else ""), {"heats": heats_text(heats)}

    orders = bracket_orders(state)
    winners = [k for k in heat_winners(orders) if k]
    losers = [k for k in heat_losers(orders) if k]
    nxt = sch.next_round(round_key)
    if not nxt:
        return "", {}

    if round_key == S.TURNO1:
        rep = [k for k in heat_winners(bracket_orders(state, REP_RESULTS)) if k]
        heats = sprint_fixed_heats(state, S.quarter_heats(winners, rep))
        return (nxt if heats else ""), {"heats": heats_text(heats)}
    if round_key == S.QUARTI:
        # the quarti decide two races: the semifinals, and - for those they
        # knocked out - the 5°-8° final, which is ridden in the finals round
        heats = sprint_fixed_heats(state, S.semifinal_heats(winners))
        return (nxt if heats else ""), {"heats": heats_text(heats)}
    if round_key == S.SEMI:
        heats = sprint_fixed_heats(state, S.final_heats(winners, losers))
        return (nxt if heats else ""), {"heats": heats_text(heats)}
    return "", {}


def final_labels() -> list[str]:
    """What each final of a velocità rides for, in the order they are ridden.

    The batteria column of a finals sheet, where "1" and "2" say nothing. Read
    when the sheet is built and not once at import: the words come from the
    catalogue of the language in force.
    """
    return [label("final_3_4"), label("final_1_2")]


def composition_title(round_name: str) -> str:
    """The heading of a block composed under a results sheet.

    A composed batteria *is* the start order of the round it names, and the
    sheet carries two tables: the heading has to say which one is which, or a
    block of names under the results reads as more results.
    """
    return f"{round_name} - {label('start_order')}"


def sprint_composition(store, comp: Competition, el: EntryList,
                       state: RaceState, doc_kind: str
                       ) -> list[tuple[str, list[list[str]]]]:
    """The batterie a sheet announces under its own results.

    Every comunicato of a velocità does two jobs: it files the round that was
    ridden and it composes the next one - "risultati 1° turno" is also the
    start order of the recuperi. Returns (banner, heats) blocks, in the order
    they print.
    """
    from .formats import sprint as S

    if doc_kind not in (DOC_RESULTS, DOC_RESULTS_REP):
        # a start order composes nothing: it *is* what the sheet before it
        # composed, and repeating the next round under it says it twice
        return []
    round_key = state.round_key
    orders = bracket_orders(state)
    winners = [k for k in heat_winners(orders) if k]
    losers = [k for k in heat_losers(orders) if k]

    if round_key == S.TURNO1:
        if doc_kind == DOC_RESULTS:
            # the recuperi are ridden inside this round: they are named after it
            rep = sprint_repechages(state)
            title = composition_title(ui("round_repechages", round=round_key))
            return [(title, rep)] if rep else []
        rep_win = [k for k in heat_winners(bracket_orders(state, REP_RESULTS))
                   if k]
        heats = sprint_fixed_heats(state, S.quarter_heats(winners, rep_win))
        return [(composition_title(ui("quarters_full")), heats)] if heats else []
    if round_key == S.QUARTI:
        out = []
        semi = sprint_fixed_heats(state, S.semifinal_heats(winners))
        if semi:
            out.append((composition_title(ui("semifinals_full")), semi))
        f58 = (S.final_5_8_heat(losers)
               if sprint_has_58(store, comp, state.cat, state.event) else [])
        if f58:
            out.append((composition_title(label("final_5_8")), f58))
        return out
    if round_key == S.SEMI:
        heats = sprint_fixed_heats(state, S.final_heats(winners, losers))
        if not heats:
            return []
        # one table: what each final rides for is the batteria column, and two
        # tables of one line each would be two headings for one race
        labels = final_labels()[-len(heats):]
        return [(composition_title(ui("finals_full")), heats, labels)]
    return []


def load_sprint_round(store, comp: Competition, el: EntryList,
                      state: RaceState) -> tuple[str, int]:
    """Compose the round that follows this one and save it. (round, batterie).

    The finals are loaded once, from the semifinals; the 5°-8° final they also
    ride was decided in the quarti, so it is written there - onto the finals
    race - the moment the semifinals are composed. A year that does not ride
    it (`sprint_has_58`) composes nothing: the finals are the two races for
    the first four places and nobody else is loaded into them.
    """
    from .formats import sprint as S

    nxt, data = sprint_next(store, comp, el, state)
    if not nxt:
        return "", 0
    has_58 = sprint_has_58(store, comp, state.cat, state.event)
    target = ensure_state(store, comp, state.cat, state.event, nxt, el)
    heats = heats_from_text(data["heats"])
    target.payload["heats"] = data["heats"]
    target.entrants = [k for h in heats for k in h]
    if target.round_key == S.FINALI and has_58:
        # the finals round rides two races: the 3°/4° and 1°/2° composed here,
        # and the 5°-8° the quarti decided - everybody in it is a starter
        target.entrants += [k for h in bracket_heats(target, HEATS_58)
                            for k in h if k not in target.entrants]
    if state.round_key == S.QUARTI and has_58:
        # the four beaten in the quarti ride the 5°-8° final, in the finals
        losers = [k for k in heat_losers(bracket_orders(state)) if k]
        fin = (target if target.round_key == S.FINALI
               else sprint_finals_race(store, comp, el, state.cat, state.event))
        if fin is not None:
            fin.payload[HEATS_58] = heats_text(S.final_5_8_heat(losers))
            # its startlist is what has been loaded into it and nothing else:
            # a finals race opened early carries the whole entry list, and the
            # 5°-8° must not add itself to that
            fin.entrants = [k for h in bracket_heats(fin) for k in h] + \
                [k for k in losers if k]
            if fin is not target:
                store.save_race(fin, action="load_final_5_8")
    if bracket_heats(state, NEXT_HEATS):
        # the jury composed this round by hand: what loaded the next race is
        # filed with the race that composed it, or pressing the button again
        # would seed it back to the table
        store.save_race(state, action="sprint_composition")
    store.save_race(target, action="load_sprint_round")
    return nxt, len(heats)


def sprint_finals_race(store, comp: Competition, el: EntryList, cat: str,
                       event: str):
    """The finals race of a velocità, created if it is not on disk yet."""
    from .formats import sprint as S

    sch = sprint_scheme(store, comp, cat, event)
    if S.FINALI not in sch.rounds:
        return None
    return ensure_state(store, comp, cat, event, S.FINALI, el)


def sprint_standings(store, comp: Competition, el: EntryList, cat: str,
                     event: str) -> Result:
    """Classification of the whole velocità: the finals, then the 200 m.

    Below the places the finals ride for, the only race everybody rode is the
    qualifying, and that is what separates them - a rider out in the first
    round and one out in the quarti are ranked on their time, not on how far
    they got.

    Ridden, the 5°-8° gives places 5 to 8 and the 200 m ranks everybody from
    the ninth down. Turned off - the finals are the 1°-4° and nothing else -
    the classification follows the 200 m from the fifth place on: no race after
    the quarti separated those riders, so there is nothing else to rank them on
    and the four beaten in the quarti hold no place of their own.
    """
    from .formats import sprint as S

    fin = store.load_race(race_key(cat, event, S.FINALI))
    finals = bracket_orders(fin) if fin is not None else []
    f58 = (bracket_orders(fin, RESULTS_58)
           if fin is not None and sprint_has_58(store, comp, cat, event)
           else [])
    qual_ranking = sprint_ranking(store, comp, el, cat, event)
    statuses: dict[str, Status] = {}
    for name in [r.key for r in comp.rounds(cat, event)]:
        st = store.load_race(race_key(cat, event, name))
        if st is not None:
            # every race of the round, the recuperi and the 5°-8° included:
            # the classification of the event owes a line to all of them
            statuses.update(all_statuses(st))
    return S.scheme_classification(
        finals=finals, final_5_8=f58[0] if f58 else [],
        qual_ranking=qual_ranking,
        # whoever rode the 200 m and then missed a round lost that round: her
        # DNS stays on its sheet and she is ranked on her time (`sprint_statuses`)
        statuses=sprint_statuses(store, comp, cat, event, statuses))


# ── keirin: the tournament of UCI 3.2.135 ───────────────────────────────────
#
# Where a velocità is seeded off the 200 m, a keirin is not seeded off anything:
# its first round is the first race of the event, and the jury composes it by
# hand. What the number of riders entered decides is the *shape* of the
# tournament - how many batterie, how many go through, whether the recuperi and
# the semifinali are ridden at all - and that is one row of the UCI table
# (`formats.keirin.SCHEMES`), read here and never typed anywhere.
#
# Like a velocità, two rounds carry a race that is not a round of its own:
#   Turno 1 (or the Quarti) - the recuperi, ridden by everybody the batterie
#                             left behind, composed by the UCI table
#   Finali                  - the final under the title one, 7°-12° with twelve
#                             riders, ridden by whoever the semifinali did not
#                             send to the first final
# Each keeps its own composition, results and statuses in the payload of the
# round it is ridden in, which is the comunicato that publishes it.
#
# The second final is the one of the two that is not always ridden - exactly as
# the 5°-8° of a velocità is not. The programme says what was planned and the
# jury settles it on the first round, before the tournament has sent anybody
# anywhere (`keirin_has_final_b`). Not ridden, there is one final: the riders
# the last round qualified ride it, and everybody else keeps the place how far
# she got gives her.

REP_HEATS = "rep_heats"          # a round's recuperi: their composition
HEATS_B = "heats_final_b"        # finali: who rides the final under the title
RESULTS_B = "results_final_b"    # finali: its finishing order
FINAL_B = "final_b"              # first round: is the second final ridden


def is_keirin(comp: Competition, event: str) -> bool:
    """True for a keirin - the event the tables of 3.2.135 describe."""
    return comp.event(event).fmt == "keirin"


def keirin_first_round(comp: Competition, cat: str, event: str) -> str:
    """Key of the round the jury composes by hand: the first one in the programme."""
    rounds = [r.key for r in comp.rounds(cat, event)]
    return rounds[0] if rounds else K.TURNO1


def keirin_entrants(el: EntryList, comp: Competition, cat: str,
                    event: str) -> list[str]:
    """Who rides the keirin: the entry list of its first round, NP excluded."""
    return entrants(el, comp, cat, event, keirin_first_round(comp, cat, event))


def keirin_scheme(comp: Competition, el: EntryList, cat: str,
                  event: str) -> K.Scheme:
    """Which row of UCI 3.2.135 this keirin is run under.

    The row is picked by the riders actually entered, read through the check-in:
    declaring an atleta NP the morning of the race can take the event from one
    band into the one below, and the number of batterie has to follow - it is
    the thing the jury would otherwise look up in the regulation with the track
    waiting.
    """
    return K.scheme_for(len(keirin_entrants(el, comp, cat, event)))


def keirin_has_final_b(store, comp: Competition, cat: str, event: str) -> bool:
    """Whether this keirin rides the final under the one for the title.

    UCI 3.2.135 ends every tournament with two finals - 1°-6° and 7°-12° with
    twelve riders in the semifinali - but a programme is free to ride only the
    first and classify the others by how far they got, which is the same
    decision a velocità takes about its 5°-8°. The programme says what was
    planned and the jury can turn it round on the day, on the first round: it
    has to be settled before the last round composes anything, because it is
    that composition that either splits the qualifiers into two races or does
    not.

    The day, then `ProgrammeItem.final_b`, then - for a programme written
    before that field existed - whether the finals round files a *risultati
    finale B* at all.
    """
    first = keirin_first_round(comp, cat, event)
    st = store.load_race(race_key(cat, event, first)) if first else None
    chosen = (st.payload or {}).get(FINAL_B) if st is not None else None
    if chosen is not None:
        return bool(chosen)
    stated = (comp.scheduled(cat, event) or _unscheduled()).final_b
    if stated is not None:
        return bool(stated)
    fin = next((r for r in comp.rounds(cat, event) if r.key == K.FINALI), None)
    return bool(fin and DOC_RESULTS_B in (fin.docs or []))


def keirin_stage(comp: Competition, el: EntryList, state: RaceState
                 ) -> K.Stage | None:
    """The table row's entry for the round in front of the jury, if it rides one."""
    return keirin_scheme(comp, el, state.cat, state.event).stage(state.round_key)


def keirin_heats(comp: Competition, el: EntryList, state: RaceState, *,
                 repechages: bool = False) -> int:
    """How many batterie this round - or its recuperi - is composed of."""
    stage = keirin_stage(comp, el, state)
    if stage is None:
        return 2 if is_finals(state.round_key) else 0
    return stage.rep_heats if repechages else stage.heats


def keirin_repechage_pool(comp: Competition, el: EntryList,
                          state: RaceState) -> list[str]:
    """Who is entitled to ride the recuperi of this round: whoever it left behind.

    Read from the results and not from the entry list: a recupero is not open to
    the whole categoria, and a rider written into one who has already qualified
    is a mistake worth saying out loud while the batterie are being composed.
    """
    stage = keirin_stage(comp, el, state)
    if stage is None or not stage.repechages:
        return []
    return [k for heat in K.not_qualified(bracket_orders(state), stage.qualify,
                                          statuses_of(state)) for k in heat]


def keirin_compose_repechages(comp: Competition, el: EntryList,
                              state: RaceState) -> list[list[str]]:
    """The recuperi of this round, from the riders its batterie left behind."""
    stage = keirin_stage(comp, el, state)
    if stage is None or not stage.repechages:
        return []
    left = K.not_qualified(bracket_orders(state), stage.qualify,
                           statuses_of(state))
    return K.in_bib_order(K.repechage_heats(left, stage.rep_heats))


def keirin_compose_next(comp: Competition, el: EntryList, state: RaceState, *,
                        final_b: bool = True
                        ) -> tuple[str, list[list[str]], list[list[str]]]:
    """(round to compose, its batterie, the second race's) from this round.

    The last round ridden sends riders to two finals at once - the one for the
    title and the one under it - which is why this returns two blocks: they are
    published together, on the sheet of the round that decided them.

    `final_b` off, that second block is empty: the tournament rides one final,
    and the riders it does not qualify are classified where the last round left
    them instead of lining up again (`keirin_has_final_b`).
    """
    sch = keirin_scheme(comp, el, state.cat, state.event)
    stage = sch.stage(state.round_key)
    if stage is None:
        return "", [], []
    nxt = sch.next_key(state.round_key)
    orders = bracket_orders(state)
    if nxt == K.FINALI:
        top, rest = K.final_heats(orders, stage.qualify, statuses_of(state))
        if not final_b:
            rest = []
        return nxt, K.in_bib_order([top] if top else []), \
            K.in_bib_order([rest] if rest else [])
    heats = K.next_heats(stage, orders, bracket_orders(state, REP_RESULTS),
                         sch.stage(nxt).heats if sch.stage(nxt) else 2,
                         statuses_of(state), statuses_of(state, STATUSES_REP))
    return nxt, K.in_bib_order([h for h in heats if h]), []


def keirin_loads(comp: Competition, el: EntryList, state: RaceState,
                 doc_kind: str) -> str:
    """What the sheet on screen composes, '' when it composes nothing.

    Every comunicato of a keirin does two jobs, as in a velocità: it files the
    race just ridden and it sends the riders on. Which sheet does which is
    fixed - the risultati of a round compose its recuperi, the risultati of the
    recuperi compose the round after, and the risultati of the last round
    compose the two finals.
    """
    stage = keirin_stage(comp, el, state)
    if stage is None:
        return ""
    if doc_kind == DOC_RESULTS and stage.repechages:
        return K.REPECHAGES
    if doc_kind == DOC_RESULTS_REP or (doc_kind == DOC_RESULTS
                                       and not stage.repechages):
        return keirin_scheme(comp, el, state.cat, state.event).next_key(
            state.round_key)
    return ""


def load_keirin_round(store, comp: Competition, el: EntryList,
                      state: RaceState, doc_kind: str) -> tuple[str, int]:
    """Compose what this sheet sends riders to, and save it. (what, batterie).

    The recuperi are written onto the round they are ridden in; every other
    round is a race of its own, and the finals get both of their batterie at
    once. Nothing is composed twice: what the jury edits afterwards stays,
    because pressing the button again is what overwrites it.
    """
    what = keirin_loads(comp, el, state, doc_kind)
    if not what:
        return "", 0

    if what == K.REPECHAGES:
        heats = keirin_compose_repechages(comp, el, state)
        if not heats:
            return "", 0
        state.payload[REP_HEATS] = heats_text(heats)
        store.save_race(state, action="load_keirin_repechages")
        return what, len(heats)

    final_b = keirin_has_final_b(store, comp, state.cat, state.event)
    nxt, heats, low = keirin_compose_next(comp, el, state, final_b=final_b)
    if not nxt or not heats:
        return "", 0
    target = ensure_state(store, comp, state.cat, state.event, nxt, el)
    target.payload["heats"] = heats_text(heats)
    target.entrants = [k for h in heats for k in h]
    if nxt == K.FINALI and not final_b:
        # the jury turned the second final off after it had been composed: the
        # round rides one final, and what is left of the other one on the race
        # would still print its sheet and hold its decisions
        for key in (HEATS_B, RESULTS_B, STATUSES_B):
            target.payload.pop(key, None)
    if low:
        # the finals: the second final is a race of its own on the same round,
        # and everybody in it is a starter of that round
        target.payload[HEATS_B] = heats_text(low)
        target.entrants += [k for h in low for k in h
                            if k not in target.entrants]
    store.save_race(target, action="load_keirin_round")
    return nxt, len(heats) + len(low)


def keirin_final_labels(state: RaceState) -> tuple[str, str]:
    """('1°-6°', '7°-12°') - what the two finals of this race ride for."""
    top = bracket_heats(state)
    low = bracket_heats(state, HEATS_B)
    return K.final_labels(len(top[0]) if top else 0, len(low[0]) if low else 0)


def keirin_composition(comp: Competition, el: EntryList, state: RaceState,
                       doc_kind: str, *, final_b: bool = True) -> list[tuple]:
    """The batterie a keirin sheet publishes under its own results.

    Only the sheet that composes the finals carries them: the recuperi and the
    rounds have an ordine di partenza of their own in the register, and printing
    the same batterie twice is how a jury ends up reading the older copy.
    """
    if doc_kind not in (DOC_RESULTS, DOC_RESULTS_REP):
        return []
    if keirin_loads(comp, el, state, doc_kind) != K.FINALI:
        return []
    _nxt, top, low = keirin_compose_next(comp, el, state, final_b=final_b)
    labels = K.final_labels(len(top[0]) if top else 0,
                            len(low[0]) if low else 0)
    out = []
    for heats, name in ((top, labels[0]), (low, labels[1])):
        if heats and name:
            out.append((composition_title(f"{label('final')} {name} posto"),
                        heats, [name]))
    return out


def keirin_statuses(statuses: dict[str, Status]) -> dict[str, Status]:
    """The decisions of a keirin *as an event*: everything but a relegation.

    A REL settles one batteria - it says who won it - and stops there; the rider
    carries on and is classified by how far she got. Everything else follows her
    to the end: a keirin has no qualifying time to be re-ranked on, so a rider
    who was not at the gate for her recupero has nothing else on the sheet, and
    the decision the jury took is what the classification files.
    """
    return {k: v for k, v in statuses.items() if v is not Status.REL}


def keirin_standings(store, comp: Competition, el: EntryList, cat: str,
                     event: str) -> Result:
    """Classification of the whole keirin: the two finals, then how far each got.

    Under the finals the riders are ranked by the round they went out in, latest
    first, and inside a round by their place in their batteria - all the riders
    who came just under the cut, then all the ones under those. That is the UCI
    table's own ranking ("all ranked 13, all ranked 17"), resolved to one line
    per rider by the order of the batterie.
    """
    sch = keirin_scheme(comp, el, cat, event)
    statuses: dict[str, Status] = {}
    eliminated: list[tuple[str, list[str]]] = []

    for stage in sch.stages:
        st = store.load_race(race_key(cat, event, stage.key))
        if st is None:
            continue
        statuses.update(all_statuses(st))
        orders = bracket_orders(st)
        own = statuses_of(st)
        left = K.left_behind(orders, stage.qualify, own)
        if stage.repechages:
            # the riders the batterie left behind rode the recuperi: they went
            # out there, not here. Whoever never lined up for them - a DSQ of
            # this round - did go out here, and the sheet has to say so.
            rep = [k for h in bracket_heats(st, REP_HEATS) for k in h]
            eliminated.append((stage.key, [k for k in left if k not in rep]))
            eliminated.append((K.REPECHAGES,
                               K.left_behind(bracket_orders(st, REP_RESULTS),
                                             stage.rep_qualify,
                                             statuses_of(st, STATUSES_REP))))
        else:
            eliminated.append((stage.key, left))

    fin = store.load_race(race_key(cat, event, K.FINALI))
    finals: list[list[str]] = []
    if fin is not None:
        statuses.update(all_statuses(fin))
        for results, composed in ((bracket_orders(fin), bracket_heats(fin)),
                                  (bracket_orders(fin, RESULTS_B),
                                   bracket_heats(fin, HEATS_B))):
            # before a final is ridden its riders are still on the sheet, in the
            # order they were composed in: a classification printed at that
            # point is incomplete, not wrong about who is in the event
            finals.append((results or composed or [[]])[0])

    res = K.classification(finals, eliminated,
                           statuses=keirin_statuses(statuses))
    # anybody the tournament never reached - entered, and out before a result
    # was typed anywhere - still belongs on the classification of the event
    seen = {p.key for p in res.placings}
    rest = [k for k in keirin_entrants(el, comp, cat, event) if k not in seen]
    if not rest:
        return res
    # first in the list is last on the sheet: `classification` reads the rounds
    # backwards, so that whoever went out later finishes ahead
    return K.classification(finals, [("", rest)] + eliminated,
                            statuses=keirin_statuses(statuses))


# ── multi-round_key standings ───────────────────────────────────────────────────

def omnium_prove(comp: Competition, cat: str, event: str = "omnium") -> list[str]:
    """The prove this omnium actually rides, in the order it rides them.

    The four of the UCI omnium are what `formats.omnium` scores, and they are
    not what every omnium is made of: a categoria may ride three of them, and a
    programme that schedules two is two prove and not «two out of four». What
    the sheets are made of is what the programme declares, so the prove are
    read from there and the four names are only the vocabulary they are
    written in.
    """
    from .formats import omnium as O

    return [r.key for r in comp.rounds(cat, event) if r.key in O.ROUNDS]


def omnium_standings(store, comp: Competition, el: EntryList, cat: str,
                     event: str = "omnium", upto: str = "") -> Result:
    """Running omnium classification across the prove of the event.

    `upto` stops at that prova included - what a *classifica parziale* is: the
    standings as they stand when one prova has been ridden and the next has not,
    which is also the ordine di partenza of the next one.
    """
    names = omnium_prove(comp, cat, event)
    if upto in names:
        names = names[:names.index(upto) + 1]
    done = {}
    for name in names:
        state = store.load_race(_rid(cat, event, name))
        # a prova the jury has filed anything in at all: the arrivals, or - on
        # a race not yet scored - the decision that took a rider out of it. A
        # DNS filed before the race is typed is still what the standings say
        # about that rider
        if state and ((state.payload or {}) or state.statuses):
            done[name] = classify(state, el, comp)
    return O.omnium_classification(done, expected=names,
                                   entrants=omnium_field(store, comp, el,
                                                         cat, event))


def omnium_field(store, comp: Competition, el: EntryList, cat: str,
                 event: str = "omnium") -> list[str]:
    """Who the omnium is ridden by: the whole entry, or who qualified for it.

    Where the programme schedules batterie di qualificazione, the omnium is the
    four prove and the classification is over the riders they sent through -
    whoever went out in the qualification is not in the standings, exactly as
    an eliminated coppia is not in the classifica of a madison.
    """
    rounds = final_rounds(comp, cat, event) if is_composed(comp, cat, event) \
        else []
    if not rounds:
        return entrants(el, comp, cat, event)
    # the first prova is the one the qualification was carried into: the four
    # are loaded together, so any of them says the same thing
    return composed_entrants(store, comp, cat, event, rounds[0], el)


def omnium_carried(store, comp: Competition, el: EntryList, cat: str,
                   event: str = "omnium") -> dict[str, int]:
    """Points each rider takes into the corsa a punti: the first three prove.

    The sheet of that race is scored from them - the jury adds the volate to
    what is already there - so they print in front of the volate, and the total
    of the sheet is the omnium total.
    """
    from .formats import omnium as O

    res = omnium_standings(store, comp, el, cat, event, upto=O.ELIMINATION)
    return {p.key: int((p.data or {}).get("total") or 0) for p in res.placings}


def omnium_prova_points(result: Result, upto: str = "") -> Result:
    """A prova's own result, with the omnium points each placing is worth.

    The risultati of a tempo race or of an eliminazione are read for two things:
    the order, and what it scores. `upto` names the prova, so the column can be
    headed with it.
    """
    from .formats import omnium as O

    for p in result.placings:
        p.data = dict(p.data or {})
        p.data["prova_points"] = (O.placing_points(p.position)
                                  if p.status in CLASSIFIED else 0)
    if upto and "prova_points" not in result.columns:
        result.columns = list(result.columns) + ["prova_points"]
    return result


def omnium_points_race(result: Result, carried: dict[str, int]) -> Result:
    """The corsa a punti as the jury scores it, on the omnium's running total.

    Each rider starts the race from the points already scored in the three
    prove, and every volata is added to those: the total on this sheet is the
    omnium total, not what the single race was worth.

    And the sheet is read in that order. The corsa a punti is the last prova,
    so its risultati *are* the classifica of the omnium: the riders print by
    total, and two on the same total are separated by their passage at the
    last volata - the tiebreak of 3.2.109, the same one the classifica finale
    applies (`formats.omnium.omnium_classification`), and not the placing in
    this race, which its own classification had already decided on points.
    Printed in the order the race was called, the sheet said the winner of the
    corsa a punti had won the omnium.
    """
    own = {p.key: int((p.data or {}).get("_tiebreak", 10 ** 6))
           for p in result.placings}
    for p in result.placings:
        p.data = dict(p.data or {})
        start = int(carried.get(p.key) or 0)
        p.data["carried"] = start
        if p.status in CLASSIFIED:
            p.data["total"] = int(p.data.get("total") or 0) + start
    placings = sorted(result.placings,
                      key=lambda p: (-int((p.data or {}).get("total") or 0),
                                     own.get(p.key, 10 ** 6)))
    result.placings = assign_positions(sort_by_status(placings))
    return result


def bracket_standings(store, comp: Competition, el: EntryList, cat: str,
                      event: str) -> Result:
    """Final classification of a sprint / keirin bracket, across all rounds."""
    from .formats import sprint as S

    rounds = [p.key for p in comp.rounds(cat, event)]
    qual_ranking: list[str] = []
    eliminated: list[tuple[str, list[str]]] = []
    finals: dict[str, list[list[str]]] = {}

    for name in rounds:
        st = store.load_race(_rid(cat, event, name))
        if st is None:
            continue
        kind = round_format(comp, cat, event, name)
        if kind == TIMED:
            res = classify(st, el, comp)
            qual_ranking = [p.key for p in res.placings if p.position]
            continue
        if is_finals(name):
            finals[name] = bracket_orders(st)
            continue
        outcome = bracket_round(st, comp)
        if outcome.eliminated:
            eliminated.append((name, outcome.eliminated))

    ordered_finals = {k: finals[k] for k in sorted(finals)}
    return S.bracket_classification(ordered_finals, eliminated,
                                    qual_ranking=qual_ranking)


# ── composition: batterie and qualification ─────────────────────────────────
#
# Two events are ridden in qualifying batterie whose composition is a decision
# of the jury, not something a result produces: the madison and the omnium.
#
#   * a madison is ridden by numbered coppie, and when there are more of them
#     than the track takes they ride qualifying heats (3.2.157): the jury
#     hands out the numbers *and* splits the coppie;
#   * an omnium with more riders than the finale takes rides a corsa a punti
#     di qualificazione in two batterie: the riders keep their dorsale, so the
#     only decision is who rides where.
#
# Both are taken once, before the event, in the round the programme declares as
# `kind: setup`. Every other round of the event reads them from there: a
# batteria starts only its own entrants, and what follows the batterie - the
# final of a madison, the four prove of an omnium - starts whoever they
# qualified. The vocabulary below is the madison's, because that is the event
# it was written for; `Pairing.numbered` is what tells the two apart.

PAIR_NUMBERS = "pair_numbers"   # payload: entrant key -> number worn
PAIR_HEATS = "pair_heats"       # payload: entrant key -> batteria (1-based)
ELIMINATE = "eliminate"         # payload: entrants eliminated from each batteria
QUALIFIED = "qualified"         # payload of the final: keys that came through


def setup_round(comp: Competition, cat: str, event: str) -> str:
    """Key of the round where this event is composed, '' when it has none."""
    for r in comp.rounds(cat, event):
        if r.kind == ROUND_SETUP:
            return r.key
    return ""


def is_composed(comp: Competition, cat: str, event: str) -> bool:
    """True for an event the jury composes: its batterie are not a result.

    What hangs off this is where a round's startlist comes from - the
    composition round and the batterie it decided, not the entry list read
    straight through (`composed_entrants`).
    """
    return bool(setup_round(comp, cat, event))


def final_rounds(comp: Competition, cat: str, event: str) -> list[str]:
    """The rounds the batterie qualify for, in programme order.

    Everything that is neither the composition round nor a batteria: the
    *Finale* of a madison, the four prove of an omnium. They are the races the
    qualified field is carried into, and the ones the entry list must stop
    ruling once it has been.
    """
    return [r.key for r in comp.rounds(cat, event)
            if r.kind != ROUND_SETUP and not heat_number(r.key)]


def heat_number(round_key: str) -> int:
    """'Qualificazioni Batteria 2' -> 2. 0 when the round is not a heat."""
    _, heat = split_heat(round_key)
    return int(heat.rsplit("-", 1)[1]) if heat else 0


def heat_rounds(comp: Competition, cat: str, event: str) -> list[tuple[int, str]]:
    """(batteria number, round key) for every qualifying heat, in order."""
    return sorted((n, r.key) for r in comp.rounds(cat, event)
                  for n in [heat_number(r.key)] if n)


@dataclass
class Pairing:
    """How one event is composed: who wears what, who rides where.

    `numbered` says whether the numbers are a decision of the jury (a madison:
    the coppia *is* its number) or simply the dorsali the riders already wear
    (an omnium: nothing to hand out, only batterie to fill).
    """

    numbers: dict[str, int] = field(default_factory=dict)  # entrant -> number
    heats: dict[str, int] = field(default_factory=dict)    # entrant -> batteria
    eliminate: int = 0            # entrants out of *each* batteria (3.2.157)
    n_heats: int = 1              # batterie the programme schedules
    pairs: list[str] = field(default_factory=list)  # every entrant, in order
    numbered: bool = True         # the jury hands out the numbers

    def number(self, key: str, default: int = 0) -> int:
        return self.numbers.get(key, default)

    def heat(self, key: str) -> int:
        return self.heats.get(key, 0)

    def in_heat(self, n: int) -> list[str]:
        """The coppie of one batteria, in pairing order."""
        return [k for k in self.pairs if self.heats.get(k) == n]

    @property
    def assigned(self) -> bool:
        """True once the jury has split the coppie into batterie."""
        return bool(self.heats)


def default_numbers(keys: list[str]) -> dict[str, int]:
    """1..N in entry order - the numbering the jury hands out at the track."""
    return {k: i for i, k in enumerate(keys, start=1)}


def bib_numbers(keys: list[str]) -> dict[str, int]:
    """The dorsale is the number, where the jury hands out none.

    An omnium composes batterie and nothing else: every rider already races
    under a number, and it is the one the batterie are read by.
    """
    return {k: int(k) for k in keys if k.isdigit()}


def spread_heats(keys: list[str], n_heats: int) -> dict[str, int]:
    """Deal the coppie into the batterie one by one, 1, 2, 1, 2, ...

    Dealt round-robin rather than cut in half: the entry order is by region,
    and halving it would put the first half of the alphabet in one batteria.
    """
    if n_heats < 1:
        return {}
    return {k: (i % n_heats) + 1 for i, k in enumerate(keys)}


def pairing(store, comp: Competition, cat: str, event: str,
            el: EntryList | None = None) -> Pairing:
    """The composition of one event, as its setup round has it.

    Falls back to the plain numbering when nothing has been composed yet, so a
    sheet printed before the jury got to it still carries a number per coppia.
    Where the numbers are not the jury's to give - an omnium - they are the
    dorsali, and the saved `PAIR_NUMBERS` are not read at all.
    """
    keys = (entrants(el, comp, cat, event) if el is not None else [])
    n_heats = len(heat_rounds(comp, cat, event)) or 1
    rnd = comp.round_of(cat, event, setup_round(comp, cat, event))
    numbered = comp.event(event).fmt == "madison"
    numbering = default_numbers if numbered else bib_numbers
    out = Pairing(numbers=numbering(keys), n_heats=n_heats, pairs=keys,
                  eliminate=rnd.eliminate or 0, numbered=numbered)

    state = store.load_race(race_key(cat, event, setup_round(comp, cat, event)))
    if state is None:
        return out
    p = state.payload or {}
    if not keys:  # no entry list at hand: the saved composition is all there is
        out.pairs = list(state.entrants)
        out.numbers = numbering(out.pairs)
    if numbered:
        out.numbers.update({k: int(v) for k, v
                            in (p.get(PAIR_NUMBERS) or {}).items()
                            if k in out.numbers or not keys})
    out.heats = {k: int(v) for k, v in (p.get(PAIR_HEATS) or {}).items()
                 if not keys or k in out.numbers}
    if p.get(ELIMINATE) is not None:
        out.eliminate = int(p[ELIMINATE])
    return out


def apply_pair_numbers(store, comp: Competition, el: EntryList) -> EntryList:
    """Stamp the numbers the jury assigned onto the entry list's coppie.

    Everything downstream - the sprint notation the jury types, the scoring,
    the printed sheets - already reads `Pair.bib`; this is the one place that
    fills it, so a number assigned in the setup round is the number the whole
    app uses from then on.
    """
    for item in comp.programme:
        if comp.event(item.event).fmt != "madison":
            continue
        pr = pairing(store, comp, item.cat, item.event, el)
        for key, number in pr.numbers.items():
            pair = el.pairs.get(key)
            if pair is not None:
                pair.bib = number
    return el


def composed_entrants(store, comp: Competition, cat: str, event: str,
                      round_key: str, el: EntryList,
                      state: RaceState | None = None) -> list[str]:
    """Who starts one round of an event the jury composes.

    The setup round holds everybody; a batteria holds who was assigned to it;
    what comes after the batterie - the final of a madison, every prova of an
    omnium - holds who they qualified, or, where the event is ridden straight
    off (ED and DA madison), everybody.

    `state` is the round's own race where the caller already has it: the
    qualified field is read off its payload.
    """
    everyone = entrants(el, comp, cat, event)
    kind = round_format(comp, cat, event, round_key)
    pr = pairing(store, comp, cat, event, el)
    if kind == SETUP:
        return everyone

    if state is None:
        state = store.load_race(race_key(cat, event, round_key))
    qualified = ((state.payload or {}).get(QUALIFIED) if state else None)
    if qualified:
        # the batterie were carried into this race: that startlist is a result,
        # and the entry list must not quietly add an entrant back to it. It is
        # called by the number the field wears - the coppia number of a
        # madison, the dorsale of an omnium - not by the order the batterie
        # sent them through: the speaker reads a startlist that runs by number.
        through = [k for k in qualified if k in everyone]
        return _by_number(through, pr)

    n = heat_number(round_key)
    if n and pr.assigned:
        return _by_number(pr.in_heat(n), pr)
    return _by_number(everyone, pr)


def _by_number(keys: list[str], pr: Pairing) -> list[str]:
    """Coppie in the order they are called: by the number they wear.

    Not the order of the entry list - once the numbers are handed out they are
    what everyone reads, the speaker first, and a startlist that runs by region
    makes them hunt for a number down the page.
    """
    return sorted(keys, key=lambda k: (pr.number(k, 10_000), k))


def heat_cut(result: Result, eliminate: int,
             ) -> tuple[list[str], list[str]]:
    """(qualified, eliminated) for one batteria, per 3.2.157.

    `eliminate` entrants go out of each heat, counted *among those who started*:
    a coppia that never took the start is not one of the eliminated, it is
    simply not there. Whoever did not finish does not go through either
    (classification rule A: they do not progress to the next round), so what
    qualifies is the head of the heat's own classification.
    """
    started = [p for p in result.placings if p.status is not Status.DNS]
    ranked = [p.key for p in started if p.position]
    n_through = max(0, len(started) - max(0, eliminate))
    qualified = ranked[:n_through]
    return qualified, [p.key for p in started if p.key not in qualified]


def qualify_count(state: RaceState, eliminate: int) -> int:
    """How many entrants of one batteria go through it.

    Counted on the startlist as it stands, not on the classification, so the
    number is there before a single sprint is entered - and counted among those
    that *started* (3.2.157): a DNS is not one of the eliminated, so it does
    not take a place away from anybody.
    """
    statuses = statuses_of(state)
    started = sum(1 for k in state.entrants
                  if statuses.get(k) is not Status.DNS)
    return max(0, started - max(0, eliminate))


def heat_qualifiers(state: RaceState, el: EntryList, comp: Competition,
                    eliminate: int) -> tuple[list[str], list[str]]:
    """(qualified, eliminated) of one batteria, as entrant keys.

    A madison is scored by the number the coppia wears, so its classification
    comes back keyed by number: here it is read back into the coppie the rest
    of the app works with. Everywhere else the key already *is* the dorsale.
    """
    result = classify(state, el, comp)
    key_of = ({v: k for k, v in pair_bib_map(state, el).items()}
              if state.fmt == MADISON else {})
    through, out = heat_cut(result, eliminate)
    return ([key_of.get(k, k) for k in through],
            [key_of.get(k, k) for k in out])


def load_qualified(store, comp: Competition, el: EntryList, cat: str,
                   event: str, rounds: list[str] | None = None,
                   current: RaceState | None = None) -> dict:
    """Send whoever every batteria qualified into the rounds that follow them.

    Those rounds are races of their own: they start the qualifiers and nobody
    else, seeded across the heats - the winners of every batteria first, then
    the seconds, and so on - so that no batteria is favoured by the order.

    A madison has one of them, its finale. An omnium has four: the qualified
    field rides all of the prove, so the four are loaded together and the
    classifica of the event is over them alone.

    `current` is the heat open in front of the jury, whose latest entry may not
    be on disk yet. Returns what happened, for the page to report.
    """
    pr = pairing(store, comp, cat, event, el)
    missing, heats, order = [], {}, []
    for n, key in heat_rounds(comp, cat, event):
        state = (current if current is not None and current.round_key == key
                 else store.load_race(race_key(cat, event, key)))
        if state is None:
            missing.append(key)
            continue
        through, out = heat_qualifiers(state, el, comp, pr.eliminate)
        if not through:
            missing.append(key)
            continue
        heats[n] = (through, out)
        order.append(through)

    # 1° batt. 1, 1° batt. 2, 2° batt. 1, ... - the qualifying order, dealt
    # out, then read back by the number the field wears: it is the startlist
    # of every round that follows, and those are called by number
    # (`composed_entrants`), not by how the batterie sent them through.
    qualified = _by_number([k for row in zip_longest(*order) for k in row if k],
                           pr)
    info = {"missing": missing, "heats": heats, "qualified": qualified,
            "eliminate": pr.eliminate, "rounds": []}
    if not qualified:
        return info

    for key in (rounds if rounds is not None
                else final_rounds(comp, cat, event)):
        fin = ensure_state(store, comp, cat, event, key, el)
        fin.payload[QUALIFIED] = qualified
        fin.payload["qual_heat"] = {k: n for n, (through, _) in heats.items()
                                    for k in through}
        fin.entrants = qualified
        store.save_race(fin, action="load_qualified")
        info["rounds"].append(key)
        info.setdefault("final", fin)
    return info


def eliminated_suggestion(comp: Competition, heats: list[int]) -> int:
    """How many coppie each batteria has to drop to fit the track (3.2.157).

    The heats qualify *up to* the track maximum without having to fill it, and
    never eliminate fewer than two per heat - so this is a floor the jury can
    raise, not a number the app imposes. The limit is the madison's own, per
    track length; an omnium has no table to read, so its floor is all there is
    and the number comes from the programme.
    """
    limit = madison_track_teams(comp.track_len)
    started = sum(heats)
    n = len(heats) or 1
    if not limit or started <= limit:
        return MIN_ELIMINATED
    # equal number out of every heat, enough to bring the field within the limit
    return max(MIN_ELIMINATED, -(-(started - limit) // n))


# ── reset ───────────────────────────────────────────────────────────────────

def saved_races(store, cat: str, event: str) -> list[RaceState]:
    """Every race saved on disk for one (category, event).

    Matched on the state's own fields, not on the id: a heat lives in a race of
    its own (`qualificazioni-batteria-1`) and would not be found by listing the
    rounds of the programme.
    """
    out = []
    for rid in store.list_races():
        st = store.load_race(rid)
        if st and st.cat == cat and st.event == event:
            out.append(st)
    return sorted(out, key=lambda s: s.race_id)


def has_results(state: RaceState) -> bool:
    """Whether anything was entered beyond the startlist the programme built."""
    return bool(state.heats or state.statuses or (state.payload or {})
                or state.decision or state.communiques)


def reset_event(store, cat: str, event: str, *, actor: str = "") -> list[str]:
    """Delete every saved race of one (category, event), qualifying rounds and
    heats included. Returns the ids removed.

    Each file is snapshotted before it goes (`.snapshots/`), so a reset made by
    mistake can still be restored. The communiqué register is left alone: a
    number that was issued stays issued, and reprinting the same document takes
    its planned number back.
    """
    ids = [s.race_id for s in saved_races(store, cat, event)]
    for rid in ids:
        store.delete_race(rid, actor=actor)
    if ids:
        store.journal(action="reset_event", target=f"{cat}/{event}",
                      actor=actor, extra={"races": ids})
    return ids


def race_key(cat: str, event: str, round_key: str) -> str:
    """Store id of a race round_key."""
    from .models import race_id
    return race_id(cat, event, round_key)


_rid = race_key
