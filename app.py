"""Commissaire Track - jury console for track cycling championships.

    streamlit run app.py

Data for each competition lives in `competitions/<NAME>/` (override with the
COMMISSAIRE_TRACK_DATA environment variable).
"""

from pathlib import Path

import streamlit as st

from core.i18n import ui
from ui import notify, state, style
from ui.pages import (check_in, decisions, documents, programme, races,
                      settings)

PAGES = {
    ui("page_races"): races.render,
    ui("page_check_in"): check_in.render,
    ui("page_decisions"): decisions.render,
    ui("page_documents"): documents.render,
    ui("page_programme"): programme.render,
    ui("page_settings"): settings.render,
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
        st.stop()
    comp = state.competition(competition)
    if comp is None:
        notify.error("no_programme", name=competition)
        st.stop()
    state.sidebar_header(comp)

    # the label is the accessible name only: over a list of six pages, under
    # the name of the competition, "Pagina" says nothing the list does not
    page = st.sidebar.radio(ui("page"), list(PAGES), key="page",
                            label_visibility="collapsed")
    st.sidebar.divider()
    PAGES[page](competition, comp, state.store(competition))


if __name__ == "__main__":
    main()
