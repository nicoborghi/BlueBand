"""What the commissaires' panel decided, as the secretary writes it down.

A jury decision is not a race result: it is a sentence about a rider, taken at
a moment of the competition, that may or may not end up on a comunicato. Until
now it lived on paper next to the laptop. Here it is one JSON file per
competition, appended to and never rewritten by anything else:

    <competition>/decisions.json

Each entry is numbered from 1, in the order the jury took it, and is a *row of
a register*, not a note: the day, the categoria, the event, la fase, the
dorsale, and the provvedimento with the UCI article it was taken under - `A1`,
`C3` - which together are the compact code the jury quotes. On top of those
columns sits the free text, which is the sentence that goes out to the teams:
`compose` proposes it from the columns, the jury edits it.

Filled in that way the log is readable both ways round: `by_round` gives what
was decided in each fase of an event - the recap the panel wants in front
of it before filing the next one - and the sheet of a race prints its own
decisions, tinted by `KINDS`, without anybody retyping them.

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
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from .i18n import msg, penalty_name
from .store import Store, now_iso

FILE = "decisions.json"

REGULATIONS = Path(__file__).resolve().parent.parent / "regulations"
PENALTIES_FILE = REGULATIONS / "penalties.json"
PUIS_FILE = REGULATIONS / "PUIS.json"

#: The four degrees a penalty is given in, in increasing gravity. The jury
#: writes the letter on the sheet; `i18n.penalty_name` spells it out.
CLASSES = ("A", "B", "C", "D")

#: The degree that is an *ammonizione*: the warning a rider carries with her.
#: It is the one penalty that outlives the race it was given in - see
#: `warned_bibs` - and the one that counts twice over (`double_warned`).
WARNING = "A"

#: What a decision *is*, for whoever has to colour it: the provvedimento, or
#: `NOTE` when the jury wrote something that sanctions nobody (how a torneo was
#: run, who is qualified). The comunicato tints the block by this and nothing
#: else - see `render.render.Note` and `Branding.note_colors`.
NOTE = "note"
KINDS = {"A": "warning", "B": "fine", "C": "relegation", "D": "disqualification"}

#: Every kind a block on a sheet can have, in the order the settings list them:
#: the four provvedimenti from the gravest down, then the plain note.
NOTE_KINDS = ("disqualification", "relegation", "fine", "warning", NOTE)

#: Keys of the reference files that are metadata, not content.
_META = "_last_updated_"


# ── one decision ────────────────────────────────────────────────────────────

@dataclass
class Decision:
    """One decision of the panel, as it will be read back weeks later.

    Every field but `text` is a *column*: the categoria, the event, the
    fase, the dorsale, the provvedimento and the UCI article it was taken
    under. They are what makes the log a register rather than a pile of notes -
    filtered, summarised per event, and printed on the sheet of the race
    they belong to without anybody retyping them.

    `text` is the sentence that goes out to the teams. The app proposes it
    (`compose`), the jury edits it: what the panel actually decided is never
    something the machine gets to have the last word on.
    """

    n: int = 0                   # numbered from 1, in the order taken
    ts: str = ""                 # when it was written down
    day: int = 0                 # day of the competition, 0 if it has none
    cat: str = ""
    event: str = ""
    round_key: str = ""
    bibs: str = ""               # as typed: "12" or "12, 15"
    penalty: str = ""            # "" | A | B | C | D
    reason: str = ""             # the UCI article number: "1", "6", "13"
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

    @property
    def code(self) -> str:
        """The compact UCI code - `A1`, `C3` - or '' when it is a plain note.

        Provvedimento and article in three characters: it is what fits in a
        column of the register, what the jury quotes on the radio, and what
        the sheet prints next to the dorsale.
        """
        return f"{str(self.penalty).upper().strip()}{str(self.reason).strip()}"

    @property
    def kind(self) -> str:
        """What this is, for whoever has to colour it (`KINDS`)."""
        return KINDS.get(str(self.penalty).upper().strip(), NOTE)


def parse_code(code: str) -> tuple[str, str]:
    """`'C3'` -> `('C', '3')`. Anything else comes back as much as is there."""
    m = re.match(r"\s*([A-Da-d])?\s*(\d+)?\s*$", str(code or ""))
    if not m:
        return "", ""
    return (m.group(1) or "").upper(), m.group(2) or ""


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


# ── ammonizioni: the decision that travels ──────────────────────────────────
#
# Every other penalty is spent on the race it was given in. An ammonizione is
# not: it stays on the rider for the whole event, is read again on the
# sheet of every fase that follows, and a second one taken in the same fase is
# a squalifica. So it is the one decision the sheets have to ask the log about,
# and this is where they ask.


def bibs_of(decision: Decision) -> list[int]:
    """The numbers one decision is about, as numbers.

    The field is typed by hand ("12, 15", "12 e 15"): anything that is not a
    number in it is not a dorsale, and a decision the jury wrote about nobody
    in particular is about nobody in particular.
    """
    return [int(n) for n in re.findall(r"\d+", str(decision.bibs or ""))]


def warnings_of(decisions: list[Decision], cat: str, event: str
                ) -> list[Decision]:
    """The ammonizioni given in one event of one categoria, in order."""
    return [d for d in decisions
            if str(d.penalty).upper() == WARNING
            and (not d.cat or not cat or d.cat == cat)
            and d.event == event]


def warned_bibs(decisions: list[Decision], cat: str, event: str, *,
                rounds: list[str] = (), upto: str = "") -> dict[int, str]:
    """dorsale -> the fase the warning was taken in, for one event.

    What the sheets print the W from. `rounds` is the fasi in the order they
    are ridden and `upto` the one being printed: a warning shows on the fasi
    that *follow* the one it was given in, and not on that one. The sheet of
    the race where it was taken says what happened in that race - the decision
    itself goes on it, in the Decisione note - and a W there would be the same
    thing said twice; what the W is for is the next race, where nothing else
    would say that this rider is already carrying one.

    Without an order to read (a warning filed against no fase, a round that is
    not in the programme) it counts everywhere: the jury wrote it down about
    this event, and losing it would be worse than showing it early.
    """
    order = {key: i for i, key in enumerate(rounds)}
    limit = order.get(upto)
    out: dict[int, str] = {}
    for d in warnings_of(decisions, cat, event):
        taken = order.get(d.round_key)
        if limit is not None and taken is not None and taken >= limit:
            continue
        for bib in bibs_of(d):
            out.setdefault(bib, d.round_key)
    return out


def double_warned(decisions: list[Decision], cat: str, event: str,
                  round_key: str) -> list[int]:
    """Who has taken two ammonizioni in the same fase: that is a squalifica.

    Reported, not applied: the DSQ is the panel's to declare, and the app says
    which numbers it is now looking at.
    """
    seen: dict[int, int] = {}
    for d in warnings_of(decisions, cat, event):
        if d.round_key != round_key:
            continue
        for bib in bibs_of(d):
            seen[bib] = seen.get(bib, 0) + 1
    return sorted(b for b, n in seen.items() if n > 1)


# ── reading the log back, per race ──────────────────────────────────────────
#
# The register is one file for the whole competition, but it is *read* one
# event at a time: what was decided in this categoria, in this evento, in
# each of its fasi. That is the summary the jury wants above the button before
# it files the next one, and it is what the sheet of a race prints.


def for_race(decisions: list[Decision], cat: str, event: str,
             round_key: str | None = None) -> list[Decision]:
    """The decisions taken in one race - or in one whole event.

    `round_key=None` is the event (every fase of it); a string, including
    `""`, is that fase and only that one. The difference matters: `""` is a
    real fase key - an event ridden in one go - and must not silently
    widen to everything the categoria did in that evento.
    """
    return [d for d in decisions
            if d.cat == cat and d.event == event
            and (round_key is None or d.round_key == round_key)]


def by_round(decisions: list[Decision], cat: str, event: str,
             rounds: list[str] = ()) -> list[tuple[str, list[Decision]]]:
    """(fase, decisions taken in it) for one event, in programme order.

    `rounds` is the fasi as the programme runs them: they come out in that
    order, and a fase nobody was penalised in does not appear at all. Anything
    filed against a fase the programme does not know - a key edited by hand, a
    round dropped from the programme afterwards - is kept, at the end, rather
    than quietly lost.
    """
    mine = for_race(decisions, cat, event)
    order = {key: i for i, key in enumerate(rounds)}
    groups: dict[str, list[Decision]] = {}
    for d in mine:
        groups.setdefault(d.round_key, []).append(d)
    return sorted(groups.items(),
                  key=lambda kv: (order.get(kv[0], len(order)), kv[0]))


def counts(decisions: list[Decision]) -> dict[str, int]:
    """How many of each kind, for the one-line recap ({'warning': 2, ...})."""
    out: dict[str, int] = {}
    for d in decisions:
        out[d.kind] = out.get(d.kind, 0) + 1
    return out


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


# ── the sentence the jury signs ─────────────────────────────────────────────

def compose(who: str, penalty: str = "", number: str = "",
            lang: str = "IT") -> str:
    """The decision as it goes out: '<who>: AMMONIZIONE (A) <UCI wording>'.

    A *proposal*, and nothing more. It is the wording the jury would have
    written by hand - the rider named as the sheets name her, the provvedimento
    spelled out with its letter, the article quoted verbatim from the UCI table
    - and the field it lands in is editable, because the panel decides what it
    decided and the app does not.

    Every part is optional and an absent one leaves no trace: a decision about
    nobody in particular, with no provvedimento, quoting no article, composes
    to the empty string and the jury types it.
    """
    line = " ".join(p for p in (
        msg("penalty_for", who=who) if who else "",
        f"{penalty_name(penalty).upper()} ({penalty})" if penalty else "",
        reason(number, lang) if number else "") if p)
    # the UCI table punctuates some of its articles and not others: the sheet
    # is not the place to notice it, so a quoted one ends as a sentence either
    # way. Only after an article - "AL 3:" on its own is a line still being
    # written, not a sentence missing its stop.
    return f"{line}." if number and line and not line.endswith(".") else line
