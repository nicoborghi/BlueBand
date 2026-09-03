"""How long each race is, and how often it sprints - the table, not the race.

Giri are derived: a distance and a track length give the laps
(`config.laps_from_distance`). The distance itself is not derivable from
anything - it is the regulation, and it differs by categoria: the same scratch
is 4 km for the esordienti and 7.5 for the allievi.

So it is a table, kept where the other regulations are kept:

    regulations/distances.json

    {
      "_last_updated_": "10 August 2026",
      "_laps_per_sprint_": 5,
      "omnium":  {"ES": {"Scratch": 4, "Corsa a Punti": 12},
                  "AL": {"Scratch": 7.5}},
      "madison": {"ES": {"qualificazioni": 8, "final": 16}},
      "ins_squadre": {"AL": {"*": 3}}
    }

Three levels, all matched loosely: **event → categoria → fase**. A fase is
looked up by its own name first, then by the family it belongs to
(`qualificazioni`, `final` - the same two prefixes the rest of the app reads a
round key by), then by `*`, which is "every fase of this event for this
categoria". A categoria of `*` is the same idea one level up: the distance that
holds whoever rides it.

Nothing here is invented. The file ships **seeded from a programme that was
actually run** (`seed`), and the jury corrects it in Impostazioni; an event
the table says nothing about proposes no distance at all, which is a blank
field on the page rather than a wrong number on a sheet.

One number sits beside the table: `_laps_per_sprint_`, how many giri a bunch
race runs between one volata and the next. It is one number and not a column
because that is what the programme it was seeded from says - every madison,
every corsa a punti and every batteria di qualificazione of CITA26 sprints
every fifth lap, over four categorie and three distances. The tempo race is
the exception and keeps its own rule (`config.sprints_from_laps`): it sprints
on every lap from the fifth, which is not an interval at all.

Unlike `penalties.json` and `PUIS.json`, which are the UCI's and are replaced
wholesale, this one is *ours* and is written by the app - hence `save`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .config import (PREFIX_FINALS, PREFIX_QUALIFYING, ROUND_PAUSE, ROUND_SETUP,
                     Competition, sprints_from_laps)
from .formats.group import MADISON, POINTS, TEMPO

FILE = Path(__file__).resolve().parent.parent / "regulations" / "distances.json"

#: The key `decisions.py` writes the date of a regulation under: one convention
#: for the whole `regulations/` folder.
META = "_last_updated_"

#: How many giri a bunch race runs between one volata and the next.
LAPS_PER_SPRINT = "_laps_per_sprint_"

#: Everything at the top level that is not an event.
RESERVED = (META, LAPS_PER_SPRINT)

#: "This one holds for every categoria / every fase."
ANY = "*"

#: The families a fase falls into when it is not named outright. Ordered: a
#: round key is tried against each prefix in turn, so the first match wins.
FAMILIES = (PREFIX_QUALIFYING, PREFIX_FINALS)


def family_of(round_key: str) -> str:
    """The family a fase belongs to ('Qualificazioni Batteria 2' -> 'qualificazioni')."""
    key = (round_key or "").strip().lower()
    return next((f for f in FAMILIES if key.startswith(f)), "")


# ── reading ─────────────────────────────────────────────────────────────────
#
# Read from disk on every lookup, and deliberately not cached: the table is
# edited in the app, and a cache would show the jury the value it has just
# corrected. It is a few kilobytes of JSON.

def load() -> dict[str, Any]:
    """The table, or an empty one when the file is missing or unreadable.

    A missing regulation must not take the page down with it: without the file
    every lookup answers 0.0, which is a blank field and a jury that types the
    distance itself - exactly what it did before this existed.
    """
    if not FILE.exists():
        return {}
    try:
        with FILE.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def updated_at() -> str:
    return str(load().get(META, ""))


def events(table: dict | None = None) -> list[str]:
    """The event the table has an entry for, in alphabetical order."""
    table = load() if table is None else table
    return sorted(k for k, v in table.items()
                  if k not in RESERVED and isinstance(v, dict))


def distance(event: str, cat: str, round_key: str = "",
             table: dict | None = None) -> float:
    """Km this fase is ridden over, 0.0 when the table does not say.

    Falls back the way the table is written: this categoria before every
    categoria, this fase before its family before every fase.
    """
    table = load() if table is None else table
    by_cat = table.get(event)
    if not isinstance(by_cat, dict):
        return 0.0
    for c in (cat, ANY):
        if c not in by_cat:
            continue
        rounds = by_cat[c]
        # a categoria written as one number rather than a mapping of fasi:
        # "ES": 8 is the shorthand for "every fase of the ES", and the file is
        # hand-edited often enough that it is worth reading
        if not isinstance(rounds, dict):
            return _km(rounds)
        for key in _lookups(round_key):
            if key in rounds:
                return _km(rounds[key])
    return 0.0


def _lookups(round_key: str) -> list[str]:
    """The keys a fase is looked for under, most specific first."""
    key = (round_key or "").strip()
    family = family_of(key)
    out = [key, key.lower(), family, ANY]
    return [k for i, k in enumerate(out) if k and k not in out[:i]]


def _km(value: Any) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


# ── how often it sprints ────────────────────────────────────────────────────

def laps_per_sprint(table: dict | None = None) -> float:
    """Giri between one volata and the next, 0.0 when the table does not say."""
    table = load() if table is None else table
    return _km(table.get(LAPS_PER_SPRINT))


#: The bunch races that sprint on a fixed interval. A tempo race is *not* one
#: of them - it sprints on every lap from the fifth - and a scratch has the one
#: volata it finishes on, which `config.sprints_from_laps` already answers.
ON_INTERVAL = (POINTS, MADISON)


def sprints(laps: float, kind: str, table: dict | None = None) -> int:
    """How many volate this many giri hold, for a round of this scoring kind.

    The interval comes from the table; everything the table has nothing to say
    about falls back on what the app has always derived
    (`config.sprints_from_laps`), so a missing regulation is the behaviour of
    yesterday rather than a zero.
    """
    every = laps_per_sprint(table)
    if kind in ON_INTERVAL and every > 0 and laps > 0:
        return int(laps // every)
    return sprints_from_laps(laps, kind)


def seed_laps_per_sprint(comp: Competition) -> float:
    """The interval a programme was actually ridden on, 0.0 when it disagrees.

    Read off every bunch round that states both its giri and its volate. One
    answer or none: an interval that is not the same throughout is not an
    interval, and guessing an average would put a wrong number on a start
    order. The tempo race is left out - it does not sprint on one.
    """
    seen = set()
    for item in comp.programme:
        for rnd in item.rounds:
            if not (rnd.laps and rnd.sprints) or _is_tempo(item, rnd):
                continue
            every = rnd.laps / rnd.sprints
            seen.add(round(every, 3))
    return next(iter(seen)) if len(seen) == 1 else 0.0


def _is_tempo(item, rnd) -> bool:
    """A tempo race, whether it is a prova of an omnium or an event of its own."""
    return TEMPO in (rnd.key or "").strip().lower()


# ── writing ─────────────────────────────────────────────────────────────────

def save(table: dict[str, Any], *, updated: str = "") -> Path:
    """Write the table back, atomically (a half-written regulation is worse)."""
    data = {META: updated or table.get(META, ""),
            LAPS_PER_SPRINT: table.get(LAPS_PER_SPRINT, 0),
            **{k: v for k, v in table.items() if k not in RESERVED}}
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(FILE.suffix + f".tmp{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write("\n")
    os.replace(tmp, FILE)
    return FILE


def seed(comp: Competition) -> dict[str, Any]:
    """Harvest the table out of a programme that has already been run.

    Every fase that states a distance becomes an entry. Where every fase of a
    (event, categoria) is ridden over the same distance the entries
    collapse into one `*`, which is both shorter to read and what the jury
    would have written by hand; where they differ - the qualificazioni and the
    finale of a madison - each family keeps its own line.

    The result is a proposal, like everything else the builder produces: it is
    returned, not written, and Impostazioni shows it before it is saved.
    """
    out: dict[str, dict[str, dict[str, float]]] = {}
    # a fase that is *not* ridden over a declared distance - the eliminazione
    # of an omnium, every fase of a keirin - is what stops the collapse below:
    # "every fase is 4 km" would be a claim the programme never made
    silent: set[tuple[str, str]] = set()
    for item in comp.programme:
        for rnd in item.rounds:
            km = _km(rnd.distance)
            if not km:
                # neither a setup fase nor a pausa is ridden at all
                if rnd.kind not in (ROUND_SETUP, ROUND_PAUSE):
                    silent.add((item.event, item.cat))
                continue
            key = family_of(rnd.key) or rnd.key
            out.setdefault(item.event, {}).setdefault(item.cat, {})[key] = km
    for event, cats in out.items():
        for cat, rounds in cats.items():
            if len(set(rounds.values())) == 1 and (event, cat) not in silent:
                cats[cat] = {ANY: next(iter(rounds.values()))}
    return {LAPS_PER_SPRINT: seed_laps_per_sprint(comp),
            **{k: out[k] for k in sorted(out)}}
