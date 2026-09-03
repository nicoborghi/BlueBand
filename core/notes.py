"""The lines a sheet opens on, decided once and not typed at every meeting.

A comunicato says what the fase it is about qualifies for: *Non si qualificano
per la finale le ultime 2 coppie tra le partenti*, *La prima squadra parte sul
rettilineo d'arrivo*, *Cambio ogni mezzo giro*. They are the same sentences at
every championship - they come out of the regulation, not out of the
programme - and until now they were half hard-coded in the pages that print
them and half typed by hand into the event of every new `programme.yaml`.

Two things live here, and they are different in kind:

**The wording** is a catalogue entry like any other prose in this app
(`core.i18n`), shipped per language and per genere. What this module adds is
that a federation may *rewrite* one: `texts()` is the installation's own
version of any of them, and `apply()` is what puts it in force for the run
(`i18n.set_texts`). Nothing else changes - every page and every sheet goes on
asking `msg` for the key it always asked for.

**Which line goes on which sheet** is the table below: one rule per sentence,
saying the format it belongs to, the fase, the document, and the condition the
regulation puts on it - a 333 m track, two squadre starting together, a
distance that is not a whole number of giri. `for_round` is what reads them.

    regulations/notes.json

    {"rules": [{"key": "note_madison_startlist", "fmt": "madison",
                "round": "heats", "doc": "partenti", "args": {"n": "eliminate"}}],
     "texts": {"it": {"note_madison_startlist": "..."}}}

`rules` ships filled in - it is the regulation - and `texts` ships empty: what
is not rewritten is what the catalogues say. Both are edited in Impostazioni,
which is also why they are one file: they are what holds for the *installation*
and not for the competition, the same way `regulations/events.json` holds
what an event is.

The **numbers are the programme's**. A rule names the field it reads - the
coppie a batteria eliminates, how many a qualification sends to the finals -
and `for_round` fills the placeholder from the fase as the jury typed it. So
the sentence is resolved when the programme is written, and re-proposed when
the number under it changes (`ui.pages.programme`), which is the difference
between a note that says what the fase does and one that used to say it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import (DOC_RESULTS, DOC_STARTLIST, ROUND_SETUP, Competition,
                     ProgrammeItem, Round)
from .formats import sprint as S
from .i18n import CATALOGUES, DEFAULT, catalogue, gendered, msg, set_texts

REGULATIONS = Path(__file__).resolve().parent.parent / "regulations"
FILE = REGULATIONS / "notes.json"

#: Same convention as the rest of `regulations/`.
META = "_last_updated_"


# ── what a fase is, as a rule asks about it ─────────────────────────────────

#: The fase families a rule can name. Not the round keys themselves: the same
#: sentence belongs to the qualificazioni of an inseguimento and of a velocità
#: a squadre, which write that fase under the same word but need not.
QUALIFYING = "qualifying"
FINALS = "finals"
HEATS = "heats"
ROUND1 = "round1"
REPECHAGE = "repechage"
QUARTERS = "quarters"
SEMIFINALS = "semifinals"


def family(key: str) -> str:
    """Which kind of fase a round key is, as the rules name it.

    Read off the key and not off a table, because the key is the programme's
    vocabulary and already says it (`rounds.QUALIFYING`, `formats.sprint`): a
    fase whose key starts with *Qualificazioni* is ridden against the clock
    whoever wrote the file.
    """
    k = (key or "").strip().lower()
    # before the qualificazioni, and not after: the batterie of a madison are
    # written *Qualificazioni Batteria 1* - they qualify for the finale - and
    # what the rules ask about them is that they are batterie
    if "batteria" in k or "heat" in k:
        return HEATS
    if k.startswith("qualif"):
        return QUALIFYING
    if k.startswith("recuper") or k.startswith("repech"):
        return REPECHAGE
    if k.startswith("quart"):
        return QUARTERS
    if k.startswith("semi"):
        return SEMIFINALS
    if k.startswith("finali") or k.startswith("finals"):
        return FINALS
    if k.startswith("turno 1") or k.startswith("round 1"):
        return ROUND1
    if k.startswith("batteria") or k.startswith("heat"):
        return HEATS
    return k


def half_laps(rnd: Round) -> bool:
    """Whether the fase is ridden over half a giro more than a whole number.

    Which is what decides where the second squadra lines up: two of them start
    half a lap apart, so a distance that is a whole number of giri puts the
    first on the finishing straight and one that is not puts it on the other.
    """
    return bool(rnd.laps) and abs(float(rnd.laps) % 1 - 0.5) < 1e-6


def track_metres(comp: Competition) -> int:
    """The track as a rule quotes it: 250, 333, 400."""
    return int(round((comp.track_len or 0) * 1000))


def starts_two(comp: Competition, item: ProgrammeItem, rnd: Round) -> bool:
    """Whether two of them are on the track at once.

    The finali of a pursuit are ridden two against two whatever the
    qualificazione did - that is what a final for the places *is* - so the fase
    decides before the event does.
    """
    if family(rnd.key) in (FINALS, ROUND1, QUARTERS, SEMIFINALS, REPECHAGE):
        return True
    per_start = item.teams_per_start or comp.event(item.event).teams_per_start
    return int(per_start or 0) >= 2


# ── the table ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Rule:
    """One sentence, and where the regulation puts it."""

    key: str                       # the catalogue key of the wording
    doc: str = DOC_STARTLIST       # which sheet it opens
    fmt: str = ""                  # "" = every format
    event: str = ""                # "" = every event of that format
    round: str = ""                # "" = every fase of it (see `family`)
    when: dict[str, Any] = field(default_factory=dict)
    args: dict[str, str] = field(default_factory=dict)

    def wording(self, female: bool) -> str:
        """The key as it is written about the riders in front of the jury."""
        if female and f"{self.key}_f" in catalogue(DEFAULT).MSG:
            return f"{self.key}_f"
        if f"{self.key}_m" in catalogue(DEFAULT).MSG:
            return f"{self.key}_f" if female else f"{self.key}_m"
        return self.key


def _table() -> dict[str, Any]:
    """The file, or an empty table when it cannot be read.

    Missing, every sheet is what the catalogues say and no rule fires: nothing
    here is load-bearing enough to take a page down over, which is the same
    bargain `core.catalogue` makes with its own tables.
    """
    if not FILE.exists():
        return {}
    try:
        with FILE.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def rules() -> list[Rule]:
    """Every rule the table states, in the order it is written in."""
    out = []
    for row in _table().get("rules") or []:
        if not isinstance(row, dict) or not row.get("key"):
            continue
        out.append(Rule(key=str(row["key"]),
                        doc=str(row.get("doc") or DOC_STARTLIST),
                        fmt=str(row.get("fmt") or ""),
                        event=str(row.get("event") or ""),
                        round=str(row.get("round") or ""),
                        when=dict(row.get("when") or {}),
                        args=dict(row.get("args") or {})))
    return out


def texts() -> dict[str, dict[str, str]]:
    """The lines this installation words its own way: {language: {key: text}}."""
    stored = _table().get("texts") or {}
    return {lang: {str(k): str(v) for k, v in (entries or {}).items()}
            for lang, entries in stored.items() if lang in CATALOGUES}


def apply() -> None:
    """Put the installation's own wordings in force for this run."""
    set_texts(texts())


def save_texts(edited: dict[str, dict[str, str]]) -> Path:
    """Write the wordings back, keeping the rules exactly as they are.

    Only what differs from the catalogue is stored. A line edited back to what
    the app ships is not a decision to record - and a table full of the
    defaults would silently stop following a correction to them.
    """
    data = _table()
    kept = {}
    for lang, entries in (edited or {}).items():
        if lang not in CATALOGUES:
            continue
        mine = {k: v.strip() for k, v in (entries or {}).items()
                if v and v.strip() and v.strip() != shipped(k, lang)}
        if mine:
            kept[lang] = mine
    data["texts"] = kept
    FILE.parent.mkdir(parents=True, exist_ok=True)
    with FILE.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    apply()
    return FILE


def shipped(key: str, lang: str) -> str:
    """What the app says for a key in a language, before anybody rewrote it."""
    table = getattr(catalogue(lang), "MSG", {})
    return table.get(key) or getattr(catalogue(DEFAULT), "MSG", {}).get(key, "")


def keys() -> list[str]:
    """Every wording a rule can put on a sheet, plus its genere.

    What the editor in Impostazioni offers: the lines that actually reach a
    comunicato, in the order the rules name them, and never the whole MSG
    catalogue - which is the app talking to the jury, not the jury to the
    riders.

    `wordings` in the table are the ones no rule can name because they are
    *composed* and not picked: a keirin describes its own tournament - how many
    batterie, what each one sends where - out of what the entries make of it,
    which the programme cannot know. The sentence is still a sentence a
    federation may word its own way, so it is offered here with the others.
    """
    out: list[str] = []
    named = [r.key for r in rules()] + list(_table().get("wordings") or [])
    for base in named:
        for key in (base, f"{base}_m", f"{base}_f"):
            if key not in out and key in catalogue(DEFAULT).MSG:
                out.append(key)
    return out


# ── which line a fase gets ──────────────────────────────────────────────────

def _matches(rule: Rule, comp: Competition, item: ProgrammeItem,
             rnd: Round) -> bool:
    ev = comp.event(item.event)
    if rule.fmt and rule.fmt != ev.fmt:
        return False
    if rule.event and rule.event != item.event:
        return False
    if rule.round and rule.round != family(rnd.key):
        return False
    for name, wanted in rule.when.items():
        if _condition(name, comp, item, rnd) != wanted:
            return False
    return True


def _condition(name: str, comp: Competition, item: ProgrammeItem,
               rnd: Round) -> Any:
    """What the programme answers to a condition a rule puts on itself."""
    if name == "track_m":
        return track_metres(comp)
    if name == "half_laps":
        return half_laps(rnd)
    if name == "starts_two":
        return starts_two(comp, item, rnd)
    if name == "direct_final":
        return not any(family(r.key) == QUALIFYING for r in item.rounds)
    if name == "team":
        return bool(comp.event(item.event).team_size)
    if name == "scheme":
        # a velocità that states no scheme rides the one the app proposes: the
        # rule has to fire on it too, or the sheet of the commonest case is the
        # one with nothing on it
        return item.scheme or S.DEFAULT_SCHEME
    return None


def _value(source: str, item: ProgrammeItem, rnd: Round, female: bool) -> Any:
    """What a rule fills a placeholder from.

    A field of the fase as the jury typed it - *how many coppie this batteria
    eliminates* - or, written `word:vincitore`, one of the words a sheet is
    written in about the riders in front of the jury.
    """
    if source.startswith("word:"):
        base = source.split(":", 1)[1]
        return gendered(female, f"{base}_m", f"{base}_f")
    if source.startswith("setup:"):
        # what the race decides before it is ridden is stated on the fase that
        # decides it: how many coppie a madison batteria eliminates is written
        # on the composizione, once, and every batteria announces the same cut
        name = source.split(":", 1)[1]
        setup = next((r for r in item.rounds if r.kind == ROUND_SETUP), None)
        return getattr(setup, name, None) if setup else None
    if hasattr(rnd, source):
        return getattr(rnd, source)
    return getattr(item, source, None)


def for_round(comp: Competition, item: ProgrammeItem,
              rnd: Round) -> dict[str, str]:
    """The lines this fase opens its sheets on: {document: text}.

    Empty where the programme does not state the number the sentence is about:
    a madison batteria that has not said how many coppie it eliminates has
    nothing to announce yet, and a sentence with a hole in it is worse than no
    sentence - it goes out on paper.
    """
    if rnd.kind == ROUND_SETUP:
        return {}
    female = comp.female(item.cat)
    lines: dict[str, list[str]] = {}
    for rule in rules():
        if not _matches(rule, comp, item, rnd):
            continue
        values = {name: _value(src, item, rnd, female)
                  for name, src in rule.args.items()}
        if any(v in (None, 0, "") for v in values.values()):
            continue
        # more than one line can belong to the same sheet - a velocità a
        # squadre on a 333 m track says where the first squadra starts *and*
        # that the change is every half lap - and they go on it in the order
        # the table states them
        text = _text(rule, female, values)
        if text not in lines.setdefault(rule.doc, []):
            lines[rule.doc].append(text)
    return {doc: "\n".join(said) for doc, said in lines.items()}


# ── writing them onto the programme ─────────────────────────────────────────
#
# The lines are *resolved into the file*, not looked up when a sheet prints.
# Which is a choice, and the reason for it is that the jury has to be able to
# read the programme and see what every sheet will say - and to type over it
# where this meeting is not like every other one.
#
# What that costs is that a resolved line can go stale: change how many coppie
# a batteria eliminates and the sentence under it still says two. So a line is
# re-proposed whenever the number it is about moves - unless the jury has
# written its own, which is recognised by its no longer being the one the rules
# resolved before the edit (`before`). Nothing is stored to know it, the same
# bargain `rounds.edited` makes.

#: Which field of a fase carries the line of which document.
FIELDS = {DOC_STARTLIST: "sheet_note", DOC_RESULTS: "results_note"}


def refresh(comp: Competition, item: ProgrammeItem, rnd: Round, *,
            before: dict[str, str] | None = None, force: bool = False) -> bool:
    """Put the resolved lines on one fase. True if any of them moved.

    `before` is what the rules said about this fase *before* whatever edit has
    just been applied: a field still holding that is a field nobody has typed
    over, and it follows the new numbers. `force` writes them whatever they
    say - which is what ↩ Riproponi means.
    """
    want = for_round(comp, item, rnd)
    was = before or {}
    moved = False
    for doc, field_name in FIELDS.items():
        now = getattr(rnd, field_name, "") or ""
        text = want.get(doc, "")
        if not force and now and now != was.get(doc, ""):
            continue                 # the jury wrote this one
        if now != text:
            setattr(rnd, field_name, text)
            moved = True
    return moved


def resolved(comp: Competition, item: ProgrammeItem) -> dict[str, dict[str, str]]:
    """What the rules say about every fase of a race, keyed by round."""
    return {r.key: for_round(comp, item, r) for r in item.rounds}


def refresh_item(comp: Competition, item: ProgrammeItem, *,
                 before: dict[str, dict[str, str]] | None = None,
                 force: bool = False) -> bool:
    """The same for a whole race - what adding one, or re-proposing it, does."""
    was = before or {}
    return any([refresh(comp, item, r, before=was.get(r.key), force=force)
                for r in item.rounds])


def _text(rule: Rule, female: bool, values: dict[str, Any]) -> str:
    key = rule.wording(female)
    if key.endswith(("_m", "_f")):
        return gendered(female, f"{rule.key}_m", f"{rule.key}_f", **values)
    return msg(key, **values)
