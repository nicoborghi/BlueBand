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

`regulations/categories.json` is the same table for the categorie - the sigle a
FCI programme is written in - read through `category_codes`, `category_name`
and `category`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Category, Event
from .i18n import DEFAULT, language

REGULATIONS = Path(__file__).resolve().parent.parent / "regulations"
FILE = REGULATIONS / "events.json"
CATEGORIES_FILE = REGULATIONS / "categories.json"

#: Same convention as the rest of `regulations/`.
META = "_last_updated_"


def _table(path: Path) -> dict[str, Any]:
    """One `regulations/` table, or an empty one when it cannot be read.

    Missing, the grid it feeds is what it always was: fields typed by hand.
    Nothing here is load-bearing enough to take a page down over.
    """
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in data.items()
            if k != META and isinstance(v, dict)} if isinstance(data, dict) else {}


def load() -> dict[str, Any]:
    """The catalogue of specialità."""
    return _table(FILE)


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


#: What the table states about a specialità, as opposed to what a programme
#: does. The *name* is not in it: a name is printed on every sheet and belongs
#: to the meeting that wrote it (see the module docstring). These are the
#: technical facts - the ones that are the same at every championship and have
#: no business being retyped into every file.
FIELDS = ("abbr", "fmt", "team_size", "teams_per_start", "entry_columns")


def event_fields(code: str) -> dict[str, Any]:
    """What the table says about a specialità, ready to be merged under a file.

    Only what it actually states: a key the table is silent about is left to
    the dataclass default, so adding a field to `Event` does not turn every
    catalogue entry into a statement about it.
    """
    entry = load().get(code)
    if entry is None:
        return {}
    out: dict[str, Any] = {}
    for name in FIELDS:
        if entry.get(name) is not None:
            out[name] = entry[name]
    return out


def save(table: dict[str, Any]) -> Path:
    """Write the catalogue back, keeping the note at the top of the file."""
    data = {}
    if FILE.exists():
        try:
            with FILE.open(encoding="utf-8") as fh:
                was = json.load(fh)
            data[META] = was.get(META, "")
        except (OSError, json.JSONDecodeError):
            pass
    data.update(table)
    FILE.parent.mkdir(parents=True, exist_ok=True)
    with FILE.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return FILE


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


# ── the categorie ───────────────────────────────────────────────────────────
#
# Same idea, same shape, other table:
#
#     regulations/categories.json
#
#     "AL": {"sex": "M", "name": {"it": "ALLIEVI MASCHI", "en": "U17 MEN"}}
#
# The sigle are the ones the FCI programmes are written in - ES/ED, AL/DA,
# JU/DJ, UN/DU - and they are what the jury types anyway; ticking them beats
# keying four fields eight times. A meeting with categorie of its own still
# declares them by hand in the grid, and anything added from here stays
# editable there.

def category_codes() -> list[str]:
    """Every categoria the table knows, in the order it is written in.

    The file's order and not alphabetical: it runs from the youngest to the
    oldest, alternating maschile and femminile, which is the order a programme
    is read in.
    """
    return list(_table(CATEGORIES_FILE))


def category_name(code: str) -> str:
    """What a categoria is called, in the language the competition is run in."""
    entry = _table(CATEGORIES_FILE).get(code) or {}
    names = entry.get("name") or {}
    if not isinstance(names, dict):
        return str(names or code)
    return str(names.get(language()) or names.get(DEFAULT) or code)


def category(code: str, order: int = 0) -> Category:
    """The categoria as a programme entry, ready to be raced.

    Unknown to the table comes back as a bare `Category` under that code -
    exactly what the grid would have made of a code typed into it.
    """
    entry = _table(CATEGORIES_FILE).get(code)
    if entry is None:
        return Category(code=code, order=order)
    return Category(code=code, name=category_name(code),
                    sex=str(entry.get("sex") or ""), order=order)
