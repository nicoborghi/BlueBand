"""The document stylesheet, put on the app's own page.

`st.html` sanitises the HTML it is handed and throws away its `<style>`: every
preview in the app was rendering as a bare browser table - no rule between one
coppia and the next, no red second rider, no column widths, no body size. The
one channel Streamlit still leaves open for CSS is `st.markdown` with
`unsafe_allow_html`, so print.css goes in through that, once per run, and the
previews can be handed the fragment alone (`to_html(..., css=False)`).

Everything in print.css is scoped to `.cmsr` except the `@media print` block,
which is written for this page anyway: it is what hides the sidebar and the
toolbar when the jury prints straight from the browser.
"""

from __future__ import annotations

import streamlit as st

from render.render import stylesheet
from ui import icons

# A zero-height component iframe is a control that does something and shows
# nothing: the scroll script, and the one that opens a saved comunicato in a
# tab. Streamlit lays the page out as a flex column with a gap between the
# elements, so left in the flow each of them opens a hole where it lands.
# App-wide, because a PDF can be saved from any page.
_HIDDEN_FRAMES = """
.stElementContainer:has(iframe[height="0"]) { position: absolute; }
"""

# The page picker, dressed as a navigation list. It stays an `st.radio` -
# `st.navigation` is the native control and looks the part, but with
# function-pages it puts nothing in the element tree and `AppTest` cannot
# reach it: adopting it would blind every headless test that changes page,
# which is the whole safety net of this app. So: same widget, no circles, a
# full-width target for each page and the current one filled in.
#
# Scoped to `.st-key-page`, the class Streamlit puts on a keyed widget's
# container, so no other radio in the app is touched. If a Streamlit release
# renames these hooks the rules stop matching and the picker goes back to
# looking like a radio - it never stops working.
_NAV = """
section[data-testid="stSidebar"] .st-key-page [role="radiogroup"] {
    gap: .1rem;
}
section[data-testid="stSidebar"] .st-key-page label {
    width: 100%;
    padding: .3rem .55rem;
    border-radius: .5rem;
    border-left: 3px solid transparent;
    cursor: pointer;
}
/* the circle: a nav says which page you are on by filling the row */
section[data-testid="stSidebar"] .st-key-page label > div:first-child {
    display: none;
}
section[data-testid="stSidebar"] .st-key-page label:hover {
    background: color-mix(in srgb, currentColor 8%, transparent);
}
section[data-testid="stSidebar"] .st-key-page label:has(input:checked) {
    background: color-mix(in srgb, currentColor 12%, transparent);
    border-left-color: var(--primary-color);
}
section[data-testid="stSidebar"] .st-key-page label:has(input:checked) p {
    font-weight: 600;
}
/* one icon per page, in the order the pages are listed (`ui.icons.NAV`).
   Drawn as a mask, not as an image: the shape is the glyph and the colour is
   the row's own, so it follows the theme - and the current page - by itself. */
section[data-testid="stSidebar"] .st-key-page label::before {
    content: "";
    flex: 0 0 auto;
    align-self: center;
    width: 1.05em;
    height: 1.05em;
    margin-right: .6rem;
    background-color: currentColor;
    opacity: .75;
    -webkit-mask: var(--fa) no-repeat center / contain;
    mask: var(--fa) no-repeat center / contain;
}
section[data-testid="stSidebar"] .st-key-page label:has(input:checked)::before {
    opacity: 1;
}
"""


def _nav_icons() -> str:
    """The icon of each page, keyed on its position in the picker."""
    return "\n".join(
        f'section[data-testid="stSidebar"] .st-key-page '
        f"label:nth-of-type({i}) {{ --fa: {icons.data_uri(name)}; }}"
        for i, name in enumerate(icons.NAV, start=1))


def inject() -> None:
    """Put print.css on the page. Cheap enough to repeat on every run."""
    st.markdown(f"<style>{stylesheet()}{_HIDDEN_FRAMES}{_NAV}"
                f"{_nav_icons()}</style>", unsafe_allow_html=True)
