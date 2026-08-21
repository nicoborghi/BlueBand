"""SETUP - the page a competition with no programme opens on.

`programme.yaml` is what everything else in the app comes out of, and until now
a folder without one was a dead end: `ui.state.competition` returned `None`,
the app said *'TR2026' non contiene un programme.yaml* and stopped - **before**
the sidebar was drawn, so Impostazioni, the only place a competition is picked,
could not be reached. Getting out of it meant editing files by hand.

This page is what happens instead: the same three things a jury would write at
the top of the file - the manifestazione, the pista, the categorie - asked for
once, written, and then the app opens normally on Programma, where the races
are added day by day and every one of these fields can be corrected.

Nothing here is a form of its own: the widgets *are* the ones of the Programma
page (`ui.pages.programme._competition_tab`), called on a blank programme. A
second set that drifted from the first is exactly the kind of thing this app
does not do - see how the check-in and the entry list share their grid.
"""

from __future__ import annotations

import streamlit as st

from core import programme as P
from core.config import Competition
from core.i18n import help_text, ui
from core.store import (Store, competitions_root, list_competitions,
                        open_competition)
from ui import notify, state
from ui.pages import programme as PROG

DRAFT = "setup_draft"


def render(competition: str, store: Store) -> None:
    """Build the first programme of a competition that has none."""
    draft = _draft(competition)

    st.title(ui("setup_title"))
    notify.info("setup_needed", name=competition)

    # the widgets of the Programma page, on a blank programme: what is filled
    # in here is editable there afterwards, in the same fields - the
    # manifestazione, the pista and the categorie, in that order
    PROG._competition_tab(draft)
    st.divider()
    PROG._categories_tab(draft)

    st.divider()
    if st.button(ui("setup_create"), type="primary",
                 disabled=not draft.categories):
        _create(competition, draft, store)


def _draft(competition: str) -> Competition:
    """The programme being built, held in the session until it is written."""
    if st.session_state.get(f"{DRAFT}_of") != competition:
        st.session_state[DRAFT] = P.blank(competition)
        st.session_state[f"{DRAFT}_of"] = competition
    return st.session_state[DRAFT]


def _create(competition: str, draft: Competition, store: Store) -> None:
    """Write the programme and let the app open on it."""
    if not draft.categories:
        notify.error("setup_no_categories")
        return
    path = store.path(state.PROGRAMME)
    P.save(path, draft, store=store)
    notify.ok("setup_done", path=path)
    st.session_state.pop(DRAFT, None)
    st.session_state.pop(f"{DRAFT}_of", None)
    state.refresh()


# ── before there is even a folder ───────────────────────────────────────────

def render_first() -> None:
    """The data folder is empty: ask for the first competition.

    One text field and a button. What it creates is a folder with no programme
    in it, which is exactly the state `render` above handles - so the app walks
    straight on into the three steps.
    """
    st.title(ui("setup_title"))
    notify.info("no_competitions", path=competitions_root())
    st.caption(help_text("new_competition"))

    name = "".join(st.text_input(ui("new_competition_name"),
                                 key="setup_first_name",
                                 placeholder="CITA27").split())
    if st.button(ui("create"), type="primary", disabled=not name,
                 key="setup_first_go"):
        if name in list_competitions():
            notify.error("competition_exists", name=name)
            return
        open_competition(name)          # `Store.__init__` makes the folder
        state.choose_competition(name)
