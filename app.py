"""Commissaire Track - jury console for track cycling championships.

    streamlit run app.py

Data for each competition lives in `competitions/<NAME>/` (override with the
COMMISSAIRE_TRACK_DATA environment variable).
"""

from pathlib import Path

import streamlit as st

from core.i18n import ui
from ui import state, style
from ui.pages import (check_in, decisions, documents, programme, races,
                      settings, setup, stats)

#: The pages, by catalogue key: the sidebar holds the key and looks the word
#: up when it draws the list, so the page stays open across a change of
#: language - and so nothing here is translated at import, before the
#: competition (and with it the language) has been read.
PAGES = {
    "page_races": races.render,
    "page_check_in": check_in.render,
    "page_decisions": decisions.render,
    "page_documents": documents.render,
    "page_stats": stats.render,
    "page_programme": programme.render,
    "page_settings": settings.render,
}

#: What the app is called - the browser tab, and what the jury asks for.
APP_NAME = "Blue Band"

LOGO = Path(__file__).resolve().parent / "header" / "track.svg"
LOGO_TEXT = Path(__file__).resolve().parent / "header" / "track_text.svg"


def main() -> None:
    st.set_page_config(page_title=APP_NAME, layout="wide",
                       page_icon=str(LOGO) if LOGO.exists() else "🚲",
                       initial_sidebar_state="expanded")
    if LOGO.exists():
        # top of the sidebar, above everything: st.logo owns that strip, so it
        # cannot push the page selector or the race controls around
        st.logo(str(LOGO_TEXT), size="large")

    # the documents' own stylesheet, on the app's page: st.html drops the
    # <style> of the fragment it is given, so the previews would show as bare
    # browser tables (see ui/style.py)
    style.inject()

    competition = state.selected_competition()
    if not competition:
        # nothing in the data folder at all - a new installation. Ask for the
        # first competition rather than reporting the emptiness of the folder
        # to somebody who has no way to fill it (see `ui.pages.setup`).
        setup.render_first()
        st.stop()
    comp = state.competition(competition)
    if comp is None:
        # No programme yet: build one instead of stopping. This used to be
        # `st.stop()`, one line above the sidebar - which left the jury with an
        # error message and no way to reach any page at all, Impostazioni
        # included (see `ui.pages.setup`).
        setup.render(competition, state.store(competition))
        st.stop()
    state.sidebar_header(comp)

    # the label is the accessible name only: over a list of six pages, under
    # the name of the competition, "Pagina" says nothing the list does not
    page = st.sidebar.radio(ui("page"), list(PAGES), key="page",
                            format_func=ui, label_visibility="collapsed")
    st.sidebar.divider()
    PAGES[page](competition, comp, state.store(competition))


if __name__ == "__main__":
    main()
