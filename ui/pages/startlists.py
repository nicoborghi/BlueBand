"""ENTRY LISTS ("Documenti → Elenchi iscritti") - one sheet, per category or per event.

The group of Documenti that composes a sheet rather than reprinting one: the
comunicato number, the note the jury writes under the title and the filters
(NP, riserve, solo verificati) are all here, because this is the sheet that
goes out.

Anything shown here prints as-is with the browser (Ctrl-P): the sidebar and the
app chrome are hidden by `render/print.css`. Every rendered set is also written
to `out/` as a self-contained HTML file, so a comunicato can be reprinted later
without the app.
"""

from __future__ import annotations

import streamlit as st

from core import communiques as C
from core import entries as E
from core import race as R
from core.config import DOC_STARTLIST, EVENT_ENTRY_LIST, Competition
from core.i18n import help_text, label, ui
from core.store import Store
from render import documents as D
from render.render import archive
from ui import notify, publish

#: The three ways an entry list is printed. A mode *is* its catalogue key:
#: that is what the widget stores and what the code below compares, so the
#: pick survives a change of language - only the word beside it moves.
BY_CATEGORY, BY_EVENT, ALL_EVENTS = ("mode_by_category", "mode_by_event",
                                     "mode_all_events")
MODES = [BY_CATEGORY, BY_EVENT, ALL_EVENTS]


def render(competition: str, comp: Competition, store: Store) -> None:
    el, stale = E.effective_entries(store, comp)
    if el is None:
        return          # the menu does not offer this page without one (`app`)
    R.apply_pair_numbers(store, comp, el)   # madison: le coppie hanno un numero

    with st.sidebar:
        # no heading of its own: the group radio right above already says
        # which half of Documenti these controls belong to
        mode = st.radio(ui("print_mode"), MODES, key="pa_mode",
                        format_func=ui)
        cats = comp.cat_order()
        cat = st.selectbox(ui("category"), cats, key="pa_cat")
        event = ""
        if mode == BY_EVENT:
            events = [s for s in comp.events_for(cat) if s != EVENT_ENTRY_LIST]
            event = st.selectbox(ui("event"), events, key="pa_event",
                                 format_func=lambda s: comp.event(s).short)
        show_index = st.checkbox(ui("row_number"), value=True, key="pa_idx",
                                 help=help_text("row_number"))
        show_matrix = st.checkbox(ui("event_matrix"), value=False,
                                  key="pa_matrix",
                                  help=help_text("event_matrix"))
        include_np = st.checkbox(ui("include_np"), value=False, key="pa_np")
        include_ris = st.checkbox(ui("include_reserves"), value=True,
                                  key="pa_ris")
        only_ver = st.checkbox(ui("only_verified"), value=False, key="pa_ver",
                               help=help_text("only_verified"))
        minimal = st.checkbox(ui("minimal_columns"), value=False, key="pa_min")
        font = st.slider(ui("table_font"), 6, 14, 9, key="pa_font")
        landscape = st.checkbox(ui("landscape"), key="pa_land",
                                help=help_text("landscape_short"))
        suffix = st.text_input(ui("title_suffix"), key="pa_suffix",
                               placeholder=ui("title_suffix_hint"),
                               help=help_text("title_suffix"))
        draft = st.checkbox(ui("not_final"), value=False, key="pa_draft",
                            help=help_text("draft"))
        com = st.text_input(label("communique_no"),
                            value=_default_com(comp, cat, event),
                            key="pa_com", disabled=draft)
        # one event, one standing note to start from; a batch of several has
        # none of its own and starts empty
        decision = st.text_area(
            ui("decision_note"),
            # written about the riders it is printed for: on a categoria
            # femminile it is *la prima atleta* who starts on the finishing
            # straight
            comp.event(event).note(female=comp.female(cat)) if event else "",
            key=f"pa_dec_{event or mode}_{cat}")
        # an elenco partenti is a startlist: it is signed only where the
        # setting says every sheet is (Impostazioni → avanzate)
        sign = st.checkbox(ui("signature_tick"),
                           value=comp.branding.signs(DOC_STARTLIST),
                           key="pa_sig", help=help_text("signature_tick"))

    # the four entry lists are a per-category job: the button belongs where
    # that mode is
    if mode == BY_CATEGORY:
        _quick_print(el, comp, store, font, show_matrix, show_index)

    p = E.check_in_progress(el, cat)
    if p.missing:
        st.caption(ui("check_in_line", cat=cat, done=p.verificati,
                      total=p.entries, left=p.missing)
                   + (f" · {p.not_starting} NP" if p.not_starting else ""))

    docs = _build(el, comp, mode, cat, event, show_matrix, show_index,
                  include_np, include_ris, only_ver, minimal, font,
                  "" if draft else com, decision)
    if not docs:
        notify.warn("no_riders_for_selection")
        return
    for d in docs:
        d.draft = draft
    publish.batch(docs, comp, store, key="pa", number="" if draft else com,
                  signature=sign, landscape=landscape, suffix=suffix)


def _quick_print(el, comp: Competition, store, font: int, matrix: bool,
                 index: bool) -> None:
    """One click for the four entry lists - the first documents of every competition.

    Each category is its own comunicato, numbered from the register, so this
    writes one file per category rather than a single bundle.
    """
    cats = [c for c in comp.cat_order() if el.by_cat(c)]
    if not cats:
        return
    if not st.button(ui("print_all_entries", n=len(cats)),
                     help=help_text("print_all_entries")):
        return
    saved = []
    with st.spinner(ui("building_documents")):
        for cat in cats:
            num = _default_com(comp, cat, "")
            doc = D.entry_list(el, comp, cat, matrix=matrix, index=index,
                               font_size=font, communique=num)
            saved.append(archive(store, doc, comp, number=num, signature=False))
    notify.saved("saved_entry_lists", n=len(saved))


def _default_com(comp: Competition, cat: str, event: str) -> str:
    """The planned number of an elenco partenti, from the register.

    The four opening comunicati hang off the pseudo-event `entry_list`; an
    event's own elenco is planned under the event. `find` is the register's own
    lookup, and the loose one on purpose: this sheet is not a round, so it
    takes the number planned for the specialità whichever fase carries it - the
    jury sees the number in the field and corrects it. The two hand-rolled
    copies of this loop that used to live here disagreed with it in one case
    (`_com_for` matched the string "partenti" rather than the constant).
    """
    planned = C.find(comp, cat, event or EVENT_ENTRY_LIST, "", DOC_STARTLIST)
    return planned.label if planned else ""


def _build(el, comp, mode, cat, event, show_matrix, show_index, include_np,
           include_ris, only_ver, minimal, font, com, decision) -> list:
    if mode == BY_CATEGORY:
        return [D.entry_list(el, comp, cat, matrix=show_matrix,
                             index=show_index,
                             include_np=include_np, only_verified=only_ver,
                             minimal=minimal, communique=com, font_size=font,
                             decision=decision)]
    if mode == BY_EVENT:
        if not event:
            return []
        return [D.event_entry_list(el, comp, cat, event, communique=com,
                                   include_reserves=include_ris,
                                   only_verified=only_ver,
                                   font_size=font, decision=decision)]
    # every event of the category, one document per page
    return [D.event_entry_list(el, comp, cat, s,
                               communique=_default_com(comp, cat, s),
                               include_reserves=include_ris,
                               only_verified=only_ver, font_size=font)
            for s in comp.events_for(cat) if s != EVENT_ENTRY_LIST
            and el.entered(cat, s, include_reserves=include_ris)]
