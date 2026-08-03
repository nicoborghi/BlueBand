"""What the commissaires' panel decided, as the secretary writes it down.

A jury decision is not a race result: it is a sentence about a rider, taken at
a moment of the competition, that may or may not end up on a comunicato. Until
now it lived on paper next to the laptop. Here it is one JSON file per
competition, appended to and never rewritten by anything else:

    <competition>/decisions.json

Each entry is numbered from 1, in the order the jury took it, and carries what
the secretary can say without typing it twice - the day, the category, the
event, the bibs, the degree of the penalty - plus the free text, which is the
part that matters and the only one that is required.

Two reference tables come with it, read-only, from `regulations/`:

* `penalties.json` - the UCI wording of the usual track offences, four
  languages, numbered as the UCI numbers them. What goes on the sheet after
  "declassato ...".
* `PUIS.json` - the federal table (*Prontuario Unico Infrazioni Sportive*) of
  what each infringement costs, in three columns of categories. What the jury
  reads before deciding.

Neither is edited by the app: they are the regulations, updated by replacing
the file.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from .store import Store, now_iso

FILE = "decisions.json"

REGULATIONS = Path(__file__).resolve().parent.parent / "regulations"
PENALTIES_FILE = REGULATIONS / "penalties.json"
PUIS_FILE = REGULATIONS / "PUIS.json"

#: The four degrees a penalty is given in, in increasing gravity. The jury
#: writes the letter on the sheet; `i18n.penalty_name` spells it out.
CLASSES = ("A", "B", "C", "D")

#: Keys of the reference files that are metadata, not content.
_META = "_last_updated_"


# ── one decision ────────────────────────────────────────────────────────────

@dataclass
class Decision:
    """One decision of the panel, as it will be read back weeks later."""

    n: int = 0                   # numbered from 1, in the order taken
    ts: str = ""                 # when it was written down
    day: int = 0                 # day of the competition, 0 if it has none
    cat: str = ""
    event: str = ""
    round_key: str = ""
    bibs: str = ""               # as typed: "12" or "12, 15"
    penalty: str = ""            # "" | A | B | C | D
    communique: str = ""         # where it was published, when it was
    text: str = ""               # what was decided - the only required part
    author: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Decision":
        known = {f: d.get(f) for f in cls.__dataclass_fields__ if f in d}
        out = cls(**known)
        out.n = int(out.n or 0)
        out.day = int(out.day or 0)
        return out

    def to_dict(self) -> dict:
        return asdict(self)


# ── the file ────────────────────────────────────────────────────────────────

def load(store: Store) -> list[Decision]:
    """Every decision taken, in the order they were taken."""
    raw = store.read_json(FILE, []) or []
    return sorted((Decision.from_dict(d) for d in raw), key=lambda d: d.n)


def save(store: Store, decisions: list[Decision], *,
         action: str = "save_decisions", actor: str = "") -> None:
    store.write_json(FILE, [d.to_dict() for d in decisions],
                     action=action, actor=actor)


def next_n(decisions: list[Decision]) -> int:
    """The number the next decision takes: one past the highest still on file.

    So deleting the last entry - the mistyped one, which is what gets deleted -
    frees its number again, while deleting one in the middle leaves a gap
    rather than renumbering everything under it. Neither is a comunicato
    number: this is the jury's own log.
    """
    return max((d.n for d in decisions), default=0) + 1


def add(store: Store, decision: Decision, *, actor: str = "") -> Decision:
    """Append a decision, numbering and timestamping it. Returns what was written."""
    current = load(store)
    decision.n = decision.n or next_n(current)
    decision.ts = decision.ts or now_iso()
    save(store, current + [decision], action="add_decision", actor=actor)
    return decision


def update(store: Store, decision: Decision, *, actor: str = "") -> None:
    """Rewrite one decision, keeping its number and its place."""
    save(store, [decision if d.n == decision.n else d for d in load(store)],
         action="edit_decision", actor=actor)


def remove(store: Store, n: int, *, actor: str = "") -> None:
    """Drop one decision, leaving the others where they are (see `next_n`).

    Nothing is lost: the previous file stays in `.snapshots/` like every other
    write, and the deletion is in the journal.
    """
    save(store, [d for d in load(store) if d.n != n],
         action="delete_decision", actor=actor)


# ── the regulations behind it ───────────────────────────────────────────────

@lru_cache(maxsize=None)
def _read(path: Path) -> dict:
    """One reference table, or an empty one when the file is not there.

    Missing regulations must not take the page down with them: the free text
    is what the jury needs, the tables are what saves it typing.
    """
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def updated_at(path: Path) -> str:
    return str(_read(path).get(_META, ""))


def reasons(lang: str = "IT") -> list[tuple[str, str]]:
    """(UCI number, wording) of every offence, in the order of the UCI table.

    Numeric order, not the order of the file and not alphabetical: the numbers
    are what the jury quotes, and 10 comes after 9.
    """
    data = _read(PENALTIES_FILE)
    out = [(str(k), str(v.get(lang) or v.get("EN") or "").strip())
           for k, v in data.items() if k != _META and isinstance(v, dict)]
    return sorted(((k, v) for k, v in out if v),
                  key=lambda r: (int(r[0]) if r[0].isdigit() else 10**6, r[0]))


def reason(number: str, lang: str = "IT") -> str:
    return dict(reasons(lang)).get(str(number), "")


def puis_columns() -> list[str]:
    """The category groups the PUIS gives a column each ('DA, AL, ED, ES')."""
    return [k for k in _read(PUIS_FILE) if k != _META]


def puis_column_for(cats: list[str]) -> str:
    """The column that covers the categories in this competition.

    A championship runs one age group, so one column of the table applies:
    the one naming most of its categories. Nothing matching (or nothing to
    match) falls back to the first column rather than to none - the jury can
    still pick another, and a table on screen beats an empty panel.
    """
    columns = puis_columns()
    if not columns:
        return ""
    wanted = {c.strip().upper() for c in cats if c}
    best, score = columns[0], 0
    for col in columns:
        codes = {p.strip().upper() for p in col.split(",")}
        hits = len(wanted & codes)
        if hits > score:
            best, score = col, hits
    return best


def puis(column: str) -> list[dict]:
    """The rows of one PUIS column: what the infringement is, what it costs."""
    rows = _read(PUIS_FILE).get(column) or []
    return [r for r in rows if isinstance(r, dict)]


def puis_search(column: str, text: str) -> list[dict]:
    """Rows whose infringement or sanction contains `text` (accent-blind enough)."""
    rows = puis(column)
    needle = text.strip().lower()
    if not needle:
        return rows
    return [r for r in rows
            if needle in f"{r.get('infrazione', '')} {r.get('sanzione', '')}".lower()]
