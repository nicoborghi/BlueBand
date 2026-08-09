"""Write `programme.yaml` back out, and check it before it is written.

The programme is the one file that decides everything about a competition:
track, categories, which events each contests, the rounds of every event with
their distances, and the register of comunicati. Until now it was written by
hand. This module is the other direction - a `Competition` back to the text -
so the Programma page can edit it and so that next year is a copy of this
year's file with a few lines changed.

**The layout is ours, and it is stable.** `yaml.safe_dump` would reflow the
whole file on every save and lose the hand-written comments; a generated layout
that never moves is what makes a diff readable and a copy-paste possible. The
notes that used to be comments have fields of their own (`note:` on a
programme item, on a round), so they survive a round trip like everything else.

The guarantee this module owes, and the one its test checks on the real
championship file: **loading a programme, writing it out and loading it again
gives back the same `Competition`.** Everything else here depends on that.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .checks import ERROR, INFO, WARN, Issue
from .config import (DOC_ALL_KINDS, DOC_CLASSIFICATION, DOC_RESULTS,
                     DOC_STARTLIST, EVENT_ENTRY_LIST, ROUND_SETUP,
                     Category, CommuniqueSpec, Competition, Event,
                     ProgrammeItem, Round, Sheet, load_competition)
from .i18n import msg

INDENT = "  "

# ── scalars ─────────────────────────────────────────────────────────────────

#: A string that can be written without quotes: no leading indicator, no `: `,
#: no ` #`, and not something YAML would read back as a number, a bool or null.
_PLAIN = re.compile(r"^[A-Za-z_][\w .'/()\u00c0-\u024f-]*$")
_RESERVED = {"true", "false", "yes", "no", "on", "off", "null", "none", "~"}


def scalar(value: Any) -> str:
    """One YAML value, quoted exactly when it has to be."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # 3.0 is a distance, not an integer: keep the point, drop the noise
        return repr(round(value, 6)).rstrip("0").rstrip(".") or "0"
    text = str(value)
    if (text and _PLAIN.match(text) and text.lower() not in _RESERVED
            and not text.endswith(" ")):
        return text
    escaped = (text.replace("\\", "\\\\").replace('"', '\\"')
               .replace("\n", "\\n").replace("\t", "\\t"))
    return f'"{escaped}"'


def flow(pairs: list[tuple[str, Any]]) -> str:
    """`{key: value, other: value}` - the one-line form the file is read in."""
    return "{" + ", ".join(f"{k}: {scalar(v)}" for k, v in pairs) + "}"


def flow_list(values: list[Any]) -> str:
    return "[" + ", ".join(scalar(v) for v in values) + "]"


def _kept(obj, *names) -> list[tuple[str, Any]]:
    """(name, value) for the attributes that are set - defaults are not written.

    A round that takes its laps from the track length says nothing about laps:
    writing the derived value back would freeze it, and a track of another
    length would then be silently wrong.
    """
    out = []
    for name in names:
        value = getattr(obj, name)
        if value not in (None, "", [], {}, False):
            out.append((name, value))
    return out


# ── sections ────────────────────────────────────────────────────────────────

def _block(key: str, lines: list[str]) -> list[str]:
    return [f"{key}:", *lines] if lines else []


def _mapping(key: str, data: dict[str, Any], *, level: int = 1) -> list[str]:
    """A plain nested mapping, one key per line."""
    pad = INDENT * level
    return [f"{pad}{scalar(k)}: {scalar(v)}" for k, v in data.items()]


def _competition_head(comp: Competition) -> list[str]:
    out = [f"name: {scalar(comp.name)}"]
    for name, value in (("short", comp.short), ("id", comp.race_id),
                        ("location", comp.location)):
        if value:
            out.append(f"{name}: {scalar(value)}")
    if comp.dates:
        out.append(f"dates: {flow_list(comp.dates)}")
    out.append(f"track_len: {scalar(comp.track_len)}")
    return out


def _entries(comp: Competition) -> list[str]:
    e = comp.entry_sheet
    if not (e.source or e.columns or e.ksport or e.check_in):
        return []
    out = ["entries:"]
    if e.source:
        out.append(f"{INDENT}source: {scalar(e.source)}")
    out.append(f"{INDENT}header_row: {e.header_row}")
    out.append(f"{INDENT}first_data_row: {e.first_data_row}")
    out.append(f"{INDENT}team_group: {e.team_group}")
    if e.team_name:
        out.append(f"{INDENT}team_name: {scalar(e.team_name)}")
    # the deroga that lets two rappresentative ride as one squadra: written
    # back, or pressing Salva would quietly undo it
    if e.team_merge:
        out.append(f"{INDENT}team_merge:")
        out += _mapping("", e.team_merge, level=2)
        if e.team_merge_events:
            out.append(f"{INDENT}team_merge_events: "
                       f"{flow_list(e.team_merge_events)}")
    for name, table in (("columns", e.columns), ("ksport", e.ksport),
                        ("check_in", e.check_in)):
        if table:
            out.append(f"{INDENT}{name}:")
            out += _mapping("", table, level=2)
    return out


def _branding(comp: Competition) -> list[str]:
    b = comp.branding
    kept = _kept(b, "header_img", "footer_img", "color", "signature",
                 "signature_label", "signature_mode", "signature_name",
                 "signature_scope", "name_style", "name_width")
    return _block("branding", [f"{INDENT}{k}: {scalar(v)}" for k, v in kept])


def _categories(comp: Competition) -> list[str]:
    lines = []
    for code in comp.cat_order():
        c = comp.categories[code]
        lines.append(f"{INDENT}{scalar(code)}: "
                     + flow(_kept(c, "name", "sex", "order")))
    return _block("categories", lines)


def _events(comp: Competition) -> list[str]:
    lines = []
    for code in comp.event_order():
        ev = comp.events[code]
        lines.append(f"{INDENT}{scalar(code)}:")
        for name, value in _kept(ev, "name", "short", "abbr", "fmt"):
            lines.append(f"{INDENT * 2}{name}: {scalar(value)}")
        if ev.team_size:
            lines.append(f"{INDENT * 2}team_size: {ev.team_size}")
        # 2 is the default and means nothing; 1 is the fact that decides
        # whether a qualifying round has batterie or a start order
        if ev.teams_per_start != 2:
            lines.append(f"{INDENT * 2}teams_per_start: {ev.teams_per_start}")
        if ev.entry_columns:
            lines.append(f"{INDENT * 2}entry_columns: "
                         f"{flow_list(ev.entry_columns)}")
        for name, value in _kept(ev, "startlist_note", "startlist_note_f",
                                 "qualifying_note", "qualifying_note_f",
                                 "finals_note", "finals_note_f"):
            lines.append(f"{INDENT * 2}{name}: {scalar(value)}")
        lines.append(f"{INDENT * 2}order: {ev.order}")
    return _block("events", lines)


def _quotas(comp: Competition) -> list[str]:
    q = comp.quotas
    lines = []
    if q.max_events_per_rider:
        lines.append(f"{INDENT}max_events_per_rider: "
                     + flow(list(q.max_events_per_rider.items())))
    lines.append(f"{INDENT}max_events_level: {scalar(q.max_events_level)}")
    lines.append(f"{INDENT}max_events_count_reserves: "
                 f"{scalar(q.max_events_count_reserves)}")
    for name, table in (("max_per_region", q.max_per_region),
                        ("max_same_club", q.max_same_club),
                        ("max_same_club_per_region", q.max_same_club_per_region),
                        ("max_teams_per_region", q.max_teams_per_region)):
        if table:
            lines.append(f"{INDENT}{name}:")
            lines += _mapping("", table, level=2)
    if q.exemptions:
        lines.append(f"{INDENT}exemptions:")
        lines += [f"{INDENT * 2}- {scalar(x)}" for x in q.exemptions]
    return _block("quotas", lines)


def _round(r: Round) -> str:
    """One round, on one line - the form the file has always been read in."""
    pairs: list[tuple[str, Any]] = [("key", r.key)]
    if r.label and r.label != r.key:
        pairs.append(("label", r.label))
    if r.kind:
        pairs.append(("kind", r.kind))
    pairs += _kept(r, "distance", "laps", "sprints", "heat_size", "qualify",
                   "eliminate", "note")
    # A round that is ridden always says which sheets it files: the default is
    # two of them, and a round that files three (a finals round with the
    # classifica of the specialità on it) has to be explicit. A setup round
    # files none, and that is its default too.
    default = [] if r.kind == ROUND_SETUP else [DOC_STARTLIST, DOC_RESULTS]
    if list(r.docs or []) != default:
        return (flow(pairs)[:-1] + f", docs: {flow_list(list(r.docs or []))}"
                + "}")
    return flow(pairs)


def _programme(comp: Competition) -> list[str]:
    """The running order, day by day, with a rule between the days.

    **In the order the list is in, never sorted.** That order is a decision -
    it is what `events_for` reads, and what a batch printed per giornata comes
    out in - so writing the file back must not quietly rearrange it. Reordering
    is something the page does when the jury asks for it, and then it is the
    list itself that changes.
    """
    lines: list[str] = []
    day = None
    for item in comp.programme:
        if item.day != day:
            day = item.day
            date = (comp.dates[day - 1]
                    if 0 < day <= len(comp.dates) else "")
            lines.append("")
            lines.append(f"{INDENT}# ── {msg('yaml_day', n=day)}"
                         + (f" · {date}" if date else "") + " "
                         + "─" * max(0, 46 - len(str(day)) - len(date)))
        lines.append(f"{INDENT}- cat: {scalar(item.cat)}")
        lines.append(f"{INDENT * 2}event: {scalar(item.event)}")
        lines.append(f"{INDENT * 2}day: {item.day}")
        for name, value in _kept(item, "time", "note"):
            lines.append(f"{INDENT * 2}{name}: {scalar(value)}")
        if item.rounds:
            lines.append(f"{INDENT * 2}rounds:")
            lines += [f"{INDENT * 3}- {_round(r)}" for r in item.rounds]
    return _block("programme", lines)


def _order(comp: Competition, item: ProgrammeItem) -> tuple:
    """Where a (category, event) sits inside its day.

    The register decides it: the first comunicato of a race is when it runs.
    Failing that - a race with no comunicato planned yet - it keeps the order
    the events are declared in, which is the only other thing that says
    anything.
    """
    numbers = [c.n for c in comp.communiques
               if c.cat == item.cat and c.event == item.event]
    return (min(numbers) if numbers else 10 ** 6,
            comp.event(item.event).order, item.cat)


def _communiques(comp: Competition) -> list[str]:
    lines: list[str] = []
    day = None
    for c in sorted(comp.communiques, key=lambda c: c.n):
        if c.day != day:
            day = c.day
            lines.append("")
            lines.append(f"{INDENT}# ── {msg('yaml_day', n=day)} "
                         + "─" * 46)
        pairs: list[tuple[str, Any]] = [
            ("n", c.n), ("day", c.day), ("cat", c.cat), ("event", c.event),
            ("round", c.round_key), ("doc", c.doc)]
        if c.ret:
            pairs.append(("ret", True))
        pairs.append(("title", c.title))
        text = f"{INDENT}- {flow(pairs)}"
        if c.extra:
            # the further documents of the same sheet, written short where they
            # are just another sheet of the same race
            text = (text[:-1] + ", with: ["
                    + ", ".join(_extra(s) for s in c.extra) + "]}")
        lines.append(text)
    return _block("communiques", lines)


def _extra(s: Sheet) -> str:
    """One entry of a `with:` list, written as short as it can be read.

    A document of the same race is just its name; anything that moves - another
    fase, another categoria - says which. A round written explicitly (`""`
    included) is kept: an omitted one means "the same fase", and the two are
    not the same statement (see `config.Sheet`).
    """
    if s.round_key is None and not s.cat and not s.event:
        return scalar(s.doc)
    pairs = _kept(s, "cat", "event")
    if s.round_key is not None:
        pairs.append(("round", s.round_key))
    pairs.append(("doc", s.doc))
    return flow(pairs)


# ── the whole file ──────────────────────────────────────────────────────────

SECTIONS = (
    ("competition", _competition_head),
    ("entries", _entries),
    ("branding", _branding),
    ("categories", _categories),
    ("events", _events),
    ("quotas", _quotas),
    ("programme", _programme),
    ("communiques", _communiques),
)


def dump(comp: Competition) -> str:
    """The whole programme as YAML, in the layout this module owns."""
    out = [msg("yaml_header", name=comp.name)]
    for name, build in SECTIONS:
        lines = build(comp)
        if not lines:
            continue
        out.append(f"\n# ── {msg(f'yaml_{name}')} "
                   + "─" * max(3, 60 - len(msg(f"yaml_{name}"))))
        out.append("\n".join(lines))
    return "\n".join(out).rstrip() + "\n"


def save(path: str | Path, comp: Competition, *, store=None) -> Path:
    """Write the programme, keeping the previous version as a snapshot.

    Through the store when there is one: that is what keeps a copy of every
    overwrite in `.snapshots/`, and a programme saved over a good one is
    exactly the case that copy exists for.
    """
    path = Path(path)
    text = dump(comp)
    if store is not None:
        rel = path.name if path.parent == Path(store.root) else str(path)
        return store.write_text(rel, text, action="save_programme",
                                snapshot=True)
    path.write_text(text, encoding="utf-8")
    return path


def reload(path: str | Path) -> Competition:
    """Read a programme back - what the round-trip guard compares against."""
    return load_competition(path)


# ── editing helpers ─────────────────────────────────────────────────────────
#
# The page edits tables; these turn a table back into the model. Kept here, out
# of `ui/`, because they are where the rules live: what a day holds, how a
# comunicato is renumbered, which sheets a round can file.

def days_of(comp: Competition) -> list[int]:
    """Every day the competition has, from the dates and from the programme.

    The dates decide: a four-day championship has four tabs even before
    anything is scheduled on the fourth. A programme item on a day the dates do
    not cover still gets one, so nothing is editable only by hand.
    """
    scheduled = {i.day for i in comp.programme if i.day}
    scheduled |= {c.day for c in comp.communiques if c.day}
    return sorted(set(range(1, len(comp.dates) + 1)) | scheduled) or [1]


def date_of(comp: Competition, day: int) -> str:
    return comp.dates[day - 1] if 0 < day <= len(comp.dates) else ""


def docs_available(comp: Competition, event: str) -> list[str]:
    """The sheets a round of this event can file.

    Every event files partenti, risultati and the classifica of the specialità.
    The others belong to a format: only a velocità rides a 5°-8° final, only a
    keirin publishes an ordine di partenza for its recuperi, only an omnium
    closes a prova on a classifica parziale.
    """
    fmt = comp.event(event).fmt
    out = [DOC_STARTLIST, DOC_RESULTS, DOC_CLASSIFICATION]
    extra = {
        "sprint": ["risultati_recuperi", "risultati_5-8"],
        "keirin": ["partenti_recuperi", "risultati_recuperi",
                   "risultati_finale_b"],
        "omnium": ["gara", "classifica_parziale"],
    }.get(fmt, [])
    return [d for d in DOC_ALL_KINDS if d in out + extra]


def renumber(specs: list[CommuniqueSpec], start: int = 1) -> list[CommuniqueSpec]:
    """Number the register 1..N in the order it is given.

    Numbers run continuously across the whole competition and are never reused:
    the order of the list *is* the order they go out in, which is the one thing
    the jury decides when it plans a day.
    """
    out = []
    n = start
    for spec in specs:
        out.append(replace_spec(spec, n=n))
        n += 1
    return out


def replace_spec(spec: CommuniqueSpec, **changes) -> CommuniqueSpec:
    from dataclasses import replace
    return replace(spec, **changes)


def moved(items: list, index: int, delta: int) -> list:
    """One row moved up or down - how a day is put in the order it is ridden."""
    out = list(items)
    target = index + delta
    if 0 <= index < len(out) and 0 <= target < len(out):
        out[index], out[target] = out[target], out[index]
    return out


def plan_day(comp: Competition, day: int, start: int) -> list[CommuniqueSpec]:
    """A register for one day, proposed from what is scheduled on it.

    A proposal and nothing more: the real order interleaves the specialità -
    the risultati of a batteria go out while another event is still on the
    track - and only the jury knows that. What this gets right is that nothing
    is *missing*, which is the tedious half.
    """
    out: list[CommuniqueSpec] = []
    n = start
    for item in sorted([i for i in comp.programme if i.day == day],
                       key=lambda i: _order(comp, i)):
        ev = comp.event(item.event)
        for rnd in item.rounds:
            for doc in rnd.docs or []:
                out.append(CommuniqueSpec(
                    n=n, day=day, cat=item.cat, event=item.event,
                    round_key="" if doc == DOC_CLASSIFICATION else rnd.key,
                    doc=doc,
                    title=title_for(item.cat, ev.short, rnd.label, doc)))
                n += 1
    return out


def rows_from_specs(specs: list[CommuniqueSpec]) -> list[dict]:
    """The register as a table: one row per *document*, not per comunicato.

    A comunicato that carries two sheets is two rows with the same number. That
    is the shape the jury edits in - a table where a number repeated is plainly
    one sheet with two documents on it - and `specs_from_rows` reads it back.
    """
    out: list[dict] = []
    for spec in sorted(specs, key=lambda c: c.n):
        for i, sheet in enumerate(spec.sheets):
            out.append({
                "n": spec.n, "day": spec.day, "cat": sheet.cat,
                "event": sheet.event, "round": sheet.round_key or "",
                "doc": sheet.doc,
                # the title and the RET mark belong to the sheet as a whole:
                # only its first row carries them
                "title": spec.title if i == 0 else "",
                "ret": spec.ret if i == 0 else False,
            })
    return out


def specs_from_rows(rows: list[dict]) -> list[CommuniqueSpec]:
    """Read the table back. Adjacent rows with one number are one comunicato.

    Adjacent on purpose: two rows far apart that happen to share a number are a
    mistake, and `issues` says so. Next to each other they are the jury saying
    "these print on one sheet".
    """
    out: list[CommuniqueSpec] = []
    for row in rows:
        n = _cell_int(row.get("n"))
        cat = _cell_text(row.get("cat"))
        event = _cell_text(row.get("event"))
        round_key = _cell_text(row.get("round"))
        doc = _cell_text(row.get("doc"))
        if out and out[-1].n == n:
            first = out[-1]
            out[-1].extra.append(Sheet(
                cat="" if cat == first.cat else cat,
                event="" if event == first.event else event,
                # only a round that differs is written: an omitted one means
                # "the same fase", which is what a recuperi sheet is
                round_key=None if round_key == first.round_key else round_key,
                doc=doc))
            continue
        out.append(CommuniqueSpec(
            n=n, day=_cell_int(row.get("day")), cat=cat, event=event,
            round_key=round_key, doc=doc, title=_cell_text(row.get("title")),
            ret=_cell_bool(row.get("ret"))))
    return out


# A row can come from a `st.data_editor`, where an empty cell is NaN: NaN is
# truthy and `int(NaN)` raises, so none of these may be read with a bare cast.

def _cell_text(value) -> str:
    return "" if value is None or value != value else str(value).strip()


def _cell_int(value) -> int:
    try:
        return 0 if value is None or value != value else int(float(value))
    except (TypeError, ValueError):
        return 0


def _cell_bool(value) -> bool:
    return bool(value) and value == value


def title_for(cat: str, event_short: str, round_label: str, doc: str) -> str:
    """`AL Velocità Turno 1 - Risultati` - the register's own wording."""
    from .i18n import label as _label
    bits = [cat, event_short, "" if doc == DOC_CLASSIFICATION else round_label]
    return " ".join(b for b in bits if b) + f" - {_label(doc)}"


# ── checks ──────────────────────────────────────────────────────────────────

def issues(comp: Competition, issued: list | None = None) -> list[Issue]:
    """What is wrong with a programme, before it is saved.

    Everything `config.validate` says about the shape, plus what only matters
    while it is being edited: a number that two sheets claim, a number already
    handed out that has been moved to another sheet, a gap in the sequence, a
    race with no comunicato planned at all.
    """
    out: list[Issue] = []
    seen: dict[int, CommuniqueSpec] = {}
    for c in sorted(comp.communiques, key=lambda c: c.n):
        if c.n in seen:
            out.append(Issue(ERROR, "communique_dup", msg(
                "cfg_duplicate_communique", n=c.n, a=seen[c.n].title,
                b=c.title)))
        seen[c.n] = c

    numbers = sorted(seen)
    gaps = [n for n in range(numbers[0], numbers[-1]) if n not in seen] \
        if numbers else []
    if gaps:
        out.append(Issue(WARN, "communique_gap", msg(
            "communique_gaps", list=", ".join(str(n) for n in gaps[:12]),
            more=" ..." if len(gaps) > 12 else "")))

    # a number already on paper that now names another sheet: the comunicato in
    # the jury's hands and the register would say two different things
    for i in issued or []:
        c = seen.get(i.n)
        if c is None or not i.doc:
            continue
        if not c.carries(i.cat, i.event, i.round_key, i.doc):
            out.append(Issue(ERROR, "communique_moved", msg(
                "communique_moved", n=i.n, was=i.title or i.doc,
                now=c.title or c.doc)))

    for item in comp.programme:
        if item.event == EVENT_ENTRY_LIST:
            continue
        if not item.rounds:
            out.append(Issue(ERROR, "round", msg(
                "cfg_no_rounds", cat=item.cat, event=item.event)))
        planned = [c for c in comp.communiques
                   if c.cat == item.cat and c.event == item.event]
        if not planned:
            out.append(Issue(INFO, "communique_missing", msg(
                "no_communique_planned", cat=item.cat,
                event=comp.event(item.event).short)))
    return out


# ── building a competition from scratch ─────────────────────────────────────

def blank(name: str, days: int = 1) -> Competition:
    """An empty programme, for a competition that has none yet.

    One day, no categories, no events: everything else the page adds. It exists
    so that starting a new championship is not copying a file by hand.
    """
    return Competition(name=name, dates=[""] * days)


def add_event(comp: Competition, code: str, name: str = "",
              fmt: str = "group") -> Event:
    ev = Event(code=code, name=name or code, fmt=fmt,
               order=len(comp.events) + 1)
    comp.events[code] = ev
    return ev


def add_category(comp: Competition, code: str, name: str = "",
                 sex: str = "") -> Category:
    cat = Category(code=code, name=name or code, sex=sex,
                   order=len(comp.categories) + 1)
    comp.categories[code] = cat
    return cat


def add_item(comp: Competition, cat: str, event: str, day: int,
             rounds: list[str] | None = None) -> ProgrammeItem:
    """Schedule a (category, event) on a day, with the rounds it is ridden in."""
    item = ProgrammeItem(cat=cat, event=event, day=day,
                         rounds=[Round(key=k) for k in (rounds or [])])
    comp.programme.append(item)
    return item
