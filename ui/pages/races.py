"""RACES ("Gare") - run a race: enter results, classify, print.

Everything typed here is written to `races/<race_id>.json` as soon as you press
*Salva*, with the previous version kept as a snapshot. Reloading the browser or
reopening the app restores the race exactly as it was.
"""

from __future__ import annotations

from collections import Counter
from typing import NamedTuple

import streamlit as st

from core import communiques as C
from core import decisions as DEC
from core import entries as E
from core import race as R
from core.config import (DOC_CLASSIFICATION, DOC_KINDS, DOC_PARTIAL, DOC_RACE,
                         DOC_RESULT_KINDS, DOC_RESULTS, DOC_RESULTS_58,
                         DOC_RESULTS_B,
                         DOC_RESULTS_REP, DOC_STARTLIST, DOC_STARTLIST_REP,
                         EVENT_ENTRY_LIST, NAME_FULL, ROUND_SETUP,
                         Competition, madison_track_teams)
from core.formats import group as G
from core.formats import keirin as K
from core.formats import omnium as O
from core.formats import sprint as S
from core.formats import timed as T
from core.checks import bib_line
from core.formats.base import Result
from core.i18n import gendered, help_text, label, msg, ordinal, plural, ui
from core.models import RaceState, Status, race_slug
from core.parse import (ParseError, format_time, parse_bibs, parse_heats,
                        parse_time_safe)
from core.store import Store
from render import documents as D
from render.render import SIG_PREVIEW_PX, to_html
from ui import decisions_form as DF
from ui import notify, savebar, scroll
from ui.download import save_button
# imported as a name, not through the module: `state` is what a RaceState is
# called in nearly every function here
from ui.state import sticky_select

#: The decisions a jury takes on a race, in the order the fields are drawn.
#: Each is labelled with the code it is written on the sheet (`i18n.STATUSES`)
#: and explained with the words behind it (`HELP["status_*"]`).
STATUS_FIELDS = [Status.DNS, Status.DNF, Status.DSQ, Status.REL]

#: A prova di gruppo has one more: the rider who comes down of her own accord
#: while the race is still on. She is not a ritirata - nothing stopped her -
#: and the points she had scored are not printed (`formats.group`). Nowhere
#: else: a velocità is two riders and a race against the clock is one, and
#: neither of them has a bunch to leave.
BUNCH_STATUS_FIELDS = [Status.DNS, Status.DNF, Status.ABD, Status.DSQ,
                       Status.REL]


def _status_fields(kind: str) -> list[Status]:
    return BUNCH_STATUS_FIELDS if kind in R.BUNCH else STATUS_FIELDS


def render(competition: str, comp: Competition, store: Store) -> None:
    el, _stale = E.effective_entries(store, comp)
    if el is None:
        return          # the menu does not offer this page without one (`app`)
    # the madison coppie wear the numbers assigned in their setup round: stamp
    # them on the entry list before anything reads a number off it
    R.apply_pair_numbers(store, comp, el)

    cat, event, round_key = _pick_race(comp, store)
    if not event:
        notify.warn("no_race_for_category")
        return

    state = R.ensure_state(store, comp, cat, event, round_key, el)
    kind = state.fmt
    # a velocità runs to a scheme decided before the 200 m (see core.race):
    # it is what composes every round from the one before, and what the sheets
    # of this event are made of
    scheme = (R.sprint_scheme(store, comp, cat, event)
              if R.is_sprint(comp, event) else None)
    # a keirin is not seeded from anything: what the number of riders entered
    # decides is the shape of the tournament, and the jury composes the first
    # round itself (see § keirin)
    keirin = R.is_keirin(comp, event) and kind == R.BRACKET
    # the pickers stay on screen, the race header comes to the top: on a laptop
    # the two together do not fit above the fold. Only on the two presses that
    # open a race - the *fase* selectbox, which is the last of the three to be
    # picked, and a pill of the recent row: moving the page under a jury that is
    # still choosing the categoria is exactly the kind of help nobody asked for.
    scroll.anchor("race")
    scroll.requested("race")
    if kind == R.SETUP:
        savebar.render(label=ui("save_pairing"))
        _pairing_page(state, el, comp, store)
        _recent_races(comp, store)
        return
    # This is the header the jury reads while working: the document's own
    # letterhead is dropped from the preview below (`head=False`) instead.
    st.header(f"{cat} · {comp.event(event).short}"
              + (f" · {round_key}" if round_key else ""))
    st.caption(ui("race_line", n=len(state.entrants),
                  info=D.distance_line(d=state.distance or 0,
                                       laps=state.n_laps or 0,
                                       sprints=state.n_sprint or 0)
                  or ui("none_short"),
                  fmt=kind, saved=state.updated_at or ui("none_short")))

    # composed before the sidebar is drawn, so that pressing Salva there saves
    # the grid as it stands and not the notation of the previous run
    heat_box = st.container()
    if kind in (R.TIMED, R.TIMED_TEAM):
        with heat_box:
            _scheme_picker(state, comp, store)
            _finals_not_loaded(state, comp, store)
            _heat_builder(state, el, comp)
    elif keirin:
        with heat_box:
            _keirin_composition(state, el, comp, store)
    elif scheme is not None:
        with heat_box:
            _sprint_not_loaded(state, comp, store, scheme)

    _seed_doc(state, comp, store)

    with st.sidebar:
        # The radio that picks the document is drawn further down the page, so
        # its value is read from the session: on the first run it is not there
        # yet and the radio will land on the first kind anyway. It is read
        # first because the sidebar is the sheet's own: a round that files two
        # results - the turno 1 and its recuperi, the finali and their 5°-8° -
        # asks for the results of the one on screen, and keeps the decisions of
        # the two apart (`race.status_scope`).
        doc_kind = (st.session_state.get(f"doc_{state.race_id}")
                    or _doc_kinds(comp, state, store)[0])
        # no rule here: app.py already draws one under the page selector, and
        # two of them read as an empty section between the pages and the race
        _inputs(state, kind, el, comp, scheme, doc_kind, keirin,
                has_58=R.sprint_has_58(store, comp, cat, event)
                if R.is_sprint(comp, event) else False)
        _statuses(state, el, kind, R.status_scope(doc_kind))
        _decision_panel(state, comp, store, el, R.status_scope(doc_kind))
        # what the log says about the riders of this specialità: the W travels
        # from the fase it was taken in to every fase after it, and the tick is
        # what puts it on paper
        warned = R.warnings_carried(store, comp, cat, event, round_key)
        if warned and not st.checkbox(ui("show_warnings"), value=True,
                                      key=f"warn_{state.race_id}",
                                      help=help_text("show_warnings")):
            warned = {}
        note = _note_field(state, comp, doc_kind,
                           _default_notes(state, comp, store, scheme, el,
                                          keirin))
        # Which sheets open with the tick on is set once, in Impostazioni ->
        # Impostazioni avanzate; here it is still a tick, and what prints is
        # what the jury leaves ticked.
        sign = st.checkbox(ui("signature_tick"),
                           value=comp.branding.signs(doc_kind),
                           key=f"sig_{state.race_id}_{doc_kind}",
                           help=help_text("signature_tick"))
        # only on the classifica: that is the sheet the societies are filed
        # from, and everywhere else the columns are already tight
        classifica = doc_kind == DOC_CLASSIFICATION
        club = classifica and st.checkbox(
            ui("club_column"),
            # on by default: the classifica is the sheet the societies are
            # filed from, and it is the one sheet with the paper to carry them
            value=True,
            key=f"club_{state.race_id}", help=help_text("club_column"))
        # an omnium: the two things its sheets show that no other event has -
        # where each rider lines up for the prova that follows, and the corsa a
        # punti as it was scored under the final classification
        omnium = comp.event(event).fmt == "omnium"
        lane = omnium and doc_kind == DOC_PARTIAL and st.checkbox(
            ui("lane_column"), value=True, key=f"lane_{state.race_id}",
            help=help_text("lane_column"))
        detail = omnium and classifica and st.checkbox(
            ui("points_race_detail"), value=True, key=f"det_{state.race_id}",
            help=help_text("points_race_detail"))
        # the times belong to the risultati of each fase: off by default here,
        # and the width goes to the names instead. A velocità or a keirin has
        # no time to offer at all - places 1-8 come from the batterie and the
        # rest from the ranking of the 200 m, and the classification carries no
        # time column (`formats.sprint.scheme_classification`): there the tick
        # was one that did nothing, and a control that does nothing is worse
        # than no control.
        timed = comp.event(event).fmt not in ("sprint", "keirin")
        time_col = st.checkbox(ui("time_column"), key=f"time_{state.race_id}",
                               help=help_text("time_column")
                               ) if classifica and timed else True
        # a madison is read by coppia: the dorsale is a second number for the
        # same rider and stays off unless the jury wants it on the sheet
        show_bib = kind != R.MADISON or st.checkbox(
            ui("bib_column"), key=f"bib_{state.race_id}",
            help=help_text("bib_column"))
        # Two sizes, because the two readers are not the same: the sheet is
        # read on paper at arm's length, the preview across a desk by whoever
        # is calling the race. Every sheet prints at 9; the classifica is the
        # one that drops a point, because it is the crowded one - it carries
        # the societies and their codes on top of everything else. Unless the
        # competition sets its names in a single column: that gives back the
        # width of a whole column, and the classifica prints at 9 like the rest.
        crowded = (doc_kind == DOC_CLASSIFICATION
                   and comp.branding.name_style != NAME_FULL)
        font = st.slider(ui("table_font_pdf"), 6, 14, 8 if crowded else 9,
                         key=f"font_{state.race_id}_{doc_kind}",
                         help=help_text("font_pdf"))
        screen_font = st.slider(ui("table_font_screen"), 6, 20, 11,
                                key=f"sfont_{state.race_id}",
                                help=help_text("font_screen"))
        st.session_state[f"land_{state.race_id}"] = st.checkbox(
            ui("landscape"), key=f"land_cb_{state.race_id}",
            help=help_text("landscape"))
    savebar.render(label=ui("save"), restore_label=ui("restore_previous"))

    # the grid up the page asked to be saved: now the race carries everything
    # this run typed into it, the sidebar included
    if st.session_state.pop(f"gridsave_{state.race_id}", False):
        store.save_race(state, action="save_heats")
        notify.saved("pairing_saved")

    result = R.classify(state, el, comp)
    # a velocità says what is missing with its own empty radios, and a keirin
    # under each field it is still missing: the generic "batteria N: risultato
    # non inserito" would be six yellow boxes over a sheet being filled in
    if not (kind == R.BRACKET and (scheme is not None or keirin)):
        for w in result.warnings:
            notify.text(w)
    _unplaced_banner(state, el, kind)

    _output(state, result, el, comp, store, kind, font, sign, club,
            time_col, note, show_bib, screen_font, scheme, keirin, lane, detail,
            warned)

    # last of all: by now the race carries everything this run typed into it.
    # The button that asked for this is pinned at the foot of the sidebar and
    # was drawn before any of it (`ui.savebar`).
    _save_bar(state, store)
    # ... and only now the row of recent races, into the place kept for it at
    # the top: whatever was just saved is already the first of them
    _recent_races(comp, store)


def _save_bar(state, store: Store) -> None:
    """Act on the pinned Salva / Ripristina, once the page has been built."""
    action = savebar.requested()
    if action == savebar.SAVE:
        store.save_race(state)
        notify.saved("race_saved")
    elif action == savebar.RESTORE:
        if store.restore(store.race_rel(state.race_id)):
            st.rerun()
        notify.warn("no_previous_version")


# ── madison: the pairing round ──────────────────────────────────────────────

def _pairing_page(state, el, comp: Competition, store: Store) -> None:
    """Compose an event: who rides which batteria, and under what number.

    Nothing is ridden here. It is the round that decides what every later sheet
    of the event says - which entrants line up in each batteria, and, in a
    madison, the number the jury shouts at the sprints - so it is saved on its
    own and read back by every other round.

    A madison hands out the numbers here; an omnium does not (`pr.numbered`):
    its riders keep their dorsale and the only decision is the batteria.
    """
    cat, event = state.cat, state.event
    pr = R.pairing(store, comp, cat, event, el)
    keys = list(state.entrants)
    st.header(f"{cat} · {comp.event(event).short} · {state.round_key}")
    line = ("pairing_line_heats" if pr.numbered else "riders_line_heats") \
        if pr.n_heats > 1 else \
        ("pairing_line_direct" if pr.numbered else "riders_line_direct")
    st.caption(ui(line, n=len(keys), heats=pr.n_heats)
               + f" · {ui('col_last_saved').lower()}: "
               + (state.updated_at or ui("none_short")))
    if not keys:
        notify.warn("no_pairs_entered" if pr.numbered else "no_riders_entered")
        return

    if pr.numbered:
        _guessed_pairings(el, comp, cat, event)
    numbers, heats = _pairing_editor(state, el, keys, pr)
    # the previews below, and everything else on the page, read the numbers off
    # the entry list: stamp what is on screen, saved or not
    for key, n in numbers.items():
        if key in el.pairs:
            el.pairs[key].bib = n

    eliminate = _eliminate_field(state, comp, pr, heats, keys)
    _pairing_problems(numbers, heats, pr, keys)

    # the composition is saved from the same place as everything else: the
    # strip pinned at the foot of the sidebar (`ui.savebar`)
    if savebar.requested() == savebar.SAVE:
        if pr.numbered:
            state.payload[R.PAIR_NUMBERS] = numbers
        state.payload[R.PAIR_HEATS] = heats
        state.payload[R.ELIMINATE] = eliminate
        store.save_race(state, action="save_pairing")
        notify.saved("pairing_saved")

    _pairing_previews(state, el, comp, heats, pr)


def _guessed_pairings(el, comp: Competition, cat: str, event: str) -> None:
    """Say which coppie the app formed by itself, so the jury confirms them.

    Three or more riders entered with a bare X leave the accoppiamento open:
    the entry list says who rides the madison, not with whom, and pairing them
    in bib order is a guess. It is the one thing to settle before the numbers
    are handed out - from here on the coppia *is* its number.
    """
    guessed = [g for g in E.guessed_pairings(el, comp)
               if g[0] == cat and g[1] == event]
    for _cat, _event, region, riders in guessed:
        notify.warn("pairs_guessed_page", region=region, n=len(riders),
                    who=" · ".join(f"{r.bib} {r.last_name}" for r in riders))


# The red of the second number of a coppia, as print.css prints it
RED = "#d93636"

# Num. | Batt. | Coppia | nero | rosso - the batteria needs no more than the
# width of a digit, once the heading says what the digit is
GRID = [1, 1, 2, 3, 3]

# Dors. | Batt. | Atleta | Società - a field that rides under its own dorsale
# has one line per rider, and no number to hand out
GRID_RIDERS = [1, 1, 4, 4]


def _pairing_editor(state, el, keys: list[str], pr) -> tuple[dict, dict]:
    """The grid: one line per entrant, its number and its batteria."""
    if not pr.numbered:
        return dict(pr.numbers), _rider_editor(state, el, keys, pr)
    rid = state.race_id
    c1, c2, _ = st.columns([1, 1, 2])
    if c1.button(ui("number_1_to_n"), help=help_text("number_pairs")):
        _seed_pairing(rid, R.default_numbers(keys), None)
    if pr.n_heats > 1 and c2.button(ui("spread_into_heats"),
                                    help=help_text("spread_pairs")):
        _seed_pairing(rid, None, R.spread_heats(keys, pr.n_heats))

    numbers, heats = {}, {}
    options = list(range(1, pr.n_heats + 1))
    # nothing composed yet: the grid opens on the proposal, not on a page where
    # every coppia sits in the first batteria and the second one is empty
    proposed = {} if pr.assigned else R.spread_heats(keys, pr.n_heats)

    # the headings go once, above the grid: repeated on every line they left
    # the batteria dropdown too narrow to read the number in it
    head = st.columns(GRID, vertical_alignment="bottom")
    for box, title in zip(head, (ui("head_number"), ui("head_heat"),
                                 ui("head_pair"), ui("head_black"),
                                 ui("head_red"))):
        box.caption(title)
    for key in keys:
        riders = R.entrant_riders(key, el)
        c = st.columns(GRID, vertical_alignment="bottom")
        numbers[key] = int(c[0].number_input(
            ui("pair_number"), 1, 999, value=pr.number(key, 1), step=1,
            key=f"num_{rid}_{key}", label_visibility="collapsed"))
        if pr.n_heats > 1:
            current = pr.heat(key) or proposed.get(key, 0)
            heats[key] = int(c[1].selectbox(
                label("heat"), options, key=f"heat_{rid}_{key}",
                index=options.index(current) if current in options else 0,
                label_visibility="collapsed"))
        # the only sheet that carries the A/B letter: here it is what tells
        # one coppia of a region from the other, before the numbers exist
        c[2].write(R.entrant_label(key, el))
        # nero and rosso, in the order the entry list has them: the first rider
        # of the coppia wears the black number, the second the red one
        for i in (0, 1):
            r = riders[i] if i < len(riders) else None
            cell = f"{r.bib or '-'} {r.last_name} {r.first_name}" if r else "-"
            c[3 + i].markdown(f"<span style='color:{RED if i else 'inherit'}"
                              f"'>{cell}</span>", unsafe_allow_html=True)
    return numbers, heats


def _rider_editor(state, el, keys: list[str], pr) -> dict:
    """The grid of an omnium: one line per rider, and the batteria it rides.

    No number column, because there is no number to give: what the sheets are
    read by is the dorsale the rider already wears. Returns the batterie alone
    - the numbers on this page are not a decision, so nothing is saved of them.
    """
    rid = state.race_id
    if pr.n_heats > 1 and st.button(ui("spread_into_heats"),
                                    help=help_text("spread_riders")):
        _seed_pairing(rid, None, R.spread_heats(keys, pr.n_heats))

    heats = {}
    options = list(range(1, pr.n_heats + 1))
    # nothing composed yet: the grid opens on the proposal, not on a page where
    # every rider sits in the first batteria and the second one is empty
    proposed = {} if pr.assigned else R.spread_heats(keys, pr.n_heats)

    head = st.columns(GRID_RIDERS, vertical_alignment="bottom")
    for box, title in zip(head, (label("bib"), ui("head_heat"),
                                 label("rider"), label("club"))):
        box.caption(f"**{title}**" if not title.startswith("**") else title)
    for key in keys:
        riders = R.entrant_riders(key, el, cat=state.cat)
        r = riders[0] if riders else None
        c = st.columns(GRID_RIDERS, vertical_alignment="bottom")
        c[0].write(str(r.bib) if r else key)
        if pr.n_heats > 1:
            current = pr.heat(key) or proposed.get(key, 0)
            heats[key] = int(c[1].selectbox(
                label("heat"), options, key=f"heat_{rid}_{key}",
                index=options.index(current) if current in options else 0,
                label_visibility="collapsed"))
        c[2].write(f"{r.last_name} {r.first_name}" if r else "-")
        c[3].write(r.club if r else "")
    return heats


def _seed_pairing(rid: str, numbers: dict | None, heats: dict | None) -> None:
    """Fill the widgets and rerun.

    The grid lives in the widgets - the composition is only read back from them
    when *Salva* is pressed - so a button that proposes a composition writes
    into the widgets themselves, the way the heat builder does.
    """
    for key, value in (numbers or {}).items():
        st.session_state[f"num_{rid}_{key}"] = int(value)
    for key, value in (heats or {}).items():
        st.session_state[f"heat_{rid}_{key}"] = int(value)
    st.rerun()


def _eliminate_field(state, comp: Competition, pr, heats: dict,
                     keys: list[str]) -> int:
    """How many entrants each batteria drops (3.2.157).

    The programme carries the cut of the event (`eliminate` on the setup
    round) and this is where the jury can move it. The track limit is the
    madison's own - a table read per track length - so it is only shown there;
    an omnium opens on what the programme says, or on the floor of two.
    """
    if pr.n_heats < 2:
        return 0
    sizes = [sum(1 for k in keys if heats.get(k) == n)
             for n in range(1, pr.n_heats + 1)]
    suggested = (R.eliminated_suggestion(comp, sizes) if pr.numbered
                 else R.MIN_ELIMINATED)
    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    n = int(c1.number_input(
        ui("eliminate_last"), 0, 20, value=int(pr.eliminate or suggested),
        step=1, key=f"elim_n_{state.race_id}",
        help=help_text("eliminate_pairs" if pr.numbered
                       else "eliminate_riders")))
    limit = madison_track_teams(comp.track_len) if pr.numbered else 0
    through = sum(max(0, s - n) for s in sizes)
    c2.caption(ui("eliminate_line" if pr.numbered else "eliminate_line_riders",
                  sizes=" + ".join(str(s) for s in sizes), through=through)
               + (ui("eliminate_track_limit", n=limit) if limit else ""))
    return n


def _pairing_problems(numbers: dict, heats: dict, pr, keys: list[str]) -> None:
    if pr.numbered:
        counts = Counter(numbers.values())
        dup = sorted(n for n, c in counts.items() if c > 1)
        if dup:
            notify.error("duplicate_pair_numbers",
                         list=", ".join(str(n) for n in dup))
    if pr.n_heats > 1:
        empty = [n for n in range(1, pr.n_heats + 1)
                 if not any(v == n for v in heats.values())]
        if empty:
            notify.warn("empty_heats" if pr.numbered else "empty_heats_riders",
                        list=", ".join(msg("heat_ordinal", n=n) for n in empty))


def _pairing_previews(state, el, comp: Competition, heats: dict, pr) -> None:
    """The sheets this composition produces, side by side."""
    cat, event = state.cat, state.event
    rounds = R.heat_rounds(comp, cat, event) or [(0, _final_round(comp, cat, event))]
    show_bib = st.checkbox(ui("bib_column"), key=f"bib_{state.race_id}",
                           help=help_text("bib_column"))
    cols = st.columns(len(rounds)) if len(rounds) > 1 else [st.container()]
    for (n, key), box in zip(rounds, cols):
        entrants = ([k for k in state.entrants if heats.get(k) == n] if n
                    else list(state.entrants))
        # by the number each entrant is called under, like the ordine di
        # partenza these previews are: the composition round lists them by
        # region, the batteria that comes out of it is read by number - the
        # coppia's own in a madison, the dorsale everywhere else
        entrants.sort(key=lambda k: pr.number(k, 10_000))
        with box:
            st.caption(ui("pairs_in_heat" if pr.numbered else "riders_in_heat",
                          round=key, n=len(entrants)))
            preview = RaceState(race_id=f"preview_{n}", cat=cat, event=event,
                                round_key=key,
                                fmt=R.round_format(comp, cat, event, key),
                                entrants=entrants)
            (preview.distance, preview.n_laps,
             preview.n_sprint) = comp.distances(cat, event, key)
            doc = D.race_startlist(preview, el, comp, show_bib=show_bib)
            st.html(to_html(doc, comp, head=False, footer=False,
                            signature=False, css=False))


def _final_round(comp: Competition, cat: str, event: str) -> str:
    """The round a madison without heats is ridden in."""
    rounds = [r.key for r in comp.rounds(cat, event) if r.kind != ROUND_SETUP]
    return rounds[-1] if rounds else ""


# ── race picker ─────────────────────────────────────────────────────────────

def _pick_race(comp: Competition, store: Store) -> tuple[str, str, str]:
    """The three selectboxes, reopened on the race left last time.

    The row of recent races goes above them, but it is *drawn* at the end of
    the run (`_recent_races`): a race saved further down the page would
    otherwise reach the row only on the next click, which is exactly the
    moment the jury looks for it. The container reserves the place here; the
    tap that came from it is picked up here too, before the pickers below are
    drawn, because that is what moves them.
    """
    last = store.settings.get("last_race") or {}
    st.session_state[RECENT_BOX] = st.container()
    _jump_requested(comp, store)

    c1, c2, c3 = st.columns(3)
    cats = comp.cat_order()
    cat = _sticky(c1, ui("category"), cats, "ga_cat", last.get("cat"))
    events = [s for s in comp.events_for(cat) if s != EVENT_ENTRY_LIST]
    if not events:
        return cat, "", ""
    event = _sticky(c2, ui("event"), events, "ga_event", last.get("event"),
                    format_func=lambda s: comp.event(s).short)
    rounds = [p.key for p in comp.rounds(cat, event)] or [""]
    # the one picker that moves the page: a fase is what opens a race, and the
    # callback is what tells a pick apart from a fase replaced under the jury
    # because the categoria above it changed (see `ui.scroll`)
    round_key = _sticky(c3, ui("round"), rounds, "ga_round", last.get("round"),
                        on_change=_round_picked)

    picked = {"cat": cat, "event": event, "round": round_key}
    if picked != last:
        store.set_setting("last_race", picked)
    return cat, event, round_key


def _round_picked() -> None:
    """A fase was chosen by hand: bring the race under the pickers."""
    scroll.request("race")


#: How many of the races last worked on are offered above the pickers. Four:
#: they are `AL · Ins. Individuale · Qualificazioni` long, and a row that wraps
#: onto a second line pushes the pickers down the page - which is the opposite
#: of what a shortcut is for.
RECENT = 4


def _jump_requested(comp: Competition, store: Store) -> None:
    """Move the pickers onto the race whose pill was tapped, if one was.

    A *tap*, not a selection. Acting on whatever the row happens to hold would
    drag the page back there on every rerun and make the three selectboxes
    unusable; clearing the pill afterwards is not allowed either - a widget's
    own key cannot be written once it is drawn. So the tap is recorded by the
    callback, consumed here exactly once, and the same pill tapped again works
    like the first time.
    """
    picked = st.session_state.pop(RECENT_JUMP, None)
    race = next((r for r in _recent(comp, store) if r.race_id == picked), None)
    if race is None:
        return
    # the pickers are keyed widgets drawn just below: setting their session
    # values before they exist is what moves them
    st.session_state.update({"ga_cat": race.cat, "ga_event": race.event,
                             "ga_round": race.round_key})
    # a pill is a press like the fase is: the run it starts scrolls to the race
    scroll.request("race")
    st.rerun()


def _recent_races(comp: Competition, store: Store) -> None:
    """The fasi last saved, one tap away - drawn into the place kept for it.

    A championship is not run one specialità at a time: the risultati of a
    batteria are typed while another event is on the track, and the jury moves
    between four or five fasi all afternoon. Doing that through three
    selectboxes - categoria, then specialità, then fase, each one reloading the
    next - is three picks to go back to the sheet left two minutes ago.

    Called last, so a race saved anywhere on the page is already at the head of
    the row when the row is built.
    """
    box = st.session_state.get(RECENT_BOX)
    races = _recent(comp, store)
    if box is None or not races:
        return
    labels = {r.race_id: _race_pill(comp, r) for r in races}
    with box:
        st.pills(ui("recent_races"), list(labels), key=RECENT_PILL,
                 format_func=labels.get, label_visibility="collapsed",
                 on_change=_jump_to, help=help_text("recent_races"))


def _recent(comp: Competition, store: Store) -> list:
    """The races last written that this programme still schedules."""
    return [r for r in store.recent_races(RECENT)
            if comp.scheduled(r.cat, r.event)]


#: The pill row: where it is drawn, what it is keyed by, and where a tap on it
#: is left for the script to pick up.
RECENT_BOX = "ga_recent_box"
RECENT_PILL = "ga_recent"
RECENT_JUMP = "ga_recent_jump"


def _jump_to() -> None:
    st.session_state[RECENT_JUMP] = st.session_state.get(RECENT_PILL)


def _race_pill(comp: Competition, race) -> str:
    """`AL · Velocità · Quarti` - what the jury calls that sheet."""
    return " · ".join(p for p in (race.cat, comp.event(race.event).short,
                                  race.round_key) if p)


#: Where the sheet last worked on is remembered, next to the race itself
#: (`_pick_race` keeps `last_race`). Both are settings of the competition and
#: not of the session: leaving the page - or closing the browser on it - must
#: bring the jury back to the sheet it was on, not to the ordine di partenza of
#: a race that has already been ridden.
LAST_DOC = "last_doc"


def _seed_doc(state, comp: Competition, store: Store) -> None:
    """Open the race on the document left last time, where it has one.

    Streamlit drops the state of a widget it has not drawn, so the *Documento*
    radio comes back empty from every other page and would land on the first
    kind. Seeded here, before the sidebar reads it, and only when the sheet is
    one this race publishes - a classifica remembered from a velocità is not a
    sheet a madison batteria has.
    """
    key = f"doc_{state.race_id}"
    if st.session_state.get(key):
        return
    last = store.settings.get(LAST_DOC)
    if last in _doc_kinds(comp, state, store):
        st.session_state[key] = last


def _sticky(container, label: str, options: list[str], key: str, saved,
            **kwargs) -> str:
    """The three race pickers, reopened on the race left last time.

    Thin wrapper on `state.sticky_select`, where the reasoning lives: the race
    last saved seeds the session and nothing more.
    """
    return sticky_select(container, label, options, key, saved, **kwargs)


# ── result entry ────────────────────────────────────────────────────────────

def _inputs(state, kind: str, el, comp: Competition, scheme=None,
            doc_kind: str = "", keirin: bool = False, *,
            has_58: bool = False) -> None:
    p = state.payload
    rid = state.race_id

    if kind == R.ELIMINATION:
        st.subheader(ui("eliminations"))
        p["eliminated"] = st.text_input(
            ui("elimination_order"), p.get("eliminated", ""),
            key=f"elim_{rid}",
            help=help_text("elimination_order", "bibs_csv"))
        # the same flag every other field of the page carries: a dorsale that
        # is not at the start cannot be eliminated from the race, and the same
        # one written twice is a line to look at now, not a warning under the
        # classification once the race is over
        notify.flag(bib_line(p["eliminated"],
                             expected=state.entrants).flag)
    elif keirin:
        # a keirin is called in by batteria: the arrival of each, as dorsali
        _keirin_inputs(state, el, comp, doc_kind)
    elif kind == R.BRACKET and scheme is not None:
        # a velocità run to a scheme asks for winners, not for notation
        _velocita_inputs(state, el, scheme, doc_kind, has_58)
    elif kind == R.BRACKET:
        _bracket_inputs(state, el)
    elif kind in (R.TIMED, R.TIMED_TEAM):
        _timed_inputs(state, el)
    else:
        _sprint_inputs(state, kind, el)
        started = R.bunch_startlist(state, el, kind)
        c1, c2 = st.columns(2)
        p["laps_gained"] = c1.text_input(
            ui("laps_gained"), p.get("laps_gained", ""), key=f"lg_{rid}",
            placeholder="7, 12", help=help_text("laps_csv"))
        p["laps_lost"] = c2.text_input(
            ui("laps_lost"), p.get("laps_lost", ""), key=f"ll_{rid}",
            placeholder="3, 3, 9", help=help_text("laps_csv"))
        # a lap is worth twenty points: a number typed here that nobody is
        # riding under moves the whole classification, so it is flagged where
        # it is typed. `3, 3` is two laps and not a mistake - hence repeats_ok.
        for box, text in ((c1, p["laps_gained"]), (c2, p["laps_lost"])):
            notify.flag(bib_line(text, expected=[str(b) for b in started],
                                 repeats_ok=True).flag, where=box)


# ── sprints ─────────────────────────────────────────────────────────────────

def _sprint_cells(raw: str) -> list[str]:
    """The sprints as typed, one string per sprint - no parsing, no loss.

    Only the trailing dashes go: a leading one is a first sprint left empty,
    and the field it belongs to has to stay empty on screen for the jury to
    see it. (The scoring skips it and says so - see the «slittano» caption.)
    """
    t = str(raw or "").strip().rstrip("-")
    return [c.strip() for c in t.split("-")] if t else []


def _sprint_note(cell: str, startlist, kind: str) -> str:
    """The short flag shown next to one sprint: wrong bib, too few finishers.

    The same notation as every other field of the page (`core.checks`): a
    sprint of a corsa a punti or of a madison scores four riders, so fewer than
    four placed is `<4` - which is the one thing this field asks for that the
    heat fields do not.
    """
    return bib_line(
        cell, expected=[str(b) for b in startlist],
        min_placed=(G.MIN_SPRINT_FINISHERS if kind in (R.POINTS, R.MADISON)
                    else 0)).flag


def _sprint_inputs(state, kind: str, el) -> None:
    """One numbered field per sprint, instead of one long notation string.

    The notation stays the canonical form in the payload - the fields only
    compose it - so the scoring, the sprint columns on the sheet, the speaker's
    banner and the races already on disk are untouched. What changes is that
    the jury can see *which* sprint each field is: correcting the second one
    used to mean counting dashes in `3,7,1,9-7,3,9,1-...`.

    Plain text_inputs and not a data_editor, which was tried and taken out: a
    cell only commits on Enter or on losing focus, so the first click on Salva
    was eaten by the commit and had to be made twice. A text_input hands the
    click through, and AppTest can drive it, which a data_editor cannot.
    """
    p, rid = state.payload, state.race_id
    st.subheader(ui("sprints"))
    startlist = R.bunch_startlist(state, el, kind)

    if kind == R.SCRATCH:
        # one arrival, not a series: a single field says it all - and it is
        # checked like every other one. It used to be the only field of the
        # page that took a dorsale without a word about it.
        p["sprints"] = st.text_input(ui("arrival_order"), p.get("sprints", ""),
                                     key=f"spr_{rid}",
                                     help=help_text("sprint_order"))
        notify.flag(_sprint_note(p["sprints"], startlist, kind))
        return

    # The string lives in the session, seeded once from the race on disk: the
    # state is reloaded from disk on every run, so what has been typed and not
    # yet saved would be thrown away. Same rule as `_pick`: seed, never re-seed.
    slot = f"sprstr_{rid}"
    if slot not in st.session_state:
        st.session_state[slot] = p.get("sprints", "")
    ver = _adopt_string(rid, slot)
    cells = _sprint_cells(st.session_state[slot])
    planned = state.n_sprint or 0
    # the programme decides how many sprints there are: exactly that many
    # fields, no spare line. Only when the number is missing does the list
    # grow as it is filled, so the race can still be entered.
    n = max(planned, len(cells)) if planned else len(cells) + 1
    # the double-points sprint is the planned last one (see formats.group)
    doubled = planned if kind in (R.POINTS, R.MADISON) else 0

    st.html(_FIELD_CSS)
    new: list[str] = []
    with st.container(key=f"sprints_{rid}"):
        for i in range(n):
            c1, c2 = st.columns([1, 4], vertical_alignment="center")
            final = i + 1 == doubled
            cls = "cmsr-n fin" if final else "cmsr-n"
            mark = ui("sprint_mark_final" if final else "sprint_mark", n=i + 1)
            c1.markdown(f"<div class='{cls}'>{mark}</div>",
                        unsafe_allow_html=True)
            val = c2.text_input(
                ui("sprint_n", n=i + 1), cells[i] if i < len(cells) else "",
                key=f"spr_{rid}_{ver}_{i}", label_visibility="collapsed",
                help=help_text("sprint_order",
                               *(["sprint_final"] if final else [])))
            new.append(str(val or "").strip())
            # the flag goes under its own field, and only when there is one:
            # a column for it would take width off every line for nothing
            notify.flag(_sprint_note(new[-1], startlist, kind))

    while new and not new[-1]:
        new.pop()
    st.session_state[slot] = p["sprints"] = "-".join(new)
    # an empty line before a full one is not a sprint that scored nothing: the
    # notation cannot say "no sprint here", so the ones after it shift up
    holes = [str(i + 1) for i, c in enumerate(new) if not c]
    if holes:
        st.caption(msg("sprint_hole", list=", ".join(holes)))

    with st.expander(ui("sprint_string_box")):
        st.text_input(label("sprint"), st.session_state[slot],
                      key=f"spr_txt_{rid}_{ver}", label_visibility="collapsed",
                      help=help_text("sprint_string"))


def _adopt_string(rid: str, slot: str) -> int:
    """Take up whatever was typed in «Stringa», and return the fields' version.

    The box is drawn under the fields but has to be read before them, or a
    string pasted into it would show up a run late. It can be: the session
    already holds what was typed, so it is read here and the fields are
    re-keyed to pick it up. Re-keyed rather than st.rerun()-ed, because a
    rerun fired from the sidebar drops the widgets further down the page that
    have not been drawn yet - the «Documento» radio among them.
    """
    ver = st.session_state.get(f"sprv_{rid}", 0)
    typed = st.session_state.get(f"spr_txt_{rid}_{ver}")
    if typed is not None and str(typed).strip() != st.session_state[slot]:
        st.session_state[slot] = str(typed).strip()
        ver += 1
        st.session_state[f"sprv_{rid}"] = ver
    return ver


#: The numbered fields of the sprints and of the keirin batterie: a list, not
#: a form. Deliberately a constant of its own - it and the speaker banner below
#: once shared a name, the second assignment won at import, and the fields lost
#: their styling everywhere (`.cmsr-n` had no rule at all).
_FIELD_CSS = """
<style>
/* the sprint fields are a list, not a form: tight enough that a corsa a punti
   of fifteen sprints stays on one screen of sidebar */
[class*="st-key-sprints_"] [data-testid="stVerticalBlock"] { gap: .25rem; }
[class*="st-key-sprints_"] [data-testid="stElementContainer"] { margin: 0; }
.cmsr-n {
    text-align: right;
    opacity: .65;
    font-size: .8rem;
    white-space: nowrap;
}
.cmsr-n.fin { opacity: 1; font-weight: 600; }
</style>"""


def _timed_order(state) -> list[str]:
    """The entrants in the order they start, once the grid has been composed.

    The times arrive one start at a time, in the order the grid says; reading
    down a sidebar still in entry order while the track runs in start order is
    how a time lands on the wrong squadra. The grid is composed above in the
    page body and read back from the payload here, so the fields follow it in
    the same run - saving it is not needed to line them up.

    Whatever the grid does not place - a squadra not yet inserted, a race whose
    batterie are still loose notation - keeps its entry order at the bottom:
    nothing disappears from the sidebar because the composition is unfinished.
    """
    order: list[str] = []
    seen: set[str] = set()
    for row in (state.payload or {}).get("heat_sides") or []:
        for key in row:
            if key and key not in seen and key in state.entrants:
                seen.add(key)
                order.append(key)
    return order + [k for k in state.entrants if k not in seen]


def _timed_inputs(state, el) -> None:
    """Times only: the heats are composed in the page body, where there is room."""
    p = state.payload
    rid = state.race_id
    st.subheader(ui("times"))
    times = dict(p.get("times") or {})
    # what the fields held when the page was last drawn, so the banner over the
    # sheet can say which start has just been timed. It is not the race: an
    # unsaved race is read back from disk on every run and every field would
    # look new, which is exactly the moment the banner has to be right.
    seen = st.session_state.setdefault(f"seen_{rid}", dict(times))
    for key in _timed_order(state):
        name = R.entrant_label(key, el)
        current = format_time(times.get(key)) if times.get(key) else ""
        txt = st.text_input(name, current, key=f"t_{rid}_{key}",
                            placeholder="m:ss,mmm", help=help_text("time_format"))
        if txt.strip():
            ms, err = parse_time_safe(txt)
            if err:
                notify.text(msg("status_field_error", field=name, error=err),
                            level="error")
            else:
                # which start the banner over the sheet is about: the one just
                # taken, which is the field that changed on this run
                if ms != seen.get(key):
                    st.session_state[f"lastt_{rid}"] = key
                times[key] = seen[key] = ms
        else:
            times.pop(key, None)
            seen.pop(key, None)
    p["times"] = times
    # what is still missing, counted once under the fields: a qualification is
    # read off this list and a squadra without a time is not classified. Said
    # as a count, not by name - while the round is being ridden most of them
    # are legitimately empty.
    left = [k for k in state.entrants if not times.get(k)]
    if left and len(left) < len(state.entrants):
        st.caption(msg("times_missing", n=len(left)))
    _unridden_finals(state, el)


#: How a final that is not ridden is closed, and where each choice is stored.
FINAL_RIDDEN, FINAL_TIED, FINAL_QUAL = "ridden", "tied", "qual"


def _unridden_finals(state, el) -> None:
    """How each final is decided: ridden, a pari merito, or on the qualifying.

    It happens on the day - a squadra left without four riders, a final the
    jury decides not to have ridden - and the classification is not a blank
    line. There are two ways of closing it and they are not the same result,
    so the jury picks one per final (`timed.finals_classification`):

    * **a pari merito** - neither place is assigned on its own: the two share
      the lower one, both 2° or both 4°, and the place above stays empty;
    * **on the qualifying times** - the two are placed by the only time they
      rode, so the final still has a first and a second.

    Under the times because that is when it is decided: the qualification has
    been ridden, the finals are seeded, and this is the alternative to timing
    them.
    """
    p = state.payload
    heats = p.get("final_heats") or []
    if not heats:
        return
    st.subheader(ui("unridden_finals"))
    modes = {FINAL_TIED: [], FINAL_QUAL: []}
    was = {**{b: FINAL_TIED for b in p.get("finals_tied") or []},
           **{b: FINAL_QUAL for b in p.get("finals_on_qual") or []}}
    for base, heat in zip(T.final_places(heats, p.get("qual_ranking") or []),
                          heats):
        options = [FINAL_RIDDEN, FINAL_TIED, FINAL_QUAL]
        names = {FINAL_RIDDEN: ui("final_ridden"),
                 FINAL_TIED: ui("final_tied", place=ordinal(base + 1)),
                 FINAL_QUAL: ui("final_on_qual")}
        mode = st.selectbox(ui("unridden_final", name=T.final_label(base)),
                            options, format_func=names.get,
                            index=options.index(was.get(base, FINAL_RIDDEN)),
                            key=f"fin_{state.race_id}_{base}",
                            help=help_text("unridden_final", place=ordinal(base + 1)))
        if mode != FINAL_RIDDEN:
            modes[mode].append(base)
            st.caption(msg("tied_final_who" if mode == FINAL_TIED
                           else "qual_final_who", place=ordinal(base + 1),
                           who=" · ".join(R.entrant_label(k, el)
                                          for k in heat)))
    p["finals_tied"] = modes[FINAL_TIED]
    p["finals_on_qual"] = modes[FINAL_QUAL]


# ── velocità: the scheme and the rounds it composes ─────────────────────────
#
# Nothing is typed as notation here and no time is asked for after the 200 m:
# a velocità is ridden man against man, so what the jury enters is who won -
# a radio per batteria in the first round and the recuperi, a radio per prova
# from the quarti on. Everything else (who meets whom next, the sheets, the
# classification) follows from that and from the scheme, see `core.race`.

def _scheme_picker(state, comp: Competition, store: Store) -> None:
    """How this velocità will be run, decided on its qualifying round.

    It belongs here and not in the programme because it is the jury's call on
    the day, taken on the entries actually presented: it sets how many the
    200 m qualify, which is printed on this very start order, and which rounds
    are ridden after it.
    """
    if not R.is_sprint(comp, state.event):
        return
    if state.round_key != R.sprint_qualifying(comp, state.cat, state.event):
        return
    keys = list(S.SCHEMES)
    current = (state.payload or {}).get(R.SCHEME) \
        or R.sprint_scheme(store, comp, state.cat, state.event).key
    picked = st.selectbox(
        ui("next_rounds"), keys,
        index=keys.index(current) if current in keys else 0,
        key=f"scheme_{state.race_id}",
        format_func=lambda k: S.SCHEMES[k].label,
        help=help_text("sprint_scheme"))
    sch = S.SCHEMES[picked]
    # the start order says how many qualify: changing the scheme changes that
    # line, unless the jury has written its own
    if picked != (state.payload or {}).get(R.SCHEME) and (
            not state.decision
            or state.decision in {s.note for s in S.SCHEMES.values()}):
        state.decision = sch.note
        st.session_state.pop(f"dec_{state.race_id}_{DOC_STARTLIST}", None)
    state.payload[R.SCHEME] = picked
    st.caption(ui("scheme_line", qualified=sch.qualify,
                  rounds=" → ".join(sch.rounds))
               + (ui("scheme_repechages") if sch.repechage else ""))
    # the other decision the qualifying round carries: whether the four beaten
    # in the quarti have a race left. It is asked here and not on the finals
    # because it has to be settled before the quarti compose anything
    has_58 = st.toggle(
        ui("ride_final_5_8"),
        value=R.sprint_has_58(store, comp, state.cat, state.event),
        key=f"f58_{state.race_id}", help=help_text("final_5_8_toggle"))
    state.payload[R.FINAL_58] = has_58
    if not has_58:
        st.caption(ui("no_final_5_8_line"))


def _composition_fields(state, el, seeded: list[list[str]], *,
                        payload_key: str, prefix: str) -> list[list[str]]:
    """A composed round, seeded by the table and then confirmed by the jury.

    The seeding knows the ranking and nothing else: three riders of the same
    region drawn into one recupero, or a quarto that has to be redrawn because
    of a decision taken between two rounds, is a composition the jury has to be
    able to correct before the race is called. What is typed is kept on the race
    that composes it (`payload_key`) and is what everything downstream reads -
    the ordine di partenza, the arrivals asked for below, the classification.

    The fields follow the seeding again whenever the round upstairs changes who
    is in the next one at all: a result corrected upstairs re-seeds them, and
    the jury's swap between two riders still in it stays.
    """
    rid = state.race_id
    pool = [k for h in seeded for k in h]
    # the seeding as it stands now: when the field itself changed, the fields
    # on screen are dropped so the fresh composition shows through instead of
    # being typed over by what was in them
    stamp = R.heats_text(seeded)
    if st.session_state.get(f"{prefix}sig_{rid}") != stamp:
        st.session_state[f"{prefix}sig_{rid}"] = stamp
        for k in [k for k in st.session_state
                  if k.startswith(f"{prefix}_{rid}_")]:
            del st.session_state[k]

    rows: list[list[str]] = []
    seen: set[str] = set()
    for h, heat in enumerate(seeded):
        txt = st.text_input(ui("heat_n", n=h + 1), ", ".join(heat),
                            key=f"{prefix}_{rid}_{h}",
                            placeholder=ui("heat_bibs"),
                            help=help_text("heat_bibs"))
        line = bib_line(txt, expected=pool, seen=seen)
        notify.flag(line.flag)
        rows.append(line.bibs)
    left = [k for k in pool if k not in seen]
    if left:
        st.caption(ui("not_in_heat_yet", n=len(left), who=" · ".join(
            _entrant_name(k, el, state.cat) for k in left)))
    heats = [h for h in rows if h]
    state.payload[payload_key] = R.heats_text(heats)
    return heats


def _repechage_composition(state, el, rep: list[list[str]]) -> list[list[str]]:
    """The batterie of the recuperi: the riders the turno 1 left behind."""
    return _composition_fields(state, el, rep, payload_key=R.REP_HEATS,
                               prefix="rc")


def _next_round_composition(state, el, seeded: list[list[str]]) -> None:
    """The batterie of the round this one sends out, before it is loaded.

    Read and corrected here, on the sheet that publishes it, and not on the
    round itself: pressing «Carica Quarti di finale» writes exactly what is in
    these fields, so what the jury fixes is what starts. Left alone they are
    the UCI seeding, which is the right answer nearly every time.
    """
    _composition_fields(state, el, seeded, payload_key=R.NEXT_HEATS,
                        prefix="nc")


def _next_round_box(state, el, scheme, doc_kind: str) -> None:
    """The quarti as the turno 1 composes them, open on the sheet that files it.

    Read after the boxes above have written this run's winners into the
    payload: the eight are the six who won a batteria and the two who won a
    recupero, exactly as «Carica Quarti di finale» will read them.
    """
    nxt = scheme.next_round(state.round_key)
    if nxt != S.QUARTI:
        return
    winners = [k for k in R.heat_winners(R.bracket_orders(state)) if k]
    rep_win = [k for k in R.heat_winners(
        R.bracket_orders(state, R.REP_RESULTS)) if k]
    seeded = S.quarter_heats(winners, rep_win)
    with _race_box(ui("compose_race", race=ui("quarters_full")),
                   doc_kind == DOC_RESULTS_REP):
        if seeded:
            _next_round_composition(state, el, seeded)
        else:
            st.caption(msg("quarters_from_winners"))


def _race_box(title: str, current: bool):
    """One race of a round, open when its sheet is the one on screen.

    A box and not a plain `if`: the controls of the *other* race have to be
    drawn all the same, or Streamlit drops their values on the run that hides
    them - switching document before pressing Salva would throw away the
    results just entered, and save an empty round over them. Closed, they are
    out of the way; open, they are the sheet being prepared.
    """
    return st.expander(title, expanded=current)


def _velocita_inputs(state, el, scheme, doc_kind: str = "",
                     has_58: bool = False) -> None:
    """Who won: the only thing a velocità asks for after the 200 m.

    One race at a time - the one the sheet on screen is about. A round that
    rides two of them (the turno 1 and its recuperi, the finali and their
    5°-8°) asked for both at once, in one column of controls; picking the
    document now opens the race it files, and the decisions of the two stay
    apart as well (see `_statuses`).
    """
    rk = state.round_key
    heats = R.bracket_heats(state)
    if rk == S.TURNO1:
        with _race_box(ui("winners_round_1"), doc_kind != DOC_RESULTS_REP):
            _order_picks(state, heats, el, "results", key_prefix="t1")
        # read after the box above has written this run's winners into the
        # payload: the recuperi are the six they beat, and asking before means
        # asking about the round as it was on disk
        rep = R.sprint_repechages(state)
        with _race_box(ui("repechages"), doc_kind == DOC_RESULTS_REP):
            if rep:
                # composed first and asked about after: the batterie the jury
                # confirms are the ones the arrivals below are entered for
                rep = _repechage_composition(state, el, rep)
                _order_picks(state, rep, el, R.REP_RESULTS, key_prefix="rep")
            else:
                st.caption(msg("repechages_from_losers"))
        # and the round this one sends out: the quarti are composed off the
        # winners above plus the two who came back, and go out on this very
        # sheet - so they are corrected here, before the button loads them
        _next_round_box(state, el, scheme, doc_kind)
        return

    if rk == S.FINALI:
        titles = [ui("final_n_place", name=n)
                  for n in R.final_labels()][-len(heats):]
        with _race_box(ui("finals_1_4"), doc_kind != DOC_RESULTS_58):
            _run_picks(state, heats, el, "results", R.RUNS, titles=titles)
        # a year that does not ride it has no box for it at all: an empty one
        # would read as a race still to be composed
        if not has_58:
            return
        f58 = R.bracket_heats(state, R.HEATS_58)
        with _race_box(ui("final_5_8"), doc_kind == DOC_RESULTS_58):
            if f58:
                _order_picks(state, f58, el, R.RESULTS_58, key_prefix="f58")
            else:
                st.caption(msg("final_5_8_from_quarters"))
        return

    if rk in S.BEST_OF_THREE:
        st.subheader(ui("runs"))
        _run_picks(state, heats, el, "results", R.RUNS)
        return
    _bracket_inputs(state, el)


def _pick_label(key: str, el, cat: str) -> str:
    return _entrant_name(key, el, cat) if key else "—"


def _pick_one(title: str, options: list[str], wid: str, saved: str, el,
              cat: str, *, show_label: bool = True) -> str:
    """Who won: the riders of a batteria as buttons, one of them pressed.

    A segmented control and not a radio, because there is nothing to read down
    a list - there are two riders, sometimes three, and the answer is one of
    them. Pressing the one already pressed clears it, which is what the empty
    option of the radio used to be there for.

    Nothing reruns from here: the sidebar draws the *Documento* radio further
    down and a rerun in the middle of it loses that widget's value (see the
    handoff). The saved order is seeded once, then the widget owns the value.
    """
    # a value the place above has just taken away is no longer on offer: it
    # reopens this place instead of standing as a contradiction - and passing
    # it to the widget as a default would raise
    if st.session_state.get(wid) not in options:
        st.session_state.pop(wid, None)
    if wid not in st.session_state and saved in options:
        st.session_state[wid] = saved
    return st.segmented_control(
        title, options, key=wid,
        format_func=lambda k: _pick_label(k, el, cat),
        label_visibility="visible" if show_label else "collapsed") or ""


def _order_picks(state, heats: list[list[str]], el, key: str, *,
                 key_prefix: str) -> None:
    """Finishing order of every batteria, one place at a time.

    A batteria of two asks one question - who won - and the same widget asks a
    batteria of three for its 1° and its 2°, the last man being whoever is
    left. Each place offers only the riders still unplaced, so the same rider
    cannot be first and second, and changing the winner reopens the place
    below it instead of silently keeping a contradiction.
    """
    rid = state.race_id
    saved = R.bracket_orders(state, key)
    orders: list[list[str]] = []
    for h, heat in enumerate(heats):
        cur = saved[h] if h < len(saved) else []
        st.caption(f"**{ui('heat_n', n=h + 1)}**" if len(heats) > 1
                   else f"**{ui('heat_one')}**")
        order: list[str] = []
        for place in range(max(0, len(heat) - 1)):
            left = [k for k in heat if k not in order]
            wid = f"{key_prefix}_{rid}_{h}_{place}"
            prev = cur[place] if place < len(cur) else ""
            picked = _pick_one(ui("place_n", n=ordinal(place + 1)), left, wid, prev,
                               el, state.cat, show_label=len(heat) > 2)
            if not picked:
                break
            order.append(picked)
        if order and len(order) == len(heat) - 1:
            order += [k for k in heat if k not in order]   # the last one left
        orders.append(order)
    state.payload[key] = R.heats_text(orders)


def _run_picks(state, heats: list[list[str]], el, key: str, runs_key: str,
               titles: list[str] = ()) -> None:
    """Two prove and, only when they are shared, the bella.

    The batteria is won by whoever takes two of them, so nothing is counted by
    hand: the *ev. bella* field appears when - and only when - the first two
    went one each, which is what «eventuale» means on the sheet.
    """
    rid = state.race_id
    runs = dict((state.payload or {}).get(runs_key) or {})
    orders: list[list[str]] = []
    for h, heat in enumerate(heats):
        title = titles[h] if h < len(titles) else ui("heat_n", n=h + 1)
        st.caption(f"**{title}** · " + " / ".join(
            _pick_label(k, el, state.cat) for k in heat))
        won = [str(x) for x in (runs.get(str(h)) or [])]
        picks: list[str] = []
        for i in range(3):
            # the bella is *eventuale*: it exists only once the two prove have
            # been ridden and gone one each
            if i == 2 and (len([p for p in picks if p]) < 2
                           or S.heat_winner(picks, heat)):
                break
            wid = f"run_{rid}_{h}_{i}"
            prev = won[i] if i < len(won) else ""
            picks.append(_pick_one(label(f"run_{i + 1}"), list(heat), wid,
                                   prev, el, state.cat))
        picks = [p for p in picks if p]
        runs[str(h)] = picks
        order = S.heat_result(picks, heat)
        orders.append(order)
        if order:
            st.caption(ui("wins", who=_pick_label(order[0], el, state.cat)))
    state.payload[runs_key] = runs
    state.payload[key] = R.heats_text(orders)


def _velocita_result(state, doc_kind: str):
    """The result one sheet of a velocità files, for the race it belongs to.

    The statuses are the round's own: this sheet files what happened in this
    round, and a rider who was not at the gate for it did not start it - DNS,
    which is what the jury typed. What she did to the *specialità* is another
    sheet's business: on the classifica that DNS drops away and she is ranked
    on her 200 m time, like anybody else who went out in that round
    (`race.sprint_statuses`).
    """
    rk = state.round_key
    scope = R.status_scope(doc_kind)
    if doc_kind == DOC_RESULTS_REP:
        heats = R.sprint_repechages(state)
        return R.heat_result(state, heats,
                             R.bracket_orders(state, R.REP_RESULTS),
                             scope=scope)
    if doc_kind == DOC_RESULTS_58:
        heats = R.bracket_heats(state, R.HEATS_58)
        # one race, so the column says what it is once - against the first line
        # of the block, the way every other batteria number is printed
        return R.heat_result(state, heats,
                             R.bracket_orders(state, R.RESULTS_58),
                             labels=[label("final_5_8_short")], scope=scope)
    heats = R.bracket_heats(state)
    # on a finals sheet the batteria number says nothing: what it rides for does
    labels = (R.final_labels()[-len(heats):] if rk == S.FINALI else [])
    return R.heat_result(state, heats, R.bracket_orders(state),
                         runs=(state.payload or {}).get(R.RUNS),
                         n_runs=3 if rk in S.BEST_OF_THREE else 0,
                         labels=labels, scope=scope)


def _velocita_subtitle(state, doc_kind: str) -> str:
    """What the sheet is called, when the round rides more than one race."""
    if doc_kind == DOC_RESULTS_REP:
        return ui("round_repechage_results", round=state.round_key)
    if doc_kind == DOC_RESULTS_58:
        return ui("final_5_8_results")
    if state.round_key == S.FINALI and doc_kind == DOC_RESULTS:
        # the round rides two finals and its 5°-8° is a sheet of its own:
        # "Finali - Risultati" would name all three
        return ui("finals_1_2_3_4_results", a=label("final_1_2"),
                  b=label("final_3_4"))
    return ui("round_results", round=state.round_key)


def _doc_label(state, doc_kind: str, sprint: bool, keirin: bool = False,
               finals: tuple[str, str] = ("", "")) -> str:
    """The name of a sheet in the *Documento* picker.

    Where a round files two results the plain *Risultati* names neither of
    them: next to *Ris. recuperi* it is the turno itself, next to *Ris. 5°-8°*
    it is the two finals for the first four places. A keirin names its finals
    by the places they ride for, which are not fixed - 7°-12° with twelve
    riders, 7°-10° with ten.
    """
    if sprint and doc_kind == DOC_RESULTS:
        if state.round_key == S.FINALI:
            return label("risultati_1-4")
        if state.round_key == S.TURNO1:
            return ui("results_short", what=S.TURNO1)
    if keirin:
        if doc_kind == DOC_RESULTS:
            if R.is_finals(state.round_key) and finals[0]:
                return ui("results_short", what=finals[0])
            return ui("results_short", what=state.round_key)
        if doc_kind == DOC_RESULTS_B and finals[1]:
            return ui("results_short", what=finals[1])
    return label(doc_kind, doc_kind.capitalize())


def _velocita_cut(state, comp: Competition, scheme, doc_kind: str) -> int:
    """Where the line goes on the 200 m results: under the last qualified.

    The same rule the jury draws by hand across the workbook, and the same one
    the inseguimento prints under its fourth squadra.
    """
    if scheme is None or doc_kind != DOC_RESULTS:
        return 0
    if state.round_key != R.sprint_qualifying(comp, state.cat, state.event):
        return 0
    return scheme.qualify


def _doc_slug(state, doc_kind: str) -> str:
    """File name of a sheet the three standard kinds do not cover.

    The recuperi and the 5°-8° final are filed under the round they are ridden
    in - two results sheets on one round would otherwise overwrite each other
    in the comunicati folder. So are the sheets of an omnium prova: a classifica
    parziale filed as a *classifica* would overwrite the one of the specialità.
    """
    if doc_kind in (DOC_RESULTS_REP, DOC_RESULTS_58, DOC_RESULTS_B,
                    DOC_PARTIAL, DOC_RACE):
        return (f"{race_slug(state.cat, state.event, state.round_key)}"
                f"_{doc_kind}")
    return ""


def _champion_label(comp: Competition, cat: str) -> str:
    """CAMPIONE or CAMPIONESSA D'ITALIA, by the category's own sex."""
    return label("champion_f" if comp.female(cat) else "champion_m")


# ── keirin: the batterie the jury composes, the tournament the table decides ─
#
# A keirin has no qualifying race to be seeded from: its first round is the
# first race of the event, so the jury composes those batterie itself - a line
# per batteria, dorsali typed in. Everything the regulation decides comes from
# the table instead (UCI 3.2.135, read by the number of riders entered): how
# many batterie that round has, how many of each go through, and the
# composition of every round after it - which the jury can still edit before it
# prints, because the table is a starting point and the jury is the jury.

class KRace(NamedTuple):
    """One race of a keirin round: the round itself, or the second one it rides.

    The recuperi are ridden inside the round whose batterie they take the
    riders from, and the finals round rides two finals: each of them is a race
    of its own - its own composition, its own arrivals, its own sheet and its
    own decisions - kept in the payload of the round that publishes it.
    """

    title: str        # what the block is called on screen
    heats: str        # payload key of its composition
    results: str      # payload key of its finishing orders
    doc: str          # the document that files it
    n_heats: int      # batterie, from the UCI table
    heat_label: str = ""   # on a final, what it rides for ("1°-6°")


def _keirin_races(state, comp: Competition, el) -> list[KRace]:
    """The races this round rides, in the order they are ridden."""
    if R.is_finals(state.round_key):
        top, low = R.keirin_final_labels(state)
        out = [KRace(ui("final_named", name=top), "heats", "results",
                     DOC_RESULTS, 1, top)]
        if low:
            out.append(KRace(ui("final_named", name=low), R.HEATS_B,
                             R.RESULTS_B, DOC_RESULTS_B, 1, low))
        return out
    out = [KRace(state.round_key, "heats", "results", DOC_RESULTS,
                 R.keirin_heats(comp, el, state))]
    rep = R.keirin_heats(comp, el, state, repechages=True)
    if rep:
        out.append(KRace(ui("round_repechages", round=state.round_key),
                         R.REP_HEATS, R.REP_RESULTS, DOC_RESULTS_REP, rep))
    return out


def _keirin_composition(state, el, comp: Competition, store: Store) -> None:
    """Compose the batterie of every race of this round: one line per batteria.

    In the page body and not in the sidebar, for the same reason as the grid of
    the inseguimento: it is read across, against the entry list, and what is
    still missing from it has to be visible while it is being filled.
    """
    st.caption(_keirin_shape(state, comp, el))
    _keirin_final_b_toggle(state, comp, store)
    if _keirin_not_ridden(state, comp, el):
        return
    # one open box at a time: the *first* race still to compose. A round with
    # recuperi opened both, and the batterie of the recuperi - which cannot be
    # composed before the round has been ridden - pushed the ones being filled
    # in off the screen.
    todo = True
    for race in _keirin_races(state, comp, el):
        heats = R.bracket_heats(state, race.heats)
        first_todo = todo and not heats
        todo = todo and bool(heats)
        with st.expander(ui("compose_race", race=race.title),
                         expanded=first_todo):
            _keirin_heat_fields(state, el, race, heats,
                                _keirin_pool(state, el, comp, race))


def _keirin_final_b_toggle(state, comp: Competition, store: Store) -> None:
    """The one thing about a keirin the UCI table does not decide: how it ends.

    Two finals or one. It is asked on the round the jury composes by hand -
    the first one - and nowhere else, because it has to be settled before the
    last round composes anything: that composition either splits the riders
    into the final for the title and the one under it, or sends the qualifiers
    to the only final there is. Saved the moment it is switched, and not left
    to *Salva*: the round it is asked on is not the round it changes, and a
    jury that ticks it here and walks to the semifinali would otherwise compose
    the finals with the old answer.
    """
    if state.round_key != R.keirin_first_round(comp, state.cat, state.event):
        return
    was = R.keirin_has_final_b(store, comp, state.cat, state.event)
    has_b = st.toggle(ui("ride_final_b"), value=was,
                      key=f"kfb_{state.race_id}",
                      help=help_text("final_b_toggle"))
    if not has_b:
        st.caption(ui("no_final_b_line"))
    if has_b != was or state.payload.get(R.FINAL_B) is None:
        state.payload[R.FINAL_B] = has_b
        store.save_race(state, action="keirin_final_b")


def _keirin_pool(state, el, comp: Competition, race: KRace) -> list[str]:
    """Who this race of the round can start, which is not the whole categoria.

    A recupero rides the riders its batterie left behind; a final rides the ones
    the round before sent to *that* final and not to the other. Getting this
    wrong is not cosmetic: it is the list of who is still to be placed, and
    against the entry list it would say six riders are missing from a final
    that is already full.
    """
    if R.is_finals(state.round_key):
        taken = {k for other in _keirin_races(state, comp, el)
                 if other.heats != race.heats
                 for h in R.bracket_heats(state, other.heats) for k in h}
        return [k for k in state.entrants if k not in taken]
    if race.heats == R.REP_HEATS:
        # before the round has a result there is nobody to send there yet: the
        # entry list is the honest answer, not an empty grid
        return R.keirin_repechage_pool(comp, el, state) or list(state.entrants)
    return list(state.entrants)


def _keirin_not_ridden(state, comp: Competition, el) -> bool:
    """Say when this round is not part of the tournament, or not loaded yet.

    The programme lists every round a keirin can have; the table says which of
    them are actually ridden - a categoria of twelve goes from the first round
    straight to the finals, and the Semifinali page would otherwise be an empty
    grid that looks like work still to do. A finals round with nothing in it is
    the other case: it is loaded from the round before, and the moment to
    notice is now and not when the sheet prints.
    """
    sch = R.keirin_scheme(comp, el, state.cat, state.event)
    if R.is_finals(state.round_key):
        if R.bracket_heats(state):
            return False
        notify.warn("finals_not_loaded_keirin", round=sch.last.key)
        return False
    if sch.stage(state.round_key) is None:
        notify.info("keirin_round_not_ridden",
                    n=len(R.keirin_entrants(el, comp, state.cat, state.event)),
                    last=sch.stages[-1].key)
        return True
    return False


def _keirin_shape(state, comp: Competition, el) -> str:
    """One line saying how this keirin runs, from the number entered."""
    sch = R.keirin_scheme(comp, el, state.cat, state.event)
    n = len(R.keirin_entrants(el, comp, state.cat, state.event))
    bits = [ui("keirin_shape", n=n, lo=sch.lo, hi=sch.hi)]
    for stage in sch.stages:
        bits.append(ui("keirin_stage", round=stage.key, heats=stage.heats)
                    + (ui("keirin_stage_rep", n=stage.rep_heats)
                       if stage.repechages else ""))
    return "  ·  ".join(bits)


def _keirin_heat_fields(state, el, race: KRace, heats: list[list[str]],
                        pool: list[str]) -> None:
    """The batterie of one race, a text field each - dorsali separated by commas.

    Saved in dorsale order: which riders are in a batteria is the composition,
    the order they are written in is the sheet, and the sheet reads by number
    (`formats.keirin.in_bib_order`). What is typed stays as typed until it is
    saved; what comes back is in order.

    `pool` is who this race can start (`_keirin_pool`): what is still missing
    from the grid is measured against it, and so is a dorsale that has no
    business being in it.
    """
    rid = state.race_id
    st.html(_FIELD_CSS)
    n = max(race.n_heats, len(heats))
    rows: list[list[str]] = []
    seen: set[str] = set()
    with st.container(key=f"kheats_{rid}_{race.heats}"):
        for h in range(n):
            c1, c2 = st.columns([1, 6], vertical_alignment="center")
            name = ui("sprint_mark", n=h + 1) if n > 1 else ui("heat_one")
            c1.markdown(f"<div class='cmsr-n'>{name}</div>",
                        unsafe_allow_html=True)
            cur = ", ".join(heats[h]) if h < len(heats) else ""
            txt = c2.text_input(ui("heat_n", n=h + 1), cur,
                                key=f"kh_{rid}_{race.heats}_{h}",
                                label_visibility="collapsed",
                                placeholder=ui("heat_bibs"),
                                help=help_text("heat_bibs"))
            line = bib_line(txt, expected=pool, seen=seen)
            notify.flag(line.flag)
            rows.append(line.bibs)
    state.payload[race.heats] = R.heats_text(K.in_bib_order(rows))

    left = [k for k in pool if k not in seen]
    if left:
        st.caption(ui("not_in_heat_yet", n=len(left), who=" · ".join(
            _entrant_name(k, el, state.cat) for k in left)))
    else:
        st.caption(ui("all_in_heat"))
    if st.button(ui("save_heats"), key=f"ksave_{rid}_{race.heats}"):
        st.session_state[f"gridsave_{rid}"] = True


def _keirin_inputs(state, el, comp: Competition, doc_kind: str) -> None:
    """The arrivals, one field per batteria - which is how they are called in.

    Both races of the round are drawn, the one whose sheet is on screen open:
    controls that are not drawn lose their value, and switching document before
    pressing Salva used to file an empty round over a full one (see the
    velocità, `_race_box`).
    """
    for race in _keirin_races(state, comp, el):
        with _race_box(ui("arrivals_of", race=race.title),
                       doc_kind == race.doc):
            _keirin_order_fields(state, el, race)


def _keirin_order_fields(state, el, race: KRace) -> None:
    """`Batt. N` and, beside it, the finishing order as dorsali."""
    rid = state.race_id
    heats = R.bracket_heats(state, race.heats)
    if not heats:
        st.caption(ui("heats_not_composed"))
        return
    saved = R.bracket_orders(state, race.results)
    # the decisions of *this* race: the sidebar draws them below, so what was
    # typed a run ago is what is read here - enough to stop counting a rider
    # who is not going to be in the arrival as missing from it
    out = R.statuses_of(state, R.status_scope(race.doc))
    st.html(_FIELD_CSS)
    orders: list[list[str]] = []
    with st.container(key=f"kres_{rid}_{race.results}"):
        for h, heat in enumerate(heats):
            c1, c2 = st.columns([1, 4], vertical_alignment="center")
            short = ui("heat_short", n=h + 1)
            name = (race.heat_label or short) if len(heats) == 1 else short
            c1.markdown(f"<div class='cmsr-n'>{name}</div>",
                        unsafe_allow_html=True)
            cur = ", ".join(saved[h]) if h < len(saved) else ""
            txt = c2.text_input(f"{ui('heat_one')} {h + 1}", cur,
                                key=f"kr_{rid}_{race.results}_{h}",
                                label_visibility="collapsed",
                                placeholder=ui("arrival"),
                                help=help_text("heat_order"))
            # whoever the jury has already taken out of this batteria is not
            # counted as still missing from it: a DNS is not a line to write
            expected = [k for k in heat
                        if out.get(k, Status.OK) in (Status.OK, Status.REL)]
            line = bib_line(txt, expected=heat, need=len(expected))
            notify.flag(line.flag)
            orders.append(line.bibs)
    state.payload[race.results] = R.heats_text(orders)


def _keirin_result(state, el, comp: Competition, doc_kind: str):
    """The result one sheet of a keirin files, for the race it belongs to."""
    race = next((r for r in _keirin_races(state, comp, el)
                 if r.doc == doc_kind), None)
    if race is None:
        return None
    return R.heat_result(state, R.bracket_heats(state, race.heats),
                         R.bracket_orders(state, race.results),
                         labels=[race.heat_label] if race.heat_label else [],
                         scope=R.status_scope(doc_kind))


def _keirin_subtitle(state, el, comp: Competition, doc_kind: str) -> str:
    """What the sheet is called: the round rides more than one race."""
    races = {r.doc: r for r in _keirin_races(state, comp, el)}
    if doc_kind == DOC_STARTLIST_REP:
        return (ui("round_repechages", round=state.round_key)
                + f" - {label('start_order')}")
    race = races.get(doc_kind)
    what = state.round_key if race is None else race.title
    return f"{what} - {label('risultati')}"


def _keirin_notes(state, el, comp: Competition,
                  final_b: bool = True) -> dict[str, str]:
    """What each sheet of a keirin says by itself: how the tournament runs.

    Only what is still relevant on that sheet. The batterie of a round announce
    what they qualify for and where the rest go; the recuperi announce their own
    cut; the semifinali announce the two finals. The finals announce nothing -
    the sheet is titled with the places it rides for.
    """
    sch = R.keirin_scheme(comp, el, state.cat, state.event)
    stage = sch.stage(state.round_key)
    if stage is None:
        return {}
    f = comp.female(state.cat)
    nxt = sch.next_key(state.round_key)
    n = len(R.keirin_entrants(el, comp, state.cat, state.event))
    to = (_keirin_next_note(sch, stage, n, f, final_b) if nxt == K.FINALI
          else (msg(plural(stage.qualify, "goes_through_1", "goes_through_n"))
                + " " + _keirin_round_note(nxt)))
    first = _keirin_place_note(stage.qualify, f)
    notes = {}
    if stage.repechages:
        line = msg("note_keirin_stage", round=stage.key, heats=stage.heats,
                   first=first, to=to,
                   rest=msg("note_keirin_repechages",
                            rest=gendered(f, "others_m", "others_f")))
        notes[DOC_STARTLIST] = notes[DOC_RESULTS] = line
        rep = msg("note_keirin_rep_stage", heats=stage.rep_heats,
                  first=_keirin_place_note(stage.rep_qualify, f), to=to)
        notes[DOC_STARTLIST_REP] = notes[DOC_RESULTS_REP] = rep
    else:
        notes[DOC_STARTLIST] = notes[DOC_RESULTS] = msg(
            "note_keirin_stage", round=stage.key, heats=stage.heats,
            first=first, to=to, rest=".")
    return notes


def _keirin_place_note(qualify: int, female: bool) -> str:
    """'Il vincitore', 'Le prime 3 classificate' - who a batteria sends on."""
    if qualify <= 1:
        return gendered(female, "winner_m", "winner_f")
    return gendered(female, "first_n_m", "first_n_f", n=qualify)


def _keirin_round_note(round_key: str) -> str:
    """'alle semifinali' - the round riders go through to, as it is written."""
    key = (round_key or "").strip().lower()
    if key.startswith("semi"):
        return msg("to_semifinals")
    if key.startswith("quarti"):
        return msg("to_quarters")
    return msg("to_round", round=round_key) if round_key else msg("to_next")


def _keirin_next_note(sch, stage, n_riders: int, female: bool,
                      final_b: bool = True) -> str:
    """What the last round before the finals sends riders to.

    The two finals are named by the places they ride for, and those come from
    the table and not from the track: they are known - and printed - before the
    round is ridden. Ten riders in two batterie make a final 1°-6° and a final
    7°-10°, which is the smallest keirin the regulation allows.
    """
    top, low = K.final_labels(sch.final_size,
                              max(_keirin_into(sch, stage, n_riders)
                                  - sch.final_size, 0) if final_b else 0)
    goes = msg(plural(stage.qualify, "goes_through_1", "goes_through_n"))
    if not low:
        return f"{goes} " + msg("to_final_one", top=top)
    return f"{goes} " + msg("to_final_two", top=top, low=low,
                            rest=gendered(female, "others_m", "others_f"))


def _keirin_into(sch, stage, n_riders: int) -> int:
    """How many riders line up for a round: the entries, or what sent them here."""
    keys = [s.key for s in sch.stages]
    i = keys.index(stage.key)
    return sch.stages[i - 1].through if i else n_riders


def _keirin_advance(comp: Competition, state, doc_kind: str, el, store: Store):
    """The button that composes what this sheet sends the riders to.

    On the sheet that publishes it and nowhere else - the risultati of a round
    compose its recuperi, the risultati of the recuperi the round after, and the
    risultati of the last round both finals at once.
    """
    what = R.keirin_loads(comp, el, state, doc_kind)
    if not what:
        return None
    names = {K.REPECHAGES: ui("load_repechages"), K.SEMI: ui("load_semifinals"),
             K.QUARTI: ui("load_quarters"), K.FINALI: ui("load_finals")}

    def run():
        loaded, n = R.load_keirin_round(store, comp, el, state, doc_kind)
        if not loaded:
            notify.warn("missing_arrival")
            return
        notify.ok("round_composed", round=loaded, n=n)
        if loaded == K.REPECHAGES:
            # the recuperi are composed onto this same race, whose fields are
            # already on screen holding what was there before: they have to be
            # let go of, or the composition just written would be typed over
            _clear_keirin_widgets(state.race_id, R.REP_HEATS)
            st.rerun()

    return (names.get(what, ui("load_generic", round=what)),
            help_text("compose_next_uci", round=what), run)


def _keirin_blocks(state, result, el, comp: Competition, font: int,
                   club: bool, show_bib: bool, extra: list):
    """The classifica of a keirin, split into the finals that decided it.

    Unlike a velocità - one ranking from the champion down - a keirin is filed
    the way it is ridden: the final for the title first, with the champion under
    the first line, and the final under it as a table of its own. Whoever the
    tournament left before them keeps the places it gave her, in a last block:
    a classification that stopped at the twelfth would leave two thirds of the
    riders off the sheet the federation files.

    Split by *who rode which final*, not by counting off the first six: a
    squalificata is sorted to the bottom of her block and must stay in it - the
    sheet of her final is what files the decision taken in it.

    One final and there is nothing to split: the classifica generale *is* the
    result of the finale 1°-6°, and it is only the six who rode it. Nobody
    else was placed by a race - the second final was not ridden - so the sheet
    files the six places the tournament actually decided and stops there.
    """
    top = {k for h in R.bracket_heats(state) for k in h}
    low = {k for h in R.bracket_heats(state, R.HEATS_B) for k in h}
    if not top:
        return result, extra, ""
    if not low:
        return (Result(placings=[p for p in result.placings if p.key in top],
                       columns=result.columns), extra, "")
    names = R.keirin_final_labels(state)
    groups = [[p for p in result.placings if p.key in top],
              [p for p in result.placings if p.key in low],
              [p for p in result.placings
               if p.key not in top and p.key not in low]]
    titles = [ui("final_named", name=names[0]).upper(),
              ui("final_named", name=names[1]).upper(),
              label("general_classification")]
    tables = []
    for placings, title in list(zip(groups, titles))[1:]:
        if not placings:
            continue
        block = D.race_classification(
            state, Result(placings=placings, columns=result.columns), el, comp,
            font_size=font, doc_kind=DOC_CLASSIFICATION, show_club=club,
            show_time=False, show_bib=show_bib)
        table = block.tables[0]
        table.title = title
        tables.append(table)
    return (Result(placings=groups[0], columns=result.columns),
            list(extra) + tables, titles[0])


def _clear_keirin_widgets(rid: str, key: str) -> None:
    """Drop the composition fields of one race, so a fresh load shows through."""
    for k in [k for k in st.session_state if k.startswith(f"kh_{rid}_{key}_")]:
        del st.session_state[k]


# ── heat composition ────────────────────────────────────────────────────────

def _entrant_bibs(key: str, el, cat: str = "") -> list[int]:
    """The numbers an entrant fields. `cat` resolves a bare dorsale: the same
    number is worn in every category (see `race.entrant_riders`)."""
    return [r.bib for r in R.entrant_riders(key, el, cat) if r.bib]


def _reserve_bibs(key: str, el) -> list[int]:
    t = el.teams.get(key) or el.pairs.get(key)
    if not t:
        return []
    return [el.riders[k].bib for k in t.reserves
            if k in el.riders and el.riders[k].bib]


def _entrant_name(key: str, el, cat: str = "") -> str:
    """'EMILIA ROMAGNA A', or '84 BORDIGNON' for an individual entrant."""
    if key in el.teams or key in el.pairs:
        return R.entrant_label(key, el)
    riders = R.entrant_riders(key, el, cat)
    return f"{key} {riders[0].last_name}" if riders else str(key)


def _bibs_text(bibs) -> str:
    return ", ".join(str(b) for b in bibs)


def _side_bibs(key: str, el, overrides: dict, cat: str = "") -> str:
    """The numbers of one side, as the check-in has them.

    The jury may swap a number in - a reserve taking a starter's place is the
    normal case - and that override survives only while every number in it is
    still one of that team's riders. Once the check-in re-composes the squadra
    the entry list wins: a side left over from an older composition would show
    numbers that no longer ride together.
    """
    bibs = _entrant_bibs(key, el, cat)
    try:
        typed = parse_bibs(overrides.get(key) or "")
    except ParseError:
        typed = []
    if typed == bibs:  # nothing changed: no point keeping a copy around
        overrides.pop(key, None)
    elif typed and len(typed) == len(bibs) and \
            set(typed) <= set(bibs) | set(_reserve_bibs(key, el)):
        return _bibs_text(typed)
    overrides.pop(key, None)
    return _bibs_text(bibs)


def _sides_from_text(state, el) -> bool:
    """Read a notation the builder did not write back into picked entrants.

    Finals and bracket rounds are seeded as text; so are the races composed
    before this builder existed. Each side is matched to the entrant with
    exactly those numbers - no guessing. A side that belongs to nobody leaves
    the whole notation as text, which the jury can still edit by hand.
    """
    p = state.payload
    if p.get("heat_sides") is not None:
        return True
    if p.get("final_heats"):  # seeded finals: the entrants are already known
        p["heat_sides"] = [(list(h) + ["", ""])[:2] for h in p["final_heats"]]
        return True
    text = p.get("heats", "")
    if not text:
        p["heat_sides"] = []
        return True
    try:
        heats = parse_heats(text)
    except ParseError:
        return False

    by_bibs = {frozenset(_entrant_bibs(k, el, state.cat)): k
               for k in state.entrants}
    sides = []
    for heat in heats:
        row = [by_bibs.get(frozenset(side), "") for side in heat[:2]]
        if not all(row):
            return False
        sides.append((row + ["", ""])[:2])
    p["heat_sides"] = sides
    return True


def _finals_not_loaded(state, comp: Competition, store: Store) -> None:
    """Warn on a finals round that the qualification has not been carried in.

    Composed by hand the finals still run - the grid below takes any two
    entrants - but nothing arrives with them: not the seeding (3/4 and 1/2), not
    the qualifying times, not who stays in the classification below the
    finalists. It is the qualification's *Carica Finali* that brings all of it,
    and the moment to notice is now, not when the sheet prints.
    """
    if not R.is_pursuit(comp, state.event, state.fmt or "") \
            or not R.is_finals(state.round_key):
        return
    if (state.payload or {}).get("final_heats"):
        return
    qual = R.qualifying_round(comp, state.cat, state.event)
    if not qual:
        return
    who = msg("teams_not_qualified" if R.is_team_format(state.fmt or "")
              else "riders_not_qualified")
    saved = store.load_race(R.race_key(state.cat, state.event, qual))
    if saved is None or not (saved.payload or {}).get("times"):
        notify.warn("qualifying_no_times", round=qual)
    else:
        notify.warn("finals_not_loaded", round=qual, who=who)


def _sprint_not_loaded(state, comp: Competition, store: Store, scheme) -> None:
    """Warn on a velocità fase the round before it has not composed.

    Every round of a velocità after the 200 m is seeded by the one before it,
    and until that button is pressed the race is not empty - it is the whole
    elenco iscritti with no batterie, which reads as a broken fase rather than
    a fase that has not been loaded. The moment to say so is when it is opened,
    with the sheet it is loaded from named: the quarti go out on the *risultati
    recuperi* of the turno 1, everything else on the plain *risultati*.
    """
    rk = state.round_key
    if state.fmt != R.BRACKET or rk not in scheme.rounds:
        return
    if R.bracket_heats(state):
        return
    i = scheme.rounds.index(rk)
    prev = (scheme.rounds[i - 1] if i
            else R.sprint_qualifying(comp, state.cat, state.event))
    if not prev:
        return
    if not i:
        # the first round is composed off the 200 m: without times there is
        # nothing to compose it from, and that is the thing to fix first
        saved = store.load_race(R.race_key(state.cat, state.event, prev))
        if saved is None or not (saved.payload or {}).get("times"):
            notify.warn("qualifying_no_times", round=prev)
    names = {S.TURNO1: ui("load_round_1"), S.QUARTI: ui("load_quarters"),
             S.SEMI: ui("load_semifinals"), S.FINALI: ui("load_finals")}
    notify.warn("sprint_round_not_loaded", round=rk, prev=prev,
                doc=label("risultati_recuperi" if prev == S.TURNO1
                          else "risultati"),
                button=names.get(rk, ui("load_generic", round=rk)))


def _heat_builder(state, el, comp: Competition) -> None:
    """Compose the heats by picking teams, then fix the numbers if needed.

    The jury thinks *Emilia Romagna A against Lombardia A*; the classification
    needs `84,88,92,80-60,62,64,65`. Here the entrants are picked from a list
    and the bibs of each side stay editable, because a reserve taking a
    starter's place is the normal case, not the exception.

    Where a side starts alone - the velocità a squadre, an inseguimento the
    jury decides to run one atleta at a time - there is nothing to pair up:
    the grid is the *ordine di partenza*, one per start, all of them in it,
    and the only thing to get right is the order and that nobody is in it
    twice. The finals are two against each other whatever the qualifying does,
    and go back to being batterie.
    """
    p, rid = state.payload, state.race_id
    finals = D.final_heat_labels(state)
    # one at a time: an ordine di partenza, not batterie. The programme says
    # what the event usually does and the jury may say otherwise here; a
    # finals round is ridden two against two even before it is seeded, so
    # there the question is not asked at all (`race.solo_starts`).
    solo = _starts_mode(state, comp)
    # the same grid composes the start order of a velocità a squadre and of a
    # 200 m lanciati: "le squadre" is nobody on the second
    team = R.is_team_format(state.fmt or "")
    everyone = ui("everyone_teams" if team else "everyone_riders")
    title = ui("build_start_order" if solo else "build_heats")
    with st.expander(title, expanded=not p.get("heats")):
        if not _sides_from_text(state, el):
            p["heats"] = st.text_area(title, p.get("heats", ""),
                                      key=f"heats_{rid}",
                                      help=help_text("heat_notation"))
            notify.flag(bib_line(p["heats"], expected=state.entrants).flag)
            st.caption(msg("heats_not_matched"))
            return

        sides: list[list[str]] = p["heat_sides"]
        overrides: dict = p.setdefault("heat_bibs", {})
        _starts_picker(state, comp, solo, team)
        lanes = (0,) if solo else (0, 1)
        per_row = len(lanes)
        # the finals are seeded, not composed: the four that ride them came out
        # of the qualification, and a button that overwrites them with the entry
        # list is a button that undoes «Carica Finali»
        seeded = R.is_finals(state.round_key)
        # a start order has as many lines as there are squadre: nothing to
        # choose, and a field to choose it in is a field to get it wrong in
        if solo:
            n, box = len(state.entrants), st.container()
            fill_help = help_text("fill_start_order", who=everyone)
        else:
            c1, c2 = st.columns([1, 2])
            # as many batterie as the field asks for: two a batteria, and the
            # odd one out rides alone. Only the opening value - once the jury
            # has composed something, that is what the grid reopens on.
            planned = max(1, -(-len(state.entrants) // per_row))
            n = int(c1.number_input(ui("heats"), 1, max(1, len(state.entrants)),
                                    value=max(1, len(sides)) if sides or seeded
                                    else planned, step=1, key=f"nh_{rid}"))
            box = c2
            fill_help = help_text("fill_pairs")
        if not seeded and box.button(ui("fill_in_entry_order"),
                                     key=f"fill_{rid}", help=fill_help):
            # the race is reloaded from disk on every run: the grid lives in
            # the widgets, so fill those and let the rerun read them back
            _clear_heat_widgets(rid)
            ents = list(state.entrants)
            if not solo:
                st.session_state[f"nh_{rid}"] = (len(ents) + 1) // 2
                # an odd field leaves somebody without an opponent, and that
                # start opens the round: the first rides the 1ª batteria alone
                # and everybody behind him goes two by two
                if len(ents) % 2:
                    ents.insert(1, "")
            for i in range(0, len(ents), per_row):
                for j in lanes:
                    st.session_state[f"hs_{rid}_{i // per_row}_{j}"] = (
                        ents[i + j] if i + j < len(ents) else "")
            st.rerun()

        while len(sides) < n:
            sides.append(["", ""])
        del sides[n:]

        options = [""] + list(state.entrants)
        seen: set[str] = set()
        for i, row in enumerate(sides):
            if solo:
                # "3ª partenza" and the squadra that rides it are one line:
                # the start order is read down the page, and a heading of its
                # own for every squadra made seven of them into a long scroll
                head, box = st.columns([1, 5], vertical_alignment="center")
                head.markdown(f"**{ui('start_n', n=i + 1)}**")
                cols = [box]
            else:
                # the batteria and the two who ride it on one line, like the
                # start order above: a heading of its own per batteria turned
                # fifteen of them into a page of scrolling
                head, box = st.columns([1, 5], vertical_alignment="center")
                head.markdown(
                    f"**{ui('final_named', name=finals[i])}**"
                    if i < len(finals) else f"**{ui('heat_n', n=i + 1)}**")
                cols = box.columns(per_row)
            for j in lanes:
                with cols[j]:
                    cur = row[j] if row[j] in options else ""
                    row[j] = st.selectbox(
                        ui("lane_n", n=j + 1), options, index=options.index(cur),
                        key=f"hs_{rid}_{i}_{j}", label_visibility="collapsed",
                        format_func=lambda k: (_entrant_name(k, el, state.cat)
                                               if k else "—"))
                    key = row[j]
                    if not key:
                        continue
                    if key in seen:
                        notify.warn(
                            ("entrant_twice_start_order_f" if team
                             else "entrant_twice_start_order_m") if solo
                            else "entrant_twice_heat")
                        continue
                    seen.add(key)
                    if len(_entrant_bibs(key, el, state.cat)) > 1:
                        # a team: the numbers vary with who actually starts
                        overrides[key] = st.text_input(
                            ui("bibs"),
                            _side_bibs(key, el, overrides, state.cat),
                            key=f"hb_{rid}_{key}",
                            help=help_text("reserve_bibs"))
                        # a swapped-in number has to be one this squadra can
                        # field: a reserve of another region on the sheet is a
                        # result filed under the wrong team
                        notify.flag(bib_line(
                            overrides[key],
                            expected=[str(b) for b in
                                      _entrant_bibs(key, el, state.cat)
                                      + _reserve_bibs(key, el)]).flag)
                    res = _reserve_bibs(key, el)
                    if res:
                        st.caption(ui("reserves_are", bibs=_bibs_text(res)))

        p["heats"] = _heats_text(sides, overrides, el, state.cat)
        st.caption(ui("notation_is", text=p["heats"] or ui("none_short")))
        # what is still on the bench: the jury composes by crossing this list
        # off, and reading it off the grid by eye is what goes wrong
        left = [k for k in state.entrants if k not in seen]
        if left:
            st.caption(ui("not_placed_yet", n=len(left), who=" · ".join(
                _entrant_name(k, el, state.cat) for k in left)))
        else:
            st.caption(ui("all_in_start_order", who=everyone.capitalize())
                       if solo else ui("all_in_heats"))

        # an odd field means somebody rides alone, and that start opens the
        # round: the batteria of one is the 1ª, so the pairing behind it holds
        # for everybody else. Composed the other way round it is the last
        # batteria that is short, which is the one the sheet reads worst.
        odd = [i for i, row in enumerate(sides)
               if len([k for k in row if k]) == 1]
        if not solo and not seeded and not left \
                and len(state.entrants) % per_row and odd != [0]:
            notify.warn("odd_field_first" if odd
                        else "odd_field_must_be_first")

        # Saved from where it is composed, like the madison's own composition
        # round: reaching the sidebar to file what was just typed here is a
        # step nobody remembers at the track. The click is only *asked* for
        # here - `render()` does the writing once the sidebar has put the
        # times and the statuses of this run into the race, or a save from up
        # the page would file it without them.
        if st.button(ui("save_start_order" if solo else "save_heats"),
                     key=f"savegrid_{rid}"):
            st.session_state[f"gridsave_{rid}"] = True


def _heats_text(sides, overrides: dict, el, cat: str = "") -> str:
    """The builder's own output, in the notation everything else reads."""
    out = []
    for row in sides:
        cells = [_side_bibs(k, el, overrides, cat).replace(" ", "")
                 for k in row if k]
        if any(cells):
            out.append("-".join(c for c in cells if c))
    return "/".join(out)


#: The picker's own widget, and the mode the grid was last laid out for.
def _starts_key(rid: str) -> str:
    return f"solo_{rid}"


def _starts_mode(state, comp: Competition) -> bool:
    """Whether this round is being composed one start at a time.

    What the jury picked in this session if they picked anything - the race is
    reloaded from disk on every run, and a choice not saved yet would flip back
    to the programme's default under their hands - else what the race says
    (`race.solo_starts`).
    """
    picked = st.session_state.get(_starts_key(state.race_id))
    if picked is not None and R.can_choose_starts(
            comp, state.event, state.fmt or "", state.round_key):
        return bool(picked)
    return R.solo_starts(comp, state)


def _starts_picker(state, comp: Competition, solo: bool, team: bool) -> None:
    """How this round is ridden: two at a time, or one at a time.

    A round against the clock does not have to be batterie. The inseguimento
    individuale is normally ridden two atleti at a time, one on each straight,
    but with a thin field - or on a track where the jury wants the times clean
    of a rival on the other side - it is ridden one start at a time, exactly
    like the velocità a squadre. That is a call taken at the track, on the
    entries actually presented, so it lives on the race and not in the
    programme (which keeps saying what the event usually does).

    The choice is not offered where it means nothing: a finals round and a
    bracket are ridden man against man whatever anybody picks.

    Switching re-flows what is already composed rather than throwing it away -
    the order stands, only how many share a line changes.
    """
    p, rid = state.payload, state.race_id
    if not R.can_choose_starts(comp, state.event, state.fmt or "",
                               state.round_key):
        return
    modes = (False, True)   # due alla volta | una alla volta
    labels = {False: ui("starts_two"),
              True: ui("starts_one_teams" if team else "starts_one_riders")}
    pick = st.radio(ui("starts_mode"), modes, index=modes.index(solo),
                    horizontal=True, key=_starts_key(rid),
                    format_func=labels.get, help=help_text("starts_mode"))
    # the choice rides on the race, and is written to disk with it
    p[R.SOLO_STARTS] = pick
    # re-flow only when the jury *moves* the radio. Compared against what the
    # grid was last laid out for and not against the race on disk: unsaved,
    # the race still reads the old way on the next run, and re-flowing on
    # every run would undo the edits made in between.
    laid = f"solomode_{rid}"
    if st.session_state.get(laid) is None:
        st.session_state[laid] = pick
    elif st.session_state[laid] != pick:
        st.session_state[laid] = pick
        _reflow_sides(p, rid, pick)


def _composed_keys(p: dict, rid: str) -> list[str]:
    """The grid as it stands right now, read down the page.

    The widgets first: the race is reloaded from disk on every run, so what
    was composed and not saved yet lives only in them - and re-flowing off the
    payload would silently throw that composition away. The race answers for
    the lines the widgets have not been drawn for.
    """
    rows = p.get("heat_sides") or []
    drawn = [k.rsplit("_", 2) for k in st.session_state
             if k.startswith(f"hs_{rid}_")]
    top = max((int(bits[-2]) for bits in drawn if bits[-2].isdigit()),
              default=-1)
    out = []
    for i in range(max(len(rows), top + 1)):
        for j in (0, 1):
            wid = f"hs_{rid}_{i}_{j}"
            key = (st.session_state[wid] if wid in st.session_state
                   else rows[i][j] if i < len(rows) and j < len(rows[i])
                   else "")
            if key:
                out.append(key)
    return out


def _reflow_sides(p: dict, rid: str, solo: bool) -> None:
    """Re-lay the composed grid for the other shape, keeping the order.

    Going to one at a time, a batteria of two becomes two starts; going back,
    the starts pair up two by two. Nobody is dropped and nobody is reordered:
    the jury composed that sequence, and only the number of lines changes.
    """
    keys = _composed_keys(p, rid)
    per_row = 1 if solo else 2
    # pairing up an odd field leaves somebody without an opponent, and that
    # start opens the round (`odd_field_must_be_first`): the first rides the
    # 1ª batteria alone and everybody behind him goes two by two
    if not solo and len(keys) % 2:
        keys.insert(1, "")
    p["heat_sides"] = [[(keys[i + j] if i + j < len(keys) else "")
                        for j in range(2)]
                       for i in range(0, len(keys), per_row)]
    _clear_heat_widgets(rid)
    for i, row in enumerate(p["heat_sides"]):
        for j in range(per_row):
            st.session_state[f"hs_{rid}_{i}_{j}"] = row[j]
    if not solo:
        st.session_state[f"nh_{rid}"] = max(1, len(p["heat_sides"]))


def _clear_heat_widgets(rid: str) -> None:
    """Drop the per-slot selectboxes so a refilled grid is not overruled."""
    for k in [k for k in st.session_state
              if k.startswith(f"hs_{rid}_") or k == f"nh_{rid}"]:
        del st.session_state[k]


def _bracket_inputs(state, el) -> None:
    """Velocità / keirin round: composition on top, finishing orders below."""
    p = state.payload
    rid = state.race_id
    st.subheader(ui("heats"))
    p["heats"] = st.text_area(ui("heat_composition"), p.get("heats", ""),
                              key=f"bh_{rid}", help=help_text("heat_notation"))
    # the free-text notation used to be the one input of the page nothing
    # looked at: a dorsale that is not entered, or one written into two
    # batterie, only surfaced as a warning under the classification
    notify.flag(bib_line(p["heats"], expected=state.entrants).flag)
    st.caption(msg("heats_from_previous"))
    p["results"] = st.text_area(ui("heat_order_by_heat"), p.get("results", ""),
                                key=f"br_{rid}",
                                help=help_text("heat_notation_same"))
    notify.flag(bib_line(p["results"],
                         expected=R.heats_from_text(p["heats"]) and
                         [k for h in R.heats_from_text(p["heats"]) for k in h]
                         or state.entrants).flag)


def _status_help(status: Status, *, teams: bool = False) -> str:
    """What one status field means, plus how it is filled in."""
    return help_text(f"status_{status.value.lower()}",
                     "teams_pick" if teams else "bibs_csv")


def _status_label(status: Status) -> str:
    """`DNS` - the code the decision is written on the sheet with."""
    return label(status.value)


def _statuses(state, el, kind: str = "", scope: str = "") -> None:
    """The decisions taken in the race the sheet on screen is about.

    `scope` is which of the round's races that is (`race.status_scope`): a
    rider relegated in the recuperi was not relegated in the turno 1, and the
    two sheets are filed separately - so are the fields that fill them.
    """
    st.subheader(ui("statuses"))
    saved = R.status_dict(state, scope)
    fields = _status_fields(kind)
    if kind == R.TIMED_TEAM:
        # a squadra is DNS as a squadra: nothing here is typed as a dorsale
        for status in fields:
            current = [k for k, v in saved.items()
                       if v == status.value and k in state.entrants]
            picked = st.multiselect(
                _status_label(status), state.entrants, default=current,
                key=f"team_{status.value.lower()}_{state.race_id}",
                help=_status_help(status, teams=True),
                format_func=lambda k: R.entrant_label(k, el))
            for k in current:
                saved.pop(k, None)
            for k in picked:
                R.set_status(state, k, status, scope)
        return

    # what is typed here is a number: a dorsale, or - in a madison - a coppia.
    # The status belongs to the coppia, so the two are translated both ways
    # and the field keeps showing the number the jury shouted.
    keys = R.status_keys(state, el, kind)
    shown = {key: bib for bib, key in keys.items()}
    # what a decision may be written about: the numbers this race is called
    # by. In a madison that is the coppia number, which is what `status_keys`
    # translates - so the flag is measured against the same set the field is.
    known = list(keys) or [str(b) for b in R.bunch_startlist(state, el, kind)]
    cols = st.columns(2)
    for i, status in enumerate(fields):
        # the scope is in the widget key: the same field for two sheets would
        # carry what was typed on one over to the other
        key = f"{status.value.lower()}_{state.race_id}_{scope}"
        name = _status_label(status)
        current = ", ".join(shown.get(k, k) for k, v in saved.items()
                            if v == status.value)
        txt = cols[i % 2].text_input(name, current, key=key,
                                     help=_status_help(status))
        for k in [k for k, v in saved.items() if v == status.value]:
            saved.pop(k, None)
        try:
            R.set_statuses_from_text(state, txt, status, keys=keys, scope=scope)
        except ParseError as exc:
            notify.text(msg("status_field_error", field=name, error=exc),
                        level="error", where=cols[i % 2])
            continue
        # a decision taken on a number nobody is riding under is a decision
        # that lands on nobody: the field says so where it is typed
        notify.flag(bib_line(txt, expected=known).flag, where=cols[i % 2])


# ── decisions, written where they are taken ─────────────────────────────────
#
# A decision belongs to the race the panel took it in, so it is written there,
# on the sheet being run - not afterwards, from memory, on a page of its own.
# What it goes into is the one log of the competition (`core.decisions`): the
# Decisioni page is that log read back, filtered and printed.
#
# The ammonizione is the one that comes back here. It travels with the rider
# through the specialità (a W on every sheet from the fase it was given in),
# and a second one in the same fase is a squalifica - written into the DSQ
# field of the race, where the jury can still take it out.


def _decision_panel(state, comp: Competition, store: Store, el,
                    scope: str = "") -> None:
    """File a decision from the race it was taken in.

    What the panel reads before it files the next one comes first: the recap of
    the whole specialità, fase by fase, then who is already carrying an
    ammonizione into this one. Only then the button - because a decision taken
    without knowing what was decided an hour ago in the turno 1 is the one that
    gets contested.
    """
    taken = DEC.load(store)
    with st.expander(ui("decision_panel")):
        DF.recap(comp, store, state.cat, state.event, decisions=taken)
        _warned_here(taken, state)
        DF.insert(comp, store, el, key=f"d_{state.race_id}", cat=state.cat,
                  event=state.event, round_key=state.round_key, locked=True,
                  on_filed=lambda d: _after_filing(state, store, scope))
        st.caption(help_text("decision_panel"))
        _decisions_here(comp, store, state, taken)


def _decisions_on(store: Store, state, doc_kind: str, kinds=()) -> list:
    """The decisions that print on the sheet being prepared.

    A decision is published with the *result* of the race it was taken in: an
    ordine di partenza goes out before the race is ridden, and a squalifica on
    it would be a squalifica taken before the start - which happens, but is
    filed on the sheet that closes the fase like every other.

    A decision goes out **once**, on the comunicato of the fase it was taken
    in, and the classifica does not repeat it: the classifica ranks the
    specialità, and a sheet that reprints every retrocessione of every turno
    under a final ranking reads as a fresh set of sanctions rather than as the
    order they produced. `kinds` is what this round files (`_doc_kinds`): only
    where the classifica is the round's *own* result sheet - a specialità
    ridden in one go, filed as a classification and nothing else - does it
    carry the decisions taken in it, because there is no other comunicato they
    could go out on.
    """
    if doc_kind in (DOC_STARTLIST, DOC_STARTLIST_REP):
        return []
    if doc_kind == DOC_CLASSIFICATION and any(
            k in DOC_RESULT_KINDS and k != DOC_CLASSIFICATION for k in kinds):
        return []
    return DEC.for_race(DEC.load(store), state.cat, state.event,
                        state.round_key)


def _after_filing(state, store: Store, scope: str) -> None:
    """What the rules ask for once a decision is on file.

    Two ammonizioni in the same fase are a squalifica: the numbers go into the
    DSQ field of the race, where the jury can still take them out. Written from
    inside the callback that filed the decision - a widget already drawn this
    run is one only a callback may write to.
    """
    twice = DEC.double_warned(DEC.load(store), state.cat, state.event,
                              state.round_key)
    if twice:
        _declare_dsq(state, twice, scope)
        notify.text(msg("warned_twice",
                        bibs=", ".join(str(b) for b in twice)), level="error")


def _declare_dsq(state, bibs: list[int], scope: str) -> None:
    """Add numbers to the DSQ field of the race, keeping what is already in it."""
    key = f"{Status.DSQ.value.lower()}_{state.race_id}_{scope}"
    current = [b.strip() for b in
               str(st.session_state.get(key, "")).split(",") if b.strip()]
    st.session_state[key] = ", ".join(
        current + [str(b) for b in bibs if str(b) not in current])


def _decisions_here(comp: Competition, store: Store, state, taken: list
                    ) -> None:
    """The decisions already filed in this race: corrected, or taken back.

    Only this race's own, and only where there are any: the register of the
    whole competition is the Decisioni page. A decision written on the wrong
    dorsale has to be fixable *here*, while the race it belongs to is on
    screen - walking away from the track to another page to correct a number
    is how the correction does not get made.

    The buttons under each are callbacks, like the one that files a decision: a
    rerun fired from the sidebar would drop the widgets of the page below it,
    the Documento radio among them.
    """
    mine = DEC.for_race(taken, state.cat, state.event, state.round_key)
    if not mine:
        return
    st.caption(ui("decisions_here", n=len(mine)))
    for d in mine:
        with st.container(border=True):
            st.caption(DF.head(comp, d))
            DF.edit(store, d, f"{state.race_id}_{d.n}")


def _warned_here(taken: list, state) -> None:
    """Who carries an ammonizione in this specialità, under the panel."""
    warned = DEC.warned_bibs(taken, state.cat, state.event)
    st.caption(msg("warned_carried",
                   bibs=", ".join(str(b) for b in sorted(warned)))
               if warned else msg("warned_none"))


def _heat_size_warnings(heats, comp: Competition, state) -> list[str]:
    """Sides that do not field the team size the event asks for.

    The riserva is written as an X on the entry list, so a squadra often
    carries five names: four of them start. Said here, on the sheet the jury
    reads out at the track, while there is still time to strike one out.
    """
    size = comp.event(state.event).team_size or 0
    if not size or not heats:
        return []
    return [msg("heat_wrong_size", heat=h + 1, lane=s + 1, n=len(side),
                size=size, bibs=", ".join(str(b) for b in side))
            for h, heat in enumerate(heats)
            for s, side in enumerate(heat) if len(side) != size]


# ── omnium: the four prove and the sheets between them ──────────────────────
#
# The prove of an omnium are not four races filed one after the other: each one
# is read into the next. The standings after a prova are the ordine di partenza
# of the one that follows, so that is the sheet the register numbers - the
# *classifica parziale* - and the risultati of the prova itself go out
# unnumbered, as the jury's own working sheet.


def _is_prova(comp: Competition, state) -> bool:
    """Whether this round is one of the four prove of an omnium."""
    return (comp.event(state.event).fmt == "omnium"
            and state.round_key in O.ROUNDS)


def _omnium_docs(round_key: str, docs: list[str]) -> list[str]:
    """The sheets a prova files, on top of the two the programme declares.

    The tempo race files its result twice: the *gara*, one column per volata,
    which is what the jury scores it on, and the *risultati*, which publish the
    order and the omnium points it is worth. The first three prove each close on
    the classifica parziale that starts the next one.
    """
    out = list(docs)
    if round_key == O.TEMPO and DOC_RESULTS in out:
        out.insert(out.index(DOC_RESULTS), DOC_RACE)
    if round_key in O.PLACING_ROUNDS:
        out.append(DOC_PARTIAL)
    return out


def _omnium_subtitle(state, doc_kind: str) -> str:
    """What a sheet of a prova is called.

    A classifica parziale says both things it is: the standings after this
    prova, and the ordine di partenza of the next one - which is what it is
    printed for.
    """
    rk = state.round_key
    if doc_kind == DOC_PARTIAL:
        if rk == O.SCRATCH:
            return ui("partial_after_scratch", scratch=O.SCRATCH, next=O.TEMPO)
        nxt = O.ROUNDS[O.ROUNDS.index(rk) + 1]
        return ui("partial_standings", next=nxt)
    if doc_kind == DOC_RACE:
        return f"{rk} - {label('gara')}"
    if doc_kind == DOC_RESULTS and rk == O.TEMPO:
        return ui("results_of", round=O.TEMPO)
    return ""


def _omnium_points_cols(state, doc_kind: str) -> list[tuple[str, str]]:
    """The points columns at the end of a sheet of a prova.

    A classifica parziale carries one column per prova ridden and, once there
    is more than one, their total; the risultati of a prova carry what that one
    prova scored.
    """
    rk = state.round_key
    if doc_kind == DOC_PARTIAL:
        done = O.ROUNDS[:O.ROUNDS.index(rk) + 1]
        cols = [(O.points_key(n), f"{label('points_of')} {n}") for n in done]
        return cols if len(cols) == 1 else cols + [("total",
                                                    label("points_total"))]
    if doc_kind == DOC_RESULTS and rk in (O.TEMPO, O.ELIMINATION):
        return [("prova_points", f"{label('points_of')} {rk}")]
    return []


def _omnium_result(state, el, comp: Competition, store: Store, result,
                   doc_kind: str):
    """The result a sheet of a prova is printed from.

    The classifica parziale is the standings up to and including this prova;
    the risultati of the tempo race and of the eliminazione carry the omnium
    points of their own placings; the corsa a punti is scored on the running
    omnium total, from the points each rider brought into it.
    """
    if doc_kind == DOC_PARTIAL:
        return R.omnium_standings(store, comp, el, state.cat, state.event,
                                  upto=state.round_key)
    if doc_kind == DOC_RESULTS and state.round_key in (O.TEMPO, O.ELIMINATION):
        return R.omnium_prova_points(result, state.round_key)
    if doc_kind == DOC_RESULTS and state.round_key == O.POINTS_RACE:
        return R.omnium_points_race(
            result, R.omnium_carried(store, comp, el, state.cat, state.event))
    return result


# ── output ──────────────────────────────────────────────────────────────────

def _doc_kinds(comp: Competition, state, store: Store) -> list[str]:
    """The documents this round produces, as the programme declares them.

    A qualifying round has partenti and risultati: the classifica is the sheet
    of the event, not of the round, and offering it here is what let a
    provisional ranking go out as *the* classification. It is added back on the
    last round of an event the register plans one for.

    The 5°-8° of a velocità is the one sheet the programme does not have the
    last word on: the jury turns it on and off on the qualifying round, and
    what it decided there is what the finali offer (`race.sprint_has_58`).
    """
    docs = list(comp.round_of(state.cat, state.event, state.round_key).docs)
    if R.is_sprint(comp, state.event) and state.round_key == S.FINALI:
        on = R.sprint_has_58(store, comp, state.cat, state.event)
        if on and DOC_RESULTS_58 not in docs:
            # before the risultati of the two finals for the first four
            # places: the 5°-8° is ridden first, and files first
            at = docs.index(DOC_RESULTS) if DOC_RESULTS in docs else len(docs)
            docs.insert(at, DOC_RESULTS_58)
        elif not on:
            docs = [d for d in docs if d != DOC_RESULTS_58]
    if R.is_keirin(comp, state.event) and R.is_finals(state.round_key) \
            and not R.keirin_has_final_b(store, comp, state.cat, state.event):
        # one final: the sheet of the other one has nothing to file, and an
        # empty risultati filed under it is a comunicato that says a race was
        # ridden
        docs = [d for d in docs if d != DOC_RESULTS_B]
    if _is_prova(comp, state):
        docs = _omnium_docs(state.round_key, docs)
    rounds = [r.key for r in comp.rounds(state.cat, state.event)]
    planned = any(c.doc == DOC_CLASSIFICATION and c.cat == state.cat
                  and c.event == state.event for c in comp.communiques)
    if planned and rounds[-1:] == [state.round_key] \
            and DOC_CLASSIFICATION not in docs:
        docs.append(DOC_CLASSIFICATION)
    return docs or list(DOC_KINDS)


def _madison_notes(state, comp: Competition, store: Store) -> dict[str, str]:
    """What a batteria says by itself, sheet by sheet.

    The start order announces the cut the composition round decided; the
    results say who came through it. The count is over the coppie that
    started - a DNS is not one of the eliminated (3.2.157), so it does not
    take a place away from anybody.
    """
    if not R.heat_number(state.round_key) \
            or not R.is_composed(comp, state.cat, state.event):
        return {}
    out = state.payload.get(R.ELIMINATE)
    if out is None:
        out = R.pairing(store, comp, state.cat, state.event).eliminate
    if not out:
        return {}
    through = R.qualify_count(state, out)
    if state.fmt == R.MADISON:
        return {
            DOC_STARTLIST: msg("note_madison_startlist", n=out),
            DOC_RESULTS: msg("note_madison_results", n=through),
        }
    # an omnium: what the batteria qualifies for is the omnium itself - the
    # four prove - and the sheet says it in the words of the categoria riding
    f = comp.female(state.cat)
    return {
        DOC_STARTLIST: gendered(f, "note_omnium_startlist_m",
                                "note_omnium_startlist_f", n=out),
        DOC_RESULTS: gendered(f, "note_omnium_results_m",
                              "note_omnium_results_f", n=through),
    }


def _velocita_notes(state, comp: Competition, scheme) -> dict[str, str]:
    """What each sheet of a velocità says by itself.

    These lines are the decisions of the event, and they are known before it is
    ridden: the start order of the 200 m announces how many it qualifies, and
    each results sheet announces what the round it composes rides for.
    """
    if scheme is None:
        return {}
    rk = state.round_key
    if rk == R.sprint_qualifying(comp, state.cat, state.event):
        # the same line on both sheets: the start order announces the cut, the
        # risultati is the sheet that says who went through it
        return {DOC_STARTLIST: scheme.note, DOC_RESULTS: scheme.note}
    if rk == S.TURNO1:
        f = comp.female(state.cat)
        winner = gendered(f, "winner_m", "winner_f")
        others = gendered(f, "others_m", "others_f")
        return {
            DOC_STARTLIST: msg("note_sprint_round1_start", winner=winner,
                               others=others),
            DOC_RESULTS: msg("note_sprint_round1_results", winner=winner),
            DOC_RESULTS_REP: msg(
                "note_sprint_repechage",
                winners=gendered(f, "winners_m", "winners_f"), others=others),
        }
    return {}


def _default_notes(state, comp: Competition, store: Store,
                   scheme=None, el=None, keirin: bool = False
                   ) -> dict[str, str]:
    """What each sheet of this round says by itself, before the jury edits it.

    **The programme has the last word.** What a fase announces is decided when
    the programme is written - the regulation proposes it and the jury may
    write its own (`core.notes`) - so a fase that states a line for a sheet
    *is* that sheet's line, and nothing is stacked on top of it. What is
    generated here fills in for the sheets the programme cannot state: the
    recuperi, the finale B, and every count that is only known once the riders
    are in front of the jury - how many coppie a batteria actually sent
    through, how many turned up for a keirin.

    `Event.note()` is the older way of saying the same thing, one line per
    specialità typed into `programme.yaml`, and it still opens the ordini di
    partenza of a file written that way.
    """
    notes = dict(_madison_notes(state, comp, store))
    notes.update(_velocita_notes(state, comp, scheme))
    if keirin and el is not None:
        notes.update(_keirin_notes(
            state, el, comp,
            R.keirin_has_final_b(store, comp, state.cat, state.event)))
    finals = (R.is_finals(state.round_key)
              or bool((state.payload or {}).get("final_heats")))
    qualifying = comp.event(state.event).qualifying_note
    if qualifying and not finals:
        notes.setdefault(DOC_RESULTS, qualifying)
    rnd = comp.round_of(state.cat, state.event, state.round_key)
    if rnd.results_note:
        notes[DOC_RESULTS] = rnd.results_note
    if rnd.sheet_note:
        notes[DOC_STARTLIST] = "\n".join(p for p in (
            rnd.sheet_note,
            comp.event(state.event).note(finals=finals,
                                         female=comp.female(state.cat))) if p)
    return notes


def _note_field(state, comp: Competition, doc_kind: str,
                defaults: dict[str, str] | None = None) -> str:
    """The `Decisione / note` field of the sheet being prepared.

    One field per document: what the jury writes on one sheet has no business
    on the others. The startlist's note is the race's own `decision`; the
    others are kept in the payload. A sheet that says something by itself -
    a madison batteria - starts from that, and stays empty once emptied.
    """
    defaults = defaults or {}
    if doc_kind == DOC_STARTLIST:
        finals = (R.is_finals(state.round_key)
                  or bool((state.payload or {}).get("final_heats")))
        current = (state.decision or defaults.get(doc_kind)
                   # the sheets are written about the riders in front of the
                   # jury: "La prima atleta parte sul rettilineo d'arrivo"
                   or comp.event(state.event).note(
                       finals=finals, female=comp.female(state.cat)))
    else:
        notes = (state.payload or {}).get("notes") or {}
        current = (notes[doc_kind] if doc_kind in notes
                   else defaults.get(doc_kind, ""))
    text = st.text_area(ui("decision_note"), current,
                        key=f"dec_{state.race_id}_{doc_kind}")
    if doc_kind == DOC_STARTLIST:
        state.decision = text
    else:
        state.payload.setdefault("notes", {})[doc_kind] = text
    return text


def _output(state, result, el, comp, store: Store, kind: str, font: int,
            sign: bool = True, club: bool = False,
            time_col: bool = True, note: str = "", show_bib: bool = True,
            screen_font: int = 10, scheme=None, keirin: bool = False,
            lane: bool = False, detail: bool = False, warned=()) -> None:
    kinds = _doc_kinds(comp, state, store)
    doc_kind = (st.session_state.get(f"doc_{state.race_id}") or kinds[0])
    # a velocità round rides more than one race and composes the next one on
    # the same sheet: its results are read per batteria, and the batterie it
    # sends out print underneath (see `_velocita_inputs`)
    sprint = scheme is not None and kind == R.BRACKET
    # a keirin round does the same, and names its two finals by the places they
    # ride for instead of by a number
    finals_labels = R.keirin_final_labels(state) if keirin else ("", "")
    # one line for the whole business of the sheet - which document, its number,
    # the button that files it and the one that sends the race on - so the
    # preview starts above the fold
    advance = _advance_button(comp, state, kind, doc_kind, el, store, result,
                              scheme, keirin)
    head = st.columns([3, 1, 1, 1] if advance else [3, 1, 1],
                      vertical_alignment="bottom")
    doc_kind = head[0].radio(label("document"), kinds, horizontal=True,
                             key=f"doc_{state.race_id}",
                             format_func=lambda k: _doc_label(
                                 state, k, sprint, keirin, finals_labels),
                             label_visibility="collapsed")
    # the sheet the jury is on, kept with the race it is on (see `_seed_doc`)
    if doc_kind != store.settings.get(LAST_DOC):
        store.set_setting(LAST_DOC, doc_kind)
    com = head[1].text_input(label("communique_no"),
                             value=state.communiques.get(doc_kind, "")
                             or C.number_for(comp, state.cat, state.event,
                                             state.round_key, doc_kind),
                             key=f"com_{state.race_id}_{doc_kind}")

    heats = []
    if state.payload.get("heats"):
        try:
            heats = parse_heats(state.payload["heats"])
        except ParseError as exc:
            notify.text(str(exc), level="error")

    # the final classification of a multi-round_key event spans every round_key
    aggregate = (doc_kind == DOC_CLASSIFICATION
                 and comp.event(state.event).fmt
                 in ("omnium", "sprint", "keirin"))
    filed = _decisions_on(store, state, doc_kind, kinds)
    if doc_kind == DOC_CLASSIFICATION:
        # and the W goes with them: it says a rider carries an ammonizione
        # *into the race on this sheet*, which is something a final ranking
        # does not have. The ammonizione was published on the comunicato of the
        # fase it was given in, and is read there.
        warned = {}
    if aggregate:
        result = _standings(state, el, comp, store)
    # a prova of an omnium: the classifica parziale that starts the next one,
    # the points its own placings are worth, the running total of the corsa a
    # punti (see § omnium)
    omnium = comp.event(state.event).fmt == "omnium"
    prova = _is_prova(comp, state)
    if prova:
        result = _omnium_result(state, el, comp, store, result, doc_kind)

    extra = (D.composition_tables(
        R.sprint_composition(store, comp, el, state, doc_kind), el, state.cat,
        font_size=font) if sprint and doc_kind != DOC_CLASSIFICATION else [])
    if sprint and doc_kind in (DOC_RESULTS, DOC_RESULTS_REP, DOC_RESULTS_58):
        result = _velocita_result(state, doc_kind)
    if keirin and doc_kind != DOC_CLASSIFICATION:
        # the sheet that decides the finals publishes their ordine di partenza
        # underneath: it is the comunicato the jury reads them off
        extra = D.composition_tables(
            R.keirin_composition(
                comp, el, state, doc_kind,
                final_b=R.keirin_has_final_b(store, comp, state.cat,
                                             state.event)),
            el, state.cat, font_size=font, heat_label=label("final"))
        keirin_result = _keirin_result(state, el, comp, doc_kind)
        if keirin_result is not None:
            result = keirin_result

    if keirin and doc_kind == DOC_STARTLIST_REP:
        # the recuperi have an ordine di partenza of their own, on the round
        # they are ridden in: same sheet, other batterie
        rep = R.bracket_heats(state, R.REP_HEATS)
        doc = D.race_startlist(
            state, el, comp, communique=com, font_size=font, decision=note,
            heats=parse_heats(R.heats_text(rep)) if rep else None,
            show_uci=True, extra_tables=extra, warned=warned, decisions=filed,
            subtitle=_keirin_subtitle(state, el, comp, doc_kind),
            slug=f"{race_slug(state.cat, state.event, state.round_key)}"
                 f"_{DOC_STARTLIST_REP}")
    elif doc_kind == DOC_STARTLIST:
        for w in _heat_size_warnings(heats, comp, state):
            notify.text(w)
        labels = ([ui("final_n_place", name=n)
                   for n in R.final_labels()][-len(heats):]
                  if sprint and state.round_key == S.FINALI else [])
        if keirin and R.is_finals(state.round_key):
            # both finals on one sheet, each named by what it rides for: the
            # register plans no comunicato for it, it is the jury's own check
            low = R.bracket_heats(state, R.HEATS_B)
            heats = parse_heats(R.heats_text(R.bracket_heats(state) + low))
            labels = [ui("final_n_place", name=n)
                      for n in finals_labels if n][:len(heats)]
        if sprint and state.round_key == S.FINALI:
            f58 = (R.bracket_heats(state, R.HEATS_58)
                   if R.sprint_has_58(store, comp, state.cat, state.event)
                   else [])
            if f58:
                # one race, and it is a final: the column says which one, once
                # against the first line - as on its own risultati
                extra = D.composition_tables(
                    [(R.composition_title(label("final_5_8")), f58,
                      [label("final_5_8_short")])], el, state.cat,
                    font_size=font, heat_label=label("final")) + list(extra)
        doc = D.race_startlist(state, el, comp, heats=heats or None,
                               communique=com, font_size=font, decision=note,
                               show_bib=show_bib, heat_labels=labels,
                               # every ordine di partenza of a velocità carries
                               # the UCI ID - the 200 m as much as the batterie,
                               # and a keirin's batterie carry it too. A round
                               # of qualificazione and every prova of an omnium
                               # carry it wherever they are printed from, which
                               # is the document's own rule
                               # (`documents.race_startlist`)
                               show_uci=(R.is_sprint(comp, state.event)
                                         or keirin or None),
                               warned=warned, decisions=filed,
                               extra_tables=extra)
    else:
        subtitle = (label("final_classification")
                    if doc_kind == DOC_CLASSIFICATION
                    else _velocita_subtitle(state, doc_kind) if sprint
                    else _keirin_subtitle(state, el, comp, doc_kind) if keirin
                    else _omnium_subtitle(state, doc_kind) if prova
                    and _omnium_subtitle(state, doc_kind)
                    else ui("round_results", round=state.round_key)
                    if state.round_key else label("risultati"))
        # a finals round prints its two finals as they were ridden, and names
        # the champion only on the classification of the event
        finals = bool(state.payload.get("final_heats"))
        # a madison assigns the title in one race: the classifica of anything
        # that is not a batteria closes the specialità and names the champions
        title_race = finals or (kind == R.MADISON
                                and not R.heat_number(state.round_key))
        # a velocità is won in the 1°-2° final, a keirin in the final for the
        # title and an omnium on the points of four prove: the classification
        # of the event is where the champion is named, as everywhere else
        if (sprint or keirin or omnium) and doc_kind == DOC_CLASSIFICATION:
            title_race = True
        block_title = ""
        if keirin and doc_kind == DOC_CLASSIFICATION:
            # the classifica of a keirin is read final by final, not as one
            # ranking: the block that assigns the title, then the one under it
            result, extra, block_title = _keirin_blocks(
                state, result, el, comp, font, club, show_bib, extra)
        # what the sheets of an omnium show of the race under them
        points_cols = _omnium_points_cols(state, doc_kind) if prova else []
        show_sprints, show_rank, show_carried = not aggregate, True, False
        show_uci = show_laps = True
        if prova and doc_kind == DOC_PARTIAL:
            # the sheet is the ordine di partenza of the next prova, and on the
            # scratch the placing is the order it is already printed in
            show_sprints = False
            show_rank = state.round_key != O.SCRATCH
        elif prova and doc_kind == DOC_RESULTS:
            # the volate of a tempo race are on its gara, the sheet they were
            # called on; the corsa a punti is scored from the points brought
            # into it, and takes the width for them off the UCI ID
            show_sprints = state.round_key != O.TEMPO
            show_carried = state.round_key == O.POINTS_RACE
            show_uci = state.round_key != O.POINTS_RACE
        elif aggregate and omnium:
            # the classifica is read as the corsa a punti was scored: what each
            # rider took into it, every volata, the giri, then the total
            show_sprints = show_carried = show_laps = detail
        doc = D.race_classification(state, result, el, comp, communique=com,
                                    subtitle=subtitle, font_size=font,
                                    decision=note,
                                    show_sprints=show_sprints,
                                    show_rank=show_rank,
                                    show_uci=show_uci,
                                    show_laps=show_laps,
                                    show_carried=show_carried,
                                    lane_col=lane and doc_kind == DOC_PARTIAL,
                                    warned=warned, decisions=filed,
                                    # the standings of an omnium keep the DNS:
                                    # there the sigla is what says the rider is
                                    # out of the event, not an absence from one
                                    # prova (`documents.race_classification`)
                                    hide_dns=False if aggregate else None,
                                    points_cols=points_cols,
                                    # the classifica of an omnium files the
                                    # society by name: the code is on the
                                    # elenco iscritti, and the sheet is full
                                    show_club_code=not (aggregate and omnium),
                                    by_final=finals and doc_kind == DOC_RESULTS,
                                    champion=title_race
                                    and doc_kind == DOC_CLASSIFICATION,
                                    doc_kind=doc_kind, show_club=club,
                                    show_time=time_col, show_bib=show_bib,
                                    champion_label=(
                                        "" if R.is_team_format(kind)
                                        else _champion_label(comp, state.cat)),
                                    extra_tables=extra,
                                    slug=_doc_slug(state, doc_kind),
                                    qualify=_velocita_cut(state, comp, scheme,
                                                          doc_kind),
                                    # "12 partenti" over a sheet of batterie
                                    # counts what the table already says
                                    show_count=not (sprint or keirin))
        if block_title:
            # each block of a keirin classifica says which final it is: the
            # first one too, or the table under it would look like the only
            # one that was named
            doc.tables[0].title = block_title
    doc.landscape = bool(st.session_state.get(f"land_{state.race_id}"))

    p = save_button(store, doc, comp, number=com, key=state.race_id,
                    signature=sign, container=head[2])
    if p is not None:
        state.communiques[doc_kind] = com
        store.save_race(state)
        C.issue(store, comp, cat=state.cat, event=state.event,
                round_key=state.round_key, doc=doc_kind, number=com,
                title=f"{doc.title} - {doc.subtitle}".strip(" -"),
                file=p.name)
    # sending the race on belongs to the results sheet you have just printed:
    # it goes next to Salva PDF, in the primary colour, because it is the one
    # button of this page that changes another race
    if advance and head[3].button(advance[0], type="primary", help=advance[1]):
        advance[2]()
    if result.pending:
        # a race against the clock says it in its own words: the finali are
        # seeded, so the sheet carries an order before anyone has ridden, and
        # what is missing there is the tempi
        notify.info("pending_times" if kind in (R.TIMED, R.TIMED_TEAM)
                    else "pending_results", n=result.pending)

    # The preview is what the speaker reads while the race is on: its own body
    # size, and the last sprint called out above it. Only on screen - the PDF
    # was built (and filed) above, at the printing size.
    _last_sprint_banner(state, el, kind, doc_kind)
    _last_time_banner(state, el, kind, doc_kind)
    for t in doc.tables:
        t.font_size = screen_font
    # A sheet that carries two races leaves the first one nameless on screen:
    # the letterhead is dropped here, and the subtitle that names it goes with
    # it, while the block underneath keeps a heading of its own. So the first
    # table takes the subtitle - in the preview only, since on paper it is
    # already printed right above it. Safe after `save_button`: the PDF of this
    # run was built above, and the next run rebuilds the document from scratch.
    if len(doc.tables) > 1 and not doc.tables[0].title:
        doc.tables[0].title = doc.subtitle
    # no letterhead on screen: the page header above says the same thing, and
    # the block pushed the table below the fold. The PDF keeps it.
    st.html(to_html(doc, comp, head=False, footer=False, signature=sign,
                    sig_px=SIG_PREVIEW_PX, css=False))


def _advance_button(comp: Competition, state, kind: str, doc_kind: str,
                    el, store: Store, result, scheme=None,
                    keirin: bool = False):
    """(label, help, action) for the button that sends this race on, if any.

    Composed before the row is drawn, because it decides how many columns the
    row has - and a column that appears only after the click would move the
    others while the jury is pressing them.
    """
    if keirin:
        return _keirin_advance(comp, state, doc_kind, el, store)
    if scheme is not None:
        return _velocita_advance(comp, state, kind, doc_kind, el, store, scheme)
    if doc_kind != DOC_RESULTS and kind != R.BRACKET:
        return None
    nxt = _next_round(comp, state)
    if R.heat_number(state.round_key) \
            and R.is_composed(comp, state.cat, state.event):
        # a batteria of an event the jury composed: it qualifies for the races
        # that follow it - the finale of a madison, the four prove of an omnium
        rounds = R.final_rounds(comp, state.cat, state.event)
        pairs = kind == R.MADISON
        where = rounds[0] if len(rounds) == 1 else ui("the_prove")
        return (ui("load_madison_final" if pairs else "load_omnium_final"),
                help_text("load_madison_final", round=where) if pairs
                else help_text("load_omnium_final"),
                lambda: _load_qualified(state, el, comp, store, where))
    if (R.is_pursuit(comp, state.event, kind) and nxt and R.is_finals(nxt)
            and not state.payload.get("final_heats")):
        done = store.load_race(R.race_key(state.cat, state.event, nxt))
        name = ui("update_finals" if done and done.payload.get("final_heats")
                  else "load_finals")
        return (name, help_text("load_finals", round=nxt),
                lambda: _load_finals(state, result, el, comp, store, nxt))
    if kind == R.BRACKET:
        return (ui("compose_heats"), help_text("compose_from_previous"),
                lambda: _compose_round(state, el, comp, store))
    return None



def _velocita_advance(comp: Competition, state, kind: str, doc_kind: str,
                    el, store: Store, scheme):
    """The button that composes the next round of a velocità, where it belongs.

    On the sheet that publishes the composition, and nowhere else: the quarti
    go out on the *risultati recuperi*, so that is where «Carica Quarti di
    finale» is, and the risultati of the first round only send out the
    recuperi - which are composed by themselves, and need no button at all.
    """
    rk = state.round_key
    qual = R.sprint_qualifying(comp, state.cat, state.event)
    on = {qual: DOC_RESULTS, S.TURNO1: DOC_RESULTS_REP,
          S.QUARTI: DOC_RESULTS, S.SEMI: DOC_RESULTS}
    if doc_kind != on.get(rk):
        return None
    nxt = (scheme.rounds[0] if rk == qual else scheme.next_round(rk))
    if not nxt:
        return None
    names = {S.TURNO1: ui("load_round_1"), S.QUARTI: ui("load_quarters"),
             S.SEMI: ui("load_semifinals"), S.FINALI: ui("load_finals")}

    def run():
        loaded, n = R.load_sprint_round(store, comp, el, state)
        if not loaded:
            notify.warn("missing_result")
            return
        notify.ok("round_composed", round=loaded, n=n)

    extra = (msg("and_final_5_8") if rk == S.QUARTI
             and R.sprint_has_58(store, comp, state.cat, state.event) else "")
    return (names.get(nxt, ui("load_generic", round=nxt)),
            help_text("compose_next", round=nxt, extra=extra), run)


def _unplaced_banner(state, el, kind: str) -> None:
    """Who is still not in the arrival of a prova di gruppo that has been run.

    The sheet would classify them behind everybody else without saying so - the
    scoring has no way to tell "arrived last" from "never written down" - so
    the page says it while there is still somebody at the finish line to ask.
    """
    missing = R.bunch_unplaced(state, el, kind)
    if not missing:
        return
    who = label("pairs" if kind == R.MADISON else "athletes")
    notify.warn("unplaced_riders", n=len(missing), who=who,
                bibs=", ".join(str(b) for b in missing))


def _last_sprint_banner(state, el, kind: str, doc_kind: str) -> None:
    """The bibs of the last sprint entered, for the speaker to read out.

    On screen only: it says what has just been typed, which on paper would be
    either wrong by the time it prints or already in the sprint columns.

    Only over the risultati, which is the sheet read while the race is on. The
    classifica is the sheet that gets printed and handed out: what the last
    sprint was is over by then, and a banner above it only reads as part of it.
    """
    if doc_kind in (DOC_STARTLIST, DOC_CLASSIFICATION):
        return
    text = (state.payload or {}).get("sprints", "")
    if not text.strip():
        return
    last = [s for s in text.split("-") if s.strip()]
    if not last:
        return
    n = len(last)
    bibs = [b.strip() for b in last[-1].split(",") if b.strip()]
    # the numbers as they were called, nothing else: the first four score
    # (5-3-2-1) and are the ones the speaker reads out, so only those are bold
    called = " - ".join(f"<b>{b}</b>" if i < 4 else b
                        for i, b in enumerate(bibs))
    st.markdown(f'<div class="cmsr-sprint">'
                f'<span class="lbl">{ui("volata_n", n=n)}</span>'
                f'{called}</div>{_BANNER_CSS}', unsafe_allow_html=True)


def _last_time_banner(state, el, kind: str, doc_kind: str) -> None:
    """The start just timed, as the speaker calls it out.

    The same banner as the volate of a prova di gruppo, because it is read for
    the same thing: what has just happened on the track. A race against the
    clock is called on one line - the number, the name, and where the time puts
    the rider *for now*, which is the only thing the crowd wants to know while
    the next one is still lining up.
    """
    if kind not in (R.TIMED, R.TIMED_TEAM) or doc_kind == DOC_STARTLIST:
        return
    key = st.session_state.get(f"lastt_{state.race_id}")
    times = {k: v for k, v in ((state.payload or {}).get("times") or {}).items()
             if v}
    if not key or key not in times:
        return
    # provisional and said so: the starts still to come can only push it down
    rank = 1 + sum(1 for v in times.values() if v < times[key])
    riders = R.entrant_riders(key, el, state.cat)
    who = (f"{riders[0].bib} {riders[0].full_name}"
           if len(riders) == 1 and riders[0].bib
           else R.entrant_label(key, el))
    # the time first and in bold - it is what the banner exists for - then who
    # rode it, then where it puts them for now
    st.markdown(f'<div class="cmsr-sprint">'
                f'<b>{format_time(times[key])}</b> · {who} · '
                f'{msg("provisional_time", n=ordinal(rank))}'
                f'</div>{_BANNER_CSS}', unsafe_allow_html=True)


#: The speaker's banner over the risultati: the last volata as it was called.
_BANNER_CSS = """
<style>
.cmsr-sprint {
    border-left: 4px solid #d93636;
    background: rgba(217, 54, 54, .08);
    padding: .35rem .6rem;
    margin: .2rem 0 .4rem 0;
    font-size: 1.1rem;
    letter-spacing: .02em;
}
.cmsr-sprint .lbl {
    opacity: .7;
    font-size: .8rem;
    text-transform: uppercase;
    margin-right: .8rem;
}
</style>"""


def _next_round(comp: Competition, state) -> str:
    """The round after this one in the programme, if there is one."""
    rounds = [r.key for r in comp.rounds(state.cat, state.event)]
    i = rounds.index(state.round_key) if state.round_key in rounds else -1
    return rounds[i + 1] if 0 <= i < len(rounds) - 1 else ""


def _load_finals(state, result, el, comp: Competition, store: Store,
                 nxt: str) -> None:
    """Carry the qualification into the finals round.

    The finals are a race of their own: only the qualified start it, the heats
    are the 3/4 and the 1/2 final, and the times of the qualification travel
    with them - whoever did not qualify is classified on them.
    """
    team = R.is_team_format(state.fmt or "")
    ranking = [p.key for p in result.placings if p.position]
    n = comp.round_of(state.cat, state.event, state.round_key).qualify or 4
    if len(ranking) < 2:
        notify.warn("need_two_qualified_f" if team else "need_two_qualified_m")
        return

    fin = R.ensure_state(store, comp, state.cat, state.event, nxt, el)
    p, q = fin.payload, state.payload
    fin.entrants = ranking[:n]
    # the numbers each squadra actually fielded, reserves included
    bibs = {k: parse_bibs(_side_bibs(k, el, q.setdefault("heat_bibs", {}),
                                     state.cat))
            for k in ranking}
    p["qual_ranking"] = ranking
    # le non classificate non corrono le finali, ma la classifica della
    # specialità è il foglio che deposita la decisione presa su di loro
    p["qual_out"] = {pl.key: pl.status.value for pl in result.placings
                     if pl.status is not Status.OK and not pl.position}
    p["qual_times"] = dict(q.get("times") or {})
    p["qual_bibs"] = {k: bibs[k] for k in fin.entrants}
    p["final_heats"] = T.seed_finals(fin.entrants)
    p["heats"] = T.seed_finals_text([bibs[k] for k in fin.entrants])
    p["heat_bibs"] = {k: _bibs_text(bibs[k]) for k in fin.entrants}
    p.pop("heat_sides", None)  # rebuilt from the seeded finals
    store.save_race(fin, action="load_finals")
    names = " e ".join(T.final_label(T.final_place(h, ranking))
                       for h in p["final_heats"])
    notify.ok("finals_loaded", round=nxt, n=len(fin.entrants), names=names,
              who=msg("qualified_teams" if team else "qualified_riders"))


def _load_qualified(state, el, comp: Competition, store: Store,
                    where: str) -> None:
    """Carry every batteria into what follows it, and say what went through."""
    pairs = R.round_format(comp, state.cat, state.event,
                           state.round_key) == R.MADISON
    info = R.load_qualified(store, comp, el, state.cat, state.event,
                            current=state)
    for key in info["missing"]:
        notify.warn("madison_heat_no_result" if pairs
                    else "omnium_heat_no_result", round=key)
    if not info["qualified"]:
        notify.error("madison_no_qualified" if pairs else "omnium_no_qualified")
        return
    for n, (through, out) in sorted(info["heats"].items()):
        st.caption(ui("heat_qualified" if pairs else "heat_qualified_riders",
                      n=n, through=len(through), out=len(out)))
    notify.ok("madison_final_loaded" if pairs else "omnium_final_loaded",
              round=where, n=len(info["qualified"]))


def _standings(state, el, comp: Competition, store: Store):
    """Aggregate classification of a whole event (omnium / sprint / keirin)."""
    fmt = comp.event(state.event).fmt
    if fmt == "omnium":
        return R.omnium_standings(store, comp, el, state.cat,
                                  state.event)
    if fmt == "sprint":
        # 1-8 are the finals, everybody else is the 200 m: a velocità run to a
        # scheme knows exactly which race decided which place
        return R.sprint_standings(store, comp, el, state.cat, state.event)
    if fmt == "keirin":
        # the two finals, then how far each rider got: a keirin has no
        # qualifying time to fall back on (see `race.keirin_standings`)
        return R.keirin_standings(store, comp, el, state.cat, state.event)
    return R.bracket_standings(store, comp, el, state.cat, state.event)


def _compose_round(state, el, comp: Competition, store: Store) -> None:
    """Seed this round's heats from the ranking of the previous round_key."""
    rounds = [p.key for p in comp.rounds(state.cat, state.event)]
    if state.round_key not in rounds:
        notify.warn("round_not_in_programme")
        return
    idx = rounds.index(state.round_key)
    if idx == 0:
        notify.warn("first_round_no_previous")
        return

    ranking: list[str] = []
    for prev in reversed(rounds[:idx]):
        prev_state = store.load_race(R.race_key(state.cat, state.event, prev))
        if prev_state is None:
            continue
        if R.round_format(comp, state.cat, state.event, prev) == R.BRACKET:
            ranking = list(R.bracket_round(prev_state, comp).advancing)
        else:
            res = R.classify(prev_state, el, comp)
            ranking = [p.key for p in res.placings if p.position]
        if ranking:
            break

    if not ranking:
        notify.warn("no_previous_ranking")
        return
    state.payload["heats"] = R.compose_bracket_round(state, comp, ranking)
    state.payload.pop("heat_sides", None)
    store.save_race(state, action="compose_round")
    notify.ok("heats_composed_from", n=len(ranking))
    st.rerun()
