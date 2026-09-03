"""What one squadra is riding: the sheet a team manager asks for.

A rappresentativa turns up with a dozen riders across four categories and one
question - *who of ours rides what, and when do they line up*. The answer is
spread over four elenchi iscritti and, once the jury has composed them, over
the batterie of every round. This module gathers it.

Three things live here, all pure and testable without the app:

* **who a squadra is.** A championship groups riders by *regione* (the
  rappresentativa that enters them), by *società* (the club they are licensed
  to), by provincia or by nazione. Which one applies is declared by the
  programme (`entries.team_group`) and can be overridden in Impostazioni: it is
  the regione at an Italian championship and the società at an open meeting.
* **which batteria a rider is in**, where the jury has already composed one.
  Only what has been decided: an event whose rounds have not been composed
  contributes nothing rather than a guess.
* **the tabella event**: how many riders each categoria fields in each
  event, and how far its licence check has got.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import race as R
from .config import (DEFAULT_TEAM_GROUP, EVENT_ENTRY_LIST, TEAM_GROUPS,
                     Competition)
from .models import EntryList, Rider, split_heat

#: What "squadra" can mean, as a rider carries it. The vocabulary lives in
#: `config` (the programme states which one applies); these are its names here.
BY_REGION = "region"
BY_CLUB = "club"
BY_PROVINCE = "province"
BY_NATION = "nation"
GROUPS = TEAM_GROUPS

DEFAULT_GROUP = DEFAULT_TEAM_GROUP


def group_of(rider: Rider, group: str = DEFAULT_GROUP) -> str:
    """The squadra this rider belongs to, under the chosen meaning."""
    return (getattr(rider, group, "") or "").strip()


def teams(el: EntryList, group: str = DEFAULT_GROUP) -> list[str]:
    """Every squadra with at least one rider, in alphabetical order.

    Riders with nothing in that field are not a squadra of their own: they
    would print as an untitled sheet. They stay off the list and are reported
    by the entry-list validation, which is where a missing regione belongs.
    """
    return sorted({group_of(r, group) for r in el.riders.values()
                   if group_of(r, group)})


def riders_of(el: EntryList, team: str, cat: str = "",
              group: str = DEFAULT_GROUP, *,
              include_ns: bool = True) -> list[Rider]:
    """The riders of one squadra, by bib - of one category when asked."""
    return sorted((r for r in el.riders.values()
                   if group_of(r, group) == team
                   and (not cat or r.cat == cat)
                   and (include_ns or not r.not_starting)),
                  key=lambda r: (r.bib is None, r.bib or 0, r.last_name))


#: A category that does not contest an event has no number there - not a zero,
#: which reads as "nobody entered" instead of "not on the programme".
NOT_CONTESTED = None


@dataclass
class SpecialityRow:
    """One line of the event-entry table: a category across the programme."""

    cat: str
    entries: int = 0          # on the list, NP excluded
    checked_in: int = 0
    missing: int = 0
    not_starting: int = 0
    per_event: dict[str, int | None] = field(default_factory=dict)


def speciality_table(el: EntryList, comp: Competition
                     ) -> tuple[list[SpecialityRow], SpecialityRow]:
    """(one row per categoria, the totals row) - who is entered in what.

    The sheet the jury reads at the verifica and hands over at the briefing:
    how far the licence check has got, and how many riders each categoria
    fields in each event. Built here, so the page and the printed sheet
    can never disagree about it.

    The count per event is the starters, the same as everywhere else in
    the app (`EntryList.entered`): a riserva is on the elenco iscritti, not on
    the track. NP riders are out of every count but their own.
    """
    events = [s for s in comp.event_order() if s != EVENT_ENTRY_LIST]
    rows: list[SpecialityRow] = []
    for cat in comp.cat_order():
        contested = comp.events_for(cat)
        row = SpecialityRow(cat=cat)
        for r in el.by_cat(cat):
            if r.not_starting:
                row.not_starting += 1
                continue
            row.entries += 1
            if r.checked_in:
                row.checked_in += 1
            else:
                row.missing += 1
        row.per_event = {s: (len(el.entered(cat, s)) if s in contested
                             else NOT_CONTESTED) for s in events}
        rows.append(row)

    total = SpecialityRow(cat="")
    for row in rows:
        total.entries += row.entries
        total.checked_in += row.checked_in
        total.missing += row.missing
        total.not_starting += row.not_starting
    total.per_event = {s: sum(row.per_event[s] or 0 for row in rows)
                       for s in events}
    return rows, total


def events_of(rider: Rider, comp: Competition) -> list[str]:
    """The events a rider is entered in, in the order the programme lists them."""
    return [s for s in comp.event_order()
            if s != EVENT_ENTRY_LIST and s in rider.events]


# ── which batteria, where the jury has composed one ─────────────────────────

def heat_index(store, comp: Competition, el: EntryList) -> dict:
    """(cat, event, rider key) -> (round key, batteria number).

    The *first* round of the event that places the rider, in programme order:
    that is the one a squadra needs, because it is the one they line up in.
    Later rounds are composed from results the recap cannot know yet.

    Nothing is written and nothing is composed here: a round with no saved
    race, or a saved race whose batterie have not been filled in, simply does
    not answer. A recap printed before the jury has composed anything is the
    entry list, which is the honest sheet at that point.
    """
    out: dict[tuple[str, str, str], tuple[str, int]] = {}
    for item in comp.programme:
        for rnd in item.rounds:
            state = store.load_race(R.race_key(item.cat, item.event, rnd.key))
            if state is None:
                continue
            for number, keys in heats_of(state):
                for key in keys:
                    for rider in R.entrant_riders(key, el, item.cat):
                        out.setdefault((item.cat, item.event, rider.key),
                                       (rnd.key, number))
    return out


def heats_of(state) -> list[tuple[int, list[str]]]:
    """(batteria number, entrant keys) of one saved race, however it holds them.

    Three shapes, because three kinds of race compose differently:

    * a bunch race split into batterie keeps them in `state.heats`;
    * a velocità or a keirin keeps its bracket in `payload["heats"]`, one list
      per batteria, in the order they are ridden;
    * an inseguimento schedules each batteria as a round of its own
      ("Qualificazioni Batteria 1"), so the whole field of that race is it.
    """
    if state.heats:
        return [(h.number or i + 1, list(h.entrants))
                for i, h in enumerate(state.heats) if h.entrants]
    bracket = R.bracket_heats(state)
    if bracket:
        return [(i + 1, list(keys)) for i, keys in enumerate(bracket) if keys]
    _, heat = split_heat(state.round_key)
    if heat and state.entrants:
        return [(int(heat.rsplit("-", 1)[-1]), list(state.entrants))]
    return []
