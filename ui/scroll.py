"""Scroll the page to the work when the race being prepared changes.

The pickers sit above what they pick: on a laptop the jury chooses a fase and
the header of the race is already below the fold, so the page still shows the
three selectboxes and nothing else. Here a change of race scrolls the anchor -
the line the section starts with - just under the toolbar.

Only on a *change*: the first render of a page leaves the browser where it is,
and a rerun caused by typing a time must not move the page under the cursor.

**Only in Gare.** Every page used to do this, and every page switch did it too:
the result was a page that moved on its own for reasons the jury did not ask
about, including on the pages where nothing is below the fold to begin with.
One place where the pickers really do hide the work, and nowhere else.
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

# Negative: the block container's own top padding is part of what is measured,
# so landing exactly on the anchor still leaves the pickers above it on screen.
# Scroll past it, up to where the title is the first line of the page.
OFFSET_PX = -48

_MISSING = object()


def anchor(name: str) -> None:
    """Mark the point of the page a selection scrolls to.

    The marker is hidden: Streamlit lays the page out as a flex column with a
    gap between the elements, so an anchor left visible would open a hole in
    every page that has one. Hidden it has no box either, and the scroll is
    computed on the element that follows it instead.
    """
    st.markdown(f'{_ANCHOR_CSS}<span class="cmsr-anchor" '
                f'id="cmsr-{name}"></span>', unsafe_allow_html=True)


_ANCHOR_CSS = """
<style>
.stElementContainer:has(> .stMarkdown span.cmsr-anchor) { display: none; }
</style>"""


def on_change(name: str, value) -> None:
    """Scroll to `anchor(name)` when `value` differs from the last run."""
    key = f"_scroll_{name}"
    previous = st.session_state.get(key, _MISSING)
    st.session_state[key] = value
    if previous is _MISSING or previous == value:
        return
    scroll(name)


def scroll(name: str) -> None:
    """Scroll to `anchor(name)` on this run, whatever the selection did."""
    # the counter only makes the html unique: an identical component is not
    # re-mounted by Streamlit, so the second pick in a row would not scroll
    n = st.session_state.get("_scroll_n", 0) + 1
    st.session_state["_scroll_n"] = n
    components.html(_JS.format(name=name, offset=OFFSET_PX, nonce=n), height=0)


# The anchor is rendered in the same run as this script, but the iframe may run
# before the element is laid out: try a few times, then give up quietly.
_JS = """
<script>
(function () {{
  var nonce = {nonce};
  var tries = 0;
  function go() {{
    var d = window.parent.document;
    var mark = d.getElementById("cmsr-{name}");
    var main = d.querySelector('section.stMain')
            || d.querySelector('[data-testid="stMain"]');
    if (!mark || !main) {{
      if (++tries < 20) setTimeout(go, 50);
      return;
    }}
    // the marker itself is display:none and has no box: measure what follows
    var box = mark.closest('.stElementContainer')
           || mark.closest('[data-testid="stElementContainer"]');
    var el = (box && box.nextElementSibling) || box || mark;
    var top = el.getBoundingClientRect().top
            - main.getBoundingClientRect().top
            + main.scrollTop - {offset};
    main.scrollTo({{top: Math.max(0, top), behavior: "smooth"}});
  }}
  go();
}})();
</script>
"""
