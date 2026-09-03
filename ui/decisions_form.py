"""Filing a decision: the popover, and the recap that stands above it.

One panel, drawn in two places - in the sidebar of Gare, where the fase is the
race on screen, and on the Decisioni page, where the jury picks it. Both are
the same form and write the same row of the register, because a decision typed
one way in the box and another way on the page is how a register stops being
one.

The form is the *columns* of `core.decisions.Decision`, in the order they are
answered: which race (categoria, event, fase), which dorsale - chosen
among the partenti, not typed from memory - and under which code (`A1`, `C3`).
Out of those the app composes the sentence, in the wording of the decisions
already taken, and hands it to the jury to correct. It is a proposal and it
says so: what the panel decided is the panel's to write.

Above the button, the recap: what has already been decided in this event,
fase by fase. An event ridden in more than one fase is one the jury cannot
hold in its head - the ammonizione given in the turno 1 is what decides whether
the next one is a squalifica - so it is on the screen before the button that
files the next decision, and not a page away.
"""

from __future__ import annotations

import streamlit as st

from core import decisions as D
from core import race as R
from core.config import EVENT_ENTRY_LIST, Competition
from core.i18n import help_text, label, msg, note_kind_name, penalty_name, ui
from core.models import EntryList
from core.parse import ParseError, parse_bibs
from core.store import Store
from ui import notify

#: What the dorsale picker offers when the decision is about somebody the
#: entry list does not know: a rider of another categoria, a coppia, a squadra.
OTHER = "\x00other"


# ── the recap of an event ───────────────────────────────────────────────

def recap(comp: Competition, store: Store, cat: str, event: str, *,
          decisions: list[D.Decision] | None = None,
          always: bool = False) -> None:
    """What was decided in this event, fase by fase, in a few lines.

    Only where the event is ridden in more than one fase: on a scratch,
    which is one race, the recap would be the decisions of that race listed
    twice - once here and once under the panel. `always` overrides that, for
    the page that has no race under it.
    """
    if not cat or not event:
        return
    taken = D.load(store) if decisions is None else decisions
    rounds = [r.key for r in comp.rounds(cat, event)]
    if not always and len(rounds) < 2:
        return
    groups = D.by_round(taken, cat, event, rounds)
    st.caption(ui("decision_summary"), help=help_text("decision_summary"))
    if not groups:
        st.caption(ui("decision_summary_none"))
        return
    for round_key, taken_here in groups:
        st.markdown(f"**{round_key or comp.event(event).short}** · "
                    + " · ".join(_recap_line(d) for d in taken_here))


def _recap_line(d: D.Decision) -> str:
    """One decision in a handful of characters: `C3 dors. 32`."""
    code = d.code or msg("decision_recap_note")
    return (msg("decision_recap_line", code=code, bibs=d.bibs) if d.bibs
            else code)


# ── the form ────────────────────────────────────────────────────────────────

def insert(comp: Competition, store: Store, el: EntryList | None, *,
           key: str, cat: str = "", event: str = "", round_key: str = "",
           locked: bool = False, on_filed=None) -> None:
    """The button that opens the form, and the form.

    `locked` fixes the race to the one passed in: the sidebar of Gare is drawn
    next to the sheet of one race and a picker there is an invitation to file a
    decision against the wrong one. The Decisioni page passes it open.

    `on_filed` is called with the decision that was written, from inside the
    callback that wrote it - which is where the sidebar declares the squalifica
    that a second ammonizione in the same fase amounts to.
    """
    with st.popover(ui("decision_add"), use_container_width=True):
        where = _where(comp, el, key, cat, event, round_key, locked)
        _who(comp, el, key, where)
        _code(key)
        _text(el, key, where)
        st.button(ui("decision_file"), key=f"{key}_file",
                  use_container_width=True, type="primary",
                  on_click=_file, args=(comp, store, key, where, on_filed))


def _where(comp: Competition, el: EntryList | None, key: str, cat: str,
           event: str, round_key: str, locked: bool) -> tuple[str, str, str]:
    """Which race the decision is about: fixed, or picked here."""
    if locked:
        st.caption(msg("decision_of_this_race", cat=cat,
                       event=comp.event(event).short if event else "-",
                       round=round_key or "-"))
        return cat, event, round_key

    cats = comp.cat_order()
    c1, c2 = st.columns([1, 2])
    cat = c1.selectbox(label("cat"), cats, key=f"{key}_cat",
                       index=cats.index(cat) if cat in cats else 0)
    events = [s for s in comp.events_for(cat) if s != EVENT_ENTRY_LIST]
    event = c2.selectbox(label("event"), events, key=f"{key}_event",
                         index=events.index(event) if event in events else 0,
                         format_func=lambda s: comp.event(s).short) \
        if events else ""
    rounds = [r.key for r in comp.rounds(cat, event)] if event else []
    round_key = st.selectbox(
        ui("decision_round"), rounds, key=f"{key}_round",
        index=rounds.index(round_key) if round_key in rounds else 0) \
        if rounds else ""
    return cat, event, round_key


def _who(comp: Competition, el: EntryList | None, key: str,
         where: tuple[str, str, str]) -> None:
    """The dorsale, chosen among the partenti of the race.

    Typed from memory a dorsale is a decision filed against whoever happens to
    wear that number - and at these championships four riders do, one per
    categoria. So the field is a picker over the entry list of *this* race, and
    what it offers is named: `12 ROSSI Mario`. `Altro...` is the way out for a
    decision about somebody who is not in it (a squadra, an accompagnatore),
    and it is a typed field like before.
    """
    cat, event, round_key = where
    bibs = _starters(comp, el, cat, event, round_key)
    if not bibs:
        st.text_input(ui("decision_bib"), key=f"{key}_bibs",
                      help=help_text("decision_bib"))
        st.caption(ui("decision_no_starters"))
        return
    picked = st.selectbox(ui("decision_bib"), [*bibs, OTHER],
                          key=f"{key}_pick", help=help_text("decision_bib"),
                          format_func=lambda b: (ui("decision_bib_other")
                                                 if b == OTHER
                                                 else _named(el, cat, b)))
    if picked == OTHER:
        st.text_input(ui("decision_bib"), key=f"{key}_bibs",
                      label_visibility="collapsed",
                      placeholder=ui("bibs"))


def _starters(comp: Competition, el: EntryList | None, cat: str,
              event: str, round_key: str) -> list[str]:
    """The dorsali that took the start in this race, in numerical order.

    The entry list of the event, not the startlist of the fase: a decision
    is often taken on somebody who did not start the fase it is filed against
    (a rider penalised in the recuperi, a coppia that never lined up), and a
    picker that would not offer them is a picker the jury has to work around.
    """
    if el is None or not cat or not event:
        return []
    try:
        keys = R.entrants(el, comp, cat, event, round_key)
    except Exception:  # an event whose format the programme cannot resolve
        keys = []
    return [k for k in keys if str(k).isdigit()]


def _named(el: EntryList, cat: str, bib: str) -> str:
    """`12 ROSSI Mario` - the number with whoever is riding under it."""
    riders = R.entrant_riders(str(bib), el, cat)
    return f"{bib} {riders[0].full_name}" if riders else str(bib)


def bibs_typed(key: str) -> str:
    """What the form is about, as the register stores it ('12' or '12, 15')."""
    picked = st.session_state.get(f"{key}_pick")
    if picked and picked != OTHER:
        return str(picked)
    return str(st.session_state.get(f"{key}_bibs", "")).strip()


def _code(key: str) -> None:
    """The compact UCI code: the provvedimento, and the article behind it."""
    wording = dict(D.reasons())
    c1, c2 = st.columns([1, 2])
    c1.selectbox(ui("penalty_class"), ["", *D.CLASSES], key=f"{key}_class",
                 format_func=lambda c: (f"{c} · {penalty_name(c)}" if c
                                        else ui("decision_code_none")),
                 help=help_text("penalty_class"))
    c2.selectbox(ui("penalty_reason"), ["", *wording], key=f"{key}_reason",
                 format_func=lambda n: (f"{n}. {wording[n]}" if n else "-"),
                 help=help_text("decision_code"))


def _text(el: EntryList | None, key: str,
          where: tuple[str, str, str]) -> None:
    """The sentence, proposed from the fields above and editable under them.

    The proposal is recomposed on demand and not on every rerun: a field the
    app rewrites while the jury is typing in it is a field the jury stops
    trusting. What is composed once stays until Ricomponi is pressed again.
    """
    st.button(ui("decision_recompose"), key=f"{key}_recompose",
              use_container_width=True, on_click=_recompose,
              args=(el, key, where))
    st.text_area(ui("decision_proposal"), key=f"{key}_text", height=130,
                 help=help_text("decision_proposal"))


def _recompose(el: EntryList | None, key: str,
               where: tuple[str, str, str]) -> None:
    st.session_state[f"{key}_text"] = propose(el, key, where)


def propose(el: EntryList | None, key: str,
            where: tuple[str, str, str]) -> str:
    """The proposed wording for what the form currently says."""
    cat = where[0]
    return D.compose(who(el, cat, bibs_typed(key)),
                     str(st.session_state.get(f"{key}_class", "")),
                     str(st.session_state.get(f"{key}_reason", "")))


def who(el: EntryList | None, cat: str, bibs: str) -> str:
    """The riders a decision is about, named where the entry list knows them."""
    if el is None:
        return bibs.strip()
    try:
        numbers = parse_bibs(bibs)
    except ParseError:
        return bibs.strip()
    named = []
    for bib in numbers:
        found = [r for r in el.riders.values()
                 if r.bib == bib and r.cat == cat]
        named.append(msg("penalty_rider", cat=found[0].cat, bib=bib,
                         name=found[0].full_name) if len(found) == 1
                     else f"{label('bib')} {bib}")
    return ", ".join(named)


def _file(comp: Competition, store: Store, key: str,
          where: tuple[str, str, str], on_filed=None) -> None:
    """Write the row, and clear the form for the next one.

    A callback, and it has to be one: what follows a decision - the squalifica
    that two ammonizioni in the same fase amount to - is written into a widget
    that has already been drawn this run, which only a callback may do.
    """
    cat, event, round_key = where
    text = str(st.session_state.get(f"{key}_text", "")).strip()
    if not text:
        notify.error("decision_empty")
        return
    scheduled = comp.scheduled(cat, event)
    d = D.add(store, D.Decision(
        day=scheduled.day if scheduled else 0,
        cat=cat, event=event, round_key=round_key, bibs=bibs_typed(key),
        penalty=str(st.session_state.get(f"{key}_class", "")),
        reason=str(st.session_state.get(f"{key}_reason", "")),
        text=text))
    notify.saved("decision_saved", n=d.n)
    for suffix in ("text", "bibs"):
        st.session_state[f"{key}_{suffix}"] = ""
    if on_filed:
        on_filed(d)


# ── correcting what is already filed ────────────────────────────────────────

def edit(store: Store, d: D.Decision, wid: str, *, compact: bool = True
         ) -> None:
    """One filed decision, editable in place: the code, the dorsali, the text.

    Wherever a decision is shown it can be corrected there. A decision written
    on the wrong dorsale has to be fixable while the race it belongs to is on
    screen - walking away to another page to fix a number is how the fix does
    not get made.
    """
    c1, c2, c3 = st.columns([1, 1, 1])
    c1.text_input(ui("bibs"), d.bibs, key=f"eb_{wid}",
                  label_visibility="collapsed", placeholder=ui("bibs"))
    classes = ["", *D.CLASSES]
    c2.selectbox(ui("penalty_class"), classes, key=f"ec_{wid}",
                 index=classes.index(d.penalty) if d.penalty in classes else 0,
                 label_visibility="collapsed",
                 format_func=lambda c: (f"{c} {penalty_name(c)}" if c
                                        else ui("decision_code_none")))
    wording = dict(D.reasons())
    reasons = ["", *wording]
    c3.selectbox(ui("penalty_reason"), reasons, key=f"er_{wid}",
                 index=reasons.index(d.reason) if d.reason in reasons else 0,
                 label_visibility="collapsed",
                 format_func=lambda n: (f"{n}. {wording[n]}" if n else "-"))
    st.text_area(ui("decision_body"), d.text, key=f"et_{wid}",
                 height=80 if compact else 140, label_visibility="collapsed")
    b1, b2 = st.columns([1, 1])
    b1.button(ui("decision_update"), key=f"eu_{wid}", use_container_width=True,
              on_click=apply_edit, args=(store, d, wid))
    b2.button(ui("decision_delete"), key=f"ed_{wid}", use_container_width=True,
              on_click=drop, args=(store, d.n))


def apply_edit(store: Store, d: D.Decision, wid: str) -> None:
    text = str(st.session_state.get(f"et_{wid}", "")).strip()
    if not text:
        notify.error("decision_empty")
        return
    d.text = text
    d.bibs = str(st.session_state.get(f"eb_{wid}", "")).strip()
    d.penalty = str(st.session_state.get(f"ec_{wid}", ""))
    d.reason = str(st.session_state.get(f"er_{wid}", ""))
    D.update(store, d)
    notify.saved("decision_updated", n=d.n)


def drop(store: Store, n: int) -> None:
    D.remove(store, n)
    notify.saved("decision_removed", n=n)


def head(comp: Competition, d: D.Decision) -> str:
    """The one-line heading of a filed decision, wherever it is shown."""
    parts = [ui("decision_head", n=d.n, when=d.ts.replace("T", " ")[:16])]
    if d.code:
        parts.append(f"{d.code} · {note_kind_name(d.kind)}")
    if d.bibs:
        parts.append(f"{label('bib')} {d.bibs}")
    return " · ".join(parts)
