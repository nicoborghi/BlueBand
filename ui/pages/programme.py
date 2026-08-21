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

**The categoria is the unit.** A championship is built by saying who is racing
and then, for each of them, which specialità - so the page asks that, in that
order, and ticking a specialità is what puts the race in the programme, whole,
with the fasi the regulation proposes. Under it sit the things that differ from
categoria to categoria: the schema of the velocità, which fasi are ridden at
all, and on which giornata.

**Specialità** is the other half of the same statement, and a tab of its own:
what a specialità *is* - sigla UCI, formato, atleti per squadra, the line every
ordine di partenza opens on. It comes from the catalogue with the UCI values in
it (`core.catalogue`) and holds for every categoria riding it, which is why it
is edited in one place and not once per categoria.

**The giornata is a scaletta of fasi**, not of races. One giornata at a time,
and inside it the fasi ridden that day - a table, in the order they go on the
track, numbered by typing the numbers into it - and then, in the order they go
out, the comunicati they produce. The order of that second list *is* the
numbering. Under the scaletta, one fase at a time: the numbers the regulation
proposed and the jury may correct.

A table and one fase at a time because a giornata is thirty fasi long: drawn as
thirty rows of widgets with the fields of a fase inside each, it was a thousand
widgets rebuilt to move one of them, and Streamlit rebuilds the page on every
gesture.

Fasi and not races, because a specialità is not an indivisible block: the
velocità that qualifies on the Saturday and rides its finali on the Sunday is
two fasi here and three there, and one race throughout (`config.Round.day`).
A fase on no giornata at all is a warning, in the checks and above the day it
would go on: that is the thing this page exists to stop anybody forgetting.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from core import catalogue as CAT
from core import communiques as C
from core import entries as E
from core import entry_book as EB
from core import entry_formats as EF
from core import notes as N
from core import programme as P
from core import recap as RC
from core import rounds as RD
from core.config import (DEFAULT_TRACK_LEN, DOC_CLASSIFICATION, DOC_RESULTS,
                         DOC_REPECHAGE_KINDS, DOC_STARTLIST,
                         EVENT_ENTRY_LIST, ROUND_SETUP,
                         Competition, laps_from_distance,
                         load_competition, madison_track_teams)
from core.formats import sprint as S
from core.i18n import help_text, label, msg, ui, word
from core.store import Store
from render import documents as D
from render.render import to_html
from ui import notify, savebar, state
from ui.download import save_button

DRAFT = "prog_draft"
DRAFT_OF = "prog_draft_of"

#: The giornata being edited, and the last one that was: the picker it is read
#: off can be clicked off, and the page under it still has to be about a day.
DAY = "prog_day"
DAY_LAST = "prog_day_last"

#: The freeze lives in the session as well as on the draft: it is a switch the
#: jury flicks while it works, and the draft is rebuilt from the file whenever
#: the competition changes. `FROZEN_SET` says the jury flicked it - until then
#: what the box shows is a safety default, and defaults are not written down.
FROZEN = "prog_frozen"
FROZEN_SET = "prog_frozen_set"


def _freeze_touched() -> None:
    st.session_state[FROZEN_SET] = True

#: A track is quoted in metres and stored in kilometres.
M_PER_KM = 1000

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

    # The giornate in the middle, and the four things that are not a giornata:
    # what the competition *is*, the categorie with what each one rides, what a
    # specialità is for everybody who rides it, and the sheet it all prints as.
    # In that order, because that is the order it is decided in - a categoria
    # exists before it has a specialità, a specialità is in the file because a
    # categoria rides it, and it is on a giornata only once somebody says which
    # fasi are ridden that day.
    #
    # One tab for all of them and the day picked inside it, not a tab each:
    # `st.tabs` draws the *body* of every tab on every rerun, so four giornate
    # of thirty fasi were four scalette built to move one of them.
    tabs = st.tabs([ui("prog_tab_competition"), ui("prog_tab_categories"),
                    ui("prog_tab_days"), ui("programme_print")])
    with tabs[0]:
        _competition_tab(draft)
    with tabs[1]:
        _categories_tab(draft)
    with tabs[2]:
        _days_tab(draft)
    with tabs[3]:
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


def _pick_sync(key: str, options: list[str], current: list[str]) -> None:
    """A multiselect that *does* follow the model - without fighting it.

    `_pick` is seeded once and then owns its value; that is right for a choice
    only the widget makes. The documenti of a fase are not one: ↩ Riproponi
    rewrites them, and a widget seeded once would go on showing the old list.
    The signature is what tells the two apart - the model changing under the
    widget reseeds it, the widget changing the model does not.
    """
    sig = _sig([{"v": current}])
    if st.session_state.get(f"{key}_model") != sig:
        st.session_state[f"{key}_model"] = sig
        st.session_state[key] = [c for c in current if c in options]
    st.session_state[key] = [c for c in st.session_state.get(key, [])
                             if c in options]


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
    """What the programme is wrong about - and nothing else above the tabs.

    One line at the top of the page: the checks, folded. What the programme
    counts goes under it, and the freeze of the numbering is a switch and not a
    reading, so it sits in the sidebar with Salva (`ui.savebar`) - the two
    things that act on the file as a whole.

    Returns the issues so the caller can grey out a Salva that would write a
    programme with a duplicate comunicato number in it.
    """
    issues = P.issues(draft, C.load(store))
    errors = [i for i in issues if i.level == "error"]

    if issues:
        with st.expander(ui("checks_summary", errors=len(errors),
                            warnings=len(issues) - len(errors)),
                         expanded=bool(errors)):
            notify.issues(issues)
    _numbering(draft, store)
    st.caption(ui("programme_counts", events=len(draft.programme),
                  communiques=len(draft.communiques), path=draft.path))
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

    It lives **in the sidebar**, next to Salva: it is a switch that holds for
    the whole file rather than something read off the page, and the page is a
    stack of tabs that would each have had to carry it.
    """
    if FROZEN not in st.session_state:
        st.session_state[FROZEN] = bool(draft.numbering_frozen
                                        or draft.communiques)
    frozen = st.sidebar.checkbox(ui("freeze_numbering"), key=FROZEN,
                                 on_change=_freeze_touched,
                                 help=help_text("freeze_numbering"))
    if st.session_state.get(FROZEN_SET):
        draft.numbering_frozen = frozen
    if frozen:
        st.sidebar.caption(msg("numbering_frozen"))
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
    st.sidebar.caption(msg("numbering_free", n=pinned))


# ── the programme, printed ──────────────────────────────────────────────────

def _print_programme(draft: Competition, store: Store) -> None:
    """The running order with the comunicato numbers beside it, as a sheet."""
    st.caption(help_text("programme_print"))
    c1, c2, c3 = st.columns(3)
    times = c1.checkbox(ui("programme_times"), value=True, key="prog_sheet_time")
    merge_round = c2.checkbox(ui("programme_merge_round"), key="prog_sheet_round")
    merge_results = c3.checkbox(ui("programme_merge_results"),
                                key="prog_sheet_res")
    # what this sheet carries is decided here and not in Programmazione: the
    # working table is always the whole table, and this is the one that is
    # printed and pinned up
    c1, c2 = st.columns(2)
    numbers = c1.checkbox(ui("show_communiques"), value=True,
                          key=SHOW_NUMBERS, help=help_text("show_communiques"))
    race = c2.checkbox(ui("show_race_line"), value=True, key=SHOW_RACE,
                       help=help_text("show_race_line"))
    c1, c2 = st.columns(2)
    font = c1.slider(ui("table_font"), 6, 14, 9, key="prog_sheet_font")
    landscape = c2.checkbox(ui("landscape"), key="prog_sheet_land",
                            help=help_text("landscape_short"))

    doc = D.programme_sheet(draft, times=times, merge_round=merge_round,
                            merge_results=merge_results, numbers=numbers,
                            race=race, font_size=font)
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
    _entry_list(draft)

    # last, and under no rule of its own: what the tabs are writing, as it will
    # be on disk. A collapsed expander between two dividers read as two rules
    # with nothing in between.
    with st.expander(ui("yaml_preview")):
        st.code(P.dump(draft), language="yaml")


# ── the elenco iscritti of this competition ─────────────────────────────────
#
# It is on this page and not in Impostazioni because it cannot be done before
# the programme: the workbook this competition is run from has a sheet per
# categoria and a column per specialità of that categoria, and neither exists
# until somebody has said which categorie ride and what each of them rides. It
# was a setting when it was only a *path*; now that the file is built here, it
# is a step of writing the programme, and it comes after the two tabs that say
# what the programme is.

def _entry_list(draft: Competition) -> None:
    """Build the elenco iscritti of this competition from the federal export.

    Three questions and no more: which shape the file that arrived is in, the
    file, and - only where the export does not number its riders - how the
    dorsali are to be dealt out. What comes out is written into the folder of
    the competition and is what everything downstream reads.
    """
    store = state.store(st.session_state.get(DRAFT_OF) or "")
    st.subheader(ui("entries"))
    st.caption(msg("entry_book_caption"))
    if not _programme_says_enough(draft):
        return

    _team(draft)
    book = _book_path(store, draft)
    if book.exists():
        _entry_book_ready(draft, store, book)
        return
    _entry_book_import(draft, store, book)


def _team(draft: Competition) -> None:
    """What a squadra is at this meeting, and what every sheet calls it.

    The programme's, and here: a *squadra* is the regione at a campionato
    italiano and the società at an open meeting, and that is a fact about the
    competition - not a preference of the machine it is run on, which is what
    it used to be filed as. It decides how the squadre and the coppie of every
    team event are composed, and the word printed at the head of that column.
    """
    sheet = draft.entry_sheet
    c1, c2 = st.columns(2)
    groups = list(RC.GROUPS)
    sheet.team_group = c1.selectbox(
        ui("team_group"), groups,
        index=groups.index(sheet.team_group) if sheet.team_group in groups
        else 0,
        key="prog_team_group", format_func=_group_name,
        help=help_text("team_group"))
    sheet.team_name = c2.text_input(ui("team_name"), value=sheet.team_name,
                                    key="prog_team_name",
                                    placeholder=word("team"),
                                    help=help_text("team_name"))
    st.caption(msg("team_caption", name=draft.team_name,
                   group=_group_name(sheet.team_group)))


#: What each grouping is called: the key is looked up when the widget is drawn,
#: so the page follows a change of language on the next rerun.
GROUP_LABELS = {RC.BY_REGION: "team_group_region", RC.BY_CLUB: "team_group_club",
                RC.BY_PROVINCE: "team_group_province",
                RC.BY_NATION: "team_group_nation"}


def _group_name(value: str) -> str:
    return ui(GROUP_LABELS[value]) if value in GROUP_LABELS else str(value)


def _programme_says_enough(draft: Competition) -> bool:
    """Whether there is a programme to build a workbook from.

    A categoria with no specialità is a sheet with no columns to tick, so both
    are asked for, and the page says which of the two is missing rather than
    offering a file picker that could only produce an empty file.
    """
    if not draft.cat_order():
        notify.info("entry_book_needs_categories")
        return False
    if not any(EB.events_of(draft, cat) for cat in draft.cat_order()):
        notify.info("entry_book_needs_events")
        return False
    return True


def _book_path(store: Store, draft: Competition):
    """Where the workbook lives: in the folder of the competition, named for it."""
    # `Iscritti_` is the federation's own file name and not a word this app
    # says: it is what the jury looks for in the folder (`core.entry_book`)
    stem = draft.race_id or draft.short or draft.name[:12] or "0"
    return store.root / f"{EB.PREFIX}{stem}.xlsx"


def _entry_book_import(draft: Competition, store: Store, book) -> None:
    """The first import: the file that arrived, and what to do about dorsali."""
    codes = EF.codes()
    fmt = state.sticky_select(
        st, ui("entry_format"), codes, key="prog_entry_fmt",
        saved=EF.default(), format_func=EF.name,
        help=help_text("entry_format"))
    upload = st.file_uploader(ui("entry_upload"), type=["xls", "xlsx"],
                              key="prog_entry_file",
                              help=help_text("entry_upload"))
    if upload is None:
        return

    comp = EF.applied(draft, fmt)
    el = _read_upload(upload, comp, fmt)
    if el is None or not el.riders:
        notify.error("entry_book_read_nothing")
        return
    st.caption(ui("entry_read", n=len(el.riders), cats=", ".join(
        f"{cat} {sum(1 for r in el.riders.values() if r.cat == cat)}"
        for cat in draft.cat_order()
        if any(r.cat == cat for r in el.riders.values()))))

    how = ""
    if not EB.has_bibs(el):
        missing = EB.missing_bibs(el)
        notify.warn("entry_no_bibs", n=len(missing),
                    list=", ".join(missing[:5]),
                    more=" …" if len(missing) > 5 else "")
        how = st.radio(ui("entry_numbering"), EB.NUMBERINGS,
                       format_func=lambda k: ui(f"entry_bibs_{k}"),
                       key="prog_entry_bibs",
                       help=help_text("entry_numbering"))
    if st.button(ui("entry_build"), type="primary", key="prog_entry_go"):
        if how:
            EB.numbered(el, comp, how)
        _write_book(draft, store, comp, el, book, fmt)


def _read_upload(upload, comp: Competition, fmt: str):
    """The uploaded file, read as that format says.

    Written to the competition folder first and read from there: every reader
    in `core.entries` takes a path - the file *is* the record of what was
    received, and a temporary copy thrown away would leave the workbook with
    nothing behind it.
    """
    source = Path(state.store(st.session_state[DRAFT_OF]).root) / upload.name
    source.write_bytes(upload.getbuffer())
    try:
        if EF.is_flat(fmt):
            return E.import_ksport_export(source, comp)
        return E.import_master(source, comp)
    except Exception as exc:                      # a file that is not one
        notify.text(str(exc))
        return None


def _write_book(draft: Competition, store: Store, comp: Competition,
                el, book, fmt: str) -> None:
    """Write the workbook, and remember what it was read with.

    The layout goes into the programme (`entries:`): the file is read again on
    every rerun and by every other page, and a mapping that lived only in this
    widget would make the next run of the app unable to read the workbook it
    has just written.
    """
    EB.build(el, comp, book)
    # and from now on the file in use is *ours*: the programme is left pointing
    # at the layout this app writes (`entry_formats.master`), header on the
    # first row, not at the one the arriving file happened to be in
    draft.entry_sheet = dataclasses.replace(
        EF.applied(draft, EF.MASTER).entry_sheet, source=book.name)
    E.set_source_path(store, str(book))
    E.save_import(store, el)
    notify.ok("entry_book_built", path=str(book), n=len(el.riders))
    state.refresh()


def _entry_book_ready(draft: Competition, store: Store, book) -> None:
    """The workbook is there: what it holds, and the one thing left to do to it.

    Which is to follow the programme. A categoria added or a specialità ticked
    changes the sheets and their columns, and everything anybody has written in
    it survives - it is read back into an entry list before it is written again
    (`entry_book.sync`).
    """
    st.caption(ui("entry_book_here", path=book.name))
    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    if c1.button(ui("entry_book_sync"), key="prog_entry_sync",
                 help=help_text("entry_book_sync")):
        EB.sync(book, EF.applied(draft, EF.default()))
        notify.ok("entry_book_synced", path=book.name)
        state.refresh()
    c2.caption(msg("entry_book_sync_caption"))


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


def _categories_tab(draft: Competition) -> None:
    """The categorie, and for each one what it rides.

    The unit of a programme is the categoria. A championship is built by saying
    who is racing and then, for each of them, which specialità - so that is what
    this tab asks, in that order. Ticking a specialità *is* putting it in the
    programme: the race is created with the fasi the regulation proposes
    (`core.rounds`), on no giornata yet. Which fasi are ridden on which day is
    the giornata's business, and it is asked there.

    There is no catalogue of specialità any more. What used to be a tab of seven
    fields per event is the catalogue file (`core.catalogue`) plus, under each
    specialità of each categoria, the handful of things a jury actually corrects.
    """
    st.subheader(ui("categories"))
    st.caption(ui("categories_caption"))
    st.caption(help_text("race_options"))
    _add_categories(draft)
    if not draft.categories:
        notify.info("no_categories_yet")
        return
    for code in draft.cat_order():
        _category_block(draft, code)
    st.divider()
    _matrix(draft)


def _add_categories(draft: Competition) -> None:
    """The categorie of the catalogue, ticked instead of typed - plus a sigla.

    Only ever *adds*: the sigla, the nome and the sesso come from the table
    (`core.catalogue`), the order is the end of the programme, and everything
    stays editable in the block the categoria then gets. Removing one is the ✕
    of that block, which is the place that knows what hangs off it.
    """
    missing = [c for c in CAT.category_codes() if c not in draft.categories]
    # trimmed before the widget is built, not after: an option that has just
    # been added is gone from `missing`, and a session still naming it raises
    st.session_state["prog_cats_add"] = [
        c for c in st.session_state.get("prog_cats_add", []) if c in missing]
    pick, code, add = st.columns([5, 2, 1], vertical_alignment="bottom")
    picked = pick.multiselect(ui("add_categories"), missing,
                              key="prog_cats_add", disabled=not missing,
                              format_func=CAT.category_name,
                              help=help_text("add_categories"))
    typed = _text(code.text_input(ui("add_category_code"), key="prog_cat_code",
                                  placeholder=ui("add_category_hint"),
                                  help=help_text("add_category_code"))).upper()
    wanted = picked + ([typed] if typed and typed not in draft.categories
                       else [])
    # in the button's callback and not after it: emptying the field the sigla
    # was typed in is writing to a widget's own state, and Streamlit allows
    # that only before the widget is drawn - a callback runs there
    add.button(ui("add"), key="prog_cats_add_go", disabled=not wanted,
               use_container_width=True, on_click=_do_add_categories,
               args=(draft, wanted))


def _do_add_categories(draft: Competition, wanted: list[str]) -> None:
    order = max([c.order for c in draft.categories.values()] or [0])
    for code in wanted:
        order += 1
        draft.categories[code] = CAT.category(code, order=order)
    st.session_state["prog_cat_code"] = ""
    st.session_state["prog_cats_add"] = []


def _category_block(draft: Competition, code: str) -> None:
    """One categoria: what it is called, and what it rides."""
    cat = draft.categories[code]
    order = draft.cat_order()
    index = order.index(code)
    with st.container(border=True):
        name, sex, up, down, kill = st.columns(
            [6, 2, 1, 1, 1], vertical_alignment="bottom")
        # the nome is not a label: it is what prints on every sheet of that
        # categoria, so it is edited in full sight rather than in a grid cell
        cat.name = name.text_input(f"**{code}** · {ui('competition_name')}",
                                   cat.name, key=f"prog_catname_{code}",
                                   help=help_text("category_name"))
        cat.sex = sex.selectbox(label("sex"), ("M", "F"),
                                index=1 if draft.female(code) else 0,
                                key=f"prog_catsex_{code}",
                                help=help_text("category_sex"))
        if up.button("↑", key=f"prog_catup_{code}", disabled=index == 0,
                     help=help_text("move_up")):
            _reorder_cats(draft, index, -1)
            st.rerun()
        if down.button("↓", key=f"prog_catdown_{code}",
                       disabled=index == len(order) - 1,
                       help=help_text("move_down")):
            _reorder_cats(draft, index, 1)
            st.rerun()
        if kill.button("✕", key=f"prog_catdel_{code}",
                       help=help_text("remove_category")):
            if _remove_category(draft, code):
                st.rerun()
        _events_of_category(draft, code)


def _reorder_cats(draft: Competition, index: int, delta: int) -> None:
    """Move a categoria up or down - the order everything else is printed in."""
    for n, code in enumerate(P.moved(draft.cat_order(), index, delta), start=1):
        draft.categories[code].order = n


def _remove_category(draft: Competition, code: str) -> bool:
    """Drop a categoria, unless something is riding under it.

    Same rule the specialità had: a categoria with races in the programme is not
    one to delete from under them, and the fix is to untick the specialità - one
    decision at a time, each visible where it is made.
    """
    if [i for i in draft.programme if i.cat == code]:
        notify.warn("category_in_programme", cat=code)
        return False
    draft.categories.pop(code, None)
    return True


# ── what a categoria rides ──────────────────────────────────────────────────

def _events_of_category(draft: Competition, cat: str) -> None:
    """Tick a specialità and the categoria rides it.

    The tick is the whole declaration. The `Event` comes from the catalogue if
    the programme has not got it yet, the race is created with the fasi the
    regulation proposes, and no fase is on a giornata until one is given to it.
    Unticking removes the race - which is why what it removes is said out loud.
    """
    known = CAT.codes() + [c for c in draft.events
                           if c not in CAT.codes() and c != EVENT_ENTRY_LIST]
    key = f"prog_evs_{cat}"
    _pick(key, known, [i.event for i in draft.programme if i.cat == cat])
    picked = st.multiselect(ui("events_of_category"), known, key=key,
                            format_func=_event_name(draft),
                            help=help_text("events_of_category"))

    for code in picked:
        if not draft.scheduled(cat, code):
            _declare(draft, cat, code)
    for item in [i for i in draft.programme if i.cat == cat
                 and i.event not in picked and i.event != EVENT_ENTRY_LIST]:
        draft.programme.remove(item)
        notify.warn("race_removed", cat=cat, n=len(item.rounds),
                    event=draft.event(item.event).short)
    _drop_unused_events(draft)

    for code in [c for c in draft.event_order() if c in picked]:
        _event_settings(draft, cat, code)


def _event_name(draft: Competition):
    """What a specialità is called: what the programme says, or the catalogue."""
    return lambda code: (draft.events[code].short if code in draft.events
                         else CAT.name(code, short=True))


def _declare(draft: Competition, cat: str, event: str) -> None:
    """Put a specialità in the programme of a categoria, whole.

    Day 0 on purpose: the race exists, its fasi are the ones the regulation
    proposes, and none of them is on a giornata - which is exactly what the
    checks then say out loud until somebody puts them on one.
    """
    if event not in draft.events:
        draft.events[event] = CAT.event(event, order=len(draft.events))
    item = P.add_item(draft, cat, event, 0)
    item.rounds = RD.propose(draft, cat, event)
    # and what every one of those fasi announces: the regulation says it, so
    # the race comes into the programme already saying it (`core.notes`)
    N.refresh_item(draft, item, force=True)


def _drop_unused_events(draft: Competition) -> None:
    """`events:` is derived from the ticks - except what the register names.

    Nobody declares a specialità any more: it is in the file because a categoria
    rides it. A file that came from somewhere else can still have a comunicato
    naming an event nothing is scheduled on, and dropping it would print that
    sheet under a bare code, so that one stays.
    """
    named = {s.event for c in draft.communiques for s in c.sheets}
    for code in [c for c in draft.events if c != EVENT_ENTRY_LIST
                 and not draft.scheduled_any(c) and c not in named]:
        del draft.events[code]


def _event_settings(draft: Competition, cat: str, code: str) -> None:
    """The specialità of one categoria: how *this* categoria rides it.

    Only what differs from categoria to categoria - the schema of the velocità,
    the 5°-8°, how many start together, which fasi are ridden and on which
    giornata. What a specialità *is* - sigla UCI, formato, atleti per squadra,
    the note every ordine di partenza opens on - is the same for everybody
    riding it and lives in the Specialità tab, edited once.
    """
    ev = draft.events[code]
    item = draft.scheduled(cat, code)
    if item is None:
        return
    with st.expander(f"{cat} · {ev.short}", expanded=False):
        was = RD.options_of(draft, cat, code)
        opts = _options_form(ev.fmt, f"{cat}_{code}", was)
        _remember_options(item, opts, was, ev.fmt)
        # an answer that changes *which fasi there are* changes them now: an
        # inseguimento set to «Finale diretta» that went on offering a
        # Qualificazioni would be a programme saying two things at once
        moved = [f for f in RD.SHAPE if f in RD.options_for(ev.fmt)
                 and getattr(opts, f) != getattr(was, f)]
        if moved:
            _apply_rounds(draft, item, opts)
            notify.saved("race_reproposed", cat=cat, event=ev.short,
                         n=len(_ridden(item)))
            st.rerun()
        _composition(draft, item, opts)
        _remember_numbers(draft, item, opts, was)
        _rounds_of_race(draft, item, opts)


def _rounds_of_race(draft: Competition, item, opts: RD.Options) -> None:
    """The fasi of a race: which ones are ridden, and on which giornata.

    Two answers, both of them the jury's. **Corsa**, because a proposal is not a
    rule: an omnium can be run without the scratch and start on the
    eliminazione, and a fase nobody rides has no business filing comunicati.
    Unticking one takes it out of the programme, and `↩ Riproponi` is the way
    back - it puts the whole regulation there again.

    **Giornata**, because a specialità is not an indivisible block: «—» is a
    real answer - the fase is in the programme and on no day - and two
    different days are a race split over two of them. The numbers of a fase -
    distanza, giri, sprint, documenti - are edited on the giornata it is
    ridden, where a jury is looking at them anyway.
    """
    days = P.days_of(draft)
    names = {0: ui("day_none")} | {d: ui("day_n", n=d) for d in days}
    back = {v: k for k, v in names.items()}
    name = f"prog_days_{item.cat}_{item.event}"
    st.caption(ui("rounds_of_race_caption"))
    ridden = _ridden(item)
    edited = _grid(
        name, _round_day_rows(draft, item, names), hide_index=True,
        use_container_width=True, disabled=[label("round")],
        column_config={
            label("round"): st.column_config.TextColumn(width="large"),
            ui("round_ridden"): st.column_config.CheckboxColumn(
                width="small", help=help_text("round_ridden")),
            ui("day"): st.column_config.SelectboxColumn(
                options=list(names.values()), width="small",
                help=help_text("round_day")),
        })
    kept = []
    for i, row in edited.iterrows():
        if i >= len(ridden):
            continue
        rnd = ridden[i]
        if not _flag(row[ui("round_ridden")]):
            continue            # not contested: out of the programme
        rnd.day = back.get(_text(row[ui("day")]), 0)
        kept.append(rnd)
    # every fase unticked at once is a race with nothing in it, which is not an
    # edit anybody means: untick the specialità itself for that
    dropped = len(ridden) - len(kept)
    if kept:
        # the composizione is not in the grid and must survive it, at the head
        # of the race where the regulation puts it
        item.rounds = [r for r in item.rounds if r.kind == ROUND_SETUP] + kept
    _normalise(item)
    rows = _round_day_rows(draft, item, names)
    if dropped and kept:
        # a row that has *gone* is the one case `_grid_done` cannot cover: the
        # frame the editor is holding still has it, and its diff would be
        # replayed onto the wrong row. A clean widget on a clean frame instead.
        _grid_reset(name, rows)
        st.rerun()
    _grid_done(name, rows)
    _repropose(draft, item, opts)


def _round_day_rows(draft: Competition, item, names: dict) -> list[dict]:
    """The fasi as the grid shows them - one builder, read twice."""
    return [{label("round"): r.label, ui("round_ridden"): True,
             ui("day"): names.get(draft.day_of(item, r), ui("day_none"))}
            for r in _ridden(item)]


def _ridden(item) -> list:
    """The fasi that are *ridden* - which is not all of them.

    The composizione (coppie of a madison, batterie of an omnium) is a
    `ROUND_SETUP` round: it is where the jury composes the event before it
    starts, nobody rides it and it files no comunicato. It has no business in a
    list of fasi or in the scaletta of a giornata - it is a job, and it is
    shown as one (`_composition`).
    """
    return [r for r in item.rounds if r.kind != ROUND_SETUP]


def _composition(draft: Competition, item, opts: RD.Options) -> None:
    """The composizione: the jury's own job, and not the programme's business.

    A madison is composed before it is ridden - every coppia numbered and put
    in its batteria - and an omnium with batterie di qualificazione is too.
    That is **not optional**: it is how the race is made to exist, and it is
    done in Gare, on the composition page. The programme only has to carry it,
    because that page reads it off the race (`race.is_composed`).

    So it is not a fase and it is not a tick either: it is ensured where the
    format has one, said in one line, and kept out of both the list of fasi and
    the scaletta of the giornata - nobody rides it and it files no comunicato.
    """
    key = RD.setup_key(draft.event(item.event).fmt, opts)
    if not key:
        return
    if not any(r.kind == ROUND_SETUP for r in item.rounds):
        item.rounds.insert(0, RD.propose_round(draft, item.cat, item.event,
                                               key, opts))
        N.refresh_item(draft, item, force=True)
    st.caption(ui("composition_round", name=key))



def _repropose(draft: Competition, item, opts: RD.Options) -> None:
    """Put the regulation back, and say where it is not what is written.

    Nothing records which values the jury typed: the proposal is recomputed and
    compared (`rounds.edited`), so the marker is right even after the file has
    been edited by hand. The button keeps the notes and the start times - the
    two things no regulation can propose - and re-proposes under the options
    *above it*, so changing the schema of a velocità and pressing ↩ is one
    gesture and not two.
    """
    changed = sorted({f for r in _ridden(item)
                      for f in RD.edited(draft, item.cat, item.event, r, opts)})
    c1, c2 = st.columns([1, 4], vertical_alignment="center")
    if c1.button(ui("repropose"), key=f"prog_re_{item.cat}_{item.event}",
                 help=help_text("repropose")):
        _apply_rounds(draft, item, opts)
        notify.saved("race_reproposed", cat=item.cat,
                     event=draft.event(item.event).short, n=len(_ridden(item)))
        st.rerun()
    if changed:
        c2.caption(ui("edited_fields",
                      list=", ".join(label(f) for f in changed)))


def _apply_rounds(draft: Competition, item, opts: RD.Options) -> None:
    """Re-propose the fasi under these options, keeping what is not theirs.

    The giornate above all: the regulation has no opinion about days, and a
    fase that survives a re-proposal is ridden when it was. A fase the new
    proposal *invents* - an inseguimento that becomes a finale diretta has one
    nothing was keyed under - goes on the day the race was already on.
    """
    placed = {r.key: (draft.day_of(item, r), r.seq) for r in item.rounds}
    day = item.day or min((d for d, _s in placed.values()), default=0)
    item.rounds = RD.apply(draft, item.cat, item.event, opts)
    for r in item.rounds:
        r.day, r.seq = placed.get(r.key, (day, 0))
    N.refresh_item(draft, item, force=True)
    _normalise(item)


def _normalise(item) -> None:
    """Say the giornate the shortest way that stays unambiguous.

    `Round.day` is 0 for "the day of the race", which is what every file written
    before the split existed says - and it is also what an *unassigned* fase
    would say, which would make the two indistinguishable. So: a race with a
    fase still to place has no day of its own (`item.day = 0`) and every placed
    fase carries its own; a race entirely placed takes the day of its first fase
    and the fasi ridden that day go back to saying nothing.

    The composizione is counted in none of it: nobody rides it, so it goes on
    no giornata and it must not be what keeps a race from being placed. It says
    nothing about days and takes the race's own.
    """
    ridden = _ridden(item)
    placed = [r.day for r in ridden if r.day]
    item.day = 0 if len(placed) != len(ridden) else min(placed or [0])
    for r in item.rounds:
        if r.kind == ROUND_SETUP or (item.day and r.day == item.day):
            r.day = 0


# ── categorie × specialità ──────────────────────────────────────────────────

def _matrix(draft: Competition) -> None:
    """Rows the categorie, columns the specialità - the whole programme at once.

    The one summary worth printing on this page: it answers what the jury asks
    the file - who rides what, in how many fasi, on which giornate - and it
    shows the hole (`— senza giornata`) rather than leaving it to be discovered
    on the morning.
    """
    st.subheader(ui("programme_matrix"))
    st.caption(ui("programme_matrix_caption"))
    codes = [c for c in draft.event_order() if c != EVENT_ENTRY_LIST]
    if not codes:
        notify.info("no_events_yet")
        return
    # the nome breve and not the sigla UCI: this is the summary somebody reads
    # to check the programme, and a row of SP KE IP TP MD has to be decoded
    # before it can be read. The narrow columns of the documents are where the
    # sigla earns its place, not here.
    heads = draft.event_headers(codes)
    rows = [{label("cat"): cat} | {heads[c]: _cell(draft, cat, c)
                                   for c in codes}
            for cat in draft.cat_order()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def _cell(draft: Competition, cat: str, event: str) -> str:
    """One box of the matrix: how many fasi, on which giornate, what is loose."""
    item = draft.scheduled(cat, event)
    if item is None:
        return ""
    placed = sorted({draft.day_of(item, r) for r in item.rounds
                     if draft.day_of(item, r)})
    loose = sum(1 for r in item.rounds if not draft.day_of(item, r))
    bits = [ui("n_rounds", n=len(item.rounds))]
    if placed:
        bits.append("-".join(ui("day_short", n=d) for d in placed))
    if loose:
        bits.append(ui("rounds_no_day", n=loose))
    return " · ".join(bits)



# ── one day ─────────────────────────────────────────────────────────────────

def _days_tab(draft: Competition) -> None:
    """The giornate, one at a time: which day, and then that day.

    The picker is a segmented control and not a tab strip because only the
    giornata being worked on is drawn - which is the whole point of it being
    here (`render`). Nothing is lost: the day a fase is on is stated on the
    fase (`config.Round.day`), and the matrice above says who rides when.
    """
    days = P.days_of(draft)
    if st.session_state.get(DAY) not in days:
        st.session_state[DAY] = days[0]
    # a segmented control can be clicked off; the giornata cannot - the page
    # below it has to be about one. The last pick is kept beside the widget
    # rather than written back into it, which Streamlit forbids once it is
    # drawn.
    day = st.segmented_control(
        ui("day"), days, key=DAY, label_visibility="collapsed",
        format_func=lambda d: _day_title(draft, d))
    if day is None:
        day = st.session_state.get(DAY_LAST, days[0])
    day = day if day in days else days[0]
    st.session_state[DAY_LAST] = day
    _day_tab(draft, day)


def _day_tab(draft: Competition, day: int) -> None:
    # which giornata this is, and its date, is what the pressed button says:
    # repeating it underneath was a line to scroll past on every rerun
    _rounds_of_day(draft, day)


def _rounds_of_day(draft: Competition, day: int) -> None:
    """The scaletta of the giornata: one row per fase, in the order it is ridden.

    Per fase and not per race, because that is what a giornata is: the
    qualificazioni of the velocità are ridden on the Saturday and its finali on
    the Sunday, and each of the two is a row on the day it belongs to. What is
    still on no day at all is said above, so a fase is never forgotten by being
    invisible.

    One grid and not a row of widgets per fase. The scaletta is a list of
    thirty short lines, and drawn as thirty expander with the fields of a fase
    inside each, it was thirty times a dozen widgets built on every rerun -
    Streamlit builds the body of a closed expander like any other - to move one
    fase up. It is a table, so it is edited as one (`_grid`), and what belongs
    to a single fase is asked below, for the one fase being edited.
    """
    st.subheader(ui("rounds_of_day"))
    st.caption(ui("rounds_of_day_caption"))
    _still_loose(draft)
    _register_buttons(draft, day)
    on = draft.rounds_on(day)
    if not on:
        notify.info("no_race_on_day", day=day)
    else:
        _scaletta(draft, day, on)
        _round_detail(draft, day, on)
    _add_rounds(draft, day)


def _still_loose(draft: Competition) -> None:
    """The fasi that are in the programme and on no giornata.

    The one thing this page is for forgetting: a race declared on a categoria,
    complete with its fasi, that nobody ever put on a day. It is a warning in
    the checks at the top of the page as well - here it is the working list,
    next to the button that places them.
    """
    loose = [f"{i.cat} {draft.event(i.event).short} · {r.label}"
             for i in draft.programme for r in _ridden(i)
             if not draft.day_of(i, r)]
    if loose:
        notify.warn("rounds_still_loose", n=len(loose),
                    list=", ".join(loose[:6]),
                    more=" …" if len(loose) > 6 else "")


def _round_title(draft: Competition, item, rnd) -> str:
    return f"{item.cat} · {draft.event(item.event).short} · {rnd.label}"


# ── the scaletta, which is also the register ────────────────────────────────
#
# One table and not two. The giornata used to be a list of fasi and, under it,
# a list of comunicati - the same fasi again, in the same order, with a number
# beside them - and keeping the two in step by reading down one and up the
# other is exactly the work a table is for. So the numbers are columns of the
# scaletta: the fase, and beside it the comunicato each of its sheets goes out
# under.
#
# What is *not* a fase of the day still exists - the elenchi iscritti of the
# morning, a comunicato of the giuria - and it has its own short list below,
# drawn only when there is one.

#: The documents a fase files that get a column of their own, in print order.
ROW_DOCS = (DOC_STARTLIST, DOC_RESULTS, DOC_CLASSIFICATION)

#: …and the column each of them is read in.
DOC_COLUMN = {DOC_STARTLIST: "com_start", DOC_RESULTS: "com_res",
              DOC_CLASSIFICATION: "com_class"}

#: Sidebar switches: the numbers, and what the race is made of. Both on, because
#: both are what the giornata is checked against - and off is for the jury that
#: is only moving fasi around.
SHOW_NUMBERS = "prog_show_numbers"
SHOW_RACE = "prog_show_race"


def _docs_of(rnd) -> list[str]:
    """The documents this fase files, default included.

    `Round.docs` is `None` for *the usual two*, which is what most of a
    programme says and what nothing should have to spell out. Reading the field
    raw is what made the multiselect of a fase come up empty and then write
    that emptiness back - a fase that files nothing, because somebody opened
    it.
    """
    if rnd.kind == ROUND_SETUP:
        return []
    if rnd.docs is None:
        return [DOC_STARTLIST, DOC_RESULTS]
    return list(rnd.docs)


def _spec_of(draft: Competition, item, rnd, doc):
    """The comunicato that publishes one document of one fase, if it is planned.

    The classifica of a specialità is filed under the specialità and not under
    a fase - it is the classifica of the whole velocità, not of its finali - so
    it is looked up the other way round when the fase itself does not carry it.
    """
    for spec in draft.communiques:
        if spec.carries(item.cat, item.event, rnd.key, doc):
            return spec
    if doc == DOC_CLASSIFICATION:
        for spec in draft.communiques:
            if any(s.cat == item.cat and s.event == item.event and s.doc == doc
                   for s in spec.sheets):
                return spec
    return None


def _race_line(draft: Competition, item, rnd) -> str:
    """`(8 km · 25 giri · 5 volate)` - what the fase is, where it is read.

    Derived and not read off the file: a fase states what it wants to state and
    the rest follows from the track (`config.Competition.distances`), which is
    the whole point of leaving a field empty. Only what a fase actually has: a
    keirin quotes its giri and no distance, and a bracket has neither.
    """
    km, laps, sprints = draft.distances(item.cat, item.event, rnd.key)
    bits = []
    if km:
        bits.append(ui("n_km", n=_number(km)))
    if laps:
        bits.append(ui("n_laps", n=_number(laps)))
    if sprints > 1:
        bits.append(ui("n_sprints", n=sprints))
    return f" ({' · '.join(bits)})" if bits else ""


def _number(value: float) -> str:
    """A number as a programme writes it: 8, 1.5, 0.2 - never 8.0."""
    return f"{value:g}"


def _day_rows(draft: Competition, on: list, *, numbers: bool,
              race: bool) -> list[dict]:
    """The giornata as a table: one row per fase, numbered from 1.

    The words that say *which* fase are read, not edited - editing them here
    would mean two places that rename a fase. What is editable is what the
    giornata decides: when it is ridden, under which comunicati it goes out,
    and whether it is ridden today at all.
    """
    rows = []
    for place, (item, rnd) in enumerate(on, start=1):
        row = {"n": place, "cat": item.cat,
               "event": draft.event(item.event).short
               + (_race_line(draft, item, rnd) if race else ""),
               "round": rnd.label, "start": rnd.start or "", "off": False}
        if numbers:
            filed = _docs_of(rnd)
            for doc in ROW_DOCS:
                spec = _spec_of(draft, item, rnd, doc) if doc in filed else None
                row[DOC_COLUMN[doc]] = spec.n if spec else None
        rows.append(row)
    return rows


def _scaletta(draft: Competition, day: int, on: list) -> None:
    """The running order, edited as the table it is.

    The number is typed and the scaletta closes ranks around it, renumbered
    from 1 (`programme.reordered`) - and *several* numbers can be typed before
    anything is committed, which is the difference that matters: a giornata is
    reshuffled in one gesture instead of one rerun per fase moved.

    The orario is in the table and not below it because it is read down the
    column - a scaletta is a list of times as much as of fasi - and *Togli* is
    a box for the same reason the numbers are typed: it is applied with
    everything else, so clearing a giornata is one gesture too.
    """
    # the whole table, always: the giornata is what is *checked* here - the
    # register follows the running order, and a distance that does not match
    # the giri is a mistake nobody finds by opening thirty fasi. What is shown
    # on the printed foglio programma is that sheet's business, and is chosen
    # there.
    rows = _day_rows(draft, on, numbers=True, race=True)
    order = ["n", "com_start", "cat", "event", "round", "com_res", "com_class",
             "start", "off"]
    config = {
        "n": st.column_config.NumberColumn(
            ui("running_order"), width="small", min_value=1, max_value=99,
            step=1, required=True, help=help_text("running_order")),
        "cat": st.column_config.TextColumn(label("cat"), width="small",
                                           disabled=True),
        "event": st.column_config.TextColumn(label("event"),
                                             width="medium", disabled=True),
        "round": st.column_config.TextColumn(label("round"), disabled=True),
        "start": st.column_config.TextColumn(
            ui("round_start_optional"), width="small",
            help=help_text("round_start")),
        "off": st.column_config.CheckboxColumn(
            ui("off_day"), width="small", help=help_text("remove_from_day")),
    }
    for doc, name in DOC_COLUMN.items():
        config[name] = st.column_config.NumberColumn(
            ui(f"com_{doc}"), width="small", min_value=0, max_value=999, step=1,
            help=help_text("communique_in_scaletta"))
    edited = _grid(
        f"prog_day_{day}", rows, num_rows="fixed", hide_index=True,
        use_container_width=True, column_order=order, column_config=config)
    if _apply_scaletta(draft, on, rows, edited):
        # the model has moved, so the frame the grid was handed is stale: the
        # next run builds it again from the scaletta as it now is, which is
        # what `_grid` resets on (`_sig`)
        st.rerun()


def _apply_scaletta(draft: Competition, on: list, rows: list[dict],
                    edited) -> bool:
    """Write the edited table back onto the fasi. True if anything moved.

    In this order, and it matters: a fase taken off the giornata is out of the
    running order, so it is removed *first* and the numbers are dealt over what
    is left. Numbering only what stays is the difference between a scaletta of
    1..N and one with a hole where the jury has just removed something.

    A table nobody touched writes nothing at all - and that is not an
    optimisation. The numbers shown are 1..N whether or not the file states
    them (`config.rounds_on` falls back to the order the programme is in), so
    dealing them out unasked would put a `seq:` on every fase of a programme
    merely opened and saved.
    """
    typed = [(_int(row.get("n"), rows[i]["n"]), _text(row.get("start")),
              _flag(row.get("off")))
             for i, (_x, row) in enumerate(edited.iterrows())]
    numbers = _numbers_typed(on, rows, edited)
    if (typed == [(r["n"], r["start"], False) for r in rows]
            and not numbers):
        return False
    changed = _renumber_sheets(draft, numbers)
    for (_item, rnd), (_n, start, _off), was in zip(on, typed, rows):
        if start != was["start"]:
            rnd.start = start
            changed = True
    stay = [i for i, (_n, _s, off) in enumerate(typed) if not off]
    for i in [i for i in range(len(on)) if i not in stay]:
        _off_day(draft, *on[i])
        changed = True
    # only when a number was actually retyped: a fase taken off the day leaves
    # the ones under it a place higher, and dealing the numbers out over that
    # alone would write a `seq:` on every fase of the giornata to say what the
    # order of the programme already says
    if any(typed[i][0] != rows[i]["n"] for i in stay):
        changed = _reseq([on[i] for i in stay], [typed[i][0] for i in stay],
                         [rows[i]["n"] for i in stay]) or changed
    return changed


def _numbers_typed(on: list, rows: list[dict], edited) -> list[tuple]:
    """The comunicato numbers of the table that are not what they were.

    `(item, round, document, number)`, and a number of 0 - a cleared cell - is
    the jury taking that sheet out of the register, which is a decision like
    any other.
    """
    out = []
    for i, (_x, row) in enumerate(edited.iterrows()):
        if i >= len(rows):
            break
        for doc, name in DOC_COLUMN.items():
            if name not in rows[i]:
                continue
            was = rows[i][name]
            now = _int(row.get(name), 0) or 0
            if now != (was or 0):
                out.append((on[i][0], on[i][1], doc, now))
    return out


def _renumber_sheets(draft: Competition, typed: list[tuple]) -> bool:
    """Move the documents whose number the jury retyped.

    Through the flat form of the register (`programme.rows_from_specs`), which
    is where *two documents on one comunicato* is expressible at all: a sheet
    given a number another one already has ends up next to it, and the two are
    read back as one comunicato with two documents on it.
    """
    if not typed:
        return False
    rows = P.rows_from_specs(draft.communiques)
    for item, rnd, doc, n in typed:
        spec = _spec_of(draft, item, rnd, doc)
        # the classifica is filed under the specialità and may name no fase:
        # moving it must not invent one, or the register would carry two
        sheet = next((s for s in (spec.sheets if spec else [])
                      if s.cat == item.cat and s.event == item.event
                      and s.doc == doc), None)
        rows = P.numbered(rows, {
            "day": draft.day_of(item, rnd), "cat": item.cat,
            "event": item.event,
            "round": sheet.round_key if sheet else (
                "" if doc == DOC_CLASSIFICATION else rnd.key),
            "doc": doc, "title": "", "ret": False}, n)
    draft.communiques = P.specs_from_rows(rows)
    return True


def _reseq(on: list, want: list[int], was: list[int]) -> bool:
    """Deal the numbers 1..N over the fasi, in the order asked for.

    The order is `programme.reordered`, which is where that rule is written and
    where it is tested; here it is only written onto the fasi.
    """
    moved = False
    for place, i in enumerate(P.reordered(want, was), start=1):
        rnd = on[i][1]
        if rnd.seq != place:
            rnd.seq = place
            moved = True
    return moved


def _round_detail(draft: Competition, day: int, on: list) -> None:
    """The fields of one fase of the giornata - the one being edited.

    One at a time, and picked rather than unfolded: the fields are a dozen
    widgets and the scaletta is thirty fasi long. The pick is held by name and
    not by place, so renumbering the giornata does not move it onto another
    fase (`ui.state.sticky_select`).
    """
    keys = [f"{item.cat}|{item.event}|{rnd.key}" for item, rnd in on]
    of = dict(zip(keys, on))
    place = {k: i for i, k in enumerate(keys, start=1)}
    pick = state.sticky_select(
        st, ui("round_to_edit"), keys, key=f"prog_pick_{day}",
        # numbered as the table above numbers it: the N. of the scaletta is how
        # a fase is found when the jury is looking at the giornata and not at a
        # list of names. The pick is still held by name, so renumbering the day
        # does not move it onto another fase.
        format_func=lambda k: f"{place[k]}. {_round_title(draft, *of[k])}",
        help=help_text("round_to_edit"))
    with st.container(border=True):
        _round_fields(draft, *of[pick])
        _sheets_of_round(draft, day, *of[pick])



def _sheets_of_round(draft: Competition, day: int, item, rnd) -> None:
    """The comunicati of this fase: which number each of its sheets goes out on.

    The same numbers as the columns of the table above - this is the other way
    of typing them, one fase at a time, with room to say what the table cannot:
    that two of them **print on one comunicato**. Which is what a velocità does
    every round - the risultati of the batterie and the ordine di partenza dei
    recuperi are one sheet - and what the register expresses by giving them one
    number (`programme.specs_from_rows`).
    """
    filed = _docs_of(rnd)
    if not filed:
        return
    st.caption(f"**{ui('communiques_of_round')}**")
    cols = st.columns(len(filed))
    typed = []
    key = f"{item.cat}_{item.event}_{rnd.key}"
    for col, doc in zip(cols, filed):
        spec = _spec_of(draft, item, rnd, doc)
        was = spec.n if spec else 0
        now = _int(col.number_input(
            label(doc), min_value=0, max_value=999, step=1, value=int(was),
            key=f"prog_com_{doc}_{key}",
            help=help_text("communique_in_scaletta")), 0)
        if now != was:
            typed.append((item, rnd, doc, now))
    # no button to merge two of them: writing the same number twice *is* the
    # merge, and the register reads it that way (`programme.specs_from_rows`)
    if typed:
        _renumber_sheets(draft, typed)
        st.rerun()


def _expand(draft: Competition, item) -> None:
    """Write the giornata onto every fase, so one of them can then change.

    `Round.day` is 0 for "the day of the race": editing one fase of a race that
    says its day once would move all of them. Expanding first and normalising
    afterwards (`_normalise`) keeps the file short without making the edit lie.
    """
    for r in item.rounds:
        r.day = draft.day_of(item, r)
    item.day = 0


def _off_day(draft: Competition, item, rnd) -> None:
    """Take a fase off the giornata. It stays in the programme, on no day."""
    _expand(draft, item)
    rnd.day = 0
    _normalise(item)


def _round_fields(draft: Competition, item, rnd) -> None:
    """What the regulation proposed and the jury may correct.

    The fields of one fase, where they are read: on the giornata it is ridden.
    Empty is a real value on the numbers - it means "whatever follows from the
    track and the regulation" (`config.Competition.distances`), and writing the
    derived value back would freeze it on a track of another length.
    """
    key = f"{item.cat}_{item.event}_{rnd.key}"
    said = N.for_round(draft, item, rnd)
    c1, c2, c3 = st.columns(3)
    # the orario is optional and says so in the field: a programme is often
    # written before anybody knows at what time anything is ridden
    rnd.start = c1.text_input(ui("round_start_optional"), rnd.start,
                              key=f"prog_start_{key}",
                              placeholder=ui("round_start_hint"),
                              help=help_text("round_start"))
    # a number read out of the file can be an int (`distance: 3`) where the
    # widget counts in halves: same type or Streamlit refuses the pair
    rnd.distance = _num(c2.number_input(
        label("distance"), min_value=0.0, value=_num(rnd.distance), step=0.5,
        key=f"prog_dist_{key}", help=help_text("round_distance")))
    rnd.laps = _num(c3.number_input(
        label("laps"), min_value=0.0, value=_num(rnd.laps), step=0.5,
        key=f"prog_laps_{key}", help=help_text("round_laps")))

    c1, c2, c3 = st.columns(3)
    rnd.sprints = _int(c1.number_input(
        label("sprint"), min_value=0, value=_int(rnd.sprints), step=1,
        key=f"prog_spr_{key}"))
    rnd.qualify = _int(c2.number_input(
        ui("qualify"), min_value=0, value=_int(rnd.qualify), step=1,
        key=f"prog_qual_{key}", help=help_text("round_qualify")))
    rnd.eliminate = _int(c3.number_input(
        ui("eliminate"), min_value=0, value=_int(rnd.eliminate), step=1,
        key=f"prog_elim_{key}", help=help_text("round_eliminate")))

    _distance_check(draft, item, rnd)

    # the lines the sheets open on are about those numbers, so they follow
    # them - and stop following once the jury has written its own (`core.notes`)
    if said != N.for_round(draft, item, rnd):
        N.refresh(draft, item, rnd, before=said)

    allowed = P.docs_available(draft, item.event)
    pick = f"prog_docs_{key}"
    # the documents a fase files by default, and not an empty box: seeded from
    # the raw field, a fase that says nothing (`Round.docs = None`, the usual
    # two) came up with none ticked and wrote that back the moment it was
    # opened - a fase that files nothing because somebody looked at it
    _pick_sync(pick, allowed, _docs_of(rnd))
    rnd.docs = list(st.multiselect(
        ui("documents"), allowed, key=pick,
        help=help_text("round_docs") + " " + ", ".join(allowed)))
    setup = st.checkbox(ui("setup_round"), value=rnd.kind == ROUND_SETUP,
                        key=f"prog_setup_{key}", help=help_text("round_setup"))
    rnd.kind = ROUND_SETUP if setup else ""

    # Two notes, and the difference between them is which one the teams read.
    # One is printed - it opens the `Decisione / note` of this fase's ordine di
    # partenza, above what the specialità says on every one of them; the other
    # never leaves the file. They used to be one field, and the jury had to
    # guess which it was.
    c1, c2 = st.columns(2)
    rnd.sheet_note = c1.text_input(
        ui("round_sheet_note"), rnd.sheet_note, key=f"prog_snote_{key}",
        placeholder=ui("round_sheet_note_hint"),
        help=help_text("round_sheet_note"))
    rnd.results_note = c2.text_input(
        ui("round_results_note"), rnd.results_note, key=f"prog_rsnote_{key}",
        placeholder=ui("round_results_note_hint"),
        help=help_text("round_results_note"))
    rnd.note = st.text_input(ui("round_note"), rnd.note,
                             key=f"prog_rnote_{key}",
                             placeholder=ui("round_note_hint"),
                             help=help_text("round_note"))

    # the fasi a keirin or a velocità actually rides are decided on the day, not
    # here: saying so where the fasi are declared is the difference between a
    # programme and a promise
    if draft.event(item.event).fmt in ("keirin", "sprint"):
        st.caption(msg("rounds_decided_on_the_day"))
    changed = sorted(RD.edited(draft, item.cat, item.event, rnd,
                               RD.options_of(draft, item.cat, item.event)))
    if changed:
        st.caption(ui("edited_fields",
                      list=", ".join(label(f) for f in changed)))


def _distance_check(draft: Competition, item, rnd) -> None:
    """Whether the distance and the giri agree, on this track.

    Both are stated on a fase and either may be left empty, so they can
    disagree - 3 km written next to 10 giri on a 333 m track is a sheet that
    contradicts itself, and it is found by reading the two numbers against the
    lunghezza della pista in Gara. Half a giro of tolerance: a pursuit is
    ridden to half-lap resolution and a nominal 333.33 never divides exactly.

    A fase that says only one of them is not wrong: the other is derived
    (`config.Competition.distances`) and the line below says what it comes to.
    """
    if not draft.track_len:
        return
    fmt = draft.event(item.event).fmt
    km, laps, _sprints = draft.distances(item.cat, item.event, rnd.key)
    if not km or not laps:
        return
    exact = laps_from_distance(km, draft.track_len, fmt)
    metres = int(round(draft.track_len * 1000))
    if abs(laps - exact) > 0.5:
        notify.warn("laps_do_not_match", km=_number(km), laps=_number(laps),
                    track=metres, expected=_number(exact))
    elif rnd.distance is None or rnd.laps is None:
        st.caption(ui("laps_derived", km=_number(km), laps=_number(laps),
                      track=metres))


def _add_rounds(draft: Competition, day: int) -> None:
    """Put fasi on this giornata - some of a race, or all of it.

    Some of it is the point: a specialità is not an indivisible block, and the
    velocità that qualifies on the Saturday and rides its finali on the Sunday
    is written by adding two of its fasi here and two there.
    """
    with st.expander(ui("add_rounds")):
        cats = [c for c in draft.cat_order()
                if [i for i in draft.programme if i.cat == c]]
        if not cats:
            notify.info("declare_cats_and_events")
            return
        c1, c2 = st.columns([1, 2])
        cat = c1.selectbox(ui("category"), cats, key=f"prog_addcat_{day}")
        events = [i.event for i in draft.programme
                  if i.cat == cat and i.event != EVENT_ENTRY_LIST]
        event = c2.selectbox(ui("event"), events, key=f"prog_addev_{day}",
                             format_func=lambda e: draft.event(e).short)
        item = draft.scheduled(cat, event)
        if item is None:
            return
        free = [r.key for r in _ridden(item)
                if draft.day_of(item, r) != day]
        if not free:
            st.caption(msg("all_rounds_on_day", cat=cat,
                           event=draft.event(event).short, day=day))
            return
        key = f"prog_addrnd_{day}_{cat}_{event}"
        _pick(key, free, free)
        keys = st.multiselect(ui("rounds_to_add"), free, key=key,
                              help=help_text("rounds_to_add"))
        if st.button(ui("add"), key=f"prog_add_{day}", type="primary",
                     disabled=not keys):
            _expand(draft, item)
            for r in item.rounds:
                if r.key in keys:
                    r.day = day
            _normalise(item)
            st.rerun()


def _options_form(fmt: str, key: str, opts: RD.Options | None = None
                  ) -> RD.Options:
    """The fields this format uses, and nothing else.

    `rounds.options_for` decides which appear, so a velocità is asked how many
    the 200 m qualifies and a madison is not asked anything about schemes.

    What this form *is* is said once, above the categorie - not in every box:
    the same three lines under thirty specialità is noise, and noise is what
    stops a jury reading the one line that matters.
    """
    wanted = list(RD.options_for(fmt))
    if not wanted:
        return opts or RD.Options()
    values = dataclasses.asdict(opts or RD.Options())
    if "direct_final" in wanted:
        # its own line, above: it is not one more number - it decides how many
        # fasi there are at all, and the questions under it follow from it
        wanted.remove("direct_final")
        choices = (ui("timed_with_finals"), ui("timed_direct"))
        values["direct_final"] = st.radio(
            ui("option_direct_final"), choices, horizontal=True,
            index=1 if values["direct_final"] else 0,
            key=f"prog_opt_direct_final_{key}",
            help=help_text("option_direct_final")) == choices[1]
        if values["direct_final"]:
            # nothing qualifies for anything: there is one fase
            wanted = [w for w in wanted if w != "qualify"]
    if not wanted:
        return RD.Options(**values)
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
                horizontal=True, index=1 if values[name] == 1 else 0,
                help=help_text("starts_per_race")) == ui("starts_pairs") else 1
        else:
            values[name] = col.number_input(
                ui(f"option_{name}"), min_value=0, max_value=20, step=1,
                key=wid, value=int(values[name] or 0))
    return RD.Options(**values)


def _remember_options(item, opts: RD.Options, was: RD.Options, fmt: str) -> None:
    """Write onto the race what the jury changed, and only that.

    Only what this format actually uses: a madison that recorded a velocità
    scheme would be a line of YAML saying nothing. And only what *moved*: the
    form is drawn on every race of every categoria now, seeded with what the
    programme already says (`rounds.options_of`), so writing it back unasked
    would turn "not stated" into a statement on every file this page opens -
    `final_5_8: false` where the file was silent, and a diff on a Salva that
    changed nothing. `None` still means "not stated" (`config.ProgrammeItem`).
    """
    wanted = RD.options_for(fmt)
    if "scheme" in wanted and opts.scheme != was.scheme:
        item.scheme = opts.scheme
    if "final_5_8" in wanted and opts.final_5_8 != was.final_5_8:
        item.final_5_8 = opts.final_5_8
    if "final_b" in wanted and opts.final_b != was.final_b:
        item.final_b = opts.final_b
    # 2 is what a race that says nothing rides: the choice is only written when
    # it is the other one, or when it goes back to being the usual one
    if "per_start" in wanted and opts.per_start != (was.per_start or 2):
        item.teams_per_start = opts.per_start or None


def _remember_numbers(draft: Competition, item, opts: RD.Options,
                      was: RD.Options) -> None:
    """The two numbers of the form that live on a fase, written where they live.

    *Coppie eliminate* is stated on the composizione and *quanti si qualificano*
    on the qualificazione - they are fields of a fase, not of the race - so the
    form has to put them back there. Until it did, typing either of them moved
    the widget and nothing else: the value came back off the programme on the
    next run and was gone at Salva.

    And what they are about is what the sheets announce, so the lines follow
    them (`core.notes`) - unless the jury has written its own.
    """
    fmt = draft.event(item.event).fmt
    wanted = RD.options_for(fmt)
    before = N.resolved(draft, item)
    moved = False
    if "eliminate" in wanted and opts.eliminate != was.eliminate:
        setup = next((r for r in item.rounds if r.kind == ROUND_SETUP), None)
        if setup is not None:
            setup.eliminate = opts.eliminate or None
            moved = True
    if "qualify" in wanted and opts.qualify != was.qualify:
        qual = next((r for r in item.rounds if r.key == RD.QUALIFYING), None)
        if qual is not None:
            qual.qualify = opts.qualify or None
            moved = True
    if moved:
        N.refresh_item(draft, item, before=before)


def _register_buttons(draft: Competition, day: int) -> None:
    """The two things nobody wants to do by hand, and the range of the day.

    A championship is a hundred and forty comunicati over thirty fasi: which
    sheets a fase files and what number each of them goes out under are decided
    by the same rules every time, so they are proposed - each behind a dialog,
    because both rewrite the whole giornata and neither should happen on a
    stray click.
    """
    mine = [c for c in draft.communiques if c.day == day]
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2], vertical_alignment="bottom")
    if c1.button(ui("assign_docs"), key=f"prog_docs_go_{day}", type="primary",
                 help=help_text("assign_docs")):
        _assign_docs_dialog(draft)
    if c2.button(ui("propose_register"), key=f"prog_plan_{day}",
                 help=help_text("propose_register")):
        _propose_register_dialog(draft, day)
    if c3.button(ui("renumber_all"), key=f"prog_renum_{day}",
                 help=help_text("renumber_all")):
        every = sorted(draft.communiques, key=lambda c: (c.day, c.n))
        draft.communiques = P.renumber(every, start=1)
        st.rerun()
    if mine:
        c4.caption(ui("register_range", first=min(c.n for c in mine),
                      last=max(c.n for c in mine), n=len(mine)))


def _assign_docs_dialog(draft: Competition) -> None:
    """Which sheets every fase of the programme files, decided in one go.

    The regulation already knows: a fase files an ordine di partenza and its
    risultati, the one that closes a specialità files the classifica too, and a
    velocità and a keirin file the sheets of their recuperi
    (`rounds.docs_for`). What is asked here is the little the regulation leaves
    open - and then it is written onto every fase of the programme, which is
    the point: nobody wants to tick four boxes thirty times.
    """
    # the decorator is applied here and not on the function: its title is a
    # word of the catalogue, and the language is only known once a competition
    # has been read (`core.i18n`)
    st.dialog(ui("assign_docs"))(_assign_docs_body)(draft)


def _assign_docs_body(draft: Competition) -> None:
    st.caption(msg("assign_docs_caption"))
    classification = st.checkbox(ui("docs_classification"), value=True,
                                 key="prog_docs_class",
                                 help=help_text("docs_classification"))
    repechages = st.checkbox(ui("docs_repechages"), value=True,
                             key="prog_docs_rep",
                             help=help_text("docs_repechages"))
    keep = st.checkbox(ui("docs_keep_edited"), value=False,
                       key="prog_docs_keep", help=help_text("docs_keep_edited"))
    if st.button(ui("assign_docs_go"), type="primary", key="prog_docs_apply"):
        n = _assign_docs(draft, classification=classification,
                         repechages=repechages, keep=keep)
        notify.saved("docs_assigned", n=n)
        st.rerun()


def _assign_docs(draft: Competition, *, classification: bool,
                 repechages: bool, keep: bool) -> int:
    """Write the proposed documents onto every fase. Returns how many moved."""
    moved = 0
    for item in draft.programme:
        if item.event == EVENT_ENTRY_LIST:
            continue
        opts = RD.options_of(draft, item.cat, item.event)
        for rnd in item.rounds:
            want = ([] if rnd.kind == ROUND_SETUP
                    else list(RD.docs_for(draft, item.cat, item.event,
                                          rnd.key, opts) or []))
            if not classification:
                want = [d for d in want if d != DOC_CLASSIFICATION]
            if not repechages:
                want = [d for d in want if d not in DOC_REPECHAGE_KINDS]
            if keep and rnd.docs is not None and list(rnd.docs) != want:
                continue        # the jury said otherwise, and it stands
            if list(rnd.docs or []) != want:
                rnd.docs = want
                moved += 1
    return moved


def _propose_register_dialog(draft: Competition, day: int) -> None:
    """The numbers of one giornata, proposed in the order things go out.

    The order is `programme.plan_day` and the questions here are the ones a
    jury actually answers: whether the elenchi iscritti open the day, how many
    ordini di partenza go out before anything is ridden, and whether the
    classifica of a specialità goes out with the fase that closes it.
    """
    st.dialog(ui("propose_register"))(_propose_register_body)(draft, day)


def _propose_register_body(draft: Competition, day: int) -> None:
    st.caption(msg("propose_register_caption", day=day))
    lists = st.checkbox(ui("register_entry_lists"), value=True,
                        key=f"prog_reg_lists_{day}",
                        help=help_text("register_entry_lists"))
    ahead = st.number_input(ui("register_ahead"), min_value=0, max_value=40,
                            value=5, step=1, key=f"prog_reg_ahead_{day}",
                            help=help_text("register_ahead"))
    classification = st.checkbox(ui("register_classification"), value=True,
                                 key=f"prog_reg_class_{day}",
                                 help=help_text("register_classification"))
    follow = st.checkbox(ui("register_follow"), value=True,
                         key=f"prog_reg_follow_{day}",
                         help=help_text("register_follow"))
    if st.button(ui("propose_register_go"), type="primary",
                 key=f"prog_reg_apply_{day}"):
        others = [c for c in draft.communiques if c.day != day]
        before = [c for c in others if c.day < day]
        after = sorted([c for c in others if c.day > day],
                       key=lambda c: (c.day, c.n))
        start = max([c.n for c in before] or [0]) + 1
        planned = P.plan_day(draft, day, start, entry_lists=lists,
                             ahead=int(ahead), classification=classification)
        # the giornate before this one are not touched; the ones after it
        # follow, because a day that gains or loses sheets moves everything
        # behind it - leaving them where they were is a register with the same
        # number on two sheets, which is the one thing it may never say
        rest = (P.renumber(after, start=start + len(planned)) if follow
                else after)
        draft.communiques = before + planned + rest
        notify.saved("register_proposed", day=day, n=len(planned))
        st.rerun()


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
