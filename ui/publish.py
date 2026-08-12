"""How a batch of documents leaves the app - one way, for both halves of Documenti.

*Elenchi iscritti* and *Serie di documenti* are two different jobs: the first
prints who is entered, the second prints the sheets of races. What they do with
what they have built is the same thing, and it was written twice - how many
documents there are, the button that saves them, and the preview underneath.
Twice means the two drifted: one said how many sheets it was about to write and
the other did not, one signed and the other could not.

    publish.batch(docs, comp, store, key="pa", signature=sign)

One line at the foot of both pages. The save is the primary button, as it is
everywhere (`ui.download.save_button`), and the preview is the same HTML the
PDF is made of, without the letterhead - on screen that would only push the
table below the fold.
"""

from __future__ import annotations

import streamlit as st

from core.config import Competition
from core.i18n import plural, ui
from core.store import Store
from render.render import SIG_PREVIEW_PX, suffix_titles, to_html
from ui.download import save_button


def batch(docs: list, comp: Competition, store: Store, *, key: str,
          number: str = "", label: str = "", signature: bool = False,
          landscape: bool = False, suffix: str = "",
          preview: bool = True) -> None:
    """Say how many, offer to save them, and show what will come out.

    `landscape` and `suffix` are applied here rather than by the caller: they
    are the last two things done to a document before it is written, and doing
    them in one place is what stops a page forgetting one of them.
    """
    for doc in docs:
        doc.landscape = landscape
    suffix_titles(docs, suffix)

    c1, c2, _ = st.columns([1, 1, 4], vertical_alignment="bottom")
    c1.caption(ui("print_hint", n=len(docs),
                  what=ui(plural(len(docs), "document_one", "document_many"))))
    save_button(store, docs, comp, number=number, key=key, label=label,
                signature=signature, container=c2)
    if preview:
        st.html(to_html(docs, comp, banner=False, signature=signature,
                        footer=False, css=False,
                        sig_px=SIG_PREVIEW_PX if signature else 0))
