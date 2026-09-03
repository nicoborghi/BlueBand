"""FOGLIO INTESTATO ("Documenti → Foglio intestato") - the sheet the jury writes itself.

Everything else under Documenti is composed: the app knows what an elenco
partenti is and the jury chooses which one. This one is a blank sheet with the
testata, the piè, the numero di comunicato and the firma of the meeting on it,
and whatever has to be said typed into the middle - a convocazione, una nota di
servizio, la comunicazione che non è la classifica di niente.

It is the sheet that used to be a Word file on somebody's laptop: same paper,
different program, filed nowhere. Here it is numbered from the register like
every other comunicato and lands in `out/` with them.

The text is markdown, in the subset `render.markup` reads - grassetto, corsivo,
elenchi, titoli. Everything is escaped before a mark is read: what is typed in
the box is text, never markup.
"""

from __future__ import annotations

import streamlit as st

from core.config import DOC_RESULTS, Competition
from core.i18n import help_text, label, ui
from core.store import Store
from render import documents as D
from ui import publish

#: Where the three fields are kept between reruns. Per competition, not per
#: session: a jury that goes to look at a classifica and comes back finds the
#: sheet it was writing.
TITLE, SUBTITLE, TEXT = "letterhead_title", "letterhead_subtitle", "letterhead_text"


def render(competition: str, comp: Competition, store: Store) -> None:
    with st.sidebar:
        title = st.text_input(ui("letterhead_title"),
                              value=store.settings.get(TITLE, ""),
                              key="lh_title", placeholder=comp.name,
                              help=help_text("letterhead_title"))
        subtitle = st.text_input(ui("letterhead_subtitle"),
                                 value=store.settings.get(SUBTITLE, ""),
                                 key="lh_subtitle",
                                 help=help_text("letterhead_subtitle"))
        text = st.text_area(ui("letterhead_text"),
                            value=store.settings.get(TEXT, ""),
                            key="lh_text", height=320,
                            help=help_text("letterhead_text"))
        com = st.text_input(label("communique_no"), key="lh_com")
        # a foglio intestato is signed far more often than not: it is the jury
        # speaking, and the tick is what says so on paper
        sign = st.checkbox(ui("signature_tick"),
                           value=comp.branding.signs(DOC_RESULTS),
                           key="lh_sig", help=help_text("signature_tick"))
        landscape = st.checkbox(ui("landscape"), key="lh_land",
                                help=help_text("landscape_short"))

    _remember(store, {TITLE: title, SUBTITLE: subtitle, TEXT: text})

    doc = D.letterhead_sheet(comp, title=title, subtitle=subtitle, text=text,
                             communique=com)
    publish.batch([doc], comp, store, key="lh", number=com, signature=sign,
                  landscape=landscape)


def _remember(store: Store, fields: dict[str, str]) -> None:
    """Keep what was typed, and write only when it has actually changed.

    Every keystroke is a rerun: writing the three fields on each of them would
    be a file write per letter typed, and a snapshot of the settings per write
    (`core.store`).
    """
    for key, value in fields.items():
        if value != store.settings.get(key, ""):
            store.set_setting(key, value)
