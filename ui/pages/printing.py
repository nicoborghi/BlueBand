"""BATCHES and REGISTER - the two halves of Documenti that are not entry lists.

`render` builds one printable set, each document on its own page with its own
comunicato number:

* everything for one category (its entry list and every event),
* one event across the categories that contest it,
* everything scheduled on one day,
* exactly what one comunicato number publishes,
* one sheet per squadra, and the tabella specialità of the whole meeting.

`render_register` is the register itself: what is planned, what has gone out.
It reads the programme and the comunicati, not the entry list, so it is the one
part of the page that works before anything has been imported.

Both are reached from `ui.pages.documents`, which is the page the jury sees.
"""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from core import communiques as C
from core import entries as E
from core import race as R
from core import recap as RC
from core.config import (DOC_CLASSIFICATION, DOC_RESULTS, DOC_STARTLIST,
                         EVENT_ENTRY_LIST, Competition)
from core.i18n import help_text, label, ui
from core.store import Store
from render import documents as D
from render.render import to_html
from ui import notify, publish
from ui.download import save_button

#: The batches, each one its own catalogue key: the widget stores the key and
#: the word is looked up when the radio is drawn, so a change of language does
#: not lose the batch the jury was printing.
(BY_CATEGORY, BY_EVENT, BY_DAY, BY_COMMUNIQUE, BY_TEAM,
 SPECIALITY_TABLE) = ("mode_by_category", "mode_by_event", "mode_by_day",
                      "mode_by_communique", "mode_by_team",
                      "mode_speciality_table")
MODES = [BY_CATEGORY, BY_EVENT, BY_DAY, BY_COMMUNIQUE, BY_TEAM,
         SPECIALITY_TABLE]

#: The batches that publish what the register says, not a pick of documents.
FIXED_DOCS = (BY_COMMUNIQUE, BY_TEAM, SPECIALITY_TABLE)

#: The batches whose sheets carry a column per specialità, and so a choice
#: between the UCI sigla and the short name at the head of it.
EVENT_HEADED = (BY_TEAM, SPECIALITY_TABLE)


def render(competition: str, comp: Competition, store: Store) -> None:
    el, _stale = E.effective_entries(store, comp)
    if el is None:
        notify.info("import_entries_first")
        return
    R.apply_pair_numbers(store, comp, el)   # madison: le coppie hanno un numero

    mode = st.sidebar.radio(ui("print_mode"), MODES, key="stp_mode",
                            format_func=ui)
    font = st.sidebar.slider(ui("table_font"), 6, 14, 9, key="stp_font")
    landscape = st.sidebar.checkbox(ui("landscape"), key="stp_land")
    suffix = st.sidebar.text_input(ui("title_suffix"), key="stp_suffix",
                                   placeholder=ui("title_suffix_hint"),
                                   help=help_text("title_suffix"))
    docs_wanted = st.sidebar.multiselect(
        ui("documents"), [DOC_STARTLIST, DOC_RESULTS, DOC_CLASSIFICATION],
        default=[DOC_STARTLIST], key="stp_docs", format_func=label,
        # a comunicato publishes what the register says it publishes, and a
        # riepilogo is one sheet per squadra: picking the kinds again here
        # would be a second, contradictory answer
        disabled=mode in FIXED_DOCS)
    # only the two sheets with a column per specialità have anything to head
    short_headers = mode in EVENT_HEADED and st.sidebar.checkbox(
        ui("short_headers"), key="stp_short_heads",
        help=help_text("short_headers"))

    docs = _build(mode, comp, el, store, docs_wanted, font,
                  short_headers=short_headers)
    if not docs:
        notify.warn("no_documents_for_selection")
        return
    publish.batch(docs, comp, store, key="stp", number=docs[0].communique,
                  label=ui("save_pdf_all"), landscape=landscape, suffix=suffix)


# ── batches ─────────────────────────────────────────────────────────────────

def _build(mode: str, comp: Competition, el, store: Store,
           docs_wanted: list[str], font: int, *,
           short_headers: bool = False) -> list:
    if mode == BY_CATEGORY:
        cat = st.sidebar.selectbox(ui("category"), comp.cat_order(),
                                   key="stp_cat")
        return _category(comp, el, store, cat, docs_wanted, font)
    if mode == BY_EVENT:
        events = [s for s in comp.event_order() if s != EVENT_ENTRY_LIST]
        event = st.sidebar.selectbox(ui("event"), events, key="stp_event",
                                     format_func=lambda s: comp.event(s).short)
        return [d for cat in comp.cats_for(event)
                for d in _speciality(comp, el, store, cat, event, docs_wanted, font)]
    if mode == BY_COMMUNIQUE:
        return _communique(comp, el, store, font)
    if mode == BY_TEAM:
        return _team_recaps(comp, el, store, font,
                            short_headers=short_headers)
    if mode == SPECIALITY_TABLE:
        # one sheet, and it says the same as the Verifica page: it is printed,
        # not composed, so there is nothing to pick in the sidebar
        return [D.speciality_table(el, comp, font_size=font,
                                   short_headers=short_headers)]
    day = st.sidebar.selectbox(ui("day"), comp.days(), key="stp_day")
    out = []
    for r in [r for r in comp.programme if r.day == day]:
        out += _speciality(comp, el, store, r.cat, r.event, docs_wanted, font)
    return out


# ── one sheet per squadra ───────────────────────────────────────────────────

def _team_recaps(comp: Competition, el, store: Store, font: int, *,
                 short_headers: bool = False) -> list:
    """The riepilogo of every squadra, one page each, in one PDF.

    The whole point is *tutte insieme*: a team manager is handed their own
    sheet, and the jury prints the pile once. The picker is there for the one
    that turns up late and asks again.

    What a squadra is - regione or società - is set in Impostazioni: an
    Italian championship enters rappresentative, an open meeting societa'.
    """
    group = store.settings.get("team_group") or comp.team_group
    names = RC.teams(el, group)
    if not names:
        notify.warn("no_teams")
        return []
    all_of_them = ui("all_f")
    pick = st.sidebar.selectbox(ui("team"), [all_of_them, *names],
                                key="stp_team", help=help_text("team_recap"))
    # read once for the whole batch: every saved race is opened to find it
    heats = RC.heat_index(store, comp, el)
    docs = [D.team_recap(el, comp, name, group=group, heats=heats,
                         font_size=font, short_headers=short_headers)
            for name in (names if pick == all_of_them else [pick])]
    if len(docs) > 1:
        # one file carries the whole pile, and `out_name` names it after the
        # first sheet in it: named after the first regione, the file would look
        # like that regione's own
        docs[0].slug = label("team_recap_all_slug")
    return docs


# ── one comunicato, whatever it carries ─────────────────────────────────────

def _communique(comp: Competition, el, store: Store, font: int) -> list:
    """Exactly the documents one comunicato number publishes, in order.

    A comunicato is a number on paper, and more than one document can print
    under it: the risultati of a round and the ordine di partenza of the round
    they compose go out together, which is what the velocità and the keirin
    have always done. The register says which (`programme.yaml`, `with:`); this
    builds them into one PDF, in the order they are declared.
    """
    planned = sorted(comp.communiques, key=lambda c: c.n)
    if not planned:
        return []
    by_label = {f"{c.label} · {c.title or c.doc}": c for c in planned}
    picked = st.sidebar.selectbox(label("communique"), list(by_label),
                                  key="stp_com")
    spec = by_label[picked]
    st.caption(ui("communique_carries", n=spec.label, title=spec.title,
                  docs=" + ".join(label(s.doc) for s in spec.sheets)))
    out = []
    for sheet in spec.sheets:
        doc = _sheet_document(comp, el, store, sheet, spec.label, font)
        if doc is None:
            notify.warn("sheet_not_ready", doc=label(sheet.doc),
                        round=sheet.round_key or sheet.event)
            continue
        out.append(doc)
    return out


def _sheet_document(comp: Competition, el, store: Store, sheet, com: str,
                    font: int):
    """One document of a comunicato, or None when the race has nothing yet."""
    if sheet.event == EVENT_ENTRY_LIST:
        return D.entry_list(el, comp, sheet.cat, communique=com, font_size=font)
    state = None
    if store.load_race(R.race_key(sheet.cat, sheet.event, sheet.round_key)):
        state = R.ensure_state(store, comp, sheet.cat, sheet.event,
                               sheet.round_key, el)
    if state is None:
        # not ridden yet: an ordine di partenza can still be the entry list,
        # which is the sheet that would go out anyway
        if sheet.doc == DOC_STARTLIST:
            return D.event_entry_list(el, comp, sheet.cat, sheet.event,
                                      communique=com, font_size=font)
        return None
    # the W of an ammonizione belongs to the sheet, not to the page that prints
    # it: what Gare puts on the paper, Stampa puts on the same paper
    warned = R.warnings_carried(store, comp, sheet.cat, sheet.event,
                                sheet.round_key or "")
    # not on the classifica: the W says a rider carries an ammonizione into the
    # race on this sheet, and a final ranking is no race. It went out on the
    # comunicato of the fase where it was given (see `races._decisions_on`).
    if sheet.doc == DOC_CLASSIFICATION:
        warned = {}
    if sheet.doc == DOC_STARTLIST:
        return D.race_startlist(state, el, comp, communique=com, font_size=font,
                                warned=warned)
    result = R.classify(state, el, comp)
    return D.race_classification(state, result, el, comp, communique=com,
                                 font_size=font, doc_kind=sheet.doc,
                                 warned=warned)


def _category(comp: Competition, el, store: Store, cat: str,
              docs_wanted: list[str], font: int) -> list:
    """Entry list of the category, then every event it contests."""
    out = []
    if DOC_STARTLIST in docs_wanted:
        out.append(D.entry_list(el, comp, cat, font_size=font,
                                communique=C.number_for(
                                    comp, cat, EVENT_ENTRY_LIST, "",
                                    DOC_STARTLIST)))
    for event in comp.events_for(cat):
        out += _speciality(comp, el, store, cat, event, docs_wanted, font)
    return out


def _speciality(comp: Competition, el, store: Store, cat: str, event: str,
                docs_wanted: list[str], font: int) -> list:
    out = []
    for round_key in comp.rounds(cat, event):
        state = store.load_race(R.race_key(cat, event, round_key.key))
        if state is not None:
            # the same race the Gare page shows: a rider added at the verifica
            # after this race was opened is on it (`R.ensure_state`). Nothing
            # is written here - printing does not save.
            state = R.ensure_state(store, comp, cat, event, round_key.key, el)
        for doc in round_key.docs:
            if doc not in docs_wanted:
                continue
            com = C.number_for(comp, cat, event, round_key.key, doc)
            if doc == DOC_STARTLIST and state is None:
                # not run yet: print the entry list so the sheet still exists
                out.append(D.event_entry_list(el, comp, cat, event,
                                              communique=com,
                                              font_size=font))
                continue
            if state is None:
                continue
            warned = ({} if doc == DOC_CLASSIFICATION
                      else R.warnings_carried(store, comp, cat, event,
                                              round_key.key))
            if doc == DOC_STARTLIST:
                out.append(D.race_startlist(state, el, comp, communique=com,
                                            font_size=font, warned=warned))
            else:
                result = R.classify(state, el, comp)
                out.append(D.race_classification(state, result, el, comp,
                                                 communique=com, font_size=font,
                                                 doc_kind=doc, warned=warned))
    return out


# ── register ────────────────────────────────────────────────────────────────

def render_register(competition: str, comp: Competition, store: Store) -> None:
    """What the programme plans and what has gone out - no entry list needed."""
    register = C.load(store)
    rows = C.status(comp, register)

    done = sum(1 for r in rows if r["issued"])
    c1, c2, c3 = st.columns(3)
    c1.metric(ui("planned"), len(comp.communiques))
    c2.metric(ui("issued"), done)
    c3.metric(ui("next_free"), C.next_free(comp, register))

    dup = C.duplicates(register)
    if dup:
        notify.error("communique_duplicates",
                     list=", ".join(str(d) for d in dup))

    # what is being printed, first: the range and the size of it, then the two
    # ways out, and only then the table it is all read off. Scrolling a
    # 140-line register to reach the button that prints it is the wrong way up.
    rows = _register_range(rows)
    font = st.slider(ui("table_font"), 6, 14, 8, key="reg_font",
                     help=help_text("font_pdf"))

    doc = D.comunicati_register(rows, comp, font_size=font)
    c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
    save_button(store, doc, comp, number=label("register_slug"), key="reg",
                label=ui("save_register_pdf"), container=c1)
    table = _register_table(rows, comp)
    c2.download_button(ui("export_xlsx"), _xlsx(table, label("register_slug")),
                       file_name=f"{label('register_slug')}.xlsx", key="reg_xlsx",
                       mime="application/vnd.openxmlformats-officedocument."
                            "spreadsheetml.sheet",
                       use_container_width=True)
    with st.expander(ui("print_preview")):
        st.html(to_html(doc, comp, banner=False, signature=False,
                        footer=False, css=False))

    st.divider()
    day = st.selectbox(ui("day"), [ui("all_days"), *comp.days()], key="reg_day")
    shown = table if day == ui("all_days") else _register_table(
        [r for r in rows if r["day"] == day], comp)
    st.dataframe(shown, hide_index=True, use_container_width=True, height=600)


def _register_range(rows: list[dict]) -> list[dict]:
    """The stretch of numbers being printed.

    A championship register runs to 140 entries over four days, and what a
    jury reprints is usually a handful of them - the ones of the specialità
    just finished. One slider, and it says which numbers are on the sheet.
    """
    numbers = [r["n"] for r in rows if r["n"]]
    if len(numbers) < 2:
        return rows
    lo, hi = min(numbers), max(numbers)
    first, last = st.slider(ui("register_range_filter"), lo, hi, (lo, hi),
                            key="reg_range",
                            help=help_text("register_range_filter"))
    return [r for r in rows if first <= r["n"] <= last]


def _register_table(rows: list[dict], comp: Competition) -> pd.DataFrame:
    """The register as the page shows it - and as the export writes it."""
    return pd.DataFrame([{
        label("register_col_n"): r["label"], label("register_col_day"):
        r["day"] or "", label("cat"): r["cat"],
        label("event"): comp.event(r["event"]).short,
        label("round"): r["round_key"],
        label("document"): label(r["doc"]), ui("title"): r["title"],
        label("issued"): "✓" if r["issued"] else "",
        label("issued_at"): r["issued_at"],
    } for r in rows])


def _xlsx(table: pd.DataFrame, sheet: str) -> bytes:
    """The table as a workbook, for whoever asks for it in a spreadsheet."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        table.to_excel(writer, index=False, sheet_name=sheet[:31] or "export")
    return buffer.getvalue()
