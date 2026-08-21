"""The communiqué register: plan the numbers, then hand them out.

The register is authored in `programme.yaml` (for CITA 26 it is the 140-entry
list transcribed from *Lista Comunicati*, verified against the number printed
on every jury workbook). At print time a document takes its planned number; a
document that was not planned gets the next free one and is recorded, so the
register always reflects what was actually issued.

Numbers run continuously across the whole competition and are never reused; an
annulled document keeps its number and is marked `RET`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime

from .config import (DOC_CLASSIFICATION, DOC_STARTLIST, EVENT_ENTRY_LIST,
                     CommuniqueSpec, Competition, Sheet)
from .i18n import label
from .models import keep_known
from .programme import title_for
from .parse import duplicates as _duplicates

REGISTER_FILE = "comunicati.json"


@dataclass
class Issued:
    """A communiqué as actually produced."""

    n: int
    title: str = ""
    cat: str = ""
    event: str = ""
    round_key: str = ""
    doc: str = ""
    ret: bool = False
    issued_at: str = ""
    file: str = ""

    @property
    def label(self) -> str:
        return f"{self.n} RET" if self.ret else str(self.n)


# ── planning ────────────────────────────────────────────────────────────────

def planned(comp: Competition) -> list[CommuniqueSpec]:
    return sorted(comp.communiques, key=lambda c: c.n)


def plan_from_programme(comp: Competition) -> list[CommuniqueSpec]:
    """Propose a register from the running order, when none is authored.

    Documents are numbered day by day: first the entry lists, then for each
    event in programme order its startlist / results / classification.
    """
    out: list[CommuniqueSpec] = []
    n = 0
    for cat in comp.cat_order():
        n += 1
        out.append(CommuniqueSpec(n=n, day=1, cat=cat, event=EVENT_ENTRY_LIST,
                                  doc=DOC_STARTLIST,
                                  title=f"{label('entered').capitalize()} {cat}"))
    for day in comp.days():
        for r, rnd in comp.rounds_on(day):
            ev = comp.event(r.event)
            for doc in rnd.docs:
                n += 1
                bits = [r.cat, ev.short, rnd.label, "-", label(doc)]
                out.append(CommuniqueSpec(
                    n=n, day=day, cat=r.cat, event=r.event,
                    round_key=rnd.key, doc=doc,
                    title=" ".join(b for b in bits if b)))
    return out


def find(comp: Competition, cat: str, event: str, round_key: str, doc: str, *,
         exact: bool = False) -> CommuniqueSpec | None:
    """The planned entry for a document.

    By default a round_key that is not in the register falls back to any planned
    entry for the same (category, event, document) - good enough to
    pre-fill the field in the UI, where the jury sees and can correct it.
    `exact=True` disables that: issuing a number must never silently reuse the
    one planned for a different round_key.
    """
    pools = [[c for c in comp.communiques
              if c.carries(cat, event, round_key, doc)]]
    if not exact:
        pools.append([c for c in comp.communiques
                      for s in c.sheets
                      if s.cat == cat and s.event == event and s.doc == doc])
    for pool in pools:
        if pool:
            return sorted(pool, key=lambda c: c.n)[0]
    return None


#: What a sheet the register does not plan is numbered with. The risultati of
#: the prove di gruppo are the case: the register carries a comunicato for the
#: risultati of each batteria and for the classifica of the specialità, and none
#: for the risultati of the finale; an omnium files the risultati of a prova
#: unnumbered, because the sheet that goes out is the classifica parziale after
#: it. `-1` says so - it is visible in the field, it sorts before every real
#: number in the out folder, and it is not a number belonging to another sheet.
UNNUMBERED = "-1"


def number_for(comp: Competition, cat: str, event: str, round_key: str,
               doc: str) -> str:
    """The planned number of a sheet: this fase, then the specialità.

    A comunicato is planned for a fase (`Qualificazioni Batteria 1 -
    Risultati`) or for the specialità as a whole (`Madison - Classifica`, no
    fase). Anything else is a sheet the register does not carry: it opens on
    `-1`, and the jury gives it a number. Deliberately not `find`, which falls
    back to any entry for the same specialità: on the risultati of a finale that
    meant printing the number of the first batteria.
    """
    for want in (round_key, ""):
        for c in comp.communiques:
            if c.carries(cat, event, want, doc):
                return c.label
    return UNNUMBERED


# ── numbering: the order the sheets go out in ───────────────────────────────
#
# A number is not a property of a document: it is *when* the document goes out.
# So the register is a view of the running order, and while the programme is
# still being built the two are kept in step - move a race up the day and its
# comunicati move with it. That stops the moment a sheet is in somebody's
# hands: see `autonumber` for the three things that never move again.


def sheet_order(comp: Competition) -> list[Sheet]:
    """Every document the programme produces, in the order it is issued.

    Sorted on four things, in this order:

    1. **the day** - a competition is numbered continuously, day by day;
    2. **how deep the fase is** in its specialità - the qualificazioni are
       depth 0, the fase they compose is depth 1, and so on;
    3. **the startlist first**, results after;
    4. **the running order** the jury put the day's races in, and within a
       fase the order its documents print in.

    Two and three together are the rule as the jury states it: every ordine di
    partenza of the day goes out before any risultato, *unless* it is the start
    order of a fase that a previous fase composes - which cannot be published
    before the results that fill it. The 200 m start lists open the day; the
    start list of the finali comes out after the semifinali results, because
    its depth is higher, and nothing about the sort has to know why.
    """
    # The elenchi iscritti are not races and sit in no day's running order,
    # but they are the comunicati the competition opens with - one per
    # categoria, before anybody rides. `plan_from_programme` puts them first
    # too; here they sit at a depth below every fase, which is the same thing
    # said in the language of the sort.
    out: list[tuple[tuple, Sheet]] = [
        ((1, -1, 0, i, 0), Sheet(cat=cat, event=EVENT_ENTRY_LIST,
                                 round_key="", doc=DOC_STARTLIST))
        for i, cat in enumerate(comp.cat_order())]
    # the running order of each giornata, as the jury numbered it: a fase moved
    # up the scaletta takes its comunicati with it, which is the whole point of
    # the register being a view of the programme (`config.rounds_on`)
    rank = {(id(item), id(rnd)): (day, n)
            for day in comp.days()
            for n, (item, rnd) in enumerate(comp.rounds_on(day))}
    for index, item in enumerate(comp.programme):
        for depth, rnd in enumerate(item.rounds):
            day, place = rank.get((id(item), id(rnd)),
                                  (comp.day_of(item, rnd), index))
            # the fase's own `docs` list is the order its sheets go out in, and
            # it is not always the order of `DOC_ALL_KINDS`: a velocità rides
            # the 5°-8° before the finals 1°-4°, a keirin its second final
            # before the one for the title, and each files first
            for order, doc in enumerate(rnd.docs or []):
                # a classifica belongs to the specialità and to no fase: it is
                # the last thing that specialità files, whatever fase produced
                # the result behind it (see `config.Sheet`)
                key = (day, depth, 0 if doc == DOC_STARTLIST else 1,
                       place, order)
                out.append((key, Sheet(
                    cat=item.cat, event=item.event,
                    round_key="" if doc == DOC_CLASSIFICATION else rnd.key,
                    doc=doc)))
    return [sheet for _key, sheet in sorted(out, key=lambda p: p[0])]


def fixed_numbers(comp: Competition, register: list[Issued] | None = None
                  ) -> dict[tuple, int]:
    """The sheets whose number must not move, and the number each one has.

    Three reasons a number is fixed, and they are the same reason three times:
    somebody is expecting it. A comunicato the jury numbered by hand
    (`pinned`); one that has already been *issued* - printed, signed, handed to
    the teams; and an annullato (`ret`), which is a tombstone - the sheet is
    gone and the number stays spent, on the row that says so.

    The second is the error `programme.issues` raises after the fact; here it
    is prevented instead.
    """
    out: dict[tuple, int] = {}
    for c in comp.communiques:
        if c.pinned or c.ret:
            out[c.sheets[0].key] = c.n
    for i in register or []:
        out[Sheet(cat=i.cat, event=i.event, round_key=i.round_key,
                  doc=i.doc).key] = i.n
    return out


def autonumber(comp: Competition, register: list[Issued] | None = None,
               *, start: int = 1, add_missing: bool = True
               ) -> list[CommuniqueSpec]:
    """The register, renumbered from the running order.

    What the jury gets back is what it had - the same comunicati, carrying the
    same documents, keeping their own titles - with the numbers redealt in the
    order of `sheet_order`, flowing around the ones that are fixed
    (`fixed_numbers`). A sheet the programme produces and the register does not
    carry yet is added, unless `add_missing` says otherwise: a register the
    jury has finished deciding does not want a comunicato for every sheet -
    CITA 26 numbers 140 of its 166, because an omnium files the risultati of a
    prova unnumbered under the classifica parziale that follows it.

    **Nothing is ever thrown away.** An entry whose sheet the programme does
    not produce keeps the number it has and stays exactly where it is: it is
    either a document the rounds do not declare (the classifiche parziali of
    the CITA 26 omnium, carried by the register and by no `docs:` list) or a
    fase spelled differently in the two places (`Finali –` against `Finali`).
    Both are worth reporting - `programme.issues` does - and neither is worth
    silently deleting a line of the jury's own record over.

    Nothing here writes: it returns a list, and the page puts it on the draft.
    Frozen (`Competition.numbering_frozen`), the page does not call it at all.
    """
    fixed = fixed_numbers(comp, register)
    by_key = {c.sheets[0].key: c for c in comp.communiques}
    produced = {s.key for s in sheet_order(comp)} | _carried(by_key)
    # Numbers that cannot be handed out again: the fixed ones, the annullati
    # (the sheet is gone but the number stays spent), and the entries the
    # programme does not produce, which are staying where they are.
    orphans = [c for c in comp.communiques if c.sheets[0].key not in produced]
    taken = (set(fixed.values()) | {c.n for c in comp.communiques if c.ret}
             | {c.n for c in orphans})

    out: list[CommuniqueSpec] = []
    seen: set[tuple] = set()
    n = start - 1
    for sheet in sheet_order(comp):
        spec = by_key.get(sheet.key)
        if spec is not None and spec.sheets[0].key in seen:
            continue                      # a second document of the same sheet
        if spec is None and sheet.key in _carried(by_key):
            continue                      # ... and one that has no spec of its own
        if spec is None and not add_missing:
            continue                      # a sheet the jury numbers no comunicato for
        if spec is not None:
            seen.add(spec.sheets[0].key)
        if sheet.key in fixed:
            out.append(_renumbered(comp, spec, sheet, fixed[sheet.key]))
            continue
        n += 1
        while n in taken:
            n += 1
        out.append(_renumbered(comp, spec, sheet, n))
    return sorted(out + orphans, key=lambda c: c.n)


def _carried(by_key: dict[tuple, CommuniqueSpec]) -> set[tuple]:
    """Every sheet that rides on a comunicato numbered for another document."""
    return {s.key for c in by_key.values() for s in c.sheets[1:]}


def _renumbered(comp: Competition, spec: CommuniqueSpec | None, sheet: Sheet,
                n: int) -> CommuniqueSpec:
    """One entry at its new number, keeping everything the jury wrote on it."""
    if spec is not None:
        return replace(spec, n=n)
    ev = comp.event(sheet.event)
    rnd = comp.round_of(sheet.cat, sheet.event, sheet.round_key)
    return CommuniqueSpec(
        n=n, day=_day_of(comp, sheet), cat=sheet.cat, event=sheet.event,
        round_key=sheet.round_key, doc=sheet.doc,
        title=title_for(sheet.cat, ev.short, rnd.label, sheet.doc))


def _day_of(comp: Competition, sheet: Sheet) -> int:
    item = comp.scheduled(sheet.cat, sheet.event)
    return item.day if item else 0


# ── register of what was issued ─────────────────────────────────────────────

def load(store) -> list[Issued]:
    """Read the register, including files written before the English rename."""
    return [Issued(**keep_known(Issued, d))
            for d in store.read_json(REGISTER_FILE, [])]


def save(store, register: list[Issued], action: str = "register") -> None:
    store.write_json(REGISTER_FILE, [asdict(i) for i in register], action=action)


def next_free(comp: Competition, register: list[Issued]) -> int:
    used = {i.n for i in register} | {c.n for c in comp.communiques}
    n = 1
    while n in used:
        n += 1
    return n


def issue(store, comp: Competition, *, cat: str, event: str, round_key: str,
          doc: str, number: int | str = "", title: str = "",
          file: str = "") -> Issued:
    """Record a comunicato as issued, reusing its planned number when there is one."""
    register = load(store)
    if not number:
        planned_event = find(comp, cat, event, round_key, doc, exact=True)
        number = planned_event.n if planned_event else next_free(comp, register)
        title = title or (planned_event.title if planned_event else "")

    txt = str(number).strip().upper()
    ret = txt.endswith("RET")
    n = int("".join(ch for ch in txt if ch.isdigit()) or 0)

    entry = Issued(n=n, title=title, cat=cat, event=event, round_key=round_key, doc=doc,
                   ret=ret, issued_at=datetime.now().isoformat(timespec="seconds"),
                   file=file)
    register = [i for i in register if i.n != n] + [entry]
    register.sort(key=lambda i: i.n)
    save(store, register, action="issue_comunicato")
    return entry


def duplicates(register: list[Issued]) -> list[int]:
    """Numbers handed out more than once (see `parse.duplicates`)."""
    return _duplicates([i.n for i in register])


def status(comp: Competition, register: list[Issued]) -> list[dict]:
    """Register view: every planned document plus anything issued off-plan."""
    issued = {i.n: i for i in register}
    rows = []
    for c in planned(comp):
        i = issued.pop(c.n, None)
        rows.append({"n": c.n, "label": i.label if i else c.label,
                     "day": c.day, "cat": c.cat, "event": c.event,
                     "round_key": c.round_key, "doc": c.doc, "title": c.title,
                     # every document the number carries, the first included:
                     # a register that named only the first would not say what
                     # is actually on the sheet
                     "docs": [s.doc for s in c.sheets], "sheets": c.sheets,
                     "issued": bool(i), "issued_at": i.issued_at if i else "",
                     "file": i.file if i else ""})
    for i in sorted(issued.values(), key=lambda i: i.n):
        rows.append({"n": i.n, "label": i.label, "day": 0, "cat": i.cat,
                     "event": i.event, "round_key": i.round_key, "doc": i.doc,
                     "docs": [i.doc], "sheets": [],
                     "title": f"{i.title} ({label('off_plan')})", "issued": True,
                     "issued_at": i.issued_at, "file": i.file})
    return sorted(rows, key=lambda r: r["n"])
