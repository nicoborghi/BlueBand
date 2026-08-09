"""DECISIONS ("Decisioni") - the log the jury keeps, read back.

Everything a panel decides that is not a result: a penalty, a reclamo, a
derogation, a start refused. Each one is a row of a register - categoria,
specialità, fase, dorsale, the compact UCI code (`A1`, `C3`) - with the
sentence that goes out to the teams under it.

It is normally written **in the race it was taken in**, from the Decisioni
panel in the sidebar of Gare, and lands here already knowing which race it
belongs to. It can also be written here, from the same form: the fase is picked
instead of being the one on screen. What must not happen is a decision composed
from memory with no race attached - that is one that has lost the categoria,
the specialità and the fase that make it findable.

The page is the register read three ways:

* **per specialità** - what was decided in each fase of a categoria's evento,
  which is the recap the panel signs off;
* **in the order taken** - the log itself, numbered, corrected in place;
* **on paper** - the sheet the federation asks for afterwards.

What surrounds it are the two reference tables, read-only:

* **Penalità UCI** - the wording of the usual track offences, numbered as the
  UCI numbers them;
* **Cosa prevede il PUIS** - the federal table of what each infringement costs,
  in the column of the categories in gara.

The tick *Includi le ammonizioni* is what the printed register carries: an
ammonizione (provvedimento A) is a decision like any other, but it is the one
that is normally not published - it follows the rider on the sheets instead,
as a W (see `core.decisions`).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import decisions as D
from core import entries as E
from core.config import EVENT_ENTRY_LIST, Competition
from core.i18n import help_text, label, msg, note_kind_name, ui
from core.store import Store
from render import documents as DOC
from ui import decisions_form as DF
from ui import notify
from ui.download import save_button
from ui.state import sticky_select

ALL = ""  # every categoria / every specialità: the register as it stands


def render(competition: str, comp: Competition, store: Store) -> None:
    taken = D.load(store)
    cat, event, shown = _filters(comp, taken)
    _new(comp, store, cat, event)
    st.divider()
    _by_round(comp, store, taken, cat, event)
    _register(comp, store, shown)
    st.divider()
    _taken(comp, store, shown)
    st.divider()
    _reference(comp)


# ── what the page is about ──────────────────────────────────────────────────

def _filters(comp: Competition, taken: list[D.Decision]
             ) -> tuple[str, str, list[D.Decision]]:
    """Which decisions the page is about: the pickers over the register."""
    c1, c2, c3 = st.columns([1, 2, 2])
    cat = sticky_select(c1, ui("decisions_filter_cat"),
                        [ALL, *comp.cat_order()], "dec_f_cat",
                        format_func=lambda c: c or ui("decisions_all"))
    events = [s for s in (comp.events_for(cat) if cat else comp.event_order())
              if s != EVENT_ENTRY_LIST]
    event = sticky_select(c2, ui("decisions_filter_event"), [ALL, *events],
                          "dec_f_event",
                          format_func=lambda s: comp.event(s).short if s
                          else ui("decisions_all"))
    warnings = c3.checkbox(ui("include_warnings"), value=True,
                           key="dec_f_warn", help=help_text("include_warnings"))
    shown = [d for d in taken
             if (not cat or d.cat == cat)
             and (not event or d.event == event)
             and (warnings or str(d.penalty).upper() != D.WARNING)]
    return cat, event, shown


# ── filing one from here ────────────────────────────────────────────────────

def _new(comp: Competition, store: Store, cat: str, event: str) -> None:
    """The same form the sidebar of Gare draws, with the race left to pick.

    It opens on whatever the filters above are set to, which is nearly always
    the race the jury is looking at when it reaches for this page. Without an
    entry list there is nothing to pick a dorsale from and the form falls back
    to a typed field - which is the page still working, on a competition whose
    iscritti have not been imported yet.
    """
    el, _stale = E.effective_entries(store, comp)
    DF.insert(comp, store, el, key="dec_new", cat=cat, event=event)


# ── the recap, per specialità ───────────────────────────────────────────────

def _by_round(comp: Competition, store: Store, taken: list[D.Decision],
              cat: str, event: str) -> None:
    """What was decided in each fase of one specialità.

    Only with a categoria and a specialità chosen: across the whole
    competition, "fase per fase" is the register itself in a worse order. It is
    the summary the panel reads before signing the sheet of the specialità off.
    """
    if not cat or not event:
        return
    st.subheader(ui("decision_summary"))
    rounds = [r.key for r in comp.rounds(cat, event)]
    groups = D.by_round(taken, cat, event, rounds)
    if not groups:
        st.caption(ui("decision_summary_none"))
        return
    for round_key, here in groups:
        with st.container(border=True):
            st.caption(ui("decision_of_round",
                          round=round_key or comp.event(event).short,
                          n=len(here)))
            for d in here:
                st.markdown(f"**{d.code or note_kind_name(d.kind)}** · {d.text}")


# ── the register ────────────────────────────────────────────────────────────

def _register(comp: Competition, store: Store, shown: list[D.Decision]) -> None:
    """The table itself, and the one button that puts it on paper."""
    st.subheader(ui("decisions_register"))
    if not shown:
        notify.info("no_decisions")
        return
    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    c1.dataframe(pd.DataFrame([{
        label("register_col_n"): d.n,
        label("register_col_day"): d.day or "",
        label("cat"): d.cat,
        label("event"): comp.event(d.event).short if d.event else "",
        label("round"): d.round_key,
        ui("bibs"): d.bibs,
        label("penalty_col"): d.code,
        label("decision"): d.text,
    } for d in shown]), hide_index=True, use_container_width=True)
    save_button(store, DOC.decisions_register(shown, comp), comp,
                key="decisions", label=ui("save_decisions_pdf"), container=c2)


# ── correcting what is already filed ────────────────────────────────────────

def _taken(comp: Competition, store: Store, shown: list[D.Decision]) -> None:
    st.subheader(ui("decisions_taken", n=len(shown)))
    for d in reversed(shown):
        with st.container(border=True):
            st.caption(" · ".join(p for p in (DF.head(comp, d),
                                              _where(comp, d)) if p))
            st.write(d.text)
            with st.expander(ui("decision_edit")):
                DF.edit(store, d, f"reg_{d.n}", compact=False)


def _where(comp: Competition, d: D.Decision) -> str:
    """The race a decision is about, as one line - empty when it names none."""
    parts = []
    if d.day:
        parts.append(msg("decision_day", day=d.day))
    if d.cat or d.event:
        parts.append(msg("decision_of_race", cat=d.cat,
                         event=comp.event(d.event).short if d.event else "",
                         round=f" {d.round_key}" if d.round_key else ""))
    return " · ".join(p.strip(" ·") for p in parts if p.strip(" ·"))


# ── the regulations, for looking up ─────────────────────────────────────────

def _reference(comp: Competition) -> None:
    _penalties()
    _puis(comp)


def _penalties() -> None:
    """The UCI wording of the offences: what a decision is quoted from."""
    with st.expander(ui("penalty_quick")):
        wording = D.reasons()
        if not wording:
            notify.warn("no_penalties_table")
            return
        st.caption(help_text("penalty_quick"))
        st.dataframe(pd.DataFrame([{
            label("register_col_n"): n, label("decision"): text}
            for n, text in wording]), hide_index=True,
            use_container_width=True)
        if D.updated_at(D.PENALTIES_FILE):
            st.caption(ui("penalties_updated",
                          when=D.updated_at(D.PENALTIES_FILE)))


def _puis(comp: Competition) -> None:
    """The federal table of what an infringement costs, in the right column."""
    with st.expander(ui("puis_panel")):
        columns = D.puis_columns()
        if not columns:
            notify.warn("no_puis_table")
            return
        st.caption(help_text("puis_panel"))
        default = D.puis_column_for(comp.cat_order())
        c1, c2 = st.columns([2, 3])
        column = c1.selectbox(ui("puis_column"), columns, key="dec_puis_col",
                              index=columns.index(default) if default in columns
                              else 0)
        needle = c2.text_input(ui("puis_search"), key="dec_puis_q")
        rows = D.puis_search(column, needle)
        st.dataframe(pd.DataFrame([{
            label("infringement"): r.get("infrazione", ""),
            label("sanction"): r.get("sanzione", ""),
        } for r in rows]), hide_index=True, use_container_width=True,
            height=420)
        if D.updated_at(D.PUIS_FILE):
            st.caption(ui("puis_updated", when=D.updated_at(D.PUIS_FILE),
                          n=len(rows)))
