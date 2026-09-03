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
/* an icon for each page, in the order the pages are listed (`ui.icons.NAV`).
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


# Salva, pinned to the foot of the sidebar (`ui.savebar`). Sticky rather than
# fixed: it stays inside the sidebar's own scrolling column, so it never
# overlaps the page and never has to be positioned against a viewport that
# changes with the browser chrome. The background is the sidebar's own, so the
# controls it covers on the way past disappear under it instead of showing
# through.
#
# **What is pinned is the container's wrapper, not the container.** Streamlit
# draws a keyed `st.container` as two nested divs and puts the `st-key-` class
# on the *inner* one, whose parent box is exactly its own height: `sticky`
# there has nowhere to travel - it is already at the bottom of the only box it
# is allowed to move in - and the strip rode down with the scroll like any
# other row. The wrapper (`div:has(> .st-key-savebar)`) is the block that sits
# in the sidebar's own column, and pinning that one is what holds the strip
# against the foot of the window. Written as `:has` on the parent rather than
# against the wrapper's test id, so a renamed test id costs nothing.
#
# Three more things Streamlit does to its sidebar would leave the strip short
# of the foot, and they are undone here *only* where a savebar is on the page:
#
# * `stSidebarUserContent` carries 6rem of bottom padding. Sticky stops where
#   its own column ends, so at the end of the scroll the strip sat six rems up
#   the sidebar with nothing under it. The padding goes; the strip's own is
#   what keeps the last control off the edge.
# * that column is inset by the sidebar's horizontal padding, so a strip drawn
#   inside it is narrower than the sidebar and the controls scrolling past
#   showed down either side of it. Negative margins take it back out to the
#   full width, and the same length as padding puts the buttons back where
#   they were.
# * the sidebar's column is a flex box: a wrapper that only fills what its
#   content asks for could still be stretched by a sibling. `flex: 0 0 auto`
#   keeps the strip the height of its two buttons.
_SIDE_PAD = "calc(1rem + 2px)"

_SAVEBAR = f"""
section[data-testid="stSidebar"]:has(.st-key-savebar)
[data-testid="stSidebarUserContent"] {{
    padding-bottom: 0;
}}
section[data-testid="stSidebar"] div:has(> .st-key-savebar) {{
    position: sticky;
    bottom: 0;
    z-index: 5;
    flex: 0 0 auto;
    padding: .5rem {_SIDE_PAD} .5rem {_SIDE_PAD};
    margin: .5rem calc(-1 * {_SIDE_PAD}) 0 calc(-1 * {_SIDE_PAD});
    background: var(--secondary-background-color, #f0f2f6);
    border-top: 1px solid rgba(128, 128, 128, .25);
}}
section[data-testid="stSidebar"] .st-key-savebar .stButton {{ margin-bottom: 0; }}
"""


# The rule under the page picker (`app.py`), and any other in the sidebar.
# Streamlit gives an `hr` two *ems* of margin on each side, and the sidebar's
# own flex gap goes on top of that: four lines of empty column for one line of
# grey, in the one column where every row is a control the jury needs. The
# margins come down to a quarter of a rem and the container's negative margin
# eats most of the gap around it.
_SIDEBAR_RULE = """
section[data-testid="stSidebar"] hr {
    margin-top: .25rem;
    margin-bottom: .25rem;
}
section[data-testid="stSidebar"] .stElementContainer:has(hr) {
    margin-top: -.4rem;
    margin-bottom: -.4rem;
}
"""


# The row of races last worked on (`races._recent_races`). Six of them wrap to
# a second line on a laptop and push the pickers down the page, which is the
# opposite of what a shortcut is for: one line, and the ones that do not fit
# are scrolled to sideways. The row is one button per race in a column of its
# own, so the columns are what is kept on the line - each as wide as the name
# of the sheet it opens, not a quarter of the page.
_RECENT = """
.st-key-ga_recent [data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    overflow-x: auto;
    scrollbar-width: thin;
    gap: .4rem;
}
.st-key-ga_recent [data-testid="stColumn"] {
    flex: 0 0 auto;
    width: auto !important;
    min-width: 0;
}
.st-key-ga_recent button p { white-space: nowrap; }
"""


# The licence notice at the foot of the sidebar of Impostazioni
# (`ui.pages.settings._credit`). Small, grey and out of the way: it is a
# signature, not a control.
_CREDIT = """
section[data-testid="stSidebar"] .cmsr-credit {
    margin: 1.25rem 0 .25rem 0;
    font-size: .72rem;
    opacity: .55;
    text-align: center;
}
section[data-testid="stSidebar"] .cmsr-credit a {
    color: inherit;
    text-decoration: underline;
}
"""


# The derny board (`ui.derny`). `st.html` throws away a `<style>` handed to it,
# so the chart carries classes and the rules live here, with the rest of the
# app's own CSS. Everything is drawn in the page's own colour - the app has a
# light and a dark theme and a hard-coded grey reads as a hole in one of them -
# except the two things that must be seen from across the desk: the lap a
# rider lost, in red, and the lap whose time is off, in yellow.
_DERNY = """
/* rtl so the box opens on the lap being ridden; the table itself stays on the
   left of it - the segretario reads the chart from the first giro, and a table
   pinned to the right edge of a wide column is read as a second thing */
.dy-scroll { overflow-x: auto; direction: rtl; scrollbar-width: thin; }
.dy-scroll > table { direction: ltr; margin-right: auto; }
.dy-chart { border-collapse: collapse; font-variant-numeric: tabular-nums; }
.dy-chart th {
    font-size: .7rem;
    font-weight: 600;
    opacity: .55;
    padding: 0 .35rem;
    border-bottom: 1px solid rgba(128, 128, 128, .35);
}
.dy-chart td {
    text-align: center;
    padding: .05rem .35rem;
    font-size: .9rem;
    min-width: 2.1rem;
}
/* the lap he did not ride, printed very light where it should have been: the
   column reads complete, and the grey says he was not actually in it */
.dy-chart td.dy-lost { color: rgba(128, 128, 128, .55); }
/* the passage nobody could name: it holds its place and says nothing */
.dy-chart td.dy-unknown { opacity: .45; }
/* and the lap he came back on - the one where the giro was lost */
.dy-chart td.dy-late { color: #d02020; font-weight: 700; }
/* and the lap whose time nobody can explain */
.dy-chart td.dy-hot {
    background: #f6d24a;
    color: #1a1a1a;
    font-weight: 700;
    border-radius: .2rem;
}
.dy-recap h4 { font-size: .85rem; opacity: .6; margin: 0 0 .35rem 0; }
.dy-standings { border-collapse: collapse; width: 100%; }
.dy-standings td {
    padding: .05rem .4rem;
    font-size: .9rem;
    border-bottom: 1px solid rgba(128, 128, 128, .15);
}
.dy-standings .dy-pos { opacity: .5; text-align: right; width: 2.4rem; }
.dy-standings .dy-bib { font-weight: 700; white-space: nowrap; }
.dy-standings .dy-star { color: #d02020; font-weight: 700; }
.dy-dim { opacity: .55; font-size: .8rem; margin-left: .5rem; }
.dy-card { margin-bottom: .35rem; border-radius: .25rem; }
/* a rider with a giro outside the band: the chart itself goes yellow, the
   same yellow as the cell on the Passaggi chart - light enough that the line
   over it still reads */
.dy-card-hot { background: rgba(246, 210, 74, .28); padding: .2rem .3rem; }
.dy-card-head { font-size: .85rem; }
.dy-svg { width: 100%; height: 60px; display: block; }
.dy-splits th {
    font-size: .7rem;
    font-weight: 600;
    opacity: .55;
    text-align: right;
    padding: 0 .4rem;
}
.dy-splits td { text-align: right; font-variant-numeric: tabular-nums; }
"""


def _nav_icons() -> str:
    """The icon of each page, keyed on its position in the picker."""
    return "\n".join(
        f'section[data-testid="stSidebar"] .st-key-page '
        f"label:nth-of-type({i}) {{ --fa: {icons.data_uri(name)}; }}"
        for i, name in enumerate(icons.NAV, start=1))


def inject() -> None:
    """Put print.css on the page. Cheap enough to repeat on every run."""
    st.markdown(f"<style>{stylesheet()}{_HIDDEN_FRAMES}{_NAV}{_SAVEBAR}"
                f"{_SIDEBAR_RULE}{_RECENT}{_CREDIT}{_DERNY}{_nav_icons()}</style>",
                unsafe_allow_html=True)
