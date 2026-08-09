"""STATISTICS ("Statistiche") - the medagliere, and the podiums behind it.

One question is asked at the end of a championship more often than any other:
*how many firsts, seconds and thirds did each squadra take*. The answer is the
top table; everything else on the page exists to make it readable rather than
believed on faith:

* the counters say how much of the competition is in it - concluded specialità
  against the ones still open;
* the detail table lists every podium place the count is made of, so a line of
  the medagliere can be checked against the comunicati in a few seconds;
* the specialità that are not concluded are named, not silently dropped.

The same reading prints: the medagliere is saved as a document like every
other sheet of the meeting, with the podiums under it and the open specialità
named at the foot, so what is read out at the premiazione carries its own
evidence.

The page only reads. Nothing here saves, composes or renumbers anything, and
the counting itself lives in `core.medals` where it can be tested without the
app.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import entries as E
from core import medals as M
from core.config import Competition, EVENT_ENTRY_LIST
from core.i18n import help_text, label, ui
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
        notify.info("import_entries_in_settings")
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
        return
    provisional = {(p.cat, p.event) for p in found.places if not p.complete}
    if provisional:
        notify.warn("stats_counting_unfinished", n=len(provisional))

    _medal_table(table)
    _print(comp, store, found)
    _detail(comp, found)
    _open_events(comp, found)


# ── what is being counted ───────────────────────────────────────────────────

def _filters(comp: Competition) -> tuple[list[str], list[str], bool]:
    """(categories, events, whether the open specialità are counted).

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

def _medal_table(table: list[M.TeamMedals]) -> None:
    """The table the page is for: one line per squadra, best first."""
    st.subheader(ui("medal_table"), help=help_text("medal_table"))
    rows = [{ui("stats_position"): f"{pos}°", label("team"): t.team,
             ui("gold"): t.gold, ui("silver"): t.silver,
             ui("bronze"): t.bronze, ui("total"): t.total}
            for pos, t in M.ranked(table)]
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(ui("stats_download"),
                       df.to_csv(index=False).encode("utf-8"),
                       file_name=f"{label('medal_table_slug')}.csv",
                       mime="text/csv",
                       key="stats_csv")


# ── the same table, on paper ────────────────────────────────────────────────

def _print(comp: Competition, store: Store, found: M.Survey) -> None:
    """The medagliere as a sheet: saved where every other document is saved.

    The same reading the page is showing - filters, open specialità and all -
    so what is handed out at the premiazione cannot disagree with the screen
    it was printed from.
    """
    detail = st.sidebar.checkbox(ui("stats_print_detail"), value=True,
                                 key="stats_print_detail",
                                 help=help_text("stats_print_detail"))
    # the medagliere is reprinted all day as the specialità close: two copies
    # that differ only by the minute on the foot are two copies the jury has to
    # explain. Off by default - every other sheet of the meeting carries it.
    no_stamp = st.sidebar.checkbox(ui("stats_no_printed_at"), value=False,
                                   key="stats_no_printed_at",
                                   help=help_text("stats_no_printed_at"))
    doc = D.medal_table(found, comp, detail=detail)
    save_button(store, doc, comp, number=label("medal_table_slug"),
                key="stats", label=ui("save_medals_pdf"),
                timestamp=not no_stamp)
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
                ui("stats_position"): f"{p.position}°",
                label("team"): ", ".join(p.teams),
                ui("stats_who"): ", ".join(p.names) or p.label,
                # not which fase it came from: a specialità is counted once,
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
