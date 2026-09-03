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
and then, for each of them, which event - so the page asks that, in that
order, and ticking an event is what puts the race in the programme, whole,
with the fasi the regulation proposes. Under it sit the things that differ from
categoria to categoria: the schema of the velocità, which fasi are ridden at
all, and on which giornata.

**event** is the other half of the same statement, and a tab of its own:
what an event *is* - sigla UCI, formato, atleti per squadra, the line every
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

Fasi and not races, because an event is not an indivisible block: the
velocità that qualifies on the Saturday and rides its finali on the Sunday is
two fasi here and three there, and one race throughout (`config.Round.day`).
A fase on no giornata at all is a warning, in the checks and above the day it
would go on: that is the thing this page exists to stop anybody forgetting.

**Controlli is the regolamento**, not the programme: one row per sentence of
its articolo sulle iscrizioni - *max N atleti / squadre / coppie, per regione*
- counted over the elenco and reported here and at the licence desk. It is a
table and not a set of fields because a regulation is a list of sentences, and
next year's is the same list with different numbers in it.

**The last tab writes nothing.** *Verifica* reads the programme back - the
counts, a line per giornata, the short list of what is still missing, the
findings in full, and the file as it will be on disk. None of the tabs that
build a programme ever says whether it is *finished*, and after an afternoon of
writing one that is the question being asked.
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
from core.config import (ANY, CHECK_LEVELS, CHECK_SCOPES, CHECK_UNITS,
                         COMPETITION_KINDS, Check, DEFAULT_TRACK_LEN,
                         DOC_CLASSIFICATION, DOC_RESULTS,
                         DOC_REPECHAGE_KINDS, DOC_STARTLIST,
                         EVENT_ENTRY_LIST, EVENT_PAUSE, KIND_CHAMPIONSHIP,
                         KIND_ORDINARY, KIND_TROFEO_REGIONI,
                         ROUND_SETUP, Competition, is_pause,
                         laps_from_distance,
                         load_competition, madison_track_teams)
from core.formats import sprint as S
from core.checks import WARN, Issue
from core.i18n import catalogue, help_text, label, msg, ui, word
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

#: The section of the page being worked on, and where it is remembered: the
#: jury comes back to the tab it left, from another page or from another day,
#: because writing a programme is an afternoon's work with a race in the middle
#: of it. Kept with the competition (`Store.settings`) and not in the session,
#: which the browser closing takes with it - the same rule the race page has
#: for the sheet it was on (`ui.pages.races.LAST_DOC`).
TAB = "prog_tab"
LAST_TAB = "last_prog_tab"

#: A track is quoted in metres and stored in kilometres.
M_PER_KM = 1000

#: The formats an event can be run under - what `race.round_format` knows.
FORMATS = ("group", "elimination", "timed", "timed_team", "sprint", "keirin",
           "omnium", "madison", "time_trial", "derny", "entrylist")


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

    # The giornate in the middle, and the things that are not a giornata: what
    # the competition *is*, the categorie with what each one rides, what the
    # regolamento limits about who may be entered for them, and the sheet it
    # all prints as. In that order, because that is the order it is decided in
    # - a categoria exists before it has an event, an event is in the
    # file because a categoria rides it, it is on a giornata only once somebody
    # says which fasi are ridden that day, and what may be entered for it is a
    # sentence about a categoria and an event that both already exist.
    #
    # One tab for all of them and the day picked inside it, not a tab each:
    # four giornate of thirty fasi would be four scalette built to move one of
    # them.
    #
    # And a last one that writes nothing: what has just been built,
    # read back. A programme is an afternoon's work and the page it was written
    # on never says whether it is *finished* - so the last tab counts it, says
    # what is still missing, and shows the file that will be on disk.
    #
    # Not `st.tabs`: it draws the body of every tab on every rerun - the whole
    # page, five times over, to type one letter into one of them - and it comes
    # back on the first tab from everywhere, having no state to keep. One
    # picker, one section drawn, and the pick remembered (`_tab`).
    tab = _tab(store)
    {ui("prog_tab_competition"): lambda: _competition_tab(draft),
     ui("prog_tab_categories"): lambda: _categories_tab(draft),
     ui("prog_tab_days"): lambda: _days_tab(draft),
     ui("prog_tab_checks"): lambda: _checks_tab(draft, store),
     ui("programme_print"): lambda: _print_programme(draft, store),
     ui("prog_tab_check"): lambda: _check_tab(draft, store, issues),
     }[tab]()

    _save(competition, draft, store)


def _tab(store: Store) -> str:
    """The section being worked on, reopened where the jury left it.

    Seeded from the competition's settings before the widget exists - a keyed
    widget written to after it is drawn is what Streamlit forbids - and written
    back only when the pick changes, so a rerun is not a file write. Like the
    giornata picker underneath it, this one can be clicked off and the page
    still has to be about something: the last section stands.
    """
    names = [ui("prog_tab_competition"), ui("prog_tab_categories"),
             ui("prog_tab_days"), ui("prog_tab_checks"), ui("programme_print"),
             ui("prog_tab_check")]
    if st.session_state.get(TAB) not in names:
        last = store.settings.get(LAST_TAB)
        st.session_state[TAB] = last if last in names else names[0]
    seeded = st.session_state[TAB]
    tab = st.segmented_control(ui("page_programme"), names, key=TAB,
                               label_visibility="collapsed") or seeded
    if tab != store.settings.get(LAST_TAB):
        store.set_setting(LAST_TAB, tab)
    return tab


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
    and a jury ticking a third event watched the second one vanish.
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

    **A key that is gone is not a key that is empty.** Only one fase is drawn
    at a time (`_round_detail`), and Streamlit drops the state of a widget a
    run does not draw - while `{key}_model`, which is not a widget, survives.
    So the fase came back with its signature unchanged, nothing reseeded it,
    and the box read the missing key as *no documents ticked* and wrote that
    onto the fase: a fase that files nothing, because the jury opened it to
    change the volate. It is why an ED Omnium Tempo Race lost the comunicati
    7 and 24 mid-competition. A missing key reseeds, exactly like a moved one.
    """
    sig = _sig([{"v": current}])
    if st.session_state.get(f"{key}_model") != sig or key not in st.session_state:
        st.session_state[f"{key}_model"] = sig
        st.session_state[key] = [c for c in current if c in options]
    st.session_state[key] = [c for c in st.session_state[key] if c in options]


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

    One line at the top of the page: the checks, folded, and what the programme
    counts under it. There used to be a third thing here - the switch that
    froze the numbering - and it is gone with the renumbering it was there to
    stop: the register is recounted when somebody asks (`_recount`), so there
    is nothing to hold still.

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
    st.caption(ui("programme_counts", events=len(draft.programme),
                  communiques=len(draft.communiques), path=draft.path))
    return issues


# ── the programme, printed ──────────────────────────────────────────────────

def _print_programme(draft: Competition, store: Store) -> None:
    """The running order with the comunicato numbers beside it, as a sheet.

    Every choice is in the sidebar, where the choices of every other printed
    sheet are (`ui.pages.startlists`, `ui.pages.races`): the page itself is the
    sheet. Four groups, in the order the question is asked - which columns the
    table has, which of them are merged, what the register paints on it, and
    how it is laid on the paper.
    """
    with st.sidebar:
        st.caption(help_text("programme_print"))

        st.markdown(f"**{ui('prog_sheet_columns')}**")
        times = st.checkbox(ui("programme_times"), value=True,
                            key="prog_sheet_time",
                            help=help_text("programme_times"))
        durations = st.checkbox(ui("programme_durations"), value=True,
                                key="prog_sheet_dur",
                                help=help_text("programme_durations"))
        race = st.checkbox(ui("show_race_line"), value=True, key=SHOW_RACE,
                           help=help_text("show_race_line"))
        # what this sheet carries is decided here and not in Programmazione:
        # the working table is always the whole table, and this is the one that
        # is printed and pinned up
        numbers = st.checkbox(ui("show_communiques"), value=True,
                              key=SHOW_NUMBERS,
                              help=help_text("show_communiques"))
        # the classifica finale in bold: the parziali of an omnium are
        # classifiche too, and the column is read for the sheet that closes
        # the event
        bold_final = st.checkbox(ui("programme_bold_final"), value=True,
                                 key="prog_sheet_bold",
                                 disabled=not numbers,
                                 help=help_text("programme_bold_final"))

        st.markdown(f"**{ui('prog_sheet_merge')}**")
        merge_round = st.checkbox(ui("programme_merge_round"),
                                  key="prog_sheet_round")
        merge_results = st.checkbox(ui("programme_merge_results"),
                                    key="prog_sheet_res")

        # what has already gone out, from the register itself: the sheet says
        # it in a tint and the jury stops holding the two side by side
        st.markdown(f"**{ui('prog_sheet_issued')}**")
        mark = st.checkbox(ui("mark_issued"), value=True, key=MARK_ISSUED,
                           disabled=not numbers, help=help_text("mark_issued"))
        tint = st.color_picker(ui("issued_tint"), D.ISSUED_TINT, key=ISSUED_TINT,
                               disabled=not (numbers and mark),
                               help=help_text("issued_tint"))

        st.markdown(f"**{ui('prog_sheet_layout')}**")
        font = st.slider(ui("table_font"), 6, 14, 9, key="prog_sheet_font")
        landscape = st.checkbox(ui("landscape"), key="prog_sheet_land",
                                help=help_text("landscape_short"))

    doc = D.programme_sheet(draft, times=times, durations=durations,
                            merge_round=merge_round,
                            merge_results=merge_results, numbers=numbers,
                            race=race, bold_final=bold_final, font_size=font,
                            issued=[i.n for i in C.load(store)] if mark else (),
                            issued_tint=tint)
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
    _kind(draft)

    _communique_rules(draft)

    st.caption(ui("dates_caption"))
    # the format is not guessable and a wrong one is a competition with no
    # days at all: it is shown in the field, not only in the tooltip
    dates = st.text_input(ui("dates"), ", ".join(draft.dates), key="prog_dates",
                          placeholder=ui("dates_hint"),
                          help=help_text("dates"))
    draft.dates = [d.strip() for d in dates.split(",") if d.strip()]


def _communique_rules(draft: Competition) -> None:
    """Which documents share a comunicato, and which sheet carries its number.

    They live **here**, among the things a competition *is* - the track, the
    kind of meeting, the dates - because that is what they are: two lines of
    `programme.yaml` that hold for the whole file and change what goes on
    paper. They used to sit inside the *Rigenera il registro* dialog, so
    changing a rule meant opening the window of the one action that rewrites
    every line of the register and then closing it again without pressing the
    button.

    Nothing here numbers anything. The rules decide how the sheets group; the
    numbers follow when somebody asks for them to (`_recount`).
    """
    with st.expander(ui("communique_rules"), expanded=False):
        st.caption(msg("communique_rules_caption"))
        # the table says what a format does normally; a competition states only
        # where it differs, which is what `Competition.merge` holds
        for code, entry in C.rule_names().items():
            was = draft.merge.get(code, C.rule_on(code))
            now = st.checkbox(C.rule_name(code), value=was,
                              key=f"prog_merge_{code}",
                              help=str(entry.get("_about_") or ""))
            if now == C.rule_on(code):
                draft.merge.pop(code, None)   # the table already says so
            else:
                draft.merge[code] = now
        st.divider()
        draft.number_on_classification = st.checkbox(
            ui("number_on_classification"),
            value=draft.number_on_classification,
            key="prog_number_on_classification",
            help=help_text("number_on_classification"))


# ── the programme, read back ────────────────────────────────────────────────
#
# The last tab, and the only one that writes nothing. A programme is an
# afternoon's work spread over four tabs, and none of them ever says whether it
# is *done*: the page that built it shows what is being edited, never what has
# come out. So this one counts it, says in one list what is still missing, puts
# the findings where they can be read whole rather than folded into the line at
# the top, and ends on the file itself - which is what will be on disk.

def _check_tab(draft: Competition, store: Store, issues: list) -> None:
    """What has just been written, read back: counts, gaps, findings, file."""
    st.subheader(ui("prog_tab_check"))
    st.caption(msg("prog_check_caption"))
    _counts(draft, store)
    _days_recap(draft)
    _ready(draft, store)
    _findings(issues)
    with st.expander(ui("yaml_preview")):
        st.code(P.dump(draft), language="yaml")


def _counts(draft: Competition, store: Store) -> None:
    """The programme in six numbers - the ones a jury quotes on the phone."""
    races = [i for i in draft.programme if not is_pause(i)]
    ridden = sum(len(_ridden(item)) for item in races)
    el = E.load_import(store)
    c1, c2, c3 = st.columns(3)
    c1.metric(ui("count_categories"), len(draft.cat_order()))
    c2.metric(ui("races_scheduled"), len(races))
    c3.metric(ui("count_rounds"), ridden)
    c1, c2, c3 = st.columns(3)
    c1.metric(ui("count_days"), len(draft.days()))
    c2.metric(ui("communiques_planned"), len(draft.communiques))
    # an elenco that is not there is not a zero: nothing has been imported yet,
    # and a 0 would read as a file that came back empty
    c3.metric(ui("count_riders"), len(el.riders) if el else "—")


def _days_recap(draft: Competition) -> None:
    """One line per giornata: how long it is, and what it publishes.

    The number of fasi is what a giornata *is*; the two hours are the answer to
    the only question anybody asks about a programme once it is written - what
    time do we finish - and they are computed, so they are right or they are
    blank (`config.Competition.schedule`).
    """
    rows = []
    for day in draft.days():
        plan = draft.schedule(day)
        times = [t for _i, _r, t in plan if t]
        rows.append({
            ui("day"): day,
            ui("date"): P.date_of(draft, day),
            ui("count_rounds"): len(plan),
            ui("day_begin"): times[0] if times else "",
            ui("day_end"): draft.day_end(day),
            ui("communiques_planned"): sum(1 for c in draft.communiques
                                           if c.day == day),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True,
                     use_container_width=True)


def _ready(draft: Competition, store: Store) -> None:
    """The short list of what is done and what is not.

    Not the checks (`programme.issues`, below): those are things that are
    *wrong*. These are things not yet **there** - a categoria nobody gave a
    event, a fase on no giornata - which is the difference between a
    programme with a mistake in it and one that is not finished.
    """
    no_events = [c for c in draft.cat_order() if not EB.events_of(draft, c)]
    loose = [(i, r) for i in draft.programme if not is_pause(i)
             for r in _ridden(i) if not draft.day_of(i, r)]
    # what the giornata *shows*, not what it states: a fase with a `start`
    # anchors the clock too, and a day printed with its orari is not a day
    # somebody still has to set the clock on
    no_clock = [d for d in draft.days()
                if not any(t for _i, _r, t in draft.schedule(d))]
    book = EB.book_path(store.root)
    counts = C.counted(C.changes(draft, C.load(store)))
    behind = counts["moved"] + counts["added"] + counts["dropped"]
    # (done, what it says when it is, what it says when it is not). The third
    # is what turns a list of ticks into something to act on: *4 categorie
    # senza event: ES, ED …* and not a bare unticked box.
    rows = [
        (bool(draft.dates), "ready_dates", {}),
        (bool(draft.cat_order()) and not no_events, "ready_events",
         {"n": len(no_events), "list": ", ".join(no_events[:6])}),
        (bool(draft.programme) and not loose, "ready_days",
         {"n": len(loose)}),
        (bool(draft.days()) and not no_clock, "ready_clock",
         {"n": len(no_clock), "list": ", ".join(str(d) for d in no_clock)}),
        # not "there is a register" but "the register says what the programme
        # says": one that has fallen behind is the state this page is most
        # often left in, and it used to be invisible until something printed
        (bool(draft.communiques) and not behind, "ready_register",
         {"n": behind}),
        (book.exists(), "ready_entries", {}),
    ]
    lines = []
    for ok, key, values in rows:
        text = ui(key) if ok or f"{key}_no" not in catalogue().UI \
            else ui(f"{key}_no", **values)
        lines.append(f"- {'✓' if ok else '○'} {text}")
    st.markdown("\n".join(lines))


# ── what the regolamento limits ─────────────────────────────────────────────
#
# A tab of its own, between the giornate and Verifica: the giornate say what is
# ridden, this says what may be *entered* for it, and Verifica reports what
# came of both. It is one table, and one row of it is one sentence of the
# articolo sulle iscrizioni - "Omnium massimo 2 corridori per regione" - said
# in five words the app can count: which categoria, which event, what is
# counted, per what, how many.
#
# Nothing here blocks anything. A rule set to *errore* is red in Verifica and
# counted in the summary, and the giuria still saves, prints and races: a
# deroga is granted at the desk, not by reopening the file.


def _check_options(draft: Competition) -> dict[str, dict[str, str]]:
    """Display -> stored, for the four columns that are a choice.

    The file holds codes (`ES`, `madison`, `riders`, `region`); the grid shows
    the words the regolamento is written in. Built once per run, both ways.
    """
    any_of = ui("check_any")
    return {
        "cat": {any_of: ANY, **{c: c for c in draft.cat_order()}},
        "event": {any_of: ANY,
                  **{draft.event(c).short: c for c in draft.event_order()
                     if c != EVENT_ENTRY_LIST}},
        "unit": {ui(f"check_unit_{u}"): u for u in CHECK_UNITS},
        "per": {ui(f"check_per_{p}"): p for p in CHECK_SCOPES},
        "level": {ui(f"check_level_{lv}"): lv for lv in CHECK_LEVELS},
    }


def _check_rows(draft: Competition, opts: dict) -> list[dict]:
    """The rules as the grid shows them."""
    back = {name: {v: k for k, v in table.items()}
            for name, table in opts.items()}
    return [{
        "cat": back["cat"].get(c.cat, ui("check_any")),
        "event": back["event"].get(c.event, ui("check_any")),
        "unit": back["unit"].get(c.unit, ui("check_unit_riders")),
        "per": back["per"].get(c.per, ui("check_per_region")),
        "max": int(c.max),
        "level": back["level"].get(c.level, ui("check_level_warn")),
        "count_reserves": bool(c.count_reserves),
        "note": c.note,
    } for c in draft.checks]


def _checks_tab(draft: Competition, store: Store) -> None:
    st.subheader(ui("prog_tab_checks"))
    st.caption(msg("checks_caption"))
    opts = _check_options(draft)
    rows = _check_rows(draft, opts)
    edited = _grid(
        "prog_checks", rows, num_rows="dynamic", hide_index=True,
        use_container_width=True,
        column_order=["cat", "event", "unit", "per", "max", "level",
                      "count_reserves", "note"],
        column_config={
            "cat": st.column_config.SelectboxColumn(
                ui("check_cat"), options=list(opts["cat"]), width="small",
                help=help_text("check_cat")),
            "event": st.column_config.SelectboxColumn(
                ui("check_event"), options=list(opts["event"]),
                help=help_text("check_event")),
            "unit": st.column_config.SelectboxColumn(
                ui("check_unit"), options=list(opts["unit"]), width="small",
                help=help_text("check_unit")),
            "per": st.column_config.SelectboxColumn(
                ui("check_per"), options=list(opts["per"]),
                help=help_text("check_per")),
            "max": st.column_config.NumberColumn(
                ui("check_max"), min_value=0, max_value=99, step=1,
                width="small", help=help_text("check_max")),
            "level": st.column_config.SelectboxColumn(
                ui("check_level"), options=list(opts["level"]), width="small",
                help=help_text("check_level")),
            "count_reserves": st.column_config.CheckboxColumn(
                ui("check_reserves"), width="small",
                help=help_text("check_reserves")),
            "note": st.column_config.TextColumn(
                ui("check_note"), help=help_text("check_note")),
        })
    draft.checks = _read_checks(edited, opts)
    _grid_done("prog_checks", _check_rows(draft, opts))

    rules = draft.entry_checks()
    if not rules:
        notify.info("checks_none")
    else:
        st.caption(msg("checks_count", n=sum(1 for c in rules if c.on),
                       tot=len(rules)))
    _checks_legacy(draft)
    _checks_effect(draft, store)


def _checks_effect(draft: Competition, store: Store) -> None:
    """What these rules say about the elenco **as it is being typed**.

    Without it the tab is a form with no answer in it: a limit written here is
    counted on Verifica and at the licence desk, both of which read the
    programme *from disk* - so finding out whether anybody is over it meant
    saving, changing page, looking, coming back and changing the number. Four
    gestures to read one number, and the number is the whole reason for typing
    the rule.

    So it is counted here, on the draft, on every rerun: type 2 and the regioni
    that field three are named underneath. Nothing is written - this is the
    same reading Verifica does, done early.
    """
    el, _stale = E.effective_entries(store, draft)
    if el is None:
        notify.info("entry_book_needs_building")
        return
    found = E.check_issues(el, draft)
    st.divider()
    if not found:
        notify.ok("no_findings")
        return
    errors = [i for i in found if i.level == "error"]
    st.markdown("**" + ui("checks_summary", errors=len(errors),
                          warnings=len(found) - len(errors)) + "**")
    notify.issues(found)


def _read_checks(edited, opts: dict) -> list[Check]:
    """The grid back into rules, dropping the row nobody filled in.

    A row added and left empty is not a rule of zero: `st.data_editor` gives a
    new row all-null, and it is a rule only once it says how many.
    """
    out = []
    for _i, row in edited.iterrows():
        value = row.get("max")
        if value is None or (isinstance(value, float) and pd.isna(value)):
            continue
        out.append(Check(
            cat=opts["cat"].get(str(row.get("cat") or ""), ANY),
            event=opts["event"].get(str(row.get("event") or ""), ANY),
            unit=opts["unit"].get(str(row.get("unit") or ""), ""),
            per=opts["per"].get(str(row.get("per") or ""), ""),
            max=int(value or 0),
            level=opts["level"].get(str(row.get("level") or ""), "warn"),
            count_reserves=bool(row.get("count_reserves")),
            note=str(row.get("note") or "").strip()))
    return out


def _checks_legacy(draft: Competition) -> None:
    """The limits of a programme written before this table, and a way out.

    They are read and they hold (`Competition.entry_checks`), but they are
    keyed by event alone and cannot say what this page can - so they are
    not editable here. The button rewrites them as rules and empties the old
    block: after it, what the file says is what this table shows.
    """
    legacy = [c for c in draft.legacy_checks()
              if c.slot not in {x.slot for x in draft.checks}]
    if not legacy:
        return
    notify.warn("checks_legacy", n=len(legacy))
    if st.button(ui("checks_migrate"), key="prog_checks_migrate"):
        draft.checks = draft.checks + legacy
        draft.quotas = dataclasses.replace(
            draft.quotas, max_events_per_rider={}, max_per_region={},
            max_same_club={}, max_same_club_per_region={},
            max_teams_per_region={})
        _grid_reset("prog_checks", _check_rows(draft, _check_options(draft)))
        notify.ok("checks_migrated", n=len(legacy))
        st.rerun()


def _findings(issues: list) -> None:
    """The checks, open. Folded at the top of the page, whole down here."""
    if not issues:
        notify.ok("prog_check_clean")
        return
    errors = [i for i in issues if i.level == "error"]
    st.markdown("**" + ui("checks_summary", errors=len(errors),
                          warnings=len(issues) - len(errors)) + "**")
    notify.issues(issues)


# ── the elenco iscritti of this competition ─────────────────────────────────
#
# It is on this page and not in Impostazioni because it cannot be done before
# the programme: the workbook this competition is run from has a sheet per
# categoria and a column per event of that categoria, and neither exists
# until somebody has said which categorie ride and what each of them rides. It
# was a setting when it was only a *path*.
#
# So it sits **under the categorie**, at the foot of the tab that says who
# rides and what: that is where the file it builds becomes possible, and it is
# the order the page a new competition opens on asks in (`ui.pages.setup`).
# Under the competition, where it used to be, it came *before* the
# categorie it needs, and read as the first thing to do.

def _entry_list(draft: Competition, store: Store | None = None) -> None:
    """Build - or replace - the elenco iscritti of this competition.

    Three questions and no more: which shape the file that arrived is in, the
    file, and - only where the export does not number its riders - how the
    dorsali are to be dealt out. What comes out is written into the folder of
    the competition and is what everything downstream reads.

    The import is always here, open the first time and folded away after: a
    corrected elenco arrives at every championship, and an uploader that
    disappears the moment the workbook exists left the giuria with no way of
    taking one. What a replacement does is shown before it is done (`_replace`).
    """
    store = store or state.store(st.session_state.get(DRAFT_OF) or "")
    st.subheader(ui("entries"))
    st.caption(msg("entry_book_caption"))
    if not _programme_says_enough(draft):
        return

    _team(draft)
    book = EB.book_path(store.root)
    exists = book.exists()
    if exists:
        _entry_book_ready(draft, store, book)
    with st.expander(ui("entry_import_open" if exists else "entry_import_first"),
                     expanded=not exists):
        _entry_book_import(draft, store, book)


def _team(draft: Competition) -> None:
    """What a squadra is at this meeting, and what every sheet calls it.

    The programme's, and here: a *squadra* is the regione at a campionato
    italiano and the società at an open meeting, and that is a fact about the
    competition - not a preference of the machine it is run on, which is what
    it used to be filed as. It decides how the squadre and the coppie of every
    team events are composed, and the word printed at the head of that column.
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

    A categoria with no event is a sheet with no columns to tick, so both
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


def _entry_book_import(draft: Competition, store: Store, book) -> None:
    """The import: the file that arrived, what it changes, and the dorsali.

    The same three widgets whether this is the first elenco or the fourth. What
    differs is the middle: over an existing workbook the arriving file is
    merged onto it and the difference shown, so nothing is written before the
    giuria has seen what it costs.
    """
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
    el = _read_upload(upload, comp, fmt, store)
    # the mapping first, and whatever the file turned out to be: a file that
    # read as nothing is the one that most needs its columns pointed at, and
    # sending the jury away with an error and no way to answer it was the whole
    # problem with a mapping that lived in a table
    _mapping(draft, comp, fmt, el)
    if el is None or not el.riders:
        notify.error("entry_book_read_nothing")
        return
    st.caption(ui("entry_read", n=len(el.riders), cats=", ".join(
        f"{cat} {sum(1 for r in el.riders.values() if r.cat == cat)}"
        for cat in draft.cat_order()
        if any(r.cat == cat for r in el.riders.values()))))
    notify.issues([Issue(WARN, "entry_read", w) for w in el.warnings[:6]])

    replacing = book.exists()
    if replacing:
        el = _merged(draft, store, book, el)
        if el is None:
            return

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
    label_key = "entry_replace" if replacing else "entry_build"
    if st.button(ui(label_key), type="primary", key="prog_entry_go"):
        if how:
            EB.numbered(el, comp, how)
        _write_book(draft, store, comp, el, store.root / EB.FILENAME, fmt)


# ── which column of the file is which field of ours ─────────────────────────
#
# The mapping used to be a block of YAML somebody had to write before anything
# could be imported at all, and then a line in a table of formats. Both answer
# the same question - *which column is the squadra* - and neither can answer it
# for the file that has just arrived: an export with no `Regione` column says
# the regione inside `Note`, and no table knows that in advance.

def _mapping(draft: Competition, comp: Competition, fmt: str, el) -> None:
    """The line under the file, and the dialog behind it.

    Shown for every import and not only the ones that go wrong: what the app
    thinks a column means is worth reading before four hundred riders are
    written on it.
    """
    if not EF.is_flat(fmt):
        return          # a workbook per categoria: its columns are ours
    filled = _read_fields(comp, el)
    missing = [f for f in [*E.FLAT_REQUIRED, comp.team_group]
               if f not in filled]
    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    if c1.button(ui("map_columns"), key="prog_map_go",
                 help=help_text("map_columns")):
        _mapping_dialog(draft, comp)
    if missing:
        c2.caption(msg("map_columns_missing",
                       list=", ".join(label(f) for f in missing)))
    else:
        c2.caption(msg("map_columns_ok"))


def _read_fields(comp: Competition, el) -> set[str]:
    """Which of our fields the import actually filled, over the whole list.

    Read off the riders and not off the mapping: a column that is mapped and
    empty is the same as one that was never found, and it is the second thing
    the jury needs to know about a file it has just been handed.
    """
    out: set[str] = set()
    for rider in (el.riders.values() if el else []):
        for name in E.FLAT_FIELDS:
            if getattr(rider, name, None) not in (None, "", 0, False):
                out.add(name)
    return out


def _mapping_dialog(draft: Competition, comp: Competition) -> None:
    st.dialog(ui("map_columns"))(_mapping_body)(draft, comp)


def _mapping_body(draft: Competition, comp: Competition) -> None:
    """One row per field of ours, and the column of the file it is read from.

    Written onto the **programme** (`entries.ksport`) and not onto a setting:
    it describes the file this competition receives, it is the thing that has
    to survive being opened on another machine, and it is what every page
    downstream reads the file with.

    The mapping is written whole. Half of it read off this file and half
    inherited from the table would be a mapping of neither
    (`entry_formats.applied`).
    """
    st.caption(msg("map_columns_caption"))
    path = st.session_state.get(_UPLOADED)
    if not path or not Path(path).exists():
        notify.info("map_columns_no_file")
        return
    try:
        columns = E.flat_columns(path, comp)
    except Exception as exc:                    # a file that is not one
        notify.text(str(exc))
        return

    none = ui("map_columns_none")
    options = [none, *columns]
    sheet = comp.entry_sheet
    picked: dict[str, str] = {}
    for name in E.FLAT_FIELDS:
        was = sheet.header_of(name, ksport=True)
        # matched loosely, the way the import matches it: the file writes
        # `Nazionalità` where the mapping says `Nazionalita`
        here = next((c for c in columns if sheet.field_of(c, ksport=True)
                     == name), was if was in columns else none)
        head = f"{label(name)}{' *' if name in E.FLAT_REQUIRED else ''}"
        picked[name] = st.selectbox(head, options,
                                    index=options.index(here)
                                    if here in options else 0,
                                    key=f"prog_map_{name}")
    st.caption(msg("map_columns_required"))
    if st.button(ui("map_columns_save"), type="primary", key="prog_map_save"):
        draft.entry_sheet.ksport = {column: name
                                    for name, column in picked.items()
                                    if column != none}
        draft.entry_sheet.__post_init__()      # the lookup is built from it
        notify.saved("map_columns_saved", n=len(draft.entry_sheet.ksport))
        state.refresh()
        st.rerun()


def _merged(draft: Competition, store: Store, book, el):
    """The arriving list over the workbook already there, and what it changes.

    The workbook is read back the way every other page reads it - as the master
    layout - and the giuria's work is carried onto the new list (`entry_book.
    merge`). The delta is drawn here and nowhere else: it is about *this*
    import and is gone the moment the page reruns.
    """
    try:
        old = E.import_master(book, EF.applied(draft, EF.MASTER))
    except Exception as exc:              # a workbook we can no longer read
        notify.text(str(exc))
        notify.error("entry_merge_unreadable", path=book.name)
        return None
    el, delta = EB.merge(old, el)
    _delta(delta)
    return el


def _delta(delta) -> None:
    """What replacing the elenco does, in four numbers and the names behind them.

    The numbers first because that is the decision - two arrived, one gone,
    three moved - and the names in a list under them, for the one case where
    the numbers are not what was expected.
    """
    if not delta.touched:
        notify.info("entry_delta_none")
    cols = st.columns(4)
    for col, key, value in zip(
            cols, ("entry_delta_added", "entry_delta_removed",
                   "entry_delta_changed", "entry_delta_kept"),
            (len(delta.added), len(delta.removed), len(delta.changed),
             delta.kept_marks)):
        col.metric(ui(key), value)
    lines = [f"+ {_who(r)}" for r in delta.added]
    lines += [f"− {_who(r)}" for r in delta.removed]
    lines += [f"~ {_who(new)} · {', '.join(label(f) for f in fields)}"
              for _, new, fields in delta.changed]
    if lines:
        # a scrolling box and not an expander: this is drawn *inside* the
        # import expander, and Streamlit refuses to nest one in another
        st.caption(ui("entry_delta_detail", n=len(lines)))
        with st.container(height=min(240, 40 + 22 * len(lines))):
            st.text("\n".join(lines))
    if delta.kept_checks:
        st.caption(msg("entry_delta_kept_checks", n=delta.kept_checks))


def _who(rider) -> str:
    return f"{rider.cat} {rider.bib or '—'} {rider.full_name}".strip()


def _read_upload(upload, comp: Competition, fmt: str, store: Store):
    """The uploaded file, read as that format says.

    Written to the competition folder first and read from there: every reader
    in `core.entries` takes a path - the file *is* the record of what was
    received, and a temporary copy thrown away would leave the workbook with
    nothing behind it.
    """
    source = Path(store.root) / upload.name
    source.write_bytes(upload.getbuffer())
    # where the mapping dialog reads the file's own headings from: it is drawn
    # in a dialog, which runs on its own and cannot be handed the upload
    st.session_state[_UPLOADED] = str(source)
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

    Which is to follow the programme. A categoria added or an event ticked
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


#: The word each kind is picked by: the widget holds the value, the catalogue
#: is read when the radio is drawn, so it follows a change of language.
KIND_LABELS = {KIND_CHAMPIONSHIP: "kind_championship",
               KIND_ORDINARY: "kind_ordinary",
               KIND_TROFEO_REGIONI: "kind_trofeo_regioni"}


def _kind(draft: Competition) -> None:
    """Championship or ordinary meeting: whether a winner is a champion.

    It decides one thing, and it decides it on every classifica of the
    meeting: `SQUADRA CAMPIONE D'ITALIA` under the winning quartetto and
    `CAMPIONE / CAMPIONESSA D'ITALIA` under the rider who wins an event. A
    trofeo assigns no title, so at an ordinary meeting the band is not printed
    at all - the winner is simply first.

    A Trofeo delle Regioni prints no band either - no event of it assigns
    a title - and asks for one thing more: the meeting is scored prova by prova
    into a classifica per regione, which Statistiche shows and prints beside
    the medagliere (`core.trofeo`).

    Championship is the default: it is what every programme written before the
    question was asked is.
    """
    kinds = list(COMPETITION_KINDS)
    draft.kind = st.radio(
        ui("competition_kind"), kinds, horizontal=True, key="prog_kind",
        index=kinds.index(draft.kind) if draft.kind in kinds else 0,
        format_func=lambda k: ui(KIND_LABELS[k]),
        help=help_text("competition_kind"))


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


def _categories_tab(draft: Competition, store: Store | None = None) -> None:
    """The categorie, for each one what it rides, and the elenco iscritti.

    The unit of a programme is the categoria. A championship is built by saying
    who is racing and then, for each of them, which event - so that is what
    this tab asks, in that order. Ticking an event *is* putting it in the
    programme: the race is created with the fasi the regulation proposes
    (`core.rounds`), on no giornata yet. Which fasi are ridden on which day is
    the giornata's business, and it is asked there.

    There is no catalogue of events any more. What used to be a tab of seven
    fields per event is the catalogue file (`core.catalogue`) plus, under each
    event of each categoria, the handful of things a jury actually corrects.

    The elenco iscritti closes the tab, because it is what the two questions
    above make possible: the workbook has a sheet per categoria and a column
    per event, so it cannot exist before either. `store` is the folder it
    is built in - the page a new competition opens on has no draft of its own
    in the session to look one up from (`ui.pages.setup`).
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
    st.divider()
    _entry_list(draft, store)


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

    Same rule the event had: a categoria with races in the programme is not
    one to delete from under them, and the fix is to untick the event - one
    decision at a time, each visible where it is made.
    """
    if [i for i in draft.programme if i.cat == code]:
        notify.warn("category_in_programme", cat=code)
        return False
    draft.categories.pop(code, None)
    return True


# ── what a categoria rides ──────────────────────────────────────────────────

def _events_of_category(draft: Competition, cat: str) -> None:
    """Tick an event and the categoria rides it.

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
    """What an event is called: what the programme says, or the catalogue."""
    return lambda code: (draft.events[code].short if code in draft.events
                         else CAT.name(code, short=True))


def _declare(draft: Competition, cat: str, event: str) -> None:
    """Put an event in the programme of a categoria, whole.

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

    Nobody declares an event any more: it is in the file because a categoria
    rides it. A file that came from somewhere else can still have a comunicato
    naming an event nothing is scheduled on, and dropping it would print that
    sheet under a bare code, so that one stays.
    """
    named = {s.event for c in draft.communiques for s in c.sheets}
    for code in [c for c in draft.events if c != EVENT_ENTRY_LIST
                 and not draft.scheduled_any(c) and c not in named]:
        del draft.events[code]


def _event_settings(draft: Competition, cat: str, code: str) -> None:
    """The event of one categoria: how *this* categoria rides it.

    Only what differs from categoria to categoria - the schema of the velocità,
    the 5°-8°, how many start together, which fasi are ridden and on which
    giornata. What an event *is* - sigla UCI, formato, atleti per squadra,
    the note every ordine di partenza opens on - is the same for everybody
    riding it and lives in the event tab, edited once.
    """
    ev = draft.events[code]
    item = draft.scheduled(cat, code)
    if item is None:
        return
    with st.expander(f"{cat} · {ev.short}", expanded=False):
        was = RD.options_of(draft, cat, code)
        opts = _options_form(ev.fmt, f"{cat}_{code}", was)
        _remember_options(item, opts, was, ev)
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

    **Giornata**, because an event is not an indivisible block: «—» is a
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
    # edit anybody means: untick the event itself for that
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
    been edited by hand. The button keeps the notes and the durate - the two
    things no regulation can propose - and re-proposes under the options
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


# ── categorie × event ──────────────────────────────────────────────────

def _matrix(draft: Competition) -> None:
    """Rows the categorie, columns the event - the whole programme at once.

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
    _day_start(draft, day)
    _register_bar(draft, day)
    on = draft.rounds_on(day)
    if not on:
        notify.info("no_race_on_day", day=day)
    else:
        _scaletta(draft, day, on)
        _round_detail(draft, day, on)
    _add_rounds(draft, day)
    _add_pause(draft, day)


def _day_start(draft: Competition, day: int) -> None:
    """When the giornata starts - the one orario anybody decides.

    Every other time on the programme follows from this one and from the durate
    of what runs before (`config.Competition.schedule`), which is why it is
    asked here, once, above the scaletta it sets the clock for. Left empty the
    giornata simply has no orario: a programme written before the times are
    known is a normal thing, and an hour invented from midnight would not be.
    """
    c1, _c2 = st.columns([1, 3])
    was = draft.day_start.get(day, "")
    value = c1.text_input(ui("day_start"), was, key=f"prog_day_start_{day}",
                          placeholder=ui("round_start_hint"),
                          help=help_text("day_start")).strip()
    if value:
        draft.day_start[day] = value
    else:
        draft.day_start.pop(day, None)


def _still_loose(draft: Competition) -> None:
    """The fasi that are in the programme and on no giornata.

    The one thing this page is for forgetting: a race declared on a categoria,
    complete with its fasi, that nobody ever put on a day. It is a warning in
    the checks at the top of the page as well - here it is the working list,
    next to the button that places them.
    """
    loose = [f"{i.cat} {draft.event(i.event).short} · {r.label}"
             for i in draft.programme if not is_pause(i)
             for r in _ridden(i) if not draft.day_of(i, r)]
    if loose:
        notify.warn("rounds_still_loose", n=len(loose),
                    list=", ".join(loose[:6]),
                    more=" …" if len(loose) > 6 else "")


def _round_title(draft: Competition, item, rnd) -> str:
    if is_pause(item):
        return f"⏸ {rnd.label}"
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
#: The tint of the comunicati already issued, and whether it is laid at all:
#: the sheet is often printed to be pinned up, and there the green is noise
MARK_ISSUED = "prog_mark_issued"
ISSUED_TINT = "prog_issued_tint"


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

    The classifica of an event is filed under the event and not under
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


def _day_rows(draft: Competition, day: int, on: list, *, numbers: bool,
              race: bool) -> list[dict]:
    """The giornata as a table: one row per fase, numbered from 1.

    The words that say *which* fase are read, not edited - editing them here
    would mean two places that rename a fase. What is editable is what the
    giornata decides: how long it takes, under which comunicati it goes out,
    and whether it is ridden today at all.

    The **orario is read, not typed**: it is the start of the giornata plus the
    durate of everything above (`config.Competition.schedule`). Typing thirty
    times by hand is thirty chances to be wrong by five minutes and one certain
    afternoon of retyping them all the first time a fase moves.
    """
    at = [t for _i, _r, t in draft.schedule(day)]
    picked = st.session_state.get(_SEL % day, set())
    rows = []
    for place, (item, rnd) in enumerate(on, start=1):
        when = at[place - 1] if place <= len(at) else ""
        if is_pause(item):
            # the text where the event goes, and nothing else: a pausa has
            # no categoria, no fase and no comunicato (`config.ROUND_PAUSE`).
            # The doc columns are left off the row altogether, so a number
            # typed into one of them is read by nothing (`_numbers_typed`)
            rows.append({"n": place, "sel": _fase_key(item, rnd) in picked,
                         "cat": "", "event": rnd.label, "round": "",
                         "at": when, "duration": rnd.duration, "off": False})
            continue
        row = {"n": place, "sel": _fase_key(item, rnd) in picked,
               "cat": item.cat,
               "event": draft.event(item.event).short
               + (_race_line(draft, item, rnd) if race else ""),
               "round": rnd.label, "at": when,
               "duration": rnd.duration, "off": False}
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
    rows = _day_rows(draft, day, on, numbers=True, race=True)
    order = ["sel", "n", "at", "duration", "com_start", "cat", "event",
             "round", "com_res", "com_class", "off"]
    config = {
        "n": st.column_config.NumberColumn(
            ui("running_order"), width="small", min_value=1, max_value=99,
            step=1, required=True, help=help_text("running_order")),
        "cat": st.column_config.TextColumn(label("cat"), width="small",
                                           disabled=True),
        "event": st.column_config.TextColumn(label("event"),
                                             width="medium", disabled=True),
        "round": st.column_config.TextColumn(label("round"), disabled=True),
        "sel": st.column_config.CheckboxColumn(
            ui("pick"), width="small", help=help_text("scaletta_pick")),
        "at": st.column_config.TextColumn(
            label("programme_start"), width="small", disabled=True,
            help=help_text("round_start")),
        "duration": st.column_config.NumberColumn(
            ui("round_duration"), width="small", min_value=0, max_value=999,
            step=5, format="%d′", help=help_text("round_duration")),
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
    _move_bar(draft, day, on, edited)


#: The file the import last wrote into the folder of the competition. The
#: mapping dialog needs its columns and runs outside the page that has the
#: upload, so the path is left here rather than passed.
_UPLOADED = "prog_entry_path"


#: Which fasi of a giornata are picked, by name, one entry per giornata. Held
#: across runs on purpose: a fase moved up is still the fase being moved, and a
#: selection that emptied itself after every ▲ would make moving three places a
#: matter of ticking three times.
_SEL = "prog_sel_%d"


def _fase_key(item, rnd) -> str:
    return f"{item.cat}|{item.event}|{rnd.key}"


def _move_bar(draft: Competition, day: int, on: list, edited) -> None:
    """Move what is ticked: up, down, to the top, to the bottom, to a giornata.

    Typing the number is the long jump and stays; this is the short one. A
    scaletta is reordered mostly by swapping neighbours, and doing that by
    retyping two numbers - and their neighbours' - is the thing that made
    reordering a giornata unbearable.

    **Whole race** is the other half of it: an event is three or four fasi
    and they move together, in their own order, wherever they sit in the day.
    Without it, moving a velocità meant moving four rows one at a time.
    """
    picked = {_fase_key(*on[i]) for i, (_x, row) in enumerate(edited.iterrows())
              if i < len(on) and _flag(row.get("sel"))}
    st.session_state[_SEL % day] = picked

    c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1, 1, 3, 3],
                                        vertical_alignment="bottom")
    whole = c5.checkbox(ui("move_whole_race"), key=f"prog_move_whole_{day}",
                        help=help_text("move_whole_race"))
    chosen = _picked_rows(on, picked, whole)
    moves = ((c1, "⤒", "top"), (c2, "▲", "up"), (c3, "▼", "down"),
             (c4, "⤓", "bottom"))
    for col, glyph, where in moves:
        if col.button(glyph, key=f"prog_move_{where}_{day}",
                      disabled=not chosen, help=help_text(f"scaletta_{where}")):
            _reorder(on, _moved(len(on), chosen, where))
            st.rerun()

    days = [d for d in P.days_of(draft) if d != day]
    if days and chosen:
        with c6.popover(ui("move_to_day"), use_container_width=True):
            target = st.selectbox(ui("day"), days, key=f"prog_move_day_{day}",
                                  format_func=lambda d: _day_title(draft, d))
            if st.button(ui("move_go"), key=f"prog_move_go_{day}",
                         type="primary"):
                for i in chosen:
                    _to_day(draft, *on[i], target)
                st.session_state[_SEL % day] = set()
                st.rerun()
    if chosen:
        st.caption(ui("picked_n", n=len(chosen)))


def _picked_rows(on: list, picked: set[str], whole: bool) -> list[int]:
    """The rows the buttons act on, in the order they are in.

    Ticking one fase of a race and asking for the whole race takes the others
    with it - and takes them by *race*, not by neighbour, so a velocità whose
    finali sit at the other end of the giornata still moves whole.
    """
    if not picked:
        return []
    # a pausa is not a race and is never taken along by one: every pausa of the
    # giornata says the same (cat, event), so grouping them would move them all
    races = {(item.cat, item.event) for item, rnd in on
             if _fase_key(item, rnd) in picked and not is_pause(item)}
    return [i for i, (item, rnd) in enumerate(on)
            if _fase_key(item, rnd) in picked
            or (whole and not is_pause(item)
                and (item.cat, item.event) in races)]


def _moved(total: int, chosen: list[int], where: str) -> list[int]:
    """The running order after the picked rows go up, down, first or last.

    The picked rows travel **together and in their own order**, and land
    contiguous: a selection scattered down the giornata is a jury saying "these
    go here", not "each of these moves one place on its own".
    """
    rest = [i for i in range(total) if i not in set(chosen)]
    before = sum(1 for i in rest if i < min(chosen))
    at = {"top": 0, "bottom": len(rest),
          "up": max(0, before - 1),
          "down": min(len(rest), before + 1)}[where]
    return rest[:at] + list(chosen) + rest[at:]


def _reorder(on: list, order: list[int]) -> None:
    """Deal 1..N over the fasi in that order - the running order, restated."""
    for place, i in enumerate(order, start=1):
        on[i][1].seq = place


def _to_day(draft: Competition, item, rnd, day: int) -> None:
    """Move one fase to another giornata, leaving the rest of its race put."""
    _expand(draft, item)
    rnd.day = day
    _normalise(item)


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
    typed = [(_int(row.get("n"), rows[i]["n"]), _int(row.get("duration")),
              _flag(row.get("off")))
             for i, (_x, row) in enumerate(edited.iterrows())]
    numbers = _numbers_typed(on, rows, edited)
    if (typed == [(r["n"], _int(r["duration"]), False) for r in rows]
            and not numbers):
        return False
    changed = _renumber_sheets(draft, numbers)
    for (_item, rnd), (_n, duration, _off), was in zip(on, typed, rows):
        if duration != _int(was["duration"]):
            rnd.duration = duration or None
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
    touched: set[int] = set()
    for item, rnd, doc, n in typed:
        spec = _spec_of(draft, item, rnd, doc)
        # the classifica is filed under the event and may name no fase:
        # moving it must not invent one, or the register would carry two
        sheet = next((s for s in (spec.sheets if spec else [])
                      if s.cat == item.cat and s.event == item.event
                      and s.doc == doc), None)
        rows = P.numbered(rows, {
            "day": draft.day_of(item, rnd), "cat": item.cat,
            "event": item.event,
            "round": sheet.round_key if sheet else (
                "" if doc == DOC_CLASSIFICATION else rnd.key),
            "doc": doc, "title": "", "ret": False, "pinned": True}, n)
        touched.add(n)
    draft.communiques = P.specs_from_rows(rows)
    # a number somebody typed is somebody's expectation: it is pinned, and the
    # next recount flows around it (`communiques.fixed_numbers`). Without this
    # the numbering handed it straight back on the following run, which is the
    # whole reason the register used to need freezing.
    for spec in draft.communiques:
        if spec.n in touched:
            spec.pinned = True
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
    """The comunicati of this fase: read, with the reason each one reads so.

    **Nothing is typed here.** The number is typed in one place, the column of
    the scaletta above; this is where it is *explained* - which comunicato a
    sheet goes out on, whether it is riding under another sheet's number, and
    which rule put it there. Two number fields for the same thing, one of them
    silently the same as a column two rows up, is how a jury ends up believing
    it has two numbers.

    What is decided here is the one thing a number cannot say: **which sheets
    print together**. It used to be said by typing the same number twice, a
    convention that lived in the tooltip of a column.
    """
    filed = _docs_of(rnd)
    if not filed:
        return
    st.caption(f"**{ui('communiques_of_round')}**")
    for doc in filed:
        _sheet_line(draft, item, rnd, doc)


def _sheet_line(draft: Competition, item, rnd, doc: str) -> None:
    """One sheet of the fase: its number, or who carries it, and with what."""
    spec = _spec_of(draft, item, rnd, doc)
    c1, c2 = st.columns([2, 3], vertical_alignment="center")
    if spec is None:
        c1.markdown(f"**{label(doc)}** · {ui('sheet_unnumbered')}")
    else:
        head = spec.sheets[0]
        mine = (head.cat, head.event, head.round_key or "", head.doc) \
            == (item.cat, item.event,
                "" if doc == DOC_CLASSIFICATION else rnd.key, doc)
        # a sheet riding under another one does not carry the number: it is
        # printed on the sheet that names the comunicato (`number_for`)
        c1.markdown(f"**{label(doc)}** · {ui('sheet_on', n=spec.n)}"
                    + ("" if mine else f" · {ui('sheet_carried')}"))
        if len(spec.sheets) > 1:
            c1.caption(spec.title)
    _rides_with_picker(draft, item, rnd, doc, spec, c2)


def _rides_with_picker(draft: Competition, item, rnd, doc: str, spec,
                       col) -> None:
    """*Esce insieme a…*, and the way back out of it.

    The register expresses an accorpamento by giving two documents one number
    (`programme.specs_from_rows`), and that is still how it is written; what
    changes is that it is now *chosen* rather than typed twice into two cells
    of a table. A comunicato that publishes two things is the normal case - the
    risultati of a turno with the partenti of the next - and it was the least
    discoverable thing on the page.

    A sheet that already shares a number is offered the other half of it: a
    comunicato can be split again, and until now nothing but a full recount
    could do that.
    """
    key = f"{item.cat}_{item.event}_{rnd.key}_{doc}"
    if spec is not None and len(spec.sheets) > 1:
        if col.button(ui("rides_alone_go"), key=f"prog_alone_{key}",
                      help=help_text("rides_alone_go")):
            _renumber_sheets(draft, [(item, rnd, doc,
                                      C.next_free(draft, []))])
            st.rerun()
        return

    # the comunicati of the same giornata: an accorpamento is between sheets
    # that go out together, and offering the hundred and forty of a whole
    # championship would be a list nobody can read
    day = draft.day_of(item, rnd)
    alone = ui("rides_alone")
    others = [c for c in sorted(draft.communiques, key=lambda c: c.n)
              if c.day == day and (spec is None or c.n != spec.n)]
    options = [alone] + [f"{c.n}. {c.title or label(c.doc)}" for c in others]
    now = col.selectbox(ui("rides_with"), options, index=0,
                        key=f"prog_rides_{key}", help=help_text("rides_with"))
    if now == alone:
        return
    target = others[options.index(now) - 1]
    if col.button(ui("rides_with_go"), type="primary",
                  key=f"prog_rides_go_{key}"):
        _renumber_sheets(draft, [(item, rnd, doc, target.n)])
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
    """Take a fase off the giornata. It stays in the programme, on no day.

    A pausa is the exception, and it has to be: it belongs to the giornata and
    to nothing else - there is no race of which it is one fase - so a pausa on
    no day would be a line nothing shows and nobody could get back to. Taken
    off the day, it is gone.
    """
    if is_pause(item):
        draft.programme.remove(item)
        return
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
    if is_pause(item):
        _pause_fields(rnd)
        return
    key = f"{item.cat}_{item.event}_{rnd.key}"
    said = N.for_round(draft, item, rnd)
    c1, c2, c3 = st.columns(3)
    # the durata and not the orario: what a jury knows about a fase is how long
    # it takes, and the hour it goes on the track follows from that and from
    # the running order (`config.Competition.schedule`)
    rnd.duration = _int(c1.number_input(
        ui("round_duration"), min_value=0, value=_int(rnd.duration), step=5,
        key=f"prog_dur_{key}", help=help_text("round_duration"))) or None
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
    # partenza, above what the event says on every one of them; the other
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


def _pause_fields(rnd) -> None:
    """A pause has two fields: how long it lasts and what it says.

    Nothing else is offered because nothing else applies - a pausa is not
    ridden over a distance, qualifies nobody and files no sheet. What is typed
    here is what prints, in the column of the event and in corsivo
    (`render.documents._pause_row`).
    """
    c1, c2 = st.columns([1, 3])
    rnd.duration = _int(c1.number_input(
        ui("round_duration"), min_value=0, value=_int(rnd.duration), step=5,
        key=f"prog_pausedur_{rnd.key}",
        help=help_text("round_duration"))) or None
    rnd.label = c2.text_input(
        ui("pause_text"), rnd.label, key=f"prog_pausetxt_{rnd.key}",
        placeholder=msg("pause"), help=help_text("pause_text")).strip() \
        or msg("pause")


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

    Some of it is the point: an event is not an indivisible block, and the
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


def _add_pause(draft: Competition, day: int) -> None:
    """Put a pause on this giornata: how long, and what it is called.

    A giornata is not only races. There is the intervallo, the premiazione, the
    mezz'ora the pista takes to dry - and an hour the programme does not
    account for is an hour every orario under it is wrong by, which is the one
    mistake a foglio programma must not make.

    Two fields, because a pausa has two (`programme.add_pause`): it goes in at
    the bottom of the scaletta and is moved up from there like any other line.
    """
    with st.expander(ui("add_pause")):
        c1, c2 = st.columns([1, 3])
        minutes = int(c1.number_input(ui("round_duration"), min_value=0,
                                      value=15, step=5,
                                      key=f"prog_newpause_min_{day}",
                                      help=help_text("round_duration")))
        text = c2.text_input(ui("pause_text"), msg("pause"),
                             key=f"prog_newpause_txt_{day}",
                             help=help_text("pause_text")).strip()
        if st.button(ui("add"), key=f"prog_addpause_{day}", type="primary"):
            P.add_pause(draft, day, minutes, text)
            notify.saved("pause_added", text=text or msg("pause"),
                         minutes=minutes)
            st.rerun()


def _options_form(fmt: str, key: str, opts: RD.Options | None = None
                  ) -> RD.Options:
    """The fields this format uses, and nothing else.

    `rounds.options_for` decides which appear, so a velocità is asked how many
    the 200 m qualifies and a madison is not asked anything about schemes.

    What this form *is* is said once, above the categorie - not in every box:
    the same three lines under thirty event is noise, and noise is what
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
        elif name == "team_size":
            # seeded with the number the squadre are actually built to
            # (`rounds.options_of`), which is the regulation's own unless this
            # race has been given another one
            values[name] = col.number_input(
                ui("option_team_size"), min_value=1, max_value=12, step=1,
                key=wid, value=int(values[name] or 4),
                help=help_text("option_team_size"))
        else:
            values[name] = col.number_input(
                ui(f"option_{name}"), min_value=0, max_value=20, step=1,
                key=wid, value=int(values[name] or 0))
    return RD.Options(**values)


def _remember_options(item, opts: RD.Options, was: RD.Options, ev) -> None:
    """Write onto the race what the jury changed, and only that.

    Only what this format actually uses: a madison that recorded a velocità
    scheme would be a line of YAML saying nothing. And only what *moved*: the
    form is drawn on every race of every categoria now, seeded with what the
    programme already says (`rounds.options_of`), so writing it back unasked
    would turn "not stated" into a statement on every file this page opens -
    `final_5_8: false` where the file was silent, and a diff on a Salva that
    changed nothing. `None` still means "not stated" (`config.ProgrammeItem`).
    """
    wanted = RD.options_for(ev.fmt)
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
    # and the same for how many ride in a squadra, except that what a race
    # saying nothing rides is the regulation's number and not a constant: put
    # back to it, the race goes back to saying nothing (`Competition.team_size`)
    if "team_size" in wanted and opts.team_size != was.team_size:
        item.team_size = (opts.team_size
                          if opts.team_size != ev.team_size else None)


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


def _register_bar(draft: Competition, day: int) -> None:
    """Where the register stands, and the two things that act on it.

    Two questions and not five buttons. **Which sheets a fase files** is the
    regulation's answer and is written onto the programme (*Assegna i
    documenti*); **what number each of them goes out under** follows from the
    running order and is recounted on request (*Ricalcola i numeri*), never on
    its own and never without showing what it would move first.

    There used to be four: two of them - *Proponi dalla programmazione* and
    *Rinumera tutto* - ran a second numbering that knew nothing of the
    accorpamenti and would move the number of a comunicato already in
    somebody's hands.
    """
    store = state.store(st.session_state.get(DRAFT_OF) or "")
    rows = C.changes(draft, C.load(store))
    counts = C.counted(rows)
    todo = counts["moved"] + counts["added"] + counts["dropped"]

    c1, c2, c3 = st.columns([1, 1, 3], vertical_alignment="bottom")
    if c1.button(ui("assign_docs"), key=f"prog_docs_go_{day}",
                 help=help_text("assign_docs")):
        _assign_docs_dialog(draft)
    if c2.button(ui("recount"), key=f"prog_recount_{day}",
                 type="primary" if todo else "secondary",
                 help=help_text("recount")):
        _recount_dialog(draft, day)

    # the state of the register, said where the work is: it is the line that
    # replaces the renumbering that used to happen silently on every rerun
    mine = [c for c in draft.communiques if c.day == day]
    said = [ui("register_range", first=min(c.n for c in mine),
               last=max(c.n for c in mine), n=len(mine))] if mine else []
    said.append(msg("register_behind", n=todo) if todo
                else msg("register_in_step"))
    c3.caption(" · ".join(said))


def _recount_dialog(draft: Competition, day: int) -> None:
    """The numbers, recounted - shown first, written only if it is wanted."""
    st.dialog(ui("recount"))(_recount_body)(draft, day)


def _recount_body(draft: Competition, day: int) -> None:
    """What a recount would do, line by line, and the button that does it.

    The register of a championship is a hundred and forty lines and a recount
    moves most of them: it is not something to agree to blind. So the diff is
    the dialog - what moves, what is new, what would go, and how many are held
    because they are on paper or were typed by hand - and the button under it
    is the only thing on this page that renumbers anything.
    """
    st.caption(msg("recount_caption"))
    store = state.store(st.session_state.get(DRAFT_OF) or "")
    issued = C.load(store)

    regroup = st.checkbox(ui("recount_regroup"), value=False,
                          key="prog_recount_regroup",
                          help=help_text("recount_regroup"))
    rows = C.changes(draft, issued, rebuild=regroup)
    counts = C.counted(rows)
    st.caption(msg("recount_counts", moved=counts["moved"],
                   added=counts["added"], dropped=counts["dropped"],
                   held=counts["held"]))

    only = st.checkbox(ui("recount_this_day", day=day), value=True,
                       key="prog_recount_day")
    _recount_table(draft, rows, day if only else 0)

    if counts["dropped"]:
        notify.warn("recount_drops", n=counts["dropped"])
    if st.button(ui("recount_go"), type="primary", key="prog_recount_apply",
                 disabled=not (counts["moved"] + counts["added"]
                               + counts["dropped"])):
        draft.communiques = C.autonumber(draft, issued, rebuild=regroup)
        notify.saved("register_recounted", n=len(draft.communiques))
        st.rerun()


def _recount_table(draft: Competition, rows: list, day: int) -> None:
    """The diff itself. Held lines are counted above and not listed here.

    A held line is not news - it is a number staying where it is - and a
    hundred and forty of them would bury the dozen that move.
    """
    shown = [r for r in rows if r.kind != "held"]
    if day:
        wanted = {c.n for c in draft.communiques if c.day == day}
        shown = [r for r in shown if (r.n or r.was) in wanted or r.was in wanted]
    if not shown:
        st.caption(msg("recount_nothing"))
        return
    st.dataframe(
        [{"n": ui(f"recount_{r.kind}"),
          "was": r.was or None, "now": r.n or None,
          "title": r.title,
          "why": ui(f"held_{r.why}") if r.why else ""}
         for r in shown[:200]],
        hide_index=True, use_container_width=True,
        column_config={
            "n": st.column_config.TextColumn(ui("recount_what"), width="small"),
            "was": st.column_config.NumberColumn(ui("recount_was"),
                                                 width="small"),
            "now": st.column_config.NumberColumn(ui("recount_now"),
                                                 width="small"),
            "title": st.column_config.TextColumn(label("document"),
                                                 width="large"),
            "why": st.column_config.TextColumn(ui("recount_why"),
                                               width="medium")})
    if len(shown) > 200:
        st.caption(ui("recount_more", n=len(shown) - 200))


def _assign_docs_dialog(draft: Competition) -> None:
    """Which sheets every fase of the programme files, decided in one go.

    The regulation already knows: a fase files an ordine di partenza and its
    risultati, the one that closes an event files the classifica too, and a
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
        if item.event in (EVENT_ENTRY_LIST, EVENT_PAUSE):
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
