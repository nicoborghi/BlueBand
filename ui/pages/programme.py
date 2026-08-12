"""PROGRAMME ("Programma") - what the competition is, before anyone rides it.

Everything the app does comes out of `programme.yaml`: which categories exist,
which events each contests, the rounds of every event, and the register that
says which comunicato number every sheet goes out under. Until now that file
was written by hand. This page edits it, and writes it back in a layout that
never moves - so next year is this year's file with a few lines changed.

**Nothing here touches a race.** The page reads and writes one file; the races
on disk, the entry list and the comunicati already issued are not its business.
Until *Salva* is pressed nothing is written at all: the edits live in a working
copy held in the session, and *Ricarica dal file* throws them away.

The day is the unit. A tab per day, and inside it the two things that make a
day: which races are ridden, and - in the order they go out - the comunicati
they produce. The order of that second list *is* the numbering.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import replace

import pandas as pd
import streamlit as st

from core import catalogue as CAT
from core import communiques as C
from core import programme as P
from core import rounds as RD
from core.config import (DEFAULT_TRACK_LEN, DOC_ALL_KINDS, DOC_RESULTS,
                         DOC_STARTLIST, EVENT_ENTRY_LIST, ROUND_SETUP,
                         Category, Competition, Event, Round, load_competition,
                         madison_track_teams)
from core.formats import sprint as S
from core.i18n import help_text, label, msg, ui
from core.store import Store
from render import documents as D
from render.render import to_html
from ui import notify, savebar, state
from ui.download import save_button

DRAFT = "prog_draft"
DRAFT_OF = "prog_draft_of"

#: The freeze lives in the session as well as on the draft: it is a switch the
#: jury flicks while it works, and the draft is rebuilt from the file whenever
#: the competition changes. `FROZEN_SET` says the jury flicked it - until then
#: what the box shows is a safety default, and defaults are not written down.
FROZEN = "prog_frozen"
FROZEN_SET = "prog_frozen_set"


def _freeze_touched() -> None:
    st.session_state[FROZEN_SET] = True

#: Not a code: what the picker offers for "a specialità the catalogue has not
#: got", which is then declared by hand.
OTHER_EVENT = "*"

#: A track is quoted in metres and stored in kilometres.
M_PER_KM = 1000

#: The formats ridden against the clock two at a time or one at a time - the
#: inseguimento and, on the same machinery, the chilometro.
STARTS_CHOICE = ("timed", "time_trial")

#: The formats a specialità can be run under - what `race.round_format` knows.
FORMATS = ("group", "elimination", "timed", "timed_team", "sprint", "keirin",
           "omnium", "madison", "time_trial", "entrylist")


def render(competition: str, comp: Competition, store: Store) -> None:
    draft = _draft(competition, comp)
    issues = _toolbar(draft, store)

    # Salva and Ricarica are pinned to the foot of the sidebar, like every
    # other page's (`ui.savebar`), and are drawn before the tabs that fill the
    # draft in - so what they asked for is done at the end, below.
    savebar.render(label=ui("save_programme"),
                   restore_label=ui("reload_programme"),
                   help=help_text("save_programme"),
                   restore_help=help_text("reload_programme"),
                   disabled=any(i.level == "error" for i in issues))

    # The days in the middle, and the two things that are not a day at either
    # end: what the competition *is* first, and the sheet it all prints as
    # last. The specialità sit next to the competition because that is when
    # they are chosen - once, before any day has a race on it.
    days = P.days_of(draft)
    tabs = st.tabs([ui("prog_tab_competition"), ui("prog_tab_events")]
                   + [_day_title(draft, d) for d in days]
                   + [ui("programme_print")])
    with tabs[0]:
        _competition_tab(draft)
    with tabs[1]:
        _events_tab(draft)
    for i, day in enumerate(days):
        with tabs[2 + i]:
            _day_tab(draft, day)
    with tabs[-1]:
        _print_programme(draft, store)

    _save(competition, draft, store)


def _save(competition: str, draft: Competition, store: Store) -> None:
    """Act on the pinned Salva / Ricarica, once the tabs have been read.

    At the end and not where the buttons are: the draft is filled in by the
    grids above, and a programme saved before they had run would be the one
    the page opened on.
    """
    action = savebar.requested()
    if action == savebar.SAVE:
        P.save(draft.path, draft, store=store)
        notify.ok("programme_saved", path=draft.path)
        # the other pages hold the programme through a cache keyed on the file:
        # dropping it here is what makes the save visible at once, rather than
        # at whatever moment something else happens to reread it
        state.refresh()
    elif action == savebar.RESTORE:
        _reload(competition, draft)
        st.rerun()


# ── grids that do not fight the model behind them ───────────────────────────
#
# Every grid on this page edits a `Competition` that the page itself rebuilds
# from the grid on the next run, and that is a loop Streamlit loses: a keyed
# widget is re-initialised when the data it was given changes, and a
# `st.data_editor` keeps its edits as a *diff against the frame it was handed*.
# Feeding it a frame rebuilt from the model it has just edited therefore
# applied the diff twice, or on the wrong row - which is what "it takes one
# input and drops the next" is.
#
# So the grid is handed a frame that stays put, and is only ever rebuilt when
# the model changed for a reason that is *not* this grid: a reload, a race
# added on another tab, a renumbering. `_grid_done` is what says "the model now
# says what the grid says", and the widget key carries a generation so that a
# real rebuild starts a clean widget instead of a fresh frame under an old diff.
#
# `sticky_select` in `ui.state` is the same lesson learned on a selectbox.

def _sig(rows: list[dict]) -> str:
    return json.dumps(rows, default=str, sort_keys=True)


def _grid(name: str, rows: list[dict], **kwargs):
    """A `st.data_editor` whose source only changes when the model does."""
    if st.session_state.get(f"{name}_sig") != _sig(rows):
        _grid_reset(name, rows)
    return st.data_editor(st.session_state[f"{name}_src"],
                          key=f"{name}_{st.session_state[f'{name}_gen']}",
                          **kwargs)


def _grid_reset(name: str, rows: list[dict]) -> None:
    st.session_state[f"{name}_sig"] = _sig(rows)
    st.session_state[f"{name}_src"] = pd.DataFrame(rows)
    st.session_state[f"{name}_gen"] = st.session_state.get(f"{name}_gen", 0) + 1


def _grid_done(name: str, rows: list[dict]) -> None:
    """What the model says now, so the next run does not reset the grid."""
    st.session_state[f"{name}_sig"] = _sig(rows)


def _pick(key: str, options: list[str], current: list[str]) -> list[str]:
    """A multiselect seeded once, never handed a `default` again.

    Same trap as the grids and as `state.sticky_select`: passing `default=` on
    every run re-initialises the widget the moment the model behind it moves,
    and a jury ticking a third specialità watched the second one vanish.
    """
    if key not in st.session_state:
        st.session_state[key] = [c for c in current if c in options]
    # an option that has gone (a code deleted in the grid) would make the
    # widget raise: the session is trimmed to what is on offer, here and openly
    st.session_state[key] = [c for c in st.session_state[key] if c in options]
    return st.session_state[key]


# ── the working copy ────────────────────────────────────────────────────────

def _draft(competition: str, comp: Competition) -> Competition:
    """The programme being edited, held in the session until it is saved.

    A copy and not the loaded object: `ui.state.competition` caches that one and
    hands the same instance to every page, so editing it in place would change
    what Gare is running from - while the jury is running it.
    """
    if st.session_state.get(DRAFT_OF) != competition:
        _reload(competition, comp)
    return st.session_state[DRAFT]


def _reload(competition: str, comp: Competition) -> None:
    st.session_state[DRAFT] = load_competition(comp.path)
    st.session_state[DRAFT_OF] = competition


def _day_title(comp: Competition, day: int) -> str:
    date = P.date_of(comp, day)
    return f"{ui('day')} {day}" + (f" · {date[-5:]}" if date else "")


def _toolbar(draft: Competition, store: Store) -> list:
    """What the programme counts, what it is wrong about, and its numbering.

    Not the saving: that is pinned to the sidebar (`ui.savebar`). Returns the
    issues so the caller can grey out a Salva that would write a programme with
    a duplicate comunicato number in it.
    """
    issues = P.issues(draft, C.load(store))
    errors = [i for i in issues if i.level == "error"]

    st.caption(ui("programme_counts", events=len(draft.programme),
                  communiques=len(draft.communiques), path=draft.path))
    _numbering(draft, store)

    if issues:
        with st.expander(ui("checks_summary", errors=len(errors),
                            warnings=len(issues) - len(errors)),
                         expanded=bool(errors)):
            notify.issues(issues)
    return issues


# ── the numbers, and whether they still move ────────────────────────────────

def _numbering(draft: Competition, store: Store) -> None:
    """The freeze, and the renumbering that happens while it is off.

    Unfrozen, the register is a *view of the running order*: every rerun
    redeals the numbers from `sheet_order`, so moving a race up the day moves
    its comunicati with it and the two can never drift. What the jury typed by
    hand stays where it is, and so does anything already issued.

    It is defaulted **on** for a competition whose register is not empty:
    inheriting a hand-numbered register - CITA 26 has 140 entries transcribed
    from paper - and renumbering it on the first rerun would be the app
    rewriting the jury's own record uninvited.

    That default is a safety catch and not a statement, so it is *not* written
    to the file: `numbering_frozen:` appears in `programme.yaml` only once
    somebody has actually flicked the switch. Opening this page and pressing
    Salva has to leave the file byte for byte as it was.
    """
    if FROZEN not in st.session_state:
        st.session_state[FROZEN] = bool(draft.numbering_frozen
                                        or draft.communiques)
    frozen = st.checkbox(ui("freeze_numbering"), key=FROZEN,
                         on_change=_freeze_touched,
                         help=help_text("freeze_numbering"))
    if st.session_state.get(FROZEN_SET):
        draft.numbering_frozen = frozen
    if frozen:
        st.caption(msg("numbering_frozen"))
        return

    # Unfrozen, the register *is* the programme: every sheet it produces gets
    # a number, and one that is missing appears the moment the race is added.
    # What protects an inherited register from being rewritten is the freeze
    # above, defaulted on for exactly that case - not a second rule here, which
    # would also stop the register of a competition being built from growing
    # after its first entry.
    issued = C.load(store)
    draft.communiques = C.autonumber(draft, issued)
    pinned = sum(1 for c in draft.communiques if c.pinned) + len(issued)
    st.caption(msg("numbering_free", n=pinned))


# ── the programme, printed ──────────────────────────────────────────────────

def _print_programme(draft: Competition, store: Store) -> None:
    """The running order with the comunicato numbers beside it, as a sheet."""
    st.caption(help_text("programme_print"))
    c1, c2, c3 = st.columns(3)
    times = c1.checkbox(ui("programme_times"), value=True, key="prog_sheet_time")
    merge_round = c2.checkbox(ui("programme_merge_round"), key="prog_sheet_round")
    merge_results = c3.checkbox(ui("programme_merge_results"),
                                key="prog_sheet_res")
    c1, c2 = st.columns(2)
    font = c1.slider(ui("table_font"), 6, 14, 9, key="prog_sheet_font")
    landscape = c2.checkbox(ui("landscape"), key="prog_sheet_land",
                            help=help_text("landscape_short"))

    doc = D.programme_sheet(draft, times=times, merge_round=merge_round,
                            merge_results=merge_results, font_size=font)
    doc.landscape = landscape
    save_button(store, doc, draft, number=label("programme_slug"),
                key="prog_sheet", label=ui("save_programme_pdf"))
    st.html(to_html(doc, draft, banner=False, signature=False, footer=False,
                    css=False))


# ── the competition itself ──────────────────────────────────────────────────

def _competition_tab(draft: Competition) -> None:
    st.subheader(ui("prog_tab_competition"))
    c1, c2 = st.columns(2)
    draft.name = c1.text_input(ui("competition_name"), draft.name,
                               key="prog_name")
    draft.short = c2.text_input(ui("competition_short"), draft.short,
                                key="prog_short")
    c1, c2, c3 = st.columns(3)
    draft.race_id = c1.text_input(ui("competition_id"), draft.race_id,
                                  key="prog_id")
    draft.location = c2.text_input(ui("competition_location"), draft.location,
                                   key="prog_location")
    with c3:
        _track_len(draft)

    st.caption(ui("dates_caption"))
    # the format is not guessable and a wrong one is a competition with no
    # days at all: it is shown in the field, not only in the tooltip
    dates = st.text_input(ui("dates"), ", ".join(draft.dates), key="prog_dates",
                          placeholder=ui("dates_hint"),
                          help=help_text("dates"))
    draft.dates = [d.strip() for d in dates.split(",") if d.strip()]

    st.divider()
    _events_of(draft)

    st.divider()
    _categories(draft)

    # last, and under no rule of its own: what the tabs are writing, as it will
    # be on disk. A collapsed expander between two dividers read as two rules
    # with nothing in between.
    with st.expander(ui("yaml_preview")):
        st.code(P.dump(draft), language="yaml")


def _events_of(draft: Competition) -> None:
    """Which specialità this competition contests - a list, not a form.

    Everything *about* a specialità that a jury actually decides differs from
    categoria to categoria: how many batterie di qualificazione, what distance,
    whether the chilometro is ridden two at a time or one at a time, whether
    the velocità rides its 5°-8°. Asking those here, once per specialità, gave
    an answer that was wrong for half the categorie and looked authoritative.
    They are asked instead where they are true - when the race is put on a
    giornata (`_add_race`).

    So this is a picker: tick the specialità that are on the programme. The
    catalogue fills in the code, the sigla UCI, the format and the atleti per
    squadra (`core.catalogue`); the Specialità tab is where those are corrected
    on the rare occasion they need to be.
    """
    known = [c for c in CAT.codes()] + [c for c in draft.events
                                        if c not in CAT.codes()
                                        and c != EVENT_ENTRY_LIST]
    _pick("prog_events_pick", known, list(draft.events))
    picked = st.multiselect(
        ui("events_of_competition"), known, key="prog_events_pick",
        format_func=_event_name(draft),
        help=help_text("events_of_competition"))

    for code in picked:
        if code not in draft.events:
            draft.events[code] = CAT.event(code, order=len(draft.events))
    for code in [c for c in draft.events
                 if c not in picked and c != EVENT_ENTRY_LIST]:
        # a specialità that is on a giornata is not one to drop from under it:
        # the races would stay in the programme naming an event nobody declares
        if draft.scheduled_any(code):
            notify.warn("event_in_programme", name=draft.event(code).short)
            continue
        del draft.events[code]


def _event_name(draft: Competition):
    """What a specialità is called: what the programme says, or the catalogue."""
    return lambda code: (draft.events[code].short if code in draft.events
                         else CAT.name(code, short=True))


def _track_len(draft: Competition) -> None:
    """The length, in the units it is quoted in, and what follows from it.

    Metres, because that is what is painted on the velodrome and what a jury
    says out loud; the programme stores kilometres. The number decides the giri
    of every distance the file does not spell out and how many coppie the
    madison takes in its final (3.2.157), so the second is shown under it: a
    3330 keyed for 333 stops making sense on the line below before it becomes a
    programme of wrong lap counts.
    """
    metres = st.number_input(
        ui("track_len_m"), 100.0, 1000.0,
        float(draft.track_len or DEFAULT_TRACK_LEN) * M_PER_KM,
        step=0.01, format="%.2f", key="prog_track",
        help=help_text("track_len_m"))
    draft.track_len = float(metres) / M_PER_KM
    teams = madison_track_teams(draft.track_len)
    st.caption(msg("setup_track_holds", n=teams) if teams
               else msg("setup_track_unknown"))


def _categories(draft: Competition) -> None:
    st.subheader(ui("categories"))
    st.caption(ui("categories_caption"))
    edited = _grid(
        "prog_cats",
        _category_rows(draft) or [{label("cat"): "",
                                   ui("competition_name"): "",
                                   label("sex"): "", ui("order"): 1}],
        num_rows="dynamic", hide_index=True, use_container_width=True,
        column_config={
            label("sex"): st.column_config.SelectboxColumn(
                options=["M", "F"], help=help_text("category_sex")),
            ui("order"): st.column_config.NumberColumn(width="small"),
        })
    out = {}
    for i, row in edited.iterrows():
        code = _text(row[label("cat")])
        if not code:
            continue
        out[code] = Category(code=code,
                             name=_text(row[ui("competition_name")]) or code,
                             sex=_text(row[label("sex")]),
                             order=_int(row[ui("order")], i + 1))
    if out:
        draft.categories = out
    _grid_done("prog_cats", _category_rows(draft))


def _category_rows(draft: Competition) -> list[dict]:
    """The categorie as the grid shows them - one builder, read twice."""
    return [{label("cat"): c.code, ui("competition_name"): c.name,
             label("sex"): c.sex, ui("order"): c.order}
            for c in sorted(draft.categories.values(),
                            key=lambda c: (c.order, c.code))]


# ── the events catalogue ────────────────────────────────────────────────────

def _events_tab(draft: Competition) -> None:
    """The catalogue of specialità - what the day tabs then schedule.

    `entry_list` is deliberately not in it. It is not a specialità and nobody
    rides it: it is the pseudo-event the four opening comunicati hang off
    (`config.EVENT_ENTRY_LIST`), and showing it in a grid of races invited the
    jury to edit or delete something the register needs.
    """
    st.subheader(ui("prog_tab_events"))
    st.caption(ui("events_caption"))
    edited = _grid(
        "prog_events", _event_rows(draft), num_rows="dynamic",
        hide_index=True, use_container_width=True,
        column_config={
            ui("format"): st.column_config.SelectboxColumn(
                options=list(FORMATS), help=help_text("event_format")),
            ui("team_size"): st.column_config.NumberColumn(
                width="small", help=help_text("team_size")),
            ui("per_start"): st.column_config.NumberColumn(
                width="small", help=help_text("per_start")),
            ui("entry_columns"): st.column_config.TextColumn(
                help=help_text("entry_columns")),
            ui("order"): st.column_config.NumberColumn(width="small"),
        })

    out: dict[str, Event] = {}
    for i, row in edited.iterrows():
        code = _text(row[ui("code")])
        if not code:
            continue
        # The workbook headers are matched loosely, but they are transcribed
        # exactly - `"Omnium "`, with the trailing space that is the typo in
        # the master file. A comma-joined field cannot hold that, so the value
        # is treated as unchanged when it still reads the same: editing takes
        # effect only when the jury has actually changed something.
        columns = _columns(_text(row[ui("entry_columns")]),
                           getattr(draft.events.get(code), "entry_columns", []))
        out[code] = Event(
            code=code, name=_text(row[ui("competition_name")]) or code,
            short=_text(row[ui("short_name")]),
            abbr=_text(row[ui("abbr")]),
            fmt=_text(row[ui("format")]) or "group",
            entry_columns=columns,
            team_size=_int(row[ui("team_size")], 0),
            teams_per_start=_int(row[ui("per_start")], 2),
            order=_int(row[ui("order")], i + 1))
    if out:
        # the pseudo-event is not in the grid, so the grid cannot be what says
        # whether it exists: it is carried across every rebuild
        if EVENT_ENTRY_LIST in draft.events:
            out.setdefault(EVENT_ENTRY_LIST, draft.events[EVENT_ENTRY_LIST])
        # the six note fields are edited further down the page, one event at a
        # time: they are not in this grid and must survive it
        for code, ev in out.items():
            was = draft.events.get(code)
            if was is not None:
                for name in ("startlist_note", "startlist_note_f",
                             "qualifying_note", "qualifying_note_f",
                             "finals_note", "finals_note_f"):
                    setattr(ev, name, getattr(was, name))
        draft.events = out
    _grid_done("prog_events", _event_rows(draft))
    _event_notes(draft)


def _event_rows(draft: Competition) -> list[dict]:
    """The specialità as the grid shows them, without the pseudo-event."""
    return [{
        ui("code"): ev.code, ui("competition_name"): ev.name,
        ui("short_name"): ev.short, ui("abbr"): ev.abbr,
        ui("format"): ev.fmt, ui("team_size"): ev.team_size or None,
        ui("per_start"): ev.teams_per_start,
        ui("entry_columns"): ", ".join(ev.entry_columns),
        ui("order"): ev.order,
    } for ev in sorted(draft.events.values(), key=lambda e: (e.order, e.code))
        if ev.code != EVENT_ENTRY_LIST]


def _columns(text: str, before: list[str]) -> list[str]:
    """The entry-list column names, keeping what the field cannot express."""
    typed = [c.strip() for c in text.split(",") if c.strip()]
    if typed == [c.strip() for c in before]:
        return list(before)
    return typed


def _event_notes(draft: Competition) -> None:
    """The lines an ordine di partenza opens on, per event.

    A page of text areas rather than six more columns in the grid: they are
    sentences, and one of them is the same sentence written about women.
    """
    with st.expander(ui("event_notes")):
        st.caption(ui("event_notes_caption"))
        codes = [c for c in draft.event_order() if c != EVENT_ENTRY_LIST]
        if not codes:
            return
        code = st.selectbox(ui("event"), codes, key="prog_note_event",
                            format_func=lambda c: draft.event(c).short)
        ev = draft.events[code]
        for name, title in (("startlist_note", ui("note_startlist")),
                            ("qualifying_note", ui("note_qualifying")),
                            ("finals_note", ui("note_finals"))):
            c1, c2 = st.columns(2)
            setattr(ev, name, c1.text_area(
                title, getattr(ev, name), key=f"prog_{name}_{code}",
                height=80))
            setattr(ev, f"{name}_f", c2.text_area(
                f"{title} · {ui('feminine')}", getattr(ev, f"{name}_f"),
                key=f"prog_{name}_f_{code}", height=80,
                help=help_text("note_feminine")))


# ── one day ─────────────────────────────────────────────────────────────────

def _day_tab(draft: Competition, day: int) -> None:
    date = P.date_of(draft, day)
    st.caption(ui("day_line", day=day, date=date or ui("none_short")))
    _races_of_day(draft, day)
    st.divider()
    _communiques_of_day(draft, day)


def _races_of_day(draft: Competition, day: int) -> None:
    st.subheader(ui("races_of_day"))
    st.caption(ui("races_of_day_caption"))
    items = [i for i in draft.programme if i.day == day]
    if not items:
        notify.info("no_race_on_day", day=day)
    for item in items:
        _race_item(draft, item)
    _add_race(draft, day)


def _race_item(draft: Competition, item) -> None:
    ev = draft.event(item.event)
    key = f"{item.cat}_{item.event}_{item.day}"
    head, up, down, kill = st.columns([6, 1, 1, 1], vertical_alignment="bottom")
    head.markdown(f"**{item.cat} · {ev.short}** — "
                  + ui("n_rounds", n=len(item.rounds)))
    index = draft.programme.index(item)
    if up.button("↑", key=f"prog_up_{key}", help=help_text("move_up")):
        draft.programme = P.moved(draft.programme, index, -1)
        st.rerun()
    if down.button("↓", key=f"prog_down_{key}", help=help_text("move_down")):
        draft.programme = P.moved(draft.programme, index, 1)
        st.rerun()
    if kill.button("✕", key=f"prog_del_{key}", help=help_text("remove_race")):
        draft.programme.remove(item)
        st.rerun()

    with st.expander(ui("rounds_of", cat=item.cat, event=ev.short)):
        _rounds_editor(draft, item)
        item.note = st.text_input(label("note"), item.note, key=f"prog_note_{key}",
                                  help=help_text("programme_note"))


def _rounds_editor(draft: Competition, item) -> None:
    """The fasi of one race, and which sheets each of them files.

    `Documenti` is typed as a list of names rather than picked: a multi-value
    cell has no picker in a grid, and the names are the ones the register uses.
    What is not a document kind is flagged under the table, the way every other
    field of this app flags what it cannot read.
    """
    allowed = P.docs_available(draft, item.event)
    name = f"prog_rounds_{item.cat}_{item.event}_{item.day}"
    edited = _grid(
        name,
        _round_rows(item) or [{label("round"): "", ui("round_start"): "",
                               label("distance"): None,
                               label("laps"): None, label("sprint"): None,
                               ui("qualify"): None, ui("eliminate"): None,
                               ui("setup_round"): False,
                               ui("documents"): ", ".join(
                                   (DOC_STARTLIST, DOC_RESULTS))}],
        num_rows="dynamic", hide_index=True, use_container_width=True,
        column_config={
            ui("round_start"): st.column_config.TextColumn(
                width="small", help=help_text("round_start")),
            label("distance"): st.column_config.NumberColumn(
                width="small", help=help_text("round_distance")),
            label("laps"): st.column_config.NumberColumn(
                width="small", help=help_text("round_laps")),
            label("sprint"): st.column_config.NumberColumn(width="small"),
            ui("qualify"): st.column_config.NumberColumn(
                width="small", help=help_text("round_qualify")),
            ui("eliminate"): st.column_config.NumberColumn(
                width="small", help=help_text("round_eliminate")),
            ui("setup_round"): st.column_config.CheckboxColumn(
                width="small", help=help_text("round_setup")),
            ui("documents"): st.column_config.TextColumn(
                help=help_text("round_docs") + " " + ", ".join(allowed)),
        })

    # A round holds more than this grid shows - `heat_size`, its own `label`,
    # a note. Rebuilding it from the visible columns alone would drop them
    # silently on the first save, so an existing round is *edited*, not
    # replaced: what the grid does not show is carried over from it.
    before = {r.key: r for r in item.rounds}
    out, unknown = [], []
    for _i, row in edited.iterrows():
        key = _text(row[label("round")])
        if not key:
            continue
        docs = [d.strip() for d in _text(row[ui("documents")]).split(",")
                if d.strip()]
        unknown += [d for d in docs if d not in DOC_ALL_KINDS]
        out.append(replace(
            before.get(key, Round(key=key)),
            key=key,
            start=_text(row[ui("round_start")]),
            distance=_num(row[label("distance")]),
            laps=_num(row[label("laps")]),
            sprints=_int(row[label("sprint")]),
            qualify=_int(row[ui("qualify")]),
            eliminate=_int(row[ui("eliminate")]),
            kind=ROUND_SETUP if _flag(row[ui("setup_round")]) else "",
            docs=docs))
    item.rounds = out
    _grid_done(name, _round_rows(item))
    if unknown:
        notify.flag("?" + ",".join(dict.fromkeys(unknown)[:3]))
    off = [d for d in {d for r in out for d in r.docs} if d not in allowed]
    if off:
        notify.warn("docs_not_of_format", list=", ".join(sorted(off)),
                    fmt=draft.event(item.event).fmt)
    # the fasi a keirin or a velocità actually rides are decided on the day, not
    # here: saying so where the fasi are declared is the difference between a
    # programme and a promise
    if draft.event(item.event).fmt in ("keirin", "sprint"):
        st.caption(msg("rounds_decided_on_the_day"))
    _repropose(draft, item)


def _round_rows(item) -> list[dict]:
    """The fasi as the grid shows them - one builder, read twice."""
    return [{
        label("round"): r.key, ui("round_start"): r.start,
        label("distance"): r.distance,
        label("laps"): r.laps, label("sprint"): r.sprints,
        ui("qualify"): r.qualify, ui("eliminate"): r.eliminate,
        ui("setup_round"): r.kind == ROUND_SETUP,
        ui("documents"): ", ".join(r.docs or []),
    } for r in item.rounds]


def _repropose(draft: Competition, item) -> None:
    """Put the regulation back, and say where it is not what is written.

    Nothing records which values the jury typed: the proposal is recomputed and
    compared (`rounds.edited`), so the marker is right even after the file has
    been edited by hand. The button keeps the notes and the start times - the
    two things no regulation can propose.
    """
    opts = RD.options_of(draft, item.cat, item.event)
    changed = sorted({f for r in item.rounds
                      for f in RD.edited(draft, item.cat, item.event, r, opts)})
    c1, c2 = st.columns([1, 4], vertical_alignment="center")
    if c1.button(ui("repropose"), key=f"prog_re_{item.cat}_{item.event}_{item.day}",
                 help=help_text("repropose")):
        item.rounds = RD.apply(draft, item.cat, item.event, opts)
        notify.ok("race_reproposed", cat=item.cat,
                  event=draft.event(item.event).short, n=len(item.rounds))
        st.rerun()
    if changed:
        c2.caption(ui("edited_fields",
                      list=", ".join(label(f) for f in changed)))


def _add_race(draft: Competition, day: int) -> None:
    """Categoria, specialità, and the two or three questions the format asks.

    Adding a race used to give it one fase called *Finale* and leave the jury
    to type the rest. It now comes out whole: `core.rounds` reads the scheme
    off `formats.sprint`, the prove off `formats.omnium`, the distance off the
    regulation table and the giri off the track length, and what it proposes is
    editable in the grid below like anything else.
    """
    with st.expander(ui("add_race")):
        cats = draft.cat_order()
        events = [e for e in draft.event_order() if e != EVENT_ENTRY_LIST]
        if not cats or not events:
            notify.info("declare_cats_and_events")
            return
        c1, c2 = st.columns([1, 2])
        cat = c1.selectbox(ui("category"), cats, key=f"prog_addcat_{day}")
        event = c2.selectbox(ui("event"), events, key=f"prog_addev_{day}",
                             format_func=lambda e: draft.event(e).short)
        opts = _options_form(draft.event(event).fmt, f"add_{day}")

        if st.button(ui("add"), key=f"prog_add_{day}", type="primary"):
            if draft.scheduled(cat, event):
                notify.warn("race_already_scheduled", cat=cat,
                            event=draft.event(event).short)
                return
            item = P.add_item(draft, cat, event, day, [])
            item.rounds = RD.propose(draft, cat, event, opts)
            _remember_options(item, opts, draft.event(event).fmt)
            st.rerun()


def _options_form(fmt: str, key: str, opts: RD.Options | None = None
                  ) -> RD.Options:
    """The fields this format uses, and nothing else.

    `rounds.options_for` decides which appear, so a velocità is asked how many
    the 200 m qualifies and a madison is not asked anything about schemes.
    """
    wanted = RD.options_for(fmt)
    if not wanted:
        return opts or RD.Options()
    values = dataclasses.asdict(opts or RD.Options())
    st.caption(help_text("race_options"))
    cols = st.columns(len(wanted))
    for col, name in zip(cols, wanted):
        wid = f"prog_opt_{name}_{key}"
        if name == "scheme":
            schemes = list(S.SCHEMES)
            values[name] = col.selectbox(
                ui("option_scheme"), schemes, key=wid,
                index=schemes.index(values[name]) if values[name] in schemes else 0)
        elif name in ("final_5_8", "final_b"):
            values[name] = col.checkbox(ui(f"option_{name}"), key=wid,
                                        value=bool(values[name]))
        elif name == "per_start":
            # two at a time or one at a time, asked here because it differs by
            # categoria (`race.starts_per_race`)
            values[name] = 2 if col.radio(
                ui("option_per_start"),
                (ui("starts_pairs"), ui("starts_single")), key=wid,
                horizontal=True,
                help=help_text("starts_per_race")) == ui("starts_pairs") else 1
        else:
            values[name] = col.number_input(
                ui(f"option_{name}"), min_value=0, max_value=20, step=1,
                key=wid, value=int(values[name] or 0))
    return RD.Options(**values)


def _remember_options(item, opts: RD.Options, fmt: str) -> None:
    """Write onto the race what the format was asked, so ↩ can ask it again.

    Only what this format actually uses: a madison that recorded a velocità
    scheme would be a line of YAML saying nothing.
    """
    wanted = RD.options_for(fmt)
    if "scheme" in wanted:
        item.scheme = opts.scheme
    if "final_5_8" in wanted:
        item.final_5_8 = opts.final_5_8
    if "final_b" in wanted:
        item.final_b = opts.final_b
    if "per_start" in wanted:
        item.teams_per_start = opts.per_start or None


# ── the comunicati of one day ───────────────────────────────────────────────

def _communiques_of_day(draft: Competition, day: int) -> None:
    st.subheader(ui("communiques_of_day"))
    st.caption(ui("communiques_of_day_caption"))

    mine = [c for c in draft.communiques if c.day == day]
    others = [c for c in draft.communiques if c.day != day]
    _register_buttons(draft, day, mine, others)

    name = f"prog_reg_{day}"
    edited = _grid(
        name, P.rows_from_specs(mine) or [_blank_row(day)],
        num_rows="dynamic", hide_index=True, use_container_width=True,
        column_order=["n", "cat", "event", "round", "doc", "title", "ret"],
        column_config={
            "n": st.column_config.NumberColumn(
                label("register_col_n"), width="small",
                help=help_text("communique_number")),
            "day": None,
            "cat": st.column_config.SelectboxColumn(
                label("cat"), options=draft.cat_order(), width="small"),
            "event": st.column_config.SelectboxColumn(
                label("event"), options=list(draft.events), width="medium"),
            "round": st.column_config.TextColumn(label("round")),
            "doc": st.column_config.SelectboxColumn(
                label("document"), options=list(DOC_ALL_KINDS),
                help=help_text("communique_doc")),
            "title": st.column_config.TextColumn(ui("title"), width="large"),
            "ret": st.column_config.CheckboxColumn("RET", width="small",
                                                   help=help_text("ret")),
        })

    # An empty day is drawn with one blank row, so the grid has a shape to
    # edit; reading it back as a comunicato is what used to leave a `0` with no
    # categoria and no specialità in the register of every day nobody filled in.
    kept = [dict(row, day=day) for _i, row in edited.iterrows()
            if _text(row.get("doc")) and _text(row.get("event"))]
    draft.communiques = others + P.specs_from_rows(kept)
    _grid_done(name, P.rows_from_specs(
        [c for c in draft.communiques if c.day == day]) or [_blank_row(day)])


def _blank_row(day: int) -> dict:
    return {"n": 0, "day": day, "cat": "", "event": "", "round": "",
            "doc": "partenti", "title": "", "ret": False}


def _register_buttons(draft: Competition, day: int, mine: list,
                      others: list) -> None:
    c1, c2, c3 = st.columns([1, 1, 3], vertical_alignment="bottom")
    if c1.button(ui("propose_register"), key=f"prog_plan_{day}",
                 help=help_text("propose_register")):
        start = max([c.n for c in others if c.day < day] or [0]) + 1
        draft.communiques = others + P.plan_day(draft, day, start)
        st.rerun()
    if c2.button(ui("renumber_all"), key=f"prog_renum_{day}",
                 help=help_text("renumber_all")):
        every = sorted(draft.communiques, key=lambda c: (c.day, c.n))
        draft.communiques = P.renumber(every, start=1)
        st.rerun()
    if mine:
        c3.caption(ui("register_range", first=min(c.n for c in mine),
                      last=max(c.n for c in mine), n=len(mine)))


# ── reading a cell ──────────────────────────────────────────────────────────
#
# An empty cell of a `st.data_editor` is `NaN`, not None and not "". NaN is
# truthy and `int(NaN)` raises, so `int(cell or 0)` - the obvious thing to
# write - blows up the page on the first blank row. Every value read out of a
# grid on this page goes through one of these three.

def _num(value) -> float | None:
    """A number, or None where the cell is empty."""
    try:
        return None if value is None or pd.isna(value) else float(value)
    except (TypeError, ValueError):
        return None


def _int(value, default: int | None = None) -> int | None:
    n = _num(value)
    return default if n is None else int(n)


def _text(value) -> str:
    """A trimmed string, and "" where the cell is empty (never "nan")."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _flag(value) -> bool:
    return bool(value) and not pd.isna(value)
