"""STATISTICS ("Statistiche") - the medagliere, and the podiums behind it.

One question is asked at the end of a championship more often than any other:
*how many firsts, seconds and thirds did each squadra take*. The answer is the
top table; everything else on the page exists to make it readable rather than
believed on faith:

* the counters say how much of the competition is in it - concluded event
  against the ones still open;
* the detail table lists every podium place the count is made of, so a line of
  the medagliere can be checked against the comunicati in a few seconds;
* the event that are not concluded are named, not silently dropped.

The same reading prints: the medagliere is saved as a document like every
other sheet of the meeting, with the podiums under it and the open event
named at the foot, so what is read out at the premiazione carries its own
evidence.

Where the meeting is a Trofeo delle Regioni (`Competition.scores_teams`) a
second classifica follows the medagliere: the points of the regolamento, prova
by prova, summed per regione. It is the one the Trofeo is actually decided on,
so it is shown and printed with the same evidence under it - the score of every
squadra in every prova, and the rule it was counted under.

The page only reads. Nothing here saves, composes or renumbers anything, and
the counting itself lives in `core.medals` and `core.trofeo` where it can be
tested without the app.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import entries as E
from core import medals as M
from core import trofeo as TR
from core.config import Competition, EVENT_ENTRY_LIST
from core.i18n import help_text, label, ordinal, ui
from core.store import Store
from render import documents as D
from render.render import to_html
from ui import notify
from ui.download import save_button

#: Column keys of the medagliere, in the order they are read.
GOLD, SILVER, BRONZE = "gold", "silver", "bronze"


def render(competition: str, comp: Competition, store: Store) -> None:
    el, _ = E.effective_entries(store, comp)
    if el is None:
        notify.info("entry_book_needs_building")
        return

    cats, events, unfinished = _filters(comp)
    if not cats or not events:
        notify.info("stats_nothing_selected")
        return
    try:
        found = M.survey(store, comp, el, group=comp.team_group,
                         cats=cats, events=events,
                         include_unfinished=unfinished)
    except Exception as exc:                             # noqa: BLE001
        # a page that reads every race of the championship must not be the one
        # thing that goes down between two heats: say what happened and stop
        notify.text(str(exc), level="error")
        return

    _counters(found)
    table = M.medal_table(found.places)
    if not table:
        notify.info("stats_no_results" if not found.places else "stats_no_teams",
                    what=label("team").lower())
        _open_events(comp, found)
        _trofeo(comp, store, el, cats, events, unfinished)
        return
    provisional = {(p.cat, p.event) for p in found.places if not p.complete}
    if provisional:
        notify.warn("stats_counting_unfinished", n=len(provisional))

    df = _medal_table(table)
    _print(comp, store, found, df)
    _detail(comp, found)
    _open_events(comp, found)
    _trofeo(comp, store, el, cats, events, unfinished)


# ── what is being counted ───────────────────────────────────────────────────

def _filters(comp: Competition) -> tuple[list[str], list[str], bool]:
    """(categories, events, whether the open events are counted).

    In the sidebar, where every page of the app keeps what it is showing. The
    default is the whole competition: the medagliere is asked for as a whole,
    and a filter is the exception.
    """
    all_cats = comp.cat_order()
    all_events = [s for s in comp.event_order() if s != EVENT_ENTRY_LIST]
    cats = st.sidebar.multiselect(ui("categories"), all_cats,
                                  default=all_cats, key="stats_cats")
    events = st.sidebar.multiselect(ui("event"), all_events,
                                    default=all_events, key="stats_events",
                                    format_func=lambda s: comp.event(s).short)
    unfinished = st.sidebar.checkbox(ui("include_unfinished"), value=False,
                                     key="stats_unfinished",
                                     help=help_text("include_unfinished"))
    return cats, events, unfinished


def _counters(found: M.Survey) -> None:
    """Concluded, open, podium places - how much of the competition is in."""
    c1, c2, c3 = st.columns(3)
    c1.metric(ui("events_counted"), found.counted)
    c2.metric(ui("events_open"), len(found.open_events))
    c3.metric(ui("podium_places"), len(found.places))


# ── the medagliere ──────────────────────────────────────────────────────────

def _medal_table(table: list[M.TeamMedals]):
    """The table the page is for: one line per squadra, best first."""
    st.subheader(ui("medal_table"), help=help_text("medal_table"))
    rows = [{ui("stats_position"): ordinal(pos), label("team"): t.team,
             ui("gold"): t.gold, ui("silver"): t.silver,
             ui("bronze"): t.bronze, ui("total"): t.total}
            for pos, t in M.ranked(table)]
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    return df


# ── the same table, on paper ────────────────────────────────────────────────

def _print(comp: Competition, store: Store, found: M.Survey, df) -> None:
    """The medagliere as a sheet: saved where every other document is saved.

    The same reading the page is showing - filters, open event and all -
    so what is handed out at the premiazione cannot disagree with the screen
    it was printed from.
    """
    detail = st.sidebar.checkbox(ui("stats_print_detail"), value=True,
                                 key="stats_print_detail",
                                 help=help_text("stats_print_detail"))
    # the medagliere is reprinted all day as the event close: two copies
    # that differ only by the minute on the foot are two copies the jury has to
    # explain. Off by default - every other sheet of the meeting carries it.
    no_stamp = st.sidebar.checkbox(ui("stats_no_printed_at"), value=False,
                                   key="stats_no_printed_at",
                                   help=help_text("stats_no_printed_at"))
    doc = D.medal_table(found, comp, detail=detail)
    # the sheet the premiazione is read from, and the file the federation asks
    # for: the same table, two ways out, on one row under it
    c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
    save_button(store, doc, comp, number=label("medal_table_slug"),
                key="stats", label=ui("save_medals_pdf"),
                timestamp=not no_stamp, container=c1)
    c2.download_button(ui("stats_download"),
                       df.to_csv(index=False).encode("utf-8"),
                       file_name=f"{label('medal_table_slug')}.csv",
                       mime="text/csv", key="stats_csv",
                       use_container_width=True)
    with st.expander(ui("print_preview")):
        st.html(to_html(doc, comp, banner=False, signature=False,
                        footer=False, css=False))


def _detail(comp: Competition, found: M.Survey) -> None:
    """Every podium place the count is made of, in programme order."""
    with st.expander(ui("stats_detail")):
        rows = []
        for p in found.places:
            rows.append({
                label("cat"): p.cat,
                ui("event"): comp.event(p.event).short,
                ui("stats_position"): ordinal(p.position),
                label("team"): ", ".join(p.teams),
                ui("stats_who"): ", ".join(p.names) or p.label,
                # not which fase it came from: an event is counted once,
                # on its final classification, and that is all the table says
                "": "" if p.complete else ui("stats_provisional"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True,
                     hide_index=True)


def _open_events(comp: Competition, found: M.Survey) -> None:
    """What is not concluded yet, so a short table explains itself."""
    if not found.open_events:
        return
    with st.expander(ui("stats_open_list", n=len(found.open_events))):
        rows = [{label("cat"): cat,
                 ui("event"): comp.event(event).short,
                 ui("state"): ui("stats_partial") if any_result
                 else ui("stats_no_result_yet")}
                for cat, event, any_result in found.open_events]
        st.dataframe(pd.DataFrame(rows), use_container_width=True,
                     hide_index=True)


# ── la classifica del Trofeo delle Regioni ──────────────────────────────────

#: The two tables of the regolamento, by the word they are picked with.
SCALE_LABELS = {TR.SCALE_FINAL: "trofeo_scale_final",
                TR.SCALE_QUALIFYING: "trofeo_scale_qualifying"}


def _trofeo(comp: Competition, store: Store, el, cats: list[str],
            events: list[str], unfinished: bool) -> None:
    """The classifica per regione, where the meeting is scored on one.

    Read separately from the medagliere and not derived from it: a medagliere
    knows the first three of an event, and this table needs the first ten
    and everybody who took the start. It reads the same filters, so the two
    tables of the page are always saying something about the same races.
    """
    if not comp.scores_teams:
        return
    st.divider()
    st.subheader(ui("trofeo_table"), help=help_text("trofeo_table"))
    scale = _scale()
    try:
        found = TR.standings(store, comp, el, group=comp.team_group,
                             cats=cats, events=events,
                             include_unfinished=unfinished, scale=scale)
    except Exception as exc:                             # noqa: BLE001
        notify.text(str(exc), level="error")
        return
    if not found.rows:
        notify.info("trofeo_no_scores")
        return

    provisional = {(s.cat, s.event) for s in found.scores if not s.complete}
    if provisional:
        notify.warn("trofeo_counting_unfinished", n=len(provisional))

    _trofeo_counters(found)
    df = _trofeo_standings(found)
    _trofeo_print(comp, store, found, df)
    _trofeo_detail(comp, found)


def _scale() -> str:
    """Which table of the regolamento the prova is scored on.

    In the sidebar with the other filters. The finale is the default: it is
    what the app is opened for, and a prova di qualificazione says so here
    rather than in the programme - the same meeting file runs both.
    """
    scales = list(SCALE_LABELS)
    return st.sidebar.radio(ui("trofeo_scale"), scales, key="stats_scale",
                            format_func=lambda s: ui(SCALE_LABELS[s]),
                            help=help_text("trofeo_scale"))


def _trofeo_counters(found: TR.Standings) -> None:
    """How much of the meeting is in the count, and what it came to."""
    c1, c2, c3 = st.columns(3)
    c1.metric(ui("events_counted"), found.counted)
    c2.metric(ui("trofeo_teams_scored"), len(found.rows))
    c3.metric(ui("trofeo_points_awarded"), sum(r.total for r in found.rows))


def _trofeo_standings(found: TR.Standings):
    """The table the Trofeo is decided on, with the numbers behind it."""
    rows = [{ui("stats_position"): ordinal(pos), label("team"): t.team,
             label("trofeo_placing_points"): t.points,
             label("trofeo_participation"): t.participation,
             label("trofeo_wins"): t.wins,
             ui("trofeo_total"): t.total}
            for pos, t in TR.ranked(found.rows)]
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    winner = TR.champion(found.rows) if not found.open_events else ""
    if winner:
        st.caption(f"{ui('trofeo_champion')}: **{winner}**")
    return df


def _trofeo_print(comp: Competition, store: Store, found: TR.Standings,
                  df) -> None:
    """The same reading on paper, saved where every other sheet is saved."""
    detail = st.sidebar.checkbox(ui("trofeo_print_detail"), value=True,
                                 key="stats_trofeo_detail",
                                 help=help_text("trofeo_print_detail"))
    doc = D.trofeo_table(found, comp, detail=detail)
    c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
    save_button(store, doc, comp, number=label("trofeo_table_slug"),
                key="stats_trofeo", label=ui("save_trofeo_pdf"),
                timestamp=not st.session_state.get("stats_no_printed_at"),
                container=c1)
    c2.download_button(ui("trofeo_download"),
                       df.to_csv(index=False).encode("utf-8"),
                       file_name=f"{label('trofeo_table_slug')}.csv",
                       mime="text/csv", key="stats_trofeo_csv",
                       use_container_width=True)
    with st.expander(ui("print_preview")):
        st.html(to_html(doc, comp, banner=False, signature=False,
                        footer=False, css=False))


def _trofeo_detail(comp: Competition, found: TR.Standings) -> None:
    """Every squadra's score in every prova, so a total can be checked."""
    with st.expander(ui("trofeo_detail")):
        rows = [{label("cat"): s.cat,
                 ui("event"): comp.event(s.event).short,
                 label("team"): s.team,
                 label("trofeo_placings"): ", ".join(
                     f"{ordinal(pos)} {who}" for pos, who in s.places),
                 label("trofeo_placing_points"): s.points,
                 label("trofeo_participation"): s.participation,
                 ui("trofeo_total"): s.total,
                 "": "" if s.complete else ui("stats_provisional")}
                for s in found.scores]
        st.dataframe(pd.DataFrame(rows), use_container_width=True,
                     hide_index=True)
