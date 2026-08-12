"""Session wiring: the competition config, the store and the entry list.

Kept thin on purpose - everything below `core/` is pure python and testable;
this module is the only place that knows about `st.session_state`.
"""

from __future__ import annotations

from dataclasses import fields, replace

import streamlit as st

from core import entries as E
from core.i18n import msg, set_language, set_overrides, ui
from core.config import Competition, load_competition, validate
from core.store import (Store, competitions_root, current_competition,
                        list_competitions, open_competition,
                        set_current_competition)

PROGRAMME = "programme.yaml"

# Branding chosen on this machine (Impostazioni) instead of in the programme:
# the letterhead and the footer strip change venue every year, the signature
# changes with the jury president.
BRANDING_SETTINGS = ("signature", "header_img", "footer_img",
                     "signature_mode", "signature_name", "signature_scope",
                     "name_style", "name_width", "note_colors",
                     "decision_codes")

# What a squadra is here and what it is called: the programme states the rule,
# this machine can override it (Impostazioni → Squadra).
ENTRY_SETTINGS = ("team_group", "team_name")

#: Where the language of this competition is stored (Impostazioni → Lingua).
#: Unset - which is every competition set up before it could be chosen - is the
#: language the app was written in.
LANGUAGE = "language"


@st.cache_data(show_spinner=False)
def _load(path: str, mtime: float) -> Competition:
    """The programme, cached until the file changes.

    `mtime` is part of the cache key and must not be named `_mtime`: Streamlit
    leaves out of the key every argument whose name starts with an underscore,
    so with that spelling the programme was cached on its *path alone* - edited
    on disk, it went on being served from the first read until the process was
    restarted. Which is what the Programma page saves it for.
    """
    return load_competition(path)


def _stale_free(path: str, mtime: float) -> Competition:
    """The cached programme, re-read when the code has moved on under it.

    `st.cache_data` keeps the object across a hot reload, and it restores it
    without running `__init__`: a field added to `Branding` (or to any other
    part of the programme) since the object was cached is simply *not there* on
    the instance, and the next `dataclasses.replace` raises AttributeError on a
    running app - at the track, on a page that was working a minute ago.

    So the cached object is checked against the dataclasses as they are now,
    and a programme older than the code is dropped and read again. One `hasattr`
    per field of three small dataclasses, once per rerun; the alternative is
    telling the jury to restart the app.
    """
    comp = _load(path, mtime)
    if _complete(comp):
        return comp
    _load.clear()
    return _load(path, mtime)


def _complete(comp: Competition) -> bool:
    """Whether a cached programme still carries every field the code expects."""
    return all(hasattr(obj, f.name)
               for obj in (comp, comp.branding, comp.entry_sheet, comp.quotas)
               for f in fields(obj))


def competition(name: str) -> Competition | None:
    """The programme, with the local overrides from Impostazioni applied.

    The cached object is never mutated: the overrides land on a copy, so a
    signature chosen on this machine does not leak into another competition.
    """
    p = competitions_root() / name / PROGRAMME
    if not p.exists():
        return None
    settings = open_competition(name).settings
    # first, and before anything reads a word: everything below this line -
    # `validate`, the sidebar, the page that follows - looks up its prose in
    # the catalogue of whatever is set here
    set_language(settings.get(LANGUAGE))
    comp = _stale_free(str(p), p.stat().st_mtime)
    # an empty value is not a choice - a signature never set must not blank the
    # one the programme carries - but False *is* one: a tick taken off in
    # Impostazioni has to win over a programme that turns it on
    over = {k: settings[k] for k in BRANDING_SETTINGS
            if settings.get(k) or isinstance(settings.get(k), bool)}
    if over:
        comp = replace(comp, branding=replace(comp.branding, **over))
    over = {k: settings[k] for k in ENTRY_SETTINGS if settings.get(k)}
    if over:
        comp = replace(comp, entry_sheet=replace(comp.entry_sheet, **over))
    # every sheet calls the squadra by the word chosen for this competition,
    # so it is set once here rather than passed down to each builder
    set_overrides({"team": comp.team_name, "team_en": comp.team_name})
    return comp


def selected_competition() -> str | None:
    """The competition set in Impostazioni - chosen once, not on every page.

    `None` means there is not one to choose: a data folder with nothing in it,
    which is what a new installation is. The caller offers to create the first
    one (`ui.pages.setup`); saying so in the sidebar and stopping, which is
    what this did, left nowhere to say it *to*.
    """
    return current_competition() if list_competitions() else None


def choose_competition(name: str) -> None:
    set_current_competition(name)
    _load.clear()
    st.rerun()


def store(name: str) -> Store:
    return open_competition(name)


def entry_list(name: str, comp: Competition):
    """(EntryList, stale-patch messages). None when nothing imported yet."""
    return E.effective_entries(store(name), comp)


def refresh() -> None:
    """Drop cached data after a write."""
    _load.clear()
    st.rerun()


def sticky_select(container, label: str, options: list, key: str, saved=None,
                  **kwargs):
    """A selectbox that keeps its pick without fighting the jury.

    The value lives in the session and nowhere else: `saved` only seeds it,
    before the widget exists. Passing `index=` on every run is what made every
    pick bounce back - Streamlit re-initialises a keyed widget when its default
    changes, so a pick was kept and the next one thrown away, alternately.

    It also states what a *dependent* picker does when the list under it
    changes: a specialità held in the session that the new categoria does not
    contest is replaced here, in the open, rather than left to whatever the
    widget would do with a value that is no longer on offer.
    """
    if st.session_state.get(key) not in options:
        st.session_state[key] = saved if saved in options else options[0]
    return container.selectbox(label, options, key=key, **kwargs)


# The competition line is the only thing that says which event is loaded, so it
# is set in full contrast rather than in the muted caption grey.
_HEADER_CSS = """
<style>
.cmsr-competition { line-height: 1.25; margin: 0 0 .35rem 0; }
.cmsr-competition .name {
    color: var(--text-color);
    font-weight: 700;
    font-size: 0.86rem;
    letter-spacing: .1px;
}
.cmsr-competition .place {
    color: var(--text-color);
    opacity: .85;
    font-size: 0.8rem;
}
</style>
"""


def sidebar_header(comp: Competition | None) -> None:
    if comp is None:
        return
    st.sidebar.markdown(
        f'{_HEADER_CSS}<div class="cmsr-competition">'
        f'<div class="name">{comp.name}</div>'
        f'<div class="place">{comp.location}</div></div>',
        unsafe_allow_html=True)
    problems = validate(comp)
    if problems:
        with st.sidebar.expander("⚠ " + ui("programme_problems",
                                                 n=len(problems))):
            for p in problems:
                st.write("-", p)
