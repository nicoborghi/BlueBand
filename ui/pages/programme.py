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

from dataclasses import replace

import pandas as pd
import streamlit as st

from core import communiques as C
from core import programme as P
from core.config import (DOC_ALL_KINDS, DOC_RESULTS, DOC_STARTLIST,
                         EVENT_ENTRY_LIST, ROUND_SETUP, Category, Competition,
                         Event, Round, load_competition)
from core.i18n import help_text, label, msg, ui
from core.store import Store
from ui import notify, state

DRAFT = "prog_draft"
DRAFT_OF = "prog_draft_of"

#: The formats a specialità can be run under - what `race.round_format` knows.
FORMATS = ("group", "elimination", "timed", "timed_team", "sprint", "keirin",
           "omnium", "madison", "time_trial", "entrylist")


def render(competition: str, comp: Competition, store: Store) -> None:
    draft = _draft(competition, comp)
    _toolbar(competition, draft, store)

    days = P.days_of(draft)
    tabs = st.tabs([ui("prog_tab_competition"), ui("prog_tab_events")]
                   + [_day_title(draft, d) for d in days])
    with tabs[0]:
        _competition_tab(draft)
    with tabs[1]:
        _events_tab(draft)
    for i, day in enumerate(days):
        with tabs[2 + i]:
            _day_tab(draft, day)


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


def _toolbar(competition: str, draft: Competition, store: Store) -> None:
    """Save, reload, and everything the programme is wrong about."""
    issues = P.issues(draft, C.load(store))
    errors = [i for i in issues if i.level == "error"]

    c1, c2, c3 = st.columns([1, 1, 3], vertical_alignment="bottom")
    if c1.button(ui("save_programme"), type="primary",
                 disabled=bool(errors), help=help_text("save_programme")):
        P.save(draft.path, draft, store=store)
        notify.ok("programme_saved", path=draft.path)
        # the other pages hold the programme through a cache keyed on the file:
        # dropping it here is what makes the save visible at once, rather than
        # at whatever moment something else happens to reread it
        state.refresh()
    if c2.button(ui("reload_programme"), help=help_text("reload_programme")):
        _reload(competition, draft)
        st.rerun()
    c3.caption(ui("programme_counts", events=len(draft.programme),
                  communiques=len(draft.communiques),
                  path=draft.path))

    if issues:
        with st.expander(ui("checks_summary", errors=len(errors),
                            warnings=len(issues) - len(errors)),
                         expanded=bool(errors)):
            notify.issues(issues)
    with st.expander(ui("yaml_preview")):
        st.code(P.dump(draft), language="yaml")


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
    draft.track_len = float(c3.number_input(
        ui("track_len"), 0.1, 1.0, float(draft.track_len or 0.3333),
        step=0.001, format="%.5f", key="prog_track",
        help=help_text("track_len")))

    st.caption(ui("dates_caption"))
    dates = st.text_input(ui("dates"), ", ".join(draft.dates), key="prog_dates",
                          help=help_text("dates"))
    draft.dates = [d.strip() for d in dates.split(",") if d.strip()]

    st.divider()
    _categories(draft)


def _categories(draft: Competition) -> None:
    st.subheader(ui("categories"))
    st.caption(ui("categories_caption"))
    rows = [{label("cat"): c.code, ui("competition_name"): c.name,
             label("sex"): c.sex, ui("order"): c.order}
            for c in sorted(draft.categories.values(),
                            key=lambda c: (c.order, c.code))]
    edited = st.data_editor(
        pd.DataFrame(rows or [{label("cat"): "", ui("competition_name"): "",
                               label("sex"): "", ui("order"): 1}]),
        num_rows="dynamic", hide_index=True, use_container_width=True,
        key="prog_cats",
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


# ── the events catalogue ────────────────────────────────────────────────────

def _events_tab(draft: Competition) -> None:
    st.subheader(ui("prog_tab_events"))
    st.caption(ui("events_caption"))
    rows = [{
        ui("code"): ev.code, ui("competition_name"): ev.name,
        ui("short_name"): ev.short, ui("abbr"): ev.abbr,
        ui("format"): ev.fmt, ui("team_size"): ev.team_size or None,
        ui("per_start"): ev.teams_per_start,
        ui("entry_columns"): ", ".join(ev.entry_columns),
        ui("order"): ev.order,
    } for ev in sorted(draft.events.values(), key=lambda e: (e.order, e.code))]
    edited = st.data_editor(
        pd.DataFrame(rows), num_rows="dynamic", hide_index=True,
        use_container_width=True, key="prog_events",
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
    _event_notes(draft)


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
    rows = [{
        label("round"): r.key, label("distance"): r.distance,
        label("laps"): r.laps, label("sprint"): r.sprints,
        ui("qualify"): r.qualify, ui("eliminate"): r.eliminate,
        ui("setup_round"): r.kind == ROUND_SETUP,
        ui("documents"): ", ".join(r.docs or []),
    } for r in item.rounds]
    edited = st.data_editor(
        pd.DataFrame(rows or [{label("round"): "", label("distance"): None,
                               label("laps"): None, label("sprint"): None,
                               ui("qualify"): None, ui("eliminate"): None,
                               ui("setup_round"): False,
                               ui("documents"): ", ".join(
                                   (DOC_STARTLIST, DOC_RESULTS))}]),
        num_rows="dynamic", hide_index=True, use_container_width=True,
        key=f"prog_rounds_{item.cat}_{item.event}_{item.day}",
        column_config={
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
            distance=_num(row[label("distance")]),
            laps=_num(row[label("laps")]),
            sprints=_int(row[label("sprint")]),
            qualify=_int(row[ui("qualify")]),
            eliminate=_int(row[ui("eliminate")]),
            kind=ROUND_SETUP if _flag(row[ui("setup_round")]) else "",
            docs=docs))
    item.rounds = out
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


def _add_race(draft: Competition, day: int) -> None:
    with st.expander(ui("add_race")):
        c1, c2, c3 = st.columns([1, 2, 1], vertical_alignment="bottom")
        cats = draft.cat_order()
        events = [e for e in draft.event_order() if e != EVENT_ENTRY_LIST]
        if not cats or not events:
            notify.info("declare_cats_and_events")
            return
        cat = c1.selectbox(ui("category"), cats, key=f"prog_addcat_{day}")
        event = c2.selectbox(ui("event"), events, key=f"prog_addev_{day}",
                             format_func=lambda e: draft.event(e).short)
        if c3.button(ui("add"), key=f"prog_add_{day}", type="primary"):
            if draft.scheduled(cat, event):
                notify.warn("race_already_scheduled", cat=cat,
                            event=draft.event(event).short)
                return
            P.add_item(draft, cat, event, day, [ui("round_default")])
            st.rerun()


# ── the comunicati of one day ───────────────────────────────────────────────

def _communiques_of_day(draft: Competition, day: int) -> None:
    st.subheader(ui("communiques_of_day"))
    st.caption(ui("communiques_of_day_caption"))

    mine = [c for c in draft.communiques if c.day == day]
    others = [c for c in draft.communiques if c.day != day]
    _register_buttons(draft, day, mine, others)

    rows = P.rows_from_specs(mine)
    edited = st.data_editor(
        pd.DataFrame(rows or [_blank_row(day)]), num_rows="dynamic",
        hide_index=True, use_container_width=True, key=f"prog_reg_{day}",
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

    kept = [dict(row, day=day) for _i, row in edited.iterrows()
            if _text(row.get("doc"))]
    draft.communiques = others + P.specs_from_rows(kept)


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
