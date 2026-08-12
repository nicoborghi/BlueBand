"""Salva, where it can always be reached: the foot of the sidebar.

A jury saves at the end of a race, and by then the page is long - a velocità
finals sheet is four rounds of pickers over a preview of the document. The
*Salva* button lived at the bottom of the sidebar's own column, which on a
laptop means scrolling a sidebar to press the one control that must never be
missed. A save nobody can find is work nobody keeps.

So it is pinned. Everything a page puts in the sidebar scrolls as it always
did; this one strip does not (`ui/style.py` makes it `position: sticky`), and
it holds the same two buttons on every page that has something to save:

    savebar.render(save=..., restore=...)

The two are always the same pair, whatever the page is saving: **Salva**, which
is what the jury presses, and the way back - *Ripristina versione precedente*
on a race, *Ricarica dal file* on the programme - because the second is what
makes the first safe to press.

It is drawn last, after whatever else the page has put in the sidebar, so that
what is pinned sits under the controls rather than over them.

**It records the press; it does not do the saving.** The strip is drawn at the
top of the run, before the page body has read a single field: a race saved
there would be the race as it was when the run started, without whatever was
typed into it a moment ago. So `render` leaves a request behind and the page
picks it up with `requested()` *after* it has built everything - which is the
same reasoning as the `gridsave_` flag it replaces.

    savebar.render(label=ui("save"), restore_label=ui("restore_previous"))
    ...                                     # the whole page
    if savebar.requested() == savebar.SAVE:
        store.save_race(state)
"""

from __future__ import annotations

import streamlit as st

#: The container the stylesheet pins (see `ui.style`). One per run: a page
#: draws its own buttons into it and nothing else uses the name.
KEY = "savebar"

#: What was pressed, left in the session for the page to pick up at the end.
REQUEST = "savebar_request"
SAVE = "save"
RESTORE = "restore"


def render(*, label: str, restore_label: str = "", help: str = "",
           restore_help: str = "", disabled: bool = False,
           sidebar: bool = True) -> None:
    """Draw the pinned strip: Salva, and the way back from it."""
    where = st.sidebar if sidebar else st
    with where.container(key=KEY):
        # side by side, and not the same size: Salva is what the strip is for,
        # the way back is the small one next to it. Stacked, the two took the
        # height of four rows of the sidebar for one decision.
        save_col, back_col = (st.columns([4, 1]) if restore_label
                              else (st.container(), None))
        if save_col.button(label, type="primary", use_container_width=True,
                           key=f"{KEY}_save", help=help or None,
                           disabled=disabled):
            st.session_state[REQUEST] = SAVE
        if back_col is not None:
            if back_col.button("↩", use_container_width=True,
                               key=f"{KEY}_restore",
                               help=restore_help or restore_label):
                st.session_state[REQUEST] = RESTORE


def requested() -> str:
    """What the jury pressed this run - `SAVE`, `RESTORE` or nothing.

    Read once, at the end of the page: it is consumed, so a rerun that follows
    does not save a second time.
    """
    return st.session_state.pop(REQUEST, "")
