"""DECISIONS ("Decisioni") - the log the jury secretary keeps by hand.

Everything a panel decides that is not a result: a penalty, a reclamo, a
derogation, a start refused. Until now it went on paper; here it goes in
`decisions.json`, numbered, timestamped and kept with the competition.

The page is a big text field and nothing in its way. What surrounds it only
saves typing:

* the row of pickers says *which race* a decision belongs to, so it can be
  found again - it is not part of the text;
* **Penalità rapide** composes the line a penalty goes out as (athlete,
  degree, the UCI wording of the offence) and appends it to the text, where it
  stays editable;
* **Cosa prevede il PUIS** is the federal table, read-only, in the column of
  the categories in gara.

The structure is there for the day the races page files its own decisions here
(a DSQ typed into a result is a decision the panel took): the fields are the
ones a race would fill in.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from core import decisions as D
from core import entries as E
from core.config import EVENT_ENTRY_LIST, Competition
from core.i18n import help_text, label, msg, penalty_name, ui
from core.parse import ParseError, parse_bibs
from core.store import Store
from ui import notify
from ui.state import sticky_select

#: Widget keys cleared once a decision has been filed.
COMPOSER_KEYS = ("dec_text", "dec_bibs", "dec_class")

NONE = ""  # a decision that is not a penalty - the usual case


def render(competition: str, comp: Competition, store: Store) -> None:
    # names make the penalty line readable; without an import the page still
    # works, on the bibs alone
    el, _stale = E.effective_entries(store, comp)

    _composer(comp, store, el)
    st.divider()
    _taken(comp, store)


# ── writing one down ────────────────────────────────────────────────────────

def _composer(comp: Competition, store: Store, el) -> None:
    st.subheader(ui("decision_new"))
    day, cat, event, bibs = _context(comp)
    penalty = st.radio(ui("penalty"), [NONE, *D.CLASSES], horizontal=True,
                       key="dec_class", format_func=_penalty_label,
                       help=help_text("penalty_class"))
    # above the text and not under it: it is what *writes* the text, and a
    # panel that composes a line belongs before the line it composes
    _quick_penalty(comp, el, cat, bibs)
    text = st.text_area(ui("decision_body"), key="dec_text", height=260,
                        help=help_text("decision_body"))

    if st.button(ui("decision_save"), type="primary", key="dec_save"):
        if not text.strip():
            notify.error("decision_empty")
        else:
            d = D.add(store, D.Decision(
                day=day, cat=cat, event=event, bibs=bibs.strip(),
                penalty=penalty, text=text.strip()))
            notify.saved("decision_saved", n=d.n)
            _clear_composer()
            st.rerun()

    _puis(comp)


def _context(comp: Competition) -> tuple[int, str, str, str]:
    """Which race the decision is about. All of it optional, none of it printed.

    Every picker is `sticky_select`: the specialità offered depend on the
    categoria above them, and one held in the session after the categoria
    changed is no longer among the options.
    """
    c1, c2, c3, c4 = st.columns([1, 1, 2, 1])
    days = [0, *comp.days()]
    day = sticky_select(c1, ui("day"), days, "dec_day", _today(comp),
                        format_func=lambda d: msg("decision_day", day=d) if d
                        else ui("decision_none"),
                        help=help_text("decision_context"))
    cat = sticky_select(c2, ui("category"), [""] + comp.cat_order(), "dec_cat",
                        format_func=lambda c: c or ui("decision_none"))
    events = [""] + [s for s in (comp.events_for(cat) if cat
                                 else comp.event_order())
                     if s != EVENT_ENTRY_LIST]
    event = sticky_select(c3, ui("event"), events, "dec_event",
                          format_func=lambda s: comp.event(s).short if s
                          else ui("decision_none"))
    bibs = c4.text_input(ui("bibs"), key="dec_bibs",
                         help=help_text("decision_bibs"))
    return int(day or 0), cat, event, bibs


def _today(comp: Competition) -> int:
    """The day of the competition being ridden, so the picker opens on it."""
    today = date.today().isoformat()
    for n, when in enumerate(comp.dates, start=1):
        if str(when)[:10] == today:
            return n
    return 0


def _penalty_label(code: str) -> str:
    return f"{code} {penalty_name(code)}" if code else ui("decision_none")


def _clear_composer() -> None:
    """Drop the fields of the decision just filed, keeping the pickers set.

    The context (giornata, categoria, specialità) is where the jury still is:
    the next decision is usually about the same race.
    """
    for k in COMPOSER_KEYS:
        if k in st.session_state:
            del st.session_state[k]


# ── the two panels behind it ────────────────────────────────────────────────

def _quick_penalty(comp: Competition, el, cat: str, bibs: str) -> None:
    """Compose the sentence a penalty goes out as, and append it to the text."""
    with st.expander(ui("penalty_quick")):
        wording = dict(D.reasons())
        if not wording:
            notify.warn("no_penalties_table")
            return
        st.caption(help_text("penalty_quick"))
        c1, c2 = st.columns([4, 1])
        # picked by its UCI number, shown with the wording: the number is what
        # is quoted, and a list of plain values is what a test can drive
        pick = c1.selectbox(ui("penalty_reason"), list(wording),
                            key="dec_reason",
                            format_func=lambda n: f"{n}. {wording[n]}")
        klass = c2.selectbox(ui("penalty_class"), D.CLASSES, key="dec_qclass",
                             format_func=_penalty_label)
        line = _penalty_line(_who(el, comp, cat, bibs), klass, wording[pick])
        st.code(line, language=None, wrap_lines=True)
        st.button(ui("penalty_add"), key="dec_add", on_click=_append,
                  args=(line, klass))
        if D.updated_at(D.PENALTIES_FILE):
            st.caption(ui("penalties_updated",
                          when=D.updated_at(D.PENALTIES_FILE)))


def _append(line: str, klass: str) -> None:
    """Add the composed line to the decision text (a callback: it runs first)."""
    current = str(st.session_state.get("dec_text", "")).rstrip()
    st.session_state["dec_text"] = f"{current}\n{line}" if current else line
    # the degree of the penalty is the same statement as the line: the radio
    # above follows the pick rather than being set again by hand
    st.session_state["dec_class"] = klass


def _penalty_line(who: str, klass: str, reason: str) -> str:
    """'ES 12 ROSSI Mario: RETROCESSIONE (C) per aver ...' - as it goes on the sheet."""
    parts = []
    if who:
        parts.append(msg("penalty_for", who=who))
    if klass:
        parts.append(f"{penalty_name(klass).upper()} ({klass})")
    if reason:
        parts.append(reason)
    return " ".join(parts)


def _who(el, comp: Competition, cat: str, bibs: str) -> str:
    """The riders a penalty is about, named where the entry list knows them."""
    text = (bibs or "").strip()
    if not text:
        return ""
    try:
        numbers = parse_bibs(text)
    except ParseError:
        return text          # unreadable: keep what was typed, name nobody
    named = []
    for bib in numbers:
        rider = _rider(el, comp, cat, bib)
        named.append(msg("penalty_rider", cat=rider.cat, bib=rider.bib,
                         name=rider.full_name) if rider
                     else f"{label('bib')} {bib}")
    return ", ".join(named)


def _rider(el, comp: Competition, cat: str, bib: int):
    """The rider wearing `bib`. Without a category the number is not unique:
    the same dorsale is worn in every categoria, so an unfiltered search only
    answers when exactly one rider wears it."""
    if el is None:
        return None
    found = [r for r in el.riders.values()
             if r.bib == bib and (not cat or r.cat == cat)]
    return found[0] if len(found) == 1 else None


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


# ── what has been decided so far ────────────────────────────────────────────

def _taken(comp: Competition, store: Store) -> None:
    taken = D.load(store)
    st.subheader(ui("decisions_taken", n=len(taken)))
    if not taken:
        notify.info("no_decisions")
        return
    for d in reversed(taken):
        head = ui("decision_head", n=d.n, when=d.ts.replace("T", " "))
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            c1.caption(" · ".join(p for p in (head, _where(comp, d),
                                              _penalty_label(d.penalty)
                                              if d.penalty else "") if p))
            if c2.button(ui("decision_delete"), key=f"dec_del_{d.n}"):
                D.remove(store, d.n)
                notify.saved("decision_removed", n=d.n)
                st.rerun()
            st.write(d.text)
            _rewrite(store, d)


def _rewrite(store: Store, d: D.Decision) -> None:
    """Correct a decision already filed, without retyping it.

    Folded away: the page is read far more often than it is corrected, and a
    text field per decision would turn the log into a form.
    """
    with st.expander(ui("decision_edit")):
        text = st.text_area(ui("decision_body"), value=d.text,
                            key=f"dec_edit_{d.n}", height=160,
                            label_visibility="collapsed")
        if st.button(ui("decision_save"), key=f"dec_upd_{d.n}"):
            if not text.strip():
                notify.error("decision_empty")
                return
            d.text = text.strip()
            D.update(store, d)
            notify.saved("decision_updated", n=d.n)
            st.rerun()


def _where(comp: Competition, d: D.Decision) -> str:
    """The race a decision is about, as one line - empty when it names none."""
    parts = []
    if d.day:
        parts.append(msg("decision_day", day=d.day))
    if d.cat or d.event:
        parts.append(msg("decision_of_race", cat=d.cat,
                         event=comp.event(d.event).short if d.event else "",
                         round=f" {d.round_key}" if d.round_key else ""))
    if d.bibs:
        parts.append(f"{label('bib')} {d.bibs}")
    return " · ".join(p.strip(" ·") for p in parts if p.strip(" ·"))
