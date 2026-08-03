"""How the app says something, in one place.

Before this the same kind of remark came out four different ways: a warning
with an icon here and without one there, an error in bold on one page and plain
on the next, a finding printed as `st.error` in Verifica and as `st.warning` in
Gare. One thing said one way is what makes a jury read it - and what makes the
difference between "look at this" and "fix this" mean anything.

The rules, once:

* **error**   something to fix before the sheet goes out.   Red, ⛔.
* **warn**    something to look at.                         Yellow, ⚠.
* **info**    what to do next, or why a page is empty.      Blue, ℹ.
* **ok**      a thing that happened.                        Green, ✓.
* **flag**    the short red mark under the field it is about, with the one
              legend of `i18n.HELP["flags"]` behind its tooltip.
* **toast**   a save. Never anything the jury has to act on: a toast goes away.

The text is always a key of `core.i18n.MSG`; the helpers take the key and its
values, so no Italian is written here either.
"""

from __future__ import annotations

from typing import Iterable

import streamlit as st

from core.checks import ERROR, INFO, WARN, Issue
from core.i18n import code_name, help_text, msg

ICON_ERROR = ":material/error:"
ICON_WARN = ":material/warning:"
ICON_INFO = ":material/info:"
ICON_OK = ":material/check_circle:"
ICON_SAVE = ":material/save:"


def _box(where):
    return where if where is not None else st


def error(key: str, *, where=None, **kwargs) -> None:
    """Something the jury has to fix."""
    _box(where).error(msg(key, **kwargs), icon=ICON_ERROR)


def warn(key: str, *, where=None, **kwargs) -> None:
    """Something to look at, that does not stop the work."""
    _box(where).warning(msg(key, **kwargs), icon=ICON_WARN)


def info(key: str, *, where=None, **kwargs) -> None:
    """What to do next, or why there is nothing on the page."""
    _box(where).info(msg(key, **kwargs), icon=ICON_INFO)


def ok(key: str, *, where=None, **kwargs) -> None:
    """Something that has just happened and stays on the page."""
    _box(where).success(msg(key, **kwargs), icon=ICON_OK)


def saved(key: str, **kwargs) -> None:
    """Something that has just happened and does not need reading twice."""
    st.toast(msg(key, **kwargs), icon=ICON_SAVE)


def text(body: str, level: str = WARN, *, where=None) -> None:
    """Show wording that is already composed (a message from `core/`).

    The scoring and the entry-list validation return their warnings as strings,
    already translated: this puts them on the page with the same look as
    everything else rather than each caller picking a box of its own.

    The default level is WARN because that is what these are - a scoring
    warning, a problem in the programme. Pass the level for the other two.
    """
    box = _box(where)
    {ERROR: lambda: box.error(body, icon=ICON_ERROR),
     INFO: lambda: box.info(body, icon=ICON_INFO),
     }.get(level, lambda: box.warning(body, icon=ICON_WARN))()


def flag(mark: str, *, where=None) -> None:
    """The short red mark under the field it is about (see `core.checks`).

    Under the field and not in a column of its own: a column for it would take
    width off every line for a mark that is usually not there. The tooltip
    carries the one legend that explains the whole notation.
    """
    if not mark:
        return
    _box(where).caption(f":red[{mark}]", help=help_text("flags"))


def issues(items: Iterable[Issue], *, where=None) -> None:
    """A list of findings, errors first - the shape Verifica has always had."""
    items = list(items)
    box = _box(where)
    for i in [i for i in items if i.level == ERROR]:
        box.error(f"**{code_name(i.code)}** · {i.message}", icon=ICON_ERROR)
    for i in [i for i in items if i.level != ERROR]:
        box.warning(f"**{code_name(i.code)}** · {i.message}", icon=ICON_WARN)
