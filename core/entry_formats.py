"""How an entry file is read - one entry per shape the federation sends.

The elenco iscritti does not arrive in one shape. The federal system exports a
flat list (`Iscritti_NNNNNN.xls`, one row per rider, the *ksport* format); a
meeting that has been run before sends back the workbook this app writes, with
a sheet per categoria and a column per event. Both are read here, and a
third will be a block in a table rather than a branch in the code:

    regulations/entry_formats.json

What a format states is where its columns are and what they are called - the
mapping that used to have to be written into the `entries:` block of every new
`programme.yaml` before anything could be imported at all. A competition that
*does* state it still wins: a federation that renames a column next year is a
line in that file, not a new format.

    codes()                 the formats, in the order the table lists them
    name(code)              what one is called, in the language in force
    layout(code)            {header_row, first_data_row, columns, ksport, ...}
    applied(comp, code)     the competition with that layout filled in
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dataclasses import replace

from .config import Competition
from .i18n import DEFAULT, language

REGULATIONS = Path(__file__).resolve().parent.parent / "regulations"
FILE = REGULATIONS / "entry_formats.json"

#: The format an elenco arrives in unless somebody says otherwise.
KSPORT = "ksport"

#: The one this app writes, and reads back: a sheet per categoria, the
#: header on the first row.
MASTER = "master"

#: What `layout` answers with, and what a competition may state for itself.
FIELDS = ("header_row", "first_data_row", "columns", "ksport", "check_in")


def _table() -> dict[str, Any]:
    """The file, or an empty table when it cannot be read.

    Missing, an import falls back on what the programme states about its own
    file, which is how every competition worked before this table existed.
    """
    if not FILE.exists():
        return {}
    try:
        with FILE.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def codes() -> list[str]:
    """Every format the table knows, in the order it is written in."""
    return list((_table().get("formats") or {}))


def default() -> str:
    """The one an import opens on."""
    return str(_table().get("default") or KSPORT)


def name(code: str) -> str:
    """What a format is called, in the language the competition is run in."""
    entry = (_table().get("formats") or {}).get(code) or {}
    names = entry.get("name") or {}
    if not isinstance(names, dict):
        return str(names or code)
    return str(names.get(language()) or names.get(DEFAULT) or code)


def is_flat(code: str) -> bool:
    """Whether the file is one row per rider, or a sheet per categoria."""
    entry = (_table().get("formats") or {}).get(code) or {}
    return bool(entry.get("flat"))


def layout(code: str) -> dict[str, Any]:
    """Where the columns of that format are, and what they are called."""
    entry = (_table().get("formats") or {}).get(code) or {}
    return {f: entry[f] for f in FIELDS if entry.get(f) is not None}


def applied(comp: Competition, code: str) -> Competition:
    """The competition read with that format's layout under its own.

    Under and not over: a programme that names its columns has been made to
    match a file somebody actually received, and that always wins. What the
    format supplies is the part nobody has written down - which, for a
    competition being set up, is all of it.

    A mapping is taken **whole**: a competition that states one is describing a
    file it has in front of it, and the table's answer for the same field is
    about a different file. Merging the two key by key left a mapping with two
    headers pointing at one field, and the import took whichever came first in
    the file.
    """
    values = layout(code)
    if not values:
        return comp
    sheet = comp.entry_sheet
    # whether the programme says anything at all about its own file. The row
    # numbers cannot answer it themselves: they have a default, and a default
    # is not a statement - a competition that has never mentioned its entry
    # file would otherwise be read as insisting on the header being on row 6.
    stated = bool(sheet.columns or sheet.ksport)
    merged = {"mapped": bool(sheet.ksport)}
    for field_name, value in values.items():
        mine = getattr(sheet, field_name, None)
        if isinstance(value, dict):
            # **whole, or not at all.** A mapping is a statement about one
            # file, and half of it read off this file plus half inherited from
            # the table is not a mapping of either: a competition that says
            # `Note -> region` would go on carrying the table's `Regione ->
            # region` beside it, and which of the two columns the import took
            # would come down to their order in the file.
            merged[field_name] = dict(mine) if mine else dict(value)
        elif not stated:
            merged[field_name] = value
    return replace(comp, entry_sheet=replace(sheet, **merged))
