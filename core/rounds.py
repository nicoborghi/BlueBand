"""What an event runs, proposed - the fasi a format has, before anybody edits.

`plan_day` proposes a comunicato per document; this proposes a *fase per race*.
The jury says which categoria contests which event and answers the two or
three questions the format actually asks - a velocità qualifies 12 or 8, a
keirin does or does not ride its second final, a madison eliminates so many
coppie per batteria - and gets back the whole list of fasi, each with a
distance, its giri, its volate and the documents it files.

Everything here is a **proposal**. Nothing it returns is more true than what
the jury types over it: `propose_round` re-proposes one fase, which is what the
↩ button on the Programma page restores, and a value that differs from the
proposal is simply a value the jury chose.

Nothing is invented either. Every number comes from somewhere that already
knew it:

    the fasi of a velocità      formats.sprint.SCHEMES
    the fasi of a keirin        formats.keirin (the shape, not the batterie)
    the four prove of an omnium formats.omnium.ROUNDS
    the distance                core.distances - a table, seeded from a
                                programme that was ridden
    the giri                    config.laps_from_distance, from the track
    le volate                   core.distances.sprints
    coppie eliminate            config.MIN_ELIMINATED (3.2.157)
    which documents a fase may  programme.docs_available

What it cannot know it leaves empty, which is a blank field on the page: a
keirin states its giri and no distance at all, and no table here says how many
giri a keirin is.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from . import distances as DIST
from .config import (DOC_CLASSIFICATION, DOC_PARTIAL, DOC_RESULTS,
                     DOC_RESULTS_58, DOC_RESULTS_B, DOC_RESULTS_REP,
                     DOC_STARTLIST, DOC_STARTLIST_REP, MIN_ELIMINATED,
                     ROUND_SETUP, Competition, Round, laps_from_distance)
from .formats import keirin as K
from .formats import omnium as O
from .formats import sprint as S
from .models import heat_key

#: **Programme vocabulary, not labels** (see `formats.omnium`): the keys the
#: builder schedules a fase under. `race.round_format` reads two of them by
#: their first letters - a fase starting with *Qualificazioni* is ridden
#: against the clock, one starting with *Final* rides for places - so these are
#: not free wording: they are what makes the app find the race.
QUALIFYING = "Qualificazioni"           # the fase a pursuit or a 200 m opens on
FINALS = "Finali"                       # the two finals seeded from it
FINAL = "Finale"                        # one race, and it is the whole event
PAIRING = "Composizione coppie"         # madison: numbers and batterie
HEAT_SETUP = "Composizione batterie"    # omnium: who rides which batteria

#: How many go through from a qualification against the clock to the finals.
#: Four is what the pursuits and the velocità a squadre of CITA26 state, and
#: what two finals need; it is offered in the form, not imposed.
FINALISTS = 4


@dataclass(frozen=True)
class Options:
    """What the jury answers when it adds a race, before any fase exists.

    Only some of these mean anything to a given format - see `options_for`,
    which is what decides the fields the *Aggiungi* form shows.
    """

    scheme: str = S.DEFAULT_SCHEME  # velocità: "12" | "8" qualified
    final_5_8: bool = False         # velocità: is the 5°-8° final ridden
    final_b: bool = True            # keirin: is the second final ridden
    heats: int = 0                  # batterie di qualificazione (0 = none)
    eliminate: int = 0              # eliminated from each of them
    qualify: int = FINALISTS        # through from a qualification to the finals
    #: inseguimento (individuale or a squadre): ridden as one race against the
    #: clock, with the classifica made straight from the times, instead of a
    #: qualification and the two finals it seeds. It is what a categoria with
    #: five squadre entered does, and the programme has to be able to say it.
    direct_final: bool = False
    # how many start together in a round against the clock: two, one per
    # straight, or one at a time. It differs by categoria - thirty entered ride
    # a chilometro two at a time, eight ride it one at a time - which is why it
    # is asked here, per race, and not once per event
    per_start: int = 0              # 0 = whatever the event says
    #: velocità / inseguimento a squadre: how many atleti a squadra fields.
    #: The regulation states it per event (`Event.team_size`) and that is
    #: what this is seeded with; a categoria authorised to ride with one fewer
    #: says so here, per race, the same way `per_start` is said.
    team_size: int = 0              # 0 = whatever the event says


#: Which question each format asks. The order is the order the form shows them.
OPTIONS = {
    "sprint": ("scheme", "final_5_8"),
    "keirin": ("final_b",),
    "madison": ("heats", "eliminate"),
    "omnium": ("heats", "eliminate"),
    "timed": ("direct_final", "qualify", "per_start"),
    "timed_team": ("direct_final", "qualify", "per_start", "team_size"),
    "time_trial": ("per_start",),
}


def options_for(fmt: str) -> tuple[str, ...]:
    """The fields of `Options` this format actually uses ( () for the rest)."""
    return OPTIONS.get(fmt, ())


#: The options that change *which fasi there are*, or what they file - as
#: opposed to how one of them is ridden. Answering one of these is answering a
#: different question about the race, so the fasi follow at once: an
#: inseguimento set to «Finale diretta» must not go on offering a
#: Qualificazioni nobody is going to ride. The others (`per_start`, `qualify`)
#: leave the list alone and are simply written down.
SHAPE = ("scheme", "heats", "direct_final", "final_5_8", "final_b")


# ── proposing ───────────────────────────────────────────────────────────────

def propose(comp: Competition, cat: str, event: str,
            opts: Options | None = None) -> list[Round]:
    """Every fase this race runs, in the order it is ridden."""
    opts = opts or Options()
    fmt = comp.event(event).fmt
    keys = _keys(fmt, opts)
    return [_round(comp, cat, event, key, kind, opts) for key, kind in keys]


def propose_round(comp: Competition, cat: str, event: str, key: str,
                  opts: Options | None = None) -> Round:
    """One fase, re-proposed - what the ↩ button on the Programma page restores.

    A fase the format does not schedule (the jury added or renamed one) still
    gets a proposal: the table is asked for the distance under whatever it is
    called, and the rest follows from it.
    """
    opts = opts or Options()
    fmt = comp.event(event).fmt
    kind = dict(_keys(fmt, opts)).get(key, "")
    return _round(comp, cat, event, key, kind, opts)


def _keys(fmt: str, opts: Options) -> list[tuple[str, str]]:
    """(fase, kind) for a format, in the order they are ridden."""
    if fmt == "entrylist":
        return []
    if fmt == "sprint":
        # the 200 m first, then whichever rounds the chosen scheme rides
        return [(QUALIFYING, "")] + [(k, "") for k in S.scheme(opts.scheme).rounds]
    if fmt == "keirin":
        # the shape only: how many batterie each of these runs comes off UCI
        # 3.2.135 by entrant count, on the day (`race.keirin_scheme`)
        return [(K.TURNO1, ""), (K.SEMI, ""), (K.FINALI, "")]
    if fmt == "madison":
        # the coppie are numbered and split into batterie before anybody rides
        return ([(PAIRING, ROUND_SETUP)] + _heats(opts) + [(FINAL, "")])
    if fmt == "omnium":
        return ([(HEAT_SETUP, ROUND_SETUP)] if opts.heats else []) \
            + _heats(opts) + [(k, "") for k in O.ROUNDS]
    if fmt in ("timed", "timed_team"):
        # one race against the clock, and the classifica comes out of the times
        # - what a categoria too small for finals rides (3.2.086: the finals are
        # ridden by the four fastest, and there have to be four)
        if opts.direct_final:
            return [(FINAL, "")]
        # otherwise ridden twice: against the clock, then the finals it seeds
        return [(QUALIFYING, ""), (FINALS, "")]
    # time_trial, group, elimination: one race, and it is the whole event
    return [(FINAL, "")]


def setup_key(fmt: str, opts: Options | None = None) -> str:
    """The composizione this format runs before it is ridden, '' if none.

    The coppie of a madison, the batterie of an omnium that has any: a
    `ROUND_SETUP` round, which is a job of the jury and not a fase of the race
    (it files no comunicato and rides on no giornata). The Programma page shows
    it as such, so it asks here rather than reading the round list.
    """
    return next((k for k, kind in _keys(fmt, opts or Options())
                 if kind == ROUND_SETUP), "")


def _heats(opts: Options) -> list[tuple[str, str]]:
    return [(heat_key(QUALIFYING, i + 1), "") for i in range(max(0, opts.heats))]


def _round(comp: Competition, cat: str, event: str, key: str, kind: str,
           opts: Options) -> Round:
    """One fase with a proposal in every field the programme can state."""
    if kind == ROUND_SETUP:
        # not ridden: it is where the jury composes the event, so it has no
        # distance, no giri and files nothing
        return Round(key=key, kind=ROUND_SETUP,
                     eliminate=_eliminate(comp, event, opts))

    fmt = comp.event(event).fmt
    km = DIST.distance(event, cat, key)
    laps = _laps(comp, fmt, key, km)
    sprints = _sprints(comp, cat, event, key, laps)
    return Round(
        key=key,
        distance=km or None,
        laps=laps or None,
        # a scratch has the one volata it finishes on, and every sheet already
        # derives that: writing it down would only be a line of YAML that says
        # what the code says
        sprints=sprints if sprints > 1 else None,
        docs=docs_for(comp, cat, event, key, opts),
        heat_size=2 if _man_against_man(fmt, key) else None,
        qualify=_qualify(comp, event, key, opts),
    )


def _laps(comp: Competition, fmt: str, key: str, km: float) -> float:
    """Giri from the distance and the track, where that means anything.

    It does not always. The 200 m lanciati of a velocità is not a lap count -
    it is the last 200 metres, written 0.5 whatever the track measures - and a
    keirin states its giri and no distance at all. Both come back empty, which
    is a field the jury fills in rather than a number it has to notice is
    wrong.
    """
    if not km or (fmt == "sprint" and key.startswith(QUALIFYING)):
        return 0.0
    return laps_from_distance(km, comp.track_len, fmt)


def _sprints(comp: Competition, cat: str, event: str, key: str,
             laps: float | None) -> int:
    """Le volate of a bunch race, by the interval the regulation table states."""
    if not laps:
        return 0
    from . import race as R      # the authority on which scoring a fase is;
    # imported here and not at the top because `race` is the service layer and
    # this module sits under it
    return DIST.sprints(laps, R.round_format(comp, cat, event, key))


def _man_against_man(fmt: str, key: str) -> bool:
    """A velocità batteria: two riders, and the winner goes through.

    A keirin is a bracket too but is not ridden two at a time - six line up,
    and how many batterie there are comes off the UCI table by entrant count.
    Its `heat_size` is therefore not the programme's to state.
    """
    return (fmt == "sprint" and not key.startswith(QUALIFYING)
            and key != S.FINALI)


def _qualify(comp: Competition, event: str, key: str,
             opts: Options) -> int | None:
    """How many go through from this fase, where the programme states it."""
    fmt = comp.event(event).fmt
    if fmt in ("timed", "timed_team") and key == QUALIFYING:
        return opts.qualify or None
    if _man_against_man(fmt, key):
        return 1                     # a velocità sends the winner of each heat
    return None


def _eliminate(comp: Competition, event: str, opts: Options) -> int | None:
    """Eliminated from each batteria - never fewer than the two of 3.2.157.

    How many it *should* be depends on how many turn up, which is not known
    until the check-in (`race.eliminated_suggestion` works it out then). What
    the programme states is the floor, which is what a madison with a field
    that fits the track eliminates anyway.
    """
    if not opts.heats and comp.event(event).fmt == "omnium":
        return None
    return max(MIN_ELIMINATED, opts.eliminate) if opts.eliminate else None


# ── the documents a fase files ──────────────────────────────────────────────

def docs_for(comp: Competition, cat: str, event: str, key: str,
             opts: Options | None = None) -> list[str]:
    """Which sheets this fase produces.

    The order is the order they go out in, which is not always the order of
    `DOC_ALL_KINDS`: a keirin rides its second final *before* the one for the
    title, and a velocità rides the 5°-8° before the finals 1°-4°, so both
    file their results first.
    """
    opts = opts or Options()
    fmt = comp.event(event).fmt
    last = _last_key(fmt, opts)

    docs = [DOC_STARTLIST]
    if fmt == "sprint" and key == S.TURNO1 and S.scheme(opts.scheme).repechage:
        # the recuperi are ridden inside the turno that sends riders to them:
        # they are its second results sheet, not a fase of their own
        docs.append(DOC_RESULTS)
        docs.append(DOC_RESULTS_REP)
    elif fmt == "keirin" and key == K.TURNO1:
        docs += [DOC_RESULTS, DOC_STARTLIST_REP, DOC_RESULTS_REP]
    elif fmt == "sprint" and key == S.FINALI and opts.final_5_8:
        docs += [DOC_RESULTS_58, DOC_RESULTS]
    elif fmt == "keirin" and key == K.FINALI and opts.final_b:
        docs += [DOC_RESULTS_B, DOC_RESULTS]
    else:
        docs.append(DOC_RESULTS)

    if key == last:
        # the classification of the event hangs off its last fase
        docs.append(DOC_CLASSIFICATION)
    elif fmt == "omnium" and key in O.ROUNDS:
        # every prova of an omnium but the last is followed by the standings so
        # far. It is a sheet of its own and not a way of saying "risultati": in
        # the tempo race the two are different tables, and from the second
        # prova on it is also the ordine di partenza of the next one, which is
        # what the register does with it (`communiques.bundles`).
        docs.append(DOC_PARTIAL)
    return docs


def _last_key(fmt: str, opts: Options) -> str:
    keys = [k for k, _kind in _keys(fmt, opts)]
    return keys[-1] if keys else ""


# ── what the jury changed ───────────────────────────────────────────────────

def edited(comp: Competition, cat: str, event: str, rnd: Round,
           opts: Options | None = None) -> set[str]:
    """The fields of this fase that no longer say what the proposal says.

    Nothing is stored to know it: the proposal is recomputed and the two are
    compared. A programme that recorded which of its numbers were typed would
    start lying the first time somebody edited the file by hand.
    """
    fresh = propose_round(comp, cat, event, rnd.key, opts)
    return {f for f in ("distance", "laps", "sprints", "docs", "qualify",
                        "eliminate", "heat_size")
            if getattr(rnd, f) != getattr(fresh, f)}


def options_of(comp: Competition, cat: str, event: str) -> Options:
    """The options a scheduled race is already running under.

    Read back off the programme so the ↩ button re-proposes *this* race and
    not a default one: the fasi it schedules say which velocità scheme it is
    riding, and its documents say whether the optional finals are ridden.
    """
    item = comp.scheduled(cat, event)
    rounds = list(item.rounds) if item else []
    keys = [r.key for r in rounds]
    docs = {d for r in rounds for d in (r.docs or [])}
    heats = sum(1 for k in keys if k.startswith(QUALIFYING) and k != QUALIFYING)
    setup = next((r for r in rounds if r.kind == ROUND_SETUP), None)
    qualifying = next((r for r in rounds if r.key == QUALIFYING), None)
    return Options(
        # a race against the clock ridden as one fase *is* the direct final:
        # nothing is stored to say so, the fasi say it (see `_keys`)
        direct_final=(comp.event(event).fmt in ("timed", "timed_team")
                      and FINAL in keys and QUALIFYING not in keys),
        scheme=S.DEFAULT_SCHEME if S.TURNO1 in keys else "8",
        final_5_8=DOC_RESULTS_58 in docs,
        final_b=DOC_RESULTS_B in docs,
        heats=heats,
        eliminate=(setup.eliminate or 0) if setup else 0,
        qualify=(qualifying.qualify or FINALISTS) if qualifying else FINALISTS,
        per_start=getattr(item, "teams_per_start", 0) or 0,
        # the *effective* number and not the override: the form shows what the
        # squadre are actually built to, which on nearly every programme is the
        # regulation's own number and nowhere in the file
        team_size=comp.team_size(cat, event),
    )


def apply(comp: Competition, cat: str, event: str,
          opts: Options) -> list[Round]:
    """Re-propose a whole race, keeping what only the jury can know.

    The ↩ of a whole race: the fasi and their numbers come back from the
    regulation, and the four fields the proposal has no opinion about - when
    the fase is ridden, how long it takes, what it is called, and the jury's
    own note - stay where they were. Losing a timetable to a button that says
    *riproponi* is not what anybody means by it.
    """
    before = {r.key: r for r in (comp.scheduled(cat, event) or
                                 _empty()).rounds}
    out = []
    for rnd in propose(comp, cat, event, opts):
        was = before.get(rnd.key)
        out.append(replace(rnd, note=was.note, label=was.label,
                           duration=was.duration)
                   if was else rnd)
    return out


def _empty():
    from .config import ProgrammeItem
    return ProgrammeItem(cat="", event="")
