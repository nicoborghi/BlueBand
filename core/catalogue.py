"""The specialità of track cycling, ready to be added to a programme.

Declaring an event used to mean typing seven fields into a grid - the code, the
name, the short name, the UCI abbreviation, the format, how many ride a squadra,
how many start together - and getting any of them wrong is a programme that
runs the wrong machinery. They are the same seven fields at every meeting, so
they live in a table:

    regulations/events.json

    "chilometro": {"fmt": "time_trial", "abbr": "TT",
                   "name":  {"it": "CHILOMETRO DA FERMO", "en": "1 KM TIME TRIAL"},
                   "short": {"it": "Chilometro", "en": "Kilometre"}}

The jury picks one and gets an `Event`; everything about it stays editable in
the Specialità grid afterwards, and an event the table does not know is still
declared there by hand.

The **name is per language**, because it is not a label: it is written into
`programme.yaml` and printed on the sheets exactly as it stands there (see
`core.i18n`). Adding a specialità to an English competition writes the English
name, and it prints in English next year too, whoever opens the file.

Seeded from CITA 26 and extended with the events its programme did not contest.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Event
from .i18n import DEFAULT, language

FILE = Path(__file__).resolve().parent.parent / "regulations" / "events.json"

#: Same convention as the rest of `regulations/`.
META = "_last_updated_"


def load() -> dict[str, Any]:
    """The catalogue, or an empty one when the file is missing or unreadable.

    Missing, the Specialità grid is what it always was: seven fields typed by
    hand. Nothing here is load-bearing enough to take a page down over.
    """
    if not FILE.exists():
        return {}
    try:
        with FILE.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in data.items()
            if k != META and isinstance(v, dict)} if isinstance(data, dict) else {}


def codes() -> list[str]:
    """Every specialità the table knows, in the order it is written in.

    The file's own order and not alphabetical: it runs from the velocità to the
    corse di gruppo, which is how a programme is read and roughly how a
    championship is run.
    """
    return list(load())


def name(code: str, *, short: bool = False) -> str:
    """What a specialità is called, in the language the competition is run in."""
    entry = load().get(code) or {}
    names = entry.get("short" if short else "name") or {}
    if not isinstance(names, dict):
        return str(names or code)
    return str(names.get(language()) or names.get(DEFAULT) or code)


def event(code: str, order: int = 0) -> Event:
    """The specialità as a programme entry, ready to be scheduled.

    Unknown to the table - a specialità somebody invented, or one this file has
    not caught up with - comes back as a bare `Event` under that code, which is
    exactly what the grid would have made of a code typed into it.
    """
    entry = load().get(code)
    if entry is None:
        return Event(code=code, order=order)
    return Event(
        code=code,
        name=name(code),
        short=name(code, short=True),
        abbr=str(entry.get("abbr") or ""),
        fmt=str(entry.get("fmt") or "group"),
        team_size=int(entry.get("team_size") or 0),
        teams_per_start=int(entry.get("teams_per_start") or 2),
        order=order,
    )
