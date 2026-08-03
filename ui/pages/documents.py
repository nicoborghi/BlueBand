"""DOCUMENTS ("Documenti") - every printed sheet that is not a race sheet.

Partenti and Stampa used to be two pages, and the same two batches lived in
both: *per categoria* and *per specialità* built the same `entry_list` /
`event_entry_list` on either side, except that on Stampa they came without the
number, the note and the filters that decide what actually goes out. The real
line is not between the two old pages - it is between **composing one sheet**
(which is what Gare does for a race, and what the entry lists need here) and
**reprinting a set that is already decided**.

So one page, three groups, picked in the sidebar above whatever the group draws
of its own:

    Elenchi iscritti    one sheet at a time, with its number, its note and its
                        filters                                 (`startlists`)
    Serie di documenti  a batch: a category, an event, a day, a comunicato
                                                                   (`printing`)
    Registro comunicati what is planned and what has gone out
                                                  (`printing.render_register`)

Nothing else moved: each group is the module that always drew it, called with
the page's own arguments.
"""

from __future__ import annotations

import streamlit as st

from core.config import Competition
from core.i18n import ui
from core.store import Store
from ui.pages import printing, startlists

GROUPS = [ui("docs_entries"), ui("docs_batch"), ui("docs_register")]
ENTRIES, BATCH, REGISTER = GROUPS


def render(competition: str, comp: Competition, store: Store) -> None:
    group = st.sidebar.radio(ui("document_group"), GROUPS, key="doc_group")
    st.sidebar.divider()
    if group == ENTRIES:
        startlists.render(competition, comp, store)
    elif group == BATCH:
        printing.render(competition, comp, store)
    else:
        printing.render_register(competition, comp, store)
